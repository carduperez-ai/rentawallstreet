from src.ingestion.profile_builder import ProfileBuilder
# tests/test_castilla_la_mancha_compliance.py
from decimal import Decimal
from src.domain.fiscal_entities import TaxpayerProfile
from src.tax_compliance.regions.castilla_la_mancha.deductor import CastillaLaManchaDeductor

def test_clm01_and_clm02_nacimiento_familia_numerosa():
    # Perfil individual con 1 nacimiento y familia numerosa general con 1 miembro con discapacidad
    profile = ProfileBuilder.from_dict(dict(
        age=35,
        region="castilla_la_mancha",
        joint_declaration=False,
        birth_count_current_year=1,
        is_large_family=True,
        descendants_count=3,
        large_family_category="general",
        children_disabled_over65=1  # Detona incremento por discapacidad
    ))
    
    # Caso 1: Dentro del límite de base imponible (Indiv: <= 27000)
    big = Decimal('20000')
    bia = Decimal('5000')
    cuota_auton = Decimal('1000')
    
    deductions = CastillaLaManchaDeductor.calculate(profile, big, bia, cuota_auton)
    ded_map = {d.box_id: d.value for d in deductions}
    
    # CLM01: Nacimiento de 1 hijo individual = 100€ / 2 = 50€
    assert ded_map["CLM01"] == Decimal('50.00')
    # CLM02: Familia numerosa general con discapacidad individual = 300€ / 2 = 150€
    assert ded_map["CLM02"] == Decimal('150.00')

    # Caso 2: Fuera del límite de base imponible
    deductions_exceeded = CastillaLaManchaDeductor.calculate(profile, Decimal('25000'), Decimal('5000'), cuota_auton)
    assert len(deductions_exceeded) == 0

def test_clm03_and_clm04_monoparental_y_educacion():
    # Perfil conjunto de familia monoparental con 2 descendientes escolarizados
    profile = ProfileBuilder.from_dict(dict(
        age=40,
        region="castilla_la_mancha",
        joint_declaration=True,
        is_monoparental=True,
        descendants_count=2,
        clm_education_books_expenses=Decimal('300'),
        clm_education_languages_expenses=Decimal('200'),
        clm_education_scholarships_eur=Decimal('50'),
        minimo_personal_familiar=Decimal('7000')
    ))
    
    # General + Ahorro = 18000. base_edu = 18000 - 7000 = 11000.
    # Límite por hijo en conjunta <= 12000 es 200€ por hijo. Total límite = 200 * 2 = 400€.
    # Gasto neto = 300 + 0.15 * 200 - 50 = 280€.
    big = Decimal('15000')
    bia = Decimal('3000')
    cuota_auton = Decimal('500')
    
    deductions = CastillaLaManchaDeductor.calculate(profile, big, bia, cuota_auton)
    ded_map = {d.box_id: d.value for d in deductions}
    
    assert ded_map["CLM03"] == Decimal('200.00')
    assert ded_map["CLM04"] == Decimal('280.00')  # Gasto neto < límite total

def test_clm05_guarderia_y_clm07_discapacidad():
    # Perfil con gastos de guardería y discapacidad familiar
    profile = ProfileBuilder.from_dict(dict(
        age=32,
        region="castilla_la_mancha",
        joint_declaration=False,
        children_under_3=1,
        daycare_expenses_eur=Decimal('1000'),
        clm_guarderia_subventions_eur=Decimal('100'),
        ascendants_disabled_count=1
    ))
    
    # Gasto neto guardería = 1000 * 0.30 - 100 = 200€. Individual = 200 / 2 = 100€.
    # Discapacidad ascendiente individual = 300 / 2 = 150€.
    big = Decimal('15000')
    bia = Decimal('2000')
    
    deductions = CastillaLaManchaDeductor.calculate(profile, big, bia, Decimal('500'))
    ded_map = {d.box_id: d.value for d in deductions}
    
    assert ded_map["CLM05"] == Decimal('100.00')
    assert ded_map["CLM07"] == Decimal('150.00')

def test_clm08_and_clm09_mayores_y_cuidado():
    profile = ProfileBuilder.from_dict(dict(
        age=76,
        region="castilla_la_mancha",
        joint_declaration=False,
        ascendants_over75=1,
        clm_mayor_residence_public_over_30_days=False,
        clm_ascendant_residence_public_over_30_days=False
    ))
    
    deductions = CastillaLaManchaDeductor.calculate(profile, Decimal('10000'), Decimal('2000'), Decimal('300'))
    ded_map = {d.box_id: d.value for d in deductions}
    
    assert ded_map["CLM08"] == Decimal('150.00')
    assert ded_map["CLM09"] == Decimal('75.00')  # 150 / 2 = 75

def test_clm10_and_clm11_acogimientos():
    profile = ProfileBuilder.from_dict(dict(
        age=45,
        region="castilla_la_mancha",
        joint_declaration=False,
        clm_acogimiento_menores_count=2,
        clm_acogimiento_menores_order_first=True,  # 1º es 500, sucesivos 600
        clm_acogimiento_senior_disc_count=1
    ))
    
    # 2 acogidos: 500 + 600 = 1100. Individual = 1100 / 2 = 550.
    # Acogido senior: 600. Individual = 600 / 2 = 300.
    deductions = CastillaLaManchaDeductor.calculate(profile, Decimal('8000'), Decimal('2000'), Decimal('400'))
    ded_map = {d.box_id: d.value for d in deductions}
    
    assert ded_map["CLM10"] == Decimal('550.00')
    assert ded_map["CLM11"] == Decimal('300.00')

