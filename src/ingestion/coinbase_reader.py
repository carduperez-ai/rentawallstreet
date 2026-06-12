import os
import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Tuple, Any
from zoneinfo import ZoneInfo

from src.domain.crypto_entities import Trade
from src.domain.fiscal_entities import Dividend
from src.accounting.currency_valuation import oracle

# ---------------------------------------------------------------------------
# Tipos de transacción del CSV oficial de Coinbase
# ---------------------------------------------------------------------------
# Eventos de compra/venta que generan Trade
TRADE_TYPES = {
    'buy', 'sell',
    'advanced trade buy', 'advanced trade sell',
    'convert',        # permuta crypto-crypto
    'cardspend',      # pago con tarjeta Visa Coinbase (salida de crypto)
}
# Ingresos pasivos que generan Dividend
INCOME_TYPES = {
    'rewards income', 'staking income',
    'learning reward', 'coinbase earn',
    'card cashback', 'earn payout', 'earn_payout',
    'inflation reward',
}
# Movimientos sin evento fiscal (entradas/salidas de wallet externa)
IGNORED_TYPES = {'send', 'receive'}

FIAT = {'EUR', 'USD', 'GBP', 'CAD', 'AUD', 'CHF'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_decimal(val: Any) -> Decimal:
    try:
        return Decimal(str(val).strip().replace(',', '').replace(' ', ''))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def _parse_date(s: str) -> datetime:
    s = str(s).strip()
    # Coinbase usa ISO 8601 con zona horaria: 2021-03-14T15:30:00Z
    for fmt in (
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if 'Z' in fmt:
                return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    return None  # Sin fallback: fecha inválida se descarta


def _safe_eur(amount: Decimal, asset: str, dt: datetime, spot_price: Decimal = None, spot_currency: str = None) -> Decimal:
    """
    Convierte `amount` de `asset` a EUR.
    Si Coinbase ya nos da el precio spot, lo usamos directamente (sin llamar al oráculo).
    """
    if amount == Decimal('0'):
        return Decimal('0')
    asset_up = asset.upper()
    if asset_up == 'EUR':
        return amount
    # Usar precio spot facilitado por Coinbase si es coherente
    if spot_price and spot_price > 0 and spot_currency:
        sc = spot_currency.upper()
        val_in_spot_currency = amount * spot_price
        if sc == 'EUR':
            return val_in_spot_currency
        # Convertir de USD (o similar) a EUR vía oráculo solo para el tipo de cambio fiat
        rate = oracle.get_price_eur(sc, dt)
        if rate:
            return val_in_spot_currency * rate
    # Fallback: oráculo directo
    price = oracle.get_price_eur(asset_up, dt)
    return amount * price if price else Decimal('0')


def _normalize_type(raw: str) -> str:
    return raw.strip().lower()


# ---------------------------------------------------------------------------
# Lector principal
# ---------------------------------------------------------------------------

class CoinbaseIngestor:
    """
    Lector nativo para el CSV de transacciones de Coinbase.
    Cabeceras: Timestamp, Transaction Type, Asset, Quantity Transacted,
               Spot Price Currency, Spot Price at Transaction,
               Subtotal, Total (inclusive of fees and/or spread),
               Fees and/or Spread, Notes
    """

    # Las primeras filas del CSV de Coinbase suelen contener metadatos antes
    # de la cabecera real; buscamos la línea que contenga 'Timestamp'.
    _HEADER_MARKER = 'timestamp'

    def __init__(self):
        self.warnings: List[str] = []
        self._rows: List[Dict] = []
        self._pdf_trades: List[Trade] = []
        self._pdf_dividends: List[Dividend] = []

    def process_file(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)

        if ext == '.pdf':
            from src.ingestion.universal_pdf_reader import UniversalPDFReader
            t, d = UniversalPDFReader().parse(file_path, platform="COINBASE")
            self._pdf_trades.extend(t)
            self._pdf_dividends.extend(d)
            return True

        if ext not in ('.csv', '.xlsx', '.xls'):
            self.warnings.append(f"Coinbase ignora formato no soportado: {filename}")
            return False

        try:
            if ext in ('.xlsx', '.xls'):
                import pandas as pd
                df = pd.read_excel(file_path, header=None)
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False, header=False)
                lines = csv_buffer.getvalue().splitlines(keepends=True)
            else:
                with open(file_path, newline='', encoding='utf-8-sig') as fh:
                    lines = fh.readlines()

            # Localizar la fila de cabecera (Coinbase inserta ~7 líneas de metadata antes)
            header_idx = None
            for i, line in enumerate(lines):
                if self._HEADER_MARKER in line.lower():
                    header_idx = i
                    break

            if header_idx is None:
                self.warnings.append(f"No se encontró cabecera en {filename}")
                return False

            data_block = ''.join(lines[header_idx:])
            reader = csv.DictReader(io.StringIO(data_block))
            # Normalizar nombres de columnas (strip + lower) para robustez
            raw_rows = list(reader)
            if not raw_rows:
                return True

            # Construir mapa de nombre original → nombre normalizado
            orig_headers = list(raw_rows[0].keys())
            col_map = {h: h.strip().lower() for h in orig_headers}

            for raw_row in raw_rows:
                norm = {col_map[k]: v.strip() if isinstance(v, str) else v
                        for k, v in raw_row.items()}
                self._rows.append(norm)

            return True
        except Exception as e:
            self.warnings.append(f"Error leyendo {filename}: {e}")
            return False

    # -----------------------------------------------------------------------
    # Columnas normalizadas (robustas ante variaciones menores de nombre)
    # -----------------------------------------------------------------------

    @staticmethod
    def _get(row: Dict, *keys: str) -> str:
        for k in keys:
            if k in row:
                return str(row[k]).strip()
        return ''

    # -----------------------------------------------------------------------
    # Propiedades calculadas
    # -----------------------------------------------------------------------

    @property
    def transactions(self) -> List[Trade]:
        trades: List[Trade] = list(self._pdf_trades)

        # Para Convert necesitamos emparejar la fila de salida con la de entrada.
        # Coinbase las genera como dos filas consecutivas con el mismo timestamp y Notes.
        # Procesamos primero todas las filas simples y acumulamos las Convert por separado.
        convert_buffer: List[Dict] = []

        for row in self._rows:
            tx_type = _normalize_type(self._get(row, 'transaction type'))

            if tx_type not in TRADE_TYPES:
                continue

            dt    = _parse_date(self._get(row, 'timestamp'))
            if dt is None: continue  # Fecha inválida: descartar fila
            asset = self._get(row, 'asset').upper()
            qty   = _parse_decimal(self._get(row, 'quantity transacted'))
            spot_currency = self._get(row, 'spot price currency').upper()
            spot_price    = _parse_decimal(self._get(row, 'spot price at transaction'))
            subtotal      = _parse_decimal(self._get(row, 'subtotal'))
            total         = _parse_decimal(self._get(row, 'total (inclusive of fees and/or spread)'))
            fee_raw       = _parse_decimal(self._get(row, 'fees and/or spread'))
            notes         = self._get(row, 'notes')

            # Valor de la transacción: preferimos 'subtotal' (sin fees) para el coste base
            val_source = subtotal if subtotal > 0 else total
            val_eur = _safe_eur(val_source, spot_currency or 'USD', dt) if spot_currency in FIAT or spot_currency == '' else _safe_eur(qty, asset, dt, spot_price, spot_currency)
            if val_eur == Decimal('0') and spot_price > 0:
                val_eur = _safe_eur(val_source, spot_currency if spot_currency else 'USD', dt)

            fee_eur = _safe_eur(fee_raw, spot_currency if spot_currency else 'USD', dt)

            # ── Convert: agrupamos en un buffer plano ──
            if tx_type == 'convert':
                convert_buffer.append({
                    'dt': dt, 'asset': asset, 'qty': qty,
                    'val_eur': val_eur, 'fee_eur': fee_eur, 'notes': notes,
                    'raw_type': tx_type,
                })
                continue

            # ── Buy / Advanced Trade Buy ──
            if tx_type in ('buy', 'advanced trade buy'):
                trades.append(Trade(
                    date=dt, asset=asset, platform='Coinbase',
                    direction='buy', quantity=qty,
                    value_eur=val_eur, fee_eur=fee_eur,
                    asset_type='crypto',
                    notes=f"Coinbase {tx_type} | {notes}",
                ))

            # ── Sell / Advanced Trade Sell / CardSpend ──
            elif tx_type in ('sell', 'advanced trade sell', 'cardspend'):
                trades.append(Trade(
                    date=dt, asset=asset, platform='Coinbase',
                    direction='sell', quantity=qty,
                    value_eur=val_eur, fee_eur=fee_eur,
                    asset_type='crypto',
                    notes=f"Coinbase {tx_type} | {notes}",
                ))

        # ── Procesar pares Convert mediante Delta Temporal ──
        # Agrupamos primero por notas (que identifican el par "Convert A to B")
        converts_by_notes = {}
        for leg in convert_buffer:
            converts_by_notes.setdefault(leg['notes'], []).append(leg)

        for notes_text, legs in converts_by_notes.items():
            # Ordenar por fecha
            legs.sort(key=lambda x: x['dt'])
            paired = set()
            for i in range(len(legs)):
                if i in paired: continue
                best_match = None
                for j in range(i + 1, len(legs)):
                    if j in paired: continue
                    delta = abs((legs[j]['dt'] - legs[i]['dt']).total_seconds())
                    if delta <= 2.0:
                        best_match = j
                        break
                        
                if best_match is not None:
                    paired.add(i)
                    paired.add(best_match)
                    leg1 = legs[i]
                    leg2 = legs[best_match]
                    val_eur = max(leg1['val_eur'], leg2['val_eur'])
                    fee_eur = leg1['fee_eur'] + leg2['fee_eur']
                    dt_group = leg1['dt']
                    
                    for leg in (leg1, leg2):
                        if 'converted' in notes_text.lower():
                            parts = notes_text.lower().replace('converted ', '')
                            sold_symbol = parts.split(' ')[1].upper() if len(parts.split(' ')) > 1 else leg1['asset']
                            direction = 'sell' if leg['asset'] == sold_symbol else 'buy'
                        else:
                            direction = 'sell' if leg == leg1 else 'buy'

                        # Fee asignado solo a la pierna SELL para evitar doble conteo en FIFO
                        leg_fee = fee_eur if direction == 'sell' else Decimal('0')
                        trades.append(Trade(
                            date=dt_group, asset=leg['asset'], platform='Coinbase',
                            direction=direction, quantity=leg['qty'],
                            value_eur=leg['val_eur'], fee_eur=leg_fee,  # val individual por pierna
                            asset_type='crypto',
                            notes=f"Coinbase convert | {notes_text}",
                        ))
                else:
                    self.warnings.append(f"Fallo al emparejar Convert: {legs[i]['asset']} ({legs[i]['dt']}). Posible orfandad.")

        return sorted(trades, key=lambda t: t.date)

    @property
    def dividends(self) -> List[Dividend]:
        result: List[Dividend] = list(self._pdf_dividends)
        for row in self._rows:
            tx_type = _normalize_type(self._get(row, 'transaction type'))
            if tx_type not in INCOME_TYPES:
                continue

            dt    = _parse_date(self._get(row, 'timestamp'))
            if dt is None: continue  # Fecha inválida: descartar fila
            asset = self._get(row, 'asset').upper()
            qty   = _parse_decimal(self._get(row, 'quantity transacted'))
            spot_currency = self._get(row, 'spot price currency').upper()
            spot_price    = _parse_decimal(self._get(row, 'spot price at transaction'))
            fee_raw       = _parse_decimal(self._get(row, 'fees and/or spread'))
            notes         = self._get(row, 'notes')

            val_eur = _safe_eur(qty, asset, dt, spot_price, spot_currency)
            fee_eur = _safe_eur(fee_raw, spot_currency if spot_currency else 'USD', dt)

            # Clasificación de subtipo para la declaración
            if tx_type in ('rewards income', 'staking income', 'inflation reward'):
                income_type = 'staking'
            elif tx_type in ('learning reward', 'coinbase earn'):
                income_type = 'other_income'   # rendimiento del capital mobiliario atípico
            else:  # card cashback
                income_type = 'cashback'

            result.append(Dividend(
                date=dt, platform='Coinbase', asset=asset, isin='',
                gross_eur=val_eur,
                withholding_foreign_eur=Decimal('0'),
                withholding_spain_eur=Decimal('0'),
                type=income_type,
            ))

        return result


# ---------------------------------------------------------------------------
# Punto de entrada público (mismo contrato que binance_reader / kraken_reader)
# ---------------------------------------------------------------------------

def parse(file_paths: List[str]) -> Tuple[List[Trade], List[Dividend]]:
    ingestor = CoinbaseIngestor()
    for path in file_paths:
        ingestor.process_file(path)
    return ingestor.transactions, ingestor.dividends
