
import sys
import os
import json

# Añadir raíz del proyecto al path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.oracle_generator.test_runner import run_calculation, audit_results

def verify_single_case(case_name):
    json_path = "irpf_oracle_tests.json"
    with open(json_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    
    target_case = [c for c in cases if c["name"] == case_name]
    if not target_case:
        print(f"Caso {case_name} no encontrado")
        return

    results = run_calculation(target_case)
    for res in results:
        report = audit_results(res.input_dict, res.calculated, res.expected)
        print(f"Caso: {res.case_name}")
        print(f"Resultado Auditoría: {'PASSED' if report.all_passed else 'FAILED'}")
        for finding in report.findings:
            if not finding.passed:
                print(f"  [FAIL] {finding.rule_id}: Expected {finding.expected}, Actual {finding.actual}")
            elif "ORACLE" in finding.rule_id:
                print(f"  [OK] {finding.rule_id}: {finding.description}")

if __name__ == "__main__":
    verify_single_case("SAL-MAD-22K")
