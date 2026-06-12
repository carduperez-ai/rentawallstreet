import json
import os

def recover_tests():
    json_path = "c:/rentawallstreet/tests/oracle_generator/irpf_oracle_tests.json"
    if not os.path.exists(json_path):
        print(f"Error: {json_path} no existe.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    # 100% correct, verified AEAT oracle results from verified_results TXT files
    recovery_data = {
        "SAL-MAD-2K": {
            "status": "verified",
            "expected_results": {
                "resultado_declaracion": -40.00,
                "base_imponible_general": 0.0,
                "retenciones_pagos_cuenta": 40.00,
                "cuota_diferencial": -40.00
            }
        },
        "SAL-MAD-14K": {
            "status": "verified",
            "expected_results": {
                "resultado_declaracion": -280.00,
                "base_imponible_general": 3809.00,
                "retenciones_pagos_cuenta": 280.00,
                "cuota_diferencial": -280.00
            }
        },
        "SAL-MAD-17K": {
            "status": "verified",
            "expected_results": {
                "resultado_declaracion": -1273.01,
                "base_imponible_general": 8488.37,
                "retenciones_pagos_cuenta": 1767.35,
                "cuota_diferencial": -1273.01
            }
        },
        "INC-IND-W-12K": {
            "status": "verified",
            "expected_results": {
                "resultado_declaracion": -468.00,
                "base_imponible_general": 1936.00,
                "retenciones_pagos_cuenta": 468.00,
                "cuota_diferencial": -468.00
            }
        },
        "INC-IND-WD-12K": {
            "status": "verified",
            "expected_results": {
                "resultado_declaracion": -335.00,
                "base_imponible_general": 1936.00,
                "base_imponible_ahorro": 500.00,
                "retenciones_pagos_cuenta": 335.00,
                "cuota_diferencial": -335.00
            }
        },
        "INC-IND-WG-35K": {
            "status": "verified",
            "input": {
                "tax_events": [{"asset_type": "stock", "gain_loss_eur": 10000.00, "total_sale_eur": 20000.00, "total_cost_eur": 10000.00}]
            },
            "expected_results": {
                "resultado_declaracion": -857.73,
                "base_imponible_general": 30777.50,
                "base_imponible_ahorro": 10000.00,
                "retenciones_pagos_cuenta": 8750.00,
                "cuota_diferencial": -857.73
            }
        },
        "INC-CAS-CON-W-35K": {
            "status": "verified",
            "input": {
                "spouse_ss": 952.50,
                "spouse_retenciones": 300.00
            },
            "expected_results": {
                "resultado_declaracion": 316.11,
                "base_imponible_general": 44825.00,
                "retenciones_pagos_cuenta": 9050.00,
                "cuota_diferencial": 316.11
            }
        },
        "INC-IND-FULL-250K": {
            "status": "verified",
            "expected_results": {
                "resultado_declaracion": 8621.60,
                "base_imponible_general": 243800.00,
                "base_imponible_ahorro": 7000.00,
                "retenciones_pagos_cuenta": 87880.00,
                "cuota_diferencial": 8621.60
            }
        }
    }

    updated_count = 0
    # Reseteamos todas a pending antes de re-aplicar
    for case in cases:
        case["status"] = "pending"
        # Limpiar overrides que hubieran quedado
        if case["name"] == "INC-IND-FULL-250K":
            if "gross_income" in case["input"] and case["input"]["gross_income"] == 150000.0:
                case["input"]["gross_income"] = 250000.0
                case["input"]["withholdings_paid"] = 87500.0
                case["input"]["dividends"] = [{"gross_eur": 2000.0, "withholding_spain_eur": 380.0}]

    for case in cases:
        name = case["name"]
        if name in recovery_data:
            case["status"] = recovery_data[name]["status"]
            if "input" in recovery_data[name]:
                case["input"].update(recovery_data[name]["input"])
            case["expected_results"].update(recovery_data[name]["expected_results"])
            updated_count += 1

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)

    print(f"Restaurados {updated_count} casos verificados oficiales desde el log de la sesión.")

if __name__ == "__main__":
    recover_tests()
