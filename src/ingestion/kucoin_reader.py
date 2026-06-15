import os
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Tuple, Any, Dict

from src.domain.crypto_entities import Trade, Dividend
from src.accounting.currency_valuation import oracle

# ---------------------------------------------------------------------------
# KuCoin CSV — dos formatos posibles en el mismo lector:
#
# A) Historial Spot (Trading):
#    Cabeceras: Time, Symbol, Side, Price, Amount, Fee, Fee Coin
#    Side values: Buy, Sell
#
# B) Historial Funding (Cuenta principal):
#    Cabeceras: Time, Type, Coin, Amount, Status, Remark
#    Type values: Deposit, Withdrawal, Transfer, Staking, Reward,
#                 Airdrop, Lending, Borrowing
# ---------------------------------------------------------------------------

SPOT_SIGNATURE = {"symbol", "side", "fee coin"}
FUNDING_SIGNATURE = {"coin", "type", "remark"}

FUNDING_INCOME = {"staking", "reward", "airdrop", "returned_fees"}
FUNDING_FEE = {"lending", "borrowing", "interest", "margin interest", "deduction_fees"}
FUNDING_IGNORE = {"deposit", "withdrawal", "transfer"}

FIAT = {"EUR", "USD", "USDT", "USDC", "BUSD", "DAI", "FDUSD"}