def test_alquiler_incompatibilities_clm12_to_clm16():
    # El contribuyente califica para CLM12 (Jóvenes) y CLM14 (Familia numerosa)
    # y además CLM02 (Familia numerosa general sin discapacidad)
    # CLM14 y CLM02 son incompatibles.
    # Evaluamos qué combinación da mayor beneficio.
    # Datos:
    # rent_paid = 3000.
    # CLM12 (Joven rural): 20% de 3000 = 600, cap rural 612. Individual = 300.
    # CLM14 (Alquiler FN): 15% de 3000 = 450. Individual = 225.
    # CLM02 (Familia numerosa general): 200. Individual = 100.
    #
    # Combinación A: CLM02 activa (100€) + CLM12 (300€) = 400€.
    # Combinación B: CLM14 activa (225€) (CLM02 desactivada) = 225€.
    # El sistema óptimo debe elegir la Combinación A (CLM02 + CLM12).
    
    profile = ProfileBuilder.from_dict(dict(
        age=28,
        region="castilla_la_mancha",
        joint_declaration=False,
        rent_paid_annual_eur=Decimal('3000'),
        is_large_family=True,
        descendants_count=3,
        large_family_category="general",
        clm_rural_despoblacion_zone="intensa",
        clm_rural_municipality_population=1500,
        clm_rural_estancia_efectiva=True
    ))
    
    deductions = CastillaLaManchaDeductor.calculate(profile, Decimal('10000'), Decimal('1000'), Decimal('400'))
    ded_map = {d.box_id: d.value for d in deductions}
    
    assert "CLM02" in ded_map
    assert "CLM12" in ded_map
    assert "CLM14" not in ded_map
    
    assert ded_map["CLM02"] == Decimal('100.00')
    assert ded_map["CLM12"] == Decimal('300.00')

def test_clm17_to_clm20_donaciones_hipoteca():
    profile = ProfileBuilder.from_dict(dict(
        age=30,
        region="castilla_la_mancha",
        joint_declaration=True,
        clm_donations_cooperacion_eur=Decimal('1000'),
        clm_donations_idi_eur=Decimal('500'),
        clm_donations_cultural_mecenazgo_eur=Decimal('400'),
        clm_mortgage_interest_under_40_eur=Decimal('200')
    ))
    
    # General + Ahorro = 20000 (joint).
    # CLM17: 15% de 1000 = 150. Lim 10% de BI = 2000.
    # CLM18: 15% de 500 = 75. Lim 10% de cuota = 80.
    # CLM19: 15% de 400 = 60. Lim 10% de BI = 2000.
    # CLM20: Interest 200, cap for <= 25000 is 150.
    
    deductions = CastillaLaManchaDeductor.calculate(profile, Decimal('15000'), Decimal('5000'), Decimal('800'))
    ded_map = {d.box_id: d.value for d in deductions}
    
    assert ded_map["CLM17"] == Decimal('150.00')
    assert ded_map["CLM18"] == Decimal('75.00')
    assert ded_map["CLM19"] == Decimal('60.00')
    assert ded_map["CLM20"] == Decimal('150.00')

def test_clm21_to_clm23_despoblacion_rural():
    profile = ProfileBuilder.from_dict(dict(
        age=35,
        region="castilla_la_mancha",
        joint_declaration=False,
        clm_rural_estancia_efectiva=True,
        clm_rural_despoblacion_zone="extrema",
        clm_rural_municipality_population=1200,
        clm_rural_adq_rehab_expenses_eur=Decimal('10000'),
        clm_traslado_laboral_despoblacion=True,
        clm_traslado_laboral_year=2025
    ))
    
    # CLM21: Extrema despoblación < 2000 = 25% of cuota (1000) = 250€.
    # CLM22: 15% of 10000 = 1500€.
    # CLM23: Relocation = 500€. Capped at cuota (1000).
    
    deductions = CastillaLaManchaDeductor.calculate(profile, Decimal('15000'), Decimal('2000'), Decimal('1000'))
    ded_map = {d.box_id: d.value for d in deductions}
    
    assert ded_map["CLM21"] == Decimal('250.00')
    assert ded_map["CLM22"] == Decimal('1500.00')
    assert ded_map["CLM23"] == Decimal('500.00')

def test_clm24_to_clm27_inversiones_y_otros():
    profile = ProfileBuilder.from_dict(dict(
        age=32,
        region="castilla_la_mancha",
        joint_declaration=False,
        clm_inv_acciones_sociedades_eur=Decimal('20000'),
        clm_inv_economia_social_eur=Decimal('15000'),  # Incompatibles, se elegirá la óptima (acciones: 20000*0.2 = 4000)
        clm_ahorro_primera_vivienda_eur=Decimal('4000'),
        clm_assistant_dog_vet_expenses_eur=Decimal('200')
    ))
    
    # CLM24: Acciones = 20% of 20000 = 4000.
    # CLM25: Economía Social = 20% of 15000 = 3000.
    # CLM26: Ahorro = 15% of 4000 = 600.
    # CLM27: Vet = 30% of 200 = 60.
    
    deductions = CastillaLaManchaDeductor.calculate(profile, Decimal('15000'), Decimal('2000'), Decimal('800'))
    ded_map = {d.box_id: d.value for d in deductions}
    
    assert "CLM24" in ded_map
    assert "CLM25" not in ded_map
    assert ded_map["CLM24"] == Decimal('4000.00')
    assert ded_map["CLM26"] == Decimal('600.00')
    assert ded_map["CLM27"] == Decimal('60.00')
