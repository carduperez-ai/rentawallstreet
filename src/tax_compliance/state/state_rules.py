# src/tax_compliance/deductions/state_rules.py
from decimal import Decimal
from typing import List
from src.domain.fiscal_entities import TaxpayerProfile, Deduction


class StateDeductor:
    """Deducciones estatales LIRPF 2025."""

    @classmethod
    def calculate_quota_deductions(cls, profile: TaxpayerProfile, bi_total: Decimal) -> List[Deduction]:
        """Restan cuota íntegra (resultado: cuota líquida ≥ 0)."""
        deductions = []

        # DA 9ª — Hipoteca pre-2013 (7,5% base máx 9.040€)
        if getattr(profile, "mortgage_pre2013", False) and getattr(profile, "mortgage_paid_eur", Decimal("0")) > 0:
            acquisition_date = str(getattr(profile, "mortgage_acquisition_date", ""))
            is_valid_date = True
            if acquisition_date and acquisition_date >= "2013-01-01":
                is_valid_date = False

            if is_valid_date:
                base = min(profile.mortgage_paid_eur, Decimal("9040"))
                val = base * Decimal("0.075")
                deductions.append(Deduction("ST_DA9", val, "Deducción Hipoteca pre-2013 (DA 9ª LIRPF)"))

        # DA 11ª — Alquiler pre-2015 (10,05%, BI < 24.107,20€)
        if getattr(profile, "rent_pre2015", False) and getattr(profile, "rent_pre2015_paid_eur", Decimal("0")) > 0:
            if bi_total < Decimal("24107.20"):
                base = min(profile.rent_pre2015_paid_eur, Decimal("9040"))
                if bi_total <= Decimal("17707.20"):
                    val = base * Decimal("0.1005")
                else:
                    factor = Decimal("1") - (bi_total - Decimal("17707.20")) / Decimal("6400")
                    val = base * Decimal("0.1005") * factor
                if val > 0:
                    deductions.append(Deduction("ST_DA11", val, "Deducción Alquiler pre-2015 (DA 11ª LIRPF)"))

        # Art. 68.1 — Inversión startups
        if getattr(profile, "startup_investment_eur", Decimal("0")) > 0:
            if getattr(profile, "startup_ownership_pct", Decimal("0")) <= Decimal("0.40"):
                max_years = 7 if getattr(profile, "startup_is_emerging", False) else 5
                if getattr(profile, "startup_years_since_constitution", 0) <= max_years:
                    rate = Decimal("0.50") if getattr(profile, "startup_is_emerging", False) else Decimal("0.30")
                    base_inv = min(profile.startup_investment_eur, Decimal("100000"))
                    val = base_inv * rate
                    if val > 0:
                        deductions.append(Deduction("ST01", val, "Inversión Startups (Art. 68.1)"))

        # Art. 68.3 - Donativos (80% primeros 250€ + 40% resto; base máx 15% Base Liquidable)
        if getattr(profile, "donations_eur", Decimal("0")) > 0:
            base_don = min(profile.donations_eur, bi_total * Decimal("0.15"))
            primero = min(base_don, Decimal("250"))
            resto = max(base_don - Decimal("250"), Decimal("0"))
            rate_resto = Decimal("0.45") if getattr(profile, "donations_fidelized", False) else Decimal("0.40")
            val = primero * Decimal("0.80") + resto * rate_resto
            if val > 0:
                deductions.append(Deduction("ST03", val, "Donativos a Entidades (Art. 68.3)"))

        # Art. 68.3.c — Afiliación partido político (20% máx 600€ base)
        if getattr(profile, "political_party_eur", Decimal("0")) > 0:
            val = min(profile.political_party_eur, Decimal("600")) * Decimal("0.20")
            if val > 0:
                deductions.append(Deduction("ST_POL", val, "Cuotas Partido Político (Art. 68.3.c)"))

        # DA 50ª — Eficiencia energética (20/40/60%)
        if (
            getattr(profile, "energy_efficiency_investment_eur", Decimal("0")) > 0
            and getattr(profile, "energy_efficiency_type", 0) > 0
        ):
            rate = Decimal(str(profile.energy_efficiency_type)) / Decimal("100")
            limites = {20: Decimal("5000"), 40: Decimal("7500"), 60: Decimal("15000")}
            limite = limites.get(profile.energy_efficiency_type, Decimal("5000"))
            prior_base = getattr(profile, "energy_efficiency_prior_years_base_eur", Decimal("0"))
            base_disp = max(limite - prior_base, Decimal("0"))
            base_deducible = min(profile.energy_efficiency_investment_eur, base_disp)
            val = base_deducible * rate
            if val > 0:
                deductions.append(
                    Deduction("ST04", val, f"Mejora Eficiencia Energética ({profile.energy_efficiency_type}%) (DA 50ª)")
                )

        # DA 58ª — Vehículos eléctricos y puntos de recarga
        veh_inv = getattr(profile, "electric_vehicle_investment_eur", Decimal("0"))
        if veh_inv > 0:
            subsidies = getattr(profile, "electric_vehicle_subsidies_eur", Decimal("0"))
            veh_base = min(max(veh_inv - subsidies, Decimal("0")), Decimal("20000"))
            val = veh_base * Decimal("0.15")
            if val > 0:
                deductions.append(Deduction("ST_VEH", val, "Vehículo eléctrico (DA 58ª)"))

        rec_inv = getattr(profile, "charging_point_investment_eur", Decimal("0"))
        if rec_inv > 0 and getattr(profile, "charging_point_is_electronic_payment", False):
            rec_base = min(rec_inv, Decimal("4000"))
            val = rec_base * Decimal("0.15")
            if val > 0:
                deductions.append(Deduction("ST_REC", val, "Punto de recarga (DA 58ª)"))

        return deductions

    @classmethod
    def calculate_differential_deductions(cls, profile: TaxpayerProfile) -> List[Deduction]:
        """Art. 81/81 bis — pueden superar cuota → resultado A devolver."""
        deductions = []

        # Art. 81 — Maternidad (1.200€/año máximo)
        maternity_months = getattr(profile, "maternity_months", {})
        if maternity_months:
            total_maternity_deduction = Decimal("0")
            exempt_ss = getattr(profile, "exempt_from_ss_limit", False)
            for month, ss_contribution in maternity_months.items():
                if exempt_ss:
                    total_maternity_deduction += Decimal("100")
                else:
                    total_maternity_deduction += min(Decimal("100"), ss_contribution)
            
            if total_maternity_deduction > 0:
                deductions.append(
                    Deduction("ART81_MAT", total_maternity_deduction, "Maternidad (Art. 81)")
                )

        # Gastos Guardería
        children_u3 = getattr(profile, "children_under_3", 0)
        daycare = getattr(profile, "daycare_expenses_eur", Decimal("0"))
        if daycare > 0 and children_u3 > 0:
            val_daycare = min(daycare, Decimal("1000") * children_u3)
            deductions.append(Deduction("ART81_GUAR", val_daycare, "Gastos Guardería (Art. 81)"))

        # Art. 81 bis — Familia numerosa
        large_cat = getattr(profile, "large_family_category", "none")
        if large_cat == "general":
            deductions.append(Deduction("ART81BIS_FNG", Decimal("1200"), "Familia Numerosa General (Art. 81 bis)"))
        elif large_cat == "special":
            deductions.append(Deduction("ART81BIS_FNE", Decimal("2400"), "Familia Numerosa Especial (Art. 81 bis)"))

        # Art. 81 bis — Monoparental con ≥2 hijos (1.200€)
        if getattr(profile, "single_parent_2_children", False) and getattr(profile, "descendants_count", 0) >= 2:
            deductions.append(Deduction("ART81BIS_MONO", Decimal("1200"), "Monoparental ≥2 hijos (Art. 81 bis)"))

        # Art. 81 bis — Cónyuge discapacitado (1.200€)
        if getattr(profile, "spouse_disability_grade", 0) >= 33:
            deductions.append(Deduction("ART81BIS_CONYUGE", Decimal("1200"), "Cónyuge Discapacitado (Art. 81 bis)"))

        # Art. 81 LIRPF / Art. 81 bis: La suma de maternidad y familia numerosa (y otros de 81bis)
        # est topada por cotizaciones. Gastos de guardera exentos del tope de cotizacin.
        # "se aplicar de forma independiente respecto de cada una de las deducciones"
        capped_boxes = ("ART81_MAT", "ART81BIS_FNG", "ART81BIS_FNE", "ART81BIS_MONO", "ART81BIS_CONYUGE")
        mat_deductions = [d for d in deductions if d.box_id in capped_boxes]
        ss_total = getattr(profile, "ss_employee_eur", Decimal("0")) + getattr(
            profile, "ss_self_employed_eur", Decimal("0")
        )
        if not getattr(profile, "exempt_from_ss_limit", False):
            for d in mat_deductions:
                if d.value > ss_total:
                    d.value = ss_total

        return deductions

    @classmethod
    def calculate(cls, profile: TaxpayerProfile, bi_total: Decimal) -> List[Deduction]:
        """Compatibilidad con DeductionEngine — devuelve deducciones de cuota."""
        return cls.calculate_quota_deductions(profile, bi_total)
