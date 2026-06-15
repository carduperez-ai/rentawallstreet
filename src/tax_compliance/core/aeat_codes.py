import re
import os


class AEATDictionary:
    def __init__(self, properties_path):
        self.mapping = {}  # technical_id -> {box_id, description}
        self.box_to_id = {}  # box_id -> technical_id
        if os.path.exists(properties_path):
            self.parse_file(properties_path)

    def parse_file(self, path):
        # El formato es: ID=[PATH][TYPE][BOX_ID][DESCRIPTION]
        # Ejemplo: G2B_A=[...][P102][0328][Importe global...]
        # También hay ID=[...][X][*79][Desc]
        pattern = re.compile(r"^([^=]+)=\[(.*?)\]\[(.*?)\]\[(\*?\d+)\]\[(.*?)\]")

        with open(path, "r", encoding="latin-1") as f:  # Suelen usar latin-1 por los acentos
            for line in f:
                match = pattern.match(line.strip())
                if match:
                    tech_id, path_aeat, type_aeat, box_id, description = match.groups()
                    # Limpiar el box_id si tiene asterisco (índices internos)
                    clean_box = box_id.replace("*", "")

                    self.mapping[tech_id] = {"box": clean_box, "description": description, "path": path_aeat}
                    self.box_to_id[clean_box] = tech_id

    def get_info(self, tech_id):
        return self.mapping.get(tech_id)

    def get_by_box(self, box_id):
        tech_id = self.box_to_id.get(box_id)
        if tech_id:
            return self.mapping.get(tech_id)
        return None


# Mapeo de nuestras variables internas a IDs técnicos de la AEAT 2025
VARIABLE_MAPPING = {
    "gross_income": "C01",  # Casilla [0001]
    "ss_employee": "C03",  # Casilla [0003]
    "withholdings_work": "RET1",  # Casilla [0596]
    "dividend_gross": "B13",  # Casilla [0029]
    "dividend_ret": "RET2",  # Casilla [0597]
    "stock_proceeds": "G2B_A",  # Casilla [0328] (Ventas)
    "stock_costs": "G2B_B",  # Casilla [0331] (Costes)
    "stock_gain": "G2B_C",  # Casilla [0332] (Resultado)
    "crypto_proceeds": "G2CRIITGP",  # Casilla [1801] (Proxy)
}

# Diccionario Global (Cargado en Runtime)
_instance = None


def get_dictionary():
    global _instance
    if _instance is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "diccionarioXSD_2025.properties.txt")
        _instance = AEATDictionary(path)
    return _instance
