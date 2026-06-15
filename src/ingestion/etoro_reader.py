import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Any, Dict

import pandas as pd

from src.domain.stock_entities import Trade as StockTrade
from src.domain.stock_fiscal_entities import Dividend as StockDividend
from src.domain.crypto_entities import Trade as CryptoTrade
from src.domain.fiscal_entities import Dividend as CryptoDividend
from src.accounting.currency_valuation import oracle

# ---------------------------------------------------------------------------
# eToro Account Statement Excel
# Pestaña A — Account Activity:
#   Date, Type, Details, Amount, Realized Equity Change,
#   Realized Equity, Balance, Position ID, NWA
# Pestaña B — Closed Positions:
#   Position ID, Action, Amount, Units, Open Date, Close Date,
#   Leverage, Spread, Profit, Is Real
#
# Type values (Account Activity): Deposit, Withdrawal, Open Position,
#   Position closed, Rollover Fee, Dividend,
#   Payment caused by dividend, Corporate Action, AirDrop, Staking
# Action values (Closed Positions): Buy, Sell
# ---------------------------------------------------------------------------

ACTIVITY_INCOME = {"airdrop", "staking"}
ACTIVITY_FEE = {"rollover fee", "payment caused by dividend"}
ACTIVITY_IGNORE = {"deposit", "withdrawal", "open position", "position closed", "corporate action"}

