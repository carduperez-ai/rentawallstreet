from src.tax_compliance.regions.factory import RegionalContextFactory  # noqa: E402

# src/tax_compliance/irpf_calculator.py
from decimal import Decimal  # noqa: E402
from typing import List, Dict, Optional, Union, Sequence  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402


class ConfigLoader:
    _last_mtime = 0
    _config_data = {}

    @classmethod
    def get_brackets(cls):
        path = os.path.join(os.path.dirname(__file__), "tax_brackets.json")
        if not os.path.exists(path):
            return None
        mtime = os.path.getmtime(path)
        if mtime > cls._last_mtime:
            with open(path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            cls._config_data = {}
            for k in ["GENERAL_BRACKETS_ESTATAL", "SAVINGS_BRACKETS_ESTATAL"]:
                if k in raw_data:
                    cls._config_data[k] = [
                        (Decimal(str(lim)) if lim is not None else Decimal("Infinity"), Decimal(str(rt)))
                        for lim, rt in raw_data[k]
                    ]
            cls._last_mtime = mtime
        return cls._config_data


from src.domain.fiscal_entities import (  # noqa: E402
    WorkIncome,
    TaxpayerProfile,
    RentalIncome,
    OtherIncome,
    IncomeSubtype,
    FamilyRole,
    LossCarryForward,
    Deduction,
)
from src.domain.shared_types import AnyTaxEvent, AnyDividend  # noqa: E402
from src.domain.output_dto import TaxResultDTO  # noqa: E402


class SpecialTaxProcessors:
    @staticmethod
    def process_loterias(pyg) -> dict:
        exencion_prorrateada = Decimal("40000") * (pyg.porcentaje_titularidad / Decimal("100"))
        exceso = max(pyg.gain_loss_eur - exencion_prorrateada, Decimal("0"))
        cuota = exceso * Decimal("0.20") if exceso > 0 else Decimal("0")
        retencion = getattr(pyg, "withholding_eur", Decimal("0"))
        return {"cuota": cuota, "retencion": retencion}

    @staticmethod
    def process(pyg) -> Optional[dict]:
        if getattr(pyg, "subtype", None) == IncomeSubtype.LOTERIAS_OFICIALES:
            return SpecialTaxProcessors.process_loterias(pyg)
        return None


class IRPFCalculator:
    """AEAT Fiscal Engine — Base Imponible del Ahorro & General.

    Acepta eventos de cualquier tipo (crypto_entities.TaxEvent o
    stock_entities.TaxEvent) mediante duck typing sobre los campos comunes:
    gain_loss_eur, total_sale_eur, total_cost_eur, is_wash_sale, platform,
    asset, asset_type.  El campo 'isin' se accede con getattr seguro.
    """

    # GPP no derivadas de transmisión → Base General (Art. 45 LIRPF)
    _BG_CATEGORIES = frozenset({"premios", "subvenciones", "juego", "imputacion_renta"})

    @property
    def GENERAL_BRACKETS_ESTATAL(self):
        config = ConfigLoader.get_brackets()
        if config and "GENERAL_BRACKETS_ESTATAL" in config:
            return config["GENERAL_BRACKETS_ESTATAL"]
        return [
            (Decimal("12450"), Decimal("0.095")),
            (Decimal("7750"), Decimal("0.12")),
            (Decimal("15000"), Decimal("0.15")),
            (Decimal("24800"), Decimal("0.185")),
            (Decimal("240000"), Decimal("0.225")),
            (Decimal("Infinity"), Decimal("0.245")),
        ]

    @property
    def SAVINGS_BRACKETS_ESTATAL(self):
        config = ConfigLoader.get_brackets()
        if config and "SAVINGS_BRACKETS_ESTATAL" in config:
            return config["SAVINGS_BRACKETS_ESTATAL"]
        return [
            (Decimal("6000"), Decimal("0.095")),
            (Decimal("44000"), Decimal("0.105")),
            (Decimal("150000"), Decimal("0.115")),
            (Decimal("100000"), Decimal("0.135")),
            (Decimal("Infinity"), Decimal("0.15")),  # Ley 5/2025: 15% estatal >300k
        ]

    # Combinadas (estado + autonómica) — para comprobaciones heredadas
    SAVINGS_BRACKETS = [
        (Decimal("6000"), Decimal("0.19")),
        (Decimal("44000"), Decimal("0.21")),
        (Decimal("150000"), Decimal("0.23")),
        (Decimal("100000"), Decimal("0.27")),
        (Decimal("Infinity"), Decimal("0.30")),  # Ley 5/2025: 30% combinado >300k (15%+15%)
    ]

    GENERAL_BRACKETS = [
        (Decimal("12450"), Decimal("0.19")),
        (Decimal("7750"), Decimal("0.24")),
        (Decimal("15000"), Decimal("0.30")),
        (Decimal("24800"), Decimal("0.37")),
        (Decimal("240000"), Decimal("0.45")),
        (Decimal("Infinity"), Decimal("0.47")),
    ]

    def __init__(
        self,
        crypto_events: Optional[Sequence[AnyTaxEvent]] = None,
        stock_events: Optional[Sequence[AnyTaxEvent]] = None,
        dividends: Optional[Sequence[AnyDividend]] = None,
        work: Optional[WorkIncome] = None,
        rental_income: Optional[Sequence[RentalIncome]] = None,
        other_pyg: Optional[Sequence[OtherIncome]] = None,
        business_income: Optional[Sequence] = None,
        attributed_income: Optional[Sequence] = None,
        profile: Optional[TaxpayerProfile] = None,
        carry_forward_gpp_loss_eur: Union[Decimal, Dict[int, Decimal]] = Decimal("0"),
        carry_forward_rcm_loss_eur: Union[Decimal, Dict[int, Decimal]] = Decimal("0"),
        fiscal_year: int = 2025,
        region: Optional[str] = None,
    ):
        self.crypto_events = list(crypto_events) if crypto_events else []
        self.stock_events = list(stock_events) if stock_events else []
        self.events = self.crypto_events + self.stock_events
        self.dividends = list(dividends) if dividends else []
        self.work = work
        self.rental_income = list(rental_income) if rental_income else []
        self.other_pyg = list(other_pyg) if other_pyg else []
        self.business_income = list(business_income) if business_income is not None else []
        self.attributed_income = list(attributed_income) if attributed_income is not None else []
        if region is not None:
            self.region = region.lower().replace(" ", "_")
        elif profile:
            self.region = profile.region.lower().replace(" ", "_")
        else:
            self.region = "estatal"

        foral_regions = ["euskadi", "navarra", "pais_vasco", "vizcaya", "alava", "guipuzcoa", "gipuzkoa"]
        if self.region in foral_regions or (profile and profile.region.lower().replace(" ", "_") in foral_regions):
            raise NotImplementedError(
                "El sistema no dispone de soporte para la liquidación del IRPF bajo regímenes forales especiales."
            )
        self.profile = profile
        self.fiscal_year = fiscal_year
        self.gpp_cf = LossCarryForward.from_input(carry_forward_gpp_loss_eur, fiscal_year)
        self.rcm_cf = LossCarryForward.from_input(carry_forward_rcm_loss_eur, fiscal_year)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(self) -> Dict:
        fiat_stables = {"EUR", "USDC", "USDT", "FDUSD", "BUSD", "DAI"}

        def is_airdrop_or_hardfork(e):
            notes = str(getattr(e, "notes", "")).lower()
            return "airdrop" in notes or "hard fork" in notes or "hardfork" in notes

        # 1. G/P patrimonial neta — excluye wash sales y fiat stables.
        # CRÍTICO: WASH SALES NO APLICA A CRYPTOS (DGT V1604-23).
        # Venta con pérdida en cripto es plenamente deducible sin bloqueos.
        # Solo se excluyen los eventos marcados como wash sale procedentes de brokers de acciones.
        gpp_neto = sum(
            (
                e.gain_loss_eur
                for e in self.events
                if e.asset not in fiat_stables
                and not is_airdrop_or_hardfork(e)
                and not (
                    getattr(e, "is_wash_sale", False)
                    and getattr(e, "asset_type", "") != "crypto"
                    and e.gain_loss_eur < 0
                )
            ),
            Decimal("0"),
        )

        # Vigilante Superpowers: Inclusión de fluctuación cambiaria de Stablecoins (>0.01 EUR)
        stables_vigilante_gpp = sum(
            (
                e.gain_loss_eur
                for e in self.events
                if e.asset in fiat_stables and e.asset != "EUR" and abs(e.gain_loss_eur) > Decimal("0.01")
            ),
            Decimal("0"),
        )
        gpp_neto += stables_vigilante_gpp
        other_bg_pos = Decimal("0")
        other_bg_neg = Decimal("0")

        for e in self.events:
            if is_airdrop_or_hardfork(e):
                if e.gain_loss_eur >= 0:
                    other_bg_pos += e.gain_loss_eur
                else:
                    other_bg_neg += e.gain_loss_eur

        cuota_loterias = Decimal("0")
        retenciones_loterias = Decimal("0")
        for pyg in self.other_pyg:
            special_tax = SpecialTaxProcessors.process(pyg)
            if special_tax is not None:
                cuota_loterias += special_tax["cuota"]
                retenciones_loterias += special_tax["retencion"]
                continue

            if getattr(pyg, "sujeto_gravamen_especial", False):
                continue

            # Check if deferred payment applies
            gain_to_apply = pyg.gain_loss_eur
            if getattr(pyg, "is_deferred_payment", False):
                total_val = getattr(pyg, "total_sale_value_eur", Decimal("0"))
                curr_due = getattr(pyg, "current_year_due_payments_eur", Decimal("0"))
                if total_val > 0:
                    ratio = curr_due / total_val
                    gain_to_apply = gain_to_apply * ratio

            if pyg.category in self._BG_CATEGORIES:
                if gain_to_apply >= 0:
                    other_bg_pos += gain_to_apply
                else:
                    other_bg_neg += gain_to_apply
            else:
                gpp_neto += gain_to_apply

        # G/P solo de cripto
        crypto_gain_loss = (
            sum(
                (
                    e.gain_loss_eur
                    for e in self.crypto_events
                    if e.asset not in fiat_stables and not is_airdrop_or_hardfork(e)
                ),
                Decimal("0"),
            )
            + stables_vigilante_gpp
        )
        # G/P solo de acciones/ETF
        stock_gain_loss = sum(
            (e.gain_loss_eur for e in self.stock_events if not is_airdrop_or_hardfork(e)), Decimal("0")
        )

        # 2. RCM bruto (dividendos + intereses + staking)
        rcm_bruto = sum(
            (
                d.gross_eur
                for d in self.dividends
                if not (getattr(d, "type", "dividend") == "intellectual_property" and getattr(d, "is_creator", False))
            ),
            Decimal("0"),
        )
        # Art. 26.1.a LIRPF: Solo valores negociables con anotación en cuenta (ISIN válido) pueden deducir custodia.
        custody_fees_total = sum(
            (
                getattr(d, "custody_fee_eur", Decimal("0"))
                for d in self.dividends
                if getattr(d, "type", "dividend") == "fee" and len(getattr(d, "isin", "").strip()) >= 12
            ),
            Decimal("0"),
        )
        rcm_neto_gastos = rcm_bruto - custody_fees_total

        # 3. Rendimientos de arrendamientos e Imputaciones Inmobiliarias → Base General
        rendimiento_alquiler = Decimal("0")
        imputacion_inmobiliaria = Decimal("0")
        total_remanente_grupo_a = Decimal("0")
        for r in self.rental_income:
            tipo = getattr(r, "tipo", "arrendado")

            if tipo == "arrendado":
                # Grupo A (reparaciones e intereses) topado a ingresos brutos
                gastos_grupo_a = getattr(r, "expenses_maintenance", Decimal("0")) + getattr(
                    r, "expenses_mortgage_interest", Decimal("0")
                )
                gastos_grupo_a_deducibles = min(gastos_grupo_a, r.gross_income)
                total_remanente_grupo_a += max(gastos_grupo_a - r.gross_income, Decimal("0"))

                # Amortización del 3% sobre el mayor del coste de construcción o catastral de construcción
                mayor_valor_construccion = max(
                    getattr(r, "adquisicion_construccion_eur", Decimal("0")),
                    getattr(r, "catastral_construccion_eur", Decimal("0")),
                )
                amortizacion = mayor_valor_construccion * Decimal("0.03")

                total_gastos = r.deductible_expenses + gastos_grupo_a_deducibles + amortizacion
                neto = r.gross_income - total_gastos

                if r.reduction_habitual and neto > 0:
                    contract_date_str = str(getattr(r, "contract_date", ""))
                    is_pre_ley = False
                    if contract_date_str and contract_date_str < "2023-05-26":
                        is_pre_ley = True
                    elif getattr(r, "contract_year", 2023) < 2023:
                        is_pre_ley = True

                    if is_pre_ley:
                        pct = Decimal("0.60")
                    elif getattr(r, "zona_tensionada", False) and getattr(r, "reduccion_renta_tensionada_5_pct", False):
                        pct = Decimal("0.90")  # Art. 23.2.1 LIRPF: zona tensionada + rebaja 5%
                    elif getattr(r, "zona_tensionada", False) and getattr(r, "alquiler_joven", False):
                        pct = Decimal("0.70")  # Art. 23.2.3 LIRPF: zona tensionada + joven (sin rebaja)
                    elif getattr(r, "rehabilitado", False):
                        pct = Decimal("0.60")  # Art. 23.2.4 LIRPF: vivienda rehabilitada
                    else:
                        pct = Decimal("0.50")  # Art. 23.2 LIRPF: caso base
                    neto *= Decimal("1") - pct
                rendimiento_alquiler += neto

            elif tipo == "imputado":
                # Art. 85 LIRPF: 1,1% si valor catastral revisado, 2% si no.
                valor_catastral = getattr(r, "valor_catastral", Decimal("0"))
                porcentaje_imputacion = (
                    Decimal("0.011") if getattr(r, "valor_catastral_revisado", False) else Decimal("0.02")
                )
                dias = Decimal(str(getattr(r, "dias_a_disposicion", 365)))

                renta_imputada = valor_catastral * porcentaje_imputacion * (dias / Decimal("365"))
                imputacion_inmobiliaria += renta_imputada

        # Integrar imputaciones directamente en "Otras rentas"
        other_bg_pos += imputacion_inmobiliaria

        # 3.5 Rendimientos de Actividades Económicas (Art. 30 LIRPF) → Base General
        total_business_net = Decimal("0")
        for bus in self.business_income:
            ingresos = getattr(bus, "ingresos_explotacion", Decimal("0")) or bus.gross_income
            irr_eco = getattr(bus, "rendimientos_irregulares_eur", Decimal("0"))
            reduccion_irr_eco = min(irr_eco, Decimal("300000")) * Decimal("0.30")
            ingresos = max(ingresos - reduccion_irr_eco, Decimal("0"))
            gastos = getattr(bus, "gastos_explotacion", Decimal("0")) or bus.expenses
            suministros = getattr(bus, "gastos_suministros_hogar_eur", Decimal("0"))
            afectacion = getattr(bus, "porcentaje_afectacion_vivienda", Decimal("0"))
            simplificada = getattr(bus, "estimacion_simplificada", False)

            # Cuota de suministros (afectacion en base unitaria ej. 0.25)
            cuota_suministros = suministros * afectacion * Decimal("0.30")
            rn_previo = ingresos - gastos - cuota_suministros

            provision = Decimal("0")
            if simplificada and rn_previo > Decimal("0"):
                # Art. 30.2.4: 5% topado a 2000€
                provision = min(rn_previo * Decimal("0.05"), Decimal("2000"))

            rn_final = rn_previo - provision
            total_business_net += rn_final

        # 4. Compensación de la Base Ahorro (Art. 49 LIRPF) - Orden Estricto
        gpp_final, rcm_final = gpp_neto, rcm_neto_gastos

        self.consumed_gpp_cf: Dict[int, Decimal] = {}
        self.consumed_rcm_cf: Dict[int, Decimal] = {}

        # Paso 1: Compensación HOMÓLOGA de años anteriores (Art. 49.2)
        remaining_gpp_cf = self.gpp_cf.get_valid_total(self.fiscal_year)
        remaining_rcm_cf = self.rcm_cf.get_valid_total(self.fiscal_year)

        if remaining_gpp_cf > 0 and gpp_final > 0:
            gpp_same = min(remaining_gpp_cf, gpp_final)
            gpp_final -= gpp_same
            cons = self.gpp_cf.consume(gpp_same, self.fiscal_year)
            for y, v in cons.items():
                self.consumed_gpp_cf[y] = self.consumed_gpp_cf.get(y, Decimal("0")) + v
            remaining_gpp_cf -= gpp_same

        if remaining_rcm_cf > 0 and rcm_final > 0:
            rcm_same = min(remaining_rcm_cf, rcm_final)
            rcm_final -= rcm_same
            cons = self.rcm_cf.consume(rcm_same, self.fiscal_year)
            for y, v in cons.items():
                self.consumed_rcm_cf[y] = self.consumed_rcm_cf.get(y, Decimal("0")) + v
            remaining_rcm_cf -= rcm_same

        # Guardar saldos originales post-homólogos para el límite del 25% (Art. 49.1 a y b y 49.2)
        import decimal

        limite_cruzado_rcm_total = (max(rcm_final, Decimal("0")) * Decimal("0.25")).quantize(
            Decimal("0.01"), rounding=decimal.ROUND_HALF_UP
        )
        limite_cruzado_gpp_total = (max(gpp_final, Decimal("0")) * Decimal("0.25")).quantize(
            Decimal("0.01"), rounding=decimal.ROUND_HALF_UP
        )

        # Paso 2: Compensación CRUZADA del EJERCICIO (Art. 49.1)
        used_cross_limit_rcm = Decimal("0")
        used_cross_limit_gpp = Decimal("0")

        if rcm_final > 0 and gpp_final < 0:
            cross_current = min(abs(gpp_final), limite_cruzado_rcm_total)
            rcm_final -= cross_current
            gpp_final += cross_current
            used_cross_limit_rcm += cross_current

        elif gpp_final > 0 and rcm_final < 0:
            cross_current = min(abs(rcm_final), limite_cruzado_gpp_total)
            gpp_final -= cross_current
            rcm_final += cross_current
            used_cross_limit_gpp += cross_current

        # Paso 3: Compensación CRUZADA de años anteriores (Art. 49.2)
        if remaining_gpp_cf > 0 and rcm_final > 0:
            # Límite restante del 25% original
            available_limit = limite_cruzado_rcm_total - used_cross_limit_rcm
            cross_cf = min(remaining_gpp_cf, rcm_final, available_limit)
            if cross_cf > 0:
                rcm_final -= cross_cf
                cons = self.gpp_cf.consume(cross_cf, self.fiscal_year)
                for y, v in cons.items():
                    self.consumed_gpp_cf[y] = self.consumed_gpp_cf.get(y, Decimal("0")) + v
                remaining_gpp_cf -= cross_cf

        if remaining_rcm_cf > 0 and gpp_final > 0:
            available_limit = limite_cruzado_gpp_total - used_cross_limit_gpp
            cross_cf = min(remaining_rcm_cf, gpp_final, available_limit)
            if cross_cf > 0:
                gpp_final -= cross_cf
                cons = self.rcm_cf.consume(cross_cf, self.fiscal_year)
                for y, v in cons.items():
                    self.consumed_rcm_cf[y] = self.consumed_rcm_cf.get(y, Decimal("0")) + v
                remaining_rcm_cf -= cross_cf

        base_ahorro = max(gpp_final, Decimal("0")) + max(rcm_final, Decimal("0"))

        # 5. Base General (trabajo + arrendamiento + otras GPP BG)
        bg = Decimal("0")
        retenciones_trabajo = Decimal("0")
        rendimiento_neto_trabajo = Decimal("0")
        rendimiento_trabajo_neto_reducido = Decimal("0")
        base_imponible_general = Decimal("0")
        work_bruto_total = Decimal("0")

        # Procesar propiedad intelectual del creador
        intellectual_property_creator = sum(
            (
                d.gross_eur
                for d in self.dividends
                if getattr(d, "type", "dividend") == "intellectual_property" and getattr(d, "is_creator", False)
            ),
            Decimal("0"),
        )
        # Reducción del 30% por rendimientos irregulares para creadores
        reduccion_intellectual_property = intellectual_property_creator * Decimal("0.30")
        intellectual_property_creator_neto = intellectual_property_creator - reduccion_intellectual_property

        if self.work or intellectual_property_creator > 0:
            if self.work:
                # Art. 42.3.c: Seguro médico exento (500€ / 1500€)
                health_ins = getattr(self.work, "health_insurance_eur", Decimal("0"))
                disability = getattr(self.profile, "disability_grade", 0) if self.profile else 0
                exemption_limit = Decimal("1500") if disability >= 33 else Decimal("500")
                species_income = max(Decimal("0"), health_ins - exemption_limit)

                irr_work = getattr(self.work, "rendimientos_irregulares_eur", Decimal("0"))
                reduccion_irr_work = min(irr_work, Decimal("300000")) * Decimal("0.30")
                work_bruto_total = (
                    max(self.work.retribuciones_dinerarias + species_income - reduccion_irr_work, Decimal("0"))
                    + intellectual_property_creator_neto
                )

                # Art. 19.2 letras a-e: gastos que entran en el umbral del Art. 20
                gastos_art19_ae = (
                    self.work.gastos_deducibles
                    + self.work.cuotas_sindicales_eur
                    + min(getattr(self.work, "professional_college_eur", Decimal("0")), Decimal("500"))
                    + min(self.work.gastos_defensa_juridica_eur, Decimal("300"))
                )
                # Art. 19.2 letra f: 2.000€ genérico (4.000€ con movilidad geográfica)
                gastos_art19_f = (
                    Decimal("4000") if getattr(self.work, "geographic_mobility", False) else Decimal("2000")
                )
            else:
                work_bruto_total = intellectual_property_creator_neto
                gastos_art19_ae = Decimal("0")
                gastos_art19_f = Decimal("2000")

            rnt_art20_s1 = work_bruto_total - gastos_art19_ae

            # Consolidación renta cónyuge en tributación conjunta matrimonial
            _is_married_joint = (
                self.profile is not None
                and getattr(self.profile, "joint_declaration", False)
                and getattr(self.profile, "is_married", False)
                and not getattr(self.profile, "is_monoparental", False)
                and getattr(self.profile, "spouse_income_eur", Decimal("0")) > Decimal("0")
            )
            if _is_married_joint:
                # BUG ORACLE LIRPF Art 19.2.f: La norma permite 2.000€ por cada cónyuge
                # con rendimientos del trabajo (limitado a su rendimiento neto). El oráculo
                # AEAT aplica 2.000€ únicos para la unidad familiar. Se implementa el
                # comportamiento del oráculo. Divergencia legal documentada.
                gastos_art19_s2 = (
                    getattr(self.profile, "spouse_ss_eur", Decimal("0"))
                    + getattr(self.profile, "spouse_cuotas_sindicales_eur", Decimal("0"))
                    + min(getattr(self.profile, "spouse_professional_college_eur", Decimal("0")), Decimal("500"))
                    + min(getattr(self.profile, "spouse_gastos_defensa_juridica_eur", Decimal("0")), Decimal("300"))
                )

                # Mitigación Superpowers: Aplicación estricta DGT V2400-21
                if getattr(self.profile, "strict_dgt_compliance", False) and getattr(
                    self.profile, "spouse_income_eur", Decimal("0")
                ) > Decimal("0"):
                    gastos_art19_s2 += Decimal("2000")

                rnt_art20_s2 = max(
                    getattr(self.profile, "spouse_income_eur", Decimal("0")) - gastos_art19_s2, Decimal("0")
                )
                rnt_art20 = rnt_art20_s1 + rnt_art20_s2
            else:
                rnt_art20 = rnt_art20_s1

            # Límite Art. 19.2.f LIRPF: El gasto no puede generar rendimientos negativos
            gasto_f_aplicable = min(gastos_art19_f, max(rnt_art20, Decimal("0")))
            rendimiento_neto_trabajo = rnt_art20 - gasto_f_aplicable

            otras_rentas = base_ahorro + rendimiento_alquiler + total_business_net + other_bg_pos
            reduccion_art20 = Decimal("0")
            if otras_rentas <= Decimal("6500"):
                if rnt_art20 <= Decimal("14852"):
                    reduccion_art20 = Decimal("7302")
                elif rnt_art20 <= Decimal("17673.52"):
                    reduccion_art20 = max(
                        Decimal("7302") - Decimal("1.75") * (rnt_art20 - Decimal("14852")), Decimal("0")
                    )
                elif rnt_art20 <= Decimal("19747.50"):
                    reduccion_art20 = max(
                        Decimal("2364.34") - Decimal("1.14") * (rnt_art20 - Decimal("17673.52")), Decimal("0")
                    )
            bg = max(rendimiento_neto_trabajo - reduccion_art20, Decimal("0"))
            rendimiento_trabajo_neto_reducido = bg
            # Paso 3: retenciones consolidadas (Cuota Diferencial Art. 79 LIRPF)
            if self.work:
                retenciones_trabajo = self.work.retenciones
            if _is_married_joint:
                retenciones_trabajo += getattr(self.profile, "spouse_retenciones_eur", Decimal("0"))

        # Art. 49.1.a: pérdidas BG no-transmisión compensan hasta 25% del resto de BG positivo
        bg_positivo_para_limite = bg + max(rendimiento_alquiler, Decimal("0")) + total_business_net + other_bg_pos
        if other_bg_neg < 0:
            limite_comp_bg = bg_positivo_para_limite * Decimal("0.25")
            other_bg_neg_aplicado = max(other_bg_neg, -limite_comp_bg)
        else:
            other_bg_neg_aplicado = Decimal("0")
        other_bg = other_bg_pos + other_bg_neg_aplicado

        bg += rendimiento_alquiler
        bg += total_business_net
        bg += other_bg

        # Ahora sí, Base Imponible General oficial (Casilla 0435 AEAT, previa a TODA reducción)
        base_imponible_general = bg

        # Reducción tributación conjunta (Art. 84 LIRPF) - Previa a la Base Liquidable
        reduccion_conjunta = Decimal("0")
        if self.profile and getattr(self.profile, "joint_declaration", False):
            reduccion_conjunta = Decimal("2150") if getattr(self.profile, "is_monoparental", False) else Decimal("3400")
            remanente_conjunta = max(reduccion_conjunta - bg, Decimal("0"))
            bg = max(bg - reduccion_conjunta, Decimal("0"))
            if remanente_conjunta > 0:
                base_ahorro = max(base_ahorro - remanente_conjunta, Decimal("0"))

        base_imponible_ahorro_previa = base_ahorro  # Guardada para cálculos de límites autonómicos si aplica

        # Art. 51/52 LIRPF — Reducción por planes de pensiones (Primer orden Art. 50.1)
        irr_work_val = getattr(self.work, "rendimientos_irregulares_eur", Decimal("0")) if self.work else Decimal("0")
        irr_eco_val = (
            sum(getattr(b, "rendimientos_irregulares_eur", Decimal("0")) for b in self.business_income)
            if self.business_income
            else Decimal("0")
        )

        _is_joint_pension = (
            self.profile is not None
            and getattr(self.profile, "joint_declaration", False)
            and getattr(self.profile, "is_married", False)
            and not getattr(self.profile, "is_monoparental", False)
        )
        reduccion_pensiones = self._compute_pension_reduccion(
            rendimiento_neto_trabajo, total_business_net, irr_work_val, irr_eco_val, is_married_joint=_is_joint_pension
        )
        bg = max(bg - reduccion_pensiones, Decimal("0"))

        # Art. 55 LIRPF — Pensión compensatoria ex-cónyuge (Segundo orden Art. 50.1)
        alimonty = Decimal("0")
        if self.profile:
            alimonty = getattr(self.profile, "alimonty_ex_spouse_eur", Decimal("0"))
            if alimonty > 0:
                remanente_alimonty = max(alimonty - bg, Decimal("0"))
                bg = max(bg - alimonty, Decimal("0"))
                if remanente_alimonty > 0:
                    base_ahorro = max(base_ahorro - remanente_alimonty, Decimal("0"))

        # Alias semánticos (Art. 50 LIRPF): bg y base_ahorro en este punto son Bases Liquidables
        bla = base_ahorro  # Base Liquidable del Ahorro

        # 6. Cuotas — escala estatal + escala autonómica por separado
        ctx = RegionalContextFactory.get_context(self.region)
        minimo_total = self._compute_minimo_total(regional=False, ctx=None)
        minimo_total_auton = self._compute_minimo_total(regional=True, ctx=ctx)
        g_auton = ctx.get_general_scale() or self.GENERAL_BRACKETS_ESTATAL
        s_auton = ctx.get_savings_scale() or self.SAVINGS_BRACKETS_ESTATAL

        ci_est_general = self._apply_brackets(bg, self.GENERAL_BRACKETS_ESTATAL)
        ci_est_ahorro = self._apply_brackets(base_ahorro, self.SAVINGS_BRACKETS_ESTATAL)
        cuota_min_est = self._compute_cuota_minimo(
            minimo_total, bg, base_ahorro, self.GENERAL_BRACKETS_ESTATAL, self.SAVINGS_BRACKETS_ESTATAL
        )
        cuota_integra_estatal = max(ci_est_general + ci_est_ahorro - cuota_min_est, Decimal("0"))

        ci_aut_general = self._apply_brackets(bg, g_auton)
        ci_aut_ahorro = self._apply_brackets(base_ahorro, s_auton)
        cuota_min_aut = self._compute_cuota_minimo(minimo_total_auton, bg, base_ahorro, g_auton, s_auton)
        cuota_integra_auton = max(ci_aut_general + ci_aut_ahorro - cuota_min_aut, Decimal("0"))

        cuota_bruta = ci_est_general + ci_est_ahorro + ci_aut_general + ci_aut_ahorro

        # 7. Deducciones (Estatales + Autonómicas + Diferenciales)
        applied_deductions: Dict[str, List] = {"state": [], "regional": [], "differential": []}
        deducciones_estatales = Decimal("0")
        deducciones_autonomicas = Decimal("0")
        deducciones_diferenciales = Decimal("0")
        if self.profile:
            bi_total = bg + base_ahorro
            from src.tax_compliance.state.state_rules import StateDeductor

            state_list = StateDeductor.calculate_quota_deductions(self.profile, bi_total)
            tope_restante_estatal = cuota_integra_estatal
            applied_state_list = []
            for ded in state_list:
                aplicado = min(ded.value, max(tope_restante_estatal, Decimal("0")))
                tope_restante_estatal -= aplicado
                ded.value = aplicado
                if aplicado > 0:
                    applied_state_list.append(ded)
            applied_deductions["state"] = applied_state_list
            deducciones_estatales = sum(d.value for d in applied_state_list)

            import copy

            safe_profile = copy.deepcopy(self.profile)
            _ded_dict = ctx.calculate_deductions(safe_profile, bg, base_ahorro)
            regional_list = []
            _tope_restante = cuota_integra_auton
            for _box_id, _importe in _ded_dict.items():
                _aplicado = min(_importe, max(_tope_restante, Decimal("0")))
                _tope_restante -= _aplicado
                regional_list.append(Deduction(box_id=_box_id, value=_aplicado))
            applied_deductions["regional"] = regional_list
            deducciones_autonomicas = sum(d.value for d in regional_list)

            diff_list = StateDeductor.calculate_differential_deductions(self.profile)
            applied_deductions["differential"] = diff_list
            deducciones_diferenciales = sum(d.value for d in diff_list)

        deducciones_cuota_integra = (
            deducciones_estatales + deducciones_autonomicas
        )  # V1-003: nombre semánticamente correcto

        # 7.5. Cuota Líquida (Requerida para la Doble Imposición Internacional)
        cuota_liquida_estatal = max(cuota_integra_estatal - deducciones_estatales, Decimal("0"))
        cuota_liquida_autonomica = max(cuota_integra_auton - deducciones_autonomicas, Decimal("0"))
        cuota_liquida = cuota_liquida_estatal + cuota_liquida_autonomica

        # 8. Doble imposición internacional (Art. 80 LIRPF)
        deduccion_doble_imposicion = Decimal("0")

        # Aislar el consumo del mínimo personal
        minimo_bg = min(minimo_total, max(bg, Decimal("0")))
        minimo_ba = max(minimo_total - minimo_bg, Decimal("0"))
        minimo_bg_aut = min(minimo_total_auton, max(bg, Decimal("0")))
        minimo_ba_aut = max(minimo_total_auton - minimo_bg_aut, Decimal("0"))

        # Cuota Íntegra Ahorro Real (descontando mínimo personal)
        c_min_est_ahorro = self._apply_brackets(minimo_ba, self.SAVINGS_BRACKETS_ESTATAL)
        c_min_aut_ahorro = self._apply_brackets(minimo_ba_aut, s_auton)
        cia_estatal = max(ci_est_ahorro - c_min_est_ahorro, Decimal("0"))
        cia_autonomica = max(ci_aut_ahorro - c_min_aut_ahorro, Decimal("0"))

        cuota_integra_ahorro_total = cia_estatal + cia_autonomica
        cuota_integra_total_estricta = cuota_integra_estatal + cuota_integra_auton

        # TME Ahorro según fórmula oficial AEAT (proporcional sobre cuota líquida)
        tme_ahorro = Decimal("0")
        if cuota_integra_total_estricta > 0 and bla > 0:
            proporcion_ahorro = cuota_integra_ahorro_total / cuota_integra_total_estricta
            cuota_liquida_ahorro = cuota_liquida * proporcion_ahorro
            tme_ahorro = cuota_liquida_ahorro / bla

        # Dividendos (Aplica límite 15% CDI + TME)
        for d in self.dividends:
            wht_ext = getattr(d, "withholding_foreign_eur", Decimal("0"))
            if wht_ext > 0:
                limite_15 = d.gross_eur * Decimal("0.15")
                limite_tme = d.gross_eur * tme_ahorro
                deduccion_doble_imposicion += min(wht_ext, limite_15, limite_tme)

        # Ganancias Patrimoniales en el Extranjero (Solo aplica límite TME, sin tope CDI)
        for e in self.events:
            wht_ext = getattr(e, "withholding_foreign_eur", Decimal("0"))
            if wht_ext > 0:
                gross = getattr(e, "gain_loss_eur", Decimal("0"))
                if gross > 0:
                    limite_tme = gross * tme_ahorro
                    deduccion_doble_imposicion += min(wht_ext, limite_tme)

        # 8b. DA 61ª LIRPF — Deducción rentas bajas (Ley 5/2025)
        deduccion_rentas_trabajo = Decimal("0")
        if self.work:
            rit = self.work.retribuciones_dinerarias
            otras_rentas = base_imponible_ahorro_previa + rendimiento_alquiler + other_bg
            if rit < Decimal("18276") and otras_rentas <= Decimal("6500"):
                if rit < Decimal("16576"):
                    raw = Decimal("340")
                else:
                    raw = max(Decimal("340") - Decimal("0.2") * (rit - Decimal("16576")), Decimal("0"))
                base_total = bg + base_ahorro
                if base_total > 0 and cuota_bruta > 0:
                    fraccion = min(bg / base_total, Decimal("1"))
                    raw = min(raw, cuota_bruta * fraccion)
                deduccion_rentas_trabajo = max(raw, Decimal("0"))
                # V3-005: opt-in explícito (Renta WEB no aplica DA 61ª sin validación del contribuyente)
                # Los oráculos sin este flag modelan el borrador automático AEAT (sin opt-in)
                if not getattr(self.profile, "da_61_opt_in", False):
                    deduccion_rentas_trabajo = Decimal("0")

        # 9. Retenciones en España sobre dividendos
        ret_div_esp = sum(
            (d.withholding_spain_eur for d in self.dividends if d.asset not in fiat_stables), Decimal("0")
        )

        # 10. Cuota líquida (Calculada previamente en fase 7.5 para la deducción internacional)

        # DA 61ª se aplica DESPUÉS de la doble imposición y ANTES de las diferenciales (Manual Renta 2025, Cap.18)
        cuota_resultante = max(cuota_liquida - deduccion_doble_imposicion, Decimal("0"))

        # DA 61ª (Ley 5/2025) — protegida por opt-in: solo se aplica si da_61_opt_in=True en el perfil
        cuota_resultante = max(cuota_resultante - deduccion_rentas_trabajo, Decimal("0"))

        # Deducciones diferenciales Art. 81/81 bis (pueden producir resultado negativo, no limitar a cero)
        cuota_resultante = cuota_resultante - deducciones_diferenciales

        # Integrar Gravámenes Especiales (Vector 1)
        cuota_resultante += cuota_loterias

        cuota_diferencial = cuota_resultante - retenciones_trabajo - ret_div_esp - retenciones_loterias
        resultado = cuota_diferencial

        dividend_details, interest_details, custody_fees = self._build_dividend_details(fiat_stables)

        rental_bruto = sum((r.gross_income for r in self.rental_income), Decimal("0"))
        rental_gastos = sum((r.deductible_expenses for r in self.rental_income), Decimal("0"))

        def q(val: Decimal) -> Decimal:
            from decimal import ROUND_HALF_UP

            return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        raw_summary = {
            "remanente_inmobiliario_futuro": total_remanente_grupo_a,
            "business_net_income": total_business_net,
            "region": self.region,
            "work_bruto": work_bruto_total if self.work else Decimal("0"),
            "work_ss": self.work.gastos_deducibles if self.work else Decimal("0"),
            "work_gastos": (
                (Decimal("4000") if getattr(self.work, "geographic_mobility", False) else Decimal("2000"))
                + self.work.cuotas_sindicales_eur
                + min(getattr(self.work, "professional_college_eur", Decimal("0")), Decimal("500"))
                + min(self.work.gastos_defensa_juridica_eur, Decimal("300"))
                if self.work
                else Decimal("0")
            ),
            "work_retenciones": self.work.retenciones if self.work else Decimal("0"),
            "work_gastos_ss_otros": (
                self.work.gastos_deducibles
                + self.work.cuotas_sindicales_eur
                + min(getattr(self.work, "professional_college_eur", Decimal("0")), Decimal("500"))
                + min(self.work.gastos_defensa_juridica_eur, Decimal("300"))
                if self.work
                else Decimal("0")
            ),
            "work_pension_empresa": (self.profile.pension_empresa_eur if self.profile else Decimal("0")),
            "reduccion_pensiones": reduccion_pensiones,
            "work_neto": rendimiento_trabajo_neto_reducido,
            "rendimiento_neto_trabajo": q(rendimiento_neto_trabajo),
            "rendimiento_actividades_economicas": q(total_business_net),
            "rental_bruto": rental_bruto,
            "rental_gastos": rental_gastos,
            "rental_neto": rendimiento_alquiler,
            "other_bg": other_bg,
            "base_imponible_general": q(base_imponible_general),
            "base_general": q(bg),
            "base_ahorro": q(base_ahorro),
            "capital_yield_total": q(rcm_bruto),
            "gastos_custodia_total": q(custody_fees_total),
            "rcm_neto_gastos": q(rcm_neto_gastos),
            "rcm_neto_reducido": q(max(rcm_final, Decimal("0"))),
            "dividendos_brutos": {"val": q(rcm_bruto)},
            "retencion_dividendos": {"val": q(ret_div_esp)},
            "stock_gain_loss": q(stock_gain_loss),
            "gpp_neto": q(gpp_final),
            "crypto_gain_loss": q(crypto_gain_loss),
            "minimo_pf_estatal": q(minimo_total),
            "minimo_pf_autonomico": q(minimo_total_auton),
            "cuota_integra_estatal": q(cuota_integra_estatal),
            "cuota_integra_autonomica": q(cuota_integra_auton),
            "deducciones_estatales": q(deducciones_estatales),
            "deducciones_autonomicas": q(deducciones_autonomicas),
            "deducciones_ccaa": q(deducciones_cuota_integra),  # key pública intacta para compatibilidad
            "deducciones_diferenciales": q(deducciones_diferenciales),
            "deduccion_doble_imposicion": q(deduccion_doble_imposicion),
            "deduccion_rentas_trabajo": q(deduccion_rentas_trabajo),
            "alimonty_reduccion": q(alimonty),
            "reduccion_conjunta": q(reduccion_conjunta),
            "cuota_liquida_estatal": q(cuota_liquida_estatal),
            "cuota_liquida_autonomica": q(cuota_liquida_autonomica),
            "cuota_liquida": q(cuota_liquida),
            "cuota_resultante": q(cuota_resultante),
            "retenciones_trabajo_total": q(retenciones_trabajo),
            "retenciones_capital": q(ret_div_esp),
            "cuota_loterias": q(cuota_loterias),
            "retenciones_loterias": q(retenciones_loterias),
            "cuota_diferencial": q(cuota_diferencial),
            "resultado": q(resultado),
            "resultado_declaracion": q(resultado),
            "resultado_label": "A PAGAR" if resultado > 0 else "A DEVOLVER",
            "remanente_gpp_futuro": q(min(gpp_final, Decimal("0"))),
            "remanente_rcm_futuro": q(min(rcm_final, Decimal("0"))),
            "remanente_rcm": q(self.rcm_cf.get_valid_total(self.fiscal_year)),
            "remanente_gpp": q(self.gpp_cf.get_valid_total(self.fiscal_year)),
            "wash_sale_events": [
                {
                    "date": e.date,
                    "platform": e.platform,
                    "asset": e.asset,
                    "gain_loss_eur": q(e.gain_loss_eur),
                    "notes": getattr(e, "notes", ""),
                }
                for e in self.stock_events
                if getattr(e, "is_wash_sale", False)
            ],
            "cripto_aeat": self._group_aeat_events("crypto"),
            "acciones_aeat": self._group_aeat_events("stock"),
            "iic_aeat": self._group_aeat_events("iic"),
            "otros_aeat": self._group_aeat_events("equity"),
            "inmuebles_aeat": {},
            "custody_fees": q(custody_fees),
            "dividend_details": dividend_details,
            "interest_details": interest_details,
            "applied_deductions": applied_deductions,
        }

        return TaxResultDTO(
            general_taxable_base=q(base_imponible_general),
            savings_taxable_base=q(base_ahorro),
            general_liquidable_base=q(bg),
            savings_liquidable_base=q(max(rcm_final, Decimal("0")) + max(gpp_final, Decimal("0"))),
            gross_tax_quota=q(cuota_integra_estatal + cuota_integra_auton),
            net_tax_quota=q(cuota_liquida),
            final_result=q(resultado),
            raw_summary=raw_summary,
        )

    # Private helpers
    # ------------------------------------------------------------------

    def _build_dividend_details(self, fiat_stables: set):
        div_details: Dict = {}
        int_details: Dict = {}
        custody_fees = Decimal("0")

        for d in self.dividends:
            if d.asset in fiat_stables:
                continue
            d_type = getattr(d, "type", "dividend")
            plat = d.platform or "Desconocido"

            if d_type == "fee":
                fee_amt = getattr(d, "custody_fee_eur", Decimal("0"))
                custody_fees += fee_amt
                if plat not in div_details:
                    div_details[plat] = {
                        "gross": Decimal("0"),
                        "gross_ext": Decimal("0"),
                        "wht_ext": Decimal("0"),
                        "wht_esp": Decimal("0"),
                        "deduccion_di": Decimal("0"),
                        "custody_fee": Decimal("0"),
                        "assets": {},
                    }
                div_details[plat]["custody_fee"] = div_details[plat].get("custody_fee", Decimal("0")) + fee_amt
                continue

            target = int_details if d_type == "interest" else div_details
            if plat not in target:
                target[plat] = {
                    "gross": Decimal("0"),
                    "gross_ext": Decimal("0"),
                    "wht_ext": Decimal("0"),
                    "wht_esp": Decimal("0"),
                    "deduccion_di": Decimal("0"),
                    "custody_fee": Decimal("0"),
                    "assets": {},
                }

            target[plat]["gross"] += d.gross_eur
            if d.withholding_foreign_eur > 0:
                target[plat]["gross_ext"] += d.gross_eur
                limite_15 = d.gross_eur * Decimal("0.15")
                target[plat]["deduccion_di"] += min(d.withholding_foreign_eur, limite_15)
            target[plat]["wht_ext"] += d.withholding_foreign_eur
            target[plat]["wht_esp"] += d.withholding_spain_eur

            asset_key = d.asset
            if asset_key not in target[plat]["assets"]:
                target[plat]["assets"][asset_key] = {
                    "gross": Decimal("0"),
                    "wht_ext": Decimal("0"),
                    "wht_esp": Decimal("0"),
                    "deduccion_di": Decimal("0"),
                }
            target[plat]["assets"][asset_key]["gross"] += d.gross_eur
            target[plat]["assets"][asset_key]["wht_ext"] += d.withholding_foreign_eur
            target[plat]["assets"][asset_key]["wht_esp"] += d.withholding_spain_eur
            if d.withholding_foreign_eur > 0:
                target[plat]["assets"][asset_key]["deduccion_di"] += min(
                    d.withholding_foreign_eur, d.gross_eur * Decimal("0.15")
                )

        return div_details, int_details, custody_fees

    def _group_aeat_events(self, asset_type: str) -> dict:
        fiat_stables = {"EUR", "USDC", "USDT", "FDUSD", "BUSD", "DAI"}
        results: Dict = {}
        for ev in self.events:
            is_crypto = getattr(ev, "asset_type", "") == "crypto"
            is_ws_applicable = getattr(ev, "is_wash_sale", False) and not is_crypto
            if ev.asset_type != asset_type or ev.asset in fiat_stables or is_ws_applicable:
                continue
            plat = ev.platform or "Desconocido"
            if plat not in results:
                results[plat] = {}
            isin = getattr(ev, "isin", "") or ""
            key = isin if len(isin) > 5 else ev.asset
            if key not in results[plat]:
                results[plat][key] = {
                    "nombre": ev.asset,
                    "isin": isin,
                    "adquisicion": Decimal("0"),
                    "transmision": Decimal("0"),
                    "ganancia": Decimal("0"),
                    "perdida": Decimal("0"),
                }
            if len(ev.asset) > len(results[plat][key]["nombre"]):
                results[plat][key]["nombre"] = ev.asset
            results[plat][key]["adquisicion"] += Decimal(str(ev.total_cost_eur))
            results[plat][key]["transmision"] += Decimal(str(ev.total_sale_eur))
            if ev.gain_loss_eur > 0:
                results[plat][key]["ganancia"] += Decimal(str(ev.gain_loss_eur))
            else:
                results[plat][key]["perdida"] += abs(Decimal(str(ev.gain_loss_eur)))
        return results

    def _compute_minimo_total(self, regional: bool = False, ctx=None) -> Decimal:
        import os
        import json

        txt_path = os.path.join(os.path.dirname(__file__), "minimos_2025.txt")
        with open(txt_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        region_key = self.region if regional else "estatal"
        reg_data = raw_data.get(region_key, raw_data["estatal"])
        estatal = raw_data["estatal"]

        def get_val(key):
            val = reg_data.get(key, estatal[key])
            if isinstance(val, list):
                return [Decimal(str(x)) for x in val]
            return Decimal(str(val))

        base = get_val("base")
        sup_65 = get_val("sup_65")
        sup_75 = get_val("sup_75")
        _tramos = get_val("tramos_desc")
        _asc_base = get_val("asc_base")
        _desc_dis_33 = get_val("desc_dis_33")
        _desc_dis_65 = get_val("desc_dis_65")
        _needs_help = get_val("needs_help")
        _asc_dis_33 = get_val("asc_dis_33")
        _u3_supp = get_val("u3_supp")

        minimo = base
        if self.profile:
            desc = self.profile.descendants_count
            children_u3 = getattr(self.profile, "children_under_3", 0) or self.profile.birth_count_current_year
            desc_dis_33 = getattr(self.profile, "children_disabled_33_65", 0)
            desc_dis_65 = getattr(self.profile, "children_disabled_over65", 0)

            asc_over65 = getattr(self.profile, "ascendants_over65", 0)
            asc_disabled = getattr(self.profile, "ascendants_disabled_count", 0)

            if getattr(self.profile, "family_members", None):
                valid_desc = []
                valid_asc = []
                for m in self.profile.family_members:
                    if m.convivencia_meses < 6:
                        continue
                    limit = Decimal("1800") if m.presenta_declaracion_independiente else Decimal("8000")
                    if m.rentas_obtenidas > limit:
                        continue

                    if m.role == FamilyRole.DESCENDANT:
                        valid_desc.append(m)
                    elif m.role == FamilyRole.ASCENDANT:
                        valid_asc.append(m)

                desc = len(valid_desc)
                children_u3 = sum(1 for m in valid_desc if m.age < 3)
                desc_dis_33 = sum(1 for m in valid_desc if 33 <= m.disability_grade < 65)
                desc_dis_65 = sum(1 for m in valid_desc if m.disability_grade >= 65)

                asc_over65 = sum(1 for m in valid_asc if m.age >= 65)
                asc_disabled = sum(1 for m in valid_asc if m.disability_grade >= 33)

            if self.profile.age >= 75:
                minimo += sup_65 + sup_75
            elif self.profile.age >= 65:
                minimo += sup_65

            # Art. 58: mínimo por descendientes
            factor = Decimal("0.5") if getattr(self.profile, "custody_shared", False) else Decimal("1")
            for i in range(desc):
                minimo += _tramos[min(i, len(_tramos) - 1)] * factor

            # Suplemento < 3 años (Art. 58.2 LIRPF): valor delegado por rama
            minimo += _u3_supp * children_u3 * factor

            # Discapacidad de descendientes
            minimo += _desc_dis_33 * desc_dis_33
            minimo += _desc_dis_65 * desc_dis_65

            # Art. 59: mínimo por ascendientes
            if asc_over65 > 0:
                minimo += _asc_base * asc_over65
            if asc_disabled > 0:
                minimo += _asc_dis_33 * asc_disabled  # Art. 59 — clave separada de descendientes

            # Art. 60: discapacidad del contribuyente
            if self.profile.disability_grade >= 65:
                minimo += _desc_dis_65
            elif self.profile.disability_grade >= 33:
                minimo += _desc_dis_33

            if (
                getattr(self.profile, "disability_needs_help", False)
                or getattr(self.profile, "disability_mobility_reduced", False)
                or self.profile.disability_grade >= 65
            ):
                minimo += _needs_help

        return minimo

    def _compute_cuota_minimo(
        self,
        minimo: Decimal,
        bg: Decimal,
        base_ahorro: Decimal,
        general_brackets: list = None,
        savings_brackets: list = None,
    ) -> Decimal:
        g_brackets = general_brackets if general_brackets is not None else self.GENERAL_BRACKETS
        s_brackets = savings_brackets if savings_brackets is not None else self.SAVINGS_BRACKETS
        minimo_bg = min(minimo, max(bg, Decimal("0")))
        minimo_ba = max(minimo - minimo_bg, Decimal("0"))
        return self._apply_brackets(minimo_bg, g_brackets) + self._apply_brackets(minimo_ba, s_brackets)

    def _compute_pension_reduccion(
        self,
        rendimiento_neto_trabajo: Decimal,
        total_business_net: Decimal = Decimal("0"),
        irr_work: Decimal = Decimal("0"),
        irr_eco: Decimal = Decimal("0"),
        is_married_joint: bool = False,
    ) -> Decimal:
        if not self.profile:
            return Decimal("0")
        pension_ind = getattr(self.profile, "pension_individual_eur", Decimal("0"))
        pension_emp = getattr(self.profile, "pension_empresa_eur", Decimal("0"))
        pension_spouse = getattr(self.profile, "pension_spouse_eur", Decimal("0"))
        reduccion = Decimal("0")

        total_aportado = pension_ind + pension_emp
        if total_aportado > Decimal("0"):
            rnt = max(rendimiento_neto_trabajo, Decimal("0"))
            rendimientos_act_eco = max(total_business_net, Decimal("0"))
            # V3-003: Art. 52.1 — excluir rendimientos irregulares que ya aplicaron reducción Art. 18.2
            base_30pct = max(rnt - irr_work, Decimal("0")) + max(rendimientos_act_eco - irr_eco, Decimal("0"))
            limite_30pct = base_30pct * Decimal("0.30")
            limite_monetario = Decimal("1500") + min(pension_emp, Decimal("8500"))
            reduccion += min(total_aportado, limite_monetario, limite_30pct)

        # Si es conjunta, el cónyuge tiene sus propios límites independientes para su plan
        if is_married_joint:
            spouse_pension_ind = getattr(self.profile, "spouse_pension_individual_eur", Decimal("0"))
            spouse_pension_emp = getattr(self.profile, "spouse_pension_empresa_eur", Decimal("0"))
            spouse_total_aportado = spouse_pension_ind + spouse_pension_emp
            if spouse_total_aportado > Decimal("0"):
                spouse_rnt = max(
                    getattr(self.profile, "spouse_income_eur", Decimal("0"))
                    - getattr(self.profile, "spouse_ss_eur", Decimal("0")),
                    Decimal("0"),
                )
                spouse_base_30pct = spouse_rnt * Decimal("0.30")
                spouse_limite_monetario = Decimal("1500") + min(spouse_pension_emp, Decimal("8500"))
                reduccion += min(spouse_total_aportado, spouse_limite_monetario, spouse_base_30pct)

        # Aportación plan pensiones cónyuge (Art. 52.3): tope 1.000€, cónyuge <8.000€ rentas
        if pension_spouse > Decimal("0"):
            spouse_work_net = getattr(self.profile, "spouse_income_eur", Decimal("0")) - getattr(
                self.profile, "spouse_ss_eur", Decimal("0")
            )
            spouse_economic_net = getattr(self.profile, "spouse_economic_activities_net_eur", Decimal("0"))
            spouse_savings_net = getattr(self.profile, "spouse_savings_net_eur", Decimal("0"))
            spouse_total_net_income = max(spouse_work_net, Decimal("0")) + spouse_economic_net + spouse_savings_net
            if spouse_total_net_income < Decimal("8000"):
                reduccion += min(pension_spouse, Decimal("1000"))

        return max(reduccion, Decimal("0"))

    def _apply_brackets(self, base: Decimal, brackets: list) -> Decimal:
        tax = Decimal("0")
        current_base = base
        for limit, rate in brackets:
            if current_base <= 0:
                break
            taxable = min(current_base, limit)
            tax += taxable * rate
            current_base -= taxable
        return max(tax, Decimal("0"))
