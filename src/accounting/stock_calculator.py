from decimal import Decimal
from datetime import datetime
from typing import List, Set, Sequence
from fractions import Fraction
import dataclasses
from dataclasses import dataclass
from src.domain.stock_entities import Trade as BaseStockTrade, FIFOLot, TaxEvent as BaseStockTaxEvent
from src.domain.stock_fiscal_entities import Dividend as BaseStockDividend
from src.domain.shared_types import AnyTrade, AnyDividend, AnyTaxEvent
from src.accounting.wash_sale_scanner import WashSaleScanner
from src.domain.constants import EPSILON


@dataclass(frozen=True)
class CorporateActionEvent:
    """Registro inmutable en el Libro Mayor de Ajustes Corporativos."""

    event_date: datetime
    origin_asset_id: str  # Ticker o ISIN original
    target_asset_id: str  # Nuevo Ticker o ISIN
    event_type: str  # 'SPLIT', 'REVERSE_SPLIT', 'SPINOFF', 'MERGER'
    quantity_ratio: Fraction
    cost_basis_ratio: Fraction


@dataclass
class ProjectedLot:
    """Proyección dinámica de un lote inmutable al presente."""

    original_ref: FIFOLot
    current_asset_id: str
    projected_quantity: Decimal
    projected_cost: Decimal
    date: datetime  # Fecha original heredada intacta


class AssetLedger:
    """Gestor del historial genealógico de los activos."""

    def __init__(self):
        self.events: List[CorporateActionEvent] = []

    def add_event(self, event: CorporateActionEvent):
        self.events.append(event)
        self.events.sort(key=lambda e: e.event_date)

    def get_ancestor_asset_ids(self, target_asset_id: str, sell_date: datetime) -> Set[str]:
        """Rastrea hacia atrás para saber qué ISINs antiguos componen el actual."""
        ancestors = {target_asset_id.upper().strip()}
        relevant_events = [e for e in self.events if e.event_date <= sell_date]
        for event in reversed(relevant_events):
            if event.target_asset_id.upper().strip() in ancestors:
                ancestors.add(event.origin_asset_id.upper().strip())
        return ancestors


class InventoryProjector:
    """Proyector dinámico que aplica transformaciones matemáticas en tránsito."""

    def __init__(self, ledger: AssetLedger):
        self.ledger = ledger

    def project_lot_to_date(self, original_lot: FIFOLot, sell_date: datetime) -> ProjectedLot:
        """Calcula la realidad efectiva de un lote original en una fecha de venta."""
        current_qty = Fraction(original_lot.quantity)
        current_cost = Fraction(original_lot.quantity * original_lot.cost_per_unit_eur)
        current_asset_id = (original_lot.isin or original_lot.asset).upper().strip()

        for event in self.ledger.events:
            if original_lot.date < event.event_date <= sell_date:
                if current_asset_id == event.origin_asset_id.upper().strip():
                    current_qty *= event.quantity_ratio
                    current_cost *= event.cost_basis_ratio
                    current_asset_id = event.target_asset_id.upper().strip()

        return ProjectedLot(
            original_ref=original_lot,
            current_asset_id=current_asset_id,
            projected_quantity=Decimal(str(current_qty.numerator)) / Decimal(str(current_qty.denominator)),
            projected_cost=Decimal(str(current_cost.numerator)) / Decimal(str(current_cost.denominator)),
            date=original_lot.date,
        )


