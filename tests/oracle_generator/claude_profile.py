/* ========================================================================================
   INGENIERÍA DE DATOS - SISTEMA IRPF 2026
   Análisis completo de variables: ENTRADA → DOMINIO → PROCESO → SALIDA
    ======================================================================================== */

/* ──────────────────────────────────────────────────────────────────────────────────────
   CAPA 1: ENTRADA (INPUT) — Variables del Formulario HTML
   ────────────────────────────────────────────────────────────────────────────────────── */

-- Configuración General
fiscal_year: INT (2025)
region: VARCHAR (17 CCAA: andalucia, aragon, asturias, baleares, canarias, cantabria, castilla_la_mancha, castilla_leon, cataluna, extremadura, galicia, madrid, murcia, la_rioja, valenciana, ceuta, melilla)

-- Datos Personales
age: INT (años)
disability: INT (grado 0-100)
is_victim: BOOLEAN (violencia de género o terrorismo)

-- Estado Civil
marital_status: VARCHAR ('single' | 'married')
joint_declaration: BOOLEAN (declaración conjunta Art. 84)
spouse_income: DECIMAL (€ renta cónyuge)

-- Pensión Compensatoria / Alimentos
alimonty: DECIMAL (€ Art. 55 — pensión ex-cónyuge reduce BIG)
child_support: DECIMAL (€ Art. 64/75 — pensiones alimentos)

-- Vivienda
rent_paid: DECIMAL (€ alquiler anual pagado)
is_rent_habitual: BOOLEAN (reducción habitual)

-- Familia
descendants: INT (número hijos/descendientes)
edu_expenses: DECIMAL (€ gastos educación)
family_type: VARCHAR ('none' | 'large_general' | 'large_special')
is_monoparental: BOOLEAN (familia monoparental)
single_parent_2_children: BOOLEAN (monoparental ≥2 hijos Art. 81bis)
birth_count: INT (nacimientos en año actual)

-- Descendientes Detallado (para deducciones Art. 81)
custody_shared: BOOLEAN (custodia compartida ×0.5)
children_under_3: INT (< 3 años → Art. 81 maternidad)
is_working_mother: BOOLEAN (madre trabajadora Art. 81)
daycare_expenses: DECIMAL (€ gastos guardería Art. 81)
children_disabled_33_65: INT (hijos discapacidad 33-65%)
children_disabled_over65: INT (hijos discapacidad >65%)

-- Discapacidad
disability_mobility_reduced: BOOLEAN (movilidad reducida)
disability_needs_help: BOOLEAN (necesita ayuda tercera persona)
spouse_disability: INT (grado discapacidad cónyuge Art. 81bis)

-- Ascendientes
ascendants_over65: INT (≥65 años, no perceptores renta)
ascendants_disabled: INT (discapacitados)

-- Planes de Pensiones (Art. 51/52)
pension_plan: DECIMAL (€ plan pensiones individual)
pension_empresa: DECIMAL (€ aportación empresa)
pension_spouse: DECIMAL (€ Art. 52.3 cónyuge, tope 1000€ si renta<8000€)

-- Trabajo (Art. 19, 20, 49)
gross_income: DECIMAL (€ retribuciones dinerarias)
withholdings_paid: DECIMAL (€ retenciones practicadas)
ss_employee: DECIMAL (€ Art. 19.2.a cotizaciones SS/mutualidades)
cuotas_sindicales: DECIMAL (€ Art. 19.2.d cuotas sindicales, sin límite)
professional_college: DECIMAL (€ Art. 19.2.d colegio profesional, tope 500€)
legal_defense: DECIMAL (€ Art. 19.2.e defensa jurídica, tope 300€)
geo_mobility: BOOLEAN (Art. 19.2.f movilidad geográfica 2000€→4000€)

-- Deducciones Estatales — Cuota (Art. 68, DA 9ª, DA 11ª, DA 50ª, Art. 81, 81bis)
startup_investment: DECIMAL (€ Art. 68.1 startups, 50%, max 50.000€)
donations: DECIMAL (€ Art. 68.3 donativos, 80% primeros 250€ + 40%, max 10% BI)
energy_inv: DECIMAL (€ DA 50ª eficiencia energética)
energy_type: INT (20 | 40 | 60 %)
mortgage_pre2013: BOOLEAN (DA 9ª hipoteca pre-2013)
mortgage_paid: DECIMAL (€ cantidad pagada, 7.5%, max 9.040€)
rent_pre2015: BOOLEAN (DA 11ª alquiler pre-2015)
rent_pre2015_paid: DECIMAL (€ cantidad pagada, 10.05%, max 9.040€, BI<24.107,20€)
political_party: DECIMAL (€ Art. 68.3.c afiliación partido, 20%, max 600€ base)
ceuta_melilla_income: BOOLEAN (Art. 65 Ceuta/Melilla)

