import json
import os

# Pool de NIFs de prueba rotatorio (letra calculada mediante algoritmo oficial)
_NIF_POOL = [
    "12345678Z",
    "54357930W",
    "87654321X",
    "22222222J",
    "33333333P",
    "44444444R",
    "55555555K",
    "66666666Q",
    "77777777V",
    "99999999R",
    "11111111H",
    "22222222J",
    "33333333P",
    "44444444R",
    "55555555K",
    "66666666Q",
    "77777777V",
    "88888888Y",
    "99999999R",
    "12312312S",
]
_nif_counter = 0


def _next_nif() -> str:
    """Devuelve el siguiente NIF del pool de forma rotativa."""
    global _nif_counter
    nif = _NIF_POOL[_nif_counter % len(_NIF_POOL)]
    _nif_counter += 1
    return nif


def build_coherent_profile(gross_income: float, **kwargs) -> dict:
    """
    Construye un TaxpayerProfile tipado nativamente con coherencia matemática.
    Calcula SS y Retenciones dinámicamente si no se proveen.
    """
    # Lógica de negocio (Coherencia)
    ss_estimada = min(gross_income * 0.0635, 4200.0)

    # Simulación de tramos de retención proporcionales lógicos
    if gross_income < 15000:
        ret_rate = 0.02
    elif gross_income < 22000:
        ret_rate = 0.10
    elif gross_income < 35000:
        ret_rate = 0.15
    elif gross_income < 60000:
        ret_rate = 0.25
    else:
        ret_rate = 0.35

    retenciones_estimadas = gross_income * ret_rate

    # Perfil base estrictamente tipado
    profile = {
        "fiscal_year": 2025,
        "region": "madrid",
        "age": 30,
        "ui_gender": "Hombre",
        "disability": 0,
        "is_victim": False,
        "marital_status": "single",
        "joint_declaration": False,
        "spouse_income": 0.0,
        "alimonty": 0.0,
        "child_support": 0.0,
        "rent_paid": 0.0,
        "is_rent_habitual": False,
        "descendants": 0,
        "edu_expenses": 0.0,
        "family_type": "none",
        "is_monoparental": False,
        "single_parent_2_children": False,
        "birth_count": 0,
        "custody_shared": False,
        "children_under_3": 0,
        "is_working_mother": False,
        "daycare_expenses": 0.0,
        "children_disabled_33_65": 0,
        "children_disabled_over65": 0,
        "disability_mobility_reduced": False,
        "disability_needs_help": False,
        "spouse_disability": 0,
        "ascendants_over65": 0,
        "ascendants_disabled": 0,
        "pension_plan": 0.0,
        "pension_empresa": 0.0,
        "pension_spouse": 0.0,
        "gross_income": float(gross_income),
        "withholdings_paid": float(retenciones_estimadas),
        "ss_employee": float(ss_estimada),
        "cuotas_sindicales": 0.0,
        "professional_college": 0.0,
        "legal_defense": 0.0,
        "geo_mobility": False,
        "startup_investment": 0.0,
        "donations": 0.0,
        "energy_inv": 0.0,
        "energy_type": 0,
        "mortgage_pre2013": False,
        "mortgage_paid": 0.0,
        "rent_pre2015": False,
        "rent_pre2015_paid": 0.0,
        "political_party": 0.0,
        "ceuta_melilla_income": False,
        "is_celiac": False,
        "is_protected_housing": False,
        "vet_expenses": 0.0,
        "gym_expenses": 0.0,
        "legal_defense_expenses": 0.0,
        "dividends": [],
        "rentals": [],
        "stock_gains": [],
        "tax_events": [],
        "other_income": [],
    }

    # Sobreescribir con las mutaciones
    for k, v in kwargs.items():
        profile[k] = v

    return profile


def format_case(case_id: str, desc: str, tags: list, profile: dict, status: str = "pending") -> dict:
    return {
        "name": case_id,
        "category": " | ".join(tags),
        "input": profile,
        "expected_results": {
            "base_imponible_general": 0.0,
            "base_imponible_ahorro": 0.0,
            "cuota_integra_estatal": 0.0,
            "cuota_integra_autonomica": 0.0,
            "resultado_declaracion": 0.0,
        },
        "status": status,
    }


