import pandas as pd
import pdfplumber
import re
import os
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple
from src.domain.stock_entities import Trade
from src.domain.stock_fiscal_entities import Dividend
from src.ingestion.utils import clean_decimal, parse_date, fuzzy_match


def parse(file_path: str) -> Tuple[List[Trade], List[Dividend]]:
    if not os.path.exists(file_path):
        return [], []
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".csv", ".xlsx", ".xls"]:
        return _parse_csv_excel(file_path, ext)
    elif ext == ".pdf":
        return _parse_pdf(file_path)
    return [], []


def _parse_csv_excel(file_path: str, ext: str) -> Tuple[List[Trade], List[Dividend]]:
    df = pd.read_csv(file_path) if ext == ".csv" else pd.read_excel(file_path)
    df.columns = [str(c).strip() for c in df.columns]
    final_trades, final_divs = [], []
    c_action = fuzzy_match(df.columns, ["Action"])
    c_time = fuzzy_match(df.columns, ["Time"])
    c_isin = fuzzy_match(df.columns, ["ISIN"])
    c_ticker = fuzzy_match(df.columns, ["Ticker"])
    c_name = fuzzy_match(df.columns, ["Name"])
    c_qty = fuzzy_match(df.columns, ["No. of shares"])
    c_total = fuzzy_match(df.columns, ["Total"])
    c_fee_fx = fuzzy_match(df.columns, ["Currency conversion fee"], mandatory=False)
    c_withholding = fuzzy_match(df.columns, ["Withholding tax"], mandatory=False)
    fuzzy_match(df.columns, ["Notes"], mandatory=False)

    for _, row in df.iterrows():
        action = str(row[c_action]).lower()
        dt = parse_date(row[c_time])
        isin = str(row[c_isin]).strip().upper() if pd.notna(row[c_isin]) else ""
        ticker = str(row[c_ticker]).strip().upper() if pd.notna(row[c_ticker]) else ""
        name = str(row[c_name]).strip().upper() if pd.notna(row[c_name]) else ""
        if any(kw in action for kw in ["buy", "sell", "rights", "split"]):
            qty, total_eur = clean_decimal(row[c_qty]), abs(clean_decimal(row[c_total]))
            fee = clean_decimal(row[c_fee_fx]) if c_fee_fx and pd.notna(row[c_fee_fx]) else Decimal("0")
            direction = "buy" if any(kw in action for kw in ["buy", "rights", "open"]) else "sell"
            if "split" in action:
                direction = "split_in" if "open" in action else "split_out"

            # Ajuste de Bruto vs Neto para evitar duplicidad de comisiones en el motor FIFO
            # Trading 212 devuelve el Total NETO en el CSV. El motor espera el BRUTO para aplicar la comisión.
            total_bruto = total_eur - fee if direction == "buy" else total_eur + fee

            final_trades.append(
                Trade(
                    date=dt,
                    platform="Trading 212",
                    asset=name or ticker,
                    isin=isin,
                    ticker=ticker,
                    asset_type="stock",
                    direction=direction,
                    quantity=abs(qty),
                    value_eur=total_bruto,
                    fee_eur=fee,
                    notes="T212_CSV",
                )
            )
        elif any(kw in action for kw in ["dividend", "interest"]):
            wht, net = (
                abs(clean_decimal(row[c_withholding]))
                if c_withholding and pd.notna(row[c_withholding])
                else Decimal("0"),
                abs(clean_decimal(row[c_total])),
            )
            final_divs.append(
                Dividend(
                    date=dt,
                    platform="Trading 212",
                    asset=name or "INTERESES/DIVIDENDOS T212",
                    isin=isin,
                    gross_eur=net + wht,
                    withholding_foreign_eur=wht,
                    withholding_spain_eur=Decimal("0"),
                    type="interest" if "interest" in action else "dividend",
                )
            )
    return final_trades, final_divs


