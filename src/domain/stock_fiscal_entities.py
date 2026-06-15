from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class Dividend:
    """Dividendo o ingreso de cupón normalizado de Acciones/ETFs."""

    date: datetime
    platform: str
    asset: str  # Nombre descriptivo del activo
    isin: str  # ISIN del activo (puede ser vacío)
    gross_eur: Decimal  # Importe bruto en euros antes de retenciones
    withholding_foreign_eur: Decimal  # Retención en el país de origen
    withholding_spain_eur: Decimal  # Retención en España (IRPF)
    type: str = "dividend"  # 'dividend', 'interest' o 'fee'
    custody_fee_eur: Decimal = Decimal("0")  # Gastos de custodia/administración deducibles [0035]
    country: str = ""  # País de origen del dividendo (ISO 3166-1 alpha-2)
