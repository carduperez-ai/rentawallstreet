from decimal import Decimal
from typing import Dict
from src.domain.fiscal_entities import TaxpayerProfile


class MurciaDeductor:
    def __init__(self, profile: TaxpayerProfile, base_general: Decimal, base_ahorro: Decimal):
        self.profile = profile
        self.base_general = base_general
        self.base_ahorro = base_ahorro

    def calculate_all(self) -> Dict[str, Decimal]:
        deds = {}
        daycare = getattr(self.profile, "daycare_expenses_eur", Decimal("0"))
        children = getattr(self.profile, "children_under_3", 0)
        
        if daycare > 0 and children > 0:
            from src.tax_compliance.state.state_rules import StateDeductor
            diff_deds = StateDeductor.calculate_differential_deductions(self.profile)
            art81_guar = next((d.value for d in diff_deds if d.box_id == "ART81_GUAR"), Decimal("0"))
            
            base_minorada = max(daycare - art81_guar, Decimal("0"))
            mur_02 = min(base_minorada * Decimal("0.20"), Decimal("1000") * children)
            if mur_02 > 0:
                deds["MUR02"] = mur_02
                
        return deds
