import pytest

from src.ingestion.profile_builder import ProfileBuilder
# tests/test_irpf_calculator_correcciones.py
"""
Suite de pruebas unitarias y de estrés para certificar físicamente
las correcciones de cumplimiento de la LIRPF y prelación del Art. 49.
"""
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass
from typing import List
import pytest

from src.tax_compliance.core.irpf_calculator import IRPFCalculator
from src.domain.fiscal_entities import Dividend, WorkIncome, TaxpayerProfile, OtherIncome, BusinessIncome, RentalIncome

# ---------------------------------------------------------------------------
# Minimal stubs para simular TaxEvent de cripto y de stocks
# ---------------------------------------------------------------------------

@dataclass
class _CryptoEvent:
    asset: str
    asset_type: str
    gain_loss_eur: Decimal
    total_sale_eur: Decimal
    total_cost_eur: Decimal
    platform: str = "Binance"
    is_wash_sale: bool = False

@dataclass
class _StockEvent:
    asset: str
    asset_type: str
    gain_loss_eur: Decimal
    total_sale_eur: Decimal
    total_cost_eur: Decimal
    platform: str = "DeGiro"
    is_wash_sale: bool = False

# ---------------------------------------------------------------------------
# TESTS DE CERTIFICACIÓN FISCAL
# ---------------------------------------------------------------------------

def test_seguro_medico_especie():
    """
    Art. 42.2.f LIRPF: Seguro médico exento hasta 500€ (o 1500€ si discapacidad >= 33%).
    """
    # Caso 1: Contribuyente sin discapacidad, seguro médico = 800€ -> Exceso de 300€ imputable
    work_normal = WorkIncome(
        retribuciones_dinerarias=Decimal('45000'),
        retenciones=Decimal('9000'),
        gastos_deducibles=Decimal('2000'),
        health_insurance_eur=Decimal('800')
    )
    profile_normal = ProfileBuilder.from_dict(dict(age=40, disability_grade=0))
    
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[],
        stock_events=[],
        work=work_normal,
        profile=profile_normal,
        rental_income=[],
        other_pyg=[],
        business_income=[],
        attributed_income=[],
        region="madrid"
    )
    res = calc.calculate().raw_summary
    # Especie = 300€. El bruto total del trabajo debe ser 45000 + 300 = 45300
    assert res["work_bruto"] == Decimal('45300')

    # Caso 2: Contribuyente con discapacidad >= 33%, seguro médico = 800€ -> Exento
    profile_disabled = ProfileBuilder.from_dict(dict(age=40, disability_grade=33))
    calc_disabled = IRPFCalculator(
        dividends=[],
        crypto_events=[],
        stock_events=[],
        work=work_normal,
        profile=profile_disabled,
        rental_income=[],
        other_pyg=[],
        business_income=[],
        attributed_income=[],
        region="madrid"
    )
    res_disabled = calc_disabled.calculate().raw_summary
    assert res_disabled["work_bruto"] == Decimal('45000')


def test_suministros_teletrabajo_autonomo():
    """
    Art. 30.2.5.ª.b LIRPF: Deducción por suministros de vivienda habitual teletrabajo
    fórmula legal: gastos_suministros_hogar_eur * porcentaje_afectacion_vivienda * 0.30
    """
    business = BusinessIncome(
        ingresos_explotacion=Decimal('50000'),
        gastos_explotacion=Decimal('10000'),
        gastos_suministros_hogar_eur=Decimal('4000'),
        porcentaje_afectacion_vivienda=Decimal('0.25'), # 25% de superficie
        estimacion_simplificada=True
    )
    
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[],
        stock_events=[],
        work=None,
        profile=None,
        rental_income=[],
        other_pyg=[],
        business_income=[business],
        attributed_income=[],
        region="madrid"
    )
    res = calc.calculate().raw_summary
    # Deducción suministros = 4000 * 0.25 * 0.30 = 300
    # Rendimiento previo = 50000 - 10000 - 300 = 39700
    # Provisiones = 39700 * 0.05 = 1985 (tope 2000)
    # Neto total = 39700 - 1985 = 37715
    assert res["business_net_income"] == Decimal('37715')


def test_capital_inmobiliario_amortizacion_y_limite_grupo_a():
    """
    Art. 23.1 LIRPF:
    1. Amortización automática del 3% sobre el mayor de coste de adquisición y valor catastral de la construcción.
    2. Limitación legal del Grupo A (reparaciones + intereses) a los ingresos íntegros.
    """
    rental = RentalIncome(
        property_id="inmueble_1",
        gross_income=Decimal('10000'),
        deductible_expenses=Decimal('2000'),
        expenses_maintenance=Decimal('8000'),
        expenses_mortgage_interest=Decimal('4000'), # Suma Grupo A = 12000 (exceso de 2000)
        adquisicion_construccion_eur=Decimal('150000'), # Amortización = 150000 * 3% = 4500
        catastral_construccion_eur=Decimal('80000'),
        tipo="arrendado",
        reduction_habitual=False
    )
    
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[],
        stock_events=[],
        work=None,
        profile=None,
        rental_income=[rental],
        other_pyg=[],
        business_income=[],
        attributed_income=[],
        region="madrid"
    )
    res = calc.calculate().raw_summary
    # Ingresos = 10000
    # Gastos Grupo A aplicados = min(12000, 10000) = 10000
    # Otros gastos = 2000 + amortización (4500) = 6500
    # Neto = 10000 - 10000 - 6500 = -6500
    assert res["rental_neto"] == Decimal('-6500')
    # Remanente acumulado = 2000
    assert res["remanente_inmobiliario_futuro"] == Decimal('2000')


