from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion

class LaRiojaRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal('12450'), Decimal('0.08')),
            (Decimal('7750'), Decimal('0.106')),
            (Decimal('15000'), Decimal('0.136')),
            (Decimal('4800'), Decimal('0.178')),
            (Decimal('10000'), Decimal('0.183')),
            (Decimal('0.19'), Decimal('60000')),
            (Decimal('0.245'), Decimal('Infinity')),
        ]

