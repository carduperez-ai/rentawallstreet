import sys
import os
import json

# Añadir raíz del proyecto al path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.oracle_generator.test_runner import run_calculation, audit_results  # noqa: E402
from tests.oracle_generator.generate_test_suite import (  # noqa: E402
    generate_salary_thresholds,
    generate_family_cases,
    generate_deduction_cases,
)


def print_audit_report(report):
    print(f"\n  [CASO] {report.case_name}")
    print(
        f"  Result: {'[OK] PASSED' if report.all_passed else '[!!] FAILED'} ({report.passed_count} ok, {report.failed_count} errors)"
    )

    for finding in report.findings:
        symbol = "[V]" if finding.passed else "[X]"
        desc = (
            finding.description.replace("€", "EUR")
            .replace("≥", ">=")
            .replace("≤", "<=")
            .replace("×", "x")
            .replace("−", "-")
        )
        desc = desc.encode("ascii", "replace").decode("ascii").replace("?", "_")
        if not finding.passed or finding.severity != "INFO":
            print(f"    {symbol} [{finding.rule_id}] {desc}")
            if not finding.passed:
                print(f"       Expected: {finding.expected} | Actual: {finding.actual}")


def run_group(name, cases):
    print(f"\n{'=' * 60}")
    print(f" EJECUTANDO GRUPO: {name} ({len(cases)} casos)")
    print(f"{'=' * 60}")

    results = run_calculation(cases)
    group_passed = 0
    group_failed = 0

    for res in results:
        if res.error:
            print(f"\n  [CASO] {res.case_name} -> 💥 ERROR DE EJECUCIÓN: {res.error}")
            group_failed += 1
            continue

        report = audit_results(res.input_dict, res.calculated, res.expected)
        print_audit_report(report)

        if report.all_passed:
            group_passed += 1
        else:
            group_failed += 1

    print(f"\n--- Resumen {name}: {group_passed} Pasados, {group_failed} Fallidos ---")
    return group_passed, group_failed


def main():
    total_passed = 0
    total_failed = 0

    target_group = sys.argv[1].upper() if len(sys.argv) > 1 else None

    groups_data = [
        ("SALARIOS", generate_salary_thresholds),
        ("FAMILIA", generate_family_cases),
        ("DEDUCCIONES", generate_deduction_cases),
    ]

    selected_groups = []
    if target_group:
        if target_group == "ORACLE":
            json_path = os.path.join(os.path.dirname(__file__), "irpf_oracle_tests.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    selected_groups.append(("ORACLE JSON", json.load(f)))
        elif target_group == "SMOKE":
            json_path = os.path.join(os.path.dirname(__file__), "smoke_tests.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    selected_groups.append(("SMOKE JSON", json.load(f)))
        else:
            for name, gen in groups_data:
                if name == target_group:
                    selected_groups.append((name, gen()))
    else:
        for name, gen in groups_data:
            selected_groups.append((name, gen()))
        json_path = os.path.join(os.path.dirname(__file__), "irpf_oracle_tests.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                selected_groups.append(("ORACLE JSON", json.load(f)))

    for name, cases in selected_groups:
        passes, fails = run_group(name, cases)
        total_passed += passes
        total_failed += fails

    print(f"\n{'#' * 60}")
    print(" BALANCE FINAL")
    print(f" TOTAL PASADOS: {total_passed}")
    print(f" TOTAL FALLIDOS: {total_failed}")
    print(f"{'#' * 60}")


if __name__ == "__main__":
    main()
