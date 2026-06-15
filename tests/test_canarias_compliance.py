from src.ingestion.profile_builder import ProfileBuilder

# tests/test_canarias_compliance.py
from decimal import Decimal
from src.tax_compliance.regions.canarias.deductor import CanariasDeductor


def test_canarias_donaciones():
    # Caso 1: Individual. Cuota autonómica = 1.000€
    # Donaciones ecológicas 500€ -> 10% = 50€, tope = min(50, 1000*0.10=100, 150) = 50€
    # Donaciones históricas 1000€ -> 20% = 200€, tope = min(200, 1000*0.10=100, 150) = 100€
    # Donaciones cultural/RDI 400€ -> 15% = 60€, tope = min(60, 1000*0.05=50) = 50€
    # Donaciones tercer sector 200€ -> 150*20% + 50*15% = 30 + 7.50 = 37.50€, tope = 10% de BI (20.000*0.10=2000) -> 37.50€
    profile = ProfileBuilder.from_dict(
        dict(
            region="canarias",
            age=40,
            canarias_donations_ecological_eur=Decimal("500"),
            canarias_donations_historical_eur=Decimal("1000"),
            canarias_donations_cultural_rdi_eur=Decimal("400"),
            canarias_donations_third_sector_eur=Decimal("200"),
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in CanariasDeductor.calculate(profile, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }

    assert res.get("CAN_ECO") == Decimal("50.00")
    assert res.get("CAN_HIST_DON") == Decimal("100.00")
    assert res.get("CAN_CULT_DEP_RDI") == Decimal("50.00")
    assert res.get("CAN_ESL") == Decimal("37.50")


def test_canarias_estudios():
    # Caso 1: Individual, BI = 30.000€ (< 37.062€)
    # Educación superior: 1 hijo fuera de la isla -> 1.920€
    # Educación no superior: gastos 150€ -> 1 hijo -> tope 133€
    profile = ProfileBuilder.from_dict(
        dict(
            region="canarias",
            age=45,
            descendants_count=1,
            canarias_descendants_studying_outside_count=1,
            canarias_descendants_non_higher_edu_expenses_eur=Decimal("150"),
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in CanariasDeductor.calculate(profile, Decimal("30000"), Decimal("0"), Decimal("5000"))
    }
    assert res.get("CAN_EST_SUP") == Decimal("1920.00")
    assert res.get("CAN_EST_NOSUP") == Decimal("133.00")

    # Caso 2: Excede límite de base imponible general individual (50.000€ > 46.455€) -> Excluido
    res_high = {
        d.box_id: d.value for d in CanariasDeductor.calculate(profile, Decimal("50000"), Decimal("0"), Decimal("5000"))
    }
    assert "CAN_EST_SUP" not in res_high
    assert "CAN_EST_NOSUP" not in res_high


def test_canarias_vivienda_15_cap():
    # Cuota autonómica = 10.000€. Límite 15% conjunto = 1.500€
    # 1. Adecuación Bienes Culturales: gastos 5.000€ -> 10% = 500€ (tope 10% cuota_auton = 1000€)
    # 2. Inversión Vivienda Habitual: hipoteca 8.000€ (tope base 6.000€) -> edad 35 (< 40) -> BI < 26.035€ -> pct 5.5% -> 6000 * 5.5% = 330€
    # 3. Rehab energética: gastos 10.000€ (tope base 7.000€) -> 12% = 840€ (tope 10% cuota_auton = 1000€)
    # 4. Adecuación Vivienda Discapacidad: gastos 10.000€ -> edad 35 -> 14% = 1.400€
    # Suma raw = 500 + 330 + 840 + 1400 = 3.070€
    # Supera límite de 1.500€. Escala de reducción = 1500 / 3070 = 0.4885993...
    profile = ProfileBuilder.from_dict(
        dict(
            region="canarias",
            age=35,
            canarias_rehabilitation_historical_eur=Decimal("5000"),
            mortgage_paid_eur=Decimal("8000"),
            canarias_home_rehabilitation_energy_eur=Decimal("10000"),
            canarias_home_adequacy_disability_eur=Decimal("10000"),
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in CanariasDeductor.calculate(profile, Decimal("20000"), Decimal("0"), Decimal("10000"))
    }

    # Verificamos que se añaden las 4 deducciones y su suma exacta es 1.500,00€
    boxes = ["CAN_HIST_REHAB", "CAN_VIV_HAB", "CAN_VIV_ENER", "CAN_VIV_DISCAP"]
    active_deductions = [k for k in res if k in boxes]
    assert len(active_deductions) == 4
    total_val = sum(res[k] for k in active_deductions)
    assert total_val == Decimal("1500.00")


def test_canarias_alquileres_and_dacion():
    # Alquiler habitual: edad 30 (< 40 -> tope 760€). BI = 20.000€. Alquiler = 4.000€ (rent > 10% de BI = 2000€) -> 24% = 960€, topado a 760€
    # Alquiler por dación en pago: 3.000€ -> 25% = 750€ (tope 1200€)
    profile = ProfileBuilder.from_dict(
        dict(
            region="canarias",
            age=30,
            is_rent_habitual=True,
            rent_paid_annual_eur=Decimal("4000"),
            canarias_rent_dacion_pago_paid_eur=Decimal("3000"),
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in CanariasDeductor.calculate(profile, Decimal("20000"), Decimal("0"), Decimal("3000"))
    }
    assert res.get("CAN_ALQUILER") == Decimal("760.00")
    assert res.get("CAN_ALQ_DACION") == Decimal("750.00")


def test_canarias_incompatibilidades_arrendador():
    # Adecuación arrendamiento (CAN_ARREND_ADEQ): gastos 2000€ -> 10% = 200€ (tope 150€)
    # Seguro impago (CAN_ARREND_INSUR): primas 300€ -> 75% = 225€ (tope 150€)
    # Ambos dan 150€ -> Toma la primera (Adecuación arrendamiento) y anula la otra
    profile = ProfileBuilder.from_dict(
        dict(
            region="canarias",
            age=40,
            canarias_landlord_adequacy_rent_expenses_eur=Decimal("2000"),
            canarias_landlord_unpaid_insurance_premiums_eur=Decimal("300"),
            canarias_landlord_unpaid_insurance_monthly_rent_eur=Decimal("700"),
            canarias_landlord_unpaid_insurance_fianza_deposited=True,
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in CanariasDeductor.calculate(profile, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("CAN_ARREND_ADEQ") == Decimal("150.00")
    assert "CAN_ARREND_INSUR" not in res

    # Si Seguro impago es mayor: gastos adecuación 500€ -> 50€, seguro impago primas 100€ -> 75€
    profile_insur_wins = ProfileBuilder.from_dict(
        dict(
            region="canarias",
            age=40,
            canarias_landlord_adequacy_rent_expenses_eur=Decimal("500"),
            canarias_landlord_unpaid_insurance_premiums_eur=Decimal("100"),
            canarias_landlord_unpaid_insurance_monthly_rent_eur=Decimal("700"),
            canarias_landlord_unpaid_insurance_fianza_deposited=True,
            joint_declaration=False,
        )
    )
    res_insur = {
        d.box_id: d.value
        for d in CanariasDeductor.calculate(profile_insur_wins, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res_insur.get("CAN_ARREND_INSUR") == Decimal("75.00")
    assert "CAN_ARREND_ADEQ" not in res_insur


def test_canarias_desempleado_enfermedad_etc():
    # Contribuyente desempleado (CAN_DESEMPLEADO): trabajo 18.000€, BI = 19.500€ (resto = 1.500 <= 1600) -> 120€
    # Gastos de enfermedad profesional: 1.000€ -> 12% = 120€, tope 500€ (BI <= 46.455)
    # Familias dependientes discapacidad (CAN_DEP_DISCAP): 1 familiar -> 600€
    # Contratación empleado hogar (CAN_EMP_HOGAR): SS 1000€ -> age 45 con 1 hijo -> 20% = 200€ (tope 500€)
    profile = ProfileBuilder.from_dict(
        dict(
            region="canarias",
            age=45,
            descendants_count=1,
            canarias_is_unemployed_over_6_months=True,
            canarias_work_income_eur=Decimal("18000"),
            canarias_health_expenses_eur=Decimal("1000"),
            canarias_dependent_disabled_65_count=1,
            canarias_domestic_employee_ss_eur=Decimal("1000"),
            joint_declaration=False,
            custody_shared=True,
        )
    )
    res = {
        d.box_id: d.value for d in CanariasDeductor.calculate(profile, Decimal("19500"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("CAN_DESEMPLEADO") == Decimal("120")
    assert res.get("CAN_MED_EXP") == Decimal("120.00")
    assert res.get("CAN_DEP_DISCAP") == Decimal("300.00")
    assert res.get("CAN_EMP_HOGAR") == Decimal("200.00")


def test_canarias_nacimiento_and_personal():
    # Nacimiento: 2 hijos nacidos (1º y 2º en orden) -> 265 + 265 = 530 -> copropiedad 50% = 265€
    # Discapacidad y edad contribuyente (CAN_DISCAP_EDAD): age 66 -> 160€
    # Familia monoparental (CAN_MONOPARENTAL): monoparental con 1 hijo -> 133€
    # Familia numerosa (CAN_FAM_NUM): categoría general -> 597 / 2 = 298.50€
    profile = ProfileBuilder.from_dict(
        dict(
            region="canarias",
            age=66,
            birth_count_current_year=2,
            balears_birth_order=1,
            is_monoparental=True,
            descendants_count=3,
            is_large_family=True,
            large_family_category="general",
            joint_declaration=False,
            custody_shared=True,
        )
    )
    res = {
        d.box_id: d.value for d in CanariasDeductor.calculate(profile, Decimal("20000"), Decimal("0"), Decimal("2000"))
    }
    assert res.get("CAN_NACIMIENTO") == Decimal("265.00")
    assert res.get("CAN_DISCAP_EDAD") == Decimal("160.00")
    assert res.get("CAN_MONOPARENTAL") == Decimal("133")
    assert res.get("CAN_FAM_NUM") == Decimal("298.50")