def test_imputacion_temporal_segundas_residencias():
    """
    Art. 85 LIRPF: Imputación de renta inmobiliaria (1,1% si revisado, 2% si no) ponderado por días.
    """
    rental_revisado = RentalIncome(
        property_id="segunda_residencia",
        gross_income=Decimal('0'),
        deductible_expenses=Decimal('0'),
        valor_catastral=Decimal('120000'),
        valor_catastral_revisado=True,
        dias_a_disposicion=184,
        tipo="imputado"
    )
    
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[],
        stock_events=[],
        work=None,
        profile=None,
        rental_income=[rental_revisado],
        other_pyg=[],
        business_income=[],
        attributed_income=[],
        region="madrid"
    )
    res = calc.calculate().raw_summary
    # Imputación = 120000 * 1.1% * (184/365) = 665.4246...
    expected = (Decimal('120000') * Decimal('0.011')) * (Decimal('184') / Decimal('365'))
    assert abs(res["other_bg"] - expected) < Decimal('0.01')


def test_propiedad_intelectual_creador():
    """
    Art. 17.2.d LIRPF vs Art. 25.4.a LIRPF:
    Los derechos de autor del propio creador se integran en Base General (Rendimientos del Trabajo).
    Si los percibe un tercero (no creador), se integran en Base del Ahorro (RCM).
    """
    div_autor_creador = Dividend(
        date=datetime(2025, 6, 1),
        platform="Planeta",
        asset="EUR",
        isin="",
        gross_eur=Decimal('50000'),
        withholding_foreign_eur=Decimal('0'),
        withholding_spain_eur=Decimal('0'),
        type="intellectual_property",
        is_creator=True
    )
    
    calc_creador = IRPFCalculator(
        dividends=[div_autor_creador],
        crypto_events=[],
        stock_events=[],
        work=None,
        profile=None,
        rental_income=[],
        other_pyg=[],
        business_income=[],
        attributed_income=[],
        region="madrid"
    )
    res_creador = calc_creador.calculate().raw_summary
    # Al ser creador, se debe integrar en Base General (Rendimiento Neto Trabajo) con reducción 30%
    # Bruto = 50000. Reducción 30% = 15000. Neto previo = 35000. Gastos generales = 2000. Neto = 33000.
    assert res_creador["work_neto"] == Decimal('33000')
    assert res_creador["base_general"] == Decimal('33000')
    assert res_creador["base_ahorro"] == Decimal('0')

    # Caso 2: Tercer receptor
    div_autor_tercero = Dividend(
        date=datetime(2025, 6, 1),
        platform="Planeta",
        asset="EUR",
        isin="",
        gross_eur=Decimal('50000'),
        withholding_foreign_eur=Decimal('0'),
        withholding_spain_eur=Decimal('0'),
        type="intellectual_property"
    )
    
    calc_tercero = IRPFCalculator(
        dividends=[div_autor_tercero],
        crypto_events=[],
        stock_events=[],
        work=None,
        profile=None,
        rental_income=[],
        other_pyg=[],
        business_income=[],
        attributed_income=[],
        region="madrid"
    )
    res_tercero = calc_tercero.calculate().raw_summary
    # Al no ser creador, se debe integrar en RCM (Base del Ahorro)
    assert res_tercero["work_neto"] == Decimal('0')
    assert res_tercero["base_general"] == Decimal('0')
    assert res_tercero["base_ahorro"] == Decimal('50000')


def test_exclusion_criptomonedas_wash_sales():
    """
    DGT V1601-22: Exención de la regla de recompra (wash sale) para criptomonedas.
    Las pérdidas de cripto se compensan íntegramente aunque haya recompra rápida.
    """
    # Pérdida en cripto con recompra (is_wash_sale = True)
    crypto_event = _CryptoEvent(
        asset="BTC",
        asset_type="crypto",
        gain_loss_eur=Decimal('-15000'),
        total_sale_eur=Decimal('50000'),
        total_cost_eur=Decimal('65000'),
        is_wash_sale=True
    )
    
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[crypto_event],
        stock_events=[],
        work=None,
        profile=None,
        rental_income=[],
        other_pyg=[],
        business_income=[],
        attributed_income=[],
        region="madrid"
    )
    # Se debe permitir la compensación íntegra de la pérdida de cripto
    res = calc.calculate().raw_summary
    assert res["crypto_gain_loss"] == Decimal('-15000')
    assert res["gpp_neto"] == Decimal('-15000')


def test_exclusion_premios_gravamen_especial():
    """
    DA 33.ª LIRPF: Premios de loterías oficiales sujetos a Gravamen Especial del 20% en fuente
    quedan excluidos de la Base Imponible General.
    """
    premio_loteria = OtherIncome(
        date=datetime(2025, 12, 22),
        description="Gordo de Navidad",
        gain_loss_eur=Decimal('100000'),
        category="premios",
        sujeto_gravamen_especial=True
    )
    
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[],
        stock_events=[],
        work=None,
        profile=None,
        rental_income=[],
        other_pyg=[premio_loteria],
        business_income=[],
        attributed_income=[],
        region="madrid"
    )
    res = calc.calculate().raw_summary
    # Se debe excluir del cálculo general
    assert res["base_general"] == Decimal('0')


