"""
src/adapters/coinbase_adapter.py
"""

import logging
from typing import Tuple

from src.adapters.base_adapter import BaseAdapter
from src.ingestion.coinbase_reader import CoinbaseIngestor

logger = logging.getLogger(__name__)


class CoinbaseAdapter(BaseAdapter):
    """
    Adaptador para Coinbase Transaction History CSV.

    CoinbaseIngestor acumula _rows internamente.
    Instanciación fresca por llamada.
    """

    platform_id = "COINBASE"
    stream_type = "crypto"

    def extract(self, file_path: str) -> Tuple[list, list]:
        try:
            ingestor = CoinbaseIngestor()
            ingestor.process_file(file_path)
            return ingestor.transactions, ingestor.dividends
        except Exception as exc:
            logger.error("CoinbaseAdapter.extract falló para %s: %s", file_path, exc)
            return [], []
