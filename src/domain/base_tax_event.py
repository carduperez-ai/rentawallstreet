from typing import Protocol, runtime_checkable
from datetime import datetime
from decimal import Decimal


@runtime_checkable
class BaseTaxEvent(Protocol):
    """Contrato mínimo que satisfacen tanto crypto_entities.TaxEvent como stock_entities.TaxEvent.

    Permite que IRPFCalculator y reporting procesen listas heterogéneas sin
    acoplar el tipo concreto de cada motor.
    """

    date: datetime
    asset: str
    gain_loss_eur: Decimal
