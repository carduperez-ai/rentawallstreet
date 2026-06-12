import json
with open('smoke_tests.json', encoding='utf-8') as f:
    data = json.load(f)
for c in data:
    res = c['expected_results']
    if res['resultado_declaracion'] != 0 or res['base_imponible_general'] != 0:
        print(f"{c['name']}: Base={res['base_imponible_general']}, Res={res['resultado_declaracion']}")