-- CCAA — Campos Compartidos
is_celiac: BOOLEAN (enfermedad celíaca)
is_protected_housing: BOOLEAN (vivienda protegida)
vet_expenses: DECIMAL (€ gastos veterinarios)
gym_expenses: DECIMAL (€ gastos gimnasio/deportes)
legal_defense_expenses: DECIMAL (€ gastos defensa jurídica CCAA)


/* ──────────────────────────────────────────────────────────────────────────────────────
   CAPA 2: DOMINIO (DOMAIN ENTITIES) — Objetos Creados a Partir de Input
   ────────────────────────────────────────────────────────────────────────────────────── */

TABLE WorkIncome {
    retribuciones_dinerarias: DECIMAL
    retenciones: DECIMAL
    gastos_deducibles: DECIMAL              (Art. 19.2.a)
    cuotas_sindicales_eur: DECIMAL          (Art. 19.2.d)
    gastos_defensa_juridica_eur: DECIMAL    (Art. 19.2.e, tope 300€)
    professional_college_eur: DECIMAL       (Art. 19.2.d, tope 500€)
    geographic_mobility: BOOLEAN            (Art. 19.2.f)
    other_income: DECIMAL
    source_module: VARCHAR ('main')
}

TABLE TaxpayerProfile {
    age: INT
    disability_grade: INT
    is_victim_violence_gender_or_terrorism: BOOLEAN
    is_married: BOOLEAN
    joint_declaration: BOOLEAN
    spouse_income_eur: DECIMAL
    alimonty_ex_spouse_eur: DECIMAL (Art. 55)
    child_support_eur: DECIMAL (Art. 64/75)
    rent_paid_annual_eur: DECIMAL
    is_rent_habitual: BOOLEAN
    descendants_count: INT
    extra_education_expenses_eur: DECIMAL
    is_large_family: BOOLEAN
    large_family_category: VARCHAR ('none', 'general', 'special')
    is_monoparental: BOOLEAN
    single_parent_2_children: BOOLEAN
    birth_count_current_year: INT
    custody_shared: BOOLEAN
    children_under_3: INT
    is_working_mother: BOOLEAN
    daycare_expenses_eur: DECIMAL
    children_disabled_33_65: INT
    children_disabled_over65: INT
    disability_mobility_reduced: BOOLEAN
    disability_needs_help: BOOLEAN
    spouse_disability_grade: INT
    ascendants_over65: INT
    ascendants_disabled_count: INT
    pension_individual_eur: DECIMAL (Art. 51)
    pension_empresa_eur: DECIMAL (Art. 51)
    pension_spouse_eur: DECIMAL (Art. 52.3)
    startup_investment_eur: DECIMAL (Art. 68.1)
    donations_eur: DECIMAL (Art. 68.3)
    energy_efficiency_investment_eur: DECIMAL (DA 50ª)
    energy_efficiency_type: INT
    mortgage_pre2013: BOOLEAN (DA 9ª)
    mortgage_paid_eur: DECIMAL
    rent_pre2015: BOOLEAN (DA 11ª)
    rent_pre2015_paid_eur: DECIMAL
    political_party_eur: DECIMAL (Art. 68.3.c)
    ceuta_melilla_income: BOOLEAN (Art. 65)
    is_celiac: BOOLEAN
    is_protected_housing: BOOLEAN
    vet_expenses_eur: DECIMAL
    gym_expenses_eur: DECIMAL
    legal_defense_expenses_eur: DECIMAL
}

TABLE Dividend {
    date: DATETIME
    platform: VARCHAR (Binance, Kraken, Coinbase, Trading212, Degiro, eToro, etc.)
    asset: VARCHAR (Bitcoin, Ethereum, AAPL, etc.)
    isin: VARCHAR
    gross_eur: DECIMAL
    withholding_foreign_eur: DECIMAL
    withholding_spain_eur: DECIMAL
    country: VARCHAR
    type: VARCHAR ('dividend', 'interest', 'staking_yield', 'custody_fee')
    custody_fee_eur: DECIMAL
}

