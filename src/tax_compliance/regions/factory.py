from src.tax_compliance.regions.base_profile import RegionalFiscalProfileBase
from src.tax_compliance.regions.andalucia.facade import AndaluciaFiscalProfile
from src.tax_compliance.regions.aragon.facade import AragonFiscalProfile
from src.tax_compliance.regions.asturias.facade import AsturiasFiscalProfile
from src.tax_compliance.regions.baleares.facade import BalearesFiscalProfile
from src.tax_compliance.regions.canarias.facade import CanariasFiscalProfile
from src.tax_compliance.regions.cantabria.facade import CantabriaFiscalProfile
from src.tax_compliance.regions.castilla_la_mancha.facade import Castilla_la_manchaFiscalProfile
from src.tax_compliance.regions.castilla_leon.facade import Castilla_leonFiscalProfile
from src.tax_compliance.regions.cataluna.facade import CatalunaFiscalProfile
from src.tax_compliance.regions.extremadura.facade import ExtremaduraFiscalProfile
from src.tax_compliance.regions.galicia.facade import GaliciaFiscalProfile
from src.tax_compliance.regions.madrid.facade import MadridFiscalProfile
from src.tax_compliance.regions.murcia.facade import MurciaFiscalProfile
from src.tax_compliance.regions.la_rioja.facade import La_riojaFiscalProfile
from src.tax_compliance.regions.valenciana.facade import ValencianaFiscalProfile
from src.tax_compliance.regions.ceuta.facade import CeutaFiscalProfile
from src.tax_compliance.regions.melilla.facade import MelillaFiscalProfile


class RegionalContextFactory:
    _MAP = {
        "andalucia": AndaluciaFiscalProfile,
        "aragon": AragonFiscalProfile,
        "asturias": AsturiasFiscalProfile,
        "baleares": BalearesFiscalProfile,
        "canarias": CanariasFiscalProfile,
        "cantabria": CantabriaFiscalProfile,
        "castilla_la_mancha": Castilla_la_manchaFiscalProfile,
        "castilla_leon": Castilla_leonFiscalProfile,
        "cataluna": CatalunaFiscalProfile,
        "extremadura": ExtremaduraFiscalProfile,
        "galicia": GaliciaFiscalProfile,
        "madrid": MadridFiscalProfile,
        "murcia": MurciaFiscalProfile,
        "la_rioja": La_riojaFiscalProfile,
        "valenciana": ValencianaFiscalProfile,
        "ceuta": CeutaFiscalProfile,
        "melilla": MelillaFiscalProfile,
    }

    @staticmethod
    def get_context(region: str) -> RegionalFiscalProfileBase:
        return RegionalContextFactory._MAP.get(region.lower(), RegionalContextFactory._MAP["andalucia"])()
