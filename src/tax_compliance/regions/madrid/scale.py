from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion


class MadridRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal("13362.22"), Decimal("0.085")),
            (Decimal("5642.41"), Decimal("0.107")),
            (Decimal("16421.05"), Decimal("0.128")),
            (Decimal("21894.72"), Decimal("0.174")),
            (Decimal("Infinity"), Decimal("0.205")),
        ]

    @staticmethod
    def get_personal_minimum() -> Decimal:
        return Decimal("5956.65")

    @staticmethod
    def get_age_supplements() -> Tuple[Decimal, Decimal]:
        return Decimal("1234.26"), Decimal("1502.58")