def test_prelacion_compensaciones_base_ahorro():
    """
    Art. 49 LIRPF: Prelación jerárquica de compensaciones de la Base del Ahorro.
    1. Compensar arrastres históricos homólogos (misma naturaleza).
    2. Compensación cruzada corriente e histórica limitada al 25% del remanente positivo resultante.
    """
    # Datos:
    # Ejercicio corriente: RCM = +10.000€, GPP = -4.000€
    # Arrastres plurianuales de años anteriores: RCM histórico a compensar = -8.000€
    rcm_corriente = Dividend(
        date=datetime(2025, 6, 1),
        platform="Degiro",
        asset="USDC", # No dust
        isin="",
        gross_eur=Decimal('10000'),
        withholding_foreign_eur=Decimal('0'),
        withholding_spain_eur=Decimal('0')
    )
    gpp_corriente = _StockEvent(
        asset="SAN",
        asset_type="stock",
        gain_loss_eur=Decimal('-4000'),
        total_sale_eur=Decimal('20000'),
        total_cost_eur=Decimal('24000')
    )
    
    calc = IRPFCalculator(
        dividends=[rcm_corriente],
        crypto_events=[],
        stock_events=[gpp_corriente],
        work=None,
        profile=None,
        rental_income=[],
        other_pyg=[],
        business_income=[],
        attributed_income=[],
        carry_forward_rcm_loss_eur=Decimal('8000'), # Arrastre homólogo RCM
        carry_forward_gpp_loss_eur=Decimal('0'),
        region="madrid"
    )
    res = calc.calculate().raw_summary
    
    # Explicación del cálculo legal:
    # 1. RCM del año corriente = +10.000€.
    # 2. Compensamos RCM plurianual homólogo (-8.000€) contra RCM corriente:
    #    RCM neta intermedia = +10.000€ - 8.000€ = +2.000€.
    # 3. Límite cruzado del 25% se determina sobre el remanente positivo de RCM (+2.000€):
    #    Límite = 2.000€ * 25% = 500€.
    # 4. Compensación cruzada de la pérdida corriente de GPP (-4.000€) contra RCM:
    #    Se compensan 500€.
    # 5. Base del Ahorro final = RCM final (+1.500€) + GPP final (0€) = 1.500€.
    # 6. Remanente de pérdida GPP a arrastrar para próximos años = -3.500€.
    
    assert res["base_ahorro"] == Decimal('1500')
    assert res["rcm_neto_reducido"] == Decimal('1500')
    assert res["remanente_gpp_futuro"] == Decimal('-3500')


# ---------------------------------------------------------------------------
# TESTS DE CERTIFICACIÓN DE DEDUCCIONES ESTATALES (PASO 1)
# ---------------------------------------------------------------------------

def test_eficiencia_energetica_limite_base():
    """
    DA 50ª LIRPF: Eficiencia Energética.
    El límite anual elegible debe aplicarse a la BASE de la inversión y no a la deducción.
    - Tipo del 20%: Límite base 5.000€ (deducción máx 1.000€).
    - Inversión 10.000€ -> Base elegible 5.000€ -> Deducción = 5.000 * 20% = 1.000€
    """
    from src.tax_compliance.state.state_rules import StateDeductor
    
    # Caso 1: 20% sobre inversión de 10.000€
    profile = ProfileBuilder.from_dict(dict(
        age=40,
        energy_efficiency_investment_eur=Decimal('10000'),
        energy_efficiency_type=20
    ))
    deductions = StateDeductor.calculate_quota_deductions(profile, Decimal('50000'))
    
    ded_eff = next((d for d in deductions if d.box_id == "ST04"), None)
    assert ded_eff.value == Decimal('1000')


def test_donativos_recurrencia_fidelizacion():
    """
    Art. 68.3 LIRPF: Incremento por fidelización en donativos.
    - Sin fidelización: 80% de los primeros 250€ + 40% del resto.
    - Con fidelización: 80% de los primeros 250€ + 45% del resto.
    Ejemplo: donación de 1.000€ con base de renta alta.
    """
    from src.tax_compliance.state.state_rules import StateDeductor
    
    # Caso 1: Sin fidelización
    profile_normal = ProfileBuilder.from_dict(dict(
        age=40,
        donations_eur=Decimal('1000'),
        donations_fidelized=False
    ))
    # BI = 100.000€ (límite 10% = 10.000€, no aplica tope)
    ded_normal = StateDeductor.calculate_quota_deductions(profile_normal, Decimal('100000'))
    st03_normal = next((d for d in ded_normal if d.box_id == "ST03"), None)
    # 250 * 0.80 + 750 * 0.40 = 200 + 300 = 500
    assert st03_normal.value == Decimal('500')

    # Caso 2: Con fidelización
    profile_fidel = ProfileBuilder.from_dict(dict(
        age=40,
        donations_eur=Decimal('1000'),
        donations_fidelized=True
    ))
    ded_fidel = StateDeductor.calculate_quota_deductions(profile_fidel, Decimal('100000'))
    st03_fidel = next((d for d in ded_fidel if d.box_id == "ST03"), None)
    # 250 * 0.80 + 750 * 0.45 = 200 + 337.5 = 537.5
    assert st03_fidel.value == Decimal('537.5')


def test_alquiler_pre2015_base_maxima_lineal():
    """
    DA 11ª / DA 15ª LIRPF: Alquiler pre-2015.
    La base máxima de deducción de 9.040€ disminuye linealmente en el tramo de BI entre 17.707,20€ y 24.107,20€.
    Ejemplo: BI = 20.907,20€ (exactamente la mitad del tramo, reducción del 50% de la base máxima).
    Base máxima = 9.040 - (3.200 * 1.4125) = 9.040 - 4.520 = 4.520€.
    Deducción = 4.520 * 10.05% = 454.26€.
    """
    from src.tax_compliance.state.state_rules import StateDeductor
    
    profile = ProfileBuilder.from_dict(dict(
        age=40,
        rent_pre2015=True,
        rent_pre2015_paid_eur=Decimal('10000') # Paga más del límite
    ))
    
    # BI = 20907.20 (Tramo intermedio)
    ded = StateDeductor.calculate_quota_deductions(profile, Decimal('20907.20'))
    st_da11 = next((d for d in ded if d.box_id == "ST_DA11"), None)
    assert abs(st_da11.value - Decimal('454.26')) < Decimal('0.01')


