from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any

EPSILON = Decimal('1e-12')

from src.domain.crypto_entities import Trade, FIFOLot, TaxEvent
from src.domain.fiscal_entities import Dividend, WorkIncome, Deduction, TaxpayerProfile

# Los tramos y la lógica de aplicación se han movido dentro de la clase IRPFCalculator para mayor cohesión.

class AssetAccount:
    def __init__(self, asset: str):
        self.asset = asset
        self.inventory: List[FIFOLot] = []
        self.total_bought = Decimal('0.0')
        self.total_sold = Decimal('0.0')
        self.matched_qty = Decimal('0.0')
        self.unmatched_qty = Decimal('0.0')

    def add_lot(self, lot: FIFOLot):
        self.inventory.append(lot)

    def consume_fifo(self, quantity: Decimal) -> Tuple[Decimal, Decimal, List[dict]]:
        coste_total = Decimal('0.0')
        gastos_total = Decimal('0.0')
        matches = []
        remaining = quantity

        while remaining > Decimal('0') and self.inventory:
            lot = self.inventory[0]
            if lot.quantity <= remaining + EPSILON:
                qty = lot.quantity
                coste_total += lot.quantity * lot.cost_per_unit_eur
                gastos_total += lot.quantity * lot.buy_fee_per_unit_eur
                matches.append({'qty': qty, 'cost': lot.quantity * lot.cost_per_unit_eur, 'fee': lot.quantity * lot.buy_fee_per_unit_eur, 'date': lot.date})
                self.matched_qty += qty
                remaining -= qty
                self.inventory.pop(0)
            else:
                qty = remaining
                coste_total += qty * lot.cost_per_unit_eur
                gastos_total += qty * lot.buy_fee_per_unit_eur
                matches.append({'qty': qty, 'cost': qty * lot.cost_per_unit_eur, 'fee': qty * lot.buy_fee_per_unit_eur, 'date': lot.date})
                self.matched_qty += qty
                lot.quantity -= qty
                remaining = Decimal('0')
        
        if remaining > EPSILON:
            self.unmatched_qty += remaining
        return coste_total, gastos_total, matches

class TaxEngine:
    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year
        self.accounts: Dict[str, AssetAccount] = {}
        self.tax_events: List[TaxEvent] = []
        self.dividends: List[Dividend] = []
        self.warnings: List[str] = []
        self.min_date: Optional[datetime] = None

    def _get_account(self, asset: str) -> AssetAccount:
        if asset not in self.accounts: self.accounts[asset] = AssetAccount(asset)
        return self.accounts[asset]

    def process_trades(self, trades: List[Trade]):
        if not trades: return
        self.min_date = min(t.date for t in trades)
        sorted_trades = sorted(trades, key=lambda t: (t.date, 0 if t.direction == 'buy' else 1))
        
        for trade in sorted_trades:
            account = self._get_account(trade.asset)
            if trade.direction == "buy":
                if trade.date.year == self.tax_year and any(x in trade.notes for x in ['Income', 'RCM', 'Reward']):
                    self.dividends.append(Dividend(
                        date=trade.date, platform=trade.platform, asset=trade.asset,
                        isin="", gross_eur=trade.value_eur, 
                        withholding_foreign_eur=Decimal('0'),
                        withholding_spain_eur=Decimal('0'),
                        country="Staking"
                    ))

                buy_val = trade.value_eur
                buy_fee = trade.fee_eur
                cpu = buy_val / trade.quantity if trade.quantity > 0 else Decimal('0')
                fpu = buy_fee / trade.quantity if trade.quantity > 0 else Decimal('0')
                
                account.add_lot(FIFOLot(
                    date=trade.date, asset=trade.asset, quantity=trade.quantity, 
                    cost_per_unit_eur=cpu, buy_fee_per_unit_eur=fpu, platform=trade.platform
                ))
                account.total_bought += trade.quantity
            elif trade.direction == "sell":
                if trade.quantity <= 0: continue
                cost, fee_adq, matches = account.consume_fifo(trade.quantity)
                v_sale = trade.value_eur
                f_sale = trade.fee_eur
                
                if trade.date.year == self.tax_year:
                    matched_qty_total = Decimal('0')
                    for m in matches:
                        q_p = m['qty']
                        matched_qty_total += q_p
                        it = q_p * (v_sale / trade.quantity)
                        gt = q_p * (f_sale / trade.quantity)
                        self.tax_events.append(TaxEvent(
                            date=trade.date, platform=trade.platform, asset=trade.asset,
                            asset_type=trade.asset_type, quantity_sold=q_p,
                            acquisition_date=m['date'], acquisition_cost_eur=m['cost'],
                            sale_proceeds_eur=it, buy_fee_eur=m['fee'], sell_fee_eur=gt,
                            fee_eur=m['fee'] + gt, gain_loss_eur=it - gt - m['cost'] - m['fee'],
                            total_sale_eur=it - gt, total_cost_eur=m['cost'] + m['fee'], notes=trade.notes
                        ))
                    
                    if trade.quantity - matched_qty_total > EPSILON:
                        unmatched = trade.quantity - matched_qty_total
                        it = unmatched * (v_sale / trade.quantity)
                        gt = unmatched * (f_sale / trade.quantity)
                        self.tax_events.append(TaxEvent(
                            date=trade.date, platform=trade.platform, asset=trade.asset,
                            asset_type=trade.asset_type, quantity_sold=unmatched,
                            acquisition_date=datetime(1900, 1, 1), acquisition_cost_eur=Decimal('0'),
                            sale_proceeds_eur=it, buy_fee_eur=Decimal('0'), sell_fee_eur=gt,
                            fee_eur=gt, gain_loss_eur=it - gt,
                            total_sale_eur=it - gt, total_cost_eur=Decimal('0'),
                            notes=f"⚠️ Sin inventario previo (Coste 0) | {trade.notes}"
                        ))
                        min_date_str = self.min_date.strftime('%d/%m/%Y') if self.min_date else "el inicio"
                        self.warnings.append(
                            f"⚠️ FALTA HISTORIAL: No se encuentra el origen de {unmatched:.8f} {trade.asset} vendidos el {trade.date.strftime('%d/%m/%Y')}. "
                            f"Se ha aplicado coste 0.00€ por prudencia fiscal. "
                            f"Sugerencia: Adjunta archivos de Binance con operaciones anteriores al {min_date_str} para calcular el coste real."
                        )
            
            elif trade.direction == "withdraw":
                account.consume_fifo(trade.quantity)
                
            elif trade.direction == "deposit":
                cpu = trade.value_eur / trade.quantity if trade.quantity > 0 else Decimal('0')
                account.add_lot(FIFOLot(
                    date=trade.date, asset=trade.asset, quantity=trade.quantity, 
                    cost_per_unit_eur=cpu, buy_fee_per_unit_eur=Decimal('0'), platform=trade.platform
                ))
                account.total_bought += trade.quantity

    def process_dividends(self, dividends: List[Dividend]):
        for d in dividends:
            if d.date.year == self.tax_year: self.dividends.append(d)

