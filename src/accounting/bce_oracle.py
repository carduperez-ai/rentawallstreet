import os
import requests
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional

class BCEOracle:
    """Oráculo de tipos de cambio oficiales del Banco Central Europeo."""
    
    CSV_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv"
    CACHE_FILE = "bce_rates_cache.csv"
    
    def __init__(self, cache_dir: str = "."):
        self.cache_path = os.path.join(cache_dir, self.CACHE_FILE)
        self.rates: Dict[str, Dict[str, Decimal]] = {} # {fecha: {moneda: tasa}}
        self._load_cache()
        
    def _load_cache(self):
        if not os.path.exists(self.cache_path):
            self._update_cache()

        if not os.path.exists(self.cache_path):
            print("  ⚠️ CRÍTICO: No se pudo descargar ni encontrar el fichero de tipos BCE.")
            self.rates = {}
            return

        with open(self.cache_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row['Date']
                self.rates[date_str] = {k: Decimal(v) for k, v in row.items() if k != 'Date' and v and v != 'N/A'}

    def _update_cache(self):
        print(f"  🌐  Descargando tipos de cambio oficiales del BCE...")
        try:
            response = requests.get(self.CSV_URL, timeout=10)
            if response.status_code == 200:
                with open(self.cache_path, 'wb') as f:
                    f.write(response.content)
            else:
                print(f"  ⚠️  Error descargando BCE: {response.status_code}")
        except Exception as e:
            print(f"  ⚠️  Error de conexión con BCE: {e}")

    def get_rate(self, date: datetime, currency: str) -> Optional[Decimal]:
        """
        Devuelve el tipo de cambio oficial para una fecha y moneda.
        Retorna None si no se encuentra (Art. 119.1 LIRPF: el caller decide la alternativa).
        """
        if currency == "EUR":
            return Decimal('1.0')
            
        date_str = date.strftime('%Y-%m-%d')
        
        # Búsqueda hacia atrás (si es festivo/fin de semana, se usa el último disponible)
        current_date = date
        for _ in range(5): # Buscamos hasta 5 días atrás
            d_str = current_date.strftime('%Y-%m-%d')
            if d_str in self.rates and currency in self.rates[d_str]:
                return self.rates[d_str][currency]
            current_date -= timedelta(days=1)
        
        # Sin fallback silencioso: avisar y retornar None
        print(f"  ⚠️ BCE: Tipo de cambio no encontrado para {currency} en {date_str} ni en los 5 días anteriores.")
        return None
