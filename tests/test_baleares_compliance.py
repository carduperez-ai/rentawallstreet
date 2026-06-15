from src.ingestion.profile_builder import ProfileBuilder

# tests/test_baleares_compliance.py
from decimal import Decimal
from src.tax_compliance.regions.baleares.deductor import BalearsDeductor


def test_bal01_alquiler_general():
    # Colectivo A: menor de 36 años. BI = 20.000€ (<= 33k)
    # Alquiler de 4.000€ -> 15% = 600€, topado a 530€
    profile = ProfileBuilder.from_dict(
        dict(
            region="baleares",
            age=34,
            is_rent_habitual=True,
            rent_paid_annual_eur=Decimal("4000"),
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in BalearsDeductor.calculate(profile, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("BAL01") == Decimal("530")

    # Excede límite BI (34.000€ > 33k) -> Excluido
    res_high = {
        d.box_id: d.value for d in BalearsDeductor.calculate(profile, Decimal("34000"), Decimal("0"), Decimal("1000"))
    }
    assert "BAL01" not in res_high


def test_bal01_alquiler_colectivo_b():
    # Colectivo B: menor de 30 años. BI = 25.000€ (<= 33k)
    # Alquiler de 3.000€ -> 20% = 600€ (tope 650€)
    profile = ProfileBuilder.from_dict(
        dict(
            region="baleares",
            age=28,
            is_rent_habitual=True,
            rent_paid_annual_eur=Decimal("3000"),
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in BalearsDeductor.calculate(profile, Decimal("25000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("BAL01") == Decimal("600")


def test_bal04_books_and_material():
    # Caso 1: Individual, 1 hijo, BI=20.000€ (<= 33k), colectivo general.
    # Gastos de libros 300€ -> 100% topado a 220€
    profile = ProfileBuilder.from_dict(
        dict(
            region="baleares",
            age=40,
            descendants_count=1,
            balears_books_expenses_eur=Decimal("300"),
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in BalearsDeductor.calculate(profile, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("BAL04") == Decimal("220")

    # Caso 2: Colectivo B (discapacitado propio). Gastos 400€ -> topado a 350€
    profile_b = ProfileBuilder.from_dict(
        dict(
            region="baleares",
            age=40,
            descendants_count=1,
            balears_books_expenses_eur=Decimal("400"),
            balears_is_disabled_member=True,
            joint_declaration=False,
        )
    )
    res_b = {
        d.box_id: d.value for d in BalearsDeductor.calculate(profile_b, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res_b.get("BAL04") == Decimal("350")


def test_bal17_y_bal20_incompatibilidad():
    # Ambos con gastos. Conciliación (BAL17): gastos 1200€ -> 40% = 480€ (tope 660€)
    # Cuidado mayores (BAL20): gastos 1000€ -> 40% = 400€ (tope 660€)
    # Debe elegir Conciliación (BAL17) que da 480€ > 400€
    profile = ProfileBuilder.from_dict(
        dict(
            region="baleares",
            age=40,
            balears_conciliacion_expenses_eur=Decimal("1200"),
            balears_conciliacion_kids_count=1,
            balears_care_elderly_disabled_expenses_eur=Decimal("1000"),
            balears_care_elderly_disabled_people_count=1,
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in BalearsDeductor.calculate(profile, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("BAL17") == Decimal("480")
    assert "BAL20" not in res

    # Si Cuidado Mayores (BAL20) es mayor: gastos 2000€ -> 40% = 800€, topado a 660€ (660€ > 480€)
    profile_care_wins = ProfileBuilder.from_dict(
        dict(
            region="baleares",
            age=40,
            balears_conciliacion_expenses_eur=Decimal("1200"),
            balears_conciliacion_kids_count=1,
            balears_care_elderly_disabled_expenses_eur=Decimal("2000"),
            balears_care_elderly_disabled_people_count=1,
            joint_declaration=False,
        )
    )
    res_care = {
        d.box_id: d.value
        for d in BalearsDeductor.calculate(profile_care_wins, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res_care.get("BAL20") == Decimal("660")
    assert "BAL17" not in res_care


def test_bal18_birth_reduction_50():
    # Caso 1: 1 hijo (1º), BI=40.000€ (<= 52.8k). Individual.
    # Deducción base 800€ -> copropiedad 50% = 400€
    profile = ProfileBuilder.from_dict(
        dict(region="baleares", age=35, balears_births_count=1, balears_birth_order=1, joint_declaration=False)
    )
    res = {
        d.box_id: d.value for d in BalearsDeductor.calculate(profile, Decimal("40000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("BAL18") == Decimal("400")

    # Caso 2: Supera base imponible general individual (> 52.8k, ej. 60.000€)
    # Conserva el derecho a aplicar el 50% de la deducción = 400€ * 50% = 200€
    res_high = {
        d.box_id: d.value for d in BalearsDeductor.calculate(profile, Decimal("60000"), Decimal("0"), Decimal("1000"))
    }
    assert res_high.get("BAL18") == Decimal("200")
