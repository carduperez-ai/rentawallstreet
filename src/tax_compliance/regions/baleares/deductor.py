# src/tax_compliance/deductions/regional/baleares.py
from decimal import Decimal
from typing import List
from src.domain.fiscal_entities import TaxpayerProfile, Deduction


class BalearsDeductor:
    """Implementación de Deducciones Autonómicas de Illes Balears para el ejercicio 2025."""

    @classmethod
    def calculate(cls, profile: TaxpayerProfile, big: Decimal, bia: Decimal, cuota_auton: Decimal) -> List[Deduction]:
        deductions = []
        es_conjunta = getattr(profile, "joint_declaration", False)
        bi_total = big + bia

        # Definición de límites transversales de base imponible cruzada (BIG + BIA)
        limite_general = Decimal("52800") if es_conjunta else Decimal("33000")

        # Categorías de familias numerosas / monoparentales
        es_monoparental = getattr(profile, "is_monoparental", False)
        es_numerosa = getattr(profile, "is_large_family", False)
        large_family_category = getattr(profile, "large_family_category", "")
        es_numerosa_especial = large_family_category == "special" or getattr(profile, "is_large_family_special", False)

        # Monoparentales con 2+ hijos
        conciliacion_kids = profile.regional_data.get("balears_conciliacion_kids_count", 0)
        es_monoparental_2_kids = es_monoparental and (
            conciliacion_kids >= 2 or getattr(profile, "descendants_count", 0) >= 2
        )

        if es_numerosa_especial:
            limite_bi_cruzado = Decimal("68640") if es_conjunta else Decimal("42900")
        elif es_numerosa or es_monoparental_2_kids:
            limite_bi_cruzado = Decimal("63360") if es_conjunta else Decimal("39600")
        else:
            limite_bi_cruzado = limite_general

        # Colectivos Especiales para Alquiler, Libros de texto, Conciliación
        es_menor_30 = profile.age < 30
        es_menor_36 = profile.age < 36
        es_mayor_65 = profile.age > 65
        es_discapacitado_33 = profile.disability_grade >= 33 or profile.regional_data.get(
            "balears_is_disabled_member", False
        )
        es_discapacitado_psiquica_33 = profile.regional_data.get("balears_is_disabled_member_psiquica", False)
        es_autonomo_183_dias = profile.regional_data.get(
            "balears_autoocupacion_mantenimiento_un_ano", False
        ) or profile.regional_data.get("is_autonomo", False)

        tiene_derecho_minimo_discapacidad = (
            profile.disability_grade >= 33
            or getattr(profile, "children_disabled_over65", 0) > 0
            or getattr(profile, "ascendants_disabled_count", 0) > 0
            or profile.regional_data.get("descendants_disabled_count", 0) > 0
        )

        es_colectivo_b = (
            es_menor_30
            or es_discapacitado_33
            or tiene_derecho_minimo_discapacidad
            or es_numerosa
            or es_monoparental_2_kids
            or es_autonomo_183_dias
        )

        # 1. BAL01: Alquiler de vivienda habitual (Art. 3 bis)
        if bi_total <= limite_bi_cruzado:
            if (
                getattr(profile, "is_rent_habitual", False)
                and getattr(profile, "rent_paid_annual_eur", Decimal("0")) > 0
            ):
                gasto = profile.rent_paid_annual_eur
                if es_colectivo_b:
                    porcentaje = Decimal("0.20")
                    limite_max = Decimal("650")
                elif es_menor_36 or (es_mayor_65 and not profile.regional_data.get("has_employment_income", False)):
                    porcentaje = Decimal("0.15")
                    limite_max = Decimal("530")
                else:
                    porcentaje = Decimal("0")
                    limite_max = Decimal("0")

                val = min(gasto * porcentaje, limite_max)
                if val > 0:
                    deductions.append(Deduction("BAL01", val, "Alquiler Vivienda Habitual"))

        # 2. BAL02: Inversión mejora sostenibilidad vivienda habitual (Art. 3)
        if bi_total <= limite_general:
            inversion_sost = profile.regional_data.get("balears_vivienda_sostenible_eur", Decimal("0"))
            if inversion_sost > 0:
                val = min(inversion_sost * Decimal("0.50"), Decimal("5000"))
                if val > 0:
                    deductions.append(Deduction("BAL02", val, "Inversión Sostenibilidad Vivienda Habitual"))

        # 3. BAL03: Subvenciones zona catastrófica (Art. 3 ter)
        subv_catastrofe = profile.regional_data.get("balears_vivienda_sostenible_eur", Decimal("0"))
        if hasattr(profile, "balears_subvencion_catastrofe_eur"):
            subv_catastrofe = profile.regional_data.get("balears_subvencion_catastrofe_eur", Decimal("0"))
        if subv_catastrofe > 0:
            tipo_medio = (cuota_auton / big) if big > 0 else Decimal("0.15")
            deductions.append(
                Deduction(
                    "BAL03",
                    (subv_catastrofe * tipo_medio).quantize(Decimal("0.01")),
                    "Subvenciones por Zona Afectada por Emergencia",
                )
            )

        # 4. BAL04: Adquisición de libros de texto (Art. 4)
        if bi_total <= limite_bi_cruzado:
            libros_gastos = profile.regional_data.get("balears_books_expenses_eur", Decimal("0"))
            if libros_gastos > 0:
                hijos = getattr(profile, "descendants_count", 0)
                if hijos > 0:
                    lim_por_hijo = Decimal("350") if es_colectivo_b else Decimal("220")
                    coprop = (
                        Decimal("2")
                        if (not es_conjunta and getattr(profile, "custody_shared", False))
                        else Decimal("1")
                    )
                    val_calc = min(libros_gastos, (lim_por_hijo * hijos) / coprop)
                    if val_calc > 0:
                        deductions.append(Deduction("BAL04", val_calc, "Adquisición de Libros de Texto"))

        # 5. BAL05: Idiomas extranjeros extraescolares (Art. 4 bis)
        if bi_total <= limite_general:
            idiomas_gastos = profile.regional_data.get("balears_languages_expenses_eur", Decimal("0"))
            if idiomas_gastos > 0:
                hijos = getattr(profile, "descendants_count", 0)
                if hijos > 0:
                    coprop = (
                        Decimal("2")
                        if (not es_conjunta and getattr(profile, "custody_shared", False))
                        else Decimal("1")
                    )
                    val_calc = min(idiomas_gastos * Decimal("0.15"), (Decimal("110") * hijos) / coprop)
                    if val_calc > 0:
                        deductions.append(Deduction("BAL05", val_calc, "Aprendizaje de Idiomas Extranjeros"))

        # 6. BAL06: Estudios de educación superior fuera de la isla (Art. 4 ter)
        if bi_total <= limite_general:
            estudios_fuera = profile.regional_data.get("balears_study_outside_count", 0)
            if estudios_fuera > 0:
                coprop = (
                    Decimal("2") if (not es_conjunta and getattr(profile, "custody_shared", False)) else Decimal("1")
                )
                val_total = (Decimal("1800") * estudios_fuera) / coprop
                val_total = min(val_total, cuota_auton * Decimal("0.50"))
                if val_total > 0:
                    deductions.append(Deduction("BAL06", val_total, "Estudios Superiores Fuera de la Isla"))

        # 7. BAL07: Arrendador - Seguros de impago de alquiler (Art. 4 quater.1)
        limite_arrendador = Decimal("84480") if es_conjunta else Decimal("52800")
        if bi_total <= limite_arrendador:
            primas_seguro = profile.regional_data.get("balears_landlord_insurance_expenses_eur", Decimal("0"))
            if primas_seguro > 0:
                val = min(primas_seguro * Decimal("0.75"), Decimal("440"))
                if val > 0:
                    deductions.append(Deduction("BAL07", val, "Seguro de Impago de Alquiler"))

        # 8. BAL08: Arrendador - Gastos de conservación y sostenibilidad (Art. 4 quater.2)
        if bi_total <= limite_arrendador:
            otros_gastos_arr = profile.regional_data.get("balears_landlord_other_expenses_eur", Decimal("0"))
            if otros_gastos_arr > 0 and profile.regional_data.get("balears_is_landlord_first_year", False):
                limite_max = (
                    Decimal("1800")
                    if profile.regional_data.get("balears_landlord_is_ibavi", False)
                    else Decimal("1500")
                )
                val = min(otros_gastos_arr * Decimal("0.50"), limite_max)
                if val > 0:
                    deductions.append(Deduction("BAL08", val, "Gastos de Conservación de Vivienda Alquilada"))

        # 9. BAL09: Traslado temporal por motivos laborales (Art. 4 quinquies)
        if bi_total <= limite_general:
            traslado_alquiler = profile.regional_data.get("balears_relocation_rent_eur", Decimal("0"))
            years_active = profile.regional_data.get("balears_relocation_years_active", 0)
            if traslado_alquiler > 0 and years_active <= 3:
                val = min(traslado_alquiler * Decimal("0.15"), Decimal("440"))
                if val > 0:
                    deductions.append(Deduction("BAL09", val, "Traslado Temporal por Motivos Laborales"))

        # 10. BAL10: Gastos de vivienda ocupada ilegalmente (Art. 4 sexties)
        if bi_total <= limite_general:
            gastos_ocupado = profile.regional_data.get("balears_illegal_occupied_expenses_eur", Decimal("0"))
            if gastos_ocupado > 0:
                val = min(gastos_ocupado * Decimal("0.40"), Decimal("500"))
                if val > 0:
                    deductions.append(Deduction("BAL10", val, "Gastos por Vivienda Ocupada Ilegalmente"))

        # 11. BAL11: Donaciones a entidades de investigación (Art. 5)
        donaciones_rdi = profile.regional_data.get("balears_donations_rdi_eur", Decimal("0"))
        if donaciones_rdi > 0:
            val = donaciones_rdi * Decimal("0.25")
            limite_cuota = cuota_auton * Decimal("0.15")
            val = min(val, limite_cuota)
            if val > 0:
                deductions.append(Deduction("BAL11", val, "Donaciones Investigación o Desarrollo"))

        # 12. BAL12: Mecenazgo cultural, científico y consumo cultural (Art. 5 bis)
        val_cultural = Decimal("0")
        mecenazgo_cult_gen = profile.regional_data.get("balears_mecenazgo_cultural_general_eur", Decimal("0"))
        mecenazgo_cult_spec = profile.regional_data.get("balears_mecenazgo_cultural_special_eur", Decimal("0"))

        if mecenazgo_cult_spec > 0:
            val_cultural += min(mecenazgo_cult_spec * Decimal("0.25"), Decimal("1200"))

        if mecenazgo_cult_gen > 0 and bi_total <= limite_general:
            val_cultural += min(mecenazgo_cult_gen * Decimal("0.15"), Decimal("660"))

        if val_cultural > 0:
            deductions.append(Deduction("BAL12", val_cultural, "Mecenazgo Cultural y Científico"))

        # 13. BAL13: Mecenazgo deportivo (Art. 5 ter)
        if bi_total <= limite_general:
            mecenazgo_dep = profile.regional_data.get("balears_mecenazgo_deportivo_eur", Decimal("0"))
            if mecenazgo_dep > 0:
                val = min(mecenazgo_dep * Decimal("0.15"), Decimal("660"))
                if val > 0:
                    deductions.append(Deduction("BAL13", val, "Mecenazgo Deportivo"))

        # 14. BAL14: Fomento de la lengua catalana (Art. 5 quater)
        donaciones_catalan = profile.regional_data.get("balears_donations_catalan_eur", Decimal("0"))
        if donaciones_catalan > 0:
            val = donaciones_catalan * Decimal("0.15")
            limite_cuota = cuota_auton * Decimal("0.10")
            val = min(val, limite_cuota)
            if val > 0:
                deductions.append(Deduction("BAL14", val, "Fomento de la Lengua Catalana"))

        # 15. BAL15: Donaciones a entidades del tercer sector (Art. 5 quinquies)
        donaciones_tercer = profile.regional_data.get("balears_donations_third_sector_eur", Decimal("0"))
        if donaciones_tercer > 0:
            val = min(donaciones_tercer * Decimal("0.25"), Decimal("165"))
            if val > 0:
                deductions.append(Deduction("BAL15", val, "Donaciones a Tercer Sector de Acción Social"))

        # 16. BAL16: Personas con discapacidad personal o familiar (Art. 6)
        if bi_total <= limite_general:
            discapacidad_deduc = Decimal("0")
            if profile.disability_grade >= 33:
                if profile.disability_grade >= 65:
                    discapacidad_deduc += Decimal("165")
                elif es_discapacitado_psiquica_33:
                    discapacidad_deduc += Decimal("165")
                else:
                    discapacidad_deduc += Decimal("88")

            hijos_disc = profile.regional_data.get("descendants_disabled_count", 0)
            if hijos_disc > 0:
                discapacidad_deduc += Decimal("88") * hijos_disc

            if discapacidad_deduc > 0:
                deductions.append(Deduction("BAL16", discapacidad_deduc, "Discapacidad Personal o Familiar"))

        # 17 e 20: Incompatibilidad entre Conciliación (BAL17/Art. 6 bis) y Cuidado Mayores/Discapacidad (BAL20/Art. 6 quinquies)
        val_bal17 = Decimal("0")
        val_bal20 = Decimal("0")

        # Evaluación BAL17 (Conciliación menores de 6 años)
        if bi_total <= limite_bi_cruzado:
            concil_gastos = profile.regional_data.get("balears_conciliacion_expenses_eur", Decimal("0"))
            if concil_gastos > 0 and conciliacion_kids > 0:
                pct = Decimal("0.50") if es_colectivo_b else Decimal("0.40")
                lim_max = Decimal("900") if es_colectivo_b else Decimal("660")
                coprop = (
                    Decimal("2") if (not es_conjunta and getattr(profile, "custody_shared", False)) else Decimal("1")
                )
                val_bal17 = min(concil_gastos * pct, lim_max / coprop)

        # Evaluación BAL20 (Cuidado mayores de 65 años o con discapacidad)
        if bi_total <= limite_general:
            cuidado_gastos = profile.regional_data.get("balears_care_elderly_disabled_expenses_eur", Decimal("0"))
            cuidado_personas = profile.regional_data.get("balears_care_elderly_disabled_people_count", 0)
            if cuidado_gastos > 0 and cuidado_personas > 0:
                val_bal20 = min(cuidado_gastos * Decimal("0.40"), Decimal("660") * cuidado_personas)

        if val_bal17 > 0 and val_bal17 >= val_bal20:
            deductions.append(Deduction("BAL17", val_bal17, "Gastos Conciliación Descendientes Menores 6 Años"))
        elif val_bal20 > 0:
            deductions.append(Deduction("BAL20", val_bal20, "Gastos Cuidado Mayores o Discapacitados"))

        # 18. BAL18: Por nacimiento (Art. 6 ter)
        limite_nac_gen = Decimal("84480") if es_conjunta else Decimal("52800")
        limite_nac_inc = Decimal("101376") if es_conjunta else Decimal("63360")
        limite_nac_base = limite_nac_inc if (es_numerosa or es_monoparental_2_kids) else limite_nac_gen

        birth_count = profile.regional_data.get("balears_births_count", 0)
        if birth_count > 0:
            order = profile.regional_data.get("balears_birth_order", 1)
            cuotas_tabla = {1: Decimal("800"), 2: Decimal("1000"), 3: Decimal("1200"), 4: Decimal("1400")}
            val_base = Decimal("0")
            for i in range(birth_count):
                current_order = order + i
                val_base += cuotas_tabla.get(current_order if current_order <= 4 else 4, Decimal("1400"))

            coprop = Decimal("2") if not es_conjunta else Decimal("1")
            val_nac = val_base / coprop

            if bi_total > limite_nac_base:
                val_nac = val_nac * Decimal("0.50")

            abono = profile.regional_data.get("balears_births_anticipado_eur", Decimal("0"))
            val_final = max(val_nac - abono, Decimal("0"))
            if val_final > 0:
                deductions.append(Deduction("BAL18", val_final, "Deducción por Nacimiento"))

        # 19. BAL19: Por adopción (Art. 6 quater)
        adopt_count = profile.regional_data.get("balears_adoptions_count", 0)
        if adopt_count > 0 and bi_total <= limite_bi_cruzado:
            order = profile.regional_data.get("balears_adoption_order", 1)
            cuotas_tabla = {1: Decimal("800"), 2: Decimal("1000"), 3: Decimal("1200"), 4: Decimal("1400")}
            val_base = Decimal("0")
            for i in range(adopt_count):
                current_order = order + i
                val_base += cuotas_tabla.get(current_order if current_order <= 4 else 4, Decimal("1400"))
            coprop = Decimal("2") if not es_conjunta else Decimal("1")
            val_final = val_base / coprop
            if val_final > 0:
                deductions.append(Deduction("BAL19", val_final, "Deducción por Adopción"))

        # 21. BAL21: Esclerosis Lateral Amiotrófica (ELA) (Art. 6 sexties)
        limite_ela_bi = Decimal("84480") if es_conjunta else Decimal("52800")
        if bi_total <= limite_ela_bi:
            ela_gastos = profile.regional_data.get("balears_ela_expenses_eur", Decimal("0"))
            if ela_gastos > 0:
                deductions.append(Deduction("BAL21", min(ela_gastos, Decimal("3500")), "Gastos Derivados de la ELA"))

        # 22. BAL22: Adquisición de acciones de nuevas entidades (Art. 7)
        inv_acciones_gen = profile.regional_data.get("new_entities_investment_eur", Decimal("0"))
        inv_acciones_uni = profile.regional_data.get("mab_investment_eur", Decimal("0"))

        val_acciones = Decimal("0")
        if inv_acciones_gen > 0:
            val_acciones += inv_acciones_gen * Decimal("0.30")
        if inv_acciones_uni > 0:
            val_acciones += inv_acciones_uni * Decimal("0.50")

        if val_acciones > 0:
            limite_global = Decimal("12000") if inv_acciones_uni > 0 else Decimal("6000")
            deductions.append(
                Deduction("BAL22", min(val_acciones, limite_global), "Inversión en Acciones de Nuevas Entidades")
            )

        # 23. BAL23: Fomento de la autoocupación (Art. 7 bis)
        if bi_total <= limite_general:
            if profile.regional_data.get("balears_autoocupacion_alta_primera_vez", False):
                deductions.append(Deduction("BAL23", Decimal("1000"), "Fomento de la Autoocupación"))

        # 24. BAL24: Ocupación de plazas de difícil cobertura (Art. 7 ter)
        limite_diff_bi = Decimal("84480") if es_conjunta else Decimal("52800")
        if bi_total <= limite_diff_bi:
            gasto_diff = profile.regional_data.get("balears_difficult_coverage_expenses_eur", Decimal("0"))
            if gasto_diff > 0:
                base_calc = gasto_diff * Decimal("0.40")

                es_policia_gc = profile.regional_data.get("balears_is_police_guardia_civil", False)
                isla = profile.regional_data.get("balears_police_gc_island", "")

                if es_policia_gc and isla == "Mallorca":
                    limite_max = Decimal("1400") if bi_total <= limite_general else Decimal("700")
                elif es_policia_gc and isla == "Formentera":
                    limite_max = Decimal("2600") if bi_total <= limite_general else Decimal("1300")
                else:
                    limite_max = Decimal("2000") if bi_total <= limite_general else Decimal("1000")

                val = min(base_calc, limite_max)
                if val > 0:
                    deductions.append(Deduction("BAL24", val, "Ocupación de Plazas de Difícil Cobertura"))

        return deductions
