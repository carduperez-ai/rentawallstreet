"""
src/adapters/revolut_adapter.py
"""

import logging
from typing import Tuple

from src.adapters.base_adapter import BaseAdapter
from src.ingestion import revolut_reader

logger = logging.getLogger(__name__)


class RevolutAdapter(BaseAdapter):
    """
    Adaptador para Revolut Trading CSV.

    revolut_reader.parse() es función pura — acepta una ruta individual (str).
    """

    platform_id = "REVOLUT"
    stream_type = "crypto"

    def extract(self, file_path: str) -> Tuple[list, list]:
        try:
            return revolut_reader.parse(file_path)
        except Exception as exc:
            logger.error("RevolutAdapter.extract falló para %s: %s", file_path, exc)
            return [], []
