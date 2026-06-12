import pytest
from datetime import datetime, date
from decimal import Decimal
import os
from src.ingestion.file_classifier import FileClassifier
from src.adapters.kraken_adapter import KrakenAdapter
from src.adapters.kucoin_adapter import KuCoinAdapter
from src.adapters.coinbase_adapter import CoinbaseAdapter
from src.adapters.etoro_adapter import EToroAdapter
from src.adapters.ibkr_adapter import IBKRAdapter

ADAPTER_FIXTURES = [
    (KrakenAdapter, "mock_kraken.csv", "kraken"),
    (KuCoinAdapter, "mock_kucoin.csv", "kucoin"),
    (CoinbaseAdapter, "mock_coinbase.csv", "coinbase"),
    (EToroAdapter, "mock_etoro.xlsx", "etoro"),
    (IBKRAdapter, "mock_ibkr.csv", "ibkr")
]

@pytest.mark.parametrize("adapter_class, filename, user_pref", ADAPTER_FIXTURES)
def test_adapter_integration(adapter_class, filename, user_pref):
    path = os.path.join(os.path.dirname(__file__), "fixtures", "adapters", filename)
    adapter = adapter_class()
    
    # 1. Verifica que can_handle == True
    metadata = FileClassifier.classify(path, user_pref)
    assert adapter.can_handle(metadata) is True
    
    # 2. Ejecuta extract
    trades, dividends = adapter.extract(path)
    
    # 3. Asegura len(trades) > 0
    assert len(trades) > 0, f"{adapter_class.__name__} no extrajo trades."
    
    # 4. Valida tipado en la primera operación extraída
    first_trade = trades[0]
    assert isinstance(first_trade.date, (datetime, date)), "date no es un objeto datetime"
    assert isinstance(first_trade.quantity, Decimal), "quantity no es Decimal"
    assert hasattr(first_trade, 'value_eur') and isinstance(first_trade.value_eur, Decimal), "value_eur no es Decimal"
