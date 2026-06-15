from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from collections import deque

from src.domain.constants import EPSILON
from src.domain.crypto_entities import Trade, FIFOLot, TaxEvent
from src.domain.fiscal_entities import Dividend


class AssetAccount:
    def __init__(self, asset: str):
        self.asset = asset
        self.inventory: deque = deque()
        self.total_bought = Decimal("0.0")
        self.total_sold = Decimal("0.0")
        self.matched_qty = Decimal("0.0")
        self.unmatched_qty = Decimal("0.0")

    def add_lot(self, lot: FIFOLot):
        self.inventory.append(lot)

    def consume_fifo(self, quantity: Decimal) -> Tuple[Decimal, Decimal, List[dict]]:
        coste_total = Decimal("0.0")
        gastos_total = Decimal("0.0")
        matches = []
        remaining = quantity

        while remaining > Decimal("0") and self.inventory:
            lot = self.inventory[0]
            if lot.quantity <= remaining + EPSILON:
                qty = lot.quantity
                coste_total += lot.quantity * lot.cost_per_unit_eur
                gastos_total += lot.quantity * lot.buy_fee_per_unit_eur
                matches.append(
                    {
                        "qty": qty,
                        "cost": lot.quantity * lot.cost_per_unit_eur,
                        "fee": lot.quantity * lot.buy_fee_per_unit_eur,
                        "date": lot.date,
                        "source_buy_id": getattr(lot, "source_buy_id", 0),
                    }
                )
                self.matched_qty += qty
                remaining -= qty
                self.inventory.popleft()
            else:
                qty = remaining
                coste_total += qty * lot.cost_per_unit_eur
                gastos_total += qty * lot.buy_fee_per_unit_eur
                matches.append(
                    {
                        "qty": qty,
                        "cost": qty * lot.cost_per_unit_eur,
                        "fee": qty * lot.buy_fee_per_unit_eur,
                        "date": lot.date,
                        "source_buy_id": getattr(lot, "source_buy_id", 0),
                    }
                )
                self.matched_qty += qty
                lot.quantity -= qty
                remaining = Decimal("0")

        if remaining > EPSILON:
            self.unmatched_qty += remaining
        return coste_total, gastos_total, matches


