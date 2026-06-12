from src.ingestion.profile_builder import ProfileBuilder
# tests/test_cantabria_compliance.py
import pytest
from decimal import Decimal
from src.domain.fiscal_entities import TaxpayerProfile, Deduction
from src.tax_compliance.regions.cantabria.deductor import CantabriaDeductor

def test_cantabria_alquiler_general_and_despoblacion():
    # Caso 1: Individual. Alquiler despoblación activo -> Aplica CTB_ALQ_DESP, no CTB_ALQ
    profile = ProfileBuilder.from_dict(dict(region='cantabria', 
        age=30,
        rent_paid_annual_eur=Decimal('4000'),
        cantabria_rent_despoblacion_paid_eur=Decimal('3000'),
        joint_declaration=False, custody_shared=True
    ))
    res = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile, Decimal('20000'), Decimal('0'), Decimal('2000'))}
    assert res.get("CTB_ALQ_DESP") == Decimal('600.00')
    assert "CTB_ALQ" not in res

    # Caso 2: Alquiler general solo. Renta = 20.000€. Alquiler = 3.000€ (supera el 10% de 20.000 = 2000€)
    # edad 30 (< 36) -> Aplica CTB_ALQ. 10% = 300€, límite individual = 300€
    profile_general = ProfileBuilder.from_dict(dict(region='cantabria', 
        age=30,
        rent_paid_annual_eur=Decimal('3000'),
        joint_declaration=False, custody_shared=True
    ))
    res_general = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile_general, Decimal('20000'), Decimal('0'), Decimal('2000'))}
    assert res_general.get("CTB_ALQ") == Decimal('300.00')

def test_cantabria_nacimiento_and_cuidado():
    # Nacimiento en 2025. Renta de base límite = 20.000 - 5.550 = 14.450 < 31.485
    # Nacimiento de 1 hijo -> 1400 € / 2 (individual por defecto) = 700 €
    # Cuidado de familiares: incompatible por el mismo hijo (menor de 3 años sin discapacidad) -> 0€ cuid
    profile = ProfileBuilder.from_dict(dict(region='cantabria', 
        age=30,
        minimo_personal_familiar=Decimal('5550'),
        birth_count_current_year=1,
        children_under_3=1,
        joint_declaration=False, custody_shared=True
    ))
    res = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile, Decimal('20000'), Decimal('0'), Decimal('2000'))}
    assert res.get("CTB_NAC") == Decimal('700.00')
    assert "CTB_CUID" not in res

    # Caso con discapacidad para el menor de 3 años -> Se aplica cuidado de familiares por doble condición:
    # menor de 3 años (100€) + discapacidad (100€) = 200€ / 2 = 100€ cuid
    profile_discap = ProfileBuilder.from_dict(dict(region='cantabria', 
        age=30,
        minimo_personal_familiar=Decimal('5550'),
        birth_count_current_year=1,
        children_under_3=1,
        cantabria_descendants_under_3_disabled_65_count=1,
        joint_declaration=False, custody_shared=True
    ))
    res_discap = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile_discap, Decimal('20000'), Decimal('0'), Decimal('2000'))}
    assert res_discap.get("CTB_NAC") == Decimal('700.00')
    assert res_discap.get("CTB_CUID") == Decimal('100.00')

def test_cantabria_obras_mejora():
    # Obras de mejora de vivienda. Gasto = 4000€. Anterior no usado = 200€.
    # Raw ded = 4000 * 0.15 + 200 = 800€. Límite individual = 1000€. No hay discapacidad -> 800€
    profile = ProfileBuilder.from_dict(dict(region='cantabria', 
        age=40,
        cantabria_home_improvement_expenses_eur=Decimal('4000'),
        cantabria_home_improvement_prev_unused_eur=Decimal('200'),
        joint_declaration=False, custody_shared=True
    ))
    res = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile, Decimal('30000'), Decimal('0'), Decimal('3000'))}
    assert res.get("CTB_MEJ") == Decimal('800.00')

    # Si excede el límite: Gasto = 8000€. Raw ded = 1200€. Límite = 1000€. Con 1 miembro discapacitado (+500€) -> Límite = 1500€ -> 1200€
    profile_limit = ProfileBuilder.from_dict(dict(region='cantabria', 
        age=40,
        cantabria_home_improvement_expenses_eur=Decimal('8000'),
        cantabria_home_improvement_disabled_members_count=1,
        joint_declaration=False, custody_shared=True
    ))
    res_limit = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile_limit, Decimal('30000'), Decimal('0'), Decimal('3000'))}
    assert res_limit.get("CTB_MEJ") == Decimal('1200.00')

