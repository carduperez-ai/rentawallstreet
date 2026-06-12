from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion

class CantabriaRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal('13000'), Decimal('0.085')),
            (Decimal('8000'), Decimal('0.11')),
            (Decimal('14200'), Decimal('0.145')),
            (Decimal('24800'), Decimal('0.18')),
            (Decimal('30000'), Decimal('0.225')),
            (Decimal('Infinity'), Decimal('0.245')),
        ]

