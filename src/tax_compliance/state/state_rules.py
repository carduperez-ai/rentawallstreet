# src/tax_compliance/deductions/state_rules.py
from decimal import Decimal
from typing import List
from src.domain.fiscal_entities import TaxpayerProfile, Deduction


class StateDeductor:
    """Deducciones estatales LIRPF 2025."""

    @classmethod
    def calculate_quota_deductions(
        cls, profile: TaxpayerProfile, bi_total: Decimal
    ) -> List[Deduction]:
        """Restan cuota íntegra (resultado: cuota líquida ≥ 0)."""
        deductions = []

        # DA 9ª — Hipoteca pre-2013 (7,5% base máx 9.040€)
        if getattr(profile, 'mortgage_pre2013', False) and getattr(profile, 'mortgage_paid_eur', Decimal('0')) > 0:
            base = min(profile.mortgage_paid_eur, Decimal('9040'))
            val = base * Decimal('0.075')
            deductions.append(Deduction("ST_DA9", val, "Deducción Hipoteca pre-2013 (DA 9ª LIRPF)"))

        # DA 11ª — Alquiler pre-2015 (10,05%, BI < 24.107,20€)
        if getattr(profile, 'rent_pre2015', False) and getattr(profile, 'rent_pre2015_paid_eur', Decimal('0')) > 0:
            if bi_total < Decimal('24107.20'):
                base = min(profile.rent_pre2015_paid_eur, Decimal('9040'))
                if bi_total <= Decimal('17707.20'):
                    val = base * Decimal('0.1005')
                else:
                    factor = Decimal('1') - (bi_total - Decimal('17707.20')) / Decimal('6400')
                    val = base * Decimal('0.1005') * factor
                if val > 0:
                    deductions.append(Deduction("ST_DA11", val, "Deducción Alquiler pre-2015 (DA 11ª LIRPF)"))

        # Art. 68.1 — Inversión startups (50% sobre base; base máx 100.000€ → deducción máx 50.000€)
        if getattr(profile, 'startup_investment_eur', Decimal('0')) > 0:
            base_inv = min(profile.startup_investment_eur, Decimal('100000'))
            val = base_inv * Decimal('0.50')
            if val > 0:
                deductions.append(Deduction("ST01", val, "Inversión Empresas Nueva Creación (Art. 68.1)"))

        # Art. 68.3 — Donativos (80% primeros 250€ + 40% resto; base máx 10% Base Liquidable)
        if getattr(profile, 'donations_eur', Decimal('0')) > 0:
            base_don = min(profile.donations_eur, bi_total * Decimal('0.10'))
            primero = min(base_don, Decimal('250'))
            resto = max(base_don - Decimal('250'), Decimal('0'))
            rate_resto = Decimal('0.45') if getattr(profile, 'donations_recurrent', False) else Decimal('0.40')
            val = primero * Decimal('0.80') + resto * rate_resto
            if val > 0:
                deductions.append(Deduction("ST03", val, "Donativos a Entidades (Art. 68.3)"))

        # Art. 68.3.c — Afiliación partido político (20% máx 600€ base)
        if getattr(profile, 'political_party_eur', Decimal('0')) > 0:
            val = min(profile.political_party_eur, Decimal('600')) * Decimal('0.20')
            if val > 0:
                deductions.append(Deduction("ST_POL", val, "Cuotas Partido Político (Art. 68.3.c)"))

        # DA 50ª — Eficiencia energética (20/40/60%); tipo sobre cantidades satisfechas, tope sobre cuota deducible
        if getattr(profile, 'energy_efficiency_investment_eur', Decimal('0')) > 0 and getattr(profile, 'energy_efficiency_type', 0) > 0:
            rate = Decimal(str(profile.energy_efficiency_type)) / Decimal('100')
            limites = {20: Decimal('5000'), 40: Decimal('7500'), 60: Decimal('15000')}
            limite = limites.get(profile.energy_efficiency_type, Decimal('5000'))
            val = min(profile.energy_efficiency_investment_eur * rate, limite)  # tope sobre cuota, no sobre base
            if val > 0:
                deductions.append(Deduction("ST04", val, f"Mejora Eficiencia Energética ({profile.energy_efficiency_type}%) (DA 50ª)"))

        return deductions

    @classmethod
    def calculate_differential_deductions(
        cls, profile: TaxpayerProfile
    ) -> List[Deduction]:
        """Art. 81/81 bis — pueden superar cuota → resultado A devolver."""
        deductions = []

        # Art. 81 — Maternidad (1.200€/año por hijo < 3 años, trabaja)
        children_u3 = getattr(profile, 'children_under_3', 0)
        if children_u3 > 0 and getattr(profile, 'is_working_mother', False):
            deductions.append(Deduction("ART81_MAT", Decimal('1200') * children_u3,
                                        f"Maternidad — {children_u3} hijo(s) < 3 años (Art. 81)"))
            daycare = getattr(profile, 'daycare_expenses_eur', Decimal('0'))
            if daycare > 0:
                val_daycare = min(daycare, Decimal('1000') * children_u3)
                deductions.append(Deduction("ART81_GUAR", val_daycare, "Gastos Guardería (Art. 81)"))

        # Art. 81 bis — Familia numerosa
        large_cat = getattr(profile, 'large_family_category', 'none')
        if large_cat == 'general':
            deductions.append(Deduction("ART81BIS_FNG", Decimal('1200'), "Familia Numerosa General (Art. 81 bis)"))
        elif large_cat == 'special':
            deductions.append(Deduction("ART81BIS_FNE", Decimal('2400'), "Familia Numerosa Especial (Art. 81 bis)"))

        # Art. 81 bis — Monoparental con ≥2 hijos (1.200€)
        if getattr(profile, 'single_parent_2_children', False) and getattr(profile, 'descendants_count', 0) >= 2:
            deductions.append(Deduction("ART81BIS_MONO", Decimal('1200'), "Monoparental ≥2 hijos (Art. 81 bis)"))

        # Art. 81 bis — Cónyuge discapacitado (1.200€)
        if getattr(profile, 'spouse_disability_grade', 0) >= 33:
            deductions.append(Deduction("ART81BIS_CONYUGE", Decimal('1200'), "Cónyuge Discapacitado (Art. 81 bis)"))

        # Art. 81 LIRPF: el límite de SS aplica ÚNICAMENTE a la deducción por maternidad (ART81_MAT, ART81_GUAR)
        # Las deducciones Art. 81bis (familia numerosa, monoparental, cónyuge discapacitado) NO tienen límite SS.
        mat_deductions = [d for d in deductions if d.box_id in ('ART81_MAT', 'ART81_GUAR')]
        mat_total = sum(d.value for d in mat_deductions)
        if mat_total > 0:
            ss_total = getattr(profile, 'ss_employee_eur', Decimal('0')) + getattr(profile, 'ss_self_employed_eur', Decimal('0'))
            if mat_total > ss_total and ss_total >= Decimal('0'):
                # Prorratear solo maternidad hasta el límite de cotizaciones
                factor = ss_total / mat_total if mat_total else Decimal('0')
                for d in mat_deductions:
                    d.value *= factor

        return deductions

    @classmethod
    def calculate(cls, profile: TaxpayerProfile, bi_total: Decimal) -> List[Deduction]:
        """Compatibilidad con DeductionEngine — devuelve deducciones de cuota."""
        return cls.calculate_quota_deductions(profile, bi_total)