TABLE RentalIncome {
    property_id: VARCHAR
    gross_income: DECIMAL
    deductible_expenses: DECIMAL
    reduction_habitual: BOOLEAN
    contract_year: INT
    zona_tensionada: BOOLEAN (zona de mercado tensionado)
    alquiler_joven: BOOLEAN (alquiler para menores 35 años)
    rehabilitado: BOOLEAN (inmueble rehabilitado)
    notes: VARCHAR
}

TABLE OtherIncome {
    date: DATETIME
    description: VARCHAR
    gain_loss_eur: DECIMAL
    category: VARCHAR ('premios', 'subvenciones', 'imputacion_renta', 'juego', 'otros')
}

TABLE TaxEvent (crypto/stock) {
    date: DATETIME
    platform: VARCHAR
    asset: VARCHAR
    asset_type: VARCHAR ('crypto', 'stock', 'iic', 'equity')
    isin: VARCHAR (opcional)
    total_cost_eur: DECIMAL
    total_sale_eur: DECIMAL
    gain_loss_eur: DECIMAL
    quantity: DECIMAL
    is_wash_sale: BOOLEAN
    notes: VARCHAR
}


/* ──────────────────────────────────────────────────────────────────────────────────────
   CAPA 3: PROCESO (INTERMEDIATE CALCULATIONS) — Variables Generadas en IRPFCalculator
   ────────────────────────────────────────────────────────────────────────────────────── */

-- Trabajo (Art. 19, 20, 49)
gastos_art19_ae: DECIMAL                    (SS + sindicatos + min(colegio, 500€) + min(defensa, 300€))
gastos_art19_f: DECIMAL                     (2.000€ sin movilidad | 4.000€ con movilidad)
rnt_art20: DECIMAL                          (retribuciones - gastos_art19_ae)
rendimiento_neto_trabajo: DECIMAL           (rnt_art20 - gastos_art19_f)
reduccion_art20: DECIMAL                    (depende tramo rnt_art20:
                                              ≤14.852€: 7.302€
                                              14.852-17.673,52€: 7.302€ - 1,75×(rnt - 14.852)
                                              17.673,52-19.747,50€: 2.364,34€ - 1,14×(rnt - 17.673,52)
                                              >19.747,50€: 0€)

-- Pensiones (Art. 51, 52)
reduccion_pensiones: DECIMAL                (min(pension_individual + pension_empresa, max(2.000€, 1,5×rendimiento_neto_trabajo)))
                                            + min(pension_spouse, 1.000€) if spouse_income < 8.000€

-- Rendimientos Financieros (Dividendos, Capital Mobiliario)
rcm_bruto: DECIMAL                          (sum todos dividendos gross_eur)
ret_div_esp: DECIMAL                        (sum todos dividendos withholding_spain_eur)
custody_fees_total: DECIMAL                 (sum gastos custodia)
rcm_neto_gastos: DECIMAL                    (rcm_bruto - custody_fees_total)
rcm_final: DECIMAL                          (rcm_neto_gastos, puede ser negativo para compensación futura)

-- Ganancia/Pérdida Patrimonial (Crypto, Stock)
crypto_gain_loss: DECIMAL                   (sum TaxEvent tipo crypto, sin wash sales)
stock_gain_loss: DECIMAL                    (sum TaxEvent tipo stock, sin wash sales)
gpp_total: DECIMAL                          (crypto_gain_loss + stock_gain_loss)
gpp_neto: DECIMAL                           (gpp_total, puede ser negativo para remanente futuro)

-- Base Imponible
big: DECIMAL                                (trabajo_neto + rcm_final + rental_neto + other_bg - alimonty - pension_reduccion)
big_sin_ahorro: DECIMAL                     (BIG sin componente ahorro)
big_ahorro: DECIMAL                         (rcm_final + gpp_final, remanentes negativos)

-- Art. 55, 64, 75 — Reducciones
alimonty_reduccion: DECIMAL                 (pensióncompensatoria ex-cónyuge Art. 55)
child_support_reduccion: DECIMAL            (pensión alimentos Art. 64/75)

