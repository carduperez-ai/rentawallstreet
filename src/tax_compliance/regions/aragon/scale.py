from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion
from src.domain.fiscal_entities import Deduction, TaxpayerProfile

class AragonRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return []

    @classmethod
    def get_quota_deductions(
        cls,
        profile: TaxpayerProfile,
        base_imponible_general: Decimal,
        base_imponible_ahorro: Decimal,
        cuota_integra_autonomica: Decimal,
    ) -> List[Deduction]:
        from .deductor import AragonDeductor
        ded_dict = AragonDeductor.calculate_all(profile, base_imponible_general, base_imponible_ahorro)
        return [Deduction(box_id=k, value=v, description=k) for k, v in ded_dict.items()]
