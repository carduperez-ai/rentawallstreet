# src/tax_compliance/regions/andalucia/deductor.py
from decimal import Decimal
from src.domain.fiscal_entities import TaxpayerProfile


class AndalusiaDeductor:
    """Implementación de Deducciones Autonómicas de Andalucía (Manual Renta 2025)."""

    LIMITE_BI_INDIVIDUAL = Decimal("25000")
    LIMITE_BI_CONJUNTA = Decimal("30000")

    @classmethod
    def calculate_all(cls, profile: TaxpayerProfile, base_general: Decimal, base_ahorro: Decimal) -> dict[str, Decimal]:
        deductions = {}
        bi_total = base_general + base_ahorro

        # Deducciones UNIVERSALES (sin límite de renta 25k)

        # 3. Nacimiento / Adopción
        births = getattr(profile, "birth_count_current_year", 0)
        and03_value = Decimal("0")
        if births > 0:
            if births == 1:
                and03_value = Decimal("200")
            else:
                and03_value = Decimal("400") * births
            if getattr(profile, "custody_shared", False) and not getattr(profile, "joint_declaration", False):
                and03_value /= Decimal("2")

        # 11. Familia Numerosa
        and11_value = Decimal("0")
        limite_bi_and11 = (
            cls.LIMITE_BI_CONJUNTA if getattr(profile, "joint_declaration", False) else cls.LIMITE_BI_INDIVIDUAL
        )
        if bi_total <= limite_bi_and11 and getattr(profile, "is_large_family", False):
            if getattr(profile, "is_large_family_special", False):
                and11_value = Decimal("400")
            else:
                and11_value = Decimal("200")
            if getattr(profile, "custody_shared", False) and not getattr(profile, "joint_declaration", False):
                and11_value /= Decimal("2")

        # Incompatibilidad AND03 vs AND11
        if and03_value > 0 and and11_value > 0:
            if and11_value >= and03_value:
                deductions["AND11"] = and11_value
            else:
                deductions["AND03"] = and03_value
        else:
            if and11_value > 0:
                deductions["AND11"] = and11_value
            elif and03_value > 0:
                deductions["AND03"] = and03_value

        # 5. Enfermedad Celíaca
        if getattr(profile, "is_celiac", False):
            deductions["AND05"] = Decimal("100")

        # 6. Gastos Veterinarios (límite 80k)
        if bi_total <= Decimal("80000"):
            vet = getattr(profile, "vet_expenses_eur", Decimal("0"))
            if vet > 0:
                val = min(vet * Decimal("0.30"), Decimal("100"))
                deductions["AND06"] = val

        # Filtro de renta general para las siguientes deducciones
        limite_bi_gral = (
            cls.LIMITE_BI_CONJUNTA if getattr(profile, "joint_declaration", False) else cls.LIMITE_BI_INDIVIDUAL
        )
        if bi_total > limite_bi_gral:
            return deductions

        # 1. Alquiler Vivienda Habitual
        if profile.is_rent_habitual:
            age = profile.age
            is_victim = getattr(profile, "is_victim_violence_gender_or_terrorism", False)
            disability = getattr(profile, "disability_grade", 0)
            if age < 35 or age > 65 or is_victim:
                tope = Decimal("1500") if disability >= 33 else Decimal("1200")
                val = min(profile.rent_paid_annual_eur * Decimal("0.15"), tope)
                if val > 0:
                    deductions["AND01"] = val

        # 2. Gastos Educativos (Idiomas/Informática)
        if profile.descendants_count > 0 and profile.extra_education_expenses_eur > 0:
            limite = Decimal("150") * profile.descendants_count
            val = min(profile.extra_education_expenses_eur * Decimal("0.15"), limite)
            if val > 0:
                deductions["AND02"] = val

        # 4. Discapacidad (Contribuyente o convivientes)
        if profile.disability_grade >= 33:
            deductions["AND04"] = Decimal("150")

        # 7. Ejercicio Físico / Deporte
        gym = getattr(profile, "gym_expenses_eur", Decimal("0"))
        if gym > 0:
            val = min(gym * Decimal("0.15"), Decimal("100"))
            if val > 0:
                deductions["AND07"] = val

        # 8. Defensa Jurídica Laboral
        legal = getattr(profile, "legal_defense_expenses_eur", Decimal("0"))
        if legal > 0:
            val = min(legal, Decimal("200"))
            deductions["AND08"] = val

        # 9. Familia Monoparental
        if profile.is_monoparental and getattr(profile, "descendants_count", 0) > 0:
            asc_75 = getattr(profile, "ascendants_over75", 0)
            val = Decimal("100") + (Decimal("100") * asc_75)
            deductions["AND09"] = val

        # 10. Vivienda Protegida (VPO)
        if profile.is_protected_housing and profile.age < 35:
            # Simplificación: 2% o importe fijo según el manual
            deductions["AND10"] = Decimal("50")

        return deductions