def test_cantabria_donaciones_limite_conjunto():
    # Donaciones: fundaciones 1000€ (15% = 150€), coopera 500€ (12% = 60€), apoyo disp 500€ (15% = 75€)
    # Total raw = 285€. BI total = 2.000€ -> límite del 10% = 200€ -> Deducción topada a 200€
    profile = ProfileBuilder.from_dict(dict(region='cantabria', 
        age=40,
        cantabria_donations_foundations_eur=Decimal('1000'),
        cantabria_donations_coopera_eur=Decimal('500'),
        cantabria_donations_disabled_support_eur=Decimal('500'),
        joint_declaration=False, custody_shared=True
    ))
    res = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile, Decimal('2000'), Decimal('0'), Decimal('500'))}
    assert res.get("CTB_DON") == Decimal('200.00')

def test_cantabria_gastos_enfermedad():
    # Renta límite = 20.000 - 5.550 = 14.450 < 22.946 (individual).
    # Gasto de enfermedad = 2000€. 10% = 200€. No discapacitado -> límite 500€ -> 200€
    profile = ProfileBuilder.from_dict(dict(region='cantabria', 
        age=40,
        minimo_personal_familiar=Decimal('5550'),
        cantabria_health_expenses_eur=Decimal('2000'),
        joint_declaration=False, custody_shared=True
    ))
    res = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile, Decimal('20000'), Decimal('0'), Decimal('1000'))}
    assert res.get("CTB_ENF") == Decimal('200.00')

    # Excediendo límite de base imponible -> excluido
    res_excl = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile, Decimal('35000'), Decimal('0'), Decimal('1000'))}
    assert "CTB_ENF" not in res_excl

def test_cantabria_guarderias_and_monoparental():
    # Guardería general. Gastos = 1000€ por 1 hijo. 15% = 150€. Prorrateo individual = 75€.
    profile = ProfileBuilder.from_dict(dict(region='cantabria', 
        age=30,
        cantabria_guarderia_expenses_eur=Decimal('1000'),
        cantabria_guarderia_kids_count=1,
        cantabria_is_monoparental=True,
        descendants_count=1,
        joint_declaration=False, custody_shared=True
    ))
    res = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile, Decimal('15000'), Decimal('0'), Decimal('1000'))}
    assert res.get("CTB_GUARD") == Decimal('75.00')
    assert res.get("CTB_MONO") == Decimal('200.00')

def test_cantabria_economiasocial_educacion_empleado():
    # Economía social: aportación 1000 (20% = 200), donaciones fomento 200 (25% = 50) -> total 250
    # Educación: libros 150, idiomas 200 (15% = 30) -> total 180. Límite individual = 100 -> 100
    # Empleado hogar: SS 1000 (20% = 200), es empleador con hijos menores y ambos trabajan -> 200 / 2 = 100
    profile = ProfileBuilder.from_dict(dict(region='cantabria', 
        age=38,
        cantabria_economy_social_apport_socio_eur=Decimal('1000'),
        cantabria_economy_social_donations_fomento_eur=Decimal('200'),
        cantabria_education_books_expenses_eur=Decimal('150'),
        cantabria_education_languages_expenses_eur=Decimal('200'),
        cantabria_domestic_employee_ss_eur=Decimal('1000'),
        cantabria_domestic_employee_is_employer=True,
        cantabria_domestic_employee_has_kids=True,
        cantabria_domestic_employee_both_work=True,
        descendants_count=1,
        joint_declaration=False, custody_shared=True
    ))
    res = {d.box_id: d.value for d in CantabriaDeductor.calculate(profile, Decimal('20000'), Decimal('0'), Decimal('2000'))}
    assert res.get("CTB_ECO_SOC") == Decimal('250.00')
    assert res.get("CTB_EDUC") == Decimal('100.00')
    assert res.get("CTB_DOM") == Decimal('100.00')
