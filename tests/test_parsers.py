import pytest
from decimal import Decimal
from datetime import datetime
from src.domain.fiscal_entities import OtherIncome, IncomeSubtype, FamilyMember, FamilyRole


def test_other_income_titularidad_bounds():
    # Should work
    income = OtherIncome(
        date=datetime.now(),
        description="Lotería",
        gain_loss_eur=Decimal("100000"),
        category="premios",
        subtype=IncomeSubtype.LOTERIAS_OFICIALES,
        porcentaje_titularidad=Decimal("50.00"),
    )
    assert income.porcentaje_titularidad == Decimal("50.00")

    # Should fail if <= 0
    with pytest.raises(ValueError, match="Titularidad debe estar entre"):
        OtherIncome(
            date=datetime.now(),
            description="Lotería",
            gain_loss_eur=Decimal("100000"),
            category="premios",
            porcentaje_titularidad=Decimal("0"),
        )

    # Should fail if > 100
    with pytest.raises(ValueError, match="Titularidad debe estar entre"):
        OtherIncome(
            date=datetime.now(),
            description="Lotería",
            gain_loss_eur=Decimal("100000"),
            category="premios",
            porcentaje_titularidad=Decimal("101"),
        )

    # Should fail if not Decimal
    with pytest.raises(ValueError, match="Decimal estricto"):
        OtherIncome(date=datetime.now(), description="Lotería", gain_loss_eur=100000.0, category="premios")


def test_family_member_limits():
    m1 = FamilyMember(role=FamilyRole.DESCENDANT, age=20, rentas_obtenidas=Decimal("9000"))
    assert m1.rentas_obtenidas > Decimal("8000")

    m2 = FamilyMember(
        role=FamilyRole.DESCENDANT, age=20, rentas_obtenidas=Decimal("2000"), presenta_declaracion_independiente=True
    )
    assert m2.presenta_declaracion_independiente
    assert m2.rentas_obtenidas > Decimal("1800")

    m3 = FamilyMember(role=FamilyRole.ASCENDANT, age=70, convivencia_meses=5)
    assert m3.convivencia_meses < 6
