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

        ingestor = EToroIngestor()
        ingestor.process_file(file_path)
        trades, divs = ingestor.transactions, ingestor.dividends
        if not trades:
            raise RuntimeError(f"DEBUG NO TRADES. Path: {file_path}. Warnings: {ingestor.warnings}.")
        return trades, divs
