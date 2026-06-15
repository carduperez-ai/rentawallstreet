from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion


class CanariasRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal("13748"), Decimal("0.09")),
            (Decimal("5674"), Decimal("0.115")),
            (Decimal("16502"), Decimal("0.14")),
            (Decimal("21642"), Decimal("0.185")),
            (Decimal("35702"), Decimal("0.235")),
            (Decimal("30477"), Decimal("0.25")),
            (Decimal("Infinity"), Decimal("0.26")),
        ]

    @staticmethod
    def get_personal_minimum() -> Decimal:
        return Decimal("5606")

    @staticmethod
    def get_age_supplements() -> Tuple[Decimal, Decimal]:
        return Decimal("1162"), Decimal("1414")
