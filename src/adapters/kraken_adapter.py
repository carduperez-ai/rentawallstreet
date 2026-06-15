"""
src/adapters/kraken_adapter.py
"""

import logging
from typing import Tuple

from src.adapters.base_adapter import BaseAdapter
from src.ingestion.kraken_reader import KrakenIngestor

logger = logging.getLogger(__name__)


class KrakenAdapter(BaseAdapter):
    """
    Adaptador para Kraken Ledgers CSV.

    KrakenIngestor acumula _rows internamente.
    Instanciación fresca por llamada.
    """

    platform_id = "KRAKEN"
    stream_type = "crypto"

    def extract(self, file_path: str) -> Tuple[list, list]:

        ingestor = KrakenIngestor()
        ingestor.process_file(file_path)
        trades, divs = ingestor.transactions, ingestor.dividends
        if not trades:
            raise RuntimeError(f"DEBUG NO TRADES. Path: {file_path}. Warnings: {ingestor.warnings}.")
        return trades, divs