-- Mínimo del Contribuyente (Art. 60 LIRPF + Art. 81bis LIRPF)
minimo_total: DECIMAL                       (estatal: persona + edad + familia + discapacidad)
minimo_total_auton: DECIMAL                 (autonómico: persona + edad + familia + CCAA-específico)

Componentes mínimo_total:
  minimo_personal_estatal: 5.550€ (ó regional)
  minimo_edad: 1.150€ (60-64) | 1.400€ (≥65)
  minimo_familia: INT × Decimal (número hijos, minusvalías, custodia compartida)
  minimo_discapacidad: Decimal (33-64% | ≥65% | movilidad reducida | necesita ayuda)

-- Cuota Íntegra (Escalas de Gravamen Art. 63, 66 LIRPF)
cuota_integra_estatal: DECIMAL              (aplicar escala general estatal a BIG ó base_general)
cuota_integra_ahorro: DECIMAL               (aplicar escala ahorro estatal a base_ahorro)
cuota_integra_auton: DECIMAL                (aplicar escala autonómica a BIG ó base_general)

-- Art. 84 — Reducción Tributación Conjunta
reduccion_conjunta: DECIMAL                 (3.400€ si married + joint_declaration
                                              2.150€ si monoparental ≥2 hijos)

-- Deducciones (Art. 68, 81, 81bis, DA 9ª, DA 11ª, DA 50ª)
deducciones_estatales: LIST<Deduction>      (Art. 68.1 startups, Art. 68.3 donativos, Art. 68.3.c político, DA 9ª hipoteca, DA 11ª alquiler, DA 50ª energía)
deducciones_autonomicas: LIST<Deduction>    (específicas de cada CCAA)
deducciones_ccaa: LIST<Deduction>           (deducción cuota autonómica)
deducciones_diferenciales: LIST<Deduction>  (Art. 81 maternidad+guardería, Art. 81bis familia numerosa/monoparental/cónyuge discapacitado)

Nota: deducciones_estatales restan cuota_integra → cuota_liquida ≥ 0
      deducciones_diferenciales pueden hacer cuota_resultante < 0 → A devolver

-- Cuota Líquida (después de deducciones)
cuota_liquida_estatal: DECIMAL              (cuota_integra_estatal - deducciones_estatales)
cuota_liquida_auton: DECIMAL                (cuota_integra_auton - deducciones_ccaa)
cuota_liquida: DECIMAL                      (cuota_liquida_estatal + cuota_liquida_auton)

-- Cuota Resultante (después de reducciones)
cuota_resultante: DECIMAL                   (cuota_liquida - reduccion_conjunta - deducciones_diferenciales)

-- Deducciones por Doble Imposición / Rentas Trabajo
deduccion_doble_imposicion: DECIMAL         (retenciones capital español, compensación)
deduccion_rentas_trabajo: DECIMAL           (retenciones trabajo)

-- Resultado Final
retenciones_trabajo_total: DECIMAL          (sum work.retenciones)
retenciones_capital: DECIMAL                (sum ret_div_esp)
cuota_diferencial: DECIMAL                  (cuota_resultante - retenciones_trabajo - retenciones_capital)
resultado: DECIMAL                          (cuota_diferencial; >0: a pagar, <0: a devolver)

-- Remanentes a Futuro (Art. 49 — compensación 4 años)
remanente_gpp_futuro: DECIMAL               (min(gpp_neto, 0) → puede compensarse en futuro)
remanente_rcm_futuro: DECIMAL               (min(rcm_final, 0) → puede compensarse en futuro)


/* ──────────────────────────────────────────────────────────────────────────────────────
   CAPA 4: SALIDA (OUTPUT) — Diccionario de Resultado IRPFCalculator.calculate().raw_summary
   ────────────────────────────────────────────────────────────────────────────────────── */

