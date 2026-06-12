from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion

class MurciaRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal('12450'), Decimal('0.095')),
            (Decimal('7750'), Decimal('0.112')),
            (Decimal('13800'), Decimal('0.133')),
            (Decimal('26000'), Decimal('0.179')),
            (Decimal('Infinity'), Decimal('0.225')),
        ]

