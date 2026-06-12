from typing import List
from src.domain.fiscal_entities import RentalIncome

class RealEstateSpecialist:
    """
    Especialista en Bienes Inmuebles.
    Gestiona ingresos por alquileres (Casilla 0091).
    """
    
    @staticmethod
    def process_manual_data(data: list) -> List[RentalIncome]:
        """
        Convierte datos manuales de la web en objetos RentalIncome.
        """
        results = []
        for d in data:
            results.append(RentalIncome(
                property_id=d.get('property_id', 'Inmueble'),
                gross_income=d.get('gross_income', 0),
                deductible_expenses=d.get('deductible_expenses', 0),
                reduction_habitual=d.get('reduction_habitual', True),
                notes=d.get('notes', "")
            ))
        return results
