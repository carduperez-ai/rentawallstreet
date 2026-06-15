import re
import json


class AEATParser:
    def __init__(self):
        # Expresiones regulares para la prueba de concepto
        self.regex_sueldo = re.compile(r"sueldo íntegro ([\d\.]+) euros", re.I)
        self.regex_retenciones = re.compile(r"retenciones practicadas ascienden a ([\d\.]+) euros", re.I)
        self.regex_ss = re.compile(r"Seguridad Social son ([\d\.]+) euros", re.I)
        self.regex_base = re.compile(r"Base imponible general: ([\d\.]+,\d{2}) euros", re.I)
        self.regex_cuota = re.compile(r"Cuota íntegra estatal: ([\d\.]+,\d{2}) euros", re.I)

    def parse_number(self, num_str: str) -> float:
        """Convierte formato español '30.000,00' a float 30000.00"""
        if not num_str:
            return 0.0
        return float(num_str.replace(".", "").replace(",", "."))

    def parse_case(self, case_id: str, supuesto: str, solucion: str) -> dict:
        """Estructura el texto en el formato del Golden Master."""

        # Extracción de Input
        sueldo_match = self.regex_sueldo.search(supuesto)
        retenciones_match = self.regex_retenciones.search(supuesto)
        ss_match = self.regex_ss.search(supuesto)

        # Extracción de Resultados
        base_match = self.regex_base.search(solucion)
        cuota_match = self.regex_cuota.search(solucion)

        return {
            "name": f"AEAT_CASO_{case_id}",
            "category": "Extracción Automática",
            "input": {
                "fiscal_year": "2025",
                "region": "andalucia",  # Simplificado para PoC
                "age": "30",
                "marital_status": "single",
                "salary": self.parse_number(sueldo_match.group(1)) if sueldo_match else 0.0,
                "social_security": self.parse_number(ss_match.group(1)) if ss_match else 0.0,
                "withholdings": self.parse_number(retenciones_match.group(1)) if retenciones_match else 0.0,
            },
            "expected_results": {
                "base_imponible_general": self.parse_number(base_match.group(1)) if base_match else 0.0,
                "base_imponible_ahorro": 0.0,
                "cuota_integra_estatal": self.parse_number(cuota_match.group(1)) if cuota_match else 0.0,
                "cuota_integra_autonomica": 0.0,
                "resultado_declaracion": 0.0,
            },
        }


if __name__ == "__main__":
    parser = AEATParser()
    supuesto = "Ha percibido en concepto de sueldo íntegro 30.000 euros. Las retenciones practicadas ascienden a 4.500 euros. Sus gastos de Seguridad Social son 1.905 euros."
    solucion = "Base imponible general: 23.595,00 euros. Cuota íntegra estatal: 2.800,00 euros."
    print(json.dumps(parser.parse_case("TEST", supuesto, solucion), indent=2, ensure_ascii=False))
