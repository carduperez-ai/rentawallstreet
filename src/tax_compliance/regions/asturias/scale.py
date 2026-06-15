from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion


class AsturiasRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal("12450"), Decimal("0.09")),
            (Decimal("5257.20"), Decimal("0.12")),
            (Decimal("15300"), Decimal("0.14")),
            (Decimal("20400"), Decimal("0.192")),
            (Decimal("16592.80"), Decimal("0.215")),
            (Decimal("20000"), Decimal("0.225")),
            (Decimal("85000"), Decimal("0.25")),
            (Decimal("Infinity"), Decimal("0.26")),
        ]

    @staticmethod
    def get_personal_minimum() -> Decimal:
        return Decimal("6105")

    @staticmethod
    def get_age_supplements() -> Tuple[Decimal, Decimal]:
        return Decimal("1265"), Decimal("1540")
