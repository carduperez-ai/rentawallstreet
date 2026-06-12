from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion

class GaliciaRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal('12985.35'), Decimal('0.09')),
            (Decimal('8083.25'), Decimal('0.1165')),
            (Decimal('14131.40'), Decimal('0.149')),
            (Decimal('24800'), Decimal('0.184')),
            (Decimal('Infinity'), Decimal('0.225')),
        ]

    @staticmethod
    def get_personal_minimum() -> Decimal:
        return Decimal('5789')

    @staticmethod
    def get_age_supplements() -> Tuple[Decimal, Decimal]:
        return Decimal('1199'), Decimal('1460')

