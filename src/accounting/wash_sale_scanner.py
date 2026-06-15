from datetime import timedelta
from decimal import Decimal
import dataclasses
from dateutil.relativedelta import relativedelta


class WashSaleScanner:
    def __init__(self, trades):
        self.trades = trades

    def scan(self, tax_events, days_limit=60):
        """
        Escanea eventos fiscales en busca de recompras que invaliden la pérdida.
        Implementa regla de proporcionalidad y difiere el bloqueo hasta la venta de recompras.
        Para acciones cotizadas: 60 días. (Implementación base).
        """
        assets_map = {}
        for t in self.trades:
            key = t.asset.strip().upper()
            if key not in assets_map:
                assets_map[key] = []
            assets_map[key].append(t)

        # Diccionario de consumo: evita que la misma compra bloquee múltiples ventas
        # key = id(trade), value = cantidad ya consumida de esa compra
        consumed_buy_qty = {}

        # Lista temporal para insertar los eventos fraccionados
        new_events = []

        for te in tax_events:
            if getattr(te, "is_wash_sale", False):
                new_events.append(te)
                continue

            if te.gain_loss_eur >= 0:
                new_events.append(te)
                continue

            asset_key = te.asset.strip().upper()
            if "CFD" in asset_key:
                new_events.append(te)
                continue

            # Límite normativo de fecha a fecha (Art. 5 Código Civil y Ley IRPF)
            if getattr(te, "is_unlisted", False):
                delta = relativedelta(years=1)
                limit_text = "1 año"
            else:
                delta = relativedelta(months=2)
                limit_text = "2 meses"
            
            start_limit = te.date - delta
            end_limit = te.date + delta

            relevant_trades = assets_map.get(asset_key, [])

            # Calcular cantidad recomprada (descontando qty ya consumida por eventos anteriores)
            repurchased_qty = Decimal("0")
            repurchasing_trades = []

            for tr in relevant_trades:
                if tr.direction == "buy" and start_limit <= tr.date <= end_limit:
                    # Ignorar la propia compra original del lote vendido (misma fecha y cant)
                    if tr.date == te.acquisition_date and abs(tr.quantity - te.quantity_sold) < Decimal("0.001"):
                        continue

                    # Calcular cantidad disponible (no consumida por eventos anteriores)
                    available = tr.quantity - consumed_buy_qty.get(id(tr), Decimal("0"))
                    if available <= Decimal("0"):
                        continue

                    repurchased_qty += available
                    repurchasing_trades.append(tr)

            if repurchased_qty <= Decimal("0"):
                new_events.append(te)
                continue

            # Proporción bloqueada
            blocked_ratio = min(repurchased_qty / te.quantity_sold, Decimal("1.0"))
            blocked_qty = te.quantity_sold * blocked_ratio

            # Registrar consumo de las compras usadas para este bloqueo
            remaining_to_consume = blocked_qty
            for tr in repurchasing_trades:
                if remaining_to_consume <= Decimal("0"):
                    break
                available = tr.quantity - consumed_buy_qty.get(id(tr), Decimal("0"))
                consume_now = min(available, remaining_to_consume)
                consumed_buy_qty[id(tr)] = consumed_buy_qty.get(id(tr), Decimal("0")) + consume_now
                remaining_to_consume -= consume_now

            if blocked_ratio < Decimal("1.0"):
                # Escisión del evento: Parte Deducible (1 - ratio)
                allowed_ratio = Decimal("1.0") - blocked_ratio
                te_allowed = dataclasses.replace(
                    te,
                    quantity_sold=te.quantity_sold * allowed_ratio,
                    acquisition_cost_eur=te.acquisition_cost_eur * allowed_ratio,
                    sale_proceeds_eur=te.sale_proceeds_eur * allowed_ratio,
                    buy_fee_eur=te.buy_fee_eur * allowed_ratio,
                    sell_fee_eur=te.sell_fee_eur * allowed_ratio,
                    gain_loss_eur=te.gain_loss_eur * allowed_ratio,
                    is_wash_sale=False,
                )
                new_events.append(te_allowed)

                # Modificamos el evento original 'te' para que sea solo la parte bloqueada
                te = dataclasses.replace(
                    te,
                    quantity_sold=te.quantity_sold * blocked_ratio,
                    acquisition_cost_eur=te.acquisition_cost_eur * blocked_ratio,
                    sale_proceeds_eur=te.sale_proceeds_eur * blocked_ratio,
                    buy_fee_eur=te.buy_fee_eur * blocked_ratio,
                    sell_fee_eur=te.sell_fee_eur * blocked_ratio,
                    gain_loss_eur=te.gain_loss_eur * blocked_ratio,
                )

            te = dataclasses.replace(
                te,
                is_wash_sale=True,
                blocked_by_buys=repurchasing_trades,
                notes=f"Wash Sale: {blocked_ratio*100:.1f}% de la pérdida bloqueada por recompra en +/- {limit_text}.",
            )
            new_events.append(te)

        # Reemplazamos la lista in-place (para que el llamador vea los cambios si pasa la referencia)
        tax_events.clear()
        tax_events.extend(new_events)
