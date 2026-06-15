from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Union


@dataclass
class LossCarryForward:
    balances: Dict[int, Decimal] = field(default_factory=dict)

    @classmethod
    def from_input(
        cls, data: Union[Decimal, Dict[int, Decimal], "LossCarryForward"], current_year: int
    ) -> "LossCarryForward":
        if isinstance(data, LossCarryForward):
            return data
        if isinstance(data, dict):
            return cls(balances={int(k): max(Decimal(str(v)), Decimal("0")) for k, v in data.items()})
        val = max(Decimal(str(data)), Decimal("0"))
        return cls(balances={current_year - 1: val} if val > 0 else {})

    def get_valid_total(self, current_year: int) -> Decimal:
        return sum(amt for year, amt in self.balances.items() if 0 < (current_year - year) <= 4 and amt > 0)

    def consume(self, amount: Decimal, current_year: int) -> Dict[int, Decimal]:
        consumed: Dict[int, Decimal] = {}
        remaining = amount
        valid_years = sorted([y for y in self.balances.keys() if 0 < (current_year - y) <= 4])
        for year in valid_years:
            if remaining <= 0:
                break
            available = max(self.balances[year], Decimal("0"))
            if available > 0:
                use = min(available, remaining)
                self.balances[year] -= use
                consumed[year] = use
                remaining -= use
        return consumed


class IncomeSubtype(Enum):
    LOTERIAS_OFICIALES = "loterias_oficiales"
    OTRAS = "otras"


class FamilyRole(Enum):
    DESCENDANT = "descendant"
    ASCENDANT = "ascendant"


@dataclass(frozen=True)
class FamilyMember:
    role: FamilyRole
    age: int
    rentas_obtenidas: Decimal = Decimal("0.00")
    presenta_declaracion_independiente: bool = False
    convivencia_meses: int = 12
    disability_grade: int = 0


@dataclass(frozen=True)
class Dividend:
    """Rendimiento del Capital Mobiliario (Dividendos, Staking, Intereses, Gastos)."""

    date: datetime
    platform: str
    asset: str
    isin: str
    gross_eur: Decimal
    withholding_foreign_eur: Decimal
    withholding_spain_eur: Decimal
    country: str = ""
    type: str = "dividend"
    is_creator: bool = False
    custody_fee_eur: Decimal = Decimal("0.0")


@dataclass(frozen=True)
class WorkIncome:
    """Rendimientos del Trabajo (Base General)."""

    retribuciones_dinerarias: Decimal
    retenciones: Decimal
    gastos_deducibles: Decimal  # Art. 19.2.a — cotizaciones SS/mutualidades
    cuotas_sindicales_eur: Decimal = Decimal("0")  # Art. 19.2.d — sin límite
    gastos_defensa_juridica_eur: Decimal = Decimal("0")  # Art. 19.2.e — tope 300€
    professional_college_eur: Decimal = Decimal("0")  # Art. 19.2.d — tope 500€
    geographic_mobility: bool = False  # Art. 19.2.f — 2.000→4.000€
    other_income: Decimal = Decimal("0.0")
    health_insurance_eur: Decimal = Decimal("0.0")
    rendimientos_irregulares_eur: Decimal = Decimal("0")  # Art. 18.2 LIRPF
    source_module: str = "main"


@dataclass(frozen=True)
class RealEstateAsset:
    """Inmueble con datos fiscales para amortización."""

    expenses_maintenance: Decimal = Decimal("0")
    valor_catastral: Decimal = Decimal("0")


@dataclass(frozen=True)
class CapitalGains:
    date: datetime
    description: str
    gain_loss_eur: Decimal
    category: str
    is_deferred_payment: bool = False
    source_module: str = "main"