RESULT DICTIONARY {
    -- Configuración
    region: VARCHAR
    
    -- Trabajo (desglose)
    work_bruto: DECIMAL
    work_ss: DECIMAL
    work_gastos: DECIMAL (gastos Art. 19.2.a + Art. 19.2.d + Art. 19.2.e)
    work_retenciones: DECIMAL
    work_gastos_ss_otros: DECIMAL (sin SS)
    work_pension_empresa: DECIMAL
    reduccion_pensiones: DECIMAL
    work_neto: DECIMAL (rendimiento_trabajo_neto_reducido después Art. 20)
    rendimiento_neto_trabajo: DECIMAL (before Art. 20 reduction)
    
    -- Alquiler
    rental_bruto: DECIMAL
    rental_gastos: DECIMAL
    rental_neto: DECIMAL
    
    -- Otros
    other_bg: DECIMAL
    
    -- Base Imponible
    base_imponible_general: DECIMAL (sin ahorro)
    base_general: DECIMAL (BIG después reducciones)
    base_ahorro: DECIMAL (capital mobiliario + ganancias patrimoniales)
    
    -- Capital Mobiliario
    capital_yield_total: DECIMAL (rcm_bruto)
    gastos_custodia_total: DECIMAL
    rcm_neto_gastos: DECIMAL
    rcm_neto_reducido: DECIMAL
    
    dividendos_brutos: DICT {val: DECIMAL}
    retencion_dividendos: DICT {val: DECIMAL}
    dividend_details: DICT {
        assets: DICT {
            asset_name: {
                gross: DECIMAL,
                withholding: DECIMAL,
                net: DECIMAL,
                quantity: INT,
                percentage: DECIMAL
            }
        }
    }
    interest_details: DICT {
        assets: DICT {
            asset_name: {gross: DECIMAL, ...}
        }
    }
    
    -- Ganancias/Pérdidas Patrimoniales
    stock_gain_loss: DECIMAL
    gpp_neto: DECIMAL
    crypto_gain_loss: DECIMAL
    
    -- Mínimo del Contribuyente
    minimo_pf_estatal: DECIMAL
    minimo_pf_autonomico: DECIMAL
    
    -- Cuota
    cuota_integra_estatal: DECIMAL
    cuota_integra_autonomica: DECIMAL
    
    -- Deducciones
    deducciones_estatales: LIST<{box_id, value, description}>
    deducciones_autonomicas: LIST<{box_id, value, description}>
    deducciones_ccaa: LIST<{box_id, value, description}>
    deducciones_diferenciales: LIST<{box_id, value, description}>
    deduccion_doble_imposicion: DECIMAL
    deduccion_rentas_trabajo: DECIMAL
    
    -- Reducciones
    alimonty_reduccion: DECIMAL (Art. 55)
    reduccion_conjunta: DECIMAL (Art. 84)
    
    -- Cuota Líquida / Resultante
    cuota_liquida_estatal: DECIMAL
    cuota_liquida_autonomica: DECIMAL
    cuota_liquida: DECIMAL
    cuota_resultante: DECIMAL
    
    -- Retenciones
    retenciones_trabajo_total: DECIMAL
    retenciones_capital: DECIMAL
    
    -- Resultado
    cuota_diferencial: DECIMAL
    resultado: DECIMAL (>0: A PAGAR, <0: A DEVOLVER)
    resultado_label: VARCHAR ('A PAGAR' | 'A DEVOLVER')
    
    -- Remanentes
    remanente_gpp_futuro: DECIMAL (Art. 49 — compensación futura)
    remanente_rcm_futuro: DECIMAL (Art. 49 — compensación futura)
    
    -- Detalles AEAT (detallado por activo/plataforma)
    cripto_aeat: DICT {
        asset: {
            adquisicion: DECIMAL,
            transmision: DECIMAL,
            ganancia: DECIMAL,
            perdida: DECIMAL
        }
    }
    acciones_aeat: DICT {isin: {...}}
    iic_aeat: DICT
    otros_aeat: DICT
    inmuebles_aeat: DICT {} (empty, TODO)
    
    custody_fees: LIST<{date, platform, asset, fee}>
    
    -- Wash Sales (operaciones excluidas)
    wash_sale_events: LIST<{date, platform, asset, gain_loss_eur, notes}>
    
    -- Deducciones Aplicadas (rastreo de cuáles se aplicaron)
    applied_deductions: DICT {
        "state": LIST<Deduction>,
        "regional": LIST<Deduction>,
        "differential": LIST<Deduction>
    }
}


/* ──────────────────────────────────────────────────────────────────────────────────────
   FLUJOS DE CÁLCULO PRINCIPALES
   ────────────────────────────────────────────────────────────────────────────────────── */

