from typing import List, Dict, Sequence, Optional, Tuple
from decimal import Decimal
import os
from datetime import datetime

from src.domain.stock_fiscal_entities import Dividend
from src.domain.shared_types import AnyTrade, AnyDividend
from src.ingestion.file_classifier import FileMetadata

def ingest_and_deduplicate_stock_data(
    folder_path: str,
    classified_files: Dict[str, FileMetadata],
    orphan_trades: Optional[Sequence[AnyTrade]] = None,
    orphan_divs: Optional[Sequence[AnyDividend]] = None,
    tax_year: int = 2025
) -> Tuple[List[AnyTrade], List[AnyDividend], List[str]]:
    """
    Ingesta archivos de DEGIRO y Trading212, y aplica el algoritmo de deduplicación 
    inteligente priorizando CSVs sobre PDFs y conservando eventos corporativos.
    Retorna (unique_trades, unique_divs, warnings).
    """
    all_raw_trades = []
    all_raw_divs = []
    pdf_divs_fallback = []
    warnings = []
    report_summary = {}

    has_t212_csv = any(
        (".csv" in f.lower() and meta.platform.upper() == "TRADING212") for f, meta in classified_files.items()
    )

    degiro_files = []
    t212_files = []

    for filename, meta in classified_files.items():
        file_path = os.path.join(folder_path, filename)
        plat = meta.platform.upper()
        if plat == "DEGIRO" or plat == "DE GIRO":
            if meta.extension != ".pdf":
                degiro_files.append(file_path)
            else:
                from src.ingestion.pdf_data_extractor import PDFProcessor
                processor = PDFProcessor()
                report_summary = processor.process(file_path)
                if report_summary and report_summary.get("dividendos_brutos", 0) > 0:
                    pdf_divs_fallback.append(
                        Dividend(
                            date=datetime(tax_year, 12, 31),
                            platform="DeGiro",
                            asset="TOTAL PDF REPORT",
                            isin="",
                            gross_eur=report_summary["dividendos_brutos"],
                            withholding_foreign_eur=report_summary.get("retencion_extranjera", Decimal("0")),
                            withholding_spain_eur=Decimal("0"),
                        )
                    )
        elif plat in ("T212", "TRADING212", "TRADING 212"):
            t212_files.append((file_path, meta.extension))

    # 1. PROCESAR DEGIRO
    if degiro_files:
        from src.ingestion.degiro_reader import parse as parse_degiro
        trades, divs = parse_degiro(degiro_files)
        all_raw_trades.extend(trades)
        all_raw_divs.extend(divs)

    degiro_divs_count = sum(1 for d in all_raw_divs if d.platform.upper() == "DEGIRO")
    if degiro_divs_count == 0:
        all_raw_divs.extend(pdf_divs_fallback)

    # 2. PROCESAR TRADING 212
    from src.ingestion.trading212_reader import parse as parse_t212
    for file_path, ext in t212_files:
        trades, divs = parse_t212(file_path)
        if ext == ".pdf":
            if not has_t212_csv:
                all_raw_trades.extend(trades)
            all_raw_divs.extend(divs)
        else:
            all_raw_trades.extend(trades)
            all_raw_divs.extend(divs)

    # 3. DE-DUPLICACIÓN DE TRADES
    identity_map = {}  
    row_counters = {}  

    for t in all_raw_trades:
        isin_key = t.isin if (t.isin and len(t.isin) > 5) else getattr(t, "ticker", "") or getattr(t, "asset", "")
        identity = (t.date.strftime("%Y%m%d"), isin_key, round(t.quantity, 8), getattr(t, "direction", ""))
        source_key = (identity, getattr(t, "source_file", ""))
        row_counters[source_key] = row_counters.get(source_key, 0) + 1
        full_key = (identity, getattr(t, "source_file", ""), row_counters[source_key])
        identity_map[full_key] = t

    final_trades_dict = {}  
    for (identity, source, counter), t in identity_map.items():
        dedup_key = (identity, counter)
        if dedup_key not in final_trades_dict:
            final_trades_dict[dedup_key] = t
        else:
            existing = final_trades_dict[dedup_key]
            t_is_csv = ".csv" in getattr(t, "source_file", "").lower()
            ex_is_csv = ".csv" in getattr(existing, "source_file", "").lower()
            t_is_fallback = "FALLBACK" in getattr(t, "notes", "")
            ex_is_fallback = "FALLBACK" in getattr(existing, "notes", "")

            reorg_kws = ["SPLIT", "REORG", "CAMBIO DE PRODUCTO", "MERGER"]
            t_has_reorg = any(kw in getattr(t, "notes", "").upper() for kw in reorg_kws)
            ex_has_reorg = any(kw in getattr(existing, "notes", "").upper() for kw in reorg_kws)

            if (
                (t_has_reorg and not ex_has_reorg)
                or (t_is_csv and not ex_is_csv)
                or (not t_is_fallback and ex_is_fallback)
            ):
                final_trades_dict[dedup_key] = t

    unique_trades = list(final_trades_dict.values())

    # 4. DE-DUPLICACIÓN DE DIVIDENDOS
    non_dedup_items = [d for d in all_raw_divs if getattr(d, "type", "dividend") in ["fee", "interest"]]
    dedup_targets = [d for d in all_raw_divs if getattr(d, "type", "dividend") not in ["fee", "interest"]]

    seen_divs = {}
    for d in dedup_targets:
        isin_key = getattr(d, "isin", None)
        if not isin_key or len(isin_key) < 5:
            isin_key = getattr(d, "asset", "")
        key = (d.date.strftime("%Y%m%d"), isin_key, round(d.gross_eur, 2), round(d.custody_fee_eur, 2))

        if key not in seen_divs:
            seen_divs[key] = d
        else:
            current_is_dirty = any(g in getattr(d, "asset", "").upper() for g in ["IMPORTE", "MPORTE", "NETO"])
            existing_is_dirty = any(g in getattr(seen_divs[key], "asset", "").upper() for g in ["IMPORTE", "MPORTE", "NETO"])
            if not current_is_dirty and existing_is_dirty:
                seen_divs[key] = d

    unique_divs = list(seen_divs.values()) + non_dedup_items

    if orphan_trades:
        unique_trades.extend(orphan_trades)
    if orphan_divs:
        unique_divs.extend(orphan_divs)

    # 5. AJUSTE Y VERIFICACIÓN
    pdf_gross = report_summary.get("dividendos_brutos", Decimal("0"))
    if pdf_gross > 0:
        divs_to_adjust = [d for d in unique_divs if getattr(d, "type", "dividend") == "dividend" and getattr(d, "date", datetime.now()).year == tax_year and getattr(d, "platform", "").upper() in ("DEGIRO", "DE GIRO")]
        calc_gross = sum(d.gross_eur for d in divs_to_adjust)
        diff = abs(calc_gross - pdf_gross)
        if diff >= Decimal("0.10"):
            warnings.append(
                f"⚠️ DESVIACIÓN EN DIVIDENDOS: El PDF Anual declara {pdf_gross}€ pero los cálculos transaccionales arrojan {calc_gross}€ (Desvío: {diff}€). "
                f"Revisa manualmente los CSVs aportados."
            )

    return unique_trades, unique_divs, warnings
