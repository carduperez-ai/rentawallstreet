from src.ingestion.profile_builder import ProfileBuilder
# tests/test_castilla_y_leon_compliance.py
from decimal import Decimal
from src.domain.fiscal_entities import TaxpayerProfile
from src.tax_compliance.regions.castilla_leon.deductor import CastillaLeonDeductor

def test_cyl_num_familia_numerosa():
    # Perfil individual con familia numerosa general (3 descendientes) sin discapacidad
    profile = ProfileBuilder.from_dict(dict(
        age=35,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        is_large_family=True,
        descendants_count=3,
        minimo_personal_familiar=Decimal('5606')
    ))
    
    # 600€ base / 2 = 300€
    deductions = CastillaLeonDeductor.calculate(profile, Decimal('20000'), Decimal('1000'), Decimal('500'))
    ded_map = {d.box_id: d.value for d in deductions}
    assert ded_map["CYL_NUM"] == Decimal('300.00')

    # Caso con discapacidad >= 65% del declarante (+600€)
    profile_disc = ProfileBuilder.from_dict(dict(
        age=35,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        is_large_family=True,
        descendants_count=4,  # 1500€ base
        disability_grade=65,  # Detona incremento de 600€
        minimo_personal_familiar=Decimal('5606')
    ))
    # (1500 + 600) / 2 = 1050€
    deductions_disc = CastillaLeonDeductor.calculate(profile_disc, Decimal('20000'), Decimal('1000'), Decimal('500'))
    ded_map_disc = {d.box_id: d.value for d in deductions_disc}
    assert ded_map_disc["CYL_NUM"] == Decimal('1050.00')


def test_cyl02_nacimiento_adopcion():
    # Perfil individual con 1er nacimiento en medio general
    profile_gen = ProfileBuilder.from_dict(dict(
        age=30,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        birth_count_current_year=1,
        descendants_count=1,
        cyl_rural_municipality_population=15000, # No rural
        minimo_personal_familiar=Decimal('5606')
    ))
    # 1.010€ / 2 = 505€
    deductions_gen = CastillaLeonDeductor.calculate(profile_gen, Decimal('15000'), Decimal('500'), Decimal('300'))
    ded_map_gen = {d.box_id: d.value for d in deductions_gen}
    assert ded_map_gen["CYL02"] == Decimal('505.00')

    # Perfil individual con 2º nacimiento en municipio rural con discapacidad del nacido
    profile_rur_disc = ProfileBuilder.from_dict(dict(
        age=30,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        birth_count_current_year=1,
        descendants_count=2,
        cyl_rural_municipality_population=2500, # Rural (<= 5000)
        cyl_birth_is_disabled=True,            # Discapacidad: Duplica
        minimo_personal_familiar=Decimal('5606')
    ))
    # Rural 2º hijo: 2.070€ * 2 (discapacidad) / 2 = 2.070€
    deductions_rur = CastillaLeonDeductor.calculate(profile_rur_disc, Decimal('15000'), Decimal('500'), Decimal('300'))
    ded_map_rur = {d.box_id: d.value for d in deductions_rur}
    assert ded_map_rur["CYL02"] == Decimal('2070.00')


def test_cyl_mul_partos_multiples():
    # Perfil individual con parto doble en medio rural
    profile = ProfileBuilder.from_dict(dict(
        age=32,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        cyl_multiple_births_count=2,
        cyl_rural_municipality_population=2000,
        minimo_personal_familiar=Decimal('5606')
    ))
    # 50% de 2.070€ (Rural) * 2 = 2.070€ / 2 = 1.035€
    deductions = CastillaLeonDeductor.calculate(profile, Decimal('20000'), Decimal('0'), Decimal('500'))
    ded_map = {d.box_id: d.value for d in deductions}
    assert ded_map["CYL_MUL"] == Decimal('1035.00')


def test_cyl_adop_gastos_adopcion():
    profile = ProfileBuilder.from_dict(dict(
        age=40,
        region="castilla_leon",
        joint_declaration=True, # Conjunta: 100% de la deducción
        cyl_adoptions_count=1,
        cyl_adoption_international=True,
        minimo_personal_familiar=Decimal('5606')
    ))
    # 3.625€ * 1 = 3.625€
    deductions = CastillaLeonDeductor.calculate(profile, Decimal('30000'), Decimal('1000'), Decimal('800'))
    ded_map = {d.box_id: d.value for d in deductions}
    assert ded_map["CYL_ADOP"] == Decimal('3625.00')