def test_differential_deductions_limite_cotizaciones():
    """
    Art. 81 / 81 bis LIRPF: Límite estricto de cotizaciones a la S.S.
    La suma de maternidad y familia numerosa está topada por cotizaciones.
    Gastos de guardería exentos del tope de cotización.
    """
    from src.tax_compliance.state.state_rules import StateDeductor
    
    # Madre trabajadora con 1 hijo < 3 años y gastos de guardería de 600€
    # Cotizaciones a la Seguridad Social = 500€
    profile = ProfileBuilder.from_dict(dict(
        age=30,
        children_under_3=1,
        is_working_mother=True,
        maternity_months={i: Decimal('500') for i in range(1, 6)},
        daycare_expenses_eur=Decimal('600'),
        large_family_category="general", # Familia numerosa (1.200€)
        ss_employee_eur=Decimal('500')
    ))
    
    ded = StateDeductor.calculate_differential_deductions(profile)
    
    # Maternidad (ART81_MAT) -> Topada a 500€
    art81_mat = next((d for d in ded if d.box_id == "ART81_MAT"), None)
    assert art81_mat.value == Decimal('500')
    
    # Familia numerosa (ART81BIS_FNG) -> 500 (límite SS independiente)
    art81bis_fng = next((d for d in ded if d.box_id == "ART81BIS_FNG"), None)
    assert art81bis_fng.value == Decimal('500')
    
    # Gastos guardería (ART81_GUAR) -> Exento de cotizaciones -> Completa 600€
    art81_guar = next((d for d in ded if d.box_id == "ART81_GUAR"), None)
    assert art81_guar.value == Decimal('600')


def test_la_rioja_internet_access_youth():
    """
    La Rioja (RIO_INT): Deducción del 30% en gastos de internet para jóvenes < 36 años,
    máx 150€ anuales, con límite de renta 18.000€ indiv / 36.000€ conj.
    """
    from src.tax_compliance.core.irpf_calculator import IRPFCalculator
    
    # Caso 1: Joven califica y gasta 400€ -> 400 * 0.30 = 120€ (< 150€)
    profile = ProfileBuilder.from_dict(dict(
        age=30,
        internet_access_expenses_eur=Decimal('400'),
        joint_declaration=False
    ))
    work1 = WorkIncome(retribuciones_dinerarias=Decimal('20000'), retenciones=Decimal('0'), gastos_deducibles=Decimal('0'))
    calc = IRPFCalculator(profile=profile, region="la_rioja", work=work1)
    res = calc.calculate().raw_summary
    rio_int = next((d for d in res["applied_deductions"]["regional"] if d.box_id == "RIO_INT"), None)
    assert rio_int.value == Decimal('120')

    # Caso 2: Supera límite de renta individual -> 0 deducciones
    work2 = WorkIncome(retribuciones_dinerarias=Decimal('22000'), retenciones=Decimal('0'), gastos_deducibles=Decimal('0'))
    calc_high = IRPFCalculator(profile=profile, region="la_rioja", work=work2)
    res_high = calc_high.calculate().raw_summary
    assert not any(d.box_id == "RIO_INT" for d in res_high["applied_deductions"]["regional"])


def test_valenciana_medical_expenses():
    """
    Comunidad Valenciana (VAL_MED): Deducción del 30% en gastos de salud bucodental y óptica,
    con límites cruzados de 30.000€ indiv / 32.000€ conj.
    """
    from src.tax_compliance.core.irpf_calculator import IRPFCalculator
    
    # Caso 1: Califica individual -> 300€ dental + 200€ óptica = 500€ * 0.30 = 150€
    profile = ProfileBuilder.from_dict(dict(
        age=40,
        health_dental_expenses_eur=Decimal('300'),
        health_optical_expenses_eur=Decimal('200'),
        joint_declaration=False
    ))
    work = WorkIncome(retribuciones_dinerarias=Decimal('20000'), retenciones=Decimal('0'), gastos_deducibles=Decimal('0'))
    calc = IRPFCalculator(profile=profile, region="valenciana", work=work)
    res = calc.calculate().raw_summary
    val_med = next((d for d in res["applied_deductions"]["regional"] if d.box_id == "VAL_MED"), None)
    assert val_med.value == Decimal('150')


def test_interbloqueo_foral_euskadi_navarra():
    """
    País Vasco y Navarra (Interbloqueo legal foral): El motor debe lanzar
    NotImplementedError ante cualquier intento de cálculo foral.
    """
    import pytest
    from src.tax_compliance.core.irpf_calculator import IRPFCalculator

    with pytest.raises(NotImplementedError, match="El sistema no dispone de soporte para la liquidación del IRPF bajo regímenes forales especiales."):
        IRPFCalculator(region="navarra")

    with pytest.raises(NotImplementedError, match="El sistema no dispone de soporte para la liquidación del IRPF bajo regímenes forales especiales."):
        IRPFCalculator(region="pais_vasco")

    # Mismo test con profile
    profile_vizcaya = ProfileBuilder.from_dict(dict(age=40, region="vizcaya"))
    with pytest.raises(NotImplementedError, match="El sistema no dispone de soporte para la liquidación del IRPF bajo regímenes forales especiales."):
        IRPFCalculator(profile=profile_vizcaya, region="andalucia")


def test_exclusion_cfds_wash_sales():
    """
    Exclusión de contratos por diferencias (CFD): No están sujetos a wash sales al no ser valores homogéneos negociados.
    """
    from src.accounting.wash_sale_scanner import WashSaleScanner
    from src.domain.stock_entities import Trade, TaxEvent
    from datetime import datetime
    
    trades = [
        Trade(date=datetime(2025, 10, 1), platform="eToro", asset="AAPL CFD", isin="US0378331005", ticker="AAPL", asset_type="stock", direction="buy", quantity=Decimal('10'), value_eur=Decimal('1500'), fee_eur=Decimal('0')),
        Trade(date=datetime(2025, 10, 20), platform="eToro", asset="AAPL CFD", isin="US0378331005", ticker="AAPL", asset_type="stock", direction="buy", quantity=Decimal('10'), value_eur=Decimal('1400'), fee_eur=Decimal('0'))
    ]
    
    events = [
        TaxEvent(
            date=datetime(2025, 10, 15), platform="eToro", asset="AAPL CFD", isin="US0378331005", ticker="AAPL", asset_type="stock",
            quantity_sold=Decimal('10'), acquisition_date=datetime(2025, 10, 1),
            acquisition_cost_eur=Decimal('1500'), sale_proceeds_eur=Decimal('1400'),
            buy_fee_eur=Decimal('0'), sell_fee_eur=Decimal('0'), gain_loss_eur=Decimal('-100')
        )
    ]
    
    # 1. Escáner de WashSaleScanner
    scanner = WashSaleScanner(trades)
    scanner.scan(events)
    # Ningún evento debe quedar marcado como wash sale debido a que es un CFD
    assert not any(getattr(te, 'is_wash_sale', False) for te in events)


