import pytest
from decimal import Decimal
from datetime import datetime

from src.domain.crypto_entities import Trade, TaxEvent
from src.accounting.interwallet_controller import InterwalletController
from src.accounting.fifo_calculator_stock import TaxEngine as CryptoTaxEngine

def test_interwallet_wash_sale_relativedelta_bug():
    """
    Test de regresión para el Bug Crítico encontrado con datos reales:
    TypeError: '<=' not supported between instances of 'datetime.timedelta' and 'relativedelta'
    
    Asegura que el InterwalletController evalúa los límites temporales (months_limit)
    usando álgebra de fechas válida.
    """
    # 1. Creamos operaciones de prueba con wash sale (pérdida recomprada en <2 meses)
    t1 = Trade(
        date=datetime(2025, 1, 10, 10, 0),
        platform="Binance",
        asset_type="crypto",
        direction="buy",
        asset="BTC",
        quantity=Decimal('1.0'),
        value_eur=Decimal('10000.0'),
        fee_eur=Decimal('10.0')
    )
    t2 = Trade(
        date=datetime(2025, 1, 15, 10, 0),
        platform="Binance",
        asset_type="crypto",
        direction="sell",
        asset="BTC",
        quantity=Decimal('1.0'),
        value_eur=Decimal('5000.0'),  # Pérdida masiva
        fee_eur=Decimal('10.0')
    )
    # Compra que gatilla la regla anti-lavado (dentro de los 2 meses siguientes o anteriores)
    t3 = Trade(
        date=datetime(2025, 1, 20, 10, 0), # 5 días después de la venta
        platform="Binance",
        asset_type="crypto",
        direction="buy",
        asset="BTC",
        quantity=Decimal('1.0'),
        value_eur=Decimal('5100.0'),
        fee_eur=Decimal('10.0')
    )
    
    raw_crypto_trades = [t1, t2, t3]
    raw_stock_trades = []
    
    controller = InterwalletController(
        raw_crypto_trades=raw_crypto_trades,
        raw_stock_trades=raw_stock_trades
    )
    
    # 2. Ejecutar Pipeline. Si el bug 'timedelta vs relativedelta' sigue existiendo, esto lanzará TypeError
    crypto_events, stock_events = controller.execute_pipeline(target_fiscal_year=2025)
    
    # 3. Validar el resultado: la pérdida es retornada libremente y NO marcada como wash sale (DGT V1604-23)
    assert len(crypto_events) == 1, "Debe reportarse 1 evento (la pérdida)"
    assert crypto_events[0].is_wash_sale == False, "El evento NO debe estar marcado como wash sale en cripto"
