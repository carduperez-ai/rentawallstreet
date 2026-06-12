from decimal import Decimal
from typing import List, Tuple, Dict
from src.domain.fiscal_entities import TaxpayerProfile
from src.tax_compliance.regions.base_profile import RegionalFiscalProfileBase
from .scale import CeutaMelillaRegion
from .deductor import CeutaDeductor

class CeutaFiscalProfile(RegionalFiscalProfileBase):
    def get_general_scale(self) -> List[Tuple[Decimal, Decimal]]: return CeutaMelillaRegion.get_general_scale() if hasattr(CeutaMelillaRegion, 'get_general_scale') else []
    def get_savings_scale(self) -> List[Tuple[Decimal, Decimal]]: return CeutaMelillaRegion.get_savings_scale() if hasattr(CeutaMelillaRegion, 'get_savings_scale') else []
    def get_personal_minimum(self) -> Decimal: return CeutaMelillaRegion.get_personal_minimum() if hasattr(CeutaMelillaRegion, 'get_personal_minimum') else Decimal('5550')
    def get_age_supplements(self) -> Tuple[Decimal, Decimal]: return CeutaMelillaRegion.get_age_supplements() if hasattr(CeutaMelillaRegion, 'get_age_supplements') else (Decimal('1150'), Decimal('1400'))
    def get_descendants_brackets(self) -> List[Decimal]: return CeutaMelillaRegion.get_descendants_brackets() if hasattr(CeutaMelillaRegion, 'get_descendants_brackets') else [Decimal('2400'), Decimal('2700'), Decimal('4000'), Decimal('4500')]
    def get_descendants_under3(self) -> Decimal: return CeutaMelillaRegion.get_descendants_under3() if hasattr(CeutaMelillaRegion, 'get_descendants_under3') else Decimal('2800')
    def get_disability_limits(self) -> Tuple[Decimal, Decimal, Decimal]: return CeutaMelillaRegion.get_disability_limits() if hasattr(CeutaMelillaRegion, 'get_disability_limits') else (Decimal('3000'), Decimal('9000'), Decimal('3000'))
    
    def calculate_deductions(self, profile: TaxpayerProfile, base_general: Decimal, base_ahorro: Decimal) -> Dict[str, Decimal]:
        try:
            return CeutaDeductor(profile, base_general, base_ahorro).calculate_all()
        except TypeError:
            return CeutaDeductor().calculate_all(profile, base_general, base_ahorro) if hasattr(CeutaDeductor, 'calculate_all') else {}
