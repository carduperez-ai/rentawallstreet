"""
src/adapters/ibkr_adapter.py
"""

import logging
from typing import Tuple

from src.adapters.base_adapter import BaseAdapter
from src.ingestion.ibkr_reader import IBKRIngestor

logger = logging.getLogger(__name__)


class IBKRAdapter(BaseAdapter):
    """
    Adaptador para Interactive Brokers Flex Query (CSV/TXT).

    IBKRIngestor acumula _trade_rows / _cash_rows internamente.
    Instanciación fresca por llamada.
    """

    platform_id = "IBKR"
    stream_type = "stock"

    def extract(self, file_path: str) -> Tuple[list, list]:
        try:
            ingestor = IBKRIngestor()
            ingestor.process_file(file_path)
            return ingestor.transactions, ingestor.dividends
        except Exception as exc:
            logger.error("IBKRAdapter.extract falló para %s: %s", file_path, exc)
            return [], []
