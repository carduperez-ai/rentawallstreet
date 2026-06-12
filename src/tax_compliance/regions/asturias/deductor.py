# src/tax_compliance/deductions/regional/asturias.py
from decimal import Decimal
from typing import List
from src.domain.fiscal_entities import TaxpayerProfile, Deduction

class AsturiasDeductor:
    """Implementación de Deducciones Autonómicas del Principado de Asturias para el ejercicio 2025."""

    @classmethod
    def calculate(cls, profile: TaxpayerProfile, big: Decimal, bia: Decimal, cuota_auton: Decimal) -> List[Deduction]:
        deductions = []
        es_conjunta = getattr(profile, 'joint_declaration', False)
        bi_total = big + bia

        # Límites comunes de base imponible cruzada general y del ahorro (35.000€ ind. / 45.000€ conj.)
        limite_comun = Decimal('45000') if es_conjunta else Decimal('35000')

        # 1. AST01: Alquiler de vivienda habitual (Art. 7)
        if bi_total <= limite_comun:
            if getattr(profile, 'is_rent_habitual', False) and getattr(profile, 'rent_paid_annual_eur', Decimal('0')) > 0:
                gasto = profile.rent_paid_annual_eur
                es_colectivo_especial = (
                    profile.age < 35 or
                    getattr(profile, 'is_large_family', False) or
                    getattr(profile, 'is_monoparental', False) or
                    getattr(profile, 'is_victim_violence_gender_or_terrorism', False) or
                    profile.regional_data.get('resides_in_asturias_despoblacion', False)
                )
                if es_colectivo_especial:
                    porcentaje = Decimal('0.30')
                    limite_max = Decimal('1500')
                else:
                    porcentaje = Decimal('0.10')
                    limite_max = Decimal('500')
                
                val = min(gasto * porcentaje, limite_max)
                if val > 0:
                    deductions.append(Deduction("AST01", val, "Alquiler de vivienda habitual"))

        # 2. AST03: Acogimiento no remunerado de mayores de 65 años (Art. 3)
        limite_art3 = Decimal('37000') if es_conjunta else Decimal('26000')
        if bi_total <= limite_art3:
            acogidos = getattr(profile, 'ascendants_over65', 0)
            if acogidos > 0:
                deductions.append(Deduction("AST03", Decimal('500') * acogidos, "Acogimiento de mayores de 65 años"))

        # 3. AST04: Adquisición o adecuación de la vivienda habitual para contribuyentes con discapacidad (Art. 4)
        if bi_total <= limite_comun:
            discapacidad_valida = (
                profile.disability_grade >= 65 or
                getattr(profile, 'ascendants_disabled_count', 0) > 0 or
                getattr(profile, 'children_disabled_over65', 0) > 0
            )
            inversion = profile.regional_data.get('disabled_child_autonomy_expenses_eur', Decimal('0'))
            if discapacidad_valida and inversion > 0:
                val = min(inversion * Decimal('0.03'), Decimal('450'))
                if val > 0:
                    deductions.append(Deduction("AST04", val, "Adecuación de vivienda habitual por discapacidad"))

        # 4. AST05: Inversión en vivienda habitual protegida (Art. 6)
        if getattr(profile, 'is_protected_housing', False):
            # Usamos mortgage_paid_eur como indicador de inversión/gastos
            inversion = getattr(profile, 'mortgage_paid_eur', Decimal('0'))
            if inversion > 0:
                is_adquisicion_año = getattr(profile, 'mortgage_pre2013', False)
                limite_vpo = Decimal('5000') if is_adquisicion_año else Decimal('1000')
                val = min(inversion, limite_vpo)
                if val > 0:
                    deductions.append(Deduction("AST05", val, "Inversión en vivienda protegida"))

        # 5. AST06: Adopción internacional de menores (Art. 9)
        adoptados = profile.regional_data.get('international_adoption_count', 0)
        if adoptados > 0:
            deductions.append(Deduction("AST06", Decimal('1500') * adoptados, "Adopción internacional de menores"))

        # 6. AST07: Partos múltiples o adopciones simultáneas (Art. 10)
        births = getattr(profile, 'birth_count_current_year', 0)
        if births > 1:
            deductions.append(Deduction("AST07", Decimal('1000') * births, "Partos o adopciones múltiples"))

        # 7. AST08: Familias numerosas (Art. 11)
        if getattr(profile, 'is_large_family', False):
            is_special = getattr(profile, 'is_large_family_special', False) or getattr(profile, 'large_family_category', '') == 'special'
            val = Decimal('2000') if is_special else Decimal('1000')
            deductions.append(Deduction("AST08", val, "Familia numerosa"))

        # 8. AST09: Familias monoparentales (Art. 12)
        if bi_total <= Decimal('45000'):
            if getattr(profile, 'is_monoparental', False):
                deductions.append(Deduction("AST09", Decimal('500'), "Familia monoparental"))

        # 9. AST10: Acogimiento familiar de menores (Art. 13)
        # Reusamos descendants_count si no conviven o son acogidos de forma simulada
        if getattr(profile, 'descendants_count', 0) > 0 and getattr(profile, 'custody_shared', False):
            deductions.append(Deduction("AST10", Decimal('500') * profile.descendants_count, "Acogimiento familiar de menores"))

        # 10. AST11: Certificación de gestión forestal sostenible (Art. 14)
        inversion_eco = profile.regional_data.get('donations_ecological_research_eur', Decimal('0'))
        if inversion_eco > 0:
            val = min(inversion_eco * Decimal('0.30'), Decimal('1000'))
            if val > 0:
                deductions.append(Deduction("AST11", val, "Certificación forestal sostenible"))

        # 11 y 20: Incompatibilidad entre Gastos 0-3 Años (AST12/Art. 14 bis) y Cuidado Descendientes hasta 25 Años (AST20/Art. 14 duodecies)
        # Evaluamos ambas de forma independiente y elegiremos la óptima para el contribuyente.
        val_ast12 = Decimal('0')
        val_ast20 = Decimal('0')

        # Evaluación AST12 (Centros 0-3 Años)
        es_despoblacion = profile.regional_data.get('resides_in_asturias_despoblacion', False)
        limite_bi_12 = Decimal('45000') if es_conjunta else Decimal('35000') if es_despoblacion else Decimal('37000') if es_conjunta else Decimal('26000')
        if bi_total <= limite_bi_12:
            hijos_0_3 = getattr(profile, 'children_under_3', 0)
            gasto_daycare = getattr(profile, 'daycare_expenses_eur', Decimal('0'))
            if hijos_0_3 > 0 and gasto_daycare > 0:
                pct = Decimal('0.30') if es_despoblacion else Decimal('0.15')
                lim_max = Decimal('1000') if es_despoblacion else Decimal('500')
                subvenciones = profile.regional_data.get('asturias_0to3_care_grants_eur', Decimal('0'))
                val_calc = min(gasto_daycare * pct, lim_max * hijos_0_3) - subvenciones
                val_ast12 = max(val_calc, Decimal('0'))

        # Evaluación AST20 (Cuidado hasta 25 Años)
        if bi_total <= limite_comun:
            hijos_hasta_25 = getattr(profile, 'descendants_count', 0)
            if hijos_hasta_25 > 0:
                val_ast20 = Decimal('600') * hijos_hasta_25

        # Resolución de Incompatibilidad (Mayor beneficio financiero)
        if val_ast12 > 0 and val_ast12 >= val_ast20:
            deductions.append(Deduction("AST12", val_ast12, "Gastos descendientes en centros 0 a 3 años"))
        elif val_ast20 > 0:
            deductions.append(Deduction("AST20", val_ast20, "Cuidado de descendientes hasta 25 años"))

        # 12. AST13: Adquisición de libros de texto y material escolar (Art. 14 ter)
        limite_bi_13 = Decimal('37000') if es_conjunta else Decimal('26000')
        if bi_total <= limite_bi_13:
            gasto_escolar = profile.regional_data.get('school_material_expenses_eur', Decimal('0'))
            if gasto_escolar > 0:
                becas = profile.regional_data.get('school_material_grants_eur', Decimal('0'))
                gasto_neto = max(gasto_escolar - becas, Decimal('0'))
                hijos = getattr(profile, 'descendants_count', 0)
                if hijos > 0:
                    if getattr(profile, 'is_large_family', False):
                        lim_unitario = Decimal('150') if es_conjunta else Decimal('75')
                    else:
                        if not es_conjunta:
                            if bi_total <= Decimal('6500'):
                                lim_unitario = Decimal('50')
                            elif bi_total <= Decimal('10000'):
                                lim_unitario = Decimal('37.50')
                            else:
                                lim_unitario = Decimal('25')
                        else:
                            if bi_total <= Decimal('12000'):
                                lim_unitario = Decimal('100')
                            elif bi_total <= Decimal('20000'):
                                lim_unitario = Decimal('75')
                            else:
                                lim_unitario = Decimal('50')
                    val = min(gasto_neto, lim_unitario * hijos)
                    if val > 0:
                        deductions.append(Deduction("AST13", val, "Libros de texto y material escolar"))

        # 13. AST14: Nacimiento/adopción en concejos en riesgo de despoblamiento sucesivos (Art. 14 quater)
        if bi_total <= limite_comun:
            if es_despoblacion and births > 0 and getattr(profile, 'descendants_count', 0) >= 2:
                deductions.append(Deduction("AST14", Decimal('300') * births, "Nacimiento en concejo de despoblación"))

        # 14. AST15: Autónomos en concejos en riesgo de despoblamiento o crisis demográfica (Art. 14 quinquies)
        if bi_total <= limite_comun:
            if profile.regional_data.get('is_autonomo_asturias_despoblacion', False):
                deductions.append(Deduction("AST15", Decimal('1000'), "Establecimiento como autónomo en zona rural"))

        # 15. AST16: Gastos de transporte público para residentes en concejos en riesgo de despoblamiento (Art. 14 sexies)
        if bi_total <= limite_comun:
            gasto_pers = profile.regional_data.get('asturias_transport_pass_expenses_eur', Decimal('0'))
            val_pers = min(gasto_pers, Decimal('100'))
            
            val_desc = Decimal('0')
            desc_outside = profile.regional_data.get('asturias_descendant_transport_study_outside_count', 0)
            gasto_desc = profile.regional_data.get('asturias_descendant_transport_expenses_eur', Decimal('0'))
            if desc_outside > 0 and gasto_desc > 0:
                val_desc = min(gasto_desc * Decimal('0.10'), Decimal('300') * desc_outside)

            val_total = val_pers + val_desc
            if val_total > 0:
                deductions.append(Deduction("AST16", val_total, "Gastos de transporte público en concejo despoblado"))

        # 16 e 17: Incompatibilidad entre Gastos Formación (AST17/Art. 14 septies) y Traslado por motivos laborales (AST18/Art. 14 octies)
        val_ast17 = Decimal('0')
        val_ast18 = Decimal('0')

        # Formación cualificada
        formacion = profile.regional_data.get('asturias_training_expenses_eur', Decimal('0'))
        if formacion > 0:
            val_ast17 = min(formacion, Decimal('2000'))

        # Traslado domicilio
        traslado = profile.regional_data.get('asturias_work_relocation_expenses_eur', Decimal('0'))
        if traslado > 0:
            lim_max = Decimal('2000') if profile.regional_data.get('asturias_is_relocation_highly_qualified', False) else Decimal('1000')
            val_ast18 = min(traslado * Decimal('0.15'), lim_max)

        if val_ast17 > 0 and val_ast17 >= val_ast18:
            deductions.append(Deduction("AST17", val_ast17, "Gastos de formación trabajos cualificados"))
        elif val_ast18 > 0:
            deductions.append(Deduction("AST18", val_ast18, "Traslado de domicilio fiscal por motivos laborales"))

        # 18. AST19: Adquisición o rehabilitación de vivienda habitual en determinados colectivos (Art. 14 decies)
        if bi_total <= limite_comun:
            inversion_viv = getattr(profile, 'mortgage_paid_eur', Decimal('0'))
            if inversion_viv > 0:
                base_deduc = min(inversion_viv, Decimal('10000'))
                pct = Decimal('0')
                if es_despoblacion:
                    es_colectivo_vivienda = (
                        profile.age <= 35 or
                        getattr(profile, 'is_large_family', False) or
                        getattr(profile, 'is_monoparental', False)
                    )
                    pct = Decimal('0.10') if es_colectivo_vivienda else Decimal('0.05')
                else:
                    if profile.age <= 35:
                        pct = Decimal('0.05')
                
                val = base_deduc * pct
                if val > 0:
                    deductions.append(Deduction("AST19", val, "Adquisición/rehabilitación de vivienda habitual"))

        # 19. AST21_VEH: Adquisición de vehículos eléctricos (Art. 14 undecies)
        inv_ve = profile.regional_data.get('asturias_vehicle_electric_investment_eur', Decimal('0'))
        if inv_ve > 0:
            coprop = profile.regional_data.get('asturias_vehicle_electric_coproprietors_count', 1)
            base_max = Decimal('50000') / Decimal(str(coprop))
            val = min(inv_ve, base_max) * Decimal('0.15')
            if val > 0:
                deductions.append(Deduction("AST21_VEH", val, "Adquisición de vehículo eléctrico"))

        # 21. AST22: Emancipación de jóvenes de hasta 35 años (Art. 14 terdecies)
        if bi_total <= limite_comun and profile.age <= 35:
            gastos_emancip = profile.regional_data.get('asturias_emancipation_expenses_eur', Decimal('0'))
            if gastos_emancip > 0:
                deductions.append(Deduction("AST22", min(gastos_emancip, Decimal('1000')), "Emancipación de jóvenes"))

        # 22. AST23: Ayudas a enfermos de Esclerosis Lateral Amiotrófica (ELA) (Art. 14 quaterdecies)
        subv_ela = profile.regional_data.get('asturias_ela_subsidies_received_eur', Decimal('0'))
        if subv_ela > 0:
            tipo_medio = (cuota_auton / big) if big > 0 else Decimal('0.15')
            deductions.append(Deduction("AST23", subv_ela * tipo_medio, "Ayudas públicas a enfermos de ELA"))

        # 23. AST24: Deducción arrendador por vivienda sostenible (Art. 14 quindecies)
        gastos_arrendador = profile.regional_data.get('asturias_sustainable_rental_expenses_eur', Decimal('0'))
        if gastos_arrendador > 0:
            coprop_arr = profile.regional_data.get('asturias_sustainable_rental_owners_count', 1)
            limite_arr = Decimal('500') / Decimal(str(coprop_arr))
            deductions.append(Deduction("AST24", min(gastos_arrendador, limite_arr), "Gastos del arrendador por vivienda sostenible"))

        # 24. AST25: Gastos vitales de contribuyentes de hasta 35 años (Art. 14 sexdecies)
        # Requisito estricto: BIG + BIA <= 28.000€
        if bi_total <= Decimal('28000') and profile.age <= 35:
            if profile.age <= 25:
                lim_vital = Decimal('2000')
            elif profile.age <= 30:
                lim_vital = Decimal('1500')
            else:
                lim_vital = Decimal('1000')
            deductions.append(Deduction("AST25", lim_vital, "Gastos vitales para jóvenes"))

        # 25. AST26: Descendientes por fallecimiento por accidente laboral (Art. 14 septendecies)
        desc_acc = profile.regional_data.get('asturias_accident_death_parent_descendants_count', 0)
        if desc_acc > 0:
            deductions.append(Deduction("AST26", Decimal('1000') * desc_acc, "Descendientes por fallecimiento de progenitor laboral"))

        # 26. AST27: Inversión en adquisición de acciones de nuevas entidades (Art. 14 octodecies)
        inv_acciones = profile.regional_data.get('new_entities_investment_eur', Decimal('0'))
        if inv_acciones > 0:
            deductions.append(Deduction("AST27", min(inv_acciones * Decimal('0.30'), Decimal('6000')), "Inversión en acciones de nuevas entidades"))

        # 27. AST28: Gastos por enfermedad celíaca (Art. 14 novodecies)
        if bi_total <= limite_comun:
            celiacos = profile.regional_data.get('asturias_celiac_members_count', 0)
            if celiacos > 0:
                deductions.append(Deduction("AST28", Decimal('100') * celiacos, "Gastos por enfermedad celíaca"))

        return deductions
