import pandas as pd
from decimal import Decimal
from typing import List, Tuple
import os
from src.domain.stock_entities import Trade
from src.domain.stock_fiscal_entities import Dividend
from src.ingestion.utils import clean_decimal, parse_date, fuzzy_match
from src.accounting.stock_bce_oracle import StockBCEOracle

oracle = StockBCEOracle()


def parse(file_path: str) -> Tuple[List[Trade], List[Dividend]]:
    if not os.path.exists(file_path):
        return [], []

    pdf_trades = []
    pdf_dividends = []

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        from src.ingestion.universal_pdf_reader import UniversalPDFReader

        t, d = UniversalPDFReader().parse(file_path, platform="REVOLUT")
        pdf_trades.extend(t)
        pdf_dividends.extend(d)
        return pdf_trades, pdf_dividends

    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path)

    df.columns = [str(c).strip() for c in df.columns]

    final_trades: List[Trade] = []
    final_divs: List[Dividend] = []

    c_type = fuzzy_match(df.columns, ["type", "tipo"])
    c_date = fuzzy_match(df.columns, ["date", "fecha"])
    c_ticker = fuzzy_match(df.columns, ["ticker", "simbolo", "product"])
    c_qty = fuzzy_match(df.columns, ["quantity", "cantidad"])
    c_price = fuzzy_match(df.columns, ["price", "precio"])
    c_total = fuzzy_match(df.columns, ["total", "amount"])
    c_fee = fuzzy_match(df.columns, ["fee", "comision"])
    c_currency = fuzzy_match(df.columns, ["currency", "moneda"])

    for _, row in df.iterrows():
        t_type = str(row[c_type]).lower()
        dt = parse_date(row[c_date])
        ticker = str(row[c_ticker]).strip().upper() if pd.notna(row[c_ticker]) else ""

        # Obtener moneda y tasa de conversión
        currency = str(row[c_currency]).strip().upper() if c_currency and pd.notna(row[c_currency]) else "USD"
        rate = oracle.get_rate(dt, currency) if currency != "EUR" else Decimal("1.0")
        if rate is None:
            rate = Decimal("1.0")  # Fallback por si la red falla, aunque BCE avisa

        # 1. COMPRAS Y VENTAS
        if any(kw in t_type for kw in ["buy", "sell"]):
            qty = abs(clean_decimal(row[c_qty]))
            total_val = abs(clean_decimal(row[c_total]))
            fee = clean_decimal(row[c_fee]) if c_fee and pd.notna(row[c_fee]) else Decimal("0")

            # Conversión a EUR
            val_eur = (total_val / rate).quantize(Decimal("0.00000001")) if rate else total_val
            fee_eur = (fee / rate).quantize(Decimal("0.00000001")) if rate else fee

            final_trades.append(
                Trade(
                    date=dt,
                    platform="Revolut",
                    asset=ticker,
                    isin="",
                    ticker=ticker,
                    asset_type="stock",
                    direction="buy" if "buy" in t_type else "sell",
                    quantity=qty,
                    value_eur=val_eur,
                    fee_eur=fee_eur,
                    notes=f"REVOLUT_{t_type} | Rate: {rate}",
                )
            )

        # 2. CUSTODY FEES (Ruido pasivo a ignorar o tratar como gasto general)
        elif "custody fee" in t_type:
            continue

        # 3. DIVIDENDOS
        elif "div" in t_type:
            amount = clean_decimal(row[c_total])
            div_eur = (abs(amount) / rate).quantize(Decimal("0.00000001")) if rate else abs(amount)
            # Si hay una columna explícita de withhold (común en Revolut nuevos)
            # En csv antiguo no hay, el usuario debe revisar
            final_divs.append(
                Dividend(
                    date=dt,
                    platform="Revolut",
                    asset=ticker,
                    isin="",
                    gross_eur=div_eur,
                    withholding_foreign_eur=Decimal("0"),
                    withholding_spain_eur=Decimal("0"),
                    type="dividend",
                )
            )

        # 3. SPLITS
        elif "split" in t_type:
            qty = clean_decimal(row[c_qty])
            final_trades.append(
                Trade(
                    date=dt,
                    platform="Revolut",
                    asset=ticker,
                    isin="",
                    ticker=ticker,
                    asset_type="stock",
                    direction="split_in" if qty > 0 else "split_out",
                    quantity=abs(qty),
                    value_eur=Decimal("0"),
                    fee_eur=Decimal("0"),
                    notes="REVOLUT_SPLIT",
                )
            )

        # 4. CUSTODY FEE
        elif "custody" in t_type:
            amount = abs(clean_decimal(row[c_total]))
            fee_eur = (amount / rate).quantize(Decimal("0.00000001")) if rate else amount
            final_divs.append(
                Dividend(
                    date=dt,
                    platform="Revolut",
                    asset=ticker,
                    isin="",
                    gross_eur=Decimal("0"),
                    withholding_foreign_eur=Decimal("0"),
                    withholding_spain_eur=Decimal("0"),
                    type="fee",
                    custody_fee_eur=fee_eur,
                )
            )

    return final_trades, final_divs
