class NeedsReviewException(Exception):
    pass


class UniversalReader:
    @staticmethod
    def parse(f):
        return parse(f)


import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple
import os
from src.domain.stock_entities import Trade
from src.domain.stock_fiscal_entities import Dividend
from src.ingestion.utils import clean_decimal, parse_date, fuzzy_match


def parse(file_path: str) -> Tuple[List[Trade], List[Dividend]]:
    if not os.path.exists(file_path):
        return [], []

    # Intento de lectura robusta (CSV/Excel)
    df = pd.read_excel(file_path) if file_path.endswith((".xlsx", ".xls")) else pd.read_csv(file_path)
    df.columns = [str(c).strip() for c in df.columns]

    final_trades: List[Trade] = []
    final_divs: List[Dividend] = []

    # Diccionario Heurístico Universal
    c_type = fuzzy_match(df.columns, ["tipo", "type", "accion", "action", "operacion"])
    c_date = fuzzy_match(df.columns, ["fecha", "date", "time", "tiempo"])
    c_asset = fuzzy_match(df.columns, ["producto", "product", "asset", "activo", "ticker", "isin"])
    c_qty = fuzzy_match(df.columns, ["cantidad", "quantity", "numero", "nmero", "shares"])
    c_val = fuzzy_match(df.columns, ["valor", "value", "monto", "amount", "total", "variacion"])
    c_fee = fuzzy_match(df.columns, ["comision", "fee", "costes"])

    for _, row in df.iterrows():
        op_type = str(row[c_type]).lower() if c_type else ""
        dt = parse_date(row[c_date]) if c_date else datetime.now()
        asset = str(row[c_asset]).strip().upper() if c_asset and pd.notna(row[c_asset]) else "UNKNOWN"
        val = abs(clean_decimal(row[c_val])) if c_val else Decimal("0")
        qty = abs(clean_decimal(row[c_qty])) if c_qty else Decimal("0")

        # Clasificación Heurística Universal
        if any(kw in op_type for kw in ["compra", "buy", "adquisici"]):
            final_trades.append(
                Trade(dt, "Universal", asset, "", "", "stock", "buy", qty, val, Decimal("0"), "GENERIC_BUY")
            )

        elif any(kw in op_type for kw in ["venta", "sell", "transmisi"]):
            final_trades.append(
                Trade(dt, "Universal", asset, "", "", "stock", "sell", qty, val, Decimal("0"), "GENERIC_SELL")
            )

        elif any(kw in op_type for kw in ["div", "reparto", "coupon"]):
            final_divs.append(Dividend(dt, "Universal", asset, "", val, Decimal("0"), Decimal("0"), type="dividend"))

        elif any(kw in op_type for kw in ["interes", "interest", "rendimiento"]):
            final_divs.append(Dividend(dt, "Universal", asset, "", val, Decimal("0"), Decimal("0"), type="interest"))

        elif any(kw in op_type for kw in ["split", "reorg"]):
            final_trades.append(
                Trade(
                    dt,
                    "Universal",
                    asset,
                    "",
                    "",
                    "stock",
                    "split_in" if clean_decimal(row[c_qty]) > 0 else "split_out",
                    qty,
                    Decimal("0"),
                    Decimal("0"),
                    "GENERIC_SPLIT",
                )
            )

    return final_trades, final_divs
