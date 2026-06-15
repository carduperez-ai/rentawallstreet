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

        ingestor = CoinbaseIngestor()
        ingestor.process_file(file_path)
        trades, divs = ingestor.transactions, ingestor.dividends
        if not trades:
            raise RuntimeError(f"DEBUG NO TRADES. Path: {file_path}. Warnings: {ingestor.warnings}.")
        return trades, divs