class TaxEngine:
    """
    Motor FIFO para Criptomonedas.
    CRÍTICO: WASH SALES NO APLICA A CRYPTOS.
    """

    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year
        self.accounts: Dict[str, AssetAccount] = {}
        self._all_tax_events: List[TaxEvent] = []
        self.dividends: List[Dividend] = []
        self.warnings: List[str] = []
        self.min_date: Optional[datetime] = None

    @property
    def tax_events(self) -> List[TaxEvent]:
        return [te for te in self._all_tax_events if te.date.year == self.tax_year]

    @tax_events.setter
    def tax_events(self, value: List[TaxEvent]):
        self._all_tax_events = value

    def _get_account(self, asset: str) -> AssetAccount:
        if asset not in self.accounts:
            self.accounts[asset] = AssetAccount(asset)
        return self.accounts[asset]

    def process_trades(self, trades: List[Trade]):
        if not trades:
            return
        self.min_date = min(t.date for t in trades)
        sorted_trades = sorted(trades, key=lambda t: (t.date, 0 if t.direction == "buy" else 1))

        for trade in sorted_trades:
            account = self._get_account(trade.asset)
            if trade.direction == "buy":
                if trade.date.year == self.tax_year and any(x in trade.notes for x in ["Income", "RCM", "Reward"]):
                    self.dividends.append(
                        Dividend(
                            date=trade.date,
                            platform=trade.platform,
                            asset=trade.asset,
                            isin="",
                            gross_eur=trade.value_eur,
                            withholding_foreign_eur=Decimal("0"),
                            withholding_spain_eur=Decimal("0"),
                            country="Staking",
                        )
                    )

                buy_val = trade.value_eur
                buy_fee = trade.fee_eur
                cpu = buy_val / trade.quantity if trade.quantity > 0 else Decimal("0")
                fpu = buy_fee / trade.quantity if trade.quantity > 0 else Decimal("0")

                account.add_lot(
                    FIFOLot(
                        date=trade.date,
                        asset=trade.asset,
                        quantity=trade.quantity,
                        cost_per_unit_eur=cpu,
                        buy_fee_per_unit_eur=fpu,
                        platform=trade.platform,
                        source_buy_id=id(trade),
                    )
                )
                account.total_bought += trade.quantity
            elif trade.direction == "sell":
                if trade.quantity <= 0:
                    continue
                cost, fee_adq, matches = account.consume_fifo(trade.quantity)
                v_sale = trade.value_eur
                f_sale = trade.fee_eur

                matched_qty_total = Decimal("0")
                for m in matches:
                    q_p = m["qty"]
                    matched_qty_total += q_p
                    it = q_p * (v_sale / trade.quantity)
                    gt = q_p * (f_sale / trade.quantity)
                    self._all_tax_events.append(
                        TaxEvent(
                            date=trade.date,
                            platform=trade.platform,
                            asset=trade.asset,
                            asset_type=trade.asset_type,
                            quantity_sold=q_p,
                            acquisition_date=m["date"],
                            acquisition_cost_eur=m["cost"],
                            sale_proceeds_eur=it,
                            buy_fee_eur=m["fee"],
                            sell_fee_eur=gt,
                            fee_eur=m["fee"] + gt,
                            gain_loss_eur=it - gt - m["cost"] - m["fee"],
                            total_sale_eur=it - gt,
                            total_cost_eur=m["cost"] + m["fee"],
                            notes=trade.notes,
                            source_buy_id=m["source_buy_id"],
                        )
                    )

                if trade.quantity - matched_qty_total > EPSILON:
                    unmatched = trade.quantity - matched_qty_total
                    it = unmatched * (v_sale / trade.quantity)
                    gt = unmatched * (f_sale / trade.quantity)
                    self._all_tax_events.append(
                        TaxEvent(
                            date=trade.date,
                            platform=trade.platform,
                            asset=trade.asset,
                            asset_type=trade.asset_type,
                            quantity_sold=unmatched,
                            acquisition_date=datetime(1900, 1, 1),
                            acquisition_cost_eur=Decimal("0"),
                            sale_proceeds_eur=it,
                            buy_fee_eur=Decimal("0"),
                            sell_fee_eur=gt,
                            fee_eur=gt,
                            gain_loss_eur=it - gt,
                            total_sale_eur=it - gt,
                            total_cost_eur=Decimal("0"),
                            notes=f"⚠️ Sin inventario previo (Coste 0) | {trade.notes}",
                        )
                    )
                    if trade.date.year == self.tax_year:
                        min_date_str = self.min_date.strftime("%d/%m/%Y") if self.min_date else "el inicio"
                        self.warnings.append(
                            f"⚠️ FALTA HISTORIAL: No se encuentra el origen de {unmatched:.8f} {trade.asset} vendidos el {trade.date.strftime('%d/%m/%Y')}. "
                            f"Se ha aplicado coste 0.00€ por prudencia fiscal. "
                            f"Sugerencia: Adjunta archivos de Binance con operaciones anteriores al {min_date_str} para calcular el coste real."
                        )

            elif trade.direction == "withdraw":
                account.consume_fifo(trade.quantity)

            elif trade.direction == "deposit":
                cpu = trade.value_eur / trade.quantity if trade.quantity > 0 else Decimal("0")
                account.add_lot(
                    FIFOLot(
                        date=trade.date,
                        asset=trade.asset,
                        quantity=trade.quantity,
                        cost_per_unit_eur=cpu,
                        buy_fee_per_unit_eur=Decimal("0"),
                        platform=trade.platform,
                        source_buy_id=id(trade),
                    )
                )
                account.total_bought += trade.quantity

    def process_dividends(self, dividends: List[Dividend]):
        for d in dividends:
            if d.date.year == self.tax_year:
                self.dividends.append(d)
