import json


def add_cases():
    path = "c:/rentawallstreet/tests/oracle_generator/irpf_oracle_tests.json"
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    new_cases = [
        {
            "name": "MIX-CAT-INV",
            "category": "Mixto | Inversión | Cataluña",
            "input": {
                "fiscal_year": 2025,
                "region": "cataluña",
                "age": 35,
                "ui_gender": "Hombre",
                "marital_status": "single",
                "gross_income": 40000.0,
                "withholdings_paid": 8000.0,
                "ss_employee": 2540.0,
                "dividends": [{"gross_eur": 2000.0, "withholding_spain_eur": 380.0}],
                "stock_gains": [{"asset": "Acciones", "gain_loss_eur": 5000.0}],
            },
            "expected_results": {"resultado_declaracion": 0.0},
            "status": "pending",
        },
        {
            "name": "MIX-CAT-RENT",
            "category": "Mixto | Alquiler | Cataluña",
            "input": {
                "fiscal_year": 2025,
                "region": "cataluña",
                "age": 40,
                "ui_gender": "Mujer",
                "marital_status": "single",
                "gross_income": 35000.0,
                "withholdings_paid": 7000.0,
                "ss_employee": 2222.5,
                "rentals": [
                    {
                        "property_id": "VIV-1",
                        "gross_income": 12000.0,
                        "deductible_expenses": 2000.0,
                        "reduction_habitual": True,
                    }
                ],
            },
            "expected_results": {"resultado_declaracion": 0.0},
            "status": "pending",
        },
    ]

    # Evitar duplicados por nombre
    existing_names = {c["name"] for c in cases}
    for nc in new_cases:
        if nc["name"] not in existing_names:
            cases.append(nc)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
    print(f"Añadidos {len(new_cases)} casos complejos.")


if __name__ == "__main__":
    add_cases()
