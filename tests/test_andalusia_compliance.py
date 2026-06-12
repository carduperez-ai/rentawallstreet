from src.ingestion.profile_builder import ProfileBuilder
import pytest
from decimal import Decimal
from src.domain.fiscal_entities import TaxpayerProfile, Deduction
from src.tax_compliance.regions.andalucia.scale import AndalusiaRegion
from src.tax_compliance.regions.andalucia.deductor import AndalusiaDeductor

def test_and01_alquiler_habitual():
    profile = ProfileBuilder.from_dict(dict(
        age=30,
        disability_grade=0,
        is_rent_habitual=True,
        rent_paid_annual_eur=Decimal('10000')
    ))
    
    ded_region = AndalusiaRegion.get_quota_deductions(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    ded_deductor = AndalusiaDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region}.get("AND01") == Decimal('1200')
    assert ded_deductor.get("AND01") == Decimal('1200')

    profile_dis = ProfileBuilder.from_dict(dict(
        age=30,
        disability_grade=33,
        is_rent_habitual=True,
        rent_paid_annual_eur=Decimal('10000')
    ))
    
    ded_region_dis = AndalusiaRegion.get_quota_deductions(profile_dis, Decimal('20000'), Decimal('0'), Decimal('1000'))
    ded_deductor_dis = AndalusiaDeductor.calculate_all(profile_dis, Decimal('20000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region_dis}.get("AND01") == Decimal('1500')
    assert ded_deductor_dis.get("AND01") == Decimal('1500')

def test_and03_nacimiento_universal_multiple():
    profile_simple = ProfileBuilder.from_dict(dict(
        age=40,
        birth_count_current_year=1
    ))
    
    ded_region = AndalusiaRegion.get_quota_deductions(profile_simple, Decimal('90000'), Decimal('0'), Decimal('1000'))
    ded_deductor = AndalusiaDeductor.calculate_all(profile_simple, Decimal('90000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region}.get("AND03") == Decimal('200')
    assert ded_deductor.get("AND03") == Decimal('200')

    profile_multiple = ProfileBuilder.from_dict(dict(
        age=40,
        birth_count_current_year=2
    ))
    
    ded_region_mult = AndalusiaRegion.get_quota_deductions(profile_multiple, Decimal('90000'), Decimal('0'), Decimal('1000'))
    ded_deductor_mult = AndalusiaDeductor.calculate_all(profile_multiple, Decimal('90000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region_mult}.get("AND03") == Decimal('800')
    assert ded_deductor_mult.get("AND03") == Decimal('800')

def test_and05_celiaco_universal():
    profile = ProfileBuilder.from_dict(dict(
        age=35,
        is_celiac=True
    ))
    
    ded_region = AndalusiaRegion.get_quota_deductions(profile, Decimal('75000'), Decimal('0'), Decimal('1000'))
    ded_deductor = AndalusiaDeductor.calculate_all(profile, Decimal('75000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region}.get("AND05") == Decimal('100')
    assert ded_deductor.get("AND05") == Decimal('100')

def test_and06_gastos_veterinarios():
    profile = ProfileBuilder.from_dict(dict(
        age=30,
        vet_expenses_eur=Decimal('300')
    ))
    
    ded_region = AndalusiaRegion.get_quota_deductions(profile, Decimal('40000'), Decimal('0'), Decimal('1000'))
    ded_deductor = AndalusiaDeductor.calculate_all(profile, Decimal('40000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region}.get("AND06") == Decimal('90')
    assert ded_deductor.get("AND06") == Decimal('90')

    profile_capped = ProfileBuilder.from_dict(dict(
        age=30,
        vet_expenses_eur=Decimal('500')
    ))
    
    ded_region_cap = AndalusiaRegion.get_quota_deductions(profile_capped, Decimal('40000'), Decimal('0'), Decimal('1000'))
    ded_deductor_cap = AndalusiaDeductor.calculate_all(profile_capped, Decimal('40000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region_cap}.get("AND06") == Decimal('100')
    assert ded_deductor_cap.get("AND06") == Decimal('100')

    ded_region_excl = AndalusiaRegion.get_quota_deductions(profile, Decimal('85000'), Decimal('0'), Decimal('1000'))
    ded_deductor_excl = AndalusiaDeductor.calculate_all(profile, Decimal('85000'), Decimal('0'))
    
    assert "AND06" not in [d.box_id for d in ded_region_excl]
    assert "AND06" not in ded_deductor_excl

def test_and07_ejercicio_fisico():
    profile = ProfileBuilder.from_dict(dict(
        age=30,
        gym_expenses_eur=Decimal('1000')
    ))
    
    ded_region = AndalusiaRegion.get_quota_deductions(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    ded_deductor = AndalusiaDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region}.get("AND07") == Decimal('100')
    assert ded_deductor.get("AND07") == Decimal('100')

def test_and09_monoparental_con_ascendientes():
    profile = ProfileBuilder.from_dict(dict(
        age=40,
        is_monoparental=True,
        descendants_count=1,
        ascendants_over75=0
    ))
    
    ded_region = AndalusiaRegion.get_quota_deductions(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    ded_deductor = AndalusiaDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region}.get("AND09") == Decimal('100')
    assert ded_deductor.get("AND09") == Decimal('100')

    profile_asc = ProfileBuilder.from_dict(dict(
        age=40,
        is_monoparental=True,
        descendants_count=1,
        ascendants_over75=2
    ))
    
    ded_region_asc = AndalusiaRegion.get_quota_deductions(profile_asc, Decimal('20000'), Decimal('0'), Decimal('1000'))
    ded_deductor_asc = AndalusiaDeductor.calculate_all(profile_asc, Decimal('20000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region_asc}.get("AND09") == Decimal('300')
    assert ded_deductor_asc.get("AND09") == Decimal('300')

def test_and11_familia_numerosa_general_y_especial():
    profile_gen = ProfileBuilder.from_dict(dict(
        age=40,
        is_large_family=True,
        descendants_count=3,
        is_large_family_special=False
    ))
    
    ded_region = AndalusiaRegion.get_quota_deductions(profile_gen, Decimal('20000'), Decimal('0'), Decimal('1000'))
    ded_deductor = AndalusiaDeductor.calculate_all(profile_gen, Decimal('20000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region}.get("AND11") == Decimal('200')
    assert ded_deductor.get("AND11") == Decimal('200')

    profile_spec = ProfileBuilder.from_dict(dict(
        age=40,
        is_large_family=True,
        descendants_count=3,
        is_large_family_special=True
    ))
    
    ded_region_spec = AndalusiaRegion.get_quota_deductions(profile_spec, Decimal('20000'), Decimal('0'), Decimal('1000'))
    ded_deductor_spec = AndalusiaDeductor.calculate_all(profile_spec, Decimal('20000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region_spec}.get("AND11") == Decimal('400')
    assert ded_deductor_spec.get("AND11") == Decimal('400')

    ded_region_excl = AndalusiaRegion.get_quota_deductions(profile_gen, Decimal('35000'), Decimal('0'), Decimal('1000'))
    ded_deductor_excl = AndalusiaDeductor.calculate_all(profile_gen, Decimal('35000'), Decimal('0'))
    
    assert "AND11" not in [d.box_id for d in ded_region_excl]
    assert "AND11" not in ded_deductor_excl

def test_incompatibilidad_and03_vs_and11():
    profile_spec_birth = ProfileBuilder.from_dict(dict(
        age=40,
        birth_count_current_year=1,
        is_large_family=True,
        descendants_count=3,
        is_large_family_special=True
    ))
    
    ded_region = AndalusiaRegion.get_quota_deductions(profile_spec_birth, Decimal('20000'), Decimal('0'), Decimal('1000'))
    ded_deductor = AndalusiaDeductor.calculate_all(profile_spec_birth, Decimal('20000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region}.get("AND11") == Decimal('400')
    assert "AND03" not in [d.box_id for d in ded_region]
    assert ded_deductor.get("AND11") == Decimal('400')
    assert "AND03" not in ded_deductor

    profile_mult_birth = ProfileBuilder.from_dict(dict(
        age=40,
        birth_count_current_year=2,
        is_large_family=True,
        descendants_count=3,
        is_large_family_special=False
    ))
    
    ded_region_mult = AndalusiaRegion.get_quota_deductions(profile_mult_birth, Decimal('20000'), Decimal('0'), Decimal('1000'))
    ded_deductor_mult = AndalusiaDeductor.calculate_all(profile_mult_birth, Decimal('20000'), Decimal('0'))
    
    assert {d.box_id: d.value for d in ded_region_mult}.get("AND03") == Decimal('800')
    assert "AND11" not in {d.box_id: d.value for d in ded_region_mult}
    assert ded_deductor_mult.get("AND03") == Decimal('800')
    assert "AND11" not in ded_deductor_mult
