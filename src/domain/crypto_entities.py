"""
Modelos de datos para la declaración de la renta (Inversiones).
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class Trade:
    """Compra o venta normalizada de cualquier plataforma."""

    date: datetime
    platform: str
    asset: str
    asset_type: str  # 'crypto' o 'stock'
    direction: str  # 'buy' o 'sell'
    quantity: Decimal
    value_eur: Decimal
    fee_eur: Decimal = Decimal("0.0")
    notes: str = ""
    raw_currency: str = "EUR"
    fx_rate: Decimal = Decimal("1.0")
    asset_id: str = ""
    asset_name: str = ""
    source_module: str = "maincrypto"  # Trazabilidad DTO
    hash_id: str = ""

    def __post_init__(self):
        from src.ingestion.utils import to_dec
        import hashlib

        # Limpieza de basura Pandas/Float antes de la activación del bloqueo
        object.__setattr__(self, "quantity", to_dec(self.quantity))
        object.__setattr__(self, "value_eur", to_dec(self.value_eur))
        object.__setattr__(self, "fee_eur", to_dec(self.fee_eur))
        object.__setattr__(self, "fx_rate", to_dec(self.fx_rate))

        # Generación de Hash único determinista (ignorando metadatos)
        raw_payload = f"{self.date.isoformat()}_{self.platform}_{self.asset}_{self.quantity}_{self.value_eur}".replace(
            " ", ""
        ).encode("utf-8")
        object.__setattr__(self, "hash_id", hashlib.sha256(raw_payload).hexdigest())

        # Marcamos el objeto como inicializado para activar el bloqueo de edición
        object.__setattr__(self, "_initialized", True)

    def __setattr__(self, name, value):
        # Si el objeto ya está inicializado y se intenta cambiar algo que NO sea la comisión, lanzamos error
        if getattr(self, "_initialized", False) and name != "fee_eur":
            raise AttributeError(
                f"⚠️ BLOQUEO FISCAL: No se puede modificar el campo '{name}'. Solo se permite inyectar comisiones (fee_eur)."
            )
        object.__setattr__(self, name, value)


@dataclass
class FIFOLot:
    """Lote de activos adquiridos a un coste determinado."""

    date: datetime
    asset: str
    quantity: Decimal
    cost_per_unit_eur: Decimal
    platform: str
    buy_fee_per_unit_eur: Decimal = Decimal("0.0")
    source_buy_id: int = 0

    @property
    def total_cost_eur(self) -> Decimal:
        return self.quantity * (self.cost_per_unit_eur + self.buy_fee_per_unit_eur)


@dataclass(frozen=True)
class TaxEvent:
    """Ganancia o pérdida patrimonial realizada."""

    date: datetime
    platform: str
    asset: str
    asset_type: str
    quantity_sold: Decimal
    acquisition_date: datetime
    acquisition_cost_eur: Decimal
    sale_proceeds_eur: Decimal
    gain_loss_eur: Decimal
    buy_fee_eur: Decimal = Decimal("0.0")
    sell_fee_eur: Decimal = Decimal("0.0")
    fee_eur: Decimal = Decimal("0.0")
    notes: str = ""
    asset_id: str = ""
    asset_name: str = ""
    source_module: str = "maincrypto"  # Trazabilidad DTO
    exchange_rate_bce: Decimal = Decimal("1.0")
    is_wash_sale: bool = False
    total_sale_eur: Decimal = Decimal("0.0")
    total_cost_eur: Decimal = Decimal("0.0")
    gain_loss_eur_effective: Decimal = Decimal("0.0")
    source_buy_id: int = 0
    blocked_by_buys: list = field(default_factory=list)


@dataclass
class Dividend:
    """Renta del capital mobiliario (Dividendos)."""

    date: datetime
    platform: str
    asset: str
    isin: str
    gross_eur: Decimal
    withholding_foreign_eur: Decimal = Decimal("0.0")
    withholding_spain_eur: Decimal = Decimal("0.0")
    type: str = "dividend"
    custody_fee_eur: Decimal = Decimal("0.0")
    notes: str = ""
