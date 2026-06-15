# src/tax_compliance/deductions/regional/aragon.py
from decimal import Decimal
from src.domain.fiscal_entities import TaxpayerProfile
from src.tax_compliance.regions.base import BaseRegion


class AragonDeductor:
    """Implementación de las 19 Deducciones Autonómicas de Aragón (Manual Renta 2025/2026)."""

    @classmethod
    def _get_aragon_bi_net(cls, profile: TaxpayerProfile, big: Decimal, bia: Decimal) -> Decimal:
        """Calcula la Base Imponible Neta de Aragón: (BI General + BI Ahorro) - (Mínimo Contribuyente + Mínimo Descendientes)."""
        # Mínimo del Contribuyente
        min_cont = BaseRegion.get_personal_minimum()
        sup_65, sup_75 = BaseRegion.get_age_supplements()
        if profile.age >= 75:
            min_cont += sup_65 + sup_75
        elif profile.age >= 65:
            min_cont += sup_65

        # Mínimo por Descendientes
        min_desc = Decimal("0")
        desc_count = getattr(profile, "descendants_count", 0)
        under3_count = getattr(profile, "children_under_3", 0)

        brackets = [Decimal("2400"), Decimal("2700"), Decimal("4000"), Decimal("4500")]
        for idx in range(desc_count):
            bracket_val = brackets[idx] if idx < len(brackets) else brackets[-1]
            min_desc += bracket_val
            if idx < under3_count:
                min_desc += Decimal("2800")

        if getattr(profile, "custody_shared", False):
            min_desc /= Decimal("2")

        net_bi = (big + bia) - (min_cont + min_desc)
        return max(Decimal("0"), net_bi)

    @classmethod
    def calculate_all(
        cls, profile: TaxpayerProfile, big: Decimal, bia: Decimal, cuota_auton: Decimal = Decimal("0")
    ) -> dict[str, Decimal]:
        deductions = {}
        es_conjunta = getattr(profile, "joint_declaration", False)
        bi_total = big + bia
        bi_net = cls._get_aragon_bi_net(profile, big, bia)
        es_rural = profile.regional_data.get("resides_in_rural_despoblacion", False)

        # 1. ARA01: Por nacimiento o adopción del tercer hijo o sucesivos (Art. 110-2)
        births = getattr(profile, "birth_count_current_year", 0)
        descendants = getattr(profile, "descendants_count", 0)
        if births > 0 and descendants >= 3:
            # Determinamos si aplica el importe general o rural y si tiene incremento por bajo nivel de renta
            limite_renta_alta = Decimal("35000") if es_conjunta else Decimal("21000")
            es_renta_baja = bi_net <= limite_renta_alta

            if es_rural:
                val = Decimal("720") if es_renta_baja else Decimal("600")
            else:
                val = Decimal("600") if es_renta_baja else Decimal("500")

            # Prorrateo si custodia es compartida
            if getattr(profile, "custody_shared", False):
                val /= Decimal("2")

            deductions["ARA01"] = val * births

        # 2. ARA02: Por nacimiento o adopción de hijo con discapacidad >=33% (Art. 110-3)
        # Incompatible con ARA14 para el mismo hijo. Resolvemos incompatibilidad al final.
        val_ara02 = Decimal("0")
        if births > 0 and (
            getattr(profile, "children_disabled_33_65", 0) > 0 or getattr(profile, "children_disabled_over65", 0) > 0
        ):
            val_ara02 = Decimal("240") if es_rural else Decimal("200")
            if getattr(profile, "custody_shared", False):
                val_ara02 /= Decimal("2")
            val_ara02 *= births

        # 3. ARA03: Por adopción internacional (Art. 110-4)
        intl_adoptions = profile.regional_data.get("international_adoption_count", 0)
        if intl_adoptions > 0:
            val = Decimal("720") if es_rural else Decimal("600")
            if getattr(profile, "custody_shared", False):
                val /= Decimal("2")
            deductions["ARA03"] = val * intl_adoptions

        # 4. ARA04: Por el cuidado de personas dependientes (Art. 110-5)
        limite_dep = Decimal("35000") if es_conjunta else Decimal("21000")
        if bi_net <= limite_dep:
            dependents = profile.regional_data.get("dependents_over75_count", 0) + profile.regional_data.get(
                "dependents_disabled_over65_pct_count", 0
            )
            if dependents > 0:
                val = Decimal("300") if es_rural else Decimal("150")
                sharing_taxpayers = profile.regional_data.get("dependent_care_prorated_taxpayers_count", 1)
                val = (val * dependents) / max(Decimal("1"), Decimal(str(sharing_taxpayers)))
                deductions["ARA04"] = val

        # 5. ARA05: Por donaciones con finalidad ecológica/I+D (Art. 110-6)
        donations = profile.regional_data.get("donations_ecological_research_eur", Decimal("0"))
        if donations > 0:
            val = donations * Decimal("0.20")
            # Límite del 10% de la cuota íntegra autonómica
            limite_cuota = cuota_auton * Decimal("0.10")
            val = min(val, limite_cuota)
            if val > 0:
                deductions["ARA05"] = val

        # 6. ARA06: Por adquisición de vivienda habitual por víctimas del terrorismo (Art. 110-7)
        if getattr(profile, "is_victim_violence_gender_or_terrorism", False) and getattr(
            profile, "is_protected_housing", False
        ):
            # 3% de las cantidades satisfechas en vivienda habitual, tope base 9.040€
            inversion = getattr(profile, "rent_paid_annual_eur", Decimal("0"))  # Simulación de inversión
            if inversion > 0:
                base = min(inversion, Decimal("9040"))
                val = base * Decimal("0.03")
                if getattr(profile, "is_shared_ownership", False) and not getattr(profile, "joint_declaration", False):
                    val /= Decimal("2")
                deductions["ARA06"] = val

        # 7. ARA07: Por inversión en acciones de entidades MAB (Art. 110-8)
        mab = profile.regional_data.get("mab_investment_eur", Decimal("0"))
        if mab > 0:
            val = min(mab * Decimal("0.20"), Decimal("10000"))
            deductions["ARA07"] = val

        # 8. ARA08: Por inversión en adquisición de acciones de entidades nuevas/reciente creación (Art. 110-9)
        new_ent = profile.regional_data.get("new_entities_investment_eur", Decimal("0"))
        if new_ent > 100000:
            val = min((new_ent - Decimal("100000")) * Decimal("0.20"), Decimal("4000"))
            deductions["ARA08"] = val

        # 9. ARA09: Por adquisición o rehabilitación de vivienda en núcleos rurales o análogos (Art. 110-10)
        limite_viv_rural = Decimal("35000") if es_conjunta else Decimal("21000")
        if bi_net <= limite_viv_rural and profile.age < 36:
            if profile.regional_data.get("is_first_vivienda_rural", False) and (
                profile.regional_data.get("vivienda_rural_population_under3k", False) or es_rural
            ):
                inversion = getattr(profile, "rent_paid_annual_eur", Decimal("0"))
                if inversion > 0:
                    base = min(inversion, Decimal("9040"))
                    pct = Decimal("0.075") if es_rural else Decimal("0.05")
                    val = base * pct
                    deductions["ARA09"] = val

        # 10. ARA10: Por adquisición de libros de texto y material escolar (Art. 110-11)
        expenses_libros = profile.regional_data.get("school_material_expenses_eur", Decimal("0"))
        grants_libros = profile.regional_data.get("school_material_grants_eur", Decimal("0"))
        gasto_neto_libros = max(Decimal("0"), expenses_libros - grants_libros)

        if descendants > 0 and gasto_neto_libros > 0:
            es_num = (
                getattr(profile, "is_large_family", False)
                or getattr(profile, "large_family_category", "none") != "none"
            )
            # Determinar límite por descendiente
            lim_child = Decimal("0")
            if es_rural:
                if es_conjunta:
                    if es_num:
                        if bi_total <= 40000:
                            lim_child = Decimal("180")
                    else:
                        if bi_total <= 12000:
                            lim_child = Decimal("120")
                        elif bi_total <= 20000:
                            lim_child = Decimal("60")
                        elif bi_total <= 25000:
                            lim_child = Decimal("45")
                else:
                    if es_num:
                        if bi_total <= 30000:
                            lim_child = Decimal("90")
                    else:
                        if bi_total <= 6500:
                            lim_child = Decimal("60")
                        elif bi_total <= 10000:
                            lim_child = Decimal("45")
                        elif bi_total <= 12500:
                            lim_child = Decimal("30")
            else:
                if es_conjunta:
                    if es_num:
                        if bi_total <= 40000:
                            lim_child = Decimal("150")
                    else:
                        if bi_total <= 12000:
                            lim_child = Decimal("100")
                        elif bi_total <= 20000:
                            lim_child = Decimal("50")
                        elif bi_total <= 25000:
                            lim_child = Decimal("37.50")
                else:
                    if es_num:
                        if bi_total <= 30000:
                            lim_child = Decimal("75")
                    else:
                        if bi_total <= 6500:
                            lim_child = Decimal("50")
                        elif bi_total <= 10000:
                            lim_child = Decimal("37.50")
                        elif bi_total <= 12500:
                            lim_child = Decimal("25")

            if getattr(profile, "custody_shared", False):
                lim_child /= Decimal("2")

            val = min(gasto_neto_libros, lim_child * descendants)
            if val > 0:
                deductions["ARA10"] = val

        # 11. ARA11: Por arrendamiento de vivienda habitual por dación en pago (Art. 110-12)
        limite_dacion = Decimal("25000") if es_conjunta else Decimal("15000")
        if bi_total <= limite_dacion:
            rent_dacion = profile.regional_data.get("dacion_en_pago_rent_paid_eur", Decimal("0"))
            if rent_dacion > 0:
                val = min(rent_dacion, Decimal("4800")) * Decimal("0.10")
                deductions["ARA11"] = val

        # 12. ARA12: Por arrendamiento de vivienda social (arrendador) (Art. 110-13)
        social_rent_net = profile.regional_data.get("social_rental_net_income_eur", Decimal("0"))
        if social_rent_net > 0 and big > 0:
            # Cuota íntegra autonómica proporcional al rendimiento neto de capital inmobiliario
            prop_cuota = cuota_auton * (social_rent_net / big)
            prop_cuota = min(prop_cuota, cuota_auton)
            val = prop_cuota * Decimal("0.30")
            if val > 0:
                deductions["ARA12"] = val

        # 13. ARA13: Para mayores de 70 años (Art. 110-14)
        limite_70 = Decimal("35000") if es_conjunta else Decimal("23000")
        if (
            bi_total <= limite_70
            and profile.age >= 70
            and profile.regional_data.get("has_non_capital_general_income", False)
        ):
            deductions["ARA13"] = Decimal("75")

        # 14. ARA14: Por nacimiento/adopción de 1er/2do hijo en poblaciones de menos de 10.000 hab. (Art. 110-16)
        # Incompatible con ARA02 para el mismo hijo. Resolvemos incompatibilidad al final.
        val_ara14 = Decimal("0")
        if (
            births > 0
            and profile.regional_data.get("resides_under10k_population", False)
            and profile.regional_data.get("resided_previous_year_under10k", False)
        ):
            limite_bajo_renta = Decimal("35000") if es_conjunta else Decimal("23000")
            es_renta_baja_ara14 = bi_total <= limite_bajo_renta

            # Prorrateamos de forma análoga a nacimientos comunes
            for idx in range(births):
                hijo_num = descendants - births + idx + 1
                if hijo_num == 1:
                    val_ara14 += Decimal("200") if es_renta_baja_ara14 else Decimal("100")
                elif hijo_num == 2:
                    val_ara14 += Decimal("300") if es_renta_baja_ara14 else Decimal("150")

            if getattr(profile, "custody_shared", False):
                val_ara14 /= Decimal("2")

        # Resolver incompatibilidad ARA02 vs ARA14
        if val_ara02 > 0 and val_ara14 > 0:
            if val_ara02 >= val_ara14:
                deductions["ARA02"] = val_ara02
            else:
                deductions["ARA14"] = val_ara14
        elif val_ara02 > 0:
            deductions["ARA02"] = val_ara02
        elif val_ara14 > 0:
            deductions["ARA14"] = val_ara14

        # 15. ARA15: Por gastos de guardería de menores de 3 años (Art. 110-17)
        limite_guard_total = Decimal("50000") if es_conjunta else Decimal("35000")
        if bi_total <= limite_guard_total and bia <= 4000:
            expenses_guard = getattr(profile, "daycare_expenses_eur", Decimal("0"))
            if expenses_guard > 0:
                under3 = getattr(profile, "children_under_3", 0)
                if under3 > 0:
                    val_guard = expenses_guard * Decimal("0.15")
                    max_guard = Decimal("300") if es_rural else Decimal("250")
                    # Si el menor cumple 3 años en el ejercicio, el límite es la mitad (150€ o 125€)
                    # Para simplificar y dar el máximo beneficio, asumimos el límite completo, pero si la edad es 3 lo bajamos.
                    # Si profile.age == 3, o children_under_3 representa cumpliendo 3 años:
                    if getattr(profile, "children_turning_3", 0) > 0:
                        max_guard /= Decimal("2")

                    if getattr(profile, "custody_shared", False):
                        max_guard /= Decimal("2")

                    val = min(val_guard, max_guard * under3)
                    if val > 0:
                        deductions["ARA15"] = val

        # 16. ARA16: Por inversión en entidades de economía social (Art. 110-19)
        social_inv = profile.regional_data.get("economy_social_investment_eur", Decimal("0"))
        if social_inv > 0:
            val = min(social_inv * Decimal("0.20"), Decimal("4000"))
            deductions["ARA16"] = val

        # 17. ARA17: Por gastos en clases de apoyo o refuerzo (Art. 110-21)
        expenses_apoyo = profile.regional_data.get("school_support_classes_expenses_eur", Decimal("0"))
        grants_apoyo = profile.regional_data.get("school_support_classes_grants_eur", Decimal("0"))
        gasto_neto_apoyo = max(Decimal("0"), expenses_apoyo - grants_apoyo)

        if descendants > 0 and gasto_neto_apoyo > 0:
            # Determinamos límites basados en la misma escala que libros de texto pero con importes dobles
            lim_child_apoyo = Decimal("0")
            es_num = (
                getattr(profile, "is_large_family", False)
                or getattr(profile, "large_family_category", "none") != "none"
            )
            if es_conjunta:
                if es_num:
                    if bi_total <= 40000:
                        lim_child_apoyo = Decimal("300")
                else:
                    if bi_total <= 12000:
                        lim_child_apoyo = Decimal("200")
                    elif bi_total <= 20000:
                        lim_child_apoyo = Decimal("100")
                    elif bi_total <= 25000:
                        lim_child_apoyo = Decimal("80")
            else:
                if es_num:
                    if bi_total <= 30000:
                        lim_child_apoyo = Decimal("300")
                else:
                    if bi_total <= 6500:
                        lim_child_apoyo = Decimal("100")
                    elif bi_total <= 10000:
                        lim_child_apoyo = Decimal("80")
                    elif bi_total <= 12500:
                        lim_child_apoyo = Decimal("50")

            if getattr(profile, "custody_shared", False):
                lim_child_apoyo /= Decimal("2")

            val = min(gasto_neto_apoyo * Decimal("0.25"), lim_child_apoyo * descendants)
            if val > 0:
                deductions["ARA17"] = val

        # 18. ARA18: Por gastos en formación para la autonomía de menores con discapacidad (Art. 110-22)
        expenses_auton = profile.regional_data.get("disabled_child_autonomy_expenses_eur", Decimal("0"))
        grants_auton = profile.regional_data.get("disabled_child_autonomy_grants_eur", Decimal("0"))
        gasto_neto_auton = max(Decimal("0"), expenses_auton - grants_auton)

        if (
            descendants > 0
            and gasto_neto_auton > 0
            and (
                getattr(profile, "children_disabled_33_65", 0) > 0
                or getattr(profile, "children_disabled_over65", 0) > 0
            )
        ):
            lim_child_auton = Decimal("0")
            es_num = (
                getattr(profile, "is_large_family", False)
                or getattr(profile, "large_family_category", "none") != "none"
            )
            if es_conjunta:
                if es_num:
                    if bi_total <= 40000:
                        lim_child_auton = Decimal("300")
                else:
                    if bi_total <= 12000:
                        lim_child_auton = Decimal("200")
                    elif bi_total <= 20000:
                        lim_child_auton = Decimal("100")
                    elif bi_total <= 25000:
                        lim_child_auton = Decimal("80")
            else:
                if es_num:
                    if bi_total <= 30000:
                        lim_child_auton = Decimal("300")
                else:
                    if bi_total <= 6500:
                        lim_child_auton = Decimal("100")
                    elif bi_total <= 10000:
                        lim_child_auton = Decimal("80")
                    elif bi_total <= 12500:
                        lim_child_auton = Decimal("50")

            if getattr(profile, "custody_shared", False):
                lim_child_auton /= Decimal("2")

            val = min(gasto_neto_auton * Decimal("0.25"), lim_child_auton * descendants)
            if val > 0:
                deductions["ARA18"] = val

        # 19. ARA19: Por residencia en determinados municipios en riesgo extremo (Art. 160-2.8)
        if profile.regional_data.get("resides_in_extreme_despoblacion", False):
            limite_res = Decimal("50000") if es_conjunta else Decimal("35000")
            if bi_total <= limite_res and bia <= 4000:
                val = Decimal("1200") if es_conjunta else Decimal("600")
                deductions["ARA19"] = val

        return deductions