class StockTaxEngine:
    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year
        self.all_static_lots: List[FIFOLot] = []  # Registro inmutable bloqueado
        self.ledger = AssetLedger()
        self._all_tax_events: List[AnyTaxEvent] = []
        self.dividends: List[AnyDividend] = []
        self.warnings: List[str] = []
        self.raw_trades: List[AnyTrade] = []

    @property
    def tax_events(self) -> List[AnyTaxEvent]:
        return [te for te in self._all_tax_events if te.date.year == self.tax_year]

    @tax_events.setter
    def tax_events(self, value: List[AnyTaxEvent]):
        self._all_tax_events = value

    def process_trades(self, trades: Sequence[AnyTrade]):
        if not trades:
            return

        seen_hashes = set()
        unique_trades = []
        for trade in trades:
            if hasattr(trade, "hash_id") and trade.hash_id:
                if trade.hash_id in seen_hashes:
                    continue
                seen_hashes.add(trade.hash_id)
            unique_trades.append(trade)

        trades = unique_trades
        self.raw_trades.extend(trades)

        # 1. CAPA LEDGER: Registro de Eventos Corporativos (Determinismo Matemático)
        reorgs = [
            t
            for t in trades
            if any(kw in t.notes.upper() for kw in ["SPLIT", "REORG", "CAMBIO DE PRODUCTO"]) or "split" in t.direction
        ]
        processed_keys = set()

        for t in sorted(reorgs, key=lambda x: x.date):
            key = f"{t.date.date()}_{t.asset.upper().strip()}"
            if key in processed_keys:
                continue

            out_t = [
                r
                for r in reorgs
                if r.date.date() == t.date.date()
                and r.asset.upper().strip() == t.asset.upper().strip()
                and (r.direction in ["sell", "split_out"])
            ]
            in_t = [
                r
                for r in reorgs
                if r.date.date() == t.date.date()
                and r.asset.upper().strip() == t.asset.upper().strip()
                and (r.direction in ["buy", "split_in"])
            ]

            if out_t and in_t:
                old_q = sum(r.quantity for r in out_t)
                new_q = sum(r.quantity for r in in_t)

                # Búsqueda de liquidación de fracciones (Cash in Lieu)
                fractional_sales = [
                    r
                    for r in trades
                    if r.date.date() == t.date.date()
                    and r.asset.upper().strip() == t.asset.upper().strip()
                    and r.direction == "sell"
                    and r not in out_t
                ]

                fractional_q = sum(r.quantity for r in fractional_sales)
                theoretical_new_q = new_q + fractional_q
                ratio = Fraction(theoretical_new_q) / Fraction(old_q)

                self.ledger.add_event(
                    CorporateActionEvent(
                        event_date=t.date,
                        origin_asset_id=(out_t[0].isin or out_t[0].asset).upper().strip(),
                        target_asset_id=(in_t[0].isin or in_t[0].asset).upper().strip(),
                        event_type="SPLIT",
                        quantity_ratio=ratio,
                        cost_basis_ratio=Fraction(1, 1),
                    )
                )
                processed_keys.add(key)

        # 2. CAPA PROYECTOR: Procesamiento de Operaciones
        projector = InventoryProjector(self.ledger)
        for t in sorted(trades, key=lambda x: x.date):
            if (
                any(kw in t.notes.upper() for kw in ["SPLIT", "REORG", "MERGER", "CAMBIO DE PRODUCTO"])
                or "split" in t.direction
            ):
                continue

            target_id = (t.isin or t.asset).upper().strip()

            if t.direction == "buy":
                lot = FIFOLot(
                    t.date,
                    target_id,
                    t.asset,
                    t.quantity,
                    t.value_eur / t.quantity,
                    t.platform,
                    t.fee_eur / t.quantity,
                    source_buy_id=id(t),
                )
                lot.consumed_original_qty = Decimal("0")
                self.all_static_lots.append(lot)

            elif t.direction == "sell":
                ancestors = self.ledger.get_ancestor_asset_ids(target_id, t.date)
                projected_inventory = []
                for lot in self.all_static_lots:
                    if (lot.isin or lot.asset).upper().strip() in ancestors and lot.date <= t.date:
                        p_lot = projector.project_lot_to_date(lot, t.date)
                        if p_lot.current_asset_id == target_id:
                            orig_avail = lot.quantity - getattr(lot, "consumed_original_qty", Decimal("0"))
                            if orig_avail > EPSILON:
                                p_lot.projected_quantity = p_lot.projected_quantity * (
                                    Decimal(str(orig_avail)) / Decimal(str(lot.quantity))
                                )
                                projected_inventory.append(p_lot)

                projected_inventory.sort(key=lambda p: p.date)
                remaining = t.quantity
                for p in projected_inventory:
                    if remaining <= EPSILON:
                        break
                    lot = p.original_ref
                    if p.projected_quantity <= remaining + EPSILON:
                        q_eff, q_orig = p.projected_quantity, lot.quantity - lot.consumed_original_qty
                    else:
                        q_eff = remaining
                        q_orig = (
                            (remaining / p.projected_quantity) * (lot.quantity - lot.consumed_original_qty)
                            if p.projected_quantity > 0
                            else Decimal("0")
                        )

                    # Para soportar Wash Sale Interanual, guardamos TODO el historial de ventas
                    s_proc = (q_eff / t.quantity) * t.value_eur
                    s_fee = (q_eff / t.quantity) * t.fee_eur
                    c_orig = q_orig * lot.cost_per_unit_eur
                    f_orig = q_orig * lot.buy_fee_per_unit_eur
                    self._all_tax_events.append(
                        BaseStockTaxEvent(
                            date=t.date,
                            platform=t.platform,
                            asset=t.asset,
                            isin=target_id,
                            ticker=getattr(t, "ticker", ""),
                            asset_type=t.asset_type or "stock",
                            quantity_sold=q_eff,
                            acquisition_date=p.date,
                            acquisition_cost_eur=c_orig,
                            sale_proceeds_eur=s_proc,
                            buy_fee_eur=f_orig,
                            sell_fee_eur=s_fee,
                            gain_loss_eur=(s_proc - s_fee) - (c_orig + f_orig),
                            notes=t.notes,
                            source_buy_id=getattr(lot, "source_buy_id", 0),
                        )
                    )
                    lot.consumed_original_qty += q_orig
                    remaining -= q_eff

                if remaining > EPSILON:
                    self.warnings.append(
                        f"⚠️ ERROR DE TRAZABILIDAD: Faltan {remaining} acciones en el historial para {t.asset} ({target_id}) en fecha {t.date.date()}"
                    )

            elif t.direction == "withdraw":
                ancestors = self.ledger.get_ancestor_asset_ids(target_id, t.date)
                projected_inventory = []
                for lot in self.all_static_lots:
                    if (lot.isin or lot.asset).upper().strip() in ancestors and lot.date <= t.date:
                        p_lot = projector.project_lot_to_date(lot, t.date)
                        if p_lot.current_asset_id == target_id:
                            orig_avail = lot.quantity - getattr(lot, "consumed_original_qty", Decimal("0"))
                            if orig_avail > EPSILON:
                                p_lot.projected_quantity = p_lot.projected_quantity * (
                                    Decimal(str(orig_avail)) / Decimal(str(lot.quantity))
                                )
                                projected_inventory.append(p_lot)

                projected_inventory.sort(key=lambda p: p.date)
                remaining = t.quantity
                for p in projected_inventory:
                    if remaining <= EPSILON:
                        break
                    lot = p.original_ref
                    if p.projected_quantity <= remaining + EPSILON:
                        q_eff, q_orig = p.projected_quantity, lot.quantity - lot.consumed_original_qty
                    else:
                        q_eff = remaining
                        q_orig = (
                            (remaining / p.projected_quantity) * (lot.quantity - lot.consumed_original_qty)
                            if p.projected_quantity > 0
                            else Decimal("0")
                        )

                    lot.consumed_original_qty += q_orig
                    remaining -= q_eff

            elif t.direction == "deposit":
                cpu = t.value_eur / t.quantity if t.quantity > 0 else Decimal("0")
                lot = FIFOLot(
                    t.date, target_id, t.asset, t.quantity, cpu, t.platform, Decimal("0"), source_buy_id=id(t)
                )
                lot.consumed_original_qty = Decimal("0")
                self.all_static_lots.append(lot)

    def ingest_degiro(self, file_paths: List[str]):
        from src.ingestion.degiro_reader import parse as parse_degiro

        t, d = parse_degiro(file_paths)
        self.process_trades(t)
        for div in d:
            if div.date.year == self.tax_year:
                self.dividends.append(div)

    def ingest_trading212(self, file_paths: List[str]):
        from src.ingestion.trading212_reader import parse as parse_t212

        for path in file_paths:
            t, d = parse_t212(path)
            self.process_trades(t)
            for div in d:
                if div.date.year == self.tax_year:
                    self.dividends.append(div)

    def apply_wash_sale_rules(self):
        if not self._all_tax_events:
            return
        scanner = WashSaleScanner(self.raw_trades)
        scanner.scan(self._all_tax_events)

        # Mapa de todas las ventas para encontrar rápidamente quién consumió qué compra
        sales_by_buy_id = {}
        for te in self._all_tax_events:
            s_id = getattr(te, "source_buy_id", 0)
            if s_id:
                if s_id not in sales_by_buy_id:
                    sales_by_buy_id[s_id] = []
                sales_by_buy_id[s_id].append(te)

        # Inter-year Unblocking: Si las acciones recompradas se han vendido, se desbloquea la pérdida en la fecha de venta.
        events_to_add = []
        for te in list(self._all_tax_events):
            if getattr(te, "is_wash_sale", False) and hasattr(te, "blocked_by_buys"):
                # Agrupamos todas las ventas que consumieron las recompras
                consuming_sales = []
                total_repurchased_qty = Decimal("0")

                for buy_trade in getattr(te, "blocked_by_buys", []):
                    total_repurchased_qty += buy_trade.quantity
                    b_id = id(buy_trade)
                    if b_id in sales_by_buy_id:
                        consuming_sales.extend(sales_by_buy_id[b_id])

                if consuming_sales and total_repurchased_qty > Decimal("0"):
                    # Ordenamos cronológicamente para aflorar la pérdida secuencialmente
                    consuming_sales.sort(key=lambda x: x.date)

                    # Vamos a desbloquear la pérdida proporcionalmente a cómo se venden las recompras
                    # Como una recompra pudo haber sufrido un split, usamos la proporción económica (ratio_consumido)
                    # ratio_consumido = (c_orig de la venta de la recompra) / (coste total de la recompra)

                    from copy import deepcopy

                    remaining_te = deepcopy(te)

                    for c_sale in consuming_sales:
                        # Encontrar la cantidad original consumida (usamos la proporción del coste original)
                        # c_sale.acquisition_cost_eur es el c_orig de esa venta.
                        # El coste original de la compra que originó c_sale:
                        buy_origin = next(
                            (
                                b
                                for b in getattr(te, "blocked_by_buys", [])
                                if id(b) == getattr(c_sale, "source_buy_id", 0)
                            ),
                            None,
                        )
                        if not buy_origin:
                            continue

                        cost_of_buy = buy_origin.value_eur
                        if cost_of_buy <= EPSILON:
                            ratio = (
                                c_sale.quantity_sold / buy_origin.quantity if buy_origin.quantity > 0 else Decimal("0")
                            )
                        else:
                            ratio = c_sale.acquisition_cost_eur / cost_of_buy

                        # El ratio es respecto a esa compra específica.
                        # El ratio respecto al TOTAL recomprado es:
                        global_ratio = ratio * (buy_origin.quantity / total_repurchased_qty)
                        global_ratio = min(global_ratio, Decimal("1.0"))

                        if global_ratio > Decimal("0.001"):
                            notes_val = (
                                te.notes + " [DESBLOQUEADA en el año]"
                                if c_sale.date.year == te.date.year
                                else te.notes + f" [AFLORADA: Desbloqueo interanual por venta en {c_sale.date.year}]"
                            )
                            date_val = (
                                te.date
                                if c_sale.date.year == te.date.year
                                else datetime(c_sale.date.year, 12, 31, 23, 59, 59)
                            )

                            unblock_te = dataclasses.replace(
                                te,
                                quantity_sold=te.quantity_sold * global_ratio,
                                acquisition_cost_eur=te.acquisition_cost_eur * global_ratio,
                                buy_fee_eur=te.buy_fee_eur * global_ratio,
                                sale_proceeds_eur=te.sale_proceeds_eur * global_ratio,
                                sell_fee_eur=te.sell_fee_eur * global_ratio,
                                gain_loss_eur=te.gain_loss_eur * global_ratio,
                                gain_loss_eur_effective=getattr(te, "gain_loss_eur_effective", te.gain_loss_eur)
                                * global_ratio,
                                is_wash_sale=False,
                                notes=notes_val,
                                date=date_val,
                            )

                            events_to_add.append(unblock_te)

                            # Reducir el remaining
                            remaining_te = dataclasses.replace(
                                remaining_te,
                                quantity_sold=remaining_te.quantity_sold - unblock_te.quantity_sold,
                                acquisition_cost_eur=remaining_te.acquisition_cost_eur
                                - unblock_te.acquisition_cost_eur,
                                sale_proceeds_eur=remaining_te.sale_proceeds_eur - unblock_te.sale_proceeds_eur,
                                gain_loss_eur=remaining_te.gain_loss_eur - unblock_te.gain_loss_eur,
                            )

                    if remaining_te.quantity_sold > EPSILON:
                        remaining_te = dataclasses.replace(
                            remaining_te, notes=remaining_te.notes.split("[DESBLOQUEO")[0] + " [REMANENTE BLOQUEADO]"
                        )
                        events_to_add.append(remaining_te)

                    # Eliminamos el evento original porque lo hemos sustituido por el desbloqueado + remanente
                    self._all_tax_events.remove(te)

        if events_to_add:
            self._all_tax_events.extend(events_to_add)

    def process_dividends(self, dividends: Sequence[AnyDividend]):
        for d in dividends:
            if d.date.year == self.tax_year:
                self.dividends.append(d)
