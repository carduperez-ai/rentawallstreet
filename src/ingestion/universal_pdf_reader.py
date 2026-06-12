
import pdfplumber
from decimal import Decimal
from datetime import datetime
from typing import List, Tuple, Dict, Any
from src.domain.stock_entities import Trade
from src.domain.stock_fiscal_entities import Dividend

class UniversalPDFReader:
    """
    Motor heurístico para extraer datos de CUALQUIER PDF financiero.
    Busca tablas y mapea columnas por palabras clave universales.
    """

    def parse(self, filepath: str, platform: str = "GENERIC") -> Tuple[List[Trade], List[Dividend]]:
        trades: List[Trade] = []
        dividends: List[Dividend] = []
        
        try:
            with pdfplumber.open(filepath) as pdf:
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() or ""
                    # 1. Intentar con tablas estructuradas
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table) < 2: continue
                        headers = [str(c).replace('\n', ' ').strip().lower() for c in table[0] if c]
                        idx_map = self._map_headers(headers)
                        if idx_map.get('date') != -1:
                            self._process_table(table, idx_map, trades, dividends, platform)
                
                # 2. FALLBACK: Escaneo de texto heurístico (Si no se encontró nada sustancial)
                if len(trades) == 0 and len(dividends) < 5:
                    self._heuristic_text_scan(full_text, trades, dividends, platform)
                            
        except Exception as e:
            print(f"  [UNIVERSAL PDF ERROR] {e}")
            
        return trades, dividends

    def _heuristic_text_scan(self, text: str, trades: List[Trade], dividends: List[Dividend], platform: str):
        """
        Escaneo de fuerza bruta con validación aritmética.
        """
        lines = text.split('\n')
        for line in lines:
            # 1. Buscar Fecha (Ancla)
            date_match = re.search(r"(\d{1,4}[./-]\d{1,4}[./-]\d{1,4})|(\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})", line)
            if not date_match: continue
            
            dt = self._parse_ultra_flexible_date(date_match.group(0))
            isin_match = re.search(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b", line)
            isin = isin_match.group(1) if isin_match else ""
            
            # 2. Extraer Números
            numbers = []
            for t in line.split():
                if any(c.isdigit() for c in t) and t not in date_match.group(0) and t != isin:
                    try:
                        val = self._to_decimal(t)
                        if val != 0: numbers.append(val)
                    except: continue
            
            if len(numbers) >= 2:
                # 3. VALIDACIÓN ARITMÉTICA (¿X * Y = Z?)
                # Intentamos identificar Qty, Price y Total probando combinaciones
                qty, price, total = Decimal('0'), Decimal('0'), Decimal('0')
                found_math = False
                
                # Probar todas las combinaciones de 3 números
                for i in range(len(numbers)):
                    for j in range(len(numbers)):
                        for k in range(len(numbers)):
                            if i == j or j == k or i == k: continue
                            n1, n2, n3 = abs(numbers[i]), abs(numbers[j]), abs(numbers[k])
                            # Tolerancia del 1% para tipos de cambio o redondeos
                            if abs(n1 * n2 - n3) < (n3 * Decimal('0.02')):
                                qty, price, total = n1, n2, n3
                                found_math = True
                                break
                        if found_math: break
                    if found_math: break
                
                # Fallback si no hay match aritmético (usar heurística de magnitud)
                if not found_math:
                    sorted_nums = sorted([abs(n) for n in numbers])
                    qty = sorted_nums[0]
                    total = sorted_nums[-1]
                
                asset_search = re.findall(r"\b[A-Z]{2,10}\b", line)
                asset = "UNKNOWN"
                for a in asset_search:
                    if a not in (isin, "USD", "EUR", "GBP", "JPY", "BUY", "SELL"):
                        asset = a
                        break
                
                if any(kw in line.lower() for kw in ['div', 'yield', 'interest', 'retenci', 'wht']):
                    dividends.append(Dividend(
                        date=dt, platform=platform, asset=asset, isin=isin,
                        gross_eur=total, withholding_foreign_eur=qty if qty < total * Decimal('0.5') else Decimal('0'),
                        withholding_spain_eur=Decimal('0')
                    ))
                else:
                    direction = 'sell' if any(kw in line.lower() for kw in ['sell', 'venta', 'pago', 'out']) else 'buy'
                    trades.append(Trade(
                        date=dt, platform=platform, asset=asset, isin=isin, ticker=asset,
                        asset_type="stock", direction=direction, quantity=qty,
                        value_eur=total, fee_eur=Decimal('0')
                    ))

    def _parse_ultra_flexible_date(self, s: str) -> datetime:
        # Eliminamos ruidos comunes en fechas de PDFs
        s = re.sub(r'[^\d/.\-A-Za-z\s]', '', s).strip()
        
        # Diccionario de meses para español/inglés
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
            'ene': 1, 'abr': 4, 'dic': 12
        }
        
        # Intentar formatos numéricos comunes
        for fmt in ["%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y", "%Y.%m.%d", "%d-%m-%Y", "%Y-%m-%d", "%d %m %Y"]:
            try: return datetime.strptime(s, fmt)
            except: continue
            
        # Intentar con nombres de mes
        for m_name, m_val in months.items():
            if m_name in s.lower():
                # Extraer números de la fecha
                nums = re.findall(r'\d+', s)
                if len(nums) >= 2:
                    day = int(nums[0]) if len(nums[0]) <= 2 else int(nums[1])
                    year = int(nums[1]) if len(nums[1]) > 2 else int(nums[0])
                    if len(nums) == 3: # DD Mes YYYY
                        day, year = int(nums[0]), int(nums[2])
                    if year < 100: year += 2000
                    try: return datetime(year, m_val, day)
                    except: continue
                    
        return datetime.now()

    def _map_headers(self, headers: List[str]) -> Dict[str, int]:
        mapping = {
            'date': ['fecha', 'date', 'time', 'tiempo', 'momento'],
            'asset': ['producto', 'product', 'instrument', 'activo', 'ticker', 'isin', 'symbol'],
            'type': ['tipo', 'type', 'acción', 'action', 'operación', 'operation'],
            'qty': ['cantidad', 'quantity', 'shares', 'monto', 'ero', 'number'],
            'total': ['total', 'importe', 'amount', 'valor', 'value', 'net'],
            'fee': ['comisión', 'fee', 'coste', 'cost', 'comision'],
            'wht': ['retención', 'withholding', 'impuesto', 'tax']
        }
        
        res = {}
        for key, keywords in mapping.items():
            res[key] = -1
            for i, h in enumerate(headers):
                if any(kw in h for kw in keywords):
                    res[key] = i
                    break
        return res

    def _process_table(self, table: List[List[str]], idx_map: Dict[str, int], trades: List[Trade], dividends: List[Dividend], platform: str):
        for row in table[1:]:
            try:
                # Limpieza de fila
                row = [str(c).strip() if c else "" for c in row]
                
                dt_str = row[idx_map['date']]
                dt = self._parse_flexible_date(dt_str)
                
                t_type = row[idx_map['type']].lower() if idx_map['type'] != -1 else ""
                asset = row[idx_map['asset']] if idx_map['asset'] != -1 else "UNKNOWN"
                
                total = abs(self._to_decimal(row[idx_map['total']])) if idx_map['total'] != -1 else Decimal('0')
                qty = abs(self._to_decimal(row[idx_map['qty']])) if idx_map['qty'] != -1 else Decimal('0')
                fee = abs(self._to_decimal(row[idx_map['fee']])) if idx_map['fee'] != -1 else Decimal('0')
                wht = abs(self._to_decimal(row[idx_map['wht']])) if idx_map['wht'] != -1 else Decimal('0')

                # Heurística de Dividendos
                if any(kw in t_type or kw in asset.lower() for kw in ['div', 'interest', 'rendimiento', 'cupon']):
                    dividends.append(Dividend(
                        date=dt, platform=platform, asset=asset, isin="",
                        gross_eur=total + wht, withholding_foreign_eur=wht, withholding_spain_eur=Decimal('0')
                    ))
                
                # Heurística de Trades (Buy/Sell)
                elif any(kw in t_type for kw in ['buy', 'sell', 'compra', 'venta', 'exchange']):
                    direction = 'buy' if any(kw in t_type for kw in ['buy', 'compra']) else 'sell'
                    trades.append(Trade(
                        date=dt, platform=platform, asset=asset, isin="", ticker="",
                        asset_type="stock", direction=direction, quantity=qty,
                        value_eur=total, fee_eur=fee
                    ))
            except:
                continue

    def _parse_flexible_date(self, s: str) -> datetime:
        s = s.split('\n')[0].strip() # Limpieza de multilínea
        for fmt in ["%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
            try: return datetime.strptime(s, fmt)
            except: continue
        return datetime.now()

    def _to_decimal(self, s: str) -> Decimal:
        if not s or s in ('-', ''): return Decimal('0')
        # Limpieza de símbolos de moneda
        clean = re.sub(r'[^0-9\.,\-]', '', str(s))
        # Formato europeo vs americano
        if ',' in clean and '.' in clean:
            if clean.find(',') > clean.find('.'): # 1.234,56
                clean = clean.replace('.', '').replace(',', '.')
            else: # 1,234.56
                clean = clean.replace(',', '')
        elif ',' in clean: # 1234,56
            clean = clean.replace(',', '.')
            
        try: return Decimal(clean)
        except: return Decimal('0')

import re
