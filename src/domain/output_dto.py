from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Any


@dataclass(frozen=True)
class TaxResultDTO:
    """
    Data Transfer Object que encapsula los resultados finales de la autoliquidación,
    conforme a las magnitudes exigidas por la AEAT.
    """

    general_taxable_base: Decimal
    savings_taxable_base: Decimal
    general_liquidable_base: Decimal
    savings_liquidable_base: Decimal
    gross_tax_quota: Decimal  # Cuota íntegra (estatal + autonómica)
    net_tax_quota: Decimal  # Cuota líquida (tras deducciones)
    final_result: Decimal  # Resultado de la declaración (a ingresar o a devolver)

    # Compatibilidad con el renderizado de la UI actual
    raw_summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_refund(self) -> bool:
        return self.final_result < 0
