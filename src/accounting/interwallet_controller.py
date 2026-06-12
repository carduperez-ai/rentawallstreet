from decimal import Decimal
from typing import List
from datetime import datetime
import dataclasses

from src.domain.crypto_entities import Trade, TaxEvent
from src.accounting.fifo_calculator_stock import TaxEngine as CryptoTaxEngine
from src.accounting.stock_calculator import StockTaxEngine

class InterwalletController:
    """
    Orquestador Arquitectónico V5.
    1. Neutraliza traspasos entre wallets (deposits y withdraws ciegos).
    2. Ejecuta el Motor FIFO desde el año cero para obtener el historial inmutable.
    3. Aplica la Regla Anti-Lavado y el Desbloqueo Forense sin mutar el motor.
    """
    def __init__(self, raw_crypto_trades: List, raw_stock_trades: List):
        self.raw_crypto_trades = raw_crypto_trades
        self.raw_stock_trades = raw_stock_trades
        self.crypto_warnings = []
        self.stock_warnings = []

    def execute_pipeline(self, target_fiscal_year: int) -> tuple[List, List]:
        # Fase 1: Neutralizar traspasos (crypto y stock)
        crypto_trades = self._filter_interwallet_transfers(self.raw_crypto_trades, is_crypto=True)
        stock_trades = self._filter_interwallet_transfers(self.raw_stock_trades, is_crypto=False)

        # Fase 2 & 3
        crypto_tax_events = self._run_historical_simulation(
            crypto_trades, is_crypto=True, target_year=target_fiscal_year
        )
        
        stock_tax_events = self._run_historical_simulation(
            stock_trades, is_crypto=False, target_year=target_fiscal_year
        )
        
        return crypto_tax_events, stock_tax_events

    def _filter_interwallet_transfers(self, trades: List, is_crypto: bool = True) -> List:
        trades_sorted = sorted(trades, key=lambda x: getattr(x, 'date'))
        unmatched_withdraws = []
        unmatched_deposits = []
        final_trades = []

        for trade in trades_sorted:
            d = getattr(trade, 'direction', '')
            if d == "withdraw": unmatched_withdraws.append(trade)
            elif d == "deposit": unmatched_deposits.append(trade)
            else: final_trades.append(trade)

        for deposit in list(unmatched_deposits):
            matched = False
            for withdraw in list(unmatched_withdraws):
                if getattr(deposit, 'asset') == getattr(withdraw, 'asset') and \
                   abs((getattr(deposit, 'date') - getattr(withdraw, 'date')).total_seconds()) <= 86400:
                    q_dep = getattr(deposit, 'quantity', Decimal('0'))
                    q_wit = getattr(withdraw, 'quantity', Decimal('0'))
                    
                    if q_dep <= q_wit:
                        diff = q_wit - q_dep
                        if diff > Decimal('0'):
                            # Diferencia = Network fee
                            fee_trade = dataclasses.replace(
                                withdraw,
                                quantity=diff,
                                value_eur=Decimal('0'),
                                fee_eur=Decimal('0'),
                                notes="NETWORK_FEE (Traspaso)"
                            )
                            final_trades.append(fee_trade)
                        
                        unmatched_withdraws.remove(withdraw)
                        unmatched_deposits.remove(deposit)
                        matched = True
                        break
            if not matched:
                is_income = any(kw in (getattr(deposit, 'notes', '') or '').upper() for kw in ['AIRDROP', 'MINING', 'INCOME', 'REWARD', 'STAKING'])
                if not is_income:
                    # Anulamos el valor para que el motor FIFO le asigne coste 0 (Art. 34 LIRPF)
                    modified_deposit = dataclasses.replace(deposit, value_eur=Decimal('0'))
                    
                    if is_crypto:
                        self.crypto_warnings.append(
                            f"⚠️ TRASPASO CIEGO: Asignado coste 0.00€ al depósito de {getattr(modified_deposit, 'quantity')} {getattr(modified_deposit, 'asset')} el {getattr(modified_deposit, 'date').strftime('%d/%m/%Y')} (Art. 34 LIRPF). "
                            f"Nota: {getattr(modified_deposit, 'notes')}. Unifica el historial completo para arrastrar el coste real."
                        )
                    else:
                        self.stock_warnings.append(
                            f"⚠️ TRASPASO CIEGO BURSÁTIL: Asignado coste 0.00€ al depósito de {getattr(modified_deposit, 'quantity')} {getattr(modified_deposit, 'asset')} el {getattr(modified_deposit, 'date').strftime('%d/%m/%Y')} (Art. 34 LIRPF). "
                            f"Nota: {getattr(modified_deposit, 'notes')}. Unifica el historial de tus brokers."
                        )
                    final_trades.append(modified_deposit)
                else:
                    final_trades.append(deposit)

        final_trades.extend(unmatched_withdraws)
        return sorted(final_trades, key=lambda x: getattr(x, 'date'))

    def _run_historical_simulation(self, trades: List, is_crypto: bool, target_year: int) -> List:
        if not trades: return []
        
        # El engine ya procesa todos los trades desde el origen, y guarda en 'tax_events'
        # SOLO los eventos correspondientes a 'self.tax_year'.
        # No necesitamos iterar todos los años si solo nos interesa el target_year.
        if is_crypto:
            engine = CryptoTaxEngine(tax_year=target_year)
        else:
            engine = StockTaxEngine(tax_year=target_year)
            
        engine.process_trades(trades)
        
        # Regla Anti-Aplicación (Wash Sales):
        # CRÍTICO: WASH SALES NO APLICA A CRYPTOS (DGT V1604-23). Venta con pérdida es plenamente deducible.
        # No bloquear ni alterar en absoluto la lógica del motor cripto respecto a este punto.
        # 2. Acciones: APLICA. Usamos el escáner de alta fidelidad.
        if not is_crypto:
            if hasattr(engine, 'apply_wash_sale_rules'):
                engine.apply_wash_sale_rules()
                
        if is_crypto:
            self.crypto_warnings.extend(getattr(engine, 'warnings', []))
        else:
            self.stock_warnings.extend(getattr(engine, 'warnings', []))

        final_events = getattr(engine, 'tax_events', [])
        final_events.sort(key=lambda x: getattr(x, 'date'))
        return final_events

    def _scale_tax_event(self, te, ratio: Decimal):
        """
        Clona y escala todos los campos monetarios del evento para evitar inflar la transmisión
        o el coste cuando el Wash Sale Scanner divide la venta.
        """
        import dataclasses
        cambios = {}
        # Campos monetarios susceptibles de estar en Stock o Crypto
        fields = [
            'quantity_sold', 'acquisition_cost_eur', 'sale_proceeds_eur',
            'buy_fee_eur', 'sell_fee_eur', 'fee_eur', 'gain_loss_eur',
            'total_sale_eur', 'total_cost_eur', 'gain_loss_eur_effective'
        ]
        for f in fields:
            if hasattr(te, f):
                # Importante: No podemos mutar @properties, preparamos kwargs solo de atributos reales.
                attr = getattr(type(te), f, None)
                if not isinstance(attr, property):
                    val = getattr(te, f)
                    if isinstance(val, Decimal):
                        cambios[f] = val * ratio
                        
        return dataclasses.replace(te, **cambios)
