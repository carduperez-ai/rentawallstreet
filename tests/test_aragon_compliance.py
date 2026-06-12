from src.ingestion.profile_builder import ProfileBuilder
# tests/test_aragon_compliance.py
import pytest
from decimal import Decimal
from src.domain.fiscal_entities import TaxpayerProfile, Deduction
from src.tax_compliance.regions.aragon.scale import AragonRegion
from src.tax_compliance.regions.aragon.deductor import AragonDeductor

def test_ara01_nacimiento_tercer_hijo():
    # Caso 1: Individual, 3er hijo, renta baja (BI general=15k, min personal=5.5k, min desc=2.4k+2.7k+4k = 9.1k)
    # BI Neta = 15k - (5.5k + 9.1k) = 400€ <= 21.000€ -> 600€
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        descendants_count=3,
        birth_count_current_year=1,
        joint_declaration=False
    ))
    _raw = AragonDeductor.calculate_all(profile, Decimal('15000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA01") == Decimal('600')

    # Caso 2: Rural despoblación, renta baja -> 720€
    profile_rural = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        descendants_count=3,
        birth_count_current_year=1,
        joint_declaration=False,
        ara_resides_in_rural_despoblacion=True
    ))
    res_rural = AragonDeductor.calculate_all(profile_rural, Decimal('15000'), Decimal('0'), Decimal('1000'))
    assert res_rural.get("ARA01") == Decimal('720')

    # Caso 3: Renta alta (BI=60k, BI Neta > 21k) -> 500€
    res_high = AragonDeductor.calculate_all(profile, Decimal('60000'), Decimal('0'), Decimal('1000'))
    assert res_high.get("ARA01") == Decimal('500')

def test_ara02_nacimiento_discapacidad():
    # Caso 1: Hijo con discapacidad >=33%, general -> 200€
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        birth_count_current_year=1,
        children_disabled_33_65=1
    ))
    _raw = AragonDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA02") == Decimal('200')

    # Caso 2: Rural -> 240€
    profile_rural = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        birth_count_current_year=1,
        children_disabled_33_65=1,
        ara_resides_in_rural_despoblacion=True
    ))
    res_rural = AragonDeductor.calculate_all(profile_rural, Decimal('20000'), Decimal('0'), Decimal('1000'))
    assert res_rural.get("ARA02") == Decimal('240')

def test_ara03_adopcion_internacional():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        ara_international_adoption_count=1
    ))
    _raw = AragonDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA03") == Decimal('600')

    profile_rural = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        ara_international_adoption_count=1,
        ara_resides_in_rural_despoblacion=True
    ))
    res_rural = AragonDeductor.calculate_all(profile_rural, Decimal('20000'), Decimal('0'), Decimal('1000'))
    assert res_rural.get("ARA03") == Decimal('720')

def test_ara04_cuidado_dependientes():
    # 1 dependiente >75, renta baja -> 150€
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        ara_dependents_over75_count=1
    ))
    _raw = AragonDeductor.calculate_all(profile, Decimal('15000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA04") == Decimal('150')

    # Rural -> 300€
    profile_rural = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        ara_dependents_over75_count=1,
        ara_resides_in_rural_despoblacion=True
    ))
    res_rural = AragonDeductor.calculate_all(profile_rural, Decimal('15000'), Decimal('0'), Decimal('1000'))
    assert res_rural.get("ARA04") == Decimal('300')

    # Renta superior a límite (BI net > 21k) -> Excluido
    res_high = AragonDeductor.calculate_all(profile, Decimal('45000'), Decimal('0'), Decimal('1000'))
    assert not any(d.box_id == "ARA04" for d in res_high)

def test_ara05_donaciones_ecologicas():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        ara_donations_ecological_research_eur=Decimal('500')
    ))
    # 500 * 20% = 100€, cuota autonómica = 1500€ -> Límite 10% = 150€ -> Deducción = 100€
    _raw = AragonDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA05") == Decimal('100')

    # Cuota baja (500€) -> Límite 10% = 50€ -> Deducción = 50€
    res_low = AragonDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'), Decimal('500'))
    assert res_low.get("ARA05") == Decimal('50')

def test_ara06_victimas_terrorismo():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        is_victim_violence_gender_or_terrorism=True,
        is_protected_housing=True,
        rent_paid_annual_eur=Decimal('5000') # Usando rent_paid o similar para simular inversión
    ))
    # 3% de inversión habitual. Simulamos inversión habitual de 5000€ -> 150€
    # En el motor modelaremos que la deducción aplica sobre 'rent_paid_annual_eur' (o un campo específico si existe,
    # pero usemos rent_paid_annual_eur para no sobrecargar el perfil).
    _raw = AragonDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA06") == Decimal('150')

def test_ara07_inversion_mab():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        ara_mab_investment_eur=Decimal('10000')
    ))
    # 20% de 10.000€ = 2.000€
    _raw = AragonDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA07") == Decimal('2000')

def test_ara08_inversion_entidades_nuevas():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        ara_new_entities_investment_eur=Decimal('110000')
    ))
    # Exceso sobre 100.000€ es 10.000€ -> 20% = 2.000€
    _raw = AragonDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA08") == Decimal('2000')

