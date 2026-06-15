import pandas as pd
import re
import os
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple
import dataclasses
from collections import defaultdict

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

from src.domain.stock_entities import Trade
from src.domain.fiscal_entities import Dividend


def _clean_decimal(val) -> Decimal:
    if pd.isna(val) or val == "" or val is None:
        return Decimal("0")
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    s = str(val).replace('"', "").replace("'", "").replace(".", "").replace(",", ".").strip()
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def _parse_date(s) -> datetime:
    if isinstance(s, datetime):
        return s
    if not isinstance(s, str):
        s = str(s)
    s = s.strip().replace('"', "").replace("'", "")
    if not s or s.lower() == "nan":
        return datetime(1900, 1, 1)
    for fmt in ["%d-%m-%Y %H:%M", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%Y %H:%M", "%Y/%m/%d"]:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return datetime(1900, 1, 1)


def _extract_data_from_pdf(path: str) -> Tuple[List[Trade], List[Dividend]]:
    if not PdfReader:
        return [], []
    trades = []
    divs = []
    try:
        reader = PdfReader(path)
        raw_text = "\n".join([p.extract_text() for p in reader.pages])
        text = ""
        for line in raw_text.split("\n"):
            if re.match(r"^\d{2}-\d{2}-\d{4}", line.strip()):
                text += "\n" + line.strip()
            else:
                text += " " + line.strip()

        for line in text.split("\n"):
            line = line.strip()
            if "flatexDEGIRO" in line:
                line = line.split("flatexDEGIRO")[0].strip()
            match_dt = re.match(r"^(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2})", line)
            if not match_dt:
                continue
            match_isin = re.search(r"([A-Z]{2}[A-Z0-9]{9}\d)", line)
            if not match_isin:
                continue
            dt = _parse_date(match_dt.group(1))
            isin = match_isin.group(1)
            prod = line[len(match_dt.group(1)) : line.find(isin)].strip().upper()
            parts = line[line.find(isin) + len(isin) :].split()
            if len(parts) < 3:
                continue
            origin = "DESC"
            total_eur = Decimal("0")
            for i in range(len(parts) - 1, -1, -1):
                p = parts[i]
                if re.match(r"^[A-Z]{3,5}$", p) and not any(c.isdigit() for c in p):
                    origin = p.upper()
                else:
                    try:
                        p_clean = p.replace(".", "").replace(",", ".")
                        if re.match(r"^-?[\d\.]+$", p_clean):
                            total_eur = abs(_clean_decimal(p))
                            break
                    except Exception:
                        continue
            qty = Decimal("0")
            for i in range(len(parts)):
                p = parts[i]
                try:
                    p_clean = p.replace(".", "").replace(",", ".")
                    if re.match(r"^-?[\d\.]+$", p_clean) and p_clean != "0.00":
                        qty = _clean_decimal(p)
                        break
                except Exception:
                    continue
            if qty != 0:
                trades.append(
                    Trade(
                        dt,
                        "DeGiro",
                        prod,
                        isin,
                        "",
                        "stock",
                        "buy" if qty > 0 else "sell",
                        abs(qty),
                        total_eur,
                        Decimal("0"),
                        f"TRANS_FILE|PDF|{origin}",
                    )
                )
    except Exception as e:
        print(f"Error PDF: {e}")
    return trades, divs


def parse(file_paths) -> Tuple[List[Trade], List[Dividend]]:
    if isinstance(file_paths, str):
        if os.path.isdir(file_paths):
            file_paths = [os.path.join(file_paths, f) for f in os.listdir(file_paths)]
        else:
            file_paths = [file_paths]

    final_trades = []
    final_divs = []

    seen_transactions = set()
    seen_account_lines = set()
    # Mapa global de dividendos: (Fecha_ISO, ISIN) -> Data
    div_map = defaultdict(lambda: {"gross": Decimal("0"), "withholding": Decimal("0"), "asset": "", "date": None})
    fees_list = []

    # 1. Transactions
    for path in file_paths:
        p_low = os.path.basename(path).lower()
        if "transactions" in p_low or "trade" in p_low:
            df = None
            if path.endswith(".csv"):
                try:
                    df = pd.read_csv(path)
                except Exception:
                    pass
            elif path.endswith(".xlsx"):
                try:
                    df = pd.read_excel(path)
                except Exception:
                    pass

            if df is not None:
                try:
                    df.columns = [str(c).strip() for c in df.columns]

                    # Agrupar por ID Orden + Dirección para evitar que splits se resten (3400 - 170 = 3230)
                    def get_group_key(r):
                        oid = str(r.iloc[16]) if len(r) > 16 else "nan"
                        if oid == "nan" or not oid.strip():
                            oid = f"{r.iloc[0]}_{r.iloc[1]}"  # Fecha + Hora
                        direction = "buy" if _clean_decimal(r.iloc[6]) > 0 else "sell"
                        return f"{oid}_{direction}"

                    df["tmp_group_key"] = df.apply(get_group_key, axis=1)
                    for _, group in df.groupby("tmp_group_key", sort=False):
                        first = group.iloc[0]
                        dt = _parse_date(str(first.iloc[0]) + " " + str(first.iloc[1]))
                        if not dt:
                            continue  # Sin filtro de año: el motor FIFO necesita historial completo

                        oid = str(first.iloc[16]) if len(first) > 16 else "nan"
                        if oid != "nan" and oid in seen_transactions:
                            continue
                        if oid != "nan":
                            seen_transactions.add(oid)

                        t_qty = sum([_clean_decimal(r.iloc[6]) for _, r in group.iterrows()])
                        # IMPORTANTE: Usamos Index 11 (Valor EUR / Bruto) en lugar de 15 (Total EUR / Neto)
                        # Esto evita que el motor fiscal reste las comisiones dos veces.
                        t_val = sum([_clean_decimal(r.iloc[11]) for _, r in group.iterrows()])
                        t_fee = (
                            sum([abs(_clean_decimal(r.iloc[14])) for _, r in group.iterrows()])
                            if len(first) > 14
                            else Decimal("0")
                        )

                        if t_qty != 0 or t_val != 0:
                            final_trades.append(
                                Trade(
                                    date=dt,
                                    platform="DeGiro",
                                    asset=str(first.iloc[2]).upper(),
                                    isin=str(first.iloc[3]).upper(),
                                    ticker="",
                                    asset_type="stock",
                                    direction="buy" if t_qty > 0 else "sell",
                                    quantity=abs(t_qty),
                                    value_eur=abs(t_val),
                                    fee_eur=t_fee,
                                    notes=f"TRANS_FILE|ORDER|{oid}",
                                    source_file=os.path.basename(path),
                                )
                            )
                except Exception as e:
                    print(f"Error parsing transactions from {path}: {e}")
            elif path.endswith(".pdf"):
                t, _ = _extract_data_from_pdf(path)
                for tr in t:
                    sig = (tr.date.strftime("%Y%m%d%H%M"), tr.isin, tr.quantity, tr.direction)
                    if sig not in seen_transactions:
                        # Usamos dataclasses.replace para inyectar el archivo de forma legal e inmutable
                        tr = dataclasses.replace(tr, source_file=os.path.basename(path))
                        final_trades.append(tr)
                        seen_transactions.add(sig)

    # 2. Account
    from src.accounting.stock_bce_oracle import StockBCEOracle

    oracle = StockBCEOracle()

    for path in file_paths:
        p_low = os.path.basename(path).lower()
        if "account" in p_low:
            df = None
            if path.endswith(".csv"):
                for enc in ["utf-8-sig", "latin-1", "cp1252"]:
                    try:
                        df = pd.read_csv(path, encoding=enc)
                        break
                    except Exception:
                        pass
            elif path.endswith(".xlsx"):
                try:
                    df = pd.read_excel(path)
                except Exception:
                    pass

            if df is not None:
                df.columns = [str(c).strip() for c in df.columns]
                for _, row in df.iterrows():
                    try:
                        dt = _parse_date(row.iloc[0])
                        # Sin filtro de año: el motor FIFO necesita historial completo para costes de adquisición

                        asset = str(row.iloc[3]).strip().upper() if not pd.isna(row.iloc[3]) else ""
                        isin = str(row.iloc[4]).strip().upper() if not pd.isna(row.iloc[4]) else ""
                        desc = str(row.iloc[5]).strip().upper()

                        # Detección de moneda y conversión (CRÍTICO)
                        currency = str(row.iloc[7]).strip().upper() if len(row) > 7 else "EUR"
                        val_raw = row.iloc[8]
                        val_clean = _clean_decimal(val_raw).normalize()

                        if currency != "EUR" and val_clean != 0:
                            rate = oracle.get_rate(dt, currency)
                            if rate != 0:
                                val_clean = (val_clean / rate).quantize(Decimal("0.00000001"))

                        # 2.1 DETECCIÓN DE EVENTOS CORPORATIVOS EN ACCOUNT (Splits, Reorgs)
                        # DeGiro a veces no pone 'SPLIT' en el archivo de transacciones, solo en Account.
                        reorg_keywords = ["STOCK SPLIT", "CAMBIO DE PRODUCTO", "REORGANIZACIÓN", "REORG"]
                        if any(kw in desc for kw in reorg_keywords):
                            # Intentar extraer cantidad de la descripción: "Compra 170 Senseonics..."
                            qty_match = re.search(r"(COMPRA|VENTA)\s+([\d\.,]+)", desc)
                            if qty_match:
                                direction = "buy" if qty_match.group(1) == "COMPRA" else "sell"
                                qty = _clean_decimal(qty_match.group(2))

                                # Creamos un Trade especial de reorganización
                                # Usamos val_clean como valor total (a veces es 0 en splits puros, o el valor de mercado)
                                final_trades.append(
                                    Trade(
                                        date=dt,
                                        platform="DeGiro",
                                        asset=asset,
                                        isin=isin,
                                        ticker="",
                                        asset_type="stock",
                                        direction=direction,
                                        quantity=qty,
                                        value_eur=abs(val_clean),
                                        fee_eur=Decimal("0"),
                                        notes=desc,
                                        source_file=os.path.basename(path),
                                    )
                                )
                                # Registramos la firma para evitar que el loop de transacciones lo duplique sin notas
                                sig_reorg = (dt.strftime("%Y%m%d"), isin, str(qty if direction == "buy" else -qty))
                                seen_transactions.add(sig_reorg)

                        # Firma Ultra-Robusta para líneas de Account: (Fecha, Producto, Descripción, Importe)
                        sig = (dt.strftime("%Y%m%d"), asset, desc, str(val_clean))
                        if sig in seen_account_lines:
                            continue
                        seen_account_lines.add(sig)

                        if any(x in desc for x in ["COMPRA", "VENTA", "TRANSACCIÓN"]):
                            continue

                        desc_upper = desc.upper()
                        if "DIVIDENDO" in desc_upper or "DIVIDEND" in desc_upper:
                            key = (dt.strftime("%Y-%m-%d"), asset)
                            div_map[key]["asset"] = asset
                            div_map[key]["date"] = dt
                            if isin:
                                div_map[key]["isin"] = isin
                            if "RETENCI" in desc_upper:
                                div_map[key]["withholding"] += val_clean
                            else:
                                div_map[key]["gross"] += val_clean
                        elif "INTER" in desc_upper:
                            v_clean = _clean_decimal(row.iloc[8])
                            if v_clean < 0:
                                # Intereses pagados -> NO DEDUCIBLES en IRPF (DGT V1603-15)
                                # Se omiten del reporte para no inflar la Casilla [0035]
                                pass
                            else:
                                # Intereses cobrados -> Rendimiento del Capital Mobiliario [0027]
                                final_divs.append(
                                    Dividend(
                                        dt, "DeGiro", desc, isin, v_clean, Decimal("0"), Decimal("0"), type="interest"
                                    )
                                )
                        elif "CONECTIVIDAD" in desc_upper or "CONECTIVITY" in desc_upper:
                            # Comisiones de conectividad -> Deducibles como Gastos de Administración/Custodia [0035]
                            final_divs.append(
                                Dividend(
                                    dt,
                                    "DeGiro",
                                    desc,
                                    "",
                                    Decimal("0"),
                                    Decimal("0"),
                                    Decimal("0"),
                                    type="fee",
                                    custody_fee_eur=abs(_clean_decimal(row.iloc[8])),
                                )
                            )
                        elif "COMISI" in desc_upper or "COMMIS" in desc_upper:
                            # Otras comisiones administrativas (ej. tramitación dividendos) -> [0035]
                            v_fee = abs(_clean_decimal(row.iloc[8]))
                            if v_fee > 0:
                                final_divs.append(
                                    Dividend(
                                        dt,
                                        "DeGiro",
                                        desc,
                                        "",
                                        Decimal("0"),
                                        Decimal("0"),
                                        Decimal("0"),
                                        type="fee",
                                        custody_fee_eur=v_fee,
                                    )
                                )
                    except Exception as e:
                        if "SENSEONICS" in str(row.iloc[3]).upper():
                            print(f"Error processing SENSEONICS row: {e}")
                        continue

    for _k, v in div_map.items():
        if v["gross"] > 0 or v["withholding"] > 0:
            isin_final = v.get("isin", "")
            is_spain = isin_final.startswith("ES")
            # Forzar valores positivos para el reporte fiscal
            gross = abs(v["gross"])
            withh = abs(v["withholding"])
            final_divs.append(
                Dividend(
                    v["date"],
                    "DeGiro",
                    v["asset"],
                    isin_final,
                    gross,
                    withh if not is_spain else 0,
                    withh if is_spain else 0,
                    type="dividend",
                )
            )

    # Asegurar que fees_list use valores positivos
    for f in fees_list:
        final_divs.append(
            Dividend(
                f.date,
                f.platform,
                f.asset,
                f.isin,
                f.gross_eur,
                f.withholding_foreign_eur,
                f.withholding_spain_eur,
                type=f.type,
                custody_fee_eur=abs(f.custody_fee_eur),
            )
        )

    return sorted(final_trades, key=lambda x: x.date), final_divs