class IRPFCalculator:
    """AEAT Fiscal Engine: Base Imponible del Ahorro & General."""

    SAVINGS_BRACKETS = [
        (Decimal('6000'),    Decimal('0.19')),
        (Decimal('44000'),   Decimal('0.21')),
        (Decimal('150000'),  Decimal('0.23')),
        (Decimal('100000'),  Decimal('0.27')),
        (Decimal('Infinity'), Decimal('0.28')),
    ]

    GENERAL_BRACKETS = [
        (Decimal('12450'),   Decimal('0.19')),
        (Decimal('7750'),    Decimal('0.24')),
        (Decimal('15000'),   Decimal('0.30')),
        (Decimal('24800'),   Decimal('0.37')),
        (Decimal('240000'),  Decimal('0.45')),
        (Decimal('Infinity'), Decimal('0.47')),
    ]

    def __init__(self, events: List[TaxEvent], dividends: List[Dividend], work: Optional[WorkIncome] = None, region: str = "andalucia", profile: Optional[TaxpayerProfile] = None):
        self.events = events
        self.dividends = dividends
        self.work = work
        self.region = region
        self.profile = profile

    def calculate(self) -> Dict:
        fiat_stables = {'EUR'}

        # 1. Agregación Vectorial O(N)
        gpp_neto = sum((e.gain_loss_eur for e in self.events if e.asset not in fiat_stables), Decimal('0'))
        rcm_bruto = sum((d.gross_eur for d in self.dividends if d.asset not in fiat_stables), Decimal('0'))

        # 2. Compensación Limitada al 25% (Art. 49)
        gpp_final, rcm_final = gpp_neto, rcm_bruto
        if gpp_neto < 0 and rcm_bruto > 0:
            compensacion = min(abs(gpp_neto), rcm_bruto * Decimal('0.25'))
            rcm_final -= compensacion
            gpp_final += compensacion
        elif rcm_bruto < 0 and gpp_neto > 0:
            compensacion = min(abs(rcm_bruto), gpp_neto * Decimal('0.25'))
            gpp_final -= compensacion
            rcm_final += compensacion

        base_ahorro = max(gpp_final, Decimal('0')) + max(rcm_final, Decimal('0'))

        # 3. Base General
        bg = Decimal('0')
        retenciones_trabajo = Decimal('0')
        if self.work:
            # Art. 20 LIRPF: Reducción por obtención de rendimientos del trabajo (Simplified)
            rendimiento_neto_previo = self.work.retribuciones_dinerarias - self.work.gastos_deducibles
            reduccion_art20 = Decimal('0')
            if rendimiento_neto_previo <= Decimal('14047.50'):
                reduccion_art20 = Decimal('6490')
            elif rendimiento_neto_previo <= Decimal('19747.50'):
                reduccion_art20 = Decimal('6490') - (Decimal('1.14') * (rendimiento_neto_previo - Decimal('14047.50')))
            
            bg = max(rendimiento_neto_previo - Decimal('2000') - reduccion_art20, Decimal('0'))
            retenciones_trabajo = self.work.retenciones

        # 4. Método de Cuotas y Mínimo Personal
        cuota_bruta = self._apply_brackets(bg, self.GENERAL_BRACKETS) + self._apply_brackets(base_ahorro, self.SAVINGS_BRACKETS)
        cuota_minimo = self._apply_brackets(Decimal('5550'), self.GENERAL_BRACKETS)
        cuota_liquida = max(cuota_bruta - cuota_minimo, Decimal('0'))

        # 5. Deducciones Autonómicas (Andalucía)
        deducciones_ccaa = Decimal('0')
        if self.region == "andalucia" and self.profile:
            deducciones_ccaa = self._calculate_andalusia_deductions()

        # 6. Resultado Final
        ret_div = sum((d.withholding_spain_eur for d in self.dividends if d.asset not in fiat_stables), Decimal('0'))
        resultado = max(cuota_liquida - deducciones_ccaa, Decimal('0')) - retenciones_trabajo - ret_div

        return {
            "region": self.region,
            "rendimiento_trabajo_bruto": {"val": self.work.retribuciones_dinerarias if self.work else Decimal('0')},
            "ss_trabajador": {"val": self.work.gastos_deducibles if self.work else Decimal('0')},
            "retenciones_trabajo": {"val": self.work.retenciones if self.work else Decimal('0')},
            "base_general": bg,
            "base_ahorro": base_ahorro,
            "capital_yield_total": rcm_bruto,
            "dividendos_brutos": {"val": rcm_bruto},
            "retencion_dividendos": {"val": ret_div},
            "cuota_liquida": cuota_liquida,
            "deducciones_ccaa": deducciones_ccaa,
            "resultado": resultado,
            "resultado_label": "A PAGAR" if resultado > 0 else "A DEVOLVER",
            "remanente_gpp_futuro": min(gpp_final, Decimal('0')),
            "remanente_rcm_futuro": min(rcm_final, Decimal('0')),
            "cripto_aeat": self._group_aeat_events("crypto"),
            "acciones_aeat": self._group_aeat_events("stock"),
            "iic_aeat": self._group_aeat_events("iic"),
            "otros_aeat": self._group_aeat_events("equity"),
            "dividend_details": [{"asset": d.asset, "date": d.date.strftime('%d/%m/%Y'), "gross": d.gross_eur, "wht_ext": d.withholding_foreign_eur, "wht_esp": d.withholding_spain_eur} for d in self.dividends if d.asset not in fiat_stables]
        }

    def _calculate_andalusia_deductions(self) -> Decimal:
        """Lógica exacta Deducciones Andalucía Manual Renta 2025."""
        p = self.profile
        total = Decimal('0.0')

        # 1. Alquiler de vivienda habitual (15%, límite 600€)
        if p.is_rent_habitual:
            if p.age < 35 or p.age > 65 or p.is_victim_violence_gender_or_terrorism:
                total += min(p.rent_paid_annual_eur * Decimal('0.15'), Decimal('600.0'))

        # 2. Gastos enseñanza extraescolar (15%, límite 150€ por descendiente)
        if p.descendants_count > 0:
            limite_edu = Decimal('150.0') * p.descendants_count
            total += min(p.extra_education_expenses_eur * Decimal('0.15'), limite_edu)

        # 3. Nacimiento o adopción (200€ por cada hijo)
        if p.birth_count_current_year > 0:
            total += Decimal('200.0') * p.birth_count_current_year

        return total


    def _apply_brackets(self, base: Decimal, brackets: list) -> Decimal:
        tax = Decimal('0')
        current_base = base
        for limit, rate in brackets:
            if current_base <= 0: break
            taxable = min(current_base, limit)
            tax += taxable * rate
            current_base -= taxable
        return max(tax, Decimal('0'))

    def _group_aeat_events(self, asset_type: str) -> dict:
        fiat_stables = {'EUR', 'USDC', 'USDT', 'FDUSD', 'BUSD', 'DAI'}
        results = {}
        for ev in self.events:
            if ev.asset_type == asset_type and ev.asset not in fiat_stables:
                if ev.asset not in results:
                    results[ev.asset] = {"nombre": ev.asset, "adquisicion": Decimal('0'), "transmision": Decimal('0'), "ganancia": Decimal('0'), "perdida": Decimal('0')}
                
                results[ev.asset]["adquisicion"] += Decimal(str(ev.total_cost_eur))
                results[ev.asset]["transmision"] += Decimal(str(ev.total_sale_eur))
                if ev.gain_loss_eur > 0: results[ev.asset]["ganancia"] += Decimal(str(ev.gain_loss_eur))
                else: results[ev.asset]["perdida"] += abs(Decimal(str(ev.gain_loss_eur)))
        return results
