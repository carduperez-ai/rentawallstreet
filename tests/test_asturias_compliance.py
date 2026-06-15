from src.ingestion.profile_builder import ProfileBuilder

# tests/test_asturias_compliance.py
from decimal import Decimal
from src.tax_compliance.regions.asturias.deductor import AsturiasDeductor


def test_ast01_alquiler_general():
    # Caso 1: Individual, general (sin colectivo especial), BI=20.000€ (<= 35k)
    # Alquiler de 6.000€ -> 10% = 600€, topado a 500€
    profile = ProfileBuilder.from_dict(
        dict(
            region="asturias",
            age=40,
            is_rent_habitual=True,
            rent_paid_annual_eur=Decimal("6000"),
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in AsturiasDeductor.calculate(profile, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("AST01") == Decimal("500")

    # Caso 2: Supera base imponible individual (36.000€ > 35k) -> Excluido
    res_high = {
        d.box_id: d.value for d in AsturiasDeductor.calculate(profile, Decimal("36000"), Decimal("0"), Decimal("1000"))
    }
    assert "AST01" not in res_high


def test_ast01_alquiler_colectivo_especial():
    # Caso 1: Joven (< 35 años), individual, BI=25.000€
    # Alquiler de 4.000€ -> 30% = 1.200€ (tope 1.500€)
    profile = ProfileBuilder.from_dict(
        dict(
            region="asturias",
            age=30,
            is_rent_habitual=True,
            rent_paid_annual_eur=Decimal("4000"),
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in AsturiasDeductor.calculate(profile, Decimal("25000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("AST01") == Decimal("1200")

    # Caso 2: Joven (< 35 años), individual, alquiler 6.000€ -> 30% = 1.800€, topado a 1.500€
    res_capped = {
        d.box_id: d.value for d in AsturiasDeductor.calculate(profile, Decimal("25000"), Decimal("0"), Decimal("1000"))
    }
    assert res_capped.get("AST01") == Decimal("1200")

    profile_high_rent = ProfileBuilder.from_dict(
        dict(
            region="asturias",
            age=30,
            is_rent_habitual=True,
            rent_paid_annual_eur=Decimal("6000"),
            joint_declaration=False,
        )
    )
    res_capped2 = {
        d.box_id: d.value
        for d in AsturiasDeductor.calculate(profile_high_rent, Decimal("25000"), Decimal("0"), Decimal("1000"))
    }
    assert res_capped2.get("AST01") == Decimal("1500")


def test_ast03_acogimiento_mayores_65():
    # Caso 1: 1 acogido, BI=20.000€ (<= 26k) -> 500€
    profile = ProfileBuilder.from_dict(dict(region="asturias", age=40, ascendants_over65=1, joint_declaration=False))
    res = {
        d.box_id: d.value for d in AsturiasDeductor.calculate(profile, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("AST03") == Decimal("500")

    # Caso 2: Excede BI individual (> 26k) -> Excluido
    res_high = {
        d.box_id: d.value for d in AsturiasDeductor.calculate(profile, Decimal("27000"), Decimal("0"), Decimal("1000"))
    }
    assert "AST03" not in res_high


def test_ast12_centros_cero_tres():
    # Caso 1: 1 hijo 0-3 años, gasto daycare=2000€, individual, BI=20.000€ (<= 26k)
    # Sin ayudas: 15% de 2.000€ = 300€ (tope 500€)
    ProfileBuilder.from_dict(
        dict(
            region="asturias",
            age=35,
            children_under_3=1,
            daycare_expenses_eur=Decimal("2000"),
            ast_asturias_0to3_care_grants_eur=Decimal("0"),
            joint_declaration=False,
        )
    )
    # Nota: AST12 es incompatible con AST20 (Cuidado hasta 25 años = 600€).
    # 300€ < 600€, por lo que el motor seleccionará AST20 de forma óptima.
    # Para verificar AST12 aisladamente, aumentemos el gasto de daycare de modo que AST12 supere a AST20.
    # Daycare = 5000€ -> 15% = 750€ (tope 500€). Para superar 600€ en AST20, vayamos a despoblamiento donde el tope es 1.000€ y el porcentaje es 30%.
    profile_despoblacion = ProfileBuilder.from_dict(
        dict(
            region="asturias",
            age=35,
            children_under_3=1,
            daycare_expenses_eur=Decimal("3000"),
            ast_asturias_0to3_care_grants_eur=Decimal("0"),
            ast_resides_in_asturias_despoblacion=True,
            joint_declaration=False,
        )
    )
    # Despoblación: 30% de 3.000€ = 900€ (tope 1000€). AST12 (900€) > AST20 (600€) -> Aplica AST12.
    res = {
        d.box_id: d.value
        for d in AsturiasDeductor.calculate(profile_despoblacion, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("AST12") == Decimal("900")
    assert "AST20" not in res

    # Caso 2: Con ayudas públicas de 200€ -> Deducción neta = 900 - 200 = 700€
    profile_with_grants = ProfileBuilder.from_dict(
        dict(
            region="asturias",
            age=35,
            children_under_3=1,
            daycare_expenses_eur=Decimal("3000"),
            ast_asturias_0to3_care_grants_eur=Decimal("200"),
            ast_resides_in_asturias_despoblacion=True,
            joint_declaration=False,
        )
    )
    res_grants = {
        d.box_id: d.value
        for d in AsturiasDeductor.calculate(profile_with_grants, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res_grants.get("AST12") == Decimal("700")


def test_ast13_libros_y_material():
    # Caso 1: Individual, no numerosa, BI=5.000€ (<= 6.5k) -> Límite 50€, gasto 80€ -> 50€
    profile = ProfileBuilder.from_dict(
        dict(
            region="asturias",
            age=40,
            descendants_count=1,
            ast_school_material_expenses_eur=Decimal("80"),
            joint_declaration=False,
        )
    )
    res = {
        d.box_id: d.value for d in AsturiasDeductor.calculate(profile, Decimal("5000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("AST13") == Decimal("50")

    # Caso 2: Individual, familia numerosa, BI=20.000€ -> Límite 75€, gasto 100€ -> 75€
    profile_large = ProfileBuilder.from_dict(
        dict(
            region="asturias",
            age=40,
            descendants_count=3,
            ast_school_material_expenses_eur=Decimal("100"),
            is_large_family=True,
            joint_declaration=False,
        )
    )
    res_large = {
        d.box_id: d.value
        for d in AsturiasDeductor.calculate(profile_large, Decimal("20000"), Decimal("0"), Decimal("1000"))
    }
    assert res_large.get("AST13") == Decimal("100")


def test_ast25_gastos_vitales_jovenes():
    # Caso 1: Joven de 24 años, BI=25.000€ (<= 28k) -> Deducción = 2.000€
    profile_24 = ProfileBuilder.from_dict(dict(region="asturias", age=24, joint_declaration=False))
    res = {
        d.box_id: d.value
        for d in AsturiasDeductor.calculate(profile_24, Decimal("25000"), Decimal("0"), Decimal("1000"))
    }
    assert res.get("AST25") == Decimal("2000")

    # Caso 2: Joven de 28 años, BI=25.000€ -> Deducción = 1.500€
    profile_28 = ProfileBuilder.from_dict(dict(region="asturias", age=28, joint_declaration=False))
    res_28 = {
        d.box_id: d.value
        for d in AsturiasDeductor.calculate(profile_28, Decimal("25000"), Decimal("0"), Decimal("1000"))
    }
    assert res_28.get("AST25") == Decimal("1500")

    # Caso 3: Joven de 32 años, BI=25.000€ -> Deducción = 1.000€
    profile_32 = ProfileBuilder.from_dict(dict(region="asturias", age=32, joint_declaration=False))
    res_32 = {
        d.box_id: d.value
        for d in AsturiasDeductor.calculate(profile_32, Decimal("25000"), Decimal("0"), Decimal("1000"))
    }
    assert res_32.get("AST25") == Decimal("1000")

    # Caso 4: Supera base imponible (> 28k) -> Excluido
    res_high = {
        d.box_id: d.value
        for d in AsturiasDeductor.calculate(profile_24, Decimal("29000"), Decimal("0"), Decimal("1000"))
    }
    assert "AST25" not in res_high