FLUJO 1: Cálculo de Base Imponible General
┌─────────────────────────────────────────┐
│ Trabajo                                 │
│ rendimiento_neto_trabajo (after Art.20) │
│ - alimonty_ex_spouse (Art. 55)          │
│ - reduccion_pensiones (Art. 51/52)      │
├─────────────────────────────────────────┤
│ + Alquiler                              │
│   (reduction habitual si aplica)        │
├─────────────────────────────────────────┤
│ + Otros (Premios, subvenciones)         │
├─────────────────────────────────────────┤
│ + Capital Mobiliario (RCM)              │
│   (neto gastos custodia)                │
├─────────────────────────────────────────┤
│ = BASE IMPONIBLE GENERAL                │
└─────────────────────────────────────────┘

FLUJO 2: Cálculo de Base de Ahorro
┌─────────────────────────────────────────┐
│ Capital Mobiliario (RCM)                │
│ + Ganancias Patrimoniales (GPP)         │
│ = BASE DE AHORRO                        │
│ (pueden ser negativos → remanente)      │
└─────────────────────────────────────────┘

FLUJO 3: Cálculo de Cuota Íntegra
┌─────────────────────────────────────────┐
│ Base General / Escala General (AEAT)    │
│ → Cuota Íntegra Estatal                 │
│ + Base General / Escala Regional        │
│ → Cuota Íntegra Autonómica              │
│ + Base Ahorro / Escala Ahorro (AEAT)    │
│ → Cuota Íntegra Ahorro (estatal)        │
│ + Base Ahorro / Escala Regional Ahorro  │
│ → Cuota Íntegra Ahorro Regional         │
└─────────────────────────────────────────┘

FLUJO 4: Aplicación de Mínimo del Contribuyente
┌─────────────────────────────────────────┐
│ Calcular Mínimo Estatal + Regional      │
│ Si (Cuota Integra Estatal < Mínimo):    │
│   Cuota = Mínimo                        │
│ Idem Regional                           │
└─────────────────────────────────────────┘

FLUJO 5: Aplicación de Deducciones (Orden)
┌─────────────────────────────────────────┐
│ 1. Deducciones Estatales (cuota)        │
│    → Cuota Líquida Estatal ≥ 0          │
│ 2. Deducciones Autonómicas (cuota)      │
│    → Cuota Líquida Autonómica ≥ 0       │
│ 3. Reducción Art. 84 (Conjunta)         │
│ 4. Deducciones Diferenciales            │
│    → Cuota Resultante PUEDE SER < 0     │
└─────────────────────────────────────────┘

FLUJO 6: Cálculo de Resultado
┌─────────────────────────────────────────┐
│ Cuota Resultante                        │
│ - Retenciones Trabajo                   │
│ - Retenciones Capital (español)         │
│ = CUOTA DIFERENCIAL / RESULTADO         │
│                                         │
│ Si > 0: A PAGAR                         │
│ Si < 0: A DEVOLVER                      │
│ Si = 0: DECLARACIÓN NEUTRA              │
└─────────────────────────────────────────┘


/* ──────────────────────────────────────────────────────────────────────────────────────
   REGIONES IMPLEMENTADAS (17 CCAA)
   ────────────────────────────────────────────────────────────────────────────────────── */

REGIÓN_MAP {
    "andalucia":          AndaluciaRegion,
    "aragon":             AragonRegion,
    "asturias":           AsturiasRegion,
    "baleares":           BalearsRegion,
    "canarias":           CanariasRegion,
    "cantabria":          CantabriaRegion,
    "castilla_la_mancha": CastillaLaManchaRegion,
    "castilla_leon":      CastillaLeonRegion,
    "cataluna":           CatalunaRegion,
    "extremadura":        ExtremaduraRegion,
    "galicia":            GaliciaRegion,
    "madrid":             MadridRegion,
    "murcia":             MurciaRegion,
    "la_rioja":           LaRiojaRegion,
    "valenciana":         ValencianaRegion,
    "ceuta":              CeutaMelillaRegion,
    "melilla":            CeutaMelillaRegion
}

Cada región implementa:
  - get_general_scale() → [(threshold, rate), ...]
  - get_savings_scale() → [(threshold, rate), ...]
  - get_personal_minimum() → Decimal (5550-6105€)
  - get_age_supplements() → (Decimal, Decimal) (60-64, ≥65)
  - get_quota_deductions(profile, big, bia, cuota_auton) → List<Deduction>


