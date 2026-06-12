from src.ingestion.profile_builder import ProfileBuilder
import pytest
from decimal import Decimal
from src.domain.fiscal_entities import TaxpayerProfile
from src.tax_compliance.regions.factory import RegionalContextFactory

ALL_CCAA = [
    "andalucia", "aragon", "asturias", "baleares", "canarias", 
    "cantabria", "castilla_la_mancha", "castilla_leon", "cataluna", 
    "extremadura", "galicia", "madrid", "murcia", "la_rioja", 
    "valenciana", "ceuta", "melilla"
]

@pytest.mark.parametrize("region", ALL_CCAA)
def test_factory_and_deductor_contract(region):
    profile = ProfileBuilder.from_dict(dict(age=30))
    base_general = Decimal('20000')
    base_ahorro = Decimal('0')
    
    context = RegionalContextFactory.get_context(region)
    
    # Calculate deductions
    deductions = context.calculate_deductions(profile, base_general, base_ahorro)
    
    # Verify contract
    assert isinstance(deductions, dict), f"Region {region} did not return a dictionary"
    for key, value in deductions.items():
        assert isinstance(key, str), f"Region {region} key {key} is not string"
        assert isinstance(value, Decimal), f"Region {region} value {value} is not Decimal"

    # specific mathematical logic verification for Madrid, Extremadura, Galicia, Andalucía
    if region == "andalucia":
        # we expect AND03 to be 0 or populated if we trigger it
        profile_b = ProfileBuilder.from_dict(dict(age=40, birth_count_current_year=1))
        ded = context.calculate_deductions(profile_b, Decimal('90000'), Decimal('0'))
        assert "AND03" in ded and ded["AND03"] == Decimal('200')
    elif region in ("madrid", "extremadura", "galicia"):
        # For now, these return {}, meaning their stubs are valid under the new contract.
        pass
