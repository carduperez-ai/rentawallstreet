import os
import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Tuple, Any, Dict

from src.domain.stock_entities import Trade as StockTrade
from src.domain.stock_fiscal_entities import Dividend as StockDividend
from src.accounting.currency_valuation import oracle

# ---------------------------------------------------------------------------
# IBKR Flex Query CSV
# A) Sección Trades: identifica por presencia de columna "BuySell"
#    Cabeceras clave: Symbol, ISIN, Currency, FXRateToBase, Quantity, Proceeds,
#                    Commissions, IBCommission, BuySell, DateTime, TradeType
# B) Sección Cash Transactions: identifica por columna "Type" sin "BuySell"
#    Cabeceras clave: Symbol, ISIN, Currency, FXRateToBase, Amount, Type, DateTime
#
# TradeType values: ExchTrade, FracShare, CorpAct, TradeCancel, FracShareCancel
# Cash Type values: Deposits, Withdrawals, Dividends, Withholding Tax,
#                   Broker Interest Paid, Broker Interest Received,
#                   Payment in Lieu of Dividends, Corporate Action
# ---------------------------------------------------------------------------

TRADE_CANCELS = {"tradecancel", "fracsharcancel", "fracsharecancel"}
CASH_INCOME = {"dividends", "payment in lieu of dividends", "broker interest received"}
CASH_WITHHOLD = {"withholding tax"}
CASH_FEE = {"broker interest paid"}
CASH_IGNORE = {"deposits", "withdrawals", "corporate action"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dec(val: Any) -> Decimal:
    try:
        return Decimal(str(val).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_date(s: str) -> datetime:
    s = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d %H%M%S", "%Y-%m-%d", "%Y%m%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.now()


def _to_eur(amount: Decimal, currency: str, fx_rate: Decimal, dt: datetime) -> Decimal:
    """
    Convierte amount (en `currency`) a EUR usando FXRateToBase de IBKR.
    FXRateToBase = unidades de divisa base (EUR) por 1 unidad de currency.
    """
    if amount == Decimal("0"):
        return Decimal("0")
    cu = currency.upper()
    if cu == "EUR":
        return amount
    # IBKR proporciona FXRateToBase directamente; usarlo si es válido
    if fx_rate and fx_rate > 0:
        return amount * fx_rate
    # Fallback: oráculo
    price = oracle.get_price_eur(cu, dt)
    return amount * price if price else Decimal("0")


def _norm_headers(headers) -> Dict[str, str]:
    """Devuelve mapa {nombre_normalizado: nombre_original}."""
    return {h.strip().lower(): h for h in headers}


# ---------------------------------------------------------------------------
# Lector principal
# ---------------------------------------------------------------------------


class IBKRIngestor:
    """
    Lector para exportaciones Flex Query de Interactive Brokers.
    Soporta la sección de Trades y la de Cash Transactions,
    bien en ficheros separados o en el mismo archivo (IBKR multi-sección).
    """

    def __init__(self):
        self.warnings: List[str] = []
        self._trade_rows: List[Dict] = []
        self._cash_rows: List[Dict] = []
        self._dividend_rows: List[Dict] = []
        self._corpact_rows: List[Dict] = []
        self._pdf_trades: List[StockTrade] = []
        self._pdf_dividends: List[StockDividend] = []

    def process_file(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)

        if ext == ".pdf":
            from src.ingestion.universal_pdf_reader import UniversalPDFReader

            t, d = UniversalPDFReader().parse(file_path, platform="IBKR")
            self._pdf_trades.extend(t)
            self._pdf_dividends.extend(d)
            return True

        if ext not in (".csv", ".txt", ".xlsx", ".xls"):
            self.warnings.append(f"IBKR ignora formato no soportado: {filename}")
            return False

        try:
            if ext in (".xlsx", ".xls"):
                import pandas as pd

                df = pd.read_excel(file_path)
                df = df.fillna("")
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                content = csv_buffer.getvalue()
            else:
                with open(file_path, newline="", encoding="utf-8-sig") as fh:
                    content = fh.read()

            # ── Detección de formato multi-sección ────────────────────────
            # IBKR Flex Query puede tener líneas con la primera columna como
            # nombre de sección (p.ej. "Trades,Header,..." / "Trades,Data,...").
            # Detectamos si la primera columna es no numérica y no un campo estándar.
            lines = content.splitlines()
            first_fields = [l.split(",")[0].strip() for l in lines if l.strip()]
            section_markers = {"trades", "cashtransactions", "cash transactions", "openpositions", "statement"}
            is_multisection = any(f.lower() in section_markers for f in first_fields)

            if is_multisection:
                self._parse_multisection(lines)
            else:
                # Archivo de una sola sección: detectar tipo por columnas
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)
                if not rows:
                    return True
                headers_norm = _norm_headers(rows[0].keys())
                if "buysell" in headers_norm:
                    self._trade_rows.extend(rows)
                else:
                    self._cash_rows.extend(rows)

            return True
        except Exception as e:
            self.warnings.append(f"Error leyendo {filename}: {e}")
            return False

    def _parse_multisection(self, lines: List[str]):
        """Parsea el formato IBKR donde la col-0 es el nombre de sección."""
        current_section = None
        current_header = None

        for line in lines:
            if not line.strip():
                continue
            parts = line.split(",")
            section_name = parts[0].strip().lower().replace(" ", "")
            row_type = parts[1].strip().lower() if len(parts) > 1 else ""

            if row_type == "header":
                current_section = section_name
                # Las cabeceras empiezan en parts[2]
                current_header = [p.strip() for p in parts[2:]]
                continue

            if row_type == "data" and current_header and current_section:
                values = [p.strip() for p in parts[2:]]
                # Rellenar si hay menos valores que cabeceras
                while len(values) < len(current_header):
                    values.append("")
                row = dict(zip(current_header, values))

                if current_section in ("trades",):
                    self._trade_rows.append(row)
                elif current_section in ("cashtransactions", "cash transactions"):
                    self._cash_rows.append(row)

    # -----------------------------------------------------------------------
    # Propiedades calculadas
    # -----------------------------------------------------------------------

    @property
    def transactions(self) -> List[StockTrade]:
        trades: List[StockTrade] = list(self._pdf_trades)

        for row in self._trade_rows:
            hdr = _norm_headers(row.keys())

            def g(*keys):
                for k in keys:
                    k_norm = k.lower()
                    if k_norm in hdr:
                        return str(row[hdr[k_norm]]).strip()
                return ""

            trade_type = g("TradeType", "tradetype").lower()
            # Ignorar cancelaciones
            if any(c in trade_type for c in TRADE_CANCELS):
                continue

            buy_sell = g("BuySell", "buysell").upper()
            dt = _parse_date(g("DateTime", "datetime", "TradeDate", "tradedate"))
            symbol = g("Symbol", "symbol").upper()
            isin = g("ISIN", "isin")
            currency = g("Currency", "currency").upper()
            fxrate = _dec(g("FXRateToBase", "fxratetobase"))
            qty_raw = _dec(g("Quantity", "quantity"))
            qty = abs(qty_raw)
            proceeds = abs(_dec(g("Proceeds", "proceeds")))
            commissions = abs(_dec(g("Commissions", "commissions", "IBCommission", "ibcommission")))

            val_eur = _to_eur(proceeds, currency, fxrate, dt)
            fee_eur = _to_eur(commissions, currency, fxrate, dt)

            if trade_type == "corpact" and proceeds == Decimal("0"):
                direction = "split_in" if qty_raw > 0 else "split_out"
                trades.append(
                    StockTrade(
                        date=dt,
                        platform="IBKR",
                        asset=symbol,
                        isin=isin,
                        ticker=symbol,
                        asset_type="stock",
                        direction=direction,
                        quantity=qty,
                        value_eur=Decimal("0"),
                        fee_eur=Decimal("0"),
                        notes=f"IBKR CorpAct | {g('Description', 'description')}",
                    )
                )
                continue

            if buy_sell not in ("BUY", "SELL"):
                continue

            trades.append(
                StockTrade(
                    date=dt,
                    platform="IBKR",
                    asset=symbol,
                    isin=isin,
                    ticker=symbol,
                    asset_type="stock",
                    direction="buy" if buy_sell == "BUY" else "sell",
                    quantity=qty,
                    value_eur=val_eur,
                    fee_eur=fee_eur,
                    notes=f"IBKR {trade_type} | {g('Description', 'description')}",
                )
            )

        return sorted(trades, key=lambda t: t.date)

    @property
    def dividends(self) -> List[StockDividend]:
        result: List[StockDividend] = list(self._pdf_dividends)
        # Agrupar dividendos con sus retenciones por (symbol, date) usando refid implícito
        pending: Dict[str, StockDividend] = {}

        for row in self._cash_rows:
            hdr = _norm_headers(row.keys())

            def g(*keys):
                for k in keys:
                    if k.lower() in hdr:
                        return str(row[hdr[k.lower()]]).strip()
                return ""

            cash_type = g("Type", "type").lower().strip()

            dt = _parse_date(g("DateTime", "datetime", "SettleDate", "settledate"))
            symbol = g("Symbol", "symbol").upper()
            isin = g("ISIN", "isin")
            currency = g("Currency", "currency").upper()
            fxrate = _dec(g("FXRateToBase", "fxratetobase"))
            amount = _dec(g("Amount", "amount"))
            val_eur = _to_eur(abs(amount), currency, fxrate, dt)

            key = f"{symbol}|{dt.date()}"

            if cash_type in CASH_INCOME:
                income_type = "dividend" if "dividend" in cash_type or "lieu" in cash_type else "interest"
                if key in pending:
                    # Ya existe → acumular bruto
                    existing = pending[key]
                    pending[key] = StockDividend(
                        date=existing.date,
                        platform="IBKR",
                        asset=existing.asset,
                        isin=existing.isin,
                        gross_eur=existing.gross_eur + val_eur,
                        withholding_foreign_eur=existing.withholding_foreign_eur,
                        withholding_spain_eur=Decimal("0"),
                        type=income_type,
                    )
                else:
                    pending[key] = StockDividend(
                        date=dt,
                        platform="IBKR",
                        asset=symbol,
                        isin=isin,
                        gross_eur=val_eur,
                        withholding_foreign_eur=Decimal("0"),
                        withholding_spain_eur=Decimal("0"),
                        type=income_type,
                    )

            elif cash_type in CASH_WITHHOLD:
                # Retención: reducir gross o añadir withholding
                if key in pending:
                    existing = pending[key]
                    pending[key] = StockDividend(
                        date=existing.date,
                        platform="IBKR",
                        asset=existing.asset,
                        isin=existing.isin,
                        gross_eur=existing.gross_eur,
                        withholding_foreign_eur=existing.withholding_foreign_eur + val_eur,
                        withholding_spain_eur=Decimal("0"),
                        type=existing.type,
                    )
                else:
                    pending[key] = StockDividend(
                        date=dt,
                        platform="IBKR",
                        asset=symbol,
                        isin=isin,
                        gross_eur=Decimal("0"),
                        withholding_foreign_eur=val_eur,
                        withholding_spain_eur=Decimal("0"),
                        type="dividend",
                    )

            elif cash_type in CASH_FEE:
                result.append(
                    StockDividend(
                        date=dt,
                        platform="IBKR",
                        asset=symbol,
                        isin=isin,
                        gross_eur=Decimal("0"),
                        withholding_foreign_eur=Decimal("0"),
                        withholding_spain_eur=Decimal("0"),
                        type="fee",
                        custody_fee_eur=val_eur,
                    )
                )

        result.extend(pending.values())
        return sorted(result, key=lambda d: d.date)


# ---------------------------------------------------------------------------
# Punto de entrada público
# ---------------------------------------------------------------------------


def parse(file_paths) -> Tuple[List[StockTrade], List[StockDividend]]:
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    ingestor = IBKRIngestor()
    for path in file_paths:
        ingestor.process_file(path)
    return ingestor.transactions, ingestor.dividends
