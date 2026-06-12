from typing import List, Dict, Tuple
from decimal import Decimal
import os
from datetime import datetime

from src.accounting.stock_calculator import StockTaxEngine

from src.domain.stock_entities import TaxEvent
from src.domain.fiscal_entities import Dividend
from src.ingestion.file_classifier import FileMetadata

class StockSpecialist:
    """
    Especialista en Acciones y ETFs.
    Encargado de la ingesta y auditoría de brokers de bolsa.
    """
    
    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year
        self.engine = StockTaxEngine(tax_year=tax_year)
        
    def process_files(self, folder_path: str, classified_files: Dict[str, 'FileMetadata'], orphan_trades: List = None, orphan_divs: List = None):
        """
        Procesa los archivos de bolsa de forma unificada para evitar duplicados y errores de orden.
        """
        all_raw_trades = []
        all_raw_divs = []
        pdf_divs_fallback = []

        # Detectar si tenemos CSV para Trading 212 para evitar polución de PDFs
        has_t212_csv = any(('.csv' in f.lower() and meta.platform.upper() == 'TRADING212') for f, meta in classified_files.items())

        # Agrupar archivos por plataforma para procesamiento atómico
        degiro_files = []
        t212_files = []
        
        for filename, meta in classified_files.items():
            file_path = os.path.join(folder_path, filename)
            plat = meta.platform.upper()
            if plat == 'DEGIRO':
                if meta.extension != '.pdf':
                    degiro_files.append(file_path)
                else:
                    # Procesar PDF por separado (como reporte sumario)
                    from src.ingestion.pdf_data_extractor import PDFProcessor
                    processor = PDFProcessor()
                    self.report_summary = processor.process(file_path)
                    if self.report_summary and self.report_summary['dividendos_brutos'] > 0:
                        pdf_divs_fallback.append(Dividend(
                            date=datetime(self.tax_year, 12, 31), platform="DeGiro", asset="TOTAL PDF REPORT", 
                            isin="", gross_eur=self.report_summary['dividendos_brutos'], 
                            withholding_foreign_eur=self.report_summary['retencion_extranjera'], 
                            withholding_spain_eur=Decimal('0')
                        ))
            elif plat == 'TRADING212':
                t212_files.append((file_path, meta.extension))

        # 1. PROCESAR DEGIRO (Atómico)
        if degiro_files:
            from src.ingestion.degiro_reader import parse as parse_degiro
            trades, divs = parse_degiro(degiro_files)
            all_raw_trades.extend(trades)
            all_raw_divs.extend(divs)
        
        # Solo añadir el PDF si no hay dividendos granulares (para evitar doble conteo)
        degiro_divs_count = sum(1 for d in all_raw_divs if d.platform.upper() == 'DEGIRO')
        if degiro_divs_count == 0:
            all_raw_divs.extend(pdf_divs_fallback)

        # 2. PROCESAR TRADING 212
        from src.ingestion.trading212_reader import parse as parse_t212
        for file_path, ext in t212_files:
            trades, divs = parse_t212(file_path)
            if ext == '.pdf':
                if not has_t212_csv:
                    all_raw_trades.extend(trades)
                all_raw_divs.extend(divs)
            else:
                all_raw_trades.extend(trades)
                all_raw_divs.extend(divs)


        # 1. DE-DUPLICACIÓN INTELIGENTE (Trades)
        unique_trades = []
        seen_keys_by_file = {} # file -> set of keys
        
        # Para deduplicación entre archivos (overlaps)
        # Usamos un buffer global de (fecha, isin, cantidad, direccion, order_id) -> source_file
        global_seen = {} 

        for t in all_raw_trades:
            isin_key = t.isin if (t.isin and len(t.isin) > 5) else t.ticker or t.asset
            order_id = t.notes.split("|")[-1] if "|" in t.notes else ""
            
            # Clave de identidad de la operación
            # Incluimos el ID de orden para diferenciar órdenes distintas
            # Pero permitimos que la misma orden tenga múltiples filas si están en el mismo archivo
            # (Ej: DeGiro split 3+3 shares)
            key_identity = (t.date.strftime('%Y%m%d%H%M'), isin_key, round(t.quantity, 8), t.direction, order_id)
            
            if key_identity not in global_seen:
                # Es una operación nueva nunca vista
                global_seen[key_identity] = t
                unique_trades.append(t)
            else:
                # Ya hemos visto esta operación en OTRO archivo (o en el mismo)
                existing_t = global_seen[key_identity]
                
                if t.source_file == existing_t.source_file:
                    # ¡IMPORTANTE! Si es el MISMO archivo, NO es un duplicado, es una ejecución dividida
                    # (Como el caso Acciona 3+3). Añadimos sin deduplicar.
                    unique_trades.append(t)
                else:
                    # Es el mismo trade pero en un archivo DIFERENTE. Aplicamos prioridad.
                    # 1. CSV tiene prioridad sobre PDF
                    # 2. Origen Transactions tiene prioridad sobre Fallback
                    current_is_fallback = "FALLBACK" in t.notes
                    existing_is_fallback = "FALLBACK" in existing_t.notes
                    
                    if ('.csv' in t.source_file.lower() and '.pdf' in existing_t.source_file.lower()) or \
                       (not current_is_fallback and existing_is_fallback):
                        # Reemplazamos en la lista de resultados
                        # (Esto es complejo porque unique_trades es una lista. 
                        #  Mejor usar un diccionario file_agnostic_id -> trade y luego aplanar)
                        pass

        # REFACTORIZACIÓN: Uso de Diccionario Agregador por Identidad + Origen
        # identity = (date, isin, qty, dir, order_id)
        # final_selection = { (identity, source_file) : Trade }
        # Luego deduplicamos entre identidades prefiriendo el mejor source.
        
        identity_map = {} # (identity, source_file, row_counter) -> Trade
        # Usamos un contador para diferenciar filas idénticas dentro del mismo archivo
        row_counters = {} # (identity, source_file) -> int

        for t in all_raw_trades:
            isin_key = t.isin if (t.isin and len(t.isin) > 5) else t.ticker or t.asset
            # Clave de identidad de la operación (Agregación por día, activo y cantidad)
            # Ignoramos hora y order_id para permitir match entre Transactions y Account.
            identity = (t.date.strftime('%Y%m%d'), isin_key, round(t.quantity, 8), t.direction)
            
            source_key = (identity, t.source_file)
            row_counters[source_key] = row_counters.get(source_key, 0) + 1
            full_key = (identity, t.source_file, row_counters[source_key])
            identity_map[full_key] = t

        # Ahora deduplicamos entre archivos para cada (identity, counter)
        final_trades_dict = {} # (identity, counter) -> Trade
        for (identity, source, counter), t in identity_map.items():
            dedup_key = (identity, counter)
            if dedup_key not in final_trades_dict:
                final_trades_dict[dedup_key] = t
            else:
                # Prioridad entre archivos
                existing = final_trades_dict[dedup_key]
                t_is_csv = '.csv' in t.source_file.lower()
                ex_is_csv = '.csv' in existing.source_file.lower()
                t_is_fallback = "FALLBACK" in t.notes
                ex_is_fallback = "FALLBACK" in existing.notes
                
                # NUEVO: Prioridad para eventos corporativos (tienen notas descriptivas)
                reorg_kws = ['SPLIT', 'REORG', 'CAMBIO DE PRODUCTO', 'MERGER']
                t_has_reorg = any(kw in t.notes.upper() for kw in reorg_kws)
                ex_has_reorg = any(kw in existing.notes.upper() for kw in reorg_kws)

                if (t_has_reorg and not ex_has_reorg) or \
                   (t_is_csv and not ex_is_csv) or \
                   (not t_is_fallback and ex_is_fallback):
                    final_trades_dict[dedup_key] = t
                    
        unique_trades = list(final_trades_dict.values())

        # 2. DE-DUPLICACIÓN INTELIGENTE (Dividendos)
        # Separamos dividendos reales de gastos/intereses para no de-duplicar estos últimos
        non_dedup_items = [d for d in all_raw_divs if d.type in ['fee', 'interest']]
        dedup_targets = [d for d in all_raw_divs if d.type not in ['fee', 'interest']]
        
        seen_divs = {}
        for d in dedup_targets:
            isin_key = d.isin if (d.isin and len(d.isin) > 5) else d.asset
            key = (d.date.strftime('%Y%m%d'), isin_key, round(d.gross_eur, 2), round(d.custody_fee_eur, 2))
            
            if key not in seen_divs:
                seen_divs[key] = d
            else:
                # Prioridad: Mantener el registro que NO tenga basura "IMPORTE" en el nombre
                current_is_dirty = any(g in d.asset.upper() for g in ["IMPORTE", "MPORTE", "NETO"])
                existing_is_dirty = any(g in seen_divs[key].asset.upper() for g in ["IMPORTE", "MPORTE", "NETO"])
                if not current_is_dirty and existing_is_dirty:
                    seen_divs[key] = d
        
        unique_divs = list(seen_divs.values()) + non_dedup_items
        
        if orphan_trades:
            unique_trades.extend(orphan_trades)
        if orphan_divs:
            unique_divs.extend(orphan_divs)

        self.engine.process_trades(unique_trades)
        self.engine.process_dividends(unique_divs)

        # 4. Ajuste de precisión fiscal (Priorizar Informe PDF para Dividendos)
        pdf_gross = getattr(self, 'report_summary', {}).get('dividendos_brutos', Decimal('0'))
        if pdf_gross > 0:
            # Solo verificamos los que son realmente dividendos, no las comisiones
            divs_to_adjust = [d for d in self.engine.dividends if d.type == 'dividend']
            
            calc_gross = sum(d.gross_eur for d in divs_to_adjust)
            diff = abs(calc_gross - pdf_gross)
            if diff > Decimal('0.01'):
                self.engine.warnings.append(
                    f"⚠️ DESVIACIÓN EN DIVIDENDOS: El PDF Anual declara {pdf_gross}€ pero los cálculos transaccionales arrojan {calc_gross}€ (Desvío: {diff}€). "
                    f"Revisa manualmente los CSVs aportados."
                )

        if len(self.engine.ledger.events) > 0:
            print(f"SUCCESS: {len(self.engine.ledger.events)} corporate events loaded (including Senseonics split).")

    def get_all_trades(self) -> List:
        return self.engine.raw_trades

    def get_warnings(self) -> List[str]:
        return self.engine.warnings

