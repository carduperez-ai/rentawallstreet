import os
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Tuple, Any

from src.domain.crypto_entities import Trade
from src.domain.fiscal_entities import Dividend
from src.accounting.currency_valuation import oracle

# ---------------------------------------------------------------------------
# Categorías de tipos según la API oficial de Kraken (ledgers.csv)
# ---------------------------------------------------------------------------
TRADE_TYPES = {"trade", "spend", "receive", "sale", "conversion", "nfttrade", "dust_sweep"}
INCOME_TYPES = {"staking", "reward", "dividend", "airdrop", "interest"}
# Tipos ignorados fiscalmente (movimientos, ajustes, comisiones NFT, etc.)
IGNORED_TYPES = {
    "deposit",
    "withdrawal",
    "transfer",
    "adjustment",
    "margin",
    "settled",
    "credit",
    "custodytransfer",
    "nftcreatorfee",
    "nftrebate",
}
FEE_TYPES = {"rollover"}

# Mapa de tickers internos de Kraken → símbolo estándar
_KRAKEN_ALIAS: Dict[str, str] = {
    "XXBT": "BTC",
    "XBT": "BTC",
    "XETH": "ETH",
    "XLTC": "LTC",
    "XREP": "REP",
    "XXMR": "XMR",
    "XXRP": "XRP",
    "XZEC": "ZEC",
    "XXLM": "XLM",
    "XDAO": "DAO",
    "ZEUR": "EUR",
    "ZUSD": "USD",
    "ZGBP": "GBP",
    "ZCAD": "CAD",
    "ZJPY": "JPY",
    "ZAUD": "AUD",
}

