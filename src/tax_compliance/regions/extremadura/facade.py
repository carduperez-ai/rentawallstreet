from decimal import Decimal
from typing import List, Tuple, Dict
from src.domain.fiscal_entities import TaxpayerProfile
from src.tax_compliance.regions.base_profile import RegionalFiscalProfileBase
from .scale import ExtremaduraRegion
from .deductor import ExtremaduraDeductor

class ExtremaduraFiscalProfile(RegionalFiscalProfileBase):
    def get_general_scale(self) -> List[Tuple[Decimal, Decimal]]: return ExtremaduraRegion.get_general_scale() if hasattr(ExtremaduraRegion, 'get_general_scale') else []
    def get_savings_scale(self) -> List[Tuple[Decimal, Decimal]]: return ExtremaduraRegion.get_savings_scale() if hasattr(ExtremaduraRegion, 'get_savings_scale') else []
    def get_personal_minimum(self) -> Decimal: return ExtremaduraRegion.get_personal_minimum() if hasattr(ExtremaduraRegion, 'get_personal_minimum') else Decimal('5550')
    def get_age_supplements(self) -> Tuple[Decimal, Decimal]: return ExtremaduraRegion.get_age_supplements() if hasattr(ExtremaduraRegion, 'get_age_supplements') else (Decimal('1150'), Decimal('1400'))
    def get_descendants_brackets(self) -> List[Decimal]: return ExtremaduraRegion.get_descendants_brackets() if hasattr(ExtremaduraRegion, 'get_descendants_brackets') else [Decimal('2400'), Decimal('2700'), Decimal('4000'), Decimal('4500')]
    def get_descendants_under3(self) -> Decimal: return ExtremaduraRegion.get_descendants_under3() if hasattr(ExtremaduraRegion, 'get_descendants_under3') else Decimal('2800')
    def get_disability_limits(self) -> Tuple[Decimal, Decimal, Decimal]: return ExtremaduraRegion.get_disability_limits() if hasattr(ExtremaduraRegion, 'get_disability_limits') else (Decimal('3000'), Decimal('9000'), Decimal('3000'))
    
    def calculate_deductions(self, profile: TaxpayerProfile, base_general: Decimal, base_ahorro: Decimal) -> Dict[str, Decimal]:
        try:
            return ExtremaduraDeductor(profile, base_general, base_ahorro).calculate_all()
        except TypeError:
            return ExtremaduraDeductor().calculate_all(profile, base_general, base_ahorro) if hasattr(ExtremaduraDeductor, 'calculate_all') else {}
