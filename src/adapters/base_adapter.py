"""
src/adapters/base_adapter.py

Contrato base para todos los adaptadores de plataforma.
Implementa el principio Open/Closed: para añadir una nueva plataforma
se crea un archivo nuevo heredando de BaseAdapter, sin tocar el UniversalReader.
"""

from abc import ABC, abstractmethod
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ingestion.file_classifier import FileMetadata


class BaseAdapter(ABC):
    """
    Interfaz que todos los adaptadores de plataforma deben implementar.

    Reglas del contrato:
    1. `platform_id` debe coincidir exactamente con la clave que devuelve
       `FileClassifier.classify().platform` (ej. "BINANCE", "DEGIRO").
    2. `can_handle()` NO reimplementa fingerprinting: delega en el FileClassifier.
    3. `extract()` retorna DTOs de dominio ya construidos (Trade/Dividend).
       Nunca retorna dicts crudos ni delega la construcción al Gateway.
    4. Los adaptadores que envuelvan clases con estado (Ingestors) deben
       instanciar una nueva instancia fresca por cada llamada a `extract()`.
    """

    #: Identificador de plataforma. Debe coincidir (case-insensitive)
    #: con FileClassifier.classify().platform.
    platform_id: str

    #: Tipo de flujo de datos que produce el adaptador.
    #: Debe ser 'crypto' o 'stock'.
    stream_type: str

    def can_handle(self, metadata: "FileMetadata") -> bool:
        """
        Identificación pasiva: compara el platform_id declarado con el
        resultado del FileClassifier. No lee el archivo ni reimplementa
        heurísticas de fingerprinting.
        """
        return metadata.platform.upper() == self.platform_id.upper()

    @abstractmethod
    def extract(self, file_path: str) -> Tuple[list, list]:
        """
        Extrae y retorna (trades, dividends) como listas de DTOs de dominio.

        Args:
            file_path: Ruta absoluta al archivo a procesar.

        Returns:
            Tuple[List[Trade], List[Dividend]] — entidades de dominio construidas.

        Raises:
            No debe propagar excepciones de I/O. Los errores deben loguearse
            y retornar ([], []) para que el Gateway active el fallback.
        """
