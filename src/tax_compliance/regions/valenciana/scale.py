from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion


class ValencianaRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        """
        Escala autonómica Comunitat Valenciana 2025.
        Base: Ley 13/1997, de 23 de diciembre (consolidada).
        Formato: (amplitud_tramo_eur, tipo_marginal).
        """
        return [
            (Decimal("12000"), Decimal("0.09")),  # 0 — 12.000€
            (Decimal("10000"), Decimal("0.12")),  # 12.001 — 22.000€
            (Decimal("10000"), Decimal("0.15")),  # 22.001 — 32.000€
            (Decimal("10000"), Decimal("0.175")),  # 32.001 — 42.000€
            (Decimal("10000"), Decimal("0.20")),  # 42.001 — 52.000€
            (Decimal("10000"), Decimal("0.225")),  # 52.001 — 62.000€
            (Decimal("10000"), Decimal("0.25")),  # 62.001 — 72.000€
            (Decimal("28000"), Decimal("0.265")),  # 72.001 — 100.000€
            (Decimal("50000"), Decimal("0.275")),  # 100.001 — 150.000€
            (Decimal("50000"), Decimal("0.285")),  # 150.001 — 200.000€
            (Decimal("Infinity"), Decimal("0.295")),  # > 200.000€
        ]

    @staticmethod
    def get_personal_minimum() -> Decimal:
        return Decimal("6105")

    @staticmethod
    def get_age_supplements() -> Tuple[Decimal, Decimal]:
        return Decimal("1265"), Decimal("1540")
