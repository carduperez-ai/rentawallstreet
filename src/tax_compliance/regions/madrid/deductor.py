from decimal import Decimal
from typing import Dict
from src.domain.fiscal_entities import TaxpayerProfile


class MadridDeductor:
    def calculate_all(
        self, profile: TaxpayerProfile, base_general: Decimal, base_ahorro: Decimal
    ) -> Dict[str, Decimal]:
        deds = {}
        
        # MAD01: Alquiler vivienda habitual (Jóvenes < 35)
        age = getattr(profile, "age", 0)
        is_rent_habitual = getattr(profile, "is_rent_habitual", False)
        rent_paid = getattr(profile, "rent_paid_annual_eur", Decimal("0"))
        
        if is_rent_habitual and age < 35 and rent_paid > 0:
            base_autonomica = rent_paid
            if getattr(profile, "rent_pre2015", False):
                rent_pre2015_paid = getattr(profile, "rent_pre2015_paid_eur", Decimal("0"))
                bi_total = base_general + base_ahorro
                if bi_total < Decimal("24107.20"):
                    base_estatal = min(rent_pre2015_paid, Decimal("9040"))
                    base_autonomica = max(rent_paid - base_estatal, Decimal("0"))
            
            mad_01 = base_autonomica * Decimal("0.20")
            if mad_01 > 0:
                deds["MAD01"] = mad_01
                
        return deds
