import os
import requests
import csv
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

class StockBCEOracle:
    """
    Oráculo de tipos de cambio oficiales del BCE para el ecosistema de Acciones.
    Incluye persistencia en caché local para auditoría.
    """
    
    CSV_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv"
    CACHE_FILE = "stock_bce_rates_cache.csv"
    
    def __init__(self, cache_dir: str = "."):
        self.cache_path = os.path.join(cache_dir, self.CACHE_FILE)
        self.rates: Dict[str, Dict[str, Decimal]] = {}
        self._load_cache()
        
    def _load_cache(self):
        """Carga el historial desde el archivo local o descarga si no existe."""
        if not os.path.exists(self.cache_path):
            self._update_cache()
            
        try:
            with open(self.cache_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row['Date']
                    self.rates[date_str] = {k: Decimal(v) for k, v in row.items() if k != 'Date' and v and v != 'N/A'}
        except Exception as e:
            print(f"  [!] Error leyendo caché de tipos de cambio: {e}")

    def _update_cache(self):
        """Descarga masiva de tipos de cambio desde el servidor oficial del BCE."""
        print(f"  [STOCK-ORACLE] Descargando tipos de cambio oficiales del BCE...")
        try:
            response = requests.get(self.CSV_URL, timeout=15)
            if response.status_code == 200:
                with open(self.cache_path, 'wb') as f:
                    f.write(response.content)
                print(f"  [OK] Cache de tipos de cambio guardada en {self.CACHE_FILE}")
            else:
                print(f"  [!] Fallo en descarga BCE: {response.status_code}")
        except Exception as e:
            print(f"  [!] Error de conexion con servidor BCE: {e}")

    def get_rate(self, date: datetime, currency: str) -> Decimal:
        """
        Devuelve el tipo de cambio oficial para una fecha y moneda.
        Realiza búsqueda retrospectiva y fallback a API Frankfurter.
        """
        if currency == "EUR" or not currency:
            return Decimal('1.0')
            
        currency = currency.upper().strip()
        d_str = date.strftime('%Y-%m-%d')
        
        # 1. Intentar desde memoria/caché
        from datetime import timedelta
        for offset in range(8):
            current_date = date - timedelta(days=offset)
            curr_str = current_date.strftime('%Y-%m-%d')
            if curr_str in self.rates and currency in self.rates[curr_str]:
                return self.rates[curr_str][currency]
            
        # 2. Fallback: Petición puntual a Frankfurter API (Datos BCE)
        try:
            url = f"https://api.frankfurter.app/{d_str}?to={currency}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                rate = Decimal(str(data['rates'][currency]))
                # Guardar en memoria para evitar peticiones repetidas
                if d_str not in self.rates: self.rates[d_str] = {}
                self.rates[d_str][currency] = rate
                return rate
        except Exception as e:
            print(f"  [!] Fallo fallback Frankfurter para {d_str}: {e}")
            
        # Sin fallback silencioso: avisar y retornar None
        print(f"  ⚠️ StockBCE: Tipo de cambio no encontrado para {currency} en {d_str}.")
        return None