@dataclass(frozen=True)
class RentalIncome:
    """Rendimiento del Capital Inmobiliario (Casilla 0091) e Imputaciones."""

    property_id: str
    gross_income: Decimal = Decimal("0")
    deductible_expenses: Decimal = Decimal("0")
    reduction_habitual: bool = True
    contract_year: int = 2023
    contract_date: datetime = None
    zona_tensionada: bool = False
    reduccion_renta_tensionada_5_pct: bool = False
    alquiler_joven: bool = False
    rehabilitado: bool = False

    # --- Nuevos campos fiscales inyectados (Fase 3) ---
    tipo: str = "arrendado"  # Valores: "arrendado" o "imputado"
    expenses_maintenance: Decimal = Decimal("0")
    expenses_mortgage_interest: Decimal = Decimal("0")
    adquisicion_construccion_eur: Decimal = Decimal("0")
    catastral_construccion_eur: Decimal = Decimal("0")
    valor_catastral: Decimal = Decimal("0")
    valor_catastral_revisado: bool = False
    dias_a_disposicion: int = 365
    # ---------------------------------------------------

    source_module: str = "main_bienes_inmuebles"
    notes: str = ""


@dataclass(frozen=True)
class OtherIncome:
    """Otras Ganancias/Pérdidas (Inmuebles, Premios, Subvenciones)."""

    date: datetime
    description: str
    gain_loss_eur: Decimal
    category: str
    subtype: IncomeSubtype = IncomeSubtype.OTRAS
    porcentaje_titularidad: Decimal = Decimal("100.00")
    withholding_eur: Decimal = Decimal("0.00")
    is_deferred_payment: bool = False
    source_module: str = "main_otros_pyg"
    notes: str = ""
    sujeto_gravamen_especial: bool = False
    total_sale_value_eur: Decimal = Decimal('0')
    current_year_due_payments_eur: Decimal = Decimal('0')

    def __post_init__(self):
        if not (Decimal("0") < self.porcentaje_titularidad <= Decimal("100.00")):
            raise ValueError("Titularidad debe estar entre (0, 100]")
        if (
            isinstance(self.gain_loss_eur, float)
            or isinstance(self.porcentaje_titularidad, float)
            or isinstance(self.withholding_eur, float)
        ):
            raise ValueError("Se debe usar Decimal estricto")


@dataclass(frozen=True)
class BusinessIncome:
    """Rendimientos de Actividades Económicas."""

    gross_income: Decimal = Decimal("0")
    expenses: Decimal = Decimal("0")
    ingresos_explotacion: Decimal = Decimal("0")
    gastos_explotacion: Decimal = Decimal("0")
    gastos_suministros_hogar_eur: Decimal = Decimal("0")
    porcentaje_afectacion_vivienda: Decimal = Decimal("0")
    estimacion_simplificada: bool = False
    rendimientos_irregulares_eur: Decimal = Decimal("0")  # Art. 32 LIRPF
    source_module: str = "main_business"
    notes: str = ""


