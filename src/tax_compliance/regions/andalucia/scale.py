from decimal import Decimal
from typing import List, Tuple
from src.tax_compliance.regions.base import BaseRegion
from src.domain.fiscal_entities import Deduction, TaxpayerProfile

class AndalusiaRegion(BaseRegion):
    @staticmethod
    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:
        return [
            (Decimal('13000'), Decimal('0.095')),
            (Decimal('7200'), Decimal('0.12')),
            (Decimal('7500'), Decimal('0.15')),
            (Decimal('7500'), Decimal('0.165')),
            (Decimal('14800'), Decimal('0.19')),
            (Decimal('10000'), Decimal('0.21')),
            (Decimal('240000'), Decimal('0.215')),
            (Decimal('Infinity'), Decimal('0.225')),
        ]

    @classmethod
    def get_quota_deductions(
        cls,
        profile: TaxpayerProfile,
        base_imponible_general: Decimal,
        base_imponible_ahorro: Decimal,
        cuota_integra_autonomica: Decimal,
    ) -> List[Deduction]:
        from .deductor import AndalusiaDeductor
        ded_dict = AndalusiaDeductor.calculate_all(profile, base_imponible_general, base_imponible_ahorro)
        return [Deduction(box_id=k, value=v, description=k) for k, v in ded_dict.items()]
