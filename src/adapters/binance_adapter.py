"""
src/adapters/binance_adapter.py
"""

import logging
from typing import Tuple

from src.adapters.base_adapter import BaseAdapter
from src.ingestion.binance_reader import BinanceIngestor

logger = logging.getLogger(__name__)


class BinanceAdapter(BaseAdapter):
    """
    Adaptador para archivos de Binance (Spot History y Transaction History).

    BinanceIngestor acumula estado en spot_dfs / trans_dfs.
    Se instancia fresco en cada llamada a extract() para garantizar
    aislamiento total entre sesiones concurrentes.
    """

    platform_id = "BINANCE"
    stream_type = "crypto"

    def extract(self, file_path: str) -> Tuple[list, list]:
        try:
            ingestor = BinanceIngestor()
            ingestor.process_file(file_path)
            return ingestor.transactions, ingestor.dividends
        except Exception as exc:
            logger.error("BinanceAdapter.extract falló para %s: %s", file_path, exc)
            return [], []
