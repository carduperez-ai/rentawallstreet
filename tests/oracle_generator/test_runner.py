from __future__ import annotations
from src.ingestion.profile_builder import ProfileBuilder
"""
IRPF Oracle Test Runner + Fiscal Auditor
Puente entre los casos JSON y el motor IRPFCalculator, más un auditor que
re-deriva cada cálculo intermedio desde la normativa LIRPF 2025.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.tax_compliance.core.irpf_calculator import IRPFCalculator
from src.domain.fiscal_entities import Dividend, WorkIncome, TaxpayerProfile
from tests.oracle_generator.generate_test_suite import (
    generate_salary_thresholds, generate_family_cases, generate_deduction_cases,
)

_TOLERANCE = Decimal('0.02')
_ZERO = Decimal('0')
_JSON_PATH = os.path.join(os.path.dirname(__file__), 'irpf_oracle_tests.json')


# ── Duck-typed TaxEvent stub ─────────────────────────────────────────────────

@dataclass
class _TaxEventStub:
    """Satisface la interfaz de duck typing que usa IRPFCalculator."""
    asset: str
    asset_type: str        # 'stock' | 'crypto'
    gain_loss_eur: Decimal
    total_sale_eur: Decimal
    total_cost_eur: Decimal
    platform: str = "Oracle"
    is_wash_sale: bool = False
    isin: str = ""


# ── Result / Audit data classes ──────────────────────────────────────────────

@dataclass
class RunResult:
    case_name: str
    category: str
    input_dict: Dict[str, Any]
    expected: Dict[str, float]     # de JSON "expected_results"
    calculated: Dict[str, Any]     # de IRPFCalculator.calculate().raw_summary
    error: Optional[str] = None
    status: str = "pending"


@dataclass
class AuditFinding:
    rule_id: str
    article: str
    description: str
    expected: Optional[Decimal]
    actual: Optional[Decimal]
    passed: bool
    severity: str                  # "ERROR" | "WARNING" | "INFO"


@dataclass
class AuditReport:
    case_name: str
    passed_count: int
    failed_count: int
    findings: List[AuditFinding] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.failed_count == 0


# ── Utilidades internas ──────────────────────────────────────────────────────

def _d(v, default='0') -> Decimal:
    """Convierte cualquier valor escalar a Decimal de forma segura."""
    if v is None or v == '' or v is False:
        return Decimal(default)
    if v is True:
        return Decimal('1')
    return Decimal(str(v))


def _append(findings: list, rule_id: str, article: str, description: str,
            expected: Optional[Decimal], actual: Optional[Decimal],
            passed: bool, severity: str = 'ERROR') -> None:
    findings.append(AuditFinding(
        rule_id=rule_id, article=article, description=description,
        expected=expected, actual=actual, passed=passed, severity=severity,
    ))


# ── Builders: JSON dict → domain objects ────────────────────────────────────

def _build_work_income(inp: dict) -> Optional[WorkIncome]:
    """Mapea claves del perfil JSON a WorkIncome. Acepta gross_income o salary."""
    if 'gross_income' not in inp and 'salary' not in inp:
        return None
    return WorkIncome(
        retribuciones_dinerarias=_d(inp.get('gross_income', inp.get('salary', 0))),
        retenciones=_d(inp.get('withholdings_paid', inp.get('withholdings', 0))),
        gastos_deducibles=_d(inp.get('ss_employee', inp.get('social_security', 0))),
        cuotas_sindicales_eur=_d(inp.get('cuotas_sindicales', 0)),
        gastos_defensa_juridica_eur=_d(inp.get('legal_defense', 0)),
        professional_college_eur=_d(inp.get('professional_college', 0)),
        geographic_mobility=bool(inp.get('geo_mobility', False)),
    )


def _build_profile(inp: dict) -> Optional[TaxpayerProfile]:
    """Mapea las 40+ claves del perfil JSON a TaxpayerProfile."""
    if 'age' not in inp:
        return None
    marital = inp.get('marital_status', 'single')
    family_type = inp.get('family_type', 'none')
    large_cat = (
        'general' if family_type == 'large_general'
        else ('special' if family_type == 'large_special' else 'none')
    )
    return ProfileBuilder.from_dict(dict(
        age=int(inp.get('age', 30)),
        disability_grade=int(inp.get('disability', 0)),
        is_victim_violence_gender_or_terrorism=bool(inp.get('is_victim', False)),
        is_married=(marital == 'married'),
        joint_declaration=bool(inp.get('joint_declaration', False)),
        spouse_income_eur=_d(inp.get('spouse_income', 0)),
        spouse_ss_eur=_d(inp.get('spouse_ss', inp.get('spouse_ss_eur', 0))),
        spouse_retenciones_eur=_d(inp.get('spouse_retenciones', inp.get('spouse_retenciones_eur', 0))),
        alimonty_ex_spouse_eur=_d(inp.get('alimonty', 0)),
        child_support_eur=_d(inp.get('child_support', 0)),
        rent_paid_annual_eur=_d(inp.get('rent_paid', 0)),
        is_rent_habitual=bool(inp.get('is_rent_habitual', False)),
        descendants_count=int(inp.get('descendants', 0)),
        extra_education_expenses_eur=_d(inp.get('edu_expenses', 0)),
        is_large_family=(family_type in ('large_general', 'large_special')),
        large_family_category=large_cat,
        is_monoparental=bool(inp.get('is_monoparental', False)),
        single_parent_2_children=bool(inp.get('single_parent_2_children', False)),
        birth_count_current_year=int(inp.get('birth_count', 0)),
        custody_shared=bool(inp.get('custody_shared', False)),
        children_under_3=int(inp.get('children_under_3', 0)),
        is_working_mother=bool(inp.get('is_working_mother', False)),
        daycare_expenses_eur=_d(inp.get('daycare_expenses', 0)),
        children_disabled_33_65=int(inp.get('children_disabled_33_65', 0)),
        children_disabled_over65=int(inp.get('children_disabled_over65', 0)),
        disability_mobility_reduced=bool(inp.get('disability_mobility_reduced', False)),
        disability_needs_help=bool(inp.get('disability_needs_help', False)),
        spouse_disability_grade=int(inp.get('spouse_disability', 0)),
        ascendants_over65=int(inp.get('ascendants_over65', 0)),
        ascendants_disabled_count=int(inp.get('ascendants_disabled', 0)),
        pension_individual_eur=_d(inp.get('pension_plan', 0)),
        pension_empresa_eur=_d(inp.get('pension_empresa', 0)),
        pension_spouse_eur=_d(inp.get('pension_spouse', 0)),
        spouse_pension_individual_eur=_d(inp.get('spouse_pension_individual', inp.get('spouse_pension_plan', 0))),
        spouse_pension_empresa_eur=_d(inp.get('spouse_pension_empresa', 0)),
        startup_investment_eur=_d(inp.get('startup_investment', 0)),
        donations_eur=_d(inp.get('donations', 0)),
        energy_efficiency_investment_eur=_d(inp.get('energy_inv', 0)),
        energy_efficiency_type=int(inp.get('energy_type', 0)),
        mortgage_pre2013=bool(inp.get('mortgage_pre2013', False)),
        mortgage_paid_eur=_d(inp.get('mortgage_paid', 0)),
        rent_pre2015=bool(inp.get('rent_pre2015', False)),
        rent_pre2015_paid_eur=_d(inp.get('rent_pre2015_paid', 0)),
        political_party_eur=_d(inp.get('political_party', 0)),
        ceuta_melilla_income=bool(inp.get('ceuta_melilla_income', False)),
        is_celiac=bool(inp.get('is_celiac', False)),
        is_protected_housing=bool(inp.get('is_protected_housing', False)),
        vet_expenses_eur=_d(inp.get('vet_expenses', 0)),
        gym_expenses_eur=_d(inp.get('gym_expenses', 0)),
        legal_defense_expenses_eur=_d(inp.get('legal_defense_expenses', 0)),
    ))


def _build_dividends(inp: dict) -> List[Dividend]:
    """Convierte inp['dividends'] en objetos Dividend."""
    fiscal_year = int(inp.get('fiscal_year', 2025))
    result = []
    for i, d in enumerate(inp.get('dividends', [])):
        result.append(Dividend(
            date=datetime(fiscal_year, 6, 1),
            platform=str(d.get('platform', 'Oracle')),
            asset=str(d.get('asset', f'DIV_{i}')),
            isin=str(d.get('isin', '')),
            gross_eur=_d(d.get('amount', d.get('gross_eur', 0))),
            withholding_foreign_eur=_d(d.get('withholding_foreign', d.get('withholding_foreign_eur', 0))),
            withholding_spain_eur=_d(d.get('withholding', d.get('withholding_spain', d.get('withholding_spain_eur', 0)))),
            type=str(d.get('type', 'dividend')),
        ))
    return result


def _build_events(inp: dict) -> Tuple[List[_TaxEventStub], List[_TaxEventStub]]:
    """Convierte inp['tax_events'] en stubs de bolsa y cripto."""
    stock_stubs: List[_TaxEventStub] = []
    crypto_stubs: List[_TaxEventStub] = []
    for i, ev in enumerate(inp.get('tax_events', [])):
        buy = _d(ev.get('buy_value', ev.get('total_cost_eur', 0)))
        sell = _d(ev.get('sell_value', ev.get('total_sale_eur', 0)))
        gain_loss = _d(ev.get('gain_loss_eur', sell - buy))
        if sell == _ZERO and buy == _ZERO and gain_loss != _ZERO:
            sell = gain_loss
        stub = _TaxEventStub(
            asset=str(ev.get('asset', f'ASSET_{i}')),
            asset_type=str(ev.get('type', ev.get('asset_type', 'stock'))),
            gain_loss_eur=gain_loss,
            total_sale_eur=sell,
            total_cost_eur=buy,
            platform=str(ev.get('platform', 'Oracle')),
            is_wash_sale=bool(ev.get('is_wash_sale', False)),
            isin=str(ev.get('isin', '')),
        )
        if ev.get('type') == 'crypto' or ev.get('asset_type') == 'crypto':
            crypto_stubs.append(stub)
        else:
            stock_stubs.append(stub)
    return stock_stubs, crypto_stubs


# ── Public API: run_calculation ──────────────────────────────────────────────

def run_calculation(cases: Optional[List[dict]] = None) -> List[RunResult]:
    """
    Carga casos del generador + JSON oracle, ejecuta IRPFCalculator para cada uno.
    Si cases es None: fusiona los tres generadores con irpf_oracle_tests.json,
    deduplicando por nombre.
    """
    if cases is None:
        all_cases: List[dict] = []
        seen: set = set()
        # JSON oracle tiene prioridad: contiene datos reales AEAT
        if os.path.exists(_JSON_PATH):
            with open(_JSON_PATH, encoding='utf-8') as f:
                for c in json.load(f):
                    if c['name'] not in seen:
                        all_cases.append(c)
                        seen.add(c['name'])
        # Generadores añaden casos sintéticos no presentes en el JSON
        for c in (generate_salary_thresholds()
                  + generate_family_cases()
                  + generate_deduction_cases()):
            if c['name'] not in seen:
                all_cases.append(c)
                seen.add(c['name'])
        cases = all_cases

    results: List[RunResult] = []
    for case in cases:
        inp = dict(case['input'])
        inp['__case_name'] = case['name']
        try:
            work = _build_work_income(inp)
            profile = _build_profile(inp)
            dividends = _build_dividends(inp)
            stock_events, crypto_events = _build_events(inp)
            calc = IRPFCalculator(
                work=work,
                profile=profile,
                dividends=dividends,
                stock_events=stock_events,
                crypto_events=crypto_events,
                region=inp.get('region', 'andalucia'),
            )
            calculated = calc.calculate().raw_summary
            error = None
        except Exception as e:
            calculated = {}
            error = str(e)
        results.append(RunResult(
            case_name=case['name'],
            category=case.get('category', ''),
            input_dict=inp,
            expected=case.get('expected_results', {}),
            calculated=calculated,
            error=error,
            status=case.get('status', 'pending'),
        ))
    return results


# ── Auditores parciales (un grupo por artículo) ──────────────────────────────

def _check_art19(inp: dict, result: dict, findings: list) -> None:
    """Art. 19 LIRPF — Gastos deducibles del trabajo."""
    cuotas = _d(inp.get('cuotas_sindicales', 0))
    legal_def_inp = _d(inp.get('legal_defense', 0))
    prof_col_inp = _d(inp.get('professional_college', 0))
    legal_def = min(legal_def_inp, Decimal('300'))
    prof_col = min(prof_col_inp, Decimal('500'))
    gastos_f = Decimal('4000') if bool(inp.get('geo_mobility', False)) else Decimal('2000')

    # Verificar gastos fijos Art. 19.2.f en resultado
    expected_work_gastos = gastos_f + cuotas + legal_def + prof_col
    actual_work_gastos = _d(result.get('work_gastos', _ZERO))
    passed = abs(actual_work_gastos - expected_work_gastos) <= _TOLERANCE
    _append(findings, 'ART19_GASTOS_F', 'Art. 19.2.f LIRPF',
            f'gastos fijos {"4000" if gastos_f == Decimal("4000") else "2000"}€ + cuotas/caps',
            expected_work_gastos, actual_work_gastos, passed)

    # Informar caps aplicados cuando el input los supera
    if legal_def_inp > Decimal('300'):
        _append(findings, 'ART19_DEFENSA_CAP', 'Art. 19.2.e LIRPF',
                f'Defensa jurídica capped: input={legal_def_inp}€ → aplicado={legal_def}€',
                legal_def, legal_def, True, 'INFO')
    if prof_col_inp > Decimal('500'):
        _append(findings, 'ART19_COLEGIO_CAP', 'Art. 19.2.d LIRPF',
                f'Colegio profesional capped: input={prof_col_inp}€ → aplicado={prof_col}€',
                prof_col, prof_col, True, 'INFO')


def _check_art20(inp: dict, result: dict, findings: list) -> None:
    """Art. 20 LIRPF 2025 — Reducción por rendimientos del trabajo."""
    is_joint = inp.get('joint_declaration', False)
    is_mono = inp.get('is_monoparental', False)
    is_married_joint = is_joint and not is_mono
    
    # Calcular para Cónyuge 1 (Declarante principal)
    ss_s1 = _d(inp.get('ss_employee', 0))
    gross_s1 = _d(inp.get('gross_income', inp.get('salary', 0)))
    rnt_art20_s1 = gross_s1 - ss_s1
    
    # Otras rentas
    otras_rentas = (
        _d(result.get('base_ahorro', _ZERO))
        + max(_d(result.get('rental_neto', _ZERO)), _ZERO)
        + max(_d(result.get('other_bg', _ZERO)), _ZERO)
    )
    
    if is_married_joint:
        # En tributación conjunta matrimonial, las magnitudes se acumulan y los límites/gastos del Art 19 y 20 se aplican de forma global única
        gross_s2 = _d(inp.get('spouse_income', inp.get('spouse_income_eur', 0)))
        ss_s2 = _d(inp.get('spouse_ss', inp.get('spouse_ss_eur', 0)))
        rnt_art20_comb = rnt_art20_s1 + (gross_s2 - ss_s2)
        
        if otras_rentas > Decimal('6500'):
            expected_red = _ZERO
        elif rnt_art20_comb <= Decimal('14852'):
            expected_red = Decimal('7302')
        elif rnt_art20_comb <= Decimal('17673.52'):
            expected_red = max(Decimal('7302') - Decimal('1.75') * (rnt_art20_comb - Decimal('14852')), _ZERO)
        elif rnt_art20_comb <= Decimal('19747.50'):
            expected_red = max(Decimal('2364.34') - Decimal('1.14') * (rnt_art20_comb - Decimal('17673.52')), _ZERO)
        else:
            expected_red = _ZERO
        tramo = 'JOINT'
    else:
        # Individual o monoparental
        if otras_rentas > Decimal('6500'):
            expected_red = _ZERO
        elif rnt_art20_s1 <= Decimal('14852'):
            expected_red = Decimal('7302')
        elif rnt_art20_s1 <= Decimal('17673.52'):
            expected_red = max(Decimal('7302') - Decimal('1.75') * (rnt_art20_s1 - Decimal('14852')), _ZERO)
        elif rnt_art20_s1 <= Decimal('19747.50'):
            expected_red = max(Decimal('2364.34') - Decimal('1.14') * (rnt_art20_s1 - Decimal('17673.52')), _ZERO)
        else:
            expected_red = _ZERO
        tramo = '1' if rnt_art20_s1 <= Decimal('14852') else ('2' if rnt_art20_s1 <= Decimal('17673.52') else ('3' if rnt_art20_s1 <= Decimal('19747.50') else '4'))

    rnt_trabajo = _d(result.get('rendimiento_neto_trabajo', _ZERO))
    work_neto = _d(result.get('work_neto', _ZERO))

    if work_neto == _ZERO:
        # No podemos derivar la reducción exacta cuando el resultado se florea a 0
        _append(findings, f'ART20_REDUCCION_TRAMO{tramo}', 'Art. 20 LIRPF 2025',
                f'rnt_art20={rnt_art20_s1:.2f}€ tramo {tramo}: reduccion≥{expected_red:.2f}€ (work_neto=0, no derivable)',
                expected_red, None, True, 'INFO')
    else:
        actual_red = rnt_trabajo - work_neto
        passed = abs(actual_red - expected_red) <= _TOLERANCE
        _append(findings, f'ART20_REDUCCION_TRAMO{tramo}', 'Art. 20 LIRPF 2025',
                f'rnt_art20={rnt_art20_s1:.2f}€ → reducción esperada {expected_red:.2f}€ (tramo {tramo})',
                expected_red, actual_red, passed)

    if otras_rentas > Decimal('6500'):
        _append(findings, 'ART20_OTRAS_RENTAS_GATE', 'Art. 20 LIRPF',
                f'otras_rentas={otras_rentas:.2f}€ > 6500€: reducción Art.20 debe ser 0',
                _ZERO, rnt_trabajo - work_neto if work_neto > _ZERO else None, True, 'INFO')


def _check_art49(inp: dict, result: dict, findings: list) -> None:
    """Art. 49 LIRPF — Compensación cruzada GPP ↔ RCM."""
    base_ahorro = _d(result.get('base_ahorro', _ZERO))
    _append(findings, 'ART49_BASE_AHORRO_NN', 'Art. 49 LIRPF',
            'base_ahorro ≥ 0 (invariante sistémico)',
            _ZERO, base_ahorro, base_ahorro >= _ZERO)

    gpp = _d(result.get('gpp_neto', _ZERO))
    rcm = _d(result.get('rcm_neto_reducido', _ZERO))
    if gpp < _ZERO and rcm > _ZERO:
        max_offset = rcm * Decimal('0.25')
        actual_offset = min(abs(gpp), max_offset)
        expected_ba = max(rcm - actual_offset, _ZERO) + max(gpp + actual_offset, _ZERO)
        passed = abs(base_ahorro - expected_ba) <= _TOLERANCE
        _append(findings, 'ART49_GPP_OFFSET_RCM', 'Art. 49.1.b LIRPF',
                f'Pérdida GPP ({gpp:.2f}) compensa max 25% RCM ({rcm:.2f})',
                expected_ba, base_ahorro, passed)


def _check_art51_52(inp: dict, result: dict, findings: list) -> None:
    """Art. 51/52 LIRPF — Planes de pensiones."""
    is_joint = inp.get('joint_declaration', False)
    
    if is_joint:
        # Cónyuge 1
        pension_s1 = _d(inp.get('pension_plan', 0)) + _d(inp.get('pension_empresa', 0))
        rnt_s1 = max(_d(result.get('rendimiento_neto_trabajo', _ZERO)) - (_d(inp.get('spouse_income', 0)) - _d(inp.get('spouse_ss', 0)) - Decimal('2000')), _ZERO)
        limite_s1 = max(Decimal('2000'), Decimal('1.5') * rnt_s1)
        expected_red_s1 = min(pension_s1, limite_s1)
        
        # Cónyuge 2
        pension_s2 = _d(inp.get('spouse_pension_individual_eur', 0)) + _d(inp.get('spouse_pension_empresa_eur', 0))
        rnt_s2 = max(_d(inp.get('spouse_income', 0)) - _d(inp.get('spouse_ss', 0)) - Decimal('2000'), _ZERO)
        limite_s2 = max(Decimal('2000'), Decimal('1.5') * rnt_s2)
        expected_red_s2 = min(pension_s2, limite_s2)
        
        expected_red = expected_red_s1 + expected_red_s2
        pension = pension_s1 + pension_s2
        rnt = rnt_s1 + rnt_s2
    else:
        pension = _d(inp.get('pension_plan', 0)) + _d(inp.get('pension_empresa', 0))
        rnt = _d(result.get('rendimiento_neto_trabajo', _ZERO))
        limite = max(Decimal('2000'), Decimal('1.5') * rnt)
        expected_red = min(pension, limite)
        
    actual_red = _d(result.get('reduccion_pensiones', _ZERO))
    passed = abs(actual_red - expected_red) <= _TOLERANCE
    _append(findings, 'ART51_PENSION_LIMITE', 'Art. 51/52 LIRPF',
            f'Reducción pensiones: min({pension:.2f}, max(2000, 1.5×{rnt:.2f}))',
            expected_red, actual_red, passed)

    pension_spouse = _d(inp.get('pension_spouse', 0))
    spouse_income = _d(inp.get('spouse_income', 0))
    if pension_spouse > _ZERO and not is_joint:
        if spouse_income >= Decimal('8000'):
            _append(findings, 'ART52_SPOUSE_GATE', 'Art. 52.3 LIRPF',
                    f'pension_spouse={pension_spouse}€ pero spouse_income={spouse_income}€≥8000: no aplicable',
                    _ZERO, pension_spouse, False, 'ERROR')
        elif pension_spouse > Decimal('1000'):
            _append(findings, 'ART52_SPOUSE_CAP', 'Art. 52.3 LIRPF',
                    f'pension_spouse={pension_spouse}€ supera tope de 1000€',
                    Decimal('1000'), pension_spouse, False, 'WARNING')


def _check_art55(inp: dict, result: dict, findings: list) -> None:
    """Art. 55 LIRPF — Pensión compensatoria ex-cónyuge."""
    alimonty = _d(inp.get('alimonty', 0))
    if alimonty > _ZERO:
        actual = _d(result.get('alimonty_reduccion', _ZERO))
        passed = abs(actual - alimonty) <= _TOLERANCE
        _append(findings, 'ART55_ALIMONTY_VALOR', 'Art. 55 LIRPF',
                f'Pensión compensatoria ex-cónyuge reduce BIG: esperado {alimonty:.2f}€',
                alimonty, actual, passed)


def _check_deductions(inp: dict, result: dict, findings: list) -> None:
    """DA 9ª, DA 11ª, DA 50ª, Art. 68.1, 68.3 — Deducciones de cuota."""
    applied = result.get('applied_deductions', {})
    state_deds = {d.box_id: d.value for d in applied.get('state', [])} if applied else {}
    bi = _d(result.get('base_imponible_general', _ZERO))

    # DA 9ª — Hipoteca pre-2013
    if bool(inp.get('mortgage_pre2013', False)):
        mortgage_paid = _d(inp.get('mortgage_paid', 0))
        expected = min(mortgage_paid, Decimal('9040')) * Decimal('0.075')
        actual = state_deds.get('ST_DA9', _ZERO)
        passed = abs(actual - expected) <= _TOLERANCE
        _append(findings, 'DA9_HIPOTECA_RATE', 'DA 9ª LIRPF',
                f'7.5% × min({mortgage_paid:.2f}, 9040€) = {expected:.2f}€',
                expected, actual, passed)

    # DA 11ª — Alquiler pre-2015
    if bool(inp.get('rent_pre2015', False)):
        rent_paid = _d(inp.get('rent_pre2015_paid', 0))
        if bi >= Decimal('24107.20'):
            actual = state_deds.get('ST_DA11', _ZERO)
            _append(findings, 'DA11_ALQUILER_BI_GATE', 'DA 11ª LIRPF',
                    f'BI={bi:.2f}€ ≥ 24107.20€: deducción alquiler pre-2015 = 0',
                    _ZERO, actual, actual == _ZERO)
        else:
            base = min(rent_paid, Decimal('9040'))
            if bi <= Decimal('17707.20'):
                expected = base * Decimal('0.1005')
            else:
                factor = Decimal('1') - (bi - Decimal('17707.20')) / Decimal('6400')
                expected = base * Decimal('0.1005') * factor
            actual = state_deds.get('ST_DA11', _ZERO)
            passed = abs(actual - expected) <= _TOLERANCE
            _append(findings, 'DA11_ALQUILER_SCALING', 'DA 11ª LIRPF',
                    f'Alquiler pre-2015 (BI={bi:.2f}€): esperado {expected:.2f}€',
                    expected, actual, passed)

    # Art. 68.1 — Startups
    startup = _d(inp.get('startup_investment', 0))
    if startup > _ZERO:
        expected = min(startup * Decimal('0.50'), Decimal('50000'))
        actual = state_deds.get('ST01', _ZERO)
        passed = abs(actual - expected) <= _TOLERANCE
        _append(findings, 'ART68_STARTUP_RATE', 'Art. 68.1 LIRPF',
                f'50% × {startup:.2f}€, tope 50.000€ → {expected:.2f}€',
                expected, actual, passed)

    # Art. 68.3 — Donativos
    donations = _d(inp.get('donations', 0))
    if donations > _ZERO:
        base_don = min(donations, bi * Decimal('0.10'))
        primero = min(base_don, Decimal('250'))
        resto = max(base_don - Decimal('250'), _ZERO)
        expected = primero * Decimal('0.80') + resto * Decimal('0.40')
        actual = state_deds.get('ST03', _ZERO)
        passed = abs(actual - expected) <= _TOLERANCE
        _append(findings, 'ART68_DONATIVO_TRAMOS', 'Art. 68.3 LIRPF',
                f'80%×min({donations:.2f},250) + 40%×resto, tope 10% BI → {expected:.2f}€',
                expected, actual, passed)

    # DA 50ª — Eficiencia Energética
    energy_inv = _d(inp.get('energy_inv', 0))
    energy_type = int(inp.get('energy_type', 0))
    if energy_inv > _ZERO and energy_type in (20, 40, 60):
        caps = {20: Decimal('5000'), 40: Decimal('7500'), 60: Decimal('15000')}
        rate = Decimal(str(energy_type)) / Decimal('100')
        expected = min(energy_inv * rate, caps[energy_type])
        actual = state_deds.get('ST04', _ZERO)
        passed = abs(actual - expected) <= _TOLERANCE
        _append(findings, 'DA50_ENERGIA', 'DA 50ª LIRPF',
                f'{energy_type}% × {energy_inv:.2f}€, tope {caps[energy_type]}€ → {expected:.2f}€',
                expected, actual, passed)


def _check_art81_81bis(inp: dict, result: dict, findings: list) -> None:
    """Art. 81 y 81bis LIRPF — Deducciones diferenciales familia."""
    applied = result.get('applied_deductions', {})
    diff_deds = {d.box_id: d.value for d in applied.get('differential', [])} if applied else {}

    children_u3 = int(inp.get('children_under_3', 0))
    is_working_mother = bool(inp.get('is_working_mother', False))
    if children_u3 > 0 and is_working_mother:
        expected = Decimal('1200') * children_u3
        actual = diff_deds.get('ART81_MAT', _ZERO)
        passed = abs(actual - expected) <= _TOLERANCE
        _append(findings, 'ART81_MATERNIDAD', 'Art. 81 LIRPF',
                f'Maternidad: 1200€ × {children_u3} hijos <3 años → {expected:.2f}€',
                expected, actual, passed)

        daycare = _d(inp.get('daycare_expenses', 0))
        if daycare > _ZERO:
            expected_g = min(daycare, Decimal('1000') * children_u3)
            actual_g = diff_deds.get('ART81_GUAR', _ZERO)
            passed_g = abs(actual_g - expected_g) <= _TOLERANCE
            _append(findings, 'ART81_GUARDERIA', 'Art. 81 LIRPF',
                    f'Guardería: min({daycare:.2f}, {1000*children_u3}€) → {expected_g:.2f}€',
                    expected_g, actual_g, passed_g)

    family_type = inp.get('family_type', 'none')
    if family_type == 'large_general':
        actual = diff_deds.get('ART81BIS_FNG', _ZERO)
        passed = abs(actual - Decimal('1200')) <= _TOLERANCE
        _append(findings, 'ART81BIS_FN_GENERAL', 'Art. 81bis LIRPF',
                'Familia numerosa general: 1200€', Decimal('1200'), actual, passed)
    elif family_type == 'large_special':
        actual = diff_deds.get('ART81BIS_FNE', _ZERO)
        passed = abs(actual - Decimal('2400')) <= _TOLERANCE
        _append(findings, 'ART81BIS_FN_ESPECIAL', 'Art. 81bis LIRPF',
                'Familia numerosa especial: 2400€', Decimal('2400'), actual, passed)

    if bool(inp.get('single_parent_2_children', False)):
        actual = diff_deds.get('ART81BIS_MONO', _ZERO)
        passed = abs(actual - Decimal('1200')) <= _TOLERANCE
        _append(findings, 'ART81BIS_MONO', 'Art. 81bis LIRPF',
                'Monoparental ≥2 hijos: 1200€', Decimal('1200'), actual, passed)

    if int(inp.get('spouse_disability', 0)) >= 33:
        actual = diff_deds.get('ART81BIS_CONYUGE', _ZERO)
        passed = abs(actual - Decimal('1200')) <= _TOLERANCE
        _append(findings, 'ART81BIS_CONYUGE', 'Art. 81bis LIRPF',
                'Cónyuge discapacitado ≥33%: 1200€', Decimal('1200'), actual, passed)


def _check_art84(inp: dict, result: dict, findings: list) -> None:
    """Art. 84 LIRPF — Reducción por tributación conjunta."""
    joint = bool(inp.get('joint_declaration', False))
    married = inp.get('marital_status', 'single') == 'married'
    monoparental = bool(inp.get('is_monoparental', False))
    actual = _d(result.get('reduccion_conjunta', _ZERO))

    if joint and married and not monoparental:
        passed = abs(actual - Decimal('3400')) <= _TOLERANCE
        _append(findings, 'ART84_CONJUNTA_CASADO', 'Art. 84 LIRPF',
                'Declaración conjunta matrimonio: 3400€', Decimal('3400'), actual, passed)
    elif joint and monoparental:
        passed = abs(actual - Decimal('2150')) <= _TOLERANCE
        _append(findings, 'ART84_CONJUNTA_MONO', 'Art. 84 LIRPF',
                'Declaración conjunta monoparental: 2150€', Decimal('2150'), actual, passed)
    elif not joint and actual > _ZERO:
        _append(findings, 'ART84_CONJUNTA_SOLO_CASADOS', 'Art. 84 LIRPF',
                f'Sin joint_declaration, reduccion_conjunta debe ser 0 (actual={actual:.2f}€)',
                _ZERO, actual, False, 'WARNING')


def _check_systemic(inp: dict, result: dict, findings: list) -> None:
    """Invariantes sistémicos del cálculo IRPF."""
    cuota_liquida = _d(result.get('cuota_liquida', _ZERO))
    _append(findings, 'SYS_CUOTA_LIQUIDA_NN', 'Invariante sistémico',
            'cuota_liquida ≥ 0 (antes de deducciones diferenciales)',
            _ZERO, cuota_liquida, cuota_liquida >= _ZERO)

    base_general = _d(result.get('base_general', _ZERO))
    _append(findings, 'SYS_BASE_GENERAL_NN', 'Invariante sistémico',
            'base_general ≥ 0', _ZERO, base_general, base_general >= _ZERO)

    resultado = _d(result.get('resultado', _ZERO))
    cuota_resultante = _d(result.get('cuota_resultante', _ZERO))
    ret_trabajo = _d(result.get('retenciones_trabajo_total', _ZERO))
    ret_capital = _d(result.get('retenciones_capital', _ZERO))
    expected_resultado = cuota_resultante - ret_trabajo - ret_capital
    passed = abs(resultado - expected_resultado) <= _TOLERANCE
    _append(findings, 'SYS_RESULTADO_FORMULA', 'Invariante sistémico',
            'resultado = cuota_resultante − retenciones_trabajo − retenciones_capital',
            expected_resultado, resultado, passed)

    if cuota_resultante < _ZERO:
        _append(findings, 'SYS_CUOTA_RESULTANTE_INFO', 'Art. 103 LGT',
                f'cuota_resultante={cuota_resultante:.2f}€ < 0 → "A DEVOLVER" (legal)',
                None, cuota_resultante, True, 'INFO')


def _check_oracle(inp: dict, result: dict, findings: list) -> None:
    """Verifica los valores esperados del JSON oracle."""
    if inp.get('__status', 'pending') != 'verified':
        return
    expected = inp.get('__expected', {})
    checks = [
        ('base_imponible_general', 'base_imponible_general', 'ORACLE_BIG', 'Base Imponible General'),
        ('cuota_integra_estatal',  'cuota_integra_estatal',  'ORACLE_CIE', 'Cuota Íntegra Estatal'),
        ('resultado',              'resultado_declaracion',   'ORACLE_RESULTADO', 'Resultado declaración'),
    ]
    for result_key, exp_key, rule_id, label in checks:
        exp_val = expected.get(exp_key, 0.0)
        if exp_val == 0.0:
            _append(findings, rule_id, 'Oracle Test',
                    f'{label}: sin valor oracle (expected=0.0, se omite)', None, None, True, 'INFO')
        else:
            actual = _d(result.get(result_key, _ZERO))
            exp_d = Decimal(str(exp_val))
            passed = abs(actual - exp_d) <= _TOLERANCE
            _append(findings, rule_id, 'Oracle Test',
                    f'{label}: oracle={exp_val}€', exp_d, actual, passed)


# ── Public API: audit_results ────────────────────────────────────────────────

def audit_results(
    case_input: dict,
    result: dict,
    expected_results: Optional[dict] = None,
) -> AuditReport:
    """
    Re-deriva cada cálculo intermedio del IRPF desde case_input y lo compara
    contra el resultado de IRPFCalculator, actuando como auditor fiscalista senior.

    Args:
        case_input: dict del input del caso (claves como gross_income, pension_plan, etc.)
        result: dict devuelto por IRPFCalculator.calculate().raw_summary
        expected_results: dict con valores oracle JSON (opcional, para ORACLE_* checks)

    Returns:
        AuditReport con findings detallados por cada regla.
    """
    inp = dict(case_input)
    if expected_results is not None:
        inp['__expected'] = expected_results

    findings: List[AuditFinding] = []

    _check_art19(inp, result, findings)
    _check_art20(inp, result, findings)
    _check_art49(inp, result, findings)
    _check_art51_52(inp, result, findings)
    _check_art55(inp, result, findings)
    _check_deductions(inp, result, findings)
    _check_art81_81bis(inp, result, findings)
    _check_art84(inp, result, findings)
    _check_systemic(inp, result, findings)
    _check_oracle(inp, result, findings)

    passed_count = sum(1 for f in findings if f.passed)
    failed_count = sum(1 for f in findings if not f.passed)
    return AuditReport(
        case_name=inp.get('__case_name', 'unknown'),
        passed_count=passed_count,
        failed_count=failed_count,
        findings=findings,
    )


__all__ = ['RunResult', 'AuditFinding', 'AuditReport', 'run_calculation', 'audit_results']