# Pares de quote assets habituales en KuCoin (para dividir Symbol)
QUOTE_ASSETS = ["USDT", "USDC", "BTC", "ETH", "KCS", "EUR", "BUSD", "DAI"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dec(val: Any) -> Decimal:
    try:
        return Decimal(str(val).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_date(s: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            continue
    return datetime.now()


def _to_eur(amount: Decimal, asset: str, dt: datetime) -> Decimal:
    if amount == Decimal("0"):
        return Decimal("0")
    a = asset.upper()
    if a == "EUR":
        return amount
    price = oracle.get_price_eur(a, dt)
    return amount * price if price else Decimal("0")


def _split_symbol(symbol: str):
    """Divide 'BTC-USDT' o 'BTCUSDT' en (base, quote)."""
    s = symbol.upper().strip()
    if "-" in s:
        parts = s.split("-", 1)
        return parts[0], parts[1]
    for q in QUOTE_ASSETS:
        if s.endswith(q) and len(s) > len(q):
            return s[: -len(q)], q
    return s, "UNKNOWN"


def _detect_format(headers) -> str:
    """Devuelve 'spot', 'funding' o 'unknown'."""
    h_norm = {h.strip().lower() for h in headers}
    if SPOT_SIGNATURE.issubset(h_norm):
        return "spot"
    if FUNDING_SIGNATURE.issubset(h_norm):
        return "funding"
    return "unknown"


# ---------------------------------------------------------------------------
# Lector principal
# ---------------------------------------------------------------------------


class KuCoinIngestor:
    """
    Lector nativo para exportaciones CSV de KuCoin.
    Autodetecta si el archivo es Spot Trading o Funding (cuenta principal).
    """

    def __init__(self):
        self.warnings: List[str] = []
        self._spot_rows: List[Dict] = []
        self._funding_rows: List[Dict] = []
        self._pdf_trades: List[Trade] = []
        self._pdf_dividends: List[Dividend] = []

    def process_file(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)

        if ext == ".pdf":
            from src.ingestion.universal_pdf_reader import UniversalPDFReader

            t, d = UniversalPDFReader().parse(file_path, platform="KUCOIN")
            self._pdf_trades.extend(t)
            self._pdf_dividends.extend(d)
            return True

        if ext not in (".csv", ".xlsx", ".xls"):
            self.warnings.append(f"KuCoin ignora formato no soportado: {filename}")
            return False

        try:
            if ext in (".xlsx", ".xls"):
                import pandas as pd

                df = pd.read_excel(file_path)
                df = df.fillna("")
                rows = df.to_dict("records")
            else:
                with open(file_path, newline="", encoding="utf-8-sig") as fh:
                    reader = csv.DictReader(fh)
                    rows = list(reader)

            if not rows:
                return True

            fmt = _detect_format(rows[0].keys())
            if fmt == "spot":
                self._spot_rows.extend(rows)
            elif fmt == "funding":
                self._funding_rows.extend(rows)
            else:
                self.warnings.append(
                    f"Formato KuCoin no reconocido en {filename}. " f"Cabeceras: {list(rows[0].keys())}"
                )
                return False

            return True
        except Exception as e:
            self.warnings.append(f"Error leyendo {filename}: {e}")
            return False

    # -----------------------------------------------------------------------
    # Helpers internos
    # -----------------------------------------------------------------------

    @staticmethod
    def _g(row: Dict, *keys: str) -> str:
        for k in keys:
            if k in row:
                return str(row[k]).strip()
            for rk in row:
                if rk.strip().lower() == k.lower():
                    return str(row[rk]).strip()
        return ""

    # -----------------------------------------------------------------------
    # Propiedades calculadas
    # -----------------------------------------------------------------------

    @property
    def transactions(self) -> List[Trade]:
        trades: List[Trade] = list(self._pdf_trades)

        for row in self._spot_rows:
            g = lambda *k: self._g(row, *k)

            dt = _parse_date(g("Time"))
            symbol = g("Symbol")
            side = g("Side").strip().lower()
            price = _dec(g("Price"))
            amount = _dec(g("Amount"))  # cantidad de asset base
            fee = _dec(g("Fee"))
            fee_coin = g("Fee Coin").upper()

            base, quote = _split_symbol(symbol)
            if base == "UNKNOWN":
                self.warnings.append(f"No se pudo dividir el par '{symbol}'")
                continue

            # Valor de la operación: price * amount (en quote currency)
            raw_value = price * amount
            val_eur = _to_eur(raw_value, quote, dt)
            fee_eur = _to_eur(fee, fee_coin, dt)

            trades.append(
                Trade(
                    date=dt,
                    asset=base,
                    platform="KuCoin",
                    direction="buy" if "buy" in side else "sell",
                    quantity=amount,
                    value_eur=val_eur,
                    fee_eur=fee_eur,
                    asset_type="crypto",
                    notes=f"KuCoin Spot | {symbol}",
                )
            )

        return sorted(trades, key=lambda t: t.date)

    @property
    def dividends(self) -> List[Dividend]:
        result: List[Dividend] = list(self._pdf_dividends)
        for row in self._funding_rows:
            g = lambda *k: self._g(row, *k)

            tx_type = g("Type").strip().lower()
            status = g("Status").strip().lower()

            if tx_type in FUNDING_IGNORE:
                continue
            if tx_type not in FUNDING_INCOME and tx_type not in FUNDING_FEE:
                continue
            # Solo procesar operaciones completadas
            if status and status not in ("completed", "success", ""):
                continue

            dt = _parse_date(g("Time"))
            coin = g("Coin").upper()
            raw_amt = _dec(g("Amount"))
            amount = abs(raw_amt)
            val_eur = _to_eur(amount, coin, dt)

            if tx_type in FUNDING_FEE:
                # Si el monto es negativo, es un pago de interés o fee.
                # Si es positivo, es recepción del préstamo (principal) que ignoramos.
                if raw_amt < Decimal("0") or "interest" in tx_type:
                    result.append(
                        Dividend(
                            date=dt,
                            platform="KuCoin",
                            asset=coin,
                            isin="",
                            gross_eur=Decimal("0"),
                            withholding_foreign_eur=Decimal("0"),
                            withholding_spain_eur=Decimal("0"),
                            type="fee",
                            custody_fee_eur=val_eur,
                        )
                    )
                continue

            income_type = "staking" if tx_type in ("staking", "reward") else "other_income"

            result.append(
                Dividend(
                    date=dt,
                    platform="KuCoin",
                    asset=coin,
                    isin="",
                    gross_eur=val_eur,
                    withholding_foreign_eur=Decimal("0"),
                    withholding_spain_eur=Decimal("0"),
                    type=income_type,
                )
            )

        return result


# ---------------------------------------------------------------------------
# Punto de entrada público
# ---------------------------------------------------------------------------


def parse(file_paths) -> Tuple[List[Trade], List[Dividend]]:
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    ingestor = KuCoinIngestor()
    for path in file_paths:
        ingestor.process_file(path)
    return ingestor.transactions, ingestor.dividends
