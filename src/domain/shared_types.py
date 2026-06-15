from typing import Union, Sequence
from src.domain.stock_fiscal_entities import Dividend as StockDividend
from src.domain.fiscal_entities import Dividend as GeneralDividend
from src.domain.crypto_entities import Trade as CryptoTrade
from src.domain.stock_entities import Trade as StockTrade
from src.domain.crypto_entities import TaxEvent as CryptoTaxEvent
from src.domain.stock_entities import TaxEvent as StockTaxEvent

AnyDividend = Union[StockDividend, GeneralDividend]
AnyTrade = Union[CryptoTrade, StockTrade]
AnyTaxEvent = Union[CryptoTaxEvent, StockTaxEvent]
