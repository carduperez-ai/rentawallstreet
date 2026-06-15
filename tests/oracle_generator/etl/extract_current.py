import sys
import json
from playwright.sync_api import sync_playwright


def extract(test_name):
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]

            # Selectores del resumen
            selectors = {
                "resultado_declaracion": "RESINGDEV",
                "base_imponible_general": "BIGENERAL",
                "base_liquidable_general_gravamen": "BLGENERAL",
                "base_imponible_ahorro": "BIAHORRO",
                "base_liquidable_ahorro": "BLAHORRO",
                "minimo_personal_familiar_estatal": "MINPFEST",
                "minimo_personal_familiar_autonomico": "MINPFAUT",
                "cuota_integra_estatal": "CIEST",
                "cuota_integra_autonomica": "CIAUT",
                "suma_deducciones_autonomicas": "SUMDEDAUT",
                "cuota_liquida_estatal": "CLEST",
                "cuota_liquida_autonomica": "CLAUT",
                "cuota_liquida_estatal_incrementada": "CLESTINC",
                "cuota_liquida_autonomica_incrementada": "CLAUTINC",
                "cuota_liquida_incrementada_total": "CLINCTOT",
                "cuota_resultante_autoliquidacion": "CRESAUT",
                "retenciones_pagos_cuenta": "PAGOS",
                "cuota_diferencial": "CDIFEREN",
                "ingresos_integros": "INGINT",
            }

            results = {}
            for key, sid in selectors.items():
                val = page.evaluate(
                    f"() => {{ const e = document.getElementById('{sid}'); return e ? e.innerText : '0'; }}"
                )
                val = val.replace(".", "").replace(",", ".").replace(" €", "")
                try:
                    results[key] = float(val)
                except Exception:
                    results[key] = 0.0

            # Cargar JSON
            json_path = "c:/rentawallstreet/tests/oracle_generator/irpf_oracle_tests.json"
            with open(json_path, "r", encoding="utf-8") as f:
                cases = json.load(f)

            # Actualizar caso
            updated = False
            for case in cases:
                if case["name"] == test_name:
                    case["expected_results"].update(results)
                    case["status"] = "verified"
                    updated = True
                    break

            if updated:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(cases, f, indent=2, ensure_ascii=False)
                print(f"✅ Caso {test_name} actualizado con éxito.")
            else:
                print(f"❌ No se encontró el caso {test_name}.")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract(sys.argv[1])
