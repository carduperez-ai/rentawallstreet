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

        ingestor = IBKRIngestor()
        ingestor.process_file(file_path)
        trades, divs = ingestor.transactions, ingestor.dividends
        if not trades:
            raise RuntimeError(f"DEBUG NO TRADES. Path: {file_path}. Warnings: {ingestor.warnings}.")
        return trades, divs
