from decimal import Decimal
from typing import Dict
from src.domain.fiscal_entities import TaxpayerProfile

class MelillaDeductor:
    def calculate_all(self, profile: TaxpayerProfile, base_general: Decimal, base_ahorro: Decimal) -> Dict[str, Decimal]:
        return {}
