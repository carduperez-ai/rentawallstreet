# src/tax_compliance/deductions/regional/cantabria.py
from decimal import Decimal
from typing import List
from src.domain.fiscal_entities import TaxpayerProfile, Deduction


class CantabriaDeductor:
    """Implementación de Deducciones Autonómicas de la Comunidad Autónoma de Cantabria para el ejercicio 2025."""

    @classmethod
    def calculate(cls, profile: TaxpayerProfile, big: Decimal, bia: Decimal, cuota_auton: Decimal) -> List[Deduction]:
        deductions = []
        es_conjunta = getattr(profile, "joint_declaration", False)
        bi_total = big + bia

        # Mínimo personal y familiar para el cálculo de límites de renta
        mpf = profile.regional_data.get("minimum_personal_familiar", Decimal("0"))
        if mpf == 0:
            mpf = profile.regional_data.get("minimo_personal_familiar", Decimal("0"))

        # Base de cálculo para límites de renta
        base_limite_renta = bi_total - mpf

        # Incompatibilidades a nivel de vivienda e hijos para evitar duplicidades
        applied_alq_desp = False
        applied_guard_desp = {}

        # 11. CTB_ALQ_DESP: Por arrendamiento de vivienda habitual en municipios con riesgo de despoblamiento (Art 2.11.1)
        rent_desp = profile.regional_data.get("cantabria_rent_despoblacion_paid_eur", Decimal("0"))
        if rent_desp > 0:
            pct_val = rent_desp * Decimal("0.20")
            limit_taxpayer = Decimal("1200") if es_conjunta else Decimal("600")
            val = min(pct_val, limit_taxpayer)
            if val > 0:
                deductions.append(
                    Deduction(
                        "CTB_ALQ_DESP",
                        val.quantize(Decimal("0.01")),
                        "Alquiler en municipios con riesgo de despoblamiento",
                    )
                )
                applied_alq_desp = True

        # 1. CTB_ALQ: Por arrendamiento de vivienda habitual por jóvenes, mayores y personas con discapacidad (Art 2.1)
        if not applied_alq_desp:
            rent_paid = getattr(profile, "rent_paid_annual_eur", Decimal("0"))
            age = profile.age
            discap = getattr(profile, "disability_grade", 0)
            if rent_paid > 0 and (age < 36 or age >= 65 or discap >= 65):
                # Debe superar el 10% de la renta del contribuyente (bi_total)
                if rent_paid > bi_total * Decimal("0.10"):
                    pct_val = rent_paid * Decimal("0.10")
                    limit_taxpayer = Decimal("600") if es_conjunta else Decimal("300")
                    val = min(pct_val, limit_taxpayer)
                    if val > 0:
                        deductions.append(
                            Deduction(
                                "CTB_ALQ", val.quantize(Decimal("0.01")), "Arrendamiento de vivienda habitual general"
                            )
                        )

        # 10. CTB_NAC: Por nacimiento o adopción de hijos (Art 2.10)
        applied_births_count = 0
        if base_limite_renta < Decimal("31485"):
            births = getattr(profile, "birth_count_current_year", 0)
            if births > 0:
                # 1.400 € por hijo. En individual se prorratea al 50% = 700€ por hijo.
                coprop = Decimal("2") if getattr(profile, "custody_shared", False) and not es_conjunta else Decimal("1")
                val = (Decimal("1400") * births) / coprop
                if val > 0:
                    deductions.append(
                        Deduction("CTB_NAC", val.quantize(Decimal("0.01")), "Nacimiento o adopción de hijos")
                    )
                    applied_births_count = births

        # 2. CTB_CUID: Por cuidado de familiares (Art 2.2)
        # 100 € por cada familiar conviviente (>183 días) que cumpla:
        # - descendiente < 3 años
        # - ascendiente > 70 años
        # - familiar con discapacidad >= 65%
        # Incompatible con CTB_NAC para el mismo hijo, salvo si es < 3 años con discapacidad >= 65%
        # Para simplificar y dar precisión, permitimos indicar las condiciones de familiares
        cuid_count = 0
        desc_under_3 = getattr(profile, "children_under_3", 0)
        desc_under_3_disabled_65 = profile.regional_data.get("cantabria_descendants_under_3_disabled_65_count", 0)

        # Hijos menores de 3 años
        for i in range(desc_under_3):
            # Si se aplicó deducción por nacimiento/adopción para este hijo en este año, es incompatible
            # salvo si tiene discapacidad >= 65%
            if applied_births_count > 0:
                if i < desc_under_3_disabled_65:
                    # Cumple doble condición: menor de 3 años (100€) + discapacidad >= 65% (100€)
                    cuid_count += 2
                # Si no tiene discapacidad, está excluido por nacimiento
            else:
                # No se aplicó nacimiento, se aplica cuidado de familiar (100€)
                if i < desc_under_3_disabled_65:
                    cuid_count += 2
                else:
                    cuid_count += 1

        # Ascendientes > 70 años y familiares con discapacidad
        cuid_asc_70 = profile.regional_data.get("cantabria_ascendants_over_70_count", 0)
        cuid_discap_65 = profile.regional_data.get("cantabria_family_disabled_65_count", 0)
        cuid_count += cuid_asc_70 + cuid_discap_65

        if cuid_count > 0:
            coprop = Decimal("1") if es_conjunta else Decimal("2")
            val = (Decimal("100") * cuid_count) / coprop
            if val > 0:
                deductions.append(Deduction("CTB_CUID", val.quantize(Decimal("0.01")), "Cuidado de familiares"))

        # 3. CTB_MEJ: Por obras de mejora (Art 2.3)
        exp_mej = profile.regional_data.get("cantabria_home_improvement_expenses_eur", Decimal("0"))
        prev_unused = profile.regional_data.get("cantabria_home_improvement_prev_unused_eur", Decimal("0"))
        if exp_mej > 0 or prev_unused > 0:
            pct_val = exp_mej * Decimal("0.15") + prev_unused
            discap_members = profile.regional_data.get("cantabria_home_improvement_disabled_members_count", 0)

            limit_base = Decimal("1500") if es_conjunta else Decimal("1000")
            limit_increment = Decimal("500") * discap_members
            limit_total = limit_base + limit_increment

            val = min(pct_val, limit_total)
            if val > 0:
                deductions.append(
                    Deduction("CTB_MEJ", val.quantize(Decimal("0.01")), "Obras de mejora en viviendas de su propiedad")
                )

        # 4. CTB_DON: Por donativos a fundaciones, Fondo Cantabria Coopera o apoyo a discapacidad (Art 2.4)
        don_foundations = profile.regional_data.get("cantabria_donations_foundations_eur", Decimal("0"))
        don_coopera = profile.regional_data.get("cantabria_donations_coopera_eur", Decimal("0"))
        don_disabled = profile.regional_data.get("cantabria_donations_disabled_support_eur", Decimal("0"))

        if don_foundations > 0 or don_coopera > 0 or don_disabled > 0:
            raw_ded = don_foundations * Decimal("0.15") + don_coopera * Decimal("0.12") + don_disabled * Decimal("0.15")
            # Límite conjunto del 10% de la base liquidable general y del ahorro
            limit_bl = bi_total * Decimal("0.10")
            val = min(raw_ded, limit_bl)
            if val > 0:
                deductions.append(
                    Deduction(
                        "CTB_DON", val.quantize(Decimal("0.01")), "Donativos a fundaciones o apoyo a discapacidad"
                    )
                )

        # 5. CTB_ACOG: Por acogimiento familiar de menores (Art 2.5)
        foster_count = profile.regional_data.get("cantabria_foster_care_minors_count", 0)
        if foster_count > 0:
            raw_ded = Decimal("240") * foster_count
            limit_max = Decimal("1200")
            coprop = Decimal("1") if es_conjunta else Decimal("2")
            val = min(raw_ded, limit_max) / coprop
            if val > 0:
                deductions.append(
                    Deduction("CTB_ACOG", val.quantize(Decimal("0.01")), "Acogimiento familiar de menores")
                )

        # 6. CTB_ACC: Por inversión en la adquisición de acciones de nuevas entidades (Art 2.6)
        inv_new = profile.regional_data.get("cantabria_new_entities_investment_eur", Decimal("0"))
        if inv_new > 0:
            pct_val = inv_new * Decimal("0.15")
            limit_taxpayer = Decimal("1000")
            val = min(pct_val, limit_taxpayer)
            if val > 0:
                deductions.append(
                    Deduction(
                        "CTB_ACC",
                        val.quantize(Decimal("0.01")),
                        "Inversión en adquisición de acciones de nuevas entidades",
                    )
                )

        # 7. CTB_ENF: Por gastos de enfermedad (Art 2.7)
        limite_enf = Decimal("31485") if es_conjunta else Decimal("22946")
        if base_limite_renta < limite_enf:
            exp_enf = profile.regional_data.get("cantabria_health_expenses_eur", Decimal("0"))
            if exp_enf > 0:
                pct_val = exp_enf * Decimal("0.10")

                # Incremento de límite por discapacidad >= 65%
                discap_grade = getattr(profile, "disability_grade", 0)
                is_disabled = discap_grade >= 65

                # Para conjunta, consideramos si el declarante o cónyuge tienen discapacidad >= 65%
                # Usamos una variable auxiliar cantabria_home_improvement_disabled_members_count o similar para simplificar
                discap_count = 1 if is_disabled else 0
                if es_conjunta:
                    # En conjunta sumamos si hay cónyuge discapacitado
                    has_spouse_disabled = profile.regional_data.get("spouse_disabled_65", False)
                    if has_spouse_disabled:
                        discap_count += 1

                limit_base = Decimal("700") if es_conjunta else Decimal("500")
                limit_increment = Decimal("100") * discap_count
                limit_total = limit_base + limit_increment

                val = min(pct_val, limit_total)
                if val > 0:
                    deductions.append(
                        Deduction("CTB_ENF", val.quantize(Decimal("0.01")), "Gastos de enfermedad y aparatos médicos")
                    )

        # 12. CTB_GUARD_DESP: Por guarderías en municipios con riesgo de despoblamiento (Art 2.11.2)
        guard_desp = profile.regional_data.get("cantabria_guarderia_despoblacion_expenses_eur", Decimal("0"))
        if guard_desp > 0:
            kids = profile.regional_data.get("cantabria_guarderia_kids_count", 0)
            if kids > 0:
                pct_val = guard_desp * Decimal("0.30")
                limit_max = Decimal("600") * kids
                coprop = Decimal("1") if es_conjunta else Decimal("2")
                val = min(pct_val, limit_max) / coprop
                if val > 0:
                    deductions.append(
                        Deduction(
                            "CTB_GUARD_DESP",
                            val.quantize(Decimal("0.01")),
                            "Gastos de guardería en municipios con riesgo de despoblamiento",
                        )
                    )
                    applied_guard_desp = True

        # 8. CTB_GUARD: Por gastos de guardería (Art 2.8)
        if not applied_guard_desp:
            guard_gen = profile.regional_data.get("cantabria_guarderia_expenses_eur", Decimal("0"))
            if guard_gen > 0:
                kids = profile.regional_data.get("cantabria_guarderia_kids_count", 0)
                if kids > 0:
                    pct_val = guard_gen * Decimal("0.15")
                    limit_max = Decimal("300") * kids
                    coprop = Decimal("1") if es_conjunta else Decimal("2")
                    val = min(pct_val, limit_max) / coprop
                    if val > 0:
                        deductions.append(
                            Deduction("CTB_GUARD", val.quantize(Decimal("0.01")), "Gastos de guardería general")
                        )

        # 9. CTB_MONO: Para familias monoparentales (Art 2.9)
        if profile.regional_data.get("cantabria_is_monoparental", False):
            if base_limite_renta < Decimal("31485"):
                deductions.append(Deduction("CTB_MONO", Decimal("200.00"), "Familias monoparentales"))

        # 13. CTB_TRAS_DESP: Por trasladar la residencia a un municipio con riesgo de despoblamiento por motivos laborales (Art 2.11.3)
        if profile.regional_data.get("cantabria_relocation_despoblacion_motivos_laborales", False):
            year_of_transfer = profile.regional_data.get("cantabria_relocation_despoblacion_year_of_transfer", 2025)
            if year_of_transfer in (2024, 2025):
                # 500 € por contribuyente con derecho. En conjunta, si ambos se trasladan, son 1.000 €.
                num_contribuyentes = (
                    2 if (es_conjunta and profile.regional_data.get("spouse_relocation_laboral", False)) else 1
                )
                val = Decimal("500") * num_contribuyentes

                # Límite: no puede superar la cuota íntegra autonómica de rendimientos del trabajo y act. económicas
                # Para simplificar de forma segura, el límite máximo es cuota_auton
                val = min(val, cuota_auton)
                if val > 0:
                    deductions.append(
                        Deduction(
                            "CTB_TRAS_DESP",
                            val.quantize(Decimal("0.01")),
                            "Traslado de residencia por motivos laborales a municipio despoblado",
                        )
                    )

        # 14. CTB_EST_DESP: Por gastos de traslado por estudios desde municipios con riesgo de despoblamiento (Art 2.11.4)
        studying_count = profile.regional_data.get("cantabria_descendants_studying_outside_despoblacion_count", 0)
        if studying_count > 0:
            coprop = Decimal("1") if es_conjunta else Decimal("2")
            val = (Decimal("200") * studying_count) / coprop
            if val > 0:
                deductions.append(
                    Deduction(
                        "CTB_EST_DESP",
                        val.quantize(Decimal("0.01")),
                        "Gastos de traslado por estudios desde municipios despoblados",
                    )
                )

        # 15. CTB_RES_DESP: Por residencia habitual en municipios con riesgo de despoblamiento (Art 2.11.5)
        # Menor de 40 años al devengo
        if profile.regional_data.get("cantabria_residence_despoblacion_active", False) and profile.age < 40:
            # 20% de la cuota íntegra autonómica con límite de 500€ por contribuyente.
            pct_val = cuota_auton * Decimal("0.20")
            num_contribuyentes = (
                2
                if (
                    es_conjunta
                    and profile.regional_data.get("spouse_residence_despoblacion_active", False)
                    and profile.regional_data.get("spouse_age", 40) < 40
                )
                else 1
            )
            limit_total = Decimal("500") * num_contribuyentes
            val = min(pct_val, limit_total)
            if val > 0:
                deductions.append(
                    Deduction(
                        "CTB_RES_DESP",
                        val.quantize(Decimal("0.01")),
                        "Residencia habitual en municipio con riesgo de despoblamiento",
                    )
                )

        # 16. CTB_ECO_SOC: Por inversiones o donaciones a entidades de la Economía Social (Art 2.12)
        apport_socio = profile.regional_data.get("cantabria_economy_social_apport_socio_eur", Decimal("0"))
        don_dev = profile.regional_data.get("cantabria_economy_social_donations_development_eur", Decimal("0"))
        don_fom = profile.regional_data.get("cantabria_economy_social_donations_fomento_eur", Decimal("0"))

        if apport_socio > 0 or don_dev > 0 or don_fom > 0:
            raw_ded = apport_socio * Decimal("0.20") + don_dev * Decimal("0.50") + don_fom * Decimal("0.25")
            limit_total = Decimal("3000")
            val = min(raw_ded, limit_total)
            if val > 0:
                deductions.append(
                    Deduction(
                        "CTB_ECO_SOC",
                        val.quantize(Decimal("0.01")),
                        "Inversiones/donaciones a entidades de Economía Social",
                    )
                )

        # 17. CTB_EDUC: Por gastos de educación (Art 2.13)
        edu_books = profile.regional_data.get("cantabria_education_books_expenses_eur", Decimal("0"))
        edu_languages = profile.regional_data.get("cantabria_education_languages_expenses_eur", Decimal("0"))

        if edu_books > 0 or edu_languages > 0:
            raw_ded = edu_books + edu_languages * Decimal("0.15")
            # Límite conjunto de 200€ por unidad familiar. En individual se prorratea al 50% = 100€.
            coprop = Decimal("1") if es_conjunta else Decimal("2")
            limit_prop = Decimal("200") / coprop
            val = min(raw_ded, limit_prop)
            if val > 0:
                deductions.append(
                    Deduction("CTB_EDUC", val.quantize(Decimal("0.01")), "Gastos de educación (libros e idiomas)")
                )

        # 18. CTB_DOM: Por ayuda doméstica (Art 2.14)
        dom_ss = profile.regional_data.get("cantabria_domestic_employee_ss_eur", Decimal("0"))
        is_employer = profile.regional_data.get("cantabria_domestic_employee_is_employer", False)

        if dom_ss > 0 and is_employer:
            # Requisitos:
            # 1. Contribuyente + cónyuge tengan hijos menores + ambos trabajen
            # 2. Monoparental + trabaje
            # 3. Edad del contribuyente >= 75 años
            has_kids = profile.regional_data.get("cantabria_domestic_employee_has_kids", False)
            both_work = profile.regional_data.get("cantabria_domestic_employee_both_work", False)
            is_monoparental = profile.regional_data.get("cantabria_is_monoparental", False)
            age_75 = profile.age >= 75

            if (has_kids and both_work and getattr(profile, "descendants_count", 0) > 0) or is_monoparental or age_75:
                pct_val = dom_ss * Decimal("0.20")
                limit_total = Decimal("300")
                coprop = Decimal("1") if es_conjunta else Decimal("2")
                val = min(pct_val, limit_total) / coprop
                if val > 0:
                    deductions.append(
                        Deduction("CTB_DOM", val.quantize(Decimal("0.01")), "Ayuda doméstica por empleados del hogar")
                    )

        # 19. CTB_EXTR: Por inversiones de nuevos contribuyentes procedentes del extranjero (Art 2.15)
        inv_extr = profile.regional_data.get("cantabria_new_residents_foreign_investment_eur", Decimal("0"))
        offset_extr = profile.regional_data.get(
            "cantabria_new_residents_foreign_investment_offset_prev_eur", Decimal("0")
        )

        if inv_extr > 0 or offset_extr > 0:
            pct_val = inv_extr * Decimal("0.20") + offset_extr
            # No hay un límite explícito de cuantía anual, sino sujeto a la cuota íntegra. El sobrante se compensa.
            val = min(pct_val, cuota_auton)
            if val > 0:
                deductions.append(
                    Deduction(
                        "CTB_EXTR",
                        val.quantize(Decimal("0.01")),
                        "Inversiones de nuevos residentes procedentes del extranjero",
                    )
                )

        # 20. CTB_DESP_RES: Para compensar gastos de desplazamiento y permanencia de nuevos residentes (Art 2.16)
        reloc_expenses = profile.regional_data.get("cantabria_new_residents_relocation_expenses_eur", Decimal("0"))
        if reloc_expenses > 0:
            is_labor = profile.regional_data.get("cantabria_new_residents_relocation_is_labor_motivated", False)

            # En conjunta se permite duplicar los límites si ambos cónyuges tienen derecho
            num_contribuyentes = (
                2 if (es_conjunta and profile.regional_data.get("spouse_new_resident_relocation", False)) else 1
            )

            if is_labor:
                pct_val = reloc_expenses * Decimal("0.25")
                limit_total = Decimal("1500") * num_contribuyentes
            else:
                pct_val = reloc_expenses * Decimal("0.10")
                limit_total = Decimal("1000") * num_contribuyentes

            val = min(pct_val, limit_total)
            if val > 0:
                deductions.append(
                    Deduction(
                        "CTB_DESP_RES",
                        val.quantize(Decimal("0.01")),
                        "Compensación de gastos por desplazamiento de nuevos residentes",
                    )
                )

        # 21. CTB_VAC: Por el arrendamiento de viviendas vacías (Art 2.17)
        empty_count = profile.regional_data.get("cantabria_empty_properties_rent_count", 0)
        if empty_count > 0:
            ownership_list = profile.regional_data.get("cantabria_empty_properties_rent_ownership_pct", [])
            total_ded = Decimal("0")
            for i in range(empty_count):
                pct_own = ownership_list[i] if i < len(ownership_list) else Decimal("100")
                ded_vivienda = Decimal("500") * (pct_own / Decimal("100"))
                total_ded += ded_vivienda

            if total_ded > 0:
                deductions.append(
                    Deduction("CTB_VAC", total_ded.quantize(Decimal("0.01")), "Arrendamiento de viviendas vacías")
                )

        return deductions
