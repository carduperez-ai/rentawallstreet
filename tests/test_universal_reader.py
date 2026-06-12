import os
import tempfile
import csv
from decimal import Decimal
from src.ingestion.universal_reader import UniversalReader

def _make_csv(rows, fieldnames):
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='')
    writer = csv.DictWriter(tmp, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    tmp.close()
    return tmp.name

def test_parse_csv_basic():
    csv_path = _make_csv(
        [{'tipo': 'buy', 'fecha': '2024-01-15', 'activo': 'AAPL', 'cantidad': '10', 'valor': '1500', 'comision': '0'}],
        ['tipo', 'fecha', 'activo', 'cantidad', 'valor', 'comision']
    )
    
    try:
        trades, divs = UniversalReader.parse(csv_path)
        assert len(trades) == 1
        assert trades[0].asset == 'AAPL'
        assert trades[0].direction == 'buy'
        assert trades[0].value_eur == Decimal('1500')
        assert len(divs) == 0
    finally:
        os.remove(csv_path)

def test_parse_csv_dividend():
    csv_path = _make_csv(
        [{'tipo': 'div', 'fecha': '2024-01-15', 'activo': 'AAPL', 'cantidad': '0', 'valor': '150', 'comision': '0'}],
        ['tipo', 'fecha', 'activo', 'cantidad', 'valor', 'comision']
    )
    
    try:
        trades, divs = UniversalReader.parse(csv_path)
        assert len(trades) == 0
        assert len(divs) == 1
        assert divs[0].asset == 'AAPL'
        assert divs[0].gross_eur == Decimal('150')
    finally:
        os.remove(csv_path)
