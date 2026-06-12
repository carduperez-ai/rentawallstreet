# src/tax_compliance/regions/base.py
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.fiscal_entities import TaxpayerProfile, Deduction

BracketList = List[Tuple[Decimal, Decimal]]

SAVINGS_BRACKETS_ESTATAL: BracketList = [
    (Decimal('6000'),     Decimal('0.095')),
    (Decimal('44000'),    Decimal('0.105')),
    (Decimal('150000'),   Decimal('0.115')),
    (Decimal('100000'),   Decimal('0.135')),
    (Decimal('Infinity'), Decimal('0.15')),
]

# Importe estatal base (Arts. 57-59 LIRPF) — usado cuando CCAA no tiene propios
MINIMO_PERSONAL_ESTATAL = Decimal('5550')
SUP_65_ESTATAL = Decimal('1150')
SUP_75_ESTATAL = Decimal('1400')


class BaseRegion(ABC):
    """Interfaz abstracta para cada CCAA."""

    @staticmethod
    @abstractmethod
    def get_general_scale() -> BracketList: ...

    @staticmethod
    def get_savings_scale() -> BracketList:
        return SAVINGS_BRACKETS_ESTATAL

    @staticmethod
    def get_personal_minimum() -> Decimal:
        return MINIMO_PERSONAL_ESTATAL

    @staticmethod
    def get_age_supplements() -> Tuple[Decimal, Decimal]:
        """Devuelve (sup_65, sup_75_adicional)."""
        return SUP_65_ESTATAL, SUP_75_ESTATAL

    @classmethod
    def get_quota_deductions(
        cls,
        profile: 'TaxpayerProfile',
        base_imponible_general: Decimal,
        base_imponible_ahorro: Decimal,
        cuota_integra_autonomica: Decimal,
    ) -> List['Deduction']:
        return []
