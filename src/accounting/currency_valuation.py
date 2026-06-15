"""
Tipos de cambio históricos EUR/USD usando la API gratuita de Frankfurter (datos del BCE).
Incluye caché en memoria para no repetir peticiones.
"""

import urllib.request
import json
import os
from datetime import datetime, timedelta
from typing import Optional


from decimal import Decimal


# Sistema de caché local alimentado por descarga masiva
_cache_divisas: dict[str, Decimal] = {}  # clave: "YYYY-MM-DD" → EUR por 1 USD
_historial_cargado = False


def cargar_historial_completo():
    """
    Realiza una única petición masiva a la API del BCE para descargar
    todos los tipos de cambio desde 2020 hasta hoy.
    """
    global _historial_cargado

    # Rango desde 2020 para cubrir todas las declaraciones posibles
    url = "https://api.frankfurter.app/2020-01-01..?from=USD&to=EUR"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RentaCalculadora/1.0",
        "Accept": "application/json",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if "rates" in data:
                for fecha_str, rates in data["rates"].items():
                    if "EUR" in rates:
                        _cache_divisas[fecha_str] = Decimal(str(rates["EUR"]))
                _historial_cargado = True
                print("  [OK] Historial de divisas cargado.")
    except Exception as e:
        print(f"  [WARN] Fallo al descargar tipos de cambio. Usando tasa de contingencia: {e}")
        # FALLBACK: Si no hay internet, cargamos una tasa fija de seguridad para 2020-2025
        # para que el cálculo no se detenga.
        _cache_divisas["fallback"] = Decimal("0.92")
        _historial_cargado = True


def get_eur_per_usd(target_date: datetime) -> Decimal:
    """
    Obtiene el tipo de cambio oficial consultando la caché local (Descarga Masiva).
    Si no hay datos (fin de semana), retrocede localmente hasta encontrar un día hábil.
    """
    # 1. Carga inicial si el buzón está vacío
    if not _historial_cargado:
        cargar_historial_completo()

    d = target_date.date()

    # Intentar hasta 7 días atrás (retroceso local instantáneo)
    for offset in range(8):
        check = d - timedelta(days=offset)
        check_str = str(check)

        if check_str in _cache_divisas:
            return _cache_divisas[check_str]

    if "fallback" in _cache_divisas:
        return _cache_divisas["fallback"]

    # Si llegamos aquí, es que la fecha es anterior a 2020 o algo falló gravemente
    fecha_bonita = d.strftime("%d/%m/%Y")
    raise ValueError(
        f"Error: No existen datos oficiales de cambio para la fecha {fecha_bonita} en la base de datos local. "
        "Asegúrate de que la fecha es posterior a 2020."
    )


def usd_to_eur(usd_amount: Decimal, date_obj: datetime) -> Decimal:
    """
    RECEPTOR PROTEGIDO: Convierte automáticamente la entrada a Decimal
    para evitar colisiones de tipo con el rate del BCE.
    """
    # Convertidor de emergencia para entradas float
    clean_amount = Decimal(str(usd_amount)) if not isinstance(usd_amount, Decimal) else usd_amount

    rate = get_eur_per_usd(date_obj)
    return clean_amount * rate