CRYPTO_KEYWORDS = {
    "btc",
    "eth",
    "xrp",
    "ltc",
    "ada",
    "sol",
    "dot",
    "bnb",
    "doge",
    "shib",
    "avax",
    "matic",
    "link",
    "uni",
    "xlm",
    "crypto",
    "bitcoin",
    "ethereum",
    "ripple",
    "litecoin",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dec(val: Any) -> Decimal:
    try:
        s = str(val).strip().replace(",", "").replace("$", "").replace("€", "")
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_date(val: Any) -> datetime:
    if isinstance(val, datetime):
        return val
    if hasattr(val, "to_pydatetime"):
        return val.to_pydatetime().replace(tzinfo=None)
    s = str(val).strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.now()


def _usd_to_eur(amount: Decimal, dt: datetime) -> Decimal:
    if amount == Decimal("0"):
        return Decimal("0")
    price = oracle.get_price_eur("USD", dt)
    return amount * price if price else amount * Decimal("0.92")


def _is_crypto(name: str) -> bool:
    n = str(name).lower()
    return any(k in n for k in CRYPTO_KEYWORDS)


def _read_sheet(path: str, sheet_name: str) -> pd.DataFrame:
    """Lee una hoja del Excel de eToro buscándola por nombre (insensible a mayúsculas)."""
    xl = pd.ExcelFile(path)
    for sn in xl.sheet_names:
        if sn.strip().lower() == sheet_name.lower():
            return pd.read_excel(path, sheet_name=sn)
    # No encontrada → DataFrame vacío
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Lector principal
# ---------------------------------------------------------------------------


class EToroIngestor:
    """
    Lector para el Excel de estado de cuenta de eToro.
    Procesa las pestañas 'Account Activity' y 'Closed Positions'.
    """

    def __init__(self):
        self.warnings: List[str] = []
        self._activity_rows: List[Dict] = []  # Account Activity
        self._positions_rows: List[Dict] = []  # Closed Positions
        self._dividends_rows: List[Dict] = []  # Dividends
        self._pdf_trades: List[Trade] = []
        self._pdf_dividends: List[Dividend] = []

    def process_file(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)

        if ext == ".pdf":
            from src.ingestion.universal_pdf_reader import UniversalPDFReader

            t, d = UniversalPDFReader().parse(file_path, platform="ETORO")
            self._pdf_trades.extend(t)
            self._pdf_dividends.extend(d)
            return True

        if ext not in (".xlsx", ".xls", ".csv"):
            self.warnings.append(f"eToro ignora formato no soportado: {filename}")
            return False

        try:
            if ext == ".csv":
                df_activity = pd.read_csv(file_path)
                df_positions = pd.DataFrame()
                df_dividends = pd.DataFrame()
            else:
                df_activity = _read_sheet(file_path, "Account Activity")
                df_positions = _read_sheet(file_path, "Closed Positions")
                df_dividends = _read_sheet(file_path, "Dividends")

            if df_activity.empty and df_positions.empty:
                self.warnings.append(
                    f"No se encontraron las pestañas 'Account Activity' o 'Closed Positions' en {filename}"
                )
                return False

            # Normalizar cabeceras
            def norm_df(df: pd.DataFrame) -> List[Dict]:
                if df.empty:
                    return []
                df.columns = [str(c).strip() for c in df.columns]
                return df.to_dict("records")

            self._activity_rows.extend(norm_df(df_activity))
            self._positions_rows.extend(norm_df(df_positions))
            self._dividends_rows.extend(norm_df(df_dividends))
            return True

        except Exception as e:
            self.warnings.append(f"Error leyendo {filename}: {e}")
            return False

    # -----------------------------------------------------------------------
    # Helpers de acceso a fila
    # -----------------------------------------------------------------------

    @staticmethod
    def _g(row: Dict, *keys: str) -> str:
        for k in keys:
            if k in row and pd.notna(row[k]):
                return str(row[k]).strip()
            for rk in row:
                if rk.lower() == k.lower() and pd.notna(row[rk]):
                    return str(row[rk]).strip()
        return ""

    # -----------------------------------------------------------------------
    # Propiedades calculadas
    # -----------------------------------------------------------------------

    @property
    def transactions(self):
        trades = list(self._pdf_trades)

        # 1. Extraer cierres desde Closed Positions
        for row in self._positions_rows:
            is_real = self._g(row, "Is Real").upper()
            # Ignorar operaciones demo
            if is_real in ("FALSE", "NO", "0", "N"):
                continue

            action = self._g(row, "Action").strip().upper()
            details = self._g(row, "Details", "Action")  # nombre del activo
            units_str = self._g(row, "Units")
            amount_str = self._g(row, "Amount")  # tamaño de posición en USD
            profit_str = self._g(row, "Profit")  # P&L en USD
            open_date = _parse_date(self._g(row, "Open Date"))
            close_date = _parse_date(self._g(row, "Close Date"))
            leverage = _dec(self._g(row, "Leverage"))

            units = abs(_dec(units_str))
            position_sz = abs(_dec(amount_str))  # coste de apertura (USD)
            profit_usd = _dec(profit_str)  # puede ser negativo

            if units == Decimal("0") or position_sz == Decimal("0"):
                continue

            # Precio de apertura y cierre por unidad (USD)
            open_price_usd = position_sz / units
            close_proceeds_usd = position_sz + profit_usd  # total recibido al cerrar

            asset = self._g(row, "Details") or details or "UNKNOWN"
            is_cr = _is_crypto(asset)
            asset_type = "crypto" if is_cr else "stock"

            # Conversión a EUR
            open_val_eur = _usd_to_eur(position_sz, open_date)
            close_val_eur = _usd_to_eur(abs(close_proceeds_usd), close_date)

            notes_suffix = f"Leverage x{int(leverage)}" if leverage > 1 else ""
            notes_base = f"eToro | {asset} | {notes_suffix}".strip(" |")

            # Trade de COMPRA en la fecha de apertura
            if is_cr:
                trades.append(
                    CryptoTrade(
                        date=open_date,
                        asset=asset,
                        platform="eToro",
                        direction="buy",
                        quantity=units,
                        value_eur=open_val_eur,
                        fee_eur=Decimal("0"),
                        asset_type=asset_type,
                        notes=notes_base,
                    )
                )
                # Trade de VENTA en la fecha de cierre
                trades.append(
                    CryptoTrade(
                        date=close_date,
                        asset=asset,
                        platform="eToro",
                        direction="sell",
                        quantity=units,
                        value_eur=close_val_eur,
                        fee_eur=Decimal("0"),
                        asset_type=asset_type,
                        notes=notes_base,
                    )
                )
            else:
                trades.append(
                    StockTrade(
                        date=open_date,
                        platform="eToro",
                        asset=asset,
                        isin="",
                        ticker=asset,
                        asset_type=asset_type,
                        direction="buy",
                        quantity=units,
                        value_eur=open_val_eur,
                        fee_eur=Decimal("0"),
                        notes=notes_base,
                    )
                )
                trades.append(
                    StockTrade(
                        date=close_date,
                        platform="eToro",
                        asset=asset,
                        isin="",
                        ticker=asset,
                        asset_type=asset_type,
                        direction="sell",
                        quantity=units,
                        value_eur=close_val_eur,
                        fee_eur=Decimal("0"),
                        notes=notes_base,
                    )
                )

        # 2. Extraer aperturas/compras de Account Activity
        return sorted(trades, key=lambda t: t.date)

    @property
    def dividends(self):
        result = list(self._pdf_dividends)
        for row in self._dividends_rows:
            dt = _parse_date(self._g(row, "Date of Payment", "Date"))
            asset = self._g(row, "Instrument Name", "Asset")
            net_usd = _dec(self._g(row, "Net Dividend Received (USD)", "Net Dividend Received"))
            withhold_usd = _dec(self._g(row, "Withholding Tax Amount (USD)", "Withholding Tax Amount"))

            gross_usd = net_usd + withhold_usd
            gross_eur = _usd_to_eur(gross_usd, dt)
            withhold_eur = _usd_to_eur(withhold_usd, dt)

            is_cr = _is_crypto(asset)
            if is_cr:
                result.append(
                    CryptoDividend(
                        date=dt,
                        platform="eToro",
                        asset=asset,
                        isin="",
                        gross_eur=gross_eur,
                        withholding_foreign_eur=withhold_eur,
                        withholding_spain_eur=Decimal("0"),
                        type="dividend",
                    )
                )
            else:
                result.append(
                    StockDividend(
                        date=dt,
                        platform="eToro",
                        asset=asset,
                        isin="",
                        gross_eur=gross_eur,
                        withholding_foreign_eur=withhold_eur,
                        withholding_spain_eur=Decimal("0"),
                        type="dividend",
                    )
                )

        for row in self._activity_rows:
            tx_type = self._g(row, "Type").lower().strip()

            if tx_type not in ACTIVITY_INCOME and tx_type not in ACTIVITY_FEE:
                continue

            dt = _parse_date(self._g(row, "Date"))
            details = self._g(row, "Details")
            amount = _dec(self._g(row, "Amount"))
            val_eur = _usd_to_eur(abs(amount), dt)
            is_cr = _is_crypto(details)

            if tx_type in ("airdrop", "staking"):
                result.append(
                    CryptoDividend(
                        date=dt,
                        platform="eToro",
                        asset=details,
                        isin="",
                        gross_eur=val_eur,
                        withholding_foreign_eur=Decimal("0"),
                        withholding_spain_eur=Decimal("0"),
                        type="staking",
                    )
                )

            elif tx_type in ACTIVITY_FEE:
                # payment caused by dividend / Rollover Fee
                result.append(
                    StockDividend(
                        date=dt,
                        platform="eToro",
                        asset=details,
                        isin="",
                        gross_eur=Decimal("0"),
                        withholding_foreign_eur=Decimal("0"),
                        withholding_spain_eur=Decimal("0"),
                        type="fee",
                        custody_fee_eur=val_eur,
                    )
                )

        return result


# ---------------------------------------------------------------------------
# Punto de entrada público
# ---------------------------------------------------------------------------


def parse(file_paths) -> tuple:
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    ingestor = EToroIngestor()
    for path in file_paths:
        ingestor.process_file(path)
    return ingestor.transactions, ingestor.dividends
