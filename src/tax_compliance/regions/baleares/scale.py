from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion

class BalearsRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal('10000'), Decimal('0.09')),
            (Decimal('8000'), Decimal('0.1125')),
            (Decimal('12000'), Decimal('0.1425')),
            (Decimal('18000'), Decimal('0.175')),
            (Decimal('22000'), Decimal('0.19')),
            (Decimal('20000'), Decimal('0.2175')),
            (Decimal('30000'), Decimal('0.2275')),
            (Decimal('55000'), Decimal('0.2375')),
            (Decimal('Infinity'), Decimal('0.2475')),
        ]

    @staticmethod
    def get_personal_minimum() -> Decimal:
        return Decimal('5550')

    @staticmethod
    def get_age_supplements() -> Tuple[Decimal, Decimal]:
        return Decimal('1820'), Decimal('1540')

