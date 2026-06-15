from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion


class CatalunaRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal("12500"), Decimal("0.095")),
            (Decimal("9500"), Decimal("0.125")),
            (Decimal("11000"), Decimal("0.16")),
            (Decimal("20000"), Decimal("0.19")),
            (Decimal("37000"), Decimal("0.215")),
            (Decimal("30000"), Decimal("0.235")),
            (Decimal("55000"), Decimal("0.245")),
            (Decimal("Infinity"), Decimal("0.255")),
        ]
