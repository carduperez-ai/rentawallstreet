from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class Trade:
    """Compra o venta normalizada de Acciones/ETFs."""

    date: datetime
    platform: str
    asset: str  # Nombre descriptivo
    isin: str  # Identificador internacional (CRÍTICO)
    ticker: str  # Símbolo de cotización
    asset_type: str  # 'stock' o 'etf'
    direction: str  # 'buy' o 'sell'
    quantity: Decimal
    value_eur: Decimal  # Importe efectivo en Euros
    fee_eur: Decimal = Decimal("0.0")  # Comisiones totales
    notes: str = ""
    raw_currency: str = "EUR"
    fx_rate: Decimal = Decimal("1.0")
    asset_id: str = ""  # Alias para compatibilidad
    asset_name: str = ""
    source_module: str = "mainstock"  # Trazabilidad DTO
    source_file: str = ""  # Archivo de origen
    hash_id: str = ""

    def __post_init__(self):
        import hashlib

        # Asegurar compatibilidad con nombres antiguos
        if not self.asset_id:
            object.__setattr__(self, "asset_id", self.isin or self.asset)

        # Generación de Hash único determinista
        raw_payload = f"{self.date.isoformat()}_{self.platform}_{self.asset}_{self.quantity}_{self.value_eur}".replace(
            " ", ""
        ).encode("utf-8")
        object.__setattr__(self, "hash_id", hashlib.sha256(raw_payload).hexdigest())
        if not self.asset_name:
            object.__setattr__(self, "asset_name", self.asset)
        object.__setattr__(self, "_initialized", True)

    def __setattr__(self, name, value):
        if getattr(self, "_initialized", False) and name not in ("fee_eur", "notes"):
            raise AttributeError(f"⚠️ BLOQUEO FISCAL: No se puede modificar '{name}'.")
        object.__setattr__(self, name, value)


@dataclass
class FIFOLot:
    """Lote de acciones adquiridas."""

    date: datetime
    isin: str
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
    """Evento fiscal realizado en acciones (Ficha AEAT)."""

    date: datetime
    platform: str
    asset: str
    isin: str
    ticker: str
    asset_type: str
    quantity_sold: Decimal
    acquisition_date: datetime
    acquisition_cost_eur: Decimal  # Precio compra puro
    sale_proceeds_eur: Decimal  # Precio venta puro
    buy_fee_eur: Decimal  # Gastos compra (suman al coste)
    sell_fee_eur: Decimal  # Gastos venta (restan al ingreso)
    gain_loss_eur: Decimal  # Resultado fiscal (Proceds - SellFee) - (Cost + BuyFee)
    notes: str = ""
    is_wash_sale: bool = False
    source_module: str = "mainstock"  # Trazabilidad DTO
    source_buy_id: int = 0
    blocked_by_buys: list = field(default_factory=list)
    gain_loss_eur_effective: Decimal = Decimal("0.0")

    @property
    def total_sale_eur(self) -> Decimal:
        return self.sale_proceeds_eur - self.sell_fee_eur

    @property
    def total_cost_eur(self) -> Decimal:
        return self.acquisition_cost_eur + self.buy_fee_eur
