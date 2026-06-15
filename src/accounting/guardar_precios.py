import json
import os
from decimal import Decimal

CACHE_FILE = "price_cache.json"


def registrar_precio(asset, date_str, price):
    """
    Guarda un precio de forma atómica en el archivo price_cache.json.
    Asegura que el dato persista en disco inmediatamente.
    """
    asset = asset.upper().strip()
    cache = _leer_cache_completa()

    # Actualizar o insertar
    key = f"{asset}|{date_str}"
    cache[key] = str(price)

    # Escritura física
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=4)
        return True
    except Exception as e:
        print(f"  [!] ERROR CRÍTICO al escribir en disco: {e}")
        return False


def obtener_precio_guardado(asset, date_str):
    """
    Recupera un precio del archivo local. Retorna None si no existe.
    """
    asset = asset.upper().strip()
    cache = _leer_cache_completa()
    key = f"{asset}|{date_str}"

    val = cache.get(key)
    if val:
        return Decimal(str(val))
    return None


def _leer_cache_completa():
    """Lee el archivo JSON de disco y lo devuelve como diccionario."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}