def test_tolerancia_staking_binance():
    """
    Validar que el lector especialista de Binance tolera de forma estanca fallos de cotización del oráculo
    para operaciones pasivas de Staking/Earn y les asigna coste cero.
    """
    from src.ingestion.binance_reader import BinanceIngestor
    from datetime import datetime
    
    reader = BinanceIngestor()
    # Si intentamos convertir una moneda desconocida como 'STKTOKEN' para una operación de STAKING
    # debe retornar Decimal('0') de forma tolerante sin lanzar excepción
    coste = reader._safe_convert(Decimal('100'), 'STKTOKEN', datetime(2025, 6, 15), op='STAKING')
    assert coste == Decimal('0')


def test_doble_imposicion_con_tme_ahorro():
    """
    Art. 80 LIRPF: El límite por doble imposición internacional es el menor de:
    1) Lo pagado en el extranjero.
    2) El 15% del bruto.
    3) El bruto * Tipo Medio Efectivo (TME) de gravamen del ahorro.
    """
    div = Dividend(
        date=datetime(2025, 6, 15),
        platform="eToro",
        asset="AAPL",
        isin="US0378331005",
        gross_eur=Decimal('1000'),
        withholding_foreign_eur=Decimal('300'), # 30% withholding
        withholding_spain_eur=Decimal('0'),
        country="US",
        type="dividend"
    )
    # Añadimos altos ingresos de trabajo para consumir el mínimo personal y que el ahorro tribute al 19%
    work = WorkIncome(
        retribuciones_dinerarias=Decimal('100000'),
        retenciones=Decimal('30000'),
        gastos_deducibles=Decimal('5000')
    )
    profile = ProfileBuilder.from_dict(dict(age=40))
    
    calc = IRPFCalculator(
        dividends=[div],
        crypto_events=[],
        stock_events=[],
        work=work,
        profile=profile,
        region="madrid"
    )
    res = calc.calculate().raw_summary
    # TME_ahorro = 19%
    # Deducción = min(300, 15% * 1000 = 150, 19% * 1000 = 190) = 150€
    assert res["deduccion_doble_imposicion"] == Decimal('150')


def test_airdrop_hardfork_base_general():
    """
    Airdrops y Hard Forks se consideran ganancias patrimoniales que no derivan de transmisión
    y deben tributar en la Base Imponible General (BIG) a través de other_bg_pos.
    """
    event_airdrop = _CryptoEvent(
        asset="AirdropToken",
        asset_type="crypto",
        gain_loss_eur=Decimal('500'),
        total_sale_eur=Decimal('500'),
        total_cost_eur=Decimal('0')
    )
    event_airdrop.notes = "Binance Airdrop distribution"
    
    profile = ProfileBuilder.from_dict(dict(age=40))
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[event_airdrop],
        stock_events=[],
        profile=profile,
        region="madrid"
    )
    calc.events = [event_airdrop]
    calc.crypto_events = [event_airdrop]
    
    res = calc.calculate().raw_summary
    assert res["other_bg"] == Decimal('500')
    assert res["base_ahorro"] == Decimal('0')


def test_alquiler_habitual_ley_vivienda():
    """
    Art. 23.2 LIRPF (Ley de Vivienda, 26 de mayo de 2023):
    - Contratos antes de 26/05/2023: 60% reducción.
    - Contratos desde 26/05/2023 por defecto: 50% reducción.
    - Rehabilitado: 60% reducción.
    - Zona tensionada + primer alquiler joven: 70% reducción.
    - Zona tensionada + reducción del 5% renta: 90% reducción.
    """
    # 1. Antes de la Ley de Vivienda
    r_old = RentalIncome(
        property_id="P1",
        gross_income=Decimal('10000'),
        deductible_expenses=Decimal('2000'),
        expenses_maintenance=Decimal('0'),
        tipo="arrendado",
        valor_catastral=Decimal('0'),
        reduction_habitual=True,
        contract_date="2023-05-15"
    )
    # Neto = 10000 - 2000 = 8000
    # Reducción 60% -> Neto tributable = 3200
    calc_old = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], rental_income=[r_old], region="madrid")
    res_old = calc_old.calculate().raw_summary
    assert res_old["rental_neto"] == Decimal('3200')

    # 2. Después de la Ley de Vivienda por defecto
    r_new_def = RentalIncome(
        property_id="P2",
        gross_income=Decimal('10000'),
        deductible_expenses=Decimal('2000'),
        expenses_maintenance=Decimal('0'),
        tipo="arrendado",
        valor_catastral=Decimal('0'),
        reduction_habitual=True,
        contract_date="2023-06-01"
    )
    # Neto = 8000. Reducción 50% -> Neto tributable = 4000
    calc_new_def = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], rental_income=[r_new_def], region="madrid")
    res_new_def = calc_new_def.calculate().raw_summary
    assert res_new_def["rental_neto"] == Decimal('4000')

    # 3. Después de la Ley de Vivienda, Zona tensionada + Reducción 5% renta
    r_new_90 = RentalIncome(
        property_id="P3",
        gross_income=Decimal('10000'),
        deductible_expenses=Decimal('2000'),
        expenses_maintenance=Decimal('0'),
        tipo="arrendado",
        valor_catastral=Decimal('0'),
        reduction_habitual=True,
        contract_date="2023-06-01",
        zona_tensionada=True,
        reduccion_renta_tensionada_5_pct=True
    )
    # Neto = 8000. Reducción 90% -> Neto tributable = 800
    calc_new_90 = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], rental_income=[r_new_90], region="madrid")
    res_new_90 = calc_new_90.calculate().raw_summary
    assert res_new_90["rental_neto"] == Decimal('800')


