# src/tax_compliance/deductions/regional/castilla_la_mancha.py
from decimal import Decimal
from typing import List
from src.domain.fiscal_entities import TaxpayerProfile, Deduction
from src.tax_compliance.regions.base import BaseRegion

class CastillaLaManchaDeductor:
    """Implementación de Deducciones Autonómicas de la Comunidad Autónoma de Castilla-La Mancha para el ejercicio 2025."""

    @classmethod
    def calculate(cls, profile: TaxpayerProfile, big: Decimal, bia: Decimal, cuota_auton: Decimal) -> List[Deduction]:
        deductions = []
        es_conjunta = getattr(profile, 'joint_declaration', False)
        bi_total = big + bia

        # Mínimo personal y familiar para el cálculo de límites de renta en alquileres y educación
        mpf = profile.regional_data.get('minimo_personal_familiar', BaseRegion.get_personal_minimum())
        base_limite_renta_alq = bi_total - mpf

        # Límites transversales de base imponible general + ahorro (27.000€ individual / 36.000€ conjunta)
        limite_transversal = Decimal('36000') if es_conjunta else Decimal('27000')

        # --- DEDUCCIONES INDEPENDIENTES ---

        # 1. CLM01: Por nacimiento o adopción de hijos
        if bi_total <= limite_transversal:
            births = getattr(profile, 'birth_count_current_year', 0)
            if births > 0:
                if births == 1:
                    raw_val = Decimal('100')
                elif births == 2:
                    raw_val = Decimal('500')
                else:
                    raw_val = Decimal('900')
                
                coprop = Decimal('1') if es_conjunta else Decimal('2')
                val = raw_val / coprop
                deductions.append(Deduction("CLM01", val.quantize(Decimal('0.01')), "Por nacimiento o adopción de hijos"))

        # 4. CLM04: Por gastos en libros de texto, idiomas y otros gastos educativos
        # Límite por hijo basado en (BI_General + BI_Ahorro) - Mínimo por Descendientes.
        # Por simplicidad, consideramos base_limite_renta_alq como base de cálculo
        is_fn = getattr(profile, 'is_large_family', False)
        descendants = getattr(profile, 'descendants_count', 0)
        
        books = profile.regional_data.get('clm_education_books_expenses', Decimal('0'))
        languages = profile.regional_data.get('clm_education_languages_expenses', Decimal('0'))
        reinforcement = profile.regional_data.get('clm_education_reinforcement_expenses', Decimal('0'))
        internet = profile.regional_data.get('clm_education_internet_expenses', Decimal('0'))
        residence = profile.regional_data.get('clm_education_residence_expenses', Decimal('0'))
        scholarships = profile.regional_data.get('clm_education_scholarships_eur', Decimal('0'))

        subtotal_edu = books + Decimal('0.15') * (languages + reinforcement + internet + residence)
        net_edu = max(Decimal('0'), subtotal_edu - scholarships)

        if descendants > 0 and net_edu > 0:
            limit_per_child = Decimal('0')
            if es_conjunta:
                if not is_fn:
                    if base_limite_renta_alq <= Decimal('12000'):
                        limit_per_child = Decimal('200')
                    elif base_limite_renta_alq <= Decimal('20000'):
                        limit_per_child = Decimal('100')
                    elif base_limite_renta_alq <= Decimal('25000'):
                        limit_per_child = Decimal('75')
                else:
                    if base_limite_renta_alq <= Decimal('40000'):
                        limit_per_child = Decimal('300')
            else:
                if not is_fn:
                    if base_limite_renta_alq <= Decimal('6500'):
                        limit_per_child = Decimal('100')
                    elif base_limite_renta_alq <= Decimal('10000'):
                        limit_per_child = Decimal('75')
                    elif base_limite_renta_alq <= Decimal('12500'):
                        limit_per_child = Decimal('50')
                else:
                    if base_limite_renta_alq <= Decimal('30000'):
                        limit_per_child = Decimal('150')

            if limit_per_child > 0:
                coprop = Decimal('1') if es_conjunta else Decimal('2')
                net_edu_prorated = net_edu / coprop
                limit_prorated = (limit_per_child * descendants) / coprop
                val = min(net_edu_prorated, limit_prorated)
                if val > 0:
                    deductions.append(Deduction("CLM04", val.quantize(Decimal('0.01')), "Gastos en libros de texto e idiomas"))

        # 5. CLM05: Por gastos de guardería
        if bi_total <= limite_transversal:
            daycare_exp = getattr(profile, 'daycare_expenses_eur', Decimal('0'))
            if daycare_exp > 0:
                kids = getattr(profile, 'children_under_3', 0)
                if kids > 0:
                    pct_val = daycare_exp * Decimal('0.30')
                    net_exp = max(Decimal('0'), pct_val - profile.regional_data.get('clm_guarderia_subventions_eur', Decimal('0')))
                    
                    limit_per_kid = Decimal('250') if profile.regional_data.get('clm_guarderia_child_turns_3', False) else Decimal('500')
                    total_limit = limit_per_kid * kids
                    
                    coprop = Decimal('1') if es_conjunta else Decimal('2')
                    val = min(net_exp, total_limit) / coprop
                    if val > 0:
                        deductions.append(Deduction("CLM05", val.quantize(Decimal('0.01')), "Por gastos de guardería"))

        # 7. CLM07: Por discapacidad de ascendientes o descendientes
        if bi_total <= limite_transversal:
            disab_members = getattr(profile, 'children_disabled_over65', 0) + getattr(profile, 'ascendants_disabled_count', 0)
            if disab_members > 0:
                coprop = Decimal('1') if es_conjunta else Decimal('2')
                val = (Decimal('300') * disab_members) / coprop
                deductions.append(Deduction("CLM07", val.quantize(Decimal('0.01')), "Por discapacidad de ascendientes o descendientes"))

        # 8. CLM08: Para contribuyentes mayores de 75 años
        if bi_total <= limite_transversal and profile.age >= 75:
            if not profile.regional_data.get('clm_mayor_residence_public_over_30_days', False):
                deductions.append(Deduction("CLM08", Decimal('150.00'), "Para contribuyentes mayores de 75 años"))

        # 9. CLM09: Por el cuidado de ascendientes mayores de 75 años
        if bi_total <= limite_transversal:
            asc_75 = getattr(profile, 'ascendants_over75', 0)
            if asc_75 > 0:
                if not profile.regional_data.get('clm_ascendant_residence_public_over_30_days', False):
                    coprop = Decimal('1') if es_conjunta else Decimal('2')
                    val = (Decimal('150') * asc_75) / coprop
                    deductions.append(Deduction("CLM09", val.quantize(Decimal('0.01')), "Por cuidado de ascendientes mayores de 75 años"))

        # 10. CLM10: Por acogimiento familiar no remunerado de menores
        limite_acog = Decimal('25000') if es_conjunta else Decimal('12500')
        if bi_total <= limite_acog:
            acog_minors = profile.regional_data.get('clm_acogimiento_menores_count', 0)
            if acog_minors > 0:
                is_first = profile.regional_data.get('clm_acogimiento_menores_order_first', True)
                if is_first:
                    raw_val = Decimal('500') + Decimal('600') * (acog_minors - 1)
                else:
                    raw_val = Decimal('600') * acog_minors
                coprop = Decimal('1') if es_conjunta else Decimal('2')
                val = raw_val / coprop
                deductions.append(Deduction("CLM10", val.quantize(Decimal('0.01')), "Acogimiento familiar no remunerado de menores"))

        # 11. CLM11: Por acogimiento no remunerado de mayores de 65 años o con discapacidad
        if bi_total <= limite_acog:
            acog_senior = profile.regional_data.get('clm_acogimiento_senior_disc_count', 0)
            if acog_senior > 0:
                coprop = Decimal('1') if es_conjunta else Decimal('2')
                val = (Decimal('600') * acog_senior) / coprop
                deductions.append(Deduction("CLM11", val.quantize(Decimal('0.01')), "Acogimiento no remunerado de mayores de 65 años o con discapacidad"))

        # 17. CLM17: Por cantidades donadas para cooperación internacional
        don_coop = profile.regional_data.get('clm_donations_cooperacion_eur', Decimal('0'))
        if don_coop > 0:
            raw = don_coop * Decimal('0.15')
            lim = bi_total * Decimal('0.10')
            val = min(raw, lim)
            if val > 0:
                deductions.append(Deduction("CLM17", val.quantize(Decimal('0.01')), "Donaciones cooperación internacional"))

        # 18. CLM18: Por donaciones con finalidad en investigación y desarrollo científico
        don_idi = profile.regional_data.get('clm_donations_idi_eur', Decimal('0'))
        if don_idi > 0:
            raw = don_idi * Decimal('0.15')
            lim = cuota_auton * Decimal('0.10')
            val = min(raw, lim)
            if val > 0:
                deductions.append(Deduction("CLM18", val.quantize(Decimal('0.01')), "Donaciones investigación y desarrollo"))

        # 19. CLM19: Por donaciones de bienes culturales y conservación
        don_cult = profile.regional_data.get('clm_donations_cultural_mecenazgo_eur', Decimal('0'))
        if don_cult > 0:
            raw = don_cult * Decimal('0.15')
            lim = bi_total * Decimal('0.10')
            val = min(raw, lim)
            if val > 0:
                deductions.append(Deduction("CLM19", val.quantize(Decimal('0.01')), "Donaciones patrimonio cultural"))

        # 20. CLM20: Por gastos en intereses por financiación de primera vivienda habitual por menores de 40 años
        interest = profile.regional_data.get('clm_mortgage_interest_under_40_eur', Decimal('0'))
        if interest > 0 and profile.age < 40:
            if es_conjunta:
                cap = Decimal('150') if bi_total <= Decimal('25000') else Decimal('100') if bi_total <= Decimal('36000') else Decimal('0')
            else:
                cap = Decimal('150') if bi_total <= Decimal('12500') else Decimal('100') if bi_total <= Decimal('27000') else Decimal('0')
            
            val = min(interest, cap)
            if val > 0:
                deductions.append(Deduction("CLM20", val.quantize(Decimal('0.01')), "Intereses hipoteca jóvenes"))

        # 21. CLM21: Por residencia habitual en zonas rurales
        estancia = profile.regional_data.get('clm_rural_estancia_efectiva', False)
        zone = profile.regional_data.get('clm_rural_despoblacion_zone', '')
        pop = profile.regional_data.get('clm_rural_municipality_population', 0)
        
        if estancia and zone in ('extrema', 'intensa', 'riesgo', 'intermedia') and pop > 0:
            pct = Decimal('0')
            if zone == 'extrema':
                pct = Decimal('0.25') if pop < 2000 else Decimal('0.20') if pop < 5000 else Decimal('0')
            elif zone == 'intensa':
                pct = Decimal('0.20') if pop < 2000 else Decimal('0.15') if pop < 5000 else Decimal('0')
            elif zone == 'riesgo':
                pct = Decimal('0.15') if pop < 2000 else Decimal('0.10') if pop < 5000 else Decimal('0')
            elif zone == 'intermedia':
                pct = Decimal('0.15') if pop < 2000 else Decimal('0')
                
            if pct > 0:
                val = cuota_auton * pct
                if val > 0:
                    deductions.append(Deduction("CLM21", val.quantize(Decimal('0.01')), "Residencia habitual en zonas rurales"))

        # 22. CLM22: Por adquisición o rehabilitación de vivienda habitual en zonas rurales
        adq_exp = profile.regional_data.get('clm_rural_adq_rehab_expenses_eur', Decimal('0'))
        if adq_exp > 0 and zone in ('extrema', 'intensa') and pop < 5000:
            base = min(adq_exp, Decimal('12000'))
            val = base * Decimal('0.15')
            if val > 0:
                deductions.append(Deduction("CLM22", val.quantize(Decimal('0.01')), "Adquisición/rehabilitación vivienda habitual rural"))

        # 23. CLM23: Por traslado de vivienda habitual por motivos laborales
        limite_traslado = Decimal('31485') if es_conjunta else Decimal('22946')
        if bi_total < limite_traslado and profile.regional_data.get('clm_traslado_laboral_despoblacion', False):
            year = profile.regional_data.get('clm_traslado_laboral_year', 2025)
            if year in (2024, 2025):
                num_reloc = 2 if (es_conjunta and profile.regional_data.get('clm_traslado_laboral_spouse_relocated', False)) else 1
                raw_val = Decimal('500') * num_reloc
                val = min(raw_val, cuota_auton)
                if val > 0:
                    deductions.append(Deduction("CLM23", val.quantize(Decimal('0.01')), "Traslado de residencia por motivos laborales"))

        # 26. CLM26: Por ahorro-inversión en adquisición o construcción de primera vivienda habitual
        ahorro_viv = profile.regional_data.get('clm_ahorro_primera_vivienda_eur', Decimal('0'))
        if ahorro_viv > 0 and profile.age < 36 and bi_total <= limite_transversal:
            val = min(ahorro_viv * Decimal('0.15'), Decimal('750'))
            if val > 0:
                deductions.append(Deduction("CLM26", val.quantize(Decimal('0.01')), "Ahorro primera vivienda"))

        # 27. CLM27: Por gastos derivados de controles veterinarios por tenencia de perros de asistencia
        dog_vet = profile.regional_data.get('clm_assistant_dog_vet_expenses_eur', Decimal('0'))
        if dog_vet > 0 and bi_total <= limite_transversal:
            num_taxpayers = 2 if es_conjunta else 1
            limit = Decimal('100') * num_taxpayers
            val = min(dog_vet * Decimal('0.30'), limit)
            if val > 0:
                deductions.append(Deduction("CLM27", val.quantize(Decimal('0.01')), "Gastos veterinarios perros de asistencia"))


        # --- DEDUCCIONES CON INCOMPATIBILIDADES MUTUAS ---

        # 2. CLM02: Por familia numerosa
        val_clm02 = Decimal('0')
        if bi_total <= limite_transversal:
            if getattr(profile, 'is_large_family', False):
                is_special = getattr(profile, 'is_large_family_special', False) or getattr(profile, 'large_family_category', '') == 'special'
                has_disab_65 = (
                    profile.disability_grade >= 65 or
                    getattr(profile, 'children_disabled_over65', 0) > 0 or
                    getattr(profile, 'ascendants_disabled_count', 0) > 0 or
                    getattr(profile, 'spouse_disability_grade', 0) >= 65
                )
                if is_special:
                    raw_val = Decimal('900') if has_disab_65 else Decimal('400')
                else:
                    raw_val = Decimal('300') if has_disab_65 else Decimal('200')
                
                coprop = Decimal('1') if es_conjunta else Decimal('2')
                val_clm02 = raw_val / coprop

        # 3. CLM03: Por familia monoparental
        val_clm03 = Decimal('0')
        if bi_total <= limite_transversal:
            if profile.regional_data.get('clm_is_monoparental', False) or getattr(profile, 'is_monoparental', False):
                val_clm03 = Decimal('200.00')

        # 6. CLM06: Por discapacidad del contribuyente
        val_clm06 = Decimal('0')
        if bi_total <= limite_transversal and profile.disability_grade >= 65:
            val_clm06 = Decimal('300.00')

        # --- ALQUILER (CLM12 a CLM16) ---
        limite_alquiler = Decimal('25000') if es_conjunta else Decimal('12500')
        rent_paid = getattr(profile, 'rent_paid_annual_eur', Decimal('0'))

        val_clm12 = Decimal('0')
        val_clm13 = Decimal('0')
        val_clm14 = Decimal('0')
        val_clm15 = Decimal('0')
        val_clm16 = Decimal('0')

        if base_limite_renta_alq <= limite_alquiler:
            coprop = Decimal('1') if es_conjunta else Decimal('2')
            
            # CLM12: Alquiler jóvenes < 36 años
            if rent_paid > 0 and profile.age < 36:
                pop = profile.regional_data.get('clm_rural_municipality_population', 0)
                is_rural = False
                if pop > 0:
                    if pop <= 2500:
                        is_rural = True
                    elif pop <= 10000 and profile.regional_data.get('clm_rural_municipality_distant', False):
                        is_rural = True
                if zone in ('extrema', 'intensa', 'riesgo', 'intermedia'):
                    is_rural = True
                
                pct = Decimal('0.20') if is_rural else Decimal('0.15')
                limit = Decimal('612') if is_rural else Decimal('500')
                val_clm12 = min(rent_paid * pct, limit) / coprop

            # CLM13: Alquiler dación en pago
            rent_dacion = profile.regional_data.get('clm_rent_dacion_pago_paid_eur', Decimal('0'))
            if rent_dacion > 0:
                val_clm13 = min(rent_dacion * Decimal('0.15'), Decimal('500')) / coprop

            # CLM14: Alquiler familias numerosas
            if getattr(profile, 'is_large_family', False) and rent_paid > 0:
                val_clm14 = min(rent_paid * Decimal('0.15'), Decimal('500')) / coprop

            # CLM15: Alquiler familias monoparentales
            if (profile.regional_data.get('clm_is_monoparental', False) or getattr(profile, 'is_monoparental', False)) and rent_paid > 0:
                val_clm15 = min(rent_paid * Decimal('0.15'), Decimal('500')) / coprop

            # CLM16: Alquiler personas con discapacidad
            rent_disabled = profile.regional_data.get('clm_rent_disabled_paid_eur', Decimal('0'))
            if rent_disabled > 0 or (rent_paid > 0 and profile.disability_grade >= 65):
                actual_rent = rent_disabled if rent_disabled > 0 else rent_paid
                val_clm16 = min(actual_rent * Decimal('0.15'), Decimal('500')) / coprop

        # --- INVERSIONES (CLM24 vs CLM25) ---
        val_clm24 = Decimal('0')
        inv_acciones = profile.regional_data.get('clm_inv_acciones_sociedades_eur', Decimal('0'))
        if inv_acciones > 0:
            val_clm24 = min(inv_acciones * Decimal('0.20'), Decimal('4000'))

        val_clm25 = Decimal('0')
        inv_eco = profile.regional_data.get('clm_inv_economia_social_eur', Decimal('0'))
        if inv_eco > 0:
            val_clm25 = min(inv_eco * Decimal('0.20'), Decimal('4000'))

        # --- SISTEMA DE RESOLUCIÓN DE INCOMPATIBILIDADES OPTIMIZADO ---
        best_sum = Decimal('0')
        best_combo = []

        # Recorremos todas las combinaciones posibles de Alquiler e Inversiones
        for rent_choice in [None, 'CLM12', 'CLM13', 'CLM14', 'CLM15', 'CLM16']:
            for inv_choice in [None, 'CLM24', 'CLM25']:
                # Evaluamos compatibilidad en base a la elección
                has_clm02 = (rent_choice != 'CLM14')
                has_clm03 = (rent_choice != 'CLM15')
                has_clm06 = (rent_choice != 'CLM16')

                current_sum = Decimal('0')
                current_list = []

                if has_clm02 and val_clm02 > 0:
                    current_sum += val_clm02
                    current_list.append(("CLM02", val_clm02, "Por familia numerosa"))
                if has_clm03 and val_clm03 > 0:
                    current_sum += val_clm03
                    current_list.append(("CLM03", val_clm03, "Por familia monoparental"))
                if has_clm06 and val_clm06 > 0:
                    current_sum += val_clm06
                    current_list.append(("CLM06", val_clm06, "Por discapacidad del contribuyente"))

                if rent_choice == 'CLM12' and val_clm12 > 0:
                    current_sum += val_clm12
                    current_list.append(("CLM12", val_clm12, "Alquiler vivienda habitual por jóvenes"))
                elif rent_choice == 'CLM13' and val_clm13 > 0:
                    current_sum += val_clm13
                    current_list.append(("CLM13", val_clm13, "Alquiler vinculado a dación en pago"))
                elif rent_choice == 'CLM14' and val_clm14 > 0:
                    current_sum += val_clm14
                    current_list.append(("CLM14", val_clm14, "Alquiler por familias numerosas"))
                elif rent_choice == 'CLM15' and val_clm15 > 0:
                    current_sum += val_clm15
                    current_list.append(("CLM15", val_clm15, "Alquiler por familias monoparentales"))
                elif rent_choice == 'CLM16' and val_clm16 > 0:
                    current_sum += val_clm16
                    current_list.append(("CLM16", val_clm16, "Alquiler por discapacidad"))

                if inv_choice == 'CLM24' and val_clm24 > 0:
                    current_sum += val_clm24
                    current_list.append(("CLM24", val_clm24, "Inversión en acciones de sociedades mercantiles"))
                elif inv_choice == 'CLM25' and val_clm25 > 0:
                    current_sum += val_clm25
                    current_list.append(("CLM25", val_clm25, "Inversión en entidades de economía social"))

                if current_sum >= best_sum:
                    best_sum = current_sum
                    best_combo = current_list

        # Añadimos la combinación óptima de deducciones incompatibles al listado final
        for box_id, val, desc in best_combo:
            deductions.append(Deduction(box_id, val.quantize(Decimal('0.01')), desc))

        return deductions
