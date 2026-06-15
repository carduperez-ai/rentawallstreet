# src/tax_compliance/deductions/regional/castilla_leon.py
from decimal import Decimal
from typing import List
from src.domain.fiscal_entities import TaxpayerProfile, Deduction


class CastillaLeonDeductor:
    """Implementación de Deducciones Autonómicas de la Comunidad Autónoma de Castilla y León para el ejercicio Renta 2025."""

    @classmethod
    def calculate(cls, profile: TaxpayerProfile, big: Decimal, bia: Decimal, cuota_auton: Decimal) -> List[Deduction]:
        deductions = []
        es_conjunta = getattr(profile, "joint_declaration", False)
        bi_total = big + bia
        coprop = Decimal("2") if getattr(profile, "custody_shared", False) and not es_conjunta else Decimal("1")

        # Mínimo personal y familiar para límites cruzados
        mpf = profile.regional_data.get("minimo_personal_familiar", Decimal("5606"))
        bi_net = bi_total - mpf

        # Límite cruzado de base imponible (18.900 € individual / 31.500 € conjunta)
        limite_renta = Decimal("31500") if es_conjunta else Decimal("18900")

        # --- DEDUCCIONES SIN LÍMITE DE RENTA ---

        # 1. CYL_NUM — Familia numerosa
        # 600€ general, 1500€ 4 desc, 2500€ 5 desc, +1000€ por desc adicional.
        # Incremento +600€ por discapacidad declarante/cónyuge/descendientes >= 65%
        es_fn = getattr(profile, "is_large_family", False)
        desc_count = getattr(profile, "descendants_count", 0)

        if es_fn or desc_count >= 3:
            # Determinamos importe según número de descendientes
            if desc_count <= 3:
                val_base = Decimal("600")
            elif desc_count == 4:
                val_base = Decimal("1500")
            elif desc_count == 5:
                val_base = Decimal("2500")
            else:
                val_base = Decimal("2500") + Decimal("1000") * (desc_count - 5)

            # Incremento por discapacidad >= 65% (declarante, cónyuge o descendientes)
            tiene_discap_65 = (
                getattr(profile, "disability_grade", 0) >= 65
                or getattr(profile, "spouse_disability_grade", 0) >= 65
                or getattr(profile, "children_disabled_over65", 0) > 0
            )
            if tiene_discap_65:
                val_base += Decimal("600")

            val_prorated = val_base / coprop
            deductions.append(Deduction("CYL_NUM", val_prorated.quantize(Decimal("0.01")), "Por familia numerosa"))

        # 2. CYL02 — Nacimiento o adopción
        # 1er: 1.010€ (1.420€ rural) | 2º: 1.475€ (2.070€ rural) | 3º+: 2.351€ (3.300€ rural)
        # Duplicado por discapacidad >= 33% del nacido/adoptado
        births = getattr(profile, "birth_count_current_year", 0)
        if births > 0:
            es_rural = profile.regional_data.get("cyl_rural_municipality_population", 999999) <= 5000
            ord_hijo = desc_count

            if ord_hijo <= 1:
                val_hijo = Decimal("1420") if es_rural else Decimal("1010")
            elif ord_hijo == 2:
                val_hijo = Decimal("2070") if es_rural else Decimal("1475")
            else:
                val_hijo = Decimal("3300") if es_rural else Decimal("2351")

            # Duplicación por discapacidad
            if (
                profile.regional_data.get("cyl_birth_is_disabled", False)
                or profile.regional_data.get("cyl_births_disabled_count", 0) > 0
            ):
                val_hijo *= Decimal("2")

            val_total = val_hijo * births
            val_prorated = val_total / coprop
            deductions.append(
                Deduction("CYL02", val_prorated.quantize(Decimal("0.01")), "Por nacimiento o adopción de hijos")
            )

        # 3. CYL_MUL — Partos o adopciones múltiples
        # 50% de la deducción por nacimiento (2 hijos), 100% (3 o más hijos)
        multiple_count = profile.regional_data.get("cyl_multiple_births_count", 0)
        if multiple_count >= 2:
            es_rural = profile.regional_data.get("cyl_rural_municipality_population", 999999) <= 5000
            # Usamos importe del segundo hijo o tercero según corresponda
            if multiple_count == 2:
                val_ref = Decimal("2070") if es_rural else Decimal("1475")
                porcentaje = Decimal("0.5")
            else:
                val_ref = Decimal("3300") if es_rural else Decimal("2351")
                porcentaje = Decimal("1.0")

            val_mul = val_ref * multiple_count * porcentaje
            val_prorated = val_mul / coprop

            # Adicional: 901€ anuales por partos en 2023 o 2024
            past_multiple = profile.regional_data.get("cyl_multiple_births_past_years_count", 0)
            if past_multiple > 0:
                val_prorated += (Decimal("901") * past_multiple) / coprop

            deductions.append(
                Deduction("CYL_MUL", val_prorated.quantize(Decimal("0.01")), "Por partos o adopciones múltiples")
            )
        elif profile.regional_data.get("cyl_multiple_births_past_years_count", 0) > 0:
            past_multiple = profile.regional_data.get("cyl_multiple_births_past_years_count", 0)
            val_prorated = (Decimal("901") * past_multiple) / coprop
            deductions.append(
                Deduction("CYL_MUL", val_prorated.quantize(Decimal("0.01")), "Por partos múltiples en años anteriores")
            )

        # 4. CYL_ADOP — Gastos de adopción
        # 784€ por hijo adoptado nacionalmente, 3.625€ internacional
        adoptions = profile.regional_data.get("cyl_adoptions_count", 0)
        if adoptions > 0:
            es_internac = profile.regional_data.get("cyl_adoption_international", False)
            val_adop = Decimal("3625") if es_internac else Decimal("784")
            val_total = val_adop * adoptions
            val_prorated = val_total / coprop
            deductions.append(Deduction("CYL_ADOP", val_prorated.quantize(Decimal("0.01")), "Por gastos de adopción"))

        # --- DEDUCCIONES SUJETAS A LÍMITE DE RENTA ---
        if bi_net <= limite_renta:
            # 5. CYL_CUID — Cuidado de hijos menores (incompatibles en el mismo gasto)
            # a) Empleado de hogar: 30% de cantidades, limite 322€
            # b) Guarderías: 100% de matrícula, limite 1.320€ minus maternidad estatal
            daycare = profile.regional_data.get("cyl_daycare_expenses_eur", Decimal("0"))
            empleada = profile.regional_data.get("cyl_domestic_employee_ss_employer_eur", Decimal("0"))

            if (daycare > 0 or empleada > 0) and desc_count > 0:
                val_daycare = daycare  # 100%
                lim_daycare = Decimal("1320")

                val_empl = empleada * Decimal("0.30")
                lim_empl = Decimal("322")

                # Elegimos la más beneficiosa
                ded_cuid_daycare = min(val_daycare, lim_daycare)
                ded_cuid_empl = min(val_empl, lim_empl)
                val_max = max(ded_cuid_daycare, ded_cuid_empl)

                val_prorated = val_max / coprop
                if val_prorated > 0:
                    deductions.append(
                        Deduction("CYL_CUID", val_prorated.quantize(Decimal("0.01")), "Por cuidado de hijos menores")
                    )

            # 6. CYL_HOG — Cuotas a la SS de empleados del hogar
            # 15% cuotas satisfechas, límite 300€
            hogar_ss = profile.regional_data.get("cyl_domestic_employee_ss_home_eur", Decimal("0"))
            if hogar_ss > 0 and desc_count > 0:
                val_hog = hogar_ss * Decimal("0.15")
                val_capped = min(val_hog, Decimal("300"))
                val_prorated = val_capped / coprop
                if val_prorated > 0:
                    deductions.append(
                        Deduction(
                            "CYL_HOG",
                            val_prorated.quantize(Decimal("0.01")),
                            "Por cuotas a la SS de empleados de hogar",
                        )
                    )

            # 7. CYL_DISC — Contribuyentes con discapacidad
            # 300€ si >= 65 años con disc 33-65% | 656€ si >= 65 años disc >= 65% | 300€ si < 65 años disc >= 65%
            # Requisito: no residir en centros públicos
            discap_grade = getattr(profile, "disability_grade", 0)
            reside_publico = profile.regional_data.get("cyl_disability_resides_public_center", False)
            age = profile.age

            if discap_grade >= 33 and not reside_publico:
                val_disc = Decimal("0")
                if age >= 65:
                    val_disc = Decimal("656") if discap_grade >= 65 else Decimal("300")
                else:
                    if discap_grade >= 65:
                        val_disc = Decimal("300")

                if val_disc > 0:
                    # Esta deducción no se prorratea al ser individual del contribuyente
                    deductions.append(
                        Deduction("CYL_DISC", val_disc.quantize(Decimal("0.01")), "Por discapacidad del contribuyente")
                    )

            # 8. CYL_VIV_RURAL — Adquisición o rehabilitación de vivienda por jóvenes en medio rural
            # 15% de inversión, base máx 10.000€
            v_rural_exp = profile.regional_data.get("cyl_vivienda_rural_acquisition_rehab_expenses_eur", Decimal("0"))
            if v_rural_exp > 0 and age < 36:
                es_primera = profile.regional_data.get("cyl_vivienda_rural_is_first", True)
                valor_casa = profile.regional_data.get("cyl_vivienda_rural_value_eur", Decimal("0"))

                # Requisito de primera vivienda y precio menor de 150.000€
                if es_primera and valor_casa < Decimal("150000"):
                    val_inv = min(v_rural_exp, Decimal("10000")) * Decimal("0.15")
                    val_prorated = val_inv / coprop
                    if val_prorated > 0:
                        deductions.append(
                            Deduction(
                                "CYL_VIV_RURAL",
                                val_prorated.quantize(Decimal("0.01")),
                                "Adquisición/Rehabilitación de vivienda por jóvenes en medio rural",
                            )
                        )

            # 9. CYL01 — Arrendamiento de vivienda habitual por jóvenes
            # 20% (cap 459€) o 25% (cap 612€ rural)
            if (
                getattr(profile, "is_rent_habitual", False)
                and getattr(profile, "rent_paid_annual_eur", Decimal("0")) > 0
                and age < 36
            ):
                poblacion = profile.regional_data.get("cyl_rural_municipality_population", 999999)
                distancia = profile.regional_data.get("cyl_rural_municipality_distance_capital_km", 999)

                # Condición rural: población <= 10.000 hab, o <= 3.000 hab a menos de 30 km de la capital
                es_rural = (poblacion <= 10000) or (poblacion <= 3000 and distancia < 30)

                pct = Decimal("0.25") if es_rural else Decimal("0.20")
                tope = Decimal("612") if es_rural else Decimal("459")

                val_rent = min(profile.rent_paid_annual_eur * pct, tope)
                val_prorated = val_rent / coprop
                if val_prorated > 0:
                    deductions.append(
                        Deduction(
                            "CYL01",
                            val_prorated.quantize(Decimal("0.01")),
                            "Por arrendamiento de vivienda habitual por jóvenes",
                        )
                    )

        return deductions
