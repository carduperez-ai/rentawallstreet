import inspect
from decimal import Decimal
from typing import Dict, Any
from src.domain.fiscal_entities import TaxpayerProfile

class ProfileBuilder:
    """
    Capa Anticorrupción (ACL) para la instanciación segura de TaxpayerProfile.
    Filtra parámetros intrusos, extrae deducciones autonómicas (Art. 72 LIRPF) y asegura la coerción matemática.
    """
    @staticmethod
    def from_dict(raw_data: Dict[str, Any]) -> TaxpayerProfile:
        # 1. Leer firma oficial del dominio
        valid_keys = inspect.signature(TaxpayerProfile).parameters.keys()
        
        # 2. Purgar inyecciones intrusas (ej. fiscal_year)
        clean_data = {k: v for k, v in raw_data.items() if k in valid_keys}
        
        # 3. Lógica de Extracción Regional (Art. 72 LIRPF)
        region_str = raw_data.get('region', '').lower().replace(' ', '_')
        regional_data = {}
        
        PREFIX_MAP = {
            'andalucia': 'and_',
            'aragon': 'ara_',
            'asturias': 'ast_',
            'baleares': 'balears_',
            'canarias': 'canarias_',
            'cantabria': 'cantabria_',
            'castilla_la_mancha': 'clm_',
            'castilla_y_leon': 'cyl_',
            'castilla_leon': 'cyl_',
            'cataluna': 'cat_',
            'extremadura': 'ext_',
            'galicia': 'gal_',
            'madrid': 'mad_',
            'murcia': 'murcia_',
            'navarra': 'nav_',
            'pais_vasco': 'pv_',
            'la_rioja': 'rioja_',
            'valenciana': 'val_'
        }
        
        if region_str:
            prefix = PREFIX_MAP.get(region_str, f"{region_str}_")
            for key, value in raw_data.items():
                if key not in valid_keys and key.startswith(prefix):
                    # Coerción monetaria para importes regionales, preservando la clave original
                    if key.endswith('_eur') and value is not None:
                        regional_data[key] = Decimal(str(value))
                    else:
                        regional_data[key] = value
                    
                    # Compatibilidad para deductores sin prefijo (ej. Aragón)
                    stripped_key = key[len(prefix):]
                    if stripped_key not in regional_data:
                        regional_data[stripped_key] = regional_data[key]
            
            # Extract cross-regional overrides explicitly
            if 'minimo_personal_familiar' in raw_data:
                regional_data['minimo_personal_familiar'] = Decimal(str(raw_data['minimo_personal_familiar']))

        # 4. Coerción matemática y de tipos base
        for key, value in clean_data.items():
            if value is None:
                continue
            if key.endswith('_eur'):
                clean_data[key] = Decimal(str(value))
            elif key in ('da_61_opt_in',):
                clean_data[key] = bool(value)
                
        # Remove injected variables from clean_data so it doesn't fail on TaxpayerProfile
        mantenimiento = clean_data.pop('expenses_maintenance', raw_data.get('expenses_maintenance'))
        catastral = clean_data.pop('valor_catastral', raw_data.get('valor_catastral'))
        deferred = clean_data.pop('is_deferred_payment', raw_data.get('is_deferred_payment'))
        
        profile = TaxpayerProfile(**clean_data, regional_data=regional_data)
        
        # Intercepción directa de inmuebles
        if mantenimiento is not None or catastral is not None:
            from src.domain.fiscal_entities import RealEstateAsset
            
            inmueble = RealEstateAsset(
                expenses_maintenance=Decimal(str(mantenimiento)) if mantenimiento is not None else Decimal('0'),
                valor_catastral=Decimal(str(catastral)) if catastral is not None else Decimal('0')
            )
            
            if not hasattr(profile, 'real_estate_assets') or profile.real_estate_assets is None:
                profile.real_estate_assets = []
            
            profile.real_estate_assets.append(inmueble)
            
        # Intercepción de cobros aplazados
        if deferred is not None:
            from src.domain.fiscal_entities import CapitalGains
            from datetime import datetime
            cg = CapitalGains(
                date=datetime.now(),
                description="Cobro aplazado manual",
                gain_loss_eur=Decimal('0'), # Se ajustaría en la ingesta si hubiera importe
                category="otros",
                is_deferred_payment=bool(deferred)
            )
            if not hasattr(profile, 'capital_gains') or profile.capital_gains is None:
                profile.capital_gains = []
            profile.capital_gains.append(cg)
            
        return profile
