from decimal import Decimal
from typing import Dict
from src.domain.fiscal_entities import TaxpayerProfile


class ValencianaDeductor:
    def __init__(self, profile: TaxpayerProfile, base_general: Decimal, base_ahorro: Decimal):
        self.profile = profile
        self.base_general = base_general
        self.base_ahorro = base_ahorro

    def calculate_all(self) -> Dict[str, Decimal]:
        deds = {}

        dental = getattr(self.profile, "health_dental_expenses_eur", Decimal("0"))
        optical = getattr(self.profile, "health_optical_expenses_eur", Decimal("0"))

        if dental > 0 or optical > 0:
            is_joint = getattr(self.profile, "joint_declaration", False)
            limit_bi = Decimal("32000") if is_joint else Decimal("30000")

            bi = self.base_general + self.base_ahorro
            if bi <= limit_bi:
                val_med = (dental + optical) * Decimal("0.30")
                if val_med > 0:
                    deds["VAL_MED"] = val_med

        return deds
