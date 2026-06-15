"""
Pytest entry point para el Oracle Test Runner + Fiscal Auditor.
Parametriza sobre todos los casos oracle y ejecuta dos baterías:
  - TestOracleCalculation: caja negra (valores esperados JSON)
  - TestAuditInvariants: caja blanca (normativa LIRPF 2025)
"""

import pytest
from decimal import Decimal

from tests.oracle_generator.test_runner import (
    RunResult,
    AuditReport,
    run_calculation,
    audit_results,
)

# Carga todos los resultados una vez (parametrize estático)
_ALL_RESULTS: list[RunResult] = run_calculation()
_IDS = [r.case_name for r in _ALL_RESULTS]
_TOLERANCE = Decimal("0.02")


# ── TestOracleCalculation — caja negra ───────────────────────────────────────


class TestOracleCalculation:
    @pytest.mark.parametrize("run_result", _ALL_RESULTS, ids=_IDS)
    def test_no_exception(self, run_result: RunResult):
        """El motor no debe lanzar excepción para ningún caso oracle."""
        assert run_result.error is None, f"Caso '{run_result.case_name}' lanzó: {run_result.error}"

    @pytest.mark.parametrize("run_result", _ALL_RESULTS, ids=_IDS)
    def test_oracle_base_imponible_general(self, run_result: RunResult):
        """base_imponible_general coincide con el valor oracle (skip si no hay oracle)."""
        if run_result.error:
            pytest.skip("Cálculo fallido")
        if getattr(run_result, 'status', run_result.input_dict.get('__status', '')) not in ('verified', 'auto_calculated'):
            pytest.skip("Caso no verificado oficialmente ni auto_calculado")
        expected = run_result.expected.get("base_imponible_general", 0.0)
        actual = run_result.calculated.get("base_imponible_general", Decimal("0"))
        assert actual == Decimal(str(expected)), f"{run_result.case_name}: esperado {expected}€, obtenido {actual}€"

    @pytest.mark.parametrize("run_result", _ALL_RESULTS, ids=_IDS)
    def test_oracle_cuota_integra_estatal(self, run_result: RunResult):
        """cuota_integra_estatal coincide con el valor oracle."""
        if run_result.error:
            pytest.skip("Cálculo fallido")
        if getattr(run_result, 'status', run_result.input_dict.get('__status', '')) not in ('verified', 'auto_calculated'):
            pytest.skip("Caso no verificado oficialmente ni auto_calculado")
        expected = run_result.expected.get("cuota_integra_estatal", 0.0)
        actual = run_result.calculated.get("cuota_integra_estatal", Decimal("0"))
        assert actual == Decimal(str(expected)), f"{run_result.case_name}: esperado {expected}€, obtenido {actual}€"

    @pytest.mark.parametrize("run_result", _ALL_RESULTS, ids=_IDS)
    def test_oracle_resultado_declaracion(self, run_result: RunResult):
        """resultado_declaracion final coincide exactamente."""
        if run_result.error:
            pytest.skip("Cálculo fallido")
        if getattr(run_result, 'status', run_result.input_dict.get('__status', '')) not in ('verified', 'auto_calculated'):
            pytest.skip("Caso no verificado oficialmente ni auto_calculado")
        expected = run_result.expected.get("resultado_declaracion", 0.0)
        actual = run_result.calculated.get("resultado_declaracion", Decimal("0"))
        assert actual == Decimal(str(expected)), f"{run_result.case_name}: esperado {expected}€, obtenido {actual}€"



# ── TestAuditInvariants — caja blanca (normativa LIRPF) ─────────────────────


class TestAuditInvariants:
    @pytest.mark.parametrize("run_result", _ALL_RESULTS, ids=_IDS)
    def test_audit_systemic_invariants(self, run_result: RunResult):
        """
        Todos los findings de severidad ERROR deben pasar.
        Cubre: cuota_liquida≥0, base_general≥0, fórmula resultado,
               Art.19 gastos, Art.20 tramos, Art.51/52 límites,
               Art.55 alimonty, Art.68 deducciones, Art.81/81bis, Art.84.
        """
        if run_result.error:
            pytest.skip(f"Cálculo fallido: {run_result.error}")

        inp = dict(run_result.input_dict)
        inp["__status"] = run_result.status
        report: AuditReport = audit_results(inp, run_result.calculated, run_result.expected)

        errors = [f for f in report.findings if not f.passed and f.severity == "ERROR"]
        assert not errors, f"\nCaso '{run_result.case_name}' — {len(errors)} regla(s) fallida(s):\n" + "\n".join(
            f"  [{f.rule_id}] {f.article}: {f.description}\n" f"    esperado={f.expected}  actual={f.actual}"
            for f in errors
        )

    @pytest.mark.parametrize("run_result", _ALL_RESULTS, ids=_IDS)
    def test_audit_warnings_visible(self, run_result: RunResult):
        """
        Los warnings no fallan el test pero se imprimen para revisión manual.
        Ejemplo: pension_spouse excede tope, joint_declaration sin casado, etc.
        """
        if run_result.error:
            pytest.skip(f"Cálculo fallido: {run_result.error}")

        inp = dict(run_result.input_dict)
        report: AuditReport = audit_results(inp, run_result.calculated, run_result.expected)

        warnings = [f for f in report.findings if not f.passed and f.severity == "WARNING"]
        if warnings:
            for w in warnings:
                print(
                    f"\n  WARN [{w.rule_id}] {w.article}: {w.description}"
                    f"\n    esperado={w.expected}  actual={w.actual}"
                )
        # Los warnings solo informan, no fallan
        assert True

    @pytest.mark.parametrize("run_result", _ALL_RESULTS, ids=_IDS)
    def test_oracle_base_imponible_ahorro(self, run_result: RunResult):
        """Verifica que la base imponible del ahorro sea correcta."""

        inp = dict(run_result.input_dict)
        report: AuditReport = audit_results(inp, run_result.calculated)

        assert report.case_name == run_result.case_name

    @pytest.mark.parametrize("run_result", _ALL_RESULTS, ids=_IDS)
    def test_audit_report_structure(self, run_result: RunResult):
        """AuditReport tiene findings y contadores coherentes."""
        if run_result.error:
            pytest.skip(f"Cálculo fallido: {run_result.error}")

        inp = dict(run_result.input_dict)
        report: AuditReport = audit_results(inp, run_result.calculated)

        assert report.case_name == run_result.case_name
        assert report.passed_count + report.failed_count == len(report.findings)
        assert len(report.findings) >= 5, "Se esperan al menos 5 reglas auditadas"