def generate_full_matrix() -> list:
    cases = []

    # 1. Definición de Niveles de Ingresos (Gross)
    income_levels = [12000.0, 35000.0, 80000.0, 250000.0]

    # 2. Tipos de Declarante
    declarant_types = [
        ("IND", {"marital_status": "single", "joint_declaration": False}, ["Individual"]),
        ("CAS-IND", {"marital_status": "married", "joint_declaration": False}, ["Casado", "Individual"]),
        (
            "CAS-CON",
            {"marital_status": "married", "joint_declaration": True, "spouse_income": 15000.0},
            ["Casado", "Conjunta"],
        ),
        (
            "MONO",
            {"marital_status": "divorced", "is_monoparental": True, "joint_declaration": True, "descendants": 2},
            ["Monoparental", "Conjunta"],
        ),
    ]

    # 3. Tipos de Ingreso (Opciones)
    for decl_code, decl_params, decl_tags in declarant_types:
        for s in income_levels:
            # A. Solo Trabajo
            cases.append(
                format_case(
                    f"INC-{decl_code}-W-{int(s//1000)}K",
                    f"Declarante {decl_code} | Solo Trabajo {s}€",
                    decl_tags + ["Trabajo"],
                    build_coherent_profile(s, **decl_params),
                )
            )

            # B. Trabajo + Dividendos
            div_val = s * 0.1
            p_div = build_coherent_profile(s, **decl_params)
            p_div["dividends"] = [{"gross_eur": div_val, "withholding_spain_eur": div_val * 0.19}]
            cases.append(
                format_case(
                    f"INC-{decl_code}-WD-{int(s//1000)}K",
                    f"Declarante {decl_code} | Trabajo {s}€ + Div {div_val}€",
                    decl_tags + ["Mixto", "Dividendos"],
                    p_div,
                )
            )

            # C. Trabajo + Ganancias
            gain_val = s * 0.2
            p_gain = build_coherent_profile(s, **decl_params)
            p_gain["tax_events"] = [{"asset_type": "stock", "gain_loss_eur": gain_val}]
            cases.append(
                format_case(
                    f"INC-{decl_code}-WG-{int(s//1000)}K",
                    f"Declarante {decl_code} | Trabajo {s}€ + Ganancia {gain_val}€",
                    decl_tags + ["Mixto", "Ganancias"],
                    p_gain,
                )
            )

            # D. Trabajo + Alquileres
            rent_val = 12000.0
            p_rent = build_coherent_profile(s, **decl_params)
            p_rent["rentals"] = [
                {
                    "property_id": "V1",
                    "gross_income": rent_val,
                    "deductible_expenses": 2000.0,
                    "reduction_habitual": True,
                }
            ]
            cases.append(
                format_case(
                    f"INC-{decl_code}-WR-{int(s//1000)}K",
                    f"Declarante {decl_code} | Trabajo {s}€ + Alquiler {rent_val}€",
                    decl_tags + ["Mixto", "Alquileres"],
                    p_rent,
                )
            )

            # E. TODO (Full Mix)
            p_full = build_coherent_profile(s, **decl_params)
            p_full["dividends"] = [{"gross_eur": 2000.0, "withholding_spain_eur": 380.0}]
            p_full["tax_events"] = [{"asset_type": "stock", "gain_loss_eur": 5000.0}]
            p_full["rentals"] = [{"property_id": "V1", "gross_income": 6000.0, "reduction_habitual": True}]
            cases.append(
                format_case(
                    f"INC-{decl_code}-FULL-{int(s//1000)}K",
                    f"Declarante {decl_code} | Mix Completo {s}€ base",
                    decl_tags + ["Mixto", "Completo"],
                    p_full,
                )
            )

    return cases


def generate_salary_thresholds() -> list:
    return [c for c in generate_full_matrix() if "Trabajo" in c.get("category", "")]


def generate_family_cases() -> list:
    return [c for c in generate_full_matrix() if any(t in c.get("category", "") for t in ["Casado", "Monoparental"])]


def generate_deduction_cases() -> list:
    return [c for c in generate_full_matrix() if "Mixto" in c.get("category", "")]


def main():
    output_path = os.path.join(os.path.dirname(__file__), "irpf_oracle_tests.json")

    # 1. Cargar casos existentes para preservar los 'verified'
    existing_verified = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                existing_verified = [c for c in old_data if c.get("status") == "verified"]
        except Exception as e:
            print(f"Aviso: No se pudo cargar el JSON anterior ({e})")

    # 2. Generar nueva matriz de ingresos y declarantes
    nuevos_casos = generate_full_matrix()

    # 3. Unir preservando los verificados (los verificados mandan)
    # Filtramos de los nuevos aquellos que ya estén en verified (por nombre si coincide, aunque el naming cambia)
    # En este caso, como el naming de la matriz es nuevo (INC-...), no habrá colisión directa,
    # pero mantenemos los antiguos SAL-MAD- verified por seguridad.

    final_suite = existing_verified + nuevos_casos

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_suite, f, indent=2, ensure_ascii=False)

    print(f"Exito! Preservados {len(existing_verified)} casos verificados.")
    print(f"Generados {len(nuevos_casos)} nuevos casos con matriz completa de ingresos.")
    print(f"Total: {len(final_suite)} casos en: {output_path}")


if __name__ == "__main__":
    main()
