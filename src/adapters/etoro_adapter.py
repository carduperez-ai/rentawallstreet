"""
src/adapters/etoro_adapter.py
"""
import logging
from typing import Tuple

from src.adapters.base_adapter import BaseAdapter
from src.ingestion.etoro_reader import EToroIngestor

logger = logging.getLogger(__name__)


class EToroAdapter(BaseAdapter):
    """
    Adaptador para eToro Account Statement Excel.

    EToroIngestor acumula _activity_rows / _positions_rows.
    Instanciación fresca por llamada.
    """

    platform_id = "ETORO"
    stream_type = "stock"

    def extract(self, file_path: str) -> Tuple[list, list]:
        try:
            ingestor = EToroIngestor()
            ingestor.process_file(file_path)
            return ingestor.transactions, ingestor.dividends
        except Exception as exc:
            logger.error("EToroAdapter.extract falló para %s: %s", file_path, exc)
            return [], []