def _parse_pdf(file_path: str) -> Tuple[List[Trade], List[Dividend]]:
    trades, dividends = [], []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                lines = text.split("\n")

                for line in lines:
                    # 1. Intentar capturar VENTAS
                    m_sale = re.search(r"(\d{2}\.\d{2}\.\d{4})\s+\d{2}:\d{2}\s+([A-Z0-9]+)\s+([A-Z]{2}[A-Z0-9]+)", line)
                    if m_sale and any(x in text.lower() for x in ["venta", "posici.n cerrada", "posicion cerrada"]):
                        nums = re.findall(r"[\u20ac\$\xA3]?\s*-?[\d\.,]+", line[m_sale.end() :])
                        if len(nums) >= 4:
                            trades.append(
                                Trade(
                                    date=datetime.strptime(m_sale.group(1), "%d.%m.%Y"),
                                    platform="Trading 212",
                                    asset=m_sale.group(2),
                                    isin=m_sale.group(3),
                                    ticker=m_sale.group(2),
                                    asset_type="stock",
                                    direction="sell",
                                    quantity=_pdf_to_decimal(nums[0]),
                                    value_eur=_pdf_to_decimal(nums[-2]),
                                    fee_eur=Decimal("0"),
                                    notes="T212_PDF_SALE",
                                )
                            )
                        continue

                    # 2. Intentar capturar DIVIDENDOS
                    m_div = re.search(
                        r"([A-Za-z0-9\s\.-]+)\s+([A-Z]{2}[0-9A-Z]{5,15})\s+[A-Z]{2}\s+[\d\.,]+\s+(\d{2}\.\d{2}\.\d{4})",
                        line,
                    )
                    if m_div and "dividendo" in text.lower():
                        # Limpiar línea para extraer números
                        line_after = re.sub(r"\d+\s*%", " ", line[m_div.end() :])
                        nums = re.findall(r"[\u20ac\$\xA3]?\s*-?[\d\.,]+", line_after)
                        if len(nums) >= 4:
                            isin = m_div.group(2)
                            is_spain = isin.startswith("ES")
                            # Formato: ... BrutoEUR WHTEUR NetoEUR (los 3 últimos suelen ser estos)
                            gross = _pdf_to_decimal(nums[-3])
                            wht = _pdf_to_decimal(nums[-2])
                            dividends.append(
                                Dividend(
                                    date=datetime.strptime(m_div.group(3), "%d.%m.%Y"),
                                    platform="Trading 212",
                                    asset=m_div.group(1).strip(),
                                    isin=isin,
                                    gross_eur=gross,
                                    withholding_foreign_eur=Decimal("0") if is_spain else wht,
                                    withholding_spain_eur=wht if is_spain else Decimal("0"),
                                    type="dividend",
                                )
                            )
                        continue

                # 3. Intereses (Suelen estar al final de una página o en una específica)
                if "inter.s de efectivo" in text.lower():
                    m_int = re.search(r"([A-Z]{3})\s+([\d\.,]+)", text)
                    if m_int:
                        # Evitar duplicados si ya se capturó en esta página
                        if not any(
                            d.asset == "Intereses Efectivo" and d.gross_eur == _pdf_to_decimal(m_int.group(2))
                            for d in dividends
                        ):
                            dividends.append(
                                Dividend(
                                    date=datetime(2025, 12, 31),
                                    platform="Trading 212",
                                    asset="Intereses Efectivo",
                                    isin="",
                                    gross_eur=_pdf_to_decimal(m_int.group(2)),
                                    withholding_foreign_eur=Decimal("0"),
                                    withholding_spain_eur=Decimal("0"),
                                    type="interest",
                                )
                            )

    except:
        pass
    return trades, dividends


def _pdf_to_decimal(s: str) -> Decimal:
    if not s or s == "-":
        return Decimal("0")
    clean = re.sub(r"[^\d\.,-]", "", str(s))
    if "," in clean and "." in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    try:
        return Decimal(clean)
    except:
        return Decimal("0")
