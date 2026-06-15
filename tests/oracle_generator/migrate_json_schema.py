import json
import os


def migrate_json(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    new_results_template = {
        "resultado_declaracion": 0.0,
        "base_imponible_general": 0.0,
        "base_liquidable_general_gravamen": 0.0,
        "base_imponible_ahorro": 0.0,
        "base_liquidable_ahorro": 0.0,
        "minimo_personal_familiar_estatal": 0.0,
        "minimo_personal_familiar_autonomico": 0.0,
        "cuota_integra_estatal": 0.0,
        "cuota_integra_autonomica": 0.0,
        "suma_deducciones_autonomicas": 0.0,
        "cuota_liquida_estatal": 0.0,
        "cuota_liquida_autonomica": 0.0,
        "cuota_liquida_estatal_incrementada": 0.0,
        "cuota_liquida_autonomica_incrementada": 0.0,
        "cuota_liquida_incrementada_total": 0.0,
        "cuota_resultante_autoliquidacion": 0.0,
        "retenciones_pagos_cuenta": 0.0,
        "cuota_diferencial": 0.0,
        "deduccion_maternidad": 0.0,
        "deduccion_maternidad_guarderia": 0.0,
        "deduccion_descendientes_discapacidad": 0.0,
        "deduccion_ascendientes_discapacidad": 0.0,
        "deduccion_conyuge_discapacidad": 0.0,
        "deduccion_familia_numerosa": 0.0,
        "deduccion_ascendiente_2_hijos": 0.0,
    }

    updated_count = 0
    for case in data:
        if "expected_results" in case:
            # Preserve existing values if keys match, otherwise add new ones
            current_results = case["expected_results"]
            updated_results = new_results_template.copy()

            # Special mapping for old keys if necessary
            # (In this case, most keys match or will be overwritten with 0.0)
            for k, v in current_results.items():
                if k in updated_results:
                    updated_results[k] = v

            case["expected_results"] = updated_results
            updated_count += 1

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Migrated {updated_count} cases in {file_path}")


if __name__ == "__main__":
    files_to_migrate = [
        "c:/rentawallstreet/tests/oracle_generator/irpf_oracle_tests.json",
        "c:/rentawallstreet/tests/oracle_generator/smoke_tests.json",
        "c:/rentawallstreet/tests/oracle_generator/temp_test.json",
    ]
    for file in files_to_migrate:
        migrate_json(file)
