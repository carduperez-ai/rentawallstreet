# src/tax_compliance/deductions/regional/canarias.py
from decimal import Decimal
from typing import List
from src.domain.fiscal_entities import TaxpayerProfile, Deduction

class CanariasDeductor:
    """Implementación de Deducciones Autonómicas de la Comunidad Autónoma de Canarias para el ejercicio 2025."""

    @classmethod
    def calculate(cls, profile: TaxpayerProfile, big: Decimal, bia: Decimal, cuota_auton: Decimal) -> List[Deduction]:
        deductions = []
        es_conjunta = getattr(profile, 'joint_declaration', False)
        bi_total = big + bia

        # Límites de base imponible cruzada transversales
        limite_general = Decimal('61770') if es_conjunta else Decimal('46455')
        coprop_nac_alq = Decimal('2') if getattr(profile, 'custody_shared', False) and not es_conjunta else Decimal('1')

        # 1. CAN_ECO: Por donaciones con finalidad ecológica
        don_eco = profile.regional_data.get('canarias_donations_ecological_eur', Decimal('0'))
        if don_eco > 0:
            pct_val = don_eco * Decimal('0.10')
            limit_taxpayer = Decimal('300') if es_conjunta else Decimal('150')
            val = min(pct_val, cuota_auton * Decimal('0.10'), limit_taxpayer)
            if val > 0:
                deductions.append(Deduction("CAN_ECO", val.quantize(Decimal('0.01')), "Donaciones con finalidad ecológica"))

        # 2. CAN_HIST_DON: Por donaciones para rehabilitación o conservación del patrimonio histórico
        don_hist = profile.regional_data.get('canarias_donations_historical_eur', Decimal('0'))
        if don_hist > 0:
            pct_val = don_hist * Decimal('0.20')
            limit_taxpayer = Decimal('300') if es_conjunta else Decimal('150')
            val = min(pct_val, cuota_auton * Decimal('0.10'), limit_taxpayer)
            if val > 0:
                deductions.append(Deduction("CAN_HIST_DON", val.quantize(Decimal('0.01')), "Donaciones rehabilitación/conservación patrimonio histórico"))

        # 3. CAN_CULT_DEP_RDI: Por donaciones y aportaciones para fines culturales, deportivos, investigación o docencia
        don_cult = profile.regional_data.get('canarias_donations_cultural_rdi_eur', Decimal('0'))
        if don_cult > 0:
            pct_val = don_cult * Decimal('0.15')
            val = min(pct_val, cuota_auton * Decimal('0.05'))
            if val > 0:
                deductions.append(Deduction("CAN_CULT_DEP_RDI", val.quantize(Decimal('0.01')), "Donaciones fines culturales, deportivos o investigación"))

        # 4. CAN_ESL: Por donaciones a entidades sin ánimo de lucro
        don_esl = profile.regional_data.get('canarias_donations_third_sector_eur', Decimal('0'))
        if don_esl > 0:
            first_part = min(don_esl, Decimal('150'))
            rest_part = max(Decimal('0'), don_esl - Decimal('150'))
            pct_val = first_part * Decimal('0.20') + rest_part * Decimal('0.15')
            limit_bl = bi_total * Decimal('0.10')
            val = min(pct_val, limit_bl)
            if val > 0:
                deductions.append(Deduction("CAN_ESL", val.quantize(Decimal('0.01')), "Donaciones a entidades sin ánimo de lucro"))

        # 5. CAN_HIST_REHAB: Restauración, rehabilitación o reparación de bienes de interés cultural (base previa al cap conjunto)
        val_hist_rehab = Decimal('0')
        expenses_hist = profile.regional_data.get('canarias_rehabilitation_historical_eur', Decimal('0'))
        if expenses_hist > 0:
            pct_val = expenses_hist * Decimal('0.10')
            val_hist_rehab = min(pct_val, cuota_auton * Decimal('0.10'))

        # 6. CAN_EST_SUP: Por gastos de estudios de educación superior
        if bi_total <= limite_general:
            count_out = profile.regional_data.get('canarias_descendants_studying_outside_count', 0)
            count_same = profile.regional_data.get('canarias_descendants_studying_same_island_rental_count', 0)
            if count_out > 0 or count_same > 0:
                rate_out = Decimal('1920') if bi_total < Decimal('37062') else Decimal('1800')
                rate_same = Decimal('900')
                coprop_edu = Decimal('2') if (not es_conjunta and getattr(profile, 'custody_shared', False)) else Decimal('1')
                val = (rate_out * count_out + rate_same * count_same) / coprop_edu
                val = min(val, cuota_auton * Decimal('0.40'))
                if val > 0:
                    deductions.append(Deduction("CAN_EST_SUP", val.quantize(Decimal('0.01')), "Gastos estudios educación superior"))

        # 7. CAN_EST_NOSUP: Por gastos de estudios no superiores
        if bi_total <= limite_general:
            exp_nosup = profile.regional_data.get('canarias_descendants_non_higher_edu_expenses_eur', Decimal('0'))
            if exp_nosup > 0:
                desc_count = getattr(profile, 'descendants_count', 0)
                if desc_count > 0:
                    max_lim = Decimal('133') + Decimal('66') * (desc_count - 1)
                    coprop_edu = Decimal('2') if (not es_conjunta and getattr(profile, 'custody_shared', False)) else Decimal('1')
                    max_lim_prop = max_lim / coprop_edu
                    val = min(exp_nosup, max_lim_prop)
                    if val > 0:
                        deductions.append(Deduction("CAN_EST_NOSUP", val.quantize(Decimal('0.01')), "Gastos estudios no superiores"))

        # 8. CAN_TRASLADO: Por trasladar la residencia habitual a otra isla para realizar actividad económica
        if profile.regional_data.get('canarias_relocation_island_active', False) and profile.regional_data.get('canarias_relocation_island_year', 2025) in (2024, 2025):
            if bi_total <= limite_general:
                val = Decimal('600') if es_conjunta else Decimal('300')
                val = min(val, cuota_auton)
                if val > 0:
                    deductions.append(Deduction("CAN_TRASLADO", val.quantize(Decimal('0.01')), "Traslado de residencia habitual a otra isla"))

        # 9. CAN_ACCIONES: Por inversión en adquisición de acciones/participaciones de nuevas entidades
        val_std = profile.regional_data.get('canarias_new_entities_investment_eur', Decimal('0')) * Decimal('0.20')
        val_std = min(val_std, Decimal('4000'))
        
        val_univ = profile.regional_data.get('canarias_new_entities_investment_univ_rdi_eur', Decimal('0')) * Decimal('0.30')
        val_univ = min(val_univ, Decimal('6000'))
        
        val_coop = profile.regional_data.get('canarias_new_entities_investment_labor_coop_eur', Decimal('0')) * Decimal('0.30')
        val_coop = min(val_coop, Decimal('6000'))
        
        val_acc = val_std + val_univ + val_coop
        if val_acc > 0:
            deductions.append(Deduction("CAN_ACCIONES", val_acc.quantize(Decimal('0.01')), "Inversión en acciones de nuevas entidades"))

        # 10. CAN_NACIMIENTO: Por nacimiento o adopción de hijos
        if bi_total <= limite_general:
            births = getattr(profile, 'birth_count_current_year', 0)
            if births > 0:
                order = profile.regional_data.get('balears_birth_order', 1)
                val_nac = Decimal('0')
                for i in range(births):
                    curr_order = order + i
                    if curr_order <= 2:
                        val_nac += Decimal('265')
                    elif curr_order == 3:
                        val_nac += Decimal('530')
                    elif curr_order == 4:
                        val_nac += Decimal('796')
                    else:
                        val_nac += Decimal('928')
                
                # Plus discapacidad >= 65%
                disabled_births = getattr(profile, 'children_disabled_over65', 0)
                val_dis = Decimal('0')
                if disabled_births > 0:
                    for i in range(disabled_births):
                        curr_dis_order = i + 1
                        if curr_dis_order <= 2:
                            val_dis += Decimal('600')
                        else:
                            val_dis += Decimal('1100')
                
                val = (val_nac + val_dis) / coprop_nac_alq
                if val > 0:
                    deductions.append(Deduction("CAN_NACIMIENTO", val.quantize(Decimal('0.01')), "Nacimiento o adopción de hijos"))

        # 11. CAN_DISCAP_EDAD: Por contribuyentes con discapacidad y mayores de 65 años
        if bi_total <= limite_general:
            val_disc_edad = Decimal('0')
            if profile.disability_grade >= 33:
                val_disc_edad += Decimal('400')
            if profile.age > 65:
                val_disc_edad += Decimal('160')
            
            if es_conjunta:
                if getattr(profile, 'spouse_disability_grade', 0) >= 33:
                    val_disc_edad += Decimal('400')
                # En conjunta sumamos la edad si existiera control de cónyuge
            if val_disc_edad > 0:
                deductions.append(Deduction("CAN_DISCAP_EDAD", val_disc_edad.quantize(Decimal('0.01')), "Discapacidad o edad del contribuyente"))

        # 12. CAN_ACOGIMIENTO: Por acogimiento de menores
        foster_count = profile.regional_data.get('canarias_foster_care_minors_count', 0)
        if foster_count > 0:
            days_list = profile.regional_data.get('canarias_foster_care_days_list', [])
            val_base = Decimal('0')
            for i in range(foster_count):
                days = days_list[i] if i < len(days_list) else 365
                val_base += Decimal('330') * Decimal(days) / Decimal('365')
            
            val = val_base / coprop_nac_alq
            if val > 0:
                deductions.append(Deduction("CAN_ACOGIMIENTO", val.quantize(Decimal('0.01')), "Acogimiento de menores"))

        # 13. CAN_MONOPARENTAL: Por familias monoparentales
        if bi_total <= limite_general:
            if getattr(profile, 'is_monoparental', False) and getattr(profile, 'descendants_count', 0) > 0:
                deductions.append(Deduction("CAN_MONOPARENTAL", Decimal('133'), "Familias monoparentales"))

        # 14. CAN_GUARDERIA: Por gastos de custodia en guarderías
        if bi_total <= limite_general:
            kids3 = getattr(profile, 'children_under_3', 0)
            exp_guard = profile.regional_data.get('canarias_daycare_expenses_eur', Decimal('0'))
            if exp_guard == 0:
                exp_guard = getattr(profile, 'daycare_expenses_eur', Decimal('0'))
            if kids3 > 0 and exp_guard > 0:
                coprop_guard = Decimal('2') if (not es_conjunta and getattr(profile, 'custody_shared', False)) else Decimal('1')
                max_lim = (Decimal('530') * kids3) / coprop_guard
                val = min(exp_guard * Decimal('0.18'), max_lim)
                if val > 0:
                    deductions.append(Deduction("CAN_GUARDERIA", val.quantize(Decimal('0.01')), "Gastos de guardería"))

        # 15. CAN_FAM_NUM: Por familia numerosa
        if getattr(profile, 'is_large_family', False):
            is_special = getattr(profile, 'is_large_family_special', False) or getattr(profile, 'large_family_category', '') == 'special'
            has_disab = profile.regional_data.get('balears_is_disabled_member', False) or getattr(profile, 'children_disabled_over65', 0) > 0 or getattr(profile, 'spouse_disability_grade', 0) >= 65
            
            if is_special:
                base_val = Decimal('1459') if has_disab else Decimal('796')
            else:
                base_val = Decimal('1326') if has_disab else Decimal('597')
                
            val = base_val / coprop_nac_alq
            if val > 0:
                deductions.append(Deduction("CAN_FAM_NUM", val.quantize(Decimal('0.01')), "Familia numerosa"))

        # 16. CAN_VIV_HAB: Inversión en vivienda habitual (base previa al cap conjunto)
        val_viv_hab = Decimal('0')
        invest_viv = getattr(profile, 'mortgage_paid_eur', Decimal('0'))
        if invest_viv > 0 and bi_total < Decimal('46455'):
            base_inv = min(invest_viv, Decimal('6000'))
            age = profile.age
            if bi_total < Decimal('26035'):
                pct = Decimal('0.055') if age < 40 else Decimal('0.05')
            else:
                pct = Decimal('0.04') if age < 40 else Decimal('0.035')
            val_viv_hab = base_inv * pct

        # 17. CAN_VIV_ENER: Obras de rehabilitación energética de la vivienda habitual (base previa al cap conjunto)
        val_viv_ener = Decimal('0')
        exp_ener = profile.regional_data.get('canarias_home_rehabilitation_energy_eur', Decimal('0'))
        if exp_ener > 0:
            pct_val = min(exp_ener, Decimal('7000')) * Decimal('0.12')
            val_viv_ener = min(pct_val, cuota_auton * Decimal('0.10'))

        # 18. CAN_VIV_DISCAP: Obras adecuación vivienda por discapacidad (base previa al cap conjunto)
        val_viv_discap = Decimal('0')
        exp_disc = profile.regional_data.get('canarias_home_adequacy_disability_eur', Decimal('0'))
        if exp_disc > 0:
            coprop_disc = Decimal('2') if not es_conjunta else Decimal('1')
            base_exp = min(exp_disc, Decimal('15000') / coprop_disc)
            pct = Decimal('0.18') if profile.age > 65 else Decimal('0.14')
            val_viv_discap = base_exp * pct

        # APLICACIÓN DEL LÍMITE CONJUNTO DEL 15% PARA LAS CUATRO DEDUCCIONES VIVIENDA/BIENES CULTURALES
        raw_viv_sum = val_hist_rehab + val_viv_hab + val_viv_ener + val_viv_discap
        limit_15 = (cuota_auton * Decimal('0.15')).quantize(Decimal('0.01'))
        if raw_viv_sum > limit_15 and raw_viv_sum > 0:
            scale = limit_15 / raw_viv_sum
            v_hist = (val_hist_rehab * scale).quantize(Decimal('0.01'))
            v_hab = (val_viv_hab * scale).quantize(Decimal('0.01'))
            v_ener = (val_viv_ener * scale).quantize(Decimal('0.01'))
            v_disc = (val_viv_discap * scale).quantize(Decimal('0.01'))
            
            diff = limit_15 - (v_hist + v_hab + v_ener + v_disc)
            if diff != 0:
                vals = [("hist", v_hist), ("hab", v_hab), ("ener", v_ener), ("disc", v_disc)]
                vals.sort(key=lambda x: x[1], reverse=True)
                for i in range(len(vals)):
                    if vals[i][1] > 0:
                        name, val_to_adj = vals[i]
                        adjusted_val = val_to_adj + diff
                        if name == "hist": v_hist = adjusted_val
                        elif name == "hab": v_hab = adjusted_val
                        elif name == "ener": v_ener = adjusted_val
                        elif name == "disc": v_disc = adjusted_val
                        break
            
            val_hist_rehab = v_hist
            val_viv_hab = v_hab
            val_viv_ener = v_ener
            val_viv_discap = v_disc

        if val_hist_rehab > 0:
            deductions.append(Deduction("CAN_HIST_REHAB", val_hist_rehab, "Adecuación de bienes de interés cultural"))
        if val_viv_hab > 0:
            deductions.append(Deduction("CAN_VIV_HAB", val_viv_hab, "Inversión en vivienda habitual"))
        if val_viv_ener > 0:
            deductions.append(Deduction("CAN_VIV_ENER", val_viv_ener, "Rehabilitación energética vivienda"))
        if val_viv_discap > 0:
            deductions.append(Deduction("CAN_VIV_DISCAP", val_viv_discap, "Adecuación de vivienda por discapacidad"))

        # 19. CAN_ALQUILER: Por alquiler de vivienda habitual
        if bi_total <= limite_general:
            rent = getattr(profile, 'rent_paid_annual_eur', Decimal('0'))
            if rent > 0 and getattr(profile, 'is_rent_habitual', False):
                if rent > (bi_total * Decimal('0.10')):
                    coprop_alq = Decimal('2') if (not es_conjunta and getattr(profile, 'custody_shared', False)) else Decimal('1')
                    lim_max = Decimal('760') if (profile.age < 40 or profile.age >= 75) else Decimal('740')
                    lim_max_prop = lim_max / coprop_alq
                    val = min(rent * Decimal('0.24'), lim_max_prop)
                    if val > 0:
                        deductions.append(Deduction("CAN_ALQUILER", val.quantize(Decimal('0.01')), "Alquiler vivienda habitual"))

        # 20. CAN_ALQ_DACION: Por arrendamiento vivienda habitual vinculado a dación en pago
        if bi_total <= limite_general:
            rent = profile.regional_data.get('canarias_rent_dacion_pago_paid_eur', Decimal('0'))
            if rent > 0:
                coprop_dacion = Decimal('2') if (not es_conjunta and getattr(profile, 'custody_shared', False)) else Decimal('1')
                lim_max = Decimal('1200') / coprop_dacion
                val = min(rent * Decimal('0.25'), lim_max)
                if val > 0:
                    deductions.append(Deduction("CAN_ALQ_DACION", val.quantize(Decimal('0.01')), "Arrendamiento por dación en pago"))

        # 21. CAN_ARREND_ADEQ: Gastos de adecuación de inmueble para alquiler
        val_arrend_adeq = Decimal('0')
        exp_adeq = profile.regional_data.get('canarias_landlord_adequacy_rent_expenses_eur', Decimal('0'))
        if exp_adeq > 0:
            val_arrend_adeq = min(exp_adeq * Decimal('0.10'), Decimal('150'))

        # 22. CAN_ARREND_INSUR: Gastos de primas de seguro impago de alquiler
        val_arrend_insur = Decimal('0')
        prem_insur = profile.regional_data.get('canarias_landlord_unpaid_insurance_premiums_eur', Decimal('0'))
        rent_m = profile.regional_data.get('canarias_landlord_unpaid_insurance_monthly_rent_eur', Decimal('0'))
        fianza_dep = profile.regional_data.get('canarias_landlord_unpaid_insurance_fianza_deposited', False)
        if prem_insur > 0 and rent_m <= Decimal('800') and fianza_dep:
            val_arrend_insur = min(prem_insur * Decimal('0.75'), Decimal('150'))

        # Resolución incompatibilidad (máximo beneficio)
        if val_arrend_adeq > 0 and val_arrend_insur > 0:
            if val_arrend_adeq >= val_arrend_insur:
                val_arrend_insur = Decimal('0')
            else:
                val_arrend_adeq = Decimal('0')

        if val_arrend_adeq > 0:
            deductions.append(Deduction("CAN_ARREND_ADEQ", val_arrend_adeq.quantize(Decimal('0.01')), "Adecuación inmueble para arrendamiento"))
        elif val_arrend_insur > 0:
            deductions.append(Deduction("CAN_ARREND_INSUR", val_arrend_insur.quantize(Decimal('0.01')), "Seguro impago de alquiler"))

        # 23. CAN_ARREND_MERCADO: Por la puesta de viviendas en el mercado de arrendamiento
        prop_count = profile.regional_data.get('canarias_landlord_market_properties_count', 0)
        if prop_count > 0:
            val = Decimal('1000') * min(prop_count, 5)
            if val > 0:
                deductions.append(Deduction("CAN_ARREND_MERCADO", val.quantize(Decimal('0.01')), "Puesta de vivienda en mercado de alquiler"))

        # 24. CAN_DESEMPLEADO: Por contribuyentes desempleados
        if profile.regional_data.get('canarias_is_unemployed_over_6_months', False):
            work_inc = profile.regional_data.get('canarias_work_income_eur', Decimal('0'))
            if Decimal('15876') < work_inc <= Decimal('22000'):
                rest_income = bi_total - work_inc
                if rest_income <= Decimal('1600'):
                    deductions.append(Deduction("CAN_DESEMPLEADO", Decimal('120'), "Contribuyentes desempleados"))

        # 25. CAN_MED_EXP: Por gasto de enfermedad
        health_exp = profile.regional_data.get('canarias_health_expenses_eur', Decimal('0'))
        optical_exp = profile.regional_data.get('canarias_health_apparatus_optical_eur', Decimal('0'))
        if health_exp > 0 or optical_exp > 0:
            base_calc = (health_exp + optical_exp) * Decimal('0.12')
            if bi_total <= limite_general:
                limit_med = Decimal('700') if es_conjunta else Decimal('500')
                # Plus por > 65 o discapacidad >= 65%
                if profile.age > 65 or profile.disability_grade >= 65:
                    limit_med += Decimal('100')
                val = min(base_calc, limit_med)
            else:
                val = min(base_calc, Decimal('150'))
            if val > 0:
                deductions.append(Deduction("CAN_MED_EXP", val.quantize(Decimal('0.01')), "Gastos de enfermedad y aparatos médicos"))

        # 26. CAN_DEP_DISCAP: Por familiares dependientes con discapacidad
        dep_count = profile.regional_data.get('canarias_dependent_disabled_65_count', 0)
        if dep_count > 0 and bi_total <= limite_general:
            # 600 euros per dependent
            val_dep = Decimal('600') * dep_count
            
            # 20% of domestic helper SS contributions if the dependent needs help
            exp_ss = profile.regional_data.get('canarias_dependent_disabled_assistance_ss_eur', Decimal('0'))
            val_ss = min(exp_ss * Decimal('0.20'), Decimal('500'))
            
            val = (val_dep + val_ss) / coprop_nac_alq
            if val > 0:
                deductions.append(Deduction("CAN_DEP_DISCAP", val.quantize(Decimal('0.01')), "Familiares dependientes con discapacidad"))

        # 27. CAN_EMP_HOGAR: Por contratación de empleados de hogar
        ss_cont = profile.regional_data.get('canarias_domestic_employee_ss_eur', Decimal('0'))
        if ss_cont > 0:
            elig_child = getattr(profile, 'descendants_count', 0) > 0
            elig_age_75 = profile.age >= 75
            elig_age_65_disc = profile.age > 65 and profile.disability_grade >= 33
            if elig_child or elig_age_75 or elig_age_65_disc:
                val = min(ss_cont * Decimal('0.20'), Decimal('500'))
                if val > 0:
                    deductions.append(Deduction("CAN_EMP_HOGAR", val.quantize(Decimal('0.01')), "Contratación de empleados de hogar"))

        return deductions
