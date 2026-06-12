"""
src/adapters/degiro_adapter.py
"""
import logging
from typing import Tuple, List

from src.adapters.base_adapter import BaseAdapter
from src.ingestion import degiro_reader

logger = logging.getLogger(__name__)


class DeGiroAdapter(BaseAdapter):
    """
    Adaptador para archivos de DeGiro (transactions.csv, account.csv, PDF).

    degiro_reader.parse() es una función pura sin estado acumulado.
    Se delega directamente envolviendo file_path en lista para compatibilidad.
    """

    platform_id = "DEGIRO"
    stream_type = "stock"

    def extract(self, file_path: str) -> Tuple[list, list]:
        try:
            return degiro_reader.parse([file_path])
        except Exception as exc:
            logger.error("DeGiroAdapter.extract falló para %s: %s", file_path, exc)
            return [], []