def test_ara09_vivienda_rural():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=30,
        ara_is_first_vivienda_rural=True,
        ara_vivienda_rural_population_under3k=True,
        rent_paid_annual_eur=Decimal('8000') # Usado para inversión habitual
    ))
    # General: 5% de 8.000€ = 400€
    _raw = AragonDeductor.calculate_all(profile, Decimal('15000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA09") == Decimal('400')

    # Rural despoblación: 7.5% de 8.000€ = 600€
    profile_rural = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=30,
        ara_is_first_vivienda_rural=True,
        ara_vivienda_rural_population_under3k=True,
        ara_resides_in_rural_despoblacion=True,
        rent_paid_annual_eur=Decimal('8000')
    ))
    res_rural = AragonDeductor.calculate_all(profile_rural, Decimal('15000'), Decimal('0'), Decimal('1000'))
    assert res_rural.get("ARA09") == Decimal('600')

def test_ara10_libros_texto():
    # Caso 1: Individual, no numerosa, BI general=6.000€ -> Límite 50€, gasto 80€ -> 50€
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=40,
        descendants_count=1,
        ara_school_material_expenses_eur=Decimal('80')
    ))
    _raw = AragonDeductor.calculate_all(profile, Decimal('6000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA10") == Decimal('50')

    # Caso 2: Con beca de 20€ -> Gasto neto = 60€ -> Deducción sigue topada a 50€
    profile_grant = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=40,
        descendants_count=1,
        ara_school_material_expenses_eur=Decimal('80'),
        ara_school_material_grants_eur=Decimal('20')
    ))
    res_grant = AragonDeductor.calculate_all(profile_grant, Decimal('6000'), Decimal('0'), Decimal('1000'))
    assert res_grant.get("ARA10") == Decimal('50')

def test_ara11_arrendamiento_dacion_pago():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        ara_dacion_en_pago_rent_paid_eur=Decimal('3000')
    ))
    # 10% de 3000€ = 300€
    _raw = AragonDeductor.calculate_all(profile, Decimal('12000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA11") == Decimal('300')

def test_ara12_arrendamiento_social():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=45,
        ara_social_rental_net_income_eur=Decimal('3000')
    ))
    # Renta general = 30.000€, Cuota autonómica = 3.000€
    # Cuota correspondiente al rendimiento = 3.000 * (3.000 / 30.000) = 300€
    # Deducción = 30% de 300€ = 90€
    _raw = AragonDeductor.calculate_all(profile, Decimal('30000'), Decimal('0'), Decimal('3000'))
    res = _raw
    assert res.get("ARA12") == Decimal('90')

def test_ara13_mayores_70():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=72,
        ara_has_non_capital_general_income=True
    ))
    _raw = AragonDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA13") == Decimal('75')

def test_ara14_nacimiento_poblaciones_pequenas():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        birth_count_current_year=1,
        descendants_count=1,
        ara_resides_under10k_population=True,
        ara_resided_previous_year_under10k=True
    ))
    # BI baja <= 23.000€ -> 200€ por 1er hijo
    _raw = AragonDeductor.calculate_all(profile, Decimal('18000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA14") == Decimal('200')


def test_ara15_guarderia():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        children_under_3=1,
        daycare_expenses_eur=Decimal('1000')
    ))
    # 15% de 1.000€ = 150€ (tope general 250€)
    _raw = AragonDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA15") == Decimal('150')

def test_ara16_economia_social():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        ara_economy_social_investment_eur=Decimal('1000')
    ))
    # 20% de 1.000€ = 200€
    _raw = AragonDeductor.calculate_all(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA16") == Decimal('200')

def test_ara17_apoyo_refuerzo():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=40,
        descendants_count=1,
        ara_school_support_classes_expenses_eur=Decimal('200')
    ))
    # 25% de 200€ = 50€
    _raw = AragonDeductor.calculate_all(profile, Decimal('6000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA17") == Decimal('50')

def test_ara18_autonomia_discapacidad():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=40,
        descendants_count=1,
        children_disabled_33_65=1,
        ara_disabled_child_autonomy_expenses_eur=Decimal('200')
    ))
    # 25% de 200€ = 50€
    _raw = AragonDeductor.calculate_all(profile, Decimal('6000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA18") == Decimal('50')

def test_ara19_residencia_riesgo_extremo():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=40,
        ara_resides_in_extreme_despoblacion=True
    ))
    # 600€ si base imponible general + ahorro <= 35k e ahorro <= 4k
    _raw = AragonDeductor.calculate_all(profile, Decimal('25000'), Decimal('0'), Decimal('1000'))
    res = _raw
    assert res.get("ARA19") == Decimal('600')

def test_incompatibilidad_ara02_vs_ara14():
    profile = ProfileBuilder.from_dict(dict(
        region="aragon",
        age=35,
        birth_count_current_year=1,
        descendants_count=1,
        children_disabled_33_65=1,
        ara_resides_under10k_population=True,
        ara_resided_previous_year_under10k=True
    ))
    # ARA02 (Discapacidad) = 200€ vs ARA14 (Pequeño municipio) = 200€
    # En este caso empatan o aplica la de discapacidad preferentemente, o solo una.
    # Verificamos que solo se aplique una de las dos (ej. ARA02) y no ambas.
    _raw = AragonDeductor.calculate_all(profile, Decimal('18000'), Decimal('0'), Decimal('1000'))
    res = _raw
    applied = [k for k in res.keys() if k in ("ARA02", "ARA14")]
    assert len(applied) == 1