if __name__ == "__main__":
    import os
    from src.ingestion.file_classifier import FileClassifier
    
    print("\n" + "="*60)
    print("      ANTIGRAVITY FISCAL ENGINE - REPORTE IRPF 2025")
    print("="*60)
    
    classifier = FileClassifier()
    inventory = classifier.get_inventory('uploads', {})
    
    specialist = StockSpecialist(tax_year=2025)
    specialist.process_files('uploads', inventory)
    
    tax_events, dividends = specialist.engine.tax_events, specialist.engine.dividends
    
    # 1. BLOQUE DIVIDENDOS [0029]
    print("\n[0029] DIVIDENDOS Y RENDIMIENTOS (BASE DEL AHORRO)")
    print(f"{'Activo':<40} | {'Bruto':>10} | {'Ret.Ext':>10} | {'Ret.Esp':>10}")
    print("-" * 75)
    div_items = [d for d in dividends if d.type == 'dividend']
    for d in sorted(div_items, key=lambda x: x.asset):
        print(f"{d.asset[:40]:<40} | {d.gross_eur:>10.2f} | {d.withholding_foreign_eur:>10.2f} | {d.withholding_spain_eur:>10.2f}")
    
    subtotal_bruto = sum(d.gross_eur for d in div_items)
    subtotal_ext = sum(d.withholding_foreign_eur for d in div_items)
    subtotal_esp = sum(d.withholding_spain_eur for d in div_items)
    print("-" * 75)
    print(f"{'SUBTOTAL DEGIRO':<40} | {subtotal_bruto:>10.2f} | {subtotal_ext:>10.2f} | {subtotal_esp:>10.2f}")

    # 2. BLOQUE GASTOS [0035]
    print("\n[0035] GASTOS DE ADMINISTRACIÓN Y DEPÓSITO (DEDUCIBLES)")
    fees = [d for d in dividends if d.type == 'fee']
    for f in fees:
        print(f"- {f.asset}: {f.custody_fee_eur:>10.2f} EUR")
    print(f"TOTAL GASTOS DEDUCIBLES: {sum(f.custody_fee_eur for f in fees):>10.2f} EUR")

    # 3. BLOQUE GANANCIAS Y PÉRDIDAS (BLOQUE 3)
    print("\n[BLOQUE 3] GANANCIAS Y PÉRDIDAS PATRIMONIALES (REALIZADO)")
    gains = [t for t in tax_events if t.gain_loss_eur > 0]
    losses = [t for t in tax_events if t.gain_loss_eur < 0]
    
    print(f"Total Ganancias Patrimoniales: {sum(t.gain_loss_eur for t in gains):>10.2f} EUR ({len(gains)} ops)")
    print(f"Total Pérdidas Patrimoniales:  {sum(abs(t.gain_loss_eur) for t in losses):>10.2f} EUR ({len(losses)} ops)")
    print(f"RESULTADO NETO G/P:            {sum(t.gain_loss_eur for t in tax_events):>10.2f} EUR")

    # 4. EVENTOS CORPORATIVOS (TRACEABILIDAD)
    if specialist.engine.ledger.events:
        print("\n[INFO] EVENTOS CORPORATIVOS Y REORGANIZACIONES (NEUTRALES)")
        for ev in specialist.engine.ledger.events:
            print(f"- {ev.event_date.date()} | {ev.origin_asset_id} -> {ev.target_asset_id} (Ratio: {ev.quantity_ratio})")

    # 5. ALERTAS
    warnings = specialist.get_warnings()
    if warnings:
        print("\n[⚠️] ALERTAS Y DISCREPANCIAS:")
        for w in warnings:
            print(f"  - {w}")

    print("\n" + "="*60)
    print("      REPORTE FINALIZADO - LISTO PARA AUDITORÍA")
    print("="*60 + "\n")
