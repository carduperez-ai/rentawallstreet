from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion

class ExtremaduraRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal('12450'), Decimal('0.08')),
            (Decimal('7750'), Decimal('0.10')),
            (Decimal('4000'), Decimal('0.16')),
            (Decimal('11000'), Decimal('0.175')),
            (Decimal('24800'), Decimal('0.21')),
            (Decimal('20200'), Decimal('0.235')),
            (Decimal('19000'), Decimal('0.24')),
            (Decimal('21000'), Decimal('0.245')),
            (Decimal('Infinity'), Decimal('0.25')),
        ]

