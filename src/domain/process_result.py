from dataclasses import dataclass, field
from typing import List

from src.domain.base_tax_event import BaseTaxEvent


@dataclass
class ProcessResult:
    """Resultado de procesar un conjunto de archivos fiscales.

    is_complete indica si todos los elementos fueron clasificados y calculados.
    Cuando es False, el informe generado es parcial y debe advertirse al usuario
    antes de usarlo en una declaración.
    """

    crypto_tax_events: List[BaseTaxEvent] = field(default_factory=list)
    stock_tax_events: List[BaseTaxEvent] = field(default_factory=list)
    excluded_cfds: int = 0
    excluded_unknown: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.excluded_cfds == 0 and self.excluded_unknown == 0

    @property
    def all_tax_events(self) -> List[BaseTaxEvent]:
        return self.crypto_tax_events + self.stock_tax_events
