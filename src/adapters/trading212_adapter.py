"""
src/adapters/trading212_adapter.py
"""

import logging
from typing import Tuple

from src.adapters.base_adapter import BaseAdapter
from src.ingestion import trading212_reader

logger = logging.getLogger(__name__)


class Trading212Adapter(BaseAdapter):
    """
    Adaptador para Trading 212 (CSV y PDF).

    trading212_reader.parse() es función pura — acepta una ruta individual (str).
    """

    platform_id = "TRADING212"
    stream_type = "stock"

    def extract(self, file_path: str) -> Tuple[list, list]:
        try:
            return trading212_reader.parse(file_path)
        except Exception as exc:
            logger.error("Trading212Adapter.extract falló para %s: %s", file_path, exc)
            return [], []
