from typing import Tuple
from src.adapters.base_adapter import BaseAdapter
from src.ingestion.universal_reader import parse as parse_universal

class UniversalAdapter(BaseAdapter):
    platform_id = "UNKNOWN"
    stream_type = "crypto"

    def can_handle(self, metadata) -> bool:
        return metadata.platform.upper() in ('UNKNOWN', 'GENERIC')

    def extract(self, file_path: str) -> Tuple[list, list]:
        try:
            return parse_universal(file_path)
        except Exception:
            return [], []
