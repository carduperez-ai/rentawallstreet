import os
import pandas as pd
from typing import Dict
from dataclasses import dataclass


@dataclass
class FileMetadata:
    platform: str
    extension: str
    content_type: str  # 'TRANSACTIONS', 'ACCOUNT', 'REPORT', 'UNKNOWN'
    is_supported: bool


class FileClassifier:
    """
    Clasificador avanzado de archivos fiscales.
    Detecta plataforma, extensión y tipo de contenido para despacho preciso.
    """

    PLATFORMS = {
        "BINANCE": [
            "User_Id",
            "Time",
            "Account",
            "Operation",
            "Coin",
            "Hora_UTC",
            "Operacion",
            "Moneda",
            "Market",
            "Pair",
            "Side",
            "Fee",
        ],
        "DEGIRO": ["Fecha", "Hora", "Producto", "ISIN", "Valor"],
        "TRADING212": ["Action", "Time", "ISIN", "Ticker", "No. of shares"],
        "REVOLUT": ["Type", "Product", "Started Date", "Completed Date"],
    }

    @classmethod
    def get_inventory(cls, folder_path: str, user_prefs: Dict[str, str]) -> Dict[str, "FileMetadata"]:
        """
        Escanea la carpeta de uploads y devuelve un inventario real de archivos clasificados.
        Sincroniza la realidad del disco con las preferencias del usuario.
        """
        if not os.path.exists(folder_path):
            return {}

        files = [f for f in os.listdir(folder_path) if not f.startswith("~$") and not f.startswith(".")]
        inventory = {}

        for f in files:
            path = os.path.join(folder_path, f)
            if os.path.isfile(path):
                inventory[f] = cls.classify(path, user_prefs.get(f, "auto"))

        return inventory

    @classmethod
    def classify(cls, file_path: str, user_pref: str = "auto") -> FileMetadata:
        filename = os.path.basename(file_path).upper()
        ext = os.path.splitext(file_path)[1].lower()

        # 1. Determinación de Plataforma
        platform = user_pref.upper() if user_pref and user_pref.lower() != "auto" else "UNKNOWN"

        if platform == "UNKNOWN":
            if "BINANCE" in filename:
                platform = "BINANCE"
            elif "DEGIRO" in filename:
                platform = "DEGIRO"
            elif (
                "TRADING212" in filename or "T212" in filename or ("TRADING" in filename and "BINANCE" not in filename)
            ):
                platform = "TRADING212"
            elif "REVOLUT" in filename:
                platform = "REVOLUT"
            elif "IBKR" in filename or "IB " in filename or "INTERACTIVE" in filename:
                platform = "IBKR"
            elif "ETORO" in filename:
                platform = "ETORO"
            elif "COINBASE" in filename:
                platform = "COINBASE"
            elif "KRAKEN" in filename:
                platform = "KRAKEN"
            elif "KUCOIN" in filename:
                platform = "KUCOIN"

        # 2. Determinación de Tipo de Contenido
        content_type = "DESCONOCIDO"
        if "ORDEN" in filename or "ORDER" in filename or "SPOT" in filename:
            content_type = "ÓRDENES SPOT"
        elif "TRANSACTION" in filename or "TRANSACCI" in filename or "OPERACI" in filename or "TRADE" in filename:
            content_type = "TRANSACCIONES"
        elif "ACCOUNT" in filename or "CUENTA" in filename or "ESTADO" in filename:
            content_type = "CUENTA"
        elif (
            "REPORT" in filename
            or "INFORME" in filename
            or "ANNUAL" in filename
            or "RESUMEN" in filename
            or "STATEMENT" in filename
        ):
            content_type = "INFORME FISCAL"

        # 3. Refinamiento por cabeceras si es CSV/Excel
        if platform == "UNKNOWN" and ext in (".csv", ".xlsx", ".xls"):
            try:
                if ext == ".xlsx" or ext == ".xls":
                    df = pd.read_excel(file_path, nrows=0)
                else:
                    df = pd.read_csv(file_path, sep=None, engine="python", nrows=0)

                headers = [str(c).strip() for c in df.columns]
                for p, signatures in cls.PLATFORMS.items():
                    matches = sum(1 for sig in signatures if any(sig.lower() in h.lower() for h in headers))
                    if matches >= 2:
                        platform = p
                        break
            except Exception:
                pass

        # 4. Validación de Soporte
        is_supported = platform != "UNKNOWN" and ext in (".csv", ".xlsx", ".xls", ".pdf")

        # 5. Fallback para Informes Fiscales de plataformas no listadas
        if platform == "UNKNOWN" and content_type == "INFORME FISCAL":
            platform = "GENERIC"
            is_supported = True

        return FileMetadata(platform=platform, extension=ext, content_type=content_type, is_supported=is_supported)