/* ──────────────────────────────────────────────────────────────────────────────────────
   LÍMITES Y UMBRALES CRÍTICOS (2025)
   ────────────────────────────────────────────────────────────────────────────────────── */

ART. 20 — Reducciones por Rendimiento del Trabajo:
  ├─ ≤ 14.852€: reducción = 7.302€
  ├─ 14.852 - 17.673,52€: reducción = 7.302€ - 1,75 × (rnt - 14.852)
  ├─ 17.673,52 - 19.747,50€: reducción = 2.364,34€ - 1,14 × (rnt - 17.673,52)
  └─ > 19.747,50€: reducción = 0€

ART. 51/52 — Reducciones por Planes de Pensiones:
  └─ max(2.000€, 1,5 × rendimiento_neto_trabajo)

ART. 52.3 — Aportación por Cónyuge:
  └─ max 1.000€ si spouse_income < 8.000€

ART. 55 — Pensión Compensatoria:
  └─ reduce BIG directamente

ART. 68.1 — Startups:
  └─ 50% de inversión, max 50.000€

ART. 68.3 — Donativos:
  └─ 80% primeros 250€ + 40% resto, max 10% BI

ART. 81 — Maternidad:
  └─ 1.200€ × hijos < 3 años (si madre trabajadora)
  └─ Guardería: max 1.000€ × hijo

ART. 81bis — Familia Numerosa / Monoparental:
  ├─ General: 1.200€
  ├─ Especial: 2.400€
  └─ Monoparental ≥2 hijos: 1.200€

ART. 84 — Reducción Tributación Conjunta:
  ├─ Married + joint: 3.400€
  └─ Monoparental ≥2 hijos: 2.150€

DA 9ª — Hipoteca pre-2013:
  └─ 7,5% de cantidad pagada, max 9.040€

DA 11ª — Alquiler pre-2015:
  └─ 10,05%, max 9.040€, BI < 24.107,20€

DA 50ª — Eficiencia Energética:
  ├─ 20%: max 5.000€
  ├─ 40%: max 7.500€
  └─ 60%: max 15.000€

ART. 19.2.e — Defensa Jurídica:
  └─ max 300€

ART. 19.2.d — Colegio Profesional:
  └─ max 500€

ART. 19.2.f — Movilidad Geográfica:
  ├─ Sin movilidad: 2.000€
  └─ Con movilidad: 4.000€

ART. 65 — Ceuta/Melilla:
  └─ Deducción 60% de cuota autonómica


/* ──────────────────────────────────────────────────────────────────────────────────────
   VALIDACIONES CRÍTICAS PARA GENERADOR DE TESTS
   ────────────────────────────────────────────────────────────────────────────────────── */

1. BIG NUNCA NEGATIVA: max(big, 0)
2. CUOTA LÍQUIDA NUNCA NEGATIVA: max(cuota_liquida, 0)
3. DEDUCCIONES DIFERENCIALES PUEDEN HACER CUOTA RESULTANTE NEGATIVA
4. REMANENTES (GPP, RCM) PUEDEN SER NEGATIVOS → Art. 49 (compensación 4 años)
5. WASH SALES: eventos con is_wash_sale=True NO cuentan en GPP
6. CUSTODIA COMPARTIDA: × 0,5 para mínimo del contribuyente
7. PENSION_SPOUSE: solo si spouse_income < 8.000€ AND valor ≤ 1.000€
8. ALEGRÍA ENERGÉTICA: los tramos (20%, 40%, 60%) generan límites diferentes
9. ALQUILER PRE-2015: solo si BI < 24.107,20€ + escalado si BI 17.707,20-24.107,20€
10. DECLARACIÓN CONJUNTA: solo si married=true
11. RETENCIONES: se restan al final del cálculo, no en la base

Uso para Generador de Tests:

Este esquema te permite generar casos de prueba parametrizados:

Happy path: contribuyente sencillo (solo trabajo + mínimo base)
Casos límite: en cada umbral (14.852€, 19.747,50€, etc.)
Intersecciones: trabajo + alquiler + familia + deducciones simultáneamente
Negativos: pérdidas patrimoniales, monoparental sin hijos, discapacitado sin reducción
Regionales: mismo contribuyente en 17 CCAA → comparar resultado
