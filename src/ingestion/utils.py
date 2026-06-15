from decimal import Decimal
import math
from datetime import datetime


def to_dec(val) -> Decimal:
    """
    Conversor Universal: Limpia basura de Pandas (NaN), strings con comas europeas
    y fuerza la conversión a Decimal mediante string para evitar errores de precisión float.
    """
    if isinstance(val, Decimal):
        return val

    # Caza nulos, vacíos y NaNs de Pandas
    if val is None or val == "" or (isinstance(val, float) and math.isnan(val)):
        return Decimal("0")

    # Manejo de strings: Limpieza de comas y espacios
    if isinstance(val, str):
        val = val.strip().replace(",", ".")
        if val == "" or val == "-":
            return Decimal("0")

    try:
        # Fuerzas string para evitar el error de precisión flotante
        return Decimal(str(val).replace(",", "."))
    except:
        return Decimal("0")


def clean_decimal(val) -> Decimal:
    """Alias para compatibilidad con lectores existentes."""
    return to_dec(val)


def parse_date(val) -> datetime:
    """Parseo robusto de fechas heterogéneas."""
    if isinstance(val, datetime):
        return val
    s = str(val).strip()
    # Formatos comunes: 2024-01-01 12:00:00 o 01/01/2024
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except:
            continue
    return datetime(1900, 1, 1)


def fuzzy_match(cols, patterns, mandatory=True) -> str:
    """Busca una columna que coincida con patrones fuzzy."""
    for p in patterns:
        for c in cols:
            if p.lower() in str(c).lower():
                return c
    if mandatory:
        raise ValueError(f"No se encontró ninguna columna que coincida con {patterns}")
    return None