FIAT = {"EUR", "USD", "GBP", "CAD", "JPY", "AUD", "CHF"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_asset(raw: str) -> str:
    s = raw.strip().upper()
    return _KRAKEN_ALIAS.get(s, s)


def _parse_decimal(val: Any) -> Decimal:
    try:
        return Decimal(str(val).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_date(s: str) -> datetime:
    s = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.now()


def _safe_eur(amount: Decimal, asset: str, dt: datetime) -> Decimal:
    if amount == Decimal("0"):
        return Decimal("0")
    if asset == "EUR":
        return amount
    price = oracle.get_price_eur(asset, dt)
    return amount * price if price else Decimal("0")


# ---------------------------------------------------------------------------
# Lector principal
# ---------------------------------------------------------------------------


class KrakenIngestor:
    """
    Lector nativo para Kraken ledgers.csv.
    Cabeceras oficiales: txid, refid, time, type, subtype, aclass, asset, amount, fee, balance
    """

    def __init__(self):
        self.warnings: List[str] = []
        self._rows: List[Dict] = []
        self._pdf_trades: List[Trade] = []
        self._pdf_dividends: List[Dividend] = []

    def process_file(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)

        if ext == ".pdf":
            from src.ingestion.universal_pdf_reader import UniversalPDFReader

            t, d = UniversalPDFReader().parse(file_path, platform="KRAKEN")
            self._pdf_trades.extend(t)
            self._pdf_dividends.extend(d)
            return True

        if ext not in (".csv", ".xlsx", ".xls"):
            self.warnings.append(f"Kraken ignora formato no soportado: {filename}")
            return False

        try:
            if ext in (".xlsx", ".xls"):
                import pandas as pd

                df = pd.read_excel(file_path, header=0)
                # rellenar nans para no fallar el DictReader simulado
                df = df.fillna("")
                self._rows.extend(df.to_dict("records"))
            else:
                with open(file_path, newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    self._rows.extend(list(reader))
            return True
        except Exception as e:
            self.warnings.append(f"Error leyendo {filename}: {e}")
            return False

    # -----------------------------------------------------------------------
    # Propiedades calculadas
    # -----------------------------------------------------------------------

    @property
    def transactions(self) -> List[Trade]:
        trades: List[Trade] = list(self._pdf_trades)
        # Agrupar por refid para emparejar piernas de un mismo trade
        groups: Dict[str, List[Dict]] = {}
        for row in self._rows:
            tx_type = row.get("type", "").strip().lower()
            if tx_type not in TRADE_TYPES:
                continue
            refid = row.get("refid", "").strip() or row.get("txid", "").strip()
            groups.setdefault(refid, []).append(row)

        for refid, legs in groups.items():
            # Separar piernas negativas (vendidas) y positivas (compradas)
            sold_legs = [r for r in legs if _parse_decimal(r.get("amount", 0)) < 0]
            bought_legs = [r for r in legs if _parse_decimal(r.get("amount", 0)) > 0]

            if not sold_legs or not bought_legs:
                # Puede ser una sola pierna (p.ej. nfttrade sin contrapartida)
                for r in legs:
                    amt = _parse_decimal(r.get("amount", 0))
                    if amt == 0:
                        continue
                    dt = _parse_date(r.get("time", ""))
                    asset = _normalize_asset(r.get("asset", "UNKNOWN"))
                    fee_eur = _safe_eur(_parse_decimal(r.get("fee", 0)), asset, dt)
                    val_eur = _safe_eur(abs(amt), asset, dt)
                    direction = "buy" if amt > 0 else "sell"
                    trades.append(
                        Trade(
                            date=dt,
                            asset=asset,
                            platform="Kraken",
                            direction=direction,
                            quantity=abs(amt),
                            value_eur=val_eur,
                            fee_eur=fee_eur,
                            asset_type="crypto",
                            notes=f"Kraken {r.get('type', '?')} | refid:{refid}",
                        )
                    )
                continue

            # Caso normal: par sell/buy
            dt = _parse_date(sold_legs[0].get("time", ""))

            sold_asset = _normalize_asset(sold_legs[0].get("asset", "UNKNOWN"))
            sold_qty = abs(sum(_parse_decimal(r["amount"]) for r in sold_legs))
            sold_fee = sum(_parse_decimal(r.get("fee", 0)) for r in sold_legs)

            bought_asset = _normalize_asset(bought_legs[0].get("asset", "UNKNOWN"))
            bought_qty = sum(_parse_decimal(r["amount"]) for r in bought_legs)
            bought_fee = sum(_parse_decimal(r.get("fee", 0)) for r in bought_legs)

            # Valoración: usamos el lado fiat/stable si existe, si no el oráculo
            if sold_asset in FIAT:
                val_eur = _safe_eur(sold_qty, sold_asset, dt)
            elif bought_asset in FIAT:
                val_eur = _safe_eur(bought_qty, bought_asset, dt)
            else:
                val_eur = _safe_eur(sold_qty, sold_asset, dt)

            fee_eur = _safe_eur(sold_fee + bought_fee, sold_asset if sold_asset not in FIAT else bought_asset, dt)
            notes = f"Kraken trade | refid:{refid}"

            # VENTA del activo saliente (si no es fiat)
            if sold_asset not in FIAT:
                trades.append(
                    Trade(
                        date=dt,
                        asset=sold_asset,
                        platform="Kraken",
                        direction="sell",
                        quantity=sold_qty,
                        value_eur=val_eur,
                        fee_eur=fee_eur,
                        asset_type="crypto",
                        notes=notes,
                    )
                )

            # COMPRA del activo entrante (si no es fiat)
            if bought_asset not in FIAT:
                trades.append(
                    Trade(
                        date=dt,
                        asset=bought_asset,
                        platform="Kraken",
                        direction="buy",
                        quantity=bought_qty,
                        value_eur=val_eur,
                        fee_eur=fee_eur,
                        asset_type="crypto",
                        notes=notes,
                    )
                )

        return sorted(trades, key=lambda t: t.date)

    @property
    def dividends(self) -> List[Dividend]:
        result: List[Dividend] = list(self._pdf_dividends)
        for row in self._rows:
            tx_type = row.get("type", "").strip().lower()
            if tx_type not in INCOME_TYPES and tx_type not in FEE_TYPES:
                continue
            amt = _parse_decimal(row.get("amount", 0))
            if amt == 0:
                continue
            dt = _parse_date(row.get("time", ""))
            asset = _normalize_asset(row.get("asset", "UNKNOWN"))
            val_eur = _safe_eur(abs(amt), asset, dt)

            if tx_type in FEE_TYPES:
                result.append(
                    Dividend(
                        date=dt,
                        platform="Kraken",
                        asset=asset,
                        isin="",
                        gross_eur=Decimal("0"),
                        withholding_foreign_eur=Decimal("0"),
                        withholding_spain_eur=Decimal("0"),
                        type="fee",
                        custody_fee_eur=val_eur,
                    )
                )
            else:
                income_type = "staking" if tx_type in ("staking", "reward") else "dividend"
                result.append(
                    Dividend(
                        date=dt,
                        platform="Kraken",
                        asset=asset,
                        isin="",
                        gross_eur=val_eur,
                        withholding_foreign_eur=Decimal("0"),
                        withholding_spain_eur=Decimal("0"),
                        type=income_type,
                    )
                )
        return result


# ---------------------------------------------------------------------------
# Punto de entrada público (mismo contrato que binance_reader)
# ---------------------------------------------------------------------------


def parse(file_paths: List[str]) -> Tuple[List[Trade], List[Dividend]]:
    ingestor = KrakenIngestor()
    for path in file_paths:
        ingestor.process_file(path)
    return ingestor.transactions, ingestor.dividends
