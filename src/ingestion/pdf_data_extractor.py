import pdfplumber
import re
import os
from decimal import Decimal
from typing import Dict, Optional, List
from src.domain.stock_entities import Trade


class PDFProcessor:
    """Procesador avanzado para extraer cuadros y notas del Informe Fiscal de DeGiro."""

    def process(self, filepath: str) -> Optional[Dict]:
        try:
            with pdfplumber.open(filepath) as pdf:
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() + "\n"

                # Normalizar texto para ser tolerante a errores de codificación
                # Sustituimos caracteres extraños por comodines en las regex

                summary = {
                    "comisiones_posiciones_cerradas": Decimal("0"),
                    "comisiones_pagadas_2025": Decimal("0"),
                    "tasa_tobin_realizada": Decimal("0"),
                    "conectividad_mercado": Decimal("0"),
                    "dividendos_brutos": Decimal("0"),
                    "retencion_extranjera": Decimal("0"),
                    "notas": [],
                }

                # Regex ultra-flexibles para los cuadros de DeGiro

                # 1. Comisiones posiciones cerradas (Nota **)
                m1 = re.search(r"posiciones cerradas .*? \*\*?\s+([\d\.,]+)", full_text, re.DOTALL)
                if m1:
                    summary["comisiones_posiciones_cerradas"] = self._to_decimal(m1.group(1))

                # 2. Total comisiones pagadas (Nota *) - Usamos comodín para 'año'
                m2 = re.search(r"pagadas en el a.*?o 2025 \*?\s+([\d\.,]+)", full_text)
                if m2:
                    summary["comisiones_pagadas_2025"] = self._to_decimal(m2.group(1))

                # 3. Tobin e ITF
                m3 = re.search(r"Transacciones Financieras realizado\s+([\d\.,]+)", full_text)
                if m3:
                    summary["tasa_tobin_realizada"] = self._to_decimal(m3.group(1))

                # 4. Conectividad
                m4 = re.search(r"conectividad con el mercado\s+([\d\.,]+)", full_text)
                if m4:
                    summary["conectividad_mercado"] = self._to_decimal(m4.group(1))

                # 5. Ganancias y Pérdidas (NUEVO)
                m_gain = re.search(r"Ganancias patrimoniales totales\s+([\d\.,]+)", full_text)
                if m_gain:
                    summary["ganancias_patrimoniales"] = self._to_decimal(m_gain.group(1))

                m_loss = re.search(r"P[eé]rdidas totales\s+([\d\.,]+)", full_text)
                if m_loss:
                    summary["perdidas_totales"] = self._to_decimal(m_loss.group(1))

                # 6. Dividendos (Cuadro de rentas)
                # Buscamos la última línea de la tabla de dividendos que contiene los totales acumulados
                # El formato suele ser: [Asset] [Gross] [Withholding] [Net] y luego una línea de totales o la última fila tiene el acumulado
                # En este PDF parece que hay una fila de Pfizer y luego el total acumulado 88,52 -16,50
                div_section = re.search(
                    r"Dividendos, Cupones y otras remuneraciones(.*?)(?:Distribuciones|Relaci[oó]n de ganancias)",
                    full_text,
                    re.DOTALL,
                )
                if div_section:
                    div_text = div_section.group(1)
                    # Buscar el último bloque de 3 importes que suelen ser los totales
                    matches = re.findall(r"([\d\.,]+)\s+EUR\s+(-?[\d\.,]+)\s+EUR\s+([\d\.,]+)\s+EUR", div_text)
                    if matches:
                        last_match = matches[-1]
                        summary["dividendos_brutos"] = self._to_decimal(last_match[0])
                        summary["retencion_extranjera"] = abs(self._to_decimal(last_match[1]))

                # Agregar notas explicativas si se detectan los símbolos
                if "**" in full_text:
                    summary["notas"].append("Nota ** detectada: Incluye costes históricos de apertura.")
                if "*" in full_text:
                    summary["notas"].append("Nota * detectada: Incluye costes de cambio de divisa manual.")

                return summary
        except Exception as e:
            print(f"  [ERROR PDF] {e}")
            return None

    def extract_trades(self, filepath: str) -> List["Trade"]:
        """Extrae transacciones individuales de un PDF de transacciones."""
        from src.domain.stock_entities import Trade
        import datetime

        trades = []
        try:
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    # Patrón: Fecha Hora Producto ISIN Bolsa Centro Cantidad Precio ...
                    lines = text.split("\n")
                    for line in lines:
                        # Regex ultra-flexible: Fecha, Hora, ..., ISIN, ..., Cantidad, Precio, ..., Fee, Total
                        match = re.search(
                            r"(\d{2}-\d{2}-\d{4})\s+(\d{2}:\d{2}).*?([A-Z0-9]{12}).*?\s+(-?\d+)\s+([\d,.]+)\s+[A-Z]{3}.*?([-?\d,.]+)\s+([-?\d,.]+)\s+([-?\d,.]+)\s*$",
                            line,
                        )
                        if match:
                            date_str, time_str, isin, qty, price, fx_fee, trans_fee, total = match.groups()

                            dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
                            q = Decimal(qty.replace(".", ""))

                            parts = line.split()
                            try:
                                eur_val_idx = parts.index(fx_fee) - 1
                                eur_val = self._to_decimal(parts[eur_val_idx])
                            except:
                                eur_val = abs(q * self._to_decimal(price))

                            trades.append(
                                Trade(
                                    date=dt,
                                    platform="DeGiro",
                                    asset=isin,
                                    isin=isin,
                                    ticker="",
                                    asset_type="stock",
                                    direction="buy" if q > 0 else "sell",
                                    quantity=abs(q),
                                    value_eur=abs(eur_val),
                                    fee_eur=abs(self._to_decimal(trans_fee)),
                                    notes="EXTRACTED_FROM_PDF",
                                    source_file=os.path.basename(filepath),
                                )
                            )
                            # print(f"    [OK] Detectado trade: {dt} {isin} q={q}")
        except Exception as e:
            print(f"  [ERROR PDF TRADES] {e}")
        return trades

    def _to_decimal(self, text: str) -> Decimal:
        if not text:
            return Decimal("0")
        clean = text.replace(".", "").replace(",", ".")
        try:
            return Decimal(clean)
        except:
            return Decimal("0")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        proc = PDFProcessor()
        res = proc.process(sys.argv[1])
        import json

        class DecimalEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, Decimal):
                    return str(obj)
                return super(DecimalEncoder, self).default(obj)

        print(json.dumps(res, indent=2, cls=DecimalEncoder))
