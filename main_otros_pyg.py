from typing import List
from src.domain.fiscal_entities import OtherIncome

class OtherGainsSpecialist:
    """
    Especialista en Otras Ganancias y Pérdidas Patrimoniales.
    Venta de inmuebles, subvenciones, premios, etc.
    """
    
    @staticmethod
    def process_manual_data(data: list) -> List[OtherIncome]:
        results = []
        for d in data:
            results.append(OtherIncome(
                date=d.get('date'),
                description=d.get('description', 'Otros'),
                gain_loss_eur=d.get('gain_loss_eur', 0),
                category=d.get('category', 'otros'),
                notes=d.get('notes', "")
            ))
        return results
