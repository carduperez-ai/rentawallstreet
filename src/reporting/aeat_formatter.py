from decimal import Decimal
from collections import defaultdict
from typing import List, Dict, Any
from src.domain.crypto_entities import TaxEvent, Dividend as CryptoDividend

class AEATFormatter:
    """Formatea resultados fiscales siguiendo los bloques oficiales de la AEAT 2025 (V5 Audit)."""
    
    def __init__(self, tax_events: List[TaxEvent], dividends: List[Any]):
        self.tax_events = tax_events
        self.dividends = dividends
        
    def get_rcm_summary(self) -> Dict[str, Any]:
        """Bloque 2: RCM agrupado por AssetID + Totales."""
        grouped = defaultdict(lambda: {
            'asset_name': '', 
            'asset_id': '', 
            'gross_eur': Decimal('0'), 
            'w_foreign': Decimal('0'), 
            'w_spain': Decimal('0'),
            'custody_fee': Decimal('0'),
            'net_eur': Decimal('0')
        })
        
        totals = {
            'gross': Decimal('0'),
            'w_foreign': Decimal('0'),
            'w_spain': Decimal('0'),
            'custody_fee': Decimal('0'),
            'net': Decimal('0')
        }
        
        for d in self.dividends:
            aid = getattr(d, 'asset_id', getattr(d, 'isin', d.asset))
            g = grouped[aid]
            g['asset_id'] = aid
            g['asset_name'] = d.asset
            
            # Soporte polimórfico para StockDividend y Dividend (crypto)
            gross = getattr(d, 'gross_eur', getattr(d, 'amount_eur', Decimal('0')))
            w_f = getattr(d, 'withholding_foreign_eur', Decimal('0'))
            w_s = getattr(d, 'withholding_spain_eur', Decimal('0'))
            fee = getattr(d, 'custody_fee_eur', Decimal('0'))
            
            g['gross_eur'] += gross
            g['w_foreign'] += w_f
            g['w_spain'] += w_s
            g['custody_fee'] += fee
            
            totals['gross'] += gross
            totals['w_foreign'] += w_f
            totals['w_spain'] += w_s
            totals['custody_fee'] += fee
            
        # Redondeo final
        for g in grouped.values():
            g['gross_eur'] = g['gross_eur'].quantize(Decimal('0.01'))
            g['w_foreign'] = g['w_foreign'].quantize(Decimal('0.01'))
            g['w_spain'] = g['w_spain'].quantize(Decimal('0.01'))
            g['custody_fee'] = g['custody_fee'].quantize(Decimal('0.01'))
            g['net_eur'] = (g['gross_eur'] - g['w_foreign'] - g['w_spain']).quantize(Decimal('0.01'))
            
        for k in totals: totals[k] = totals[k].quantize(Decimal('0.01'))
        totals['net'] = (totals['gross'] - totals['w_foreign'] - totals['w_spain']).quantize(Decimal('0.01'))
            
        return {'data': sorted(grouped.values(), key=lambda x: x['asset_name']), 'totals': totals}

    def get_gpp_summary(self) -> Dict[str, Any]:
        """Bloque 3: GPP con totales por ficha y total global."""
        cards = {
            "0326": {"title": "Acciones cotizadas", "data": [], "total_cost": Decimal('0'), "total_proceeds": Decimal('0'), "total_gain": Decimal('0')},
            "0311": {"title": "IIC (Fondos/SICAV)", "data": [], "total_cost": Decimal('0'), "total_proceeds": Decimal('0'), "total_gain": Decimal('0')},
            "1803": {"title": "Criptoactivos", "data": [], "total_cost": Decimal('0'), "total_proceeds": Decimal('0'), "total_gain": Decimal('0')},
            "0000": {"title": "Otros", "data": [], "total_cost": Decimal('0'), "total_proceeds": Decimal('0'), "total_gain": Decimal('0')}
        }
        
        block_totals = {"cost": Decimal('0'), "proceeds": Decimal('0'), "gain": Decimal('0')}
        
        asset_groups = defaultdict(lambda: {
            'asset_name': '', 'asset_id': '', 'type': '',
            'cost': Decimal('0'), 'proceeds': Decimal('0'), 'gain': Decimal('0'),
            'has_wash_sales': False
        })
        
        for te in self.tax_events:
            g = asset_groups[te.asset_id]
            g['asset_id'] = te.asset_id
            g['asset_name'] = te.asset_name if te.asset_name else te.asset
            g['type'] = te.asset_type
            g['cost'] += (te.acquisition_cost_eur + te.buy_fee_eur)
            g['proceeds'] += (te.sale_proceeds_eur - te.sell_fee_eur)
            g['gain'] += te.gain_loss_eur
            if getattr(te, 'is_wash_sale', False) and getattr(te, 'asset_type', '') != 'crypto': g['has_wash_sales'] = True
            
        for aid, data in asset_groups.items():
            box = "0000"
            if data['type'] == 'crypto': box = "1803"
            elif data['type'] == 'fund': box = "0311"
            elif data['type'] in ['stock', 'etf', 'right']: box = "0326"
            
            data['cost'] = data['cost'].quantize(Decimal('0.01'))
            data['proceeds'] = data['proceeds'].quantize(Decimal('0.01'))
            data['gain'] = data['gain'].quantize(Decimal('0.01'))
            
            cards[box]['data'].append(data)
            cards[box]['total_cost'] += data['cost']
            cards[box]['total_proceeds'] += data['proceeds']
            cards[box]['total_gain'] += data['gain']
            
            block_totals['cost'] += data['cost']
            block_totals['proceeds'] += data['proceeds']
            block_totals['gain'] += data['gain']
            
        # Limpieza de fichas vacías y redondeo de totales
        final_cards = {}
        for k, v in cards.items():
            if v['data']:
                v['total_cost'] = v['total_cost'].quantize(Decimal('0.01'))
                v['total_proceeds'] = v['total_proceeds'].quantize(Decimal('0.01'))
                v['total_gain'] = v['total_gain'].quantize(Decimal('0.01'))
                final_cards[k] = v
        
        for k in block_totals: block_totals[k] = block_totals[k].quantize(Decimal('0.01'))
        
        return {'cards': final_cards, 'totals': block_totals}

    def get_audit_annex(self) -> List[Dict[str, Any]]:
        """Trazabilidad total para el usuario e inspección."""
        annex = []
        isin_map = defaultdict(list)
        for te in self.tax_events:
            isin_map[te.asset_id].append(te)
            
        for aid, events in isin_map.items():
            platforms = list(set([e.platform for e in events]))
            annex.append({
                'asset_id': aid,
                'name': events[0].asset_name,
                'platforms': platforms,
                'count': len(events),
                'total_gain': sum((e.gain_loss_eur for e in events), Decimal('0')).quantize(Decimal('0.01')),
                'has_wash_sale': any(getattr(e, 'is_wash_sale', False) and getattr(e, 'asset_type', '') != 'crypto' for e in events)
            })
        return annex