@dataclass
class TaxpayerProfile:
    """Perfil del Contribuyente para Deducciones 2025."""

    age: int
    region: str = "estatal"
    regional_data: dict = field(default_factory=dict)
    disability_grade: int = 0
    is_victim_violence_gender_or_terrorism: bool = False
    strict_dgt_compliance: bool = False

    # Estado civil y declaración
    is_married: bool = False
    joint_declaration: bool = False
    spouse_income_eur: Decimal = Decimal("0")
    spouse_ss_eur: Decimal = Decimal("0")  # SS/cotizaciones cónyuge (conjunta)
    spouse_retenciones_eur: Decimal = Decimal("0")  # Retenciones cónyuge (conjunta)
    spouse_cuotas_sindicales_eur: Decimal = Decimal("0")
    spouse_gastos_defensa_juridica_eur: Decimal = Decimal("0")
    spouse_professional_college_eur: Decimal = Decimal("0")

    # Pensión compensatoria / anualidades por alimentos
    alimonty_ex_spouse_eur: Decimal = Decimal("0")  # Art. 55 — reduce BIG
    child_support_eur: Decimal = Decimal("0")  # Art. 64/75 — split BLG

    # Alquiler
    rent_paid_annual_eur: Decimal = Decimal("0.0")
    is_rent_habitual: bool = False

    # Familia
    descendants_count: int = 0
    extra_education_expenses_eur: Decimal = Decimal("0.0")
    is_large_family: bool = False
    is_large_family_special: bool = False
    large_family_category: str = "none"  # 'none'|'general'|'special'
    is_monoparental: bool = False
    single_parent_2_children: bool = False
    birth_count_current_year: int = 0

    # Descendientes detallado
    custody_shared: bool = False
    children_under_3: int = 0
    is_working_mother: bool = False
    daycare_expenses_eur: Decimal = Decimal("0")
    children_disabled_33_65: int = 0
    children_disabled_over65: int = 0

    # Discapacidad
    disability_mobility_reduced: bool = False
    disability_needs_help: bool = False
    spouse_disability_grade: int = 0

    # Ascendientes
    ascendants_over65: int = 0
    ascendants_over75: int = 0
    ascendants_disabled_count: int = 0

    # Familiares detallados (Vector 2 Mínimos)
    family_members: List[FamilyMember] = field(default_factory=list)

    # Planes de Pensiones (Art. 51/52 LIRPF)
    pension_individual_eur: Decimal = Decimal("0.0")
    pension_empresa_eur: Decimal = Decimal("0.0")
    pension_spouse_eur: Decimal = Decimal("0")
    spouse_pension_individual_eur: Decimal = Decimal("0")  # Plan individual cónyuge (conjunta)
    spouse_pension_empresa_eur: Decimal = Decimal("0")  # Plan empresa cónyuge (conjunta)

    # Deducciones estatales — cuota
    startup_investment_eur: Decimal = Decimal("0.0")
    startup_ownership_pct: Decimal = Decimal("0.0")
    startup_years_since_constitution: int = 0
    startup_is_emerging: bool = False
    donations_eur: Decimal = Decimal("0.0")
    donations_fidelized: bool = False

    electric_vehicle_investment_eur: Decimal = Decimal("0.0")
    electric_vehicle_subsidies_eur: Decimal = Decimal("0.0")
    charging_point_investment_eur: Decimal = Decimal("0.0")
    charging_point_is_electronic_payment: bool = False

    maternity_months: Dict[int, Decimal] = field(default_factory=dict)
    exempt_from_ss_limit: bool = False
    ss_employee_eur: Decimal = Decimal("0")
    ss_self_employed_eur: Decimal = Decimal("0")

    energy_efficiency_investment_eur: Decimal = Decimal("0.0")
    energy_efficiency_type: int = 0
    energy_efficiency_prior_years_base_eur: Decimal = Decimal("0.0")
    mortgage_pre2013: bool = False
    mortgage_paid_eur: Decimal = Decimal("0")
    mortgage_acquisition_date: str = ""
    rent_pre2015: bool = False
    rent_pre2015_paid_eur: Decimal = Decimal("0")
    political_party_eur: Decimal = Decimal("0")
    ceuta_melilla_income: bool = False
    internet_access_expenses_eur: Decimal = Decimal("0.0")
    health_optical_expenses_eur: Decimal = Decimal("0.0")

    # CCAA — campos compartidos
    is_celiac: bool = False
    is_protected_housing: bool = False
    vet_expenses_eur: Decimal = Decimal("0.0")
    gym_expenses_eur: Decimal = Decimal("0.0")
    legal_defense_expenses_eur: Decimal = Decimal("0.0")
    internet_access_expenses_eur: Decimal = Decimal("0.0")
    health_dental_expenses_eur: Decimal = Decimal("0.0")

    def __post_init__(self):
        # Sanitización normativa AEAT en origen (Cero Alucinaciones)
        if self.is_monoparental and self.descendants_count == 0:
            self.is_monoparental = False

        if self.is_large_family and self.descendants_count < 2:
            self.is_large_family = False
            self.is_large_family_special = False
            self.large_family_category = "none"

        if self.single_parent_2_children and self.descendants_count < 2:
            self.single_parent_2_children = False

        # Purgas autonómicas para flags de diccionarios
        if self.regional_data:
            if self.regional_data.get("cantabria_is_monoparental", False) and self.descendants_count == 0:
                self.regional_data["cantabria_is_monoparental"] = False
            if self.regional_data.get("clm_is_monoparental", False) and self.descendants_count == 0:
                self.regional_data["clm_is_monoparental"] = False


@dataclass
class Deduction:
    """Resultado de una deducción aplicada."""

    box_id: str
    value: Decimal
    description: str = ""
    metadata: dict = field(default_factory=dict)
