"""
src/adapters/kucoin_adapter.py
"""

import logging
from typing import Tuple

from src.adapters.base_adapter import BaseAdapter
from src.ingestion.kucoin_reader import KuCoinIngestor

logger = logging.getLogger(__name__)


class KuCoinAdapter(BaseAdapter):
    """
    Adaptador para KuCoin CSV (Spot Trading y Funding History).

    KuCoinIngestor acumula _spot_rows / _funding_rows internamente.
    Instanciación fresca por llamada.
    """

    platform_id = "KUCOIN"
    stream_type = "crypto"

    def extract(self, file_path: str) -> Tuple[list, list]:
        try:
            ingestor = KuCoinIngestor()
            ingestor.process_file(file_path)
            return ingestor.transactions, ingestor.dividends
        except Exception as exc:
            logger.error("KuCoinAdapter.extract falló para %s: %s", file_path, exc)
            return [], []