class MarketPriceOracle:
    """Oráculo de precios para activos cripto cuando no hay valor fiat en el CSV."""

    def __init__(self, cache_file: str = "price_cache.json"):
        self.cache_file = cache_file
        self.cache = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    data = json.load(f)
                    for key, val in data.items():
                        asset, date = key.split("|")
                        self.cache[(asset, date)] = Decimal(str(val))
            except:
                pass

    def _save_cache(self):
        try:
            data = {f"{k[0]}|{k[1]}": str(v) for k, v in self.cache.items()}
            with open(self.cache_file, "w") as f:
                json.dump(data, f)
        except:
            pass

    def preload_batch(self, datasets: set[tuple[str, datetime]]):
        """Descarga masiva vectorizada con paginación activa y triangulación USDT."""
        import time
        from datetime import timezone

        fiat_stables = {"EUR", "USD", "USDT", "USDC", "BUSD", "FDUSD", "DAI"}
        asset_ranges = {}
        for asset, dt in datasets:
            if asset in fiat_stables: continue
            
            ts_ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
            if asset not in asset_ranges:
                asset_ranges[asset] = {"min": ts_ms, "max": ts_ms}
            else:
                asset_ranges[asset]["min"] = min(asset_ranges[asset]["min"], ts_ms)
                asset_ranges[asset]["max"] = max(asset_ranges[asset]["max"], ts_ms)

        failed_assets = set()
        headers = {"User-Agent": "Mozilla/5.0"}

        for asset, ranges in asset_ranges.items():
            min_ts = ranges["min"]
            max_ts = ranges["max"]
            
            # Intentar par directo EUR, si no, USDT
            symbol = f"{asset.upper()}EUR"
            usdt_fallback = False
            
            # Verificación rápida del par
            try:
                url_check = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit=1"
                req = urllib.request.Request(url_check, headers=headers)
                urllib.request.urlopen(req, timeout=5)
            except:
                symbol = f"{asset.upper()}USDT"
                usdt_fallback = True
                try:
                    url_check = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit=1"
                    req = urllib.request.Request(url_check, headers=headers)
                    urllib.request.urlopen(req, timeout=5)
                except:
                    failed_assets.add(asset)
                    continue

            # Paginación Activa
            current_start = min_ts
            # Binance devuelve hasta 1000 velas (casi 3 años)
            while current_start <= max_ts:
                url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&startTime={current_start}&limit=1000"
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read())
                        if not data:
                            break
                        
                        for kline in data:
                            k_time = kline[0]
                            k_close = Decimal(str(kline[4]))
                            dt_obj = datetime.fromtimestamp(k_time / 1000.0, tz=timezone.utc)
                            date_str = dt_obj.strftime("%Y-%m-%d")
                            
                            if usdt_fallback:
                                eur_per_usd = get_eur_per_usd(dt_obj)
                                price_eur = k_close * eur_per_usd
                            else:
                                price_eur = k_close
                                
                            self.cache[(asset.upper(), date_str)] = price_eur
                            current_start = kline[6] + 1 # closeTime + 1ms para la siguiente vela
                        
                        if len(data) < 1000:
                            break # No hay más datos futuros
                        
                        time.sleep(0.5) # Respetar API weights entre páginas
                except Exception as e:
                    failed_assets.add(asset)
                    break
                    
        self._save_cache()
        if failed_assets:
            self._preload_batch_cryptocompare(failed_assets, asset_ranges)

    def _preload_batch_cryptocompare(self, assets: set[str], ranges: dict):
        """Fallback para ICOs y activos delistados usando min-api."""
        import time
        from datetime import timezone
        headers = {"User-Agent": "Mozilla/5.0"}
        
        for asset in assets:
            max_ts = ranges[asset]["max"]
            min_ts = ranges[asset]["min"]
            
            # CryptoCompare requiere TS en segundos, iteramos día a día (ineficiente pero robusto)
            current_ts = int(min_ts / 1000)
            end_ts = int(max_ts / 1000)
            
            # Para evitar 429 masivos, limitamos el fallback
            step_days = 1
            max_days = 100
            days = 0
            while current_ts <= end_ts and days < max_days:
                try:
                    url = f"https://min-api.cryptocompare.com/data/pricehistorical?fsym={asset.upper()}&tsyms=EUR&ts={current_ts}"
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read())
                        if asset.upper() in data:
                            price_cc = Decimal(str(data[asset.upper()]["EUR"]))
                            dt_obj = datetime.fromtimestamp(current_ts, tz=timezone.utc)
                            date_str = dt_obj.strftime("%Y-%m-%d")
                            self.cache[(asset.upper(), date_str)] = price_cc
                except:
                    pass
                current_ts += 86400
                days += 1
                time.sleep(0.1)
                
        self._save_cache()

    def get_price_eur(self, asset: str, date_obj: datetime) -> Optional[Decimal]:
        """
        Devuelve el precio en EUR del activo en la fecha dada.
        Si es una stablecoin, usa el tipo de cambio oficial USD/EUR del BCE.
        """
        asset = asset.upper().strip()
        date_str = date_obj.strftime("%Y-%m-%d")

        # 1. Identidad EUR
        if asset == "EUR":
            return Decimal("1.0")

        # 2. Stablecoins (Dinero digital vinculado al USD)
        if asset in {"USDT", "USDC", "BUSD", "FDUSD", "DAI"}:
            try:
                # Obtenemos el valor de 1 USD en EUR para esa fecha
                return get_eur_per_usd(date_obj)
            except:
                return None

        # 3. Caché de activos volátiles
        if (asset, date_str) in self.cache:
            return self.cache[(asset, date_str)]

        # 4. Fallo: Consultar API Externa (CryptoCompare) como último recurso para comisiones
        try:
            return self._fetch_external_price(asset, date_obj)
        except:
            return None

    def _fetch_external_price(self, asset: str, date_obj: datetime) -> Optional[Decimal]:
        """Consulta el precio histórico directamente en la API de Binance (Klines)."""
        from datetime import timezone

        if date_obj.tzinfo is None:
            date_obj = date_obj.replace(tzinfo=timezone.utc)

        # Binance usa milisegundos y el par contra EUR (BTCEUR, ETHEUR, etc.)
        ts_ms = int(date_obj.timestamp() * 1000)
        symbol = f"{asset.upper()}EUR"
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&startTime={ts_ms}&limit=1"

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                # Estructura Binance: [[timestamp, open, high, low, close, ...]]
                if data and len(data) > 0:
                    price = Decimal(str(data[0][4]))  # El cierre es el índice 4
                    date_str = date_obj.strftime("%Y-%m-%d")
                    self.cache[(asset.upper(), date_str)] = price
                    print(f"  [Binance API] Precio {asset} recuperado: {price} €")
                    return price
        except Exception:
            # Reintento robusto contra USDT si EUR falla
            try:
                symbol_usdt = f"{asset.upper()}USDT"
                url_usdt = (
                    f"https://api.binance.com/api/v3/klines?symbol={symbol_usdt}&interval=1d&startTime={ts_ms}&limit=1"
                )
                req = urllib.request.Request(url_usdt, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    if data and len(data) > 0:
                        price_usdt = Decimal(str(data[0][4]))
                        # Convertir USDT a EUR usando el cambio del día
                        eur_per_usd = get_eur_per_usd(date_obj)
                        price_eur = price_usdt * eur_per_usd
                        print(f"  [Binance API] Precio {asset} recuperado via USDT: {price_eur:.2f} €")
                        return price_eur
            except:
                pass

            # 3. ÚLTIMO RECURSO: CryptoCompare (Muy robusto para históricos)
            try:
                url_cc = f"https://min-api.cryptocompare.com/data/pricehistorical?fsym={asset.upper()}&tsyms=EUR&ts={int(date_obj.timestamp())}"
                req_cc = urllib.request.Request(url_cc, headers=headers)
                with urllib.request.urlopen(req_cc, timeout=5) as resp:
                    data_cc = json.loads(resp.read())
                    if asset.upper() in data_cc:
                        price_cc = Decimal(str(data_cc[asset.upper()]["EUR"]))
                        print(f"  [CryptoCompare] Precio {asset} recuperado: {price_cc} €")
                        return price_cc
            except:
                pass

            print(
                f"  [!] ERROR CRÍTICO: Ninguna fuente (Binance/CryptoCompare) tiene datos para {asset} el {date_obj.strftime('%Y-%m-%d')}."
            )
            return None

        # Guardar cada vez que recuperamos un precio nuevo
        self._save_cache()
        return None
        return None


# Instancia global
oracle = MarketPriceOracle()


def eur_to_eur(amount: Decimal, _date: datetime) -> Decimal:
    """Identidad: ya está en EUR."""
    return amount
