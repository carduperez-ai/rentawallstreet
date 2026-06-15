from decimal import Decimal
from typing import Dict
from src.domain.fiscal_entities import TaxpayerProfile


class La_riojaDeductor:
    def __init__(self, profile: TaxpayerProfile, base_general: Decimal, base_ahorro: Decimal):
        self.profile = profile
        self.base_general = base_general
        self.base_ahorro = base_ahorro

    def calculate_all(self) -> Dict[str, Decimal]:
        deds = {}

        internet = getattr(self.profile, "internet_access_expenses_eur", Decimal("0"))
        age = getattr(self.profile, "age", 99)

        if internet > 0 and age < 36:
            is_joint = getattr(self.profile, "joint_declaration", False)
            limit_bi = Decimal("36000") if is_joint else Decimal("18000")

            bi = self.base_general + self.base_ahorro
            if bi <= limit_bi:
                rio_int = min(internet * Decimal("0.30"), Decimal("150"))
                if rio_int > 0:
                    deds["RIO_INT"] = rio_int

        return deds