def test_cobro_aplazado_criterio_caja():
    """
    Art. 14.2.d LIRPF: Operaciones a plazos.
    Se imputa proporcionalmente a los cobros exigibles en el año.
    """
    pyg = OtherIncome(
        date=datetime(2025, 10, 1),
        description="Venta de cuadro",
        gain_loss_eur=Decimal('10000'),
        category="otros",
        is_deferred_payment=True,
        total_sale_value_eur=Decimal('50000'),
        current_year_due_payments_eur=Decimal('10000') # 20% cobrado
    )
    
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[],
        stock_events=[],
        other_pyg=[pyg],
        region="madrid"
    )
    res = calc.calculate().raw_summary
    # Ganancia patrimonial computada en el año debe ser el 20% de 10000 = 2000€
    assert res["base_ahorro"] == Decimal('2000')


def test_murcia_guarderia_incompatibilidad():
    """
    Verifica que la deducción autonómica por gastos de guardería en Murcia (MUR02)
    se minora correctamente por el incremento estatal aplicado (ART81_GUAR).
    """
    from src.domain.fiscal_entities import WorkIncome
    profile = ProfileBuilder.from_dict(dict(
        age=30,
        region="murcia",
        children_under_3=1,
        is_working_mother=True,
        daycare_expenses_eur=Decimal('1500'),
        ss_employee_eur=Decimal('2000')
    ))
    from src.domain.fiscal_entities import WorkIncome
    work = WorkIncome(
        retribuciones_dinerarias=Decimal('20000'),
        retenciones=Decimal('1000'),
        gastos_deducibles=Decimal('500')
    )
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[],
        stock_events=[],
        work=work,
        profile=profile,
        region="murcia"
    )
    res = calc.calculate().raw_summary
    
    # 1. Deducción por maternidad estatal (incremento de guardería):
    # min(1500, 1000 * 1) = 1000€
    diff_deds = res["applied_deductions"]["differential"]
    daycare_estatal = next((d.value for d in diff_deds if d.box_id == "ART81_GUAR"), None)
    assert daycare_estatal == Decimal('1000')
    
    # 2. Deducción regional de Murcia (MUR02):
    # Base minorada: 1500 - 1000 = 500€
    # MUR02 = min(500 * 0.20, 1000 * 1) = 100€
    reg_deds = res["applied_deductions"]["regional"]
    mur_guarderia = next((d.value for d in reg_deds if d.box_id == "MUR02"), None)
    assert mur_guarderia == Decimal('100')


def test_alquiler_transitorio_vs_regional_solapamiento():
    """
    Verifica que la base de la deducción por alquiler regional se minora por la base
    efectivamente deducida en el estado bajo el régimen transitorio (DA 11ª).
    """
    profile = ProfileBuilder.from_dict(dict(
        age=30, # Joven < 35 para Madrid
        region="madrid",
        is_rent_habitual=True,
        rent_paid_annual_eur=Decimal('10000'),
        rent_pre2015=True,
        rent_pre2015_paid_eur=Decimal('9000'),
        ss_employee_eur=Decimal('1000')
    ))
    # Renta del trabajo alta para que BI no esté reducida
    work = WorkIncome(
        retribuciones_dinerarias=Decimal('22000'),
        retenciones=Decimal('1000'),
        gastos_deducibles=Decimal('500')
    )
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[],
        stock_events=[],
        work=work,
        profile=profile,
        region="madrid"
    )
    res = calc.calculate().raw_summary
    
    # BI = 14500 (menor que 17707.20), por lo que base máxima estatal es 9040€
    # Base estatal aplicada = min(9000, 9040) = 9000€
    # Base regional restante = max(10000 - 9000, 0) = 1000€
    # Deducción autonómica Madrid (MAD01): 20% de base regional (1000€) = 200€
    reg_deds = res["applied_deductions"]["regional"]
    mad_alquiler = next((d.value for d in reg_deds if d.box_id == "MAD01"), None)
    assert mad_alquiler == Decimal('200')


def test_eficiencia_energetica_limite_plurianual():
    """
    Verifica que la deducción por obras de eficiencia energética (ST04)
    minora su límite por bases aplicadas en ejercicios anteriores.
    """
    profile = ProfileBuilder.from_dict(dict(
        age=40,
        energy_efficiency_investment_eur=Decimal('4000'),
        energy_efficiency_type=20, # Límite acumulado de 5000€
        energy_efficiency_prior_years_base_eur=Decimal('3500') # Base ya consumida
    ))
    from src.domain.fiscal_entities import WorkIncome
    work = WorkIncome(retribuciones_dinerarias=Decimal('50000'), retenciones=Decimal('0'), gastos_deducibles=Decimal('0'))
    calc = IRPFCalculator(
        dividends=[],
        crypto_events=[],
        stock_events=[],
        profile=profile,
        region="madrid",
        work=work
    )
    res = calc.calculate().raw_summary
    
    # Límite restante: 5000 - 3500 = 1500
    # Base deducción: min(4000, 1500) = 1500
    # Deducción ST04 (20%): 1500 * 0.20 = 300
    state_deds = res["applied_deductions"]["state"]
    eficiencia = next((d.value for d in state_deds if d.box_id == "ST04"), None)
    assert eficiencia is not None, "Deducción ST04 no generada"
    assert eficiencia == Decimal('300')


