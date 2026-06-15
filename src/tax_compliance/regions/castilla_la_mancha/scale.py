from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion


class CastillaLaManchaRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal("12450"), Decimal("0.095")),
            (Decimal("7750"), Decimal("0.12")),
            (Decimal("15000"), Decimal("0.15")),
            (Decimal("24800"), Decimal("0.185")),
            (Decimal("Infinity"), Decimal("0.225")),
        ]
