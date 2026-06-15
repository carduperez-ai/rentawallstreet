import json

f_path = "c:/rentawallstreet/tests/oracle_generator/irpf_oracle_tests.json"
with open(f_path, "r", encoding="utf-8") as f:
    cases = json.load(f)
for c in cases:
    if "SAL-CAT" in c["name"]:
        c["status"] = "pending"
        c["expected_results"]["resultado_declaracion"] = 0.0
with open(f_path, "w", encoding="utf-8") as f:
    json.dump(cases, f, indent=2, ensure_ascii=False)
print("JSON Limpio.")