def test_mortgage_pre2013_date_validation():
    """
    DA 18ª: Valida fecha de adquisición de hipoteca pre-2013.
    """
    work = WorkIncome(retribuciones_dinerarias=Decimal('20000'), retenciones=Decimal('0'), gastos_deducibles=Decimal('0'))
    # Adquisición posterior al 2013-01-01 -> No aplica deducción
    profile_post = ProfileBuilder.from_dict(dict(
        age=30,
        mortgage_pre2013=True,
        mortgage_paid_eur=Decimal('5000'),
        mortgage_acquisition_date="2013-05-15"
    ))
    calc_post = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=profile_post, work=work)
    res_post = calc_post.calculate().raw_summary
    state_deds_post = res_post["applied_deductions"]["state"]
    assert not any(d.box_id == "ST_DA9" for d in state_deds_post)

    # Adquisición anterior al 2013-01-01 -> Sí aplica
    profile_pre = ProfileBuilder.from_dict(dict(
        age=30,
        mortgage_pre2013=True,
        mortgage_paid_eur=Decimal('5000'),
        mortgage_acquisition_date="2012-10-10"
    ))
    calc_pre = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=profile_pre, work=work)
    res_pre = calc_pre.calculate().raw_summary
    state_deds_pre = res_pre["applied_deductions"]["state"]
    st_da9 = next((d for d in state_deds_pre if d.box_id == "ST_DA9"), None)
    assert st_da9.value == Decimal('375') # 5000 * 0.075


def test_startup_investment_rules():
    """
    Art. 68.1: Verifica límites de participación y antigüedad para deducción de startups.
    """
    # Participación > 40% -> No aplica
    profile_pct = ProfileBuilder.from_dict(dict(
        age=30,
        startup_investment_eur=Decimal('10000'),
        startup_ownership_pct=Decimal('0.45'),
        startup_years_since_constitution=2,
        startup_is_emerging=False
    ))
    from src.domain.fiscal_entities import WorkIncome
    work = WorkIncome(retribuciones_dinerarias=Decimal('50000'), retenciones=Decimal('0'), gastos_deducibles=Decimal('0'))
    calc_pct = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=profile_pct, work=work)
    res_pct = calc_pct.calculate().raw_summary
    st01_pct = next((d for d in res_pct["applied_deductions"]["state"] if d.box_id == "ST01"), None)
    assert st01_pct is None, "ST01 no debe aplicar si pct > 40%"

    # Antigüedad > 5 (y no emergente) -> No aplica
    profile_age = ProfileBuilder.from_dict(dict(
        age=30,
        startup_investment_eur=Decimal('10000'),
        startup_ownership_pct=Decimal('0.10'),
        startup_years_since_constitution=6,
        startup_is_emerging=False
    ))
    calc_age = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=profile_age, work=work)
    res_age = calc_age.calculate().raw_summary
    st01_age = next((d for d in res_age["applied_deductions"]["state"] if d.box_id == "ST01"), None)
    assert st01_age is None, "ST01 no debe aplicar si antiguedad > 5"

    # Cumple emergente (max 7) -> Aplica 50%
    profile_emerg = ProfileBuilder.from_dict(dict(
        age=30,
        startup_investment_eur=Decimal('10000'),
        startup_ownership_pct=Decimal('0.10'),
        startup_years_since_constitution=6,
        startup_is_emerging=True
    ))
    calc_emerg = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=profile_emerg, work=work)
    res_emerg = calc_emerg.calculate().raw_summary
    st01_emerg = next((d for d in res_emerg["applied_deductions"]["state"] if d.box_id == "ST01"), None)
    assert st01_emerg is not None, "Deducción ST01 no generada"
    assert st01_emerg.value == Decimal('5000') # 10000 * 50%


def test_donations_new_15_percent_limit():
    """
    Art. 68.3: Verifica el nuevo límite incrementado al 15% de la Base Imponible.
    """
    work = WorkIncome(
        retribuciones_dinerarias=Decimal('30000'),
        retenciones=Decimal('0'),
        gastos_deducibles=Decimal('0')
    )
    profile = ProfileBuilder.from_dict(dict(
        age=30,
        donations_eur=Decimal('2000'),
        donations_fidelized=True
    ))
    calc = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], work=work, profile=profile)
    res = calc.calculate().raw_summary
    
    # BI = 28000 (30000 - 2000 gastos genéricos de trabajo, reducción Art 20 = 0)
    # Límite base = 15% de 28000 = 4200 (por lo que la base elegible es 2000 completa)
    # Deducción: 250 * 80% + (2000 - 250) * 45% = 200 + 1750 * 0.45 = 200 + 787.50 = 987.50
    st03 = next((d for d in res["applied_deductions"]["state"] if d.box_id == "ST03"), None)
    assert st03.value == Decimal('987.50')


def test_electric_vehicles_da58():
    """
    DA 58ª: Verifica deducción de vehículos eléctricos y puntos de recarga.
    """
    profile = ProfileBuilder.from_dict(dict(
        age=30,
        electric_vehicle_investment_eur=Decimal('25000'),
        electric_vehicle_subsidies_eur=Decimal('3000'),
        charging_point_investment_eur=Decimal('5000'),
        charging_point_is_electronic_payment=True
    ))
    from src.domain.fiscal_entities import WorkIncome
    work = WorkIncome(retribuciones_dinerarias=Decimal('50000'), retenciones=Decimal('0'), gastos_deducibles=Decimal('0'))
    calc = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=profile, work=work)
    res = calc.calculate().raw_summary
    state_deds = res["applied_deductions"]["state"]

    veh = next((d for d in state_deds if d.box_id == "ST_VEH"), None)
    assert veh is not None, "Deducción ST_VEH no generada"
    # Base: min(25000 - 3000, 20000) = 20000. 15% de 20000 = 3000
    assert veh.value == Decimal('3000')

    rec = next((d for d in state_deds if d.box_id == "ST_REC"), None)
    assert rec is not None, "Deducción ST_REC no generada"
    # Base: min(5000, 4000) = 4000. 15% de 4000 = 600
    assert rec.value == Decimal('600')