def test_cyl_cuid_cuidado_hijos():
    # Perfil con guardería
    profile = ProfileBuilder.from_dict(dict(
        age=34,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        descendants_count=1,
        cyl_daycare_expenses_eur=Decimal('1000'),
        minimo_personal_familiar=Decimal('5606')
    ))
    # General + Ahorro = 18000. BI Neta = 18000 - 5606 = 12394 <= 18900.
    # Guardería: 1.000€ (dentro del límite de 1.320€).
    # Individual: 1.000€ / 2 = 500€.
    deductions = CastillaLeonDeductor.calculate(profile, Decimal('15000'), Decimal('3000'), Decimal('800'))
    ded_map = {d.box_id: d.value for d in deductions}
    assert ded_map["CYL_CUID"] == Decimal('500.00')


def test_cyl_hog_cuotas_empleados_hogar():
    profile = ProfileBuilder.from_dict(dict(
        age=36,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        descendants_count=1,
        cyl_domestic_employee_ss_home_eur=Decimal('1000'),
        minimo_personal_familiar=Decimal('5606')
    ))
    # SS Hogar: 15% de 1.000€ = 150€ / 2 = 75€.
    deductions = CastillaLeonDeductor.calculate(profile, Decimal('15000'), Decimal('1000'), Decimal('500'))
    ded_map = {d.box_id: d.value for d in deductions}
    assert ded_map["CYL_HOG"] == Decimal('75.00')


def test_cyl_disc_contribuyente():
    profile = ProfileBuilder.from_dict(dict(
        age=68,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        disability_grade=65,
        cyl_disability_resides_public_center=False,
        minimo_personal_familiar=Decimal('5606')
    ))
    # Contribuyente >= 65 años con disc >= 65% = 656€. No se prorratea.
    deductions = CastillaLeonDeductor.calculate(profile, Decimal('12000'), Decimal('1000'), Decimal('400'))
    ded_map = {d.box_id: d.value for d in deductions}
    assert ded_map["CYL_DISC"] == Decimal('656.00')


def test_cyl_viv_rural_jovenes():
    profile = ProfileBuilder.from_dict(dict(
        age=32,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        cyl_vivienda_rural_acquisition_rehab_expenses_eur=Decimal('8000'),
        cyl_vivienda_rural_value_eur=Decimal('120000'),
        cyl_vivienda_rural_is_first=True,
        minimo_personal_familiar=Decimal('5606')
    ))
    # Inversión: 15% de 8.000€ = 1.200€ / 2 = 600€.
    deductions = CastillaLeonDeductor.calculate(profile, Decimal('15000'), Decimal('1000'), Decimal('500'))
    ded_map = {d.box_id: d.value for d in deductions}
    assert ded_map["CYL_VIV_RURAL"] == Decimal('600.00')


def test_cyl01_alquiler_joven():
    # Alquiler en medio urbano (> 10.000 habitantes)
    profile_urb = ProfileBuilder.from_dict(dict(
        age=34,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        is_rent_habitual=True,
        rent_paid_annual_eur=Decimal('3000'),
        cyl_rural_municipality_population=25000, # Urbano
        minimo_personal_familiar=Decimal('5606')
    ))
    # 20% de 3000 = 600€ capped at 459€ / 2 = 229.50€
    deductions_urb = CastillaLeonDeductor.calculate(profile_urb, Decimal('15000'), Decimal('1000'), Decimal('400'))
    ded_map_urb = {d.box_id: d.value for d in deductions_urb}
    assert ded_map_urb["CYL01"] == Decimal('229.50')

    # Alquiler en medio rural (<= 10.000 habitantes)
    profile_rur = ProfileBuilder.from_dict(dict(
        age=34,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        is_rent_habitual=True,
        rent_paid_annual_eur=Decimal('3000'),
        cyl_rural_municipality_population=2500, # Rural (<= 10000)
        minimo_personal_familiar=Decimal('5606')
    ))
    # 25% de 3000 = 750€ capped at 612€ / 2 = 306.00€
    deductions_rur = CastillaLeonDeductor.calculate(profile_rur, Decimal('15000'), Decimal('1000'), Decimal('400'))
    ded_map_rur = {d.box_id: d.value for d in deductions_rur}
    assert ded_map_rur["CYL01"] == Decimal('306.00')


def test_cyl_limites_renta_excedidos():
    profile = ProfileBuilder.from_dict(dict(
        age=30,
        region="castilla_leon",
        joint_declaration=False, custody_shared=True,
        is_rent_habitual=True,
        rent_paid_annual_eur=Decimal('3000'),
        minimo_personal_familiar=Decimal('5606')
    ))
    # BI General = 25000. BI Ahorro = 0. MPF = 5606. BI Neta = 19394 > 18900.
    # No califica por superar el límite de base imponible neta.
    deductions = CastillaLeonDeductor.calculate(profile, Decimal('25000'), Decimal('0'), Decimal('500'))
    assert "CYL01" not in {d.box_id for d in deductions}
