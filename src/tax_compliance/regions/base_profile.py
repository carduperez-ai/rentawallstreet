from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Tuple, Dict
from src.domain.fiscal_entities import TaxpayerProfile


class RegionalFiscalProfileBase(ABC):
    @abstractmethod
    def get_general_scale(self) -> List[Tuple[Decimal, Decimal]]: ...
    @abstractmethod
    def get_savings_scale(self) -> List[Tuple[Decimal, Decimal]]: ...
    @abstractmethod
    def get_personal_minimum(self) -> Decimal: ...
    @abstractmethod
    def get_age_supplements(self) -> Tuple[Decimal, Decimal]: ...
    @abstractmethod
    def get_descendants_brackets(self) -> List[Decimal]: ...
    @abstractmethod
    def get_descendants_under3(self) -> Decimal: ...
    @abstractmethod
    def get_disability_limits(self) -> Tuple[Decimal, Decimal, Decimal]: ...
    @abstractmethod
    def calculate_deductions(
        self, profile: TaxpayerProfile, base_general: Decimal, base_ahorro: Decimal
    ) -> Dict[str, Decimal]: ...

    def get_descendants_minimums(self) -> List[Decimal]:
        return [Decimal("2400"), Decimal("2700"), Decimal("4000"), Decimal("4500")]

    def get_ascendants_minimums(self) -> Tuple[Decimal, Decimal]:
        return Decimal("1150"), Decimal("1400")

    def get_disability_minimums(self) -> Dict[str, Decimal]:
        return {
            "grade_33": Decimal("3000"),
            "grade_65": Decimal("9000"),
            "needs_help": Decimal("3000"),
            "asc_grade_33": Decimal(
                "3000"
            ),  # Art. 59 — discapacidad ascendientes (puede diferir del de descendientes en CCAA)
        }

    def get_under3_supplement(self) -> Decimal:
        """Art. 58.2 LIRPF — Suplemento por hijo menor de 3 años. Valor estatal: 2.800€.
        Las CCAA con deflactación autonómica deben sobrescribir este método."""
        return Decimal("2800")