def test_differential_deductions_monthly_precision():
    """
    Art. 81: Verifica cálculo mensual de maternidad y exención por prestación.
    """
    # Cómputo mensualizado con cotizaciones limitadas
    profile_limit = ProfileBuilder.from_dict(dict(
        age=30,
        children_under_3=1,
        is_working_mother=True,
        maternity_months={
            1: Decimal('50'),
            2: Decimal('120'),
            3: Decimal('80')
        }
    ))
    calc_limit = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=profile_limit)
    res_limit = calc_limit.calculate().raw_summary
    diff_deds_limit = res_limit["applied_deductions"]["differential"]
    
    art81_mat = next((d for d in diff_deds_limit if d.box_id == "ART81_MAT"), None)
    assert art81_mat is not None, "Deducción ART81_MAT no generada"
    # Mes 1: min(100, 50) = 50
    # Mes 2: min(100, 120) = 100
    # Mes 3: min(100, 80) = 80
    # Total = 50 + 100 + 80 = 230

    # Cómputo mensualizado exento de cotizaciones (exempt_from_ss_limit=True)
    profile_exempt = ProfileBuilder.from_dict(dict(
        age=30,
        children_under_3=1,
        is_working_mother=True,
        exempt_from_ss_limit=True,
        maternity_months={1: Decimal('0'), 2: Decimal('0'), 3: Decimal('0')}
    ))
    calc_exempt = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=profile_exempt)
    res_exempt = calc_exempt.calculate().raw_summary
    diff_deds_exempt = res_exempt["applied_deductions"]["differential"]
    art81_mat_exempt = next((d for d in diff_deds_exempt if d.box_id == "ART81_MAT"), None)
    assert art81_mat_exempt is not None, "Deducción ART81_MAT no generada"
    # Total sin límite = 3 meses * 100 = 300
    assert art81_mat_exempt.value == Decimal('300')


def test_minimos_estatales_2025():
    """
    Certificar que los mínimos estatales de Renta 2025 son calculados
    con precisión centesimal por defecto.
    """
    # Caso 1: Contribuyente general de 40 años, sin descendientes ni discapacidad
    p1 = ProfileBuilder.from_dict(dict(age=40, disability_grade=0))
    calc1 = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=p1)
    assert calc1._compute_minimo_total(regional=False) == Decimal('5550')

    # Caso 2: Mayor de 65 años (67)
    p2 = ProfileBuilder.from_dict(dict(age=67, disability_grade=0))
    calc2 = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=p2)
    assert calc2._compute_minimo_total(regional=False) == Decimal('6700')  # 5550 + 1150

    # Caso 3: Mayor de 75 años (76)
    p3 = ProfileBuilder.from_dict(dict(age=76, disability_grade=0))
    calc3 = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=p3)
    assert calc3._compute_minimo_total(regional=False) == Decimal('8100')  # 5550 + 1150 + 1400


def test_minimo_autonomico_madrid_2025():
    """
    Certificar los mínimos autonómicos deflactados de la Comunidad de Madrid 2025.
    """
    p = ProfileBuilder.from_dict(dict(
        age=40,
        region="madrid",
        descendants_count=1,
        children_under_3=1,
        disability_grade=0
    ))
    calc = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=p)
    # Mínimo personal Madrid (5956.65) + 1º descendiente (2575.85) + menor de 3 (3005.16) = 11537.66
    assert calc._compute_minimo_total(regional=True) == Decimal('11537.66')


def test_minimo_autonomico_galicia_2025():
    """
    Certificar los mínimos autonómicos de Galicia para 2025.
    """
    p = ProfileBuilder.from_dict(dict(
        age=40,
        region="galicia",
        descendants_count=1,
        children_under_3=1,
        disability_grade=0
    ))
    calc = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=p)
    # Galicia (5789) + 1º desc (2503) + menor de 3 (2920) = 11212
    assert calc._compute_minimo_total(regional=True) == Decimal('11212')


def test_minimo_autonomico_baleares_2025():
    """
    Certificar los mínimos autonómicos de Illes Balears para 2025.
    """
    p = ProfileBuilder.from_dict(dict(
        age=40,
        region="baleares",
        descendants_count=2,
        children_under_3=0,
        disability_grade=0
    ))
    calc = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=p)
    # Balears (5790) + 1º desc (2510) + 2º desc (2820) = 11120
    assert calc._compute_minimo_total(regional=True) == Decimal('11120')


def test_minimo_autonomico_valenciana_2025():
    """
    Certificar los mínimos autonómicos de la Comunitat Valenciana para 2025.
    """
    p = ProfileBuilder.from_dict(dict(
        age=40,
        region="valenciana",
        descendants_count=1,
        children_under_3=1,
        disability_grade=0
    ))
    calc = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=p)
    # Valenciana (6105) + 1º desc (2640) + menor de 3 (3080) = 11825
    assert calc._compute_minimo_total(regional=True) == Decimal('11825')


def test_minimo_autonomico_la_rioja_2025():
    """
    Certificar los mínimos autonómicos de La Rioja para 2025 (estatales).
    """
    p = ProfileBuilder.from_dict(dict(
        age=40,
        region="la_rioja",
        descendants_count=0,
        disability_grade=70,
        disability_mobility_reduced=True
    ))
    calc = IRPFCalculator(dividends=[], crypto_events=[], stock_events=[], profile=p)
    # Personal Estatal (5606) + Discapacidad Rioja >=65% (9900) + Ayuda/Movilidad Rioja (3300) = 18806
    assert calc._compute_minimo_total(regional=True) == Decimal('18806')




