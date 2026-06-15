import os
import re


def reconstruct_scale(region_name):
    txt_file = f"c:/rentawallstreet/scale_{region_name}.txt"
    if not os.path.exists(txt_file):
        print(f"Skipping {region_name}, no txt file")
        return

    with open(txt_file, "r", encoding="utf-8") as f:
        text = f.read()

    # We need to extract the constants for get_general_scale
    # The text is the pprint of the __pycache__ consts.

    # Let's extract the list of tuples for get_general_scale
    # Search for: 'get_general_scale', 'consts': [None, '12450', '0.09', ... ]
    gen_scale_match = re.search(r"'get_general_scale',\s*'consts':\s*\[None,\s*(.*?)\]", text, re.DOTALL)

    gen_scale_tuples = []
    if gen_scale_match:
        items = re.findall(r"'([\d\.]+)'|'Infinity'", gen_scale_match.group(1))
        # Handle Infinity
        items = ["Infinity" if x == "" else x for x in items]

        # Pairs
        for i in range(0, len(items), 2):
            if i + 1 < len(items):
                gen_scale_tuples.append((items[i], items[i + 1]))

    # get_personal_minimum
    pm_match = re.search(r"'get_personal_minimum',\s*'consts':\s*\[None,\s*'([\d\.]+)'\]", text)
    pm_val = pm_match.group(1) if pm_match else None

    # get_age_supplements
    age_match = re.search(r"'get_age_supplements',\s*'consts':\s*\[None,\s*'([\d\.]+)',\s*'([\d\.]+)'\]", text)
    age_vals = (age_match.group(1), age_match.group(2)) if age_match else None

    # get_savings_scale (if exists)
    sav_scale_match = re.search(r"'get_savings_scale',\s*'consts':\s*\[None,\s*(.*?)\]", text, re.DOTALL)
    sav_scale_tuples = []
    if sav_scale_match:
        items = re.findall(r"'([\d\.]+)'|'Infinity'", sav_scale_match.group(1))
        items = ["Infinity" if x == "" else x for x in items]
        for i in range(0, len(items), 2):
            if i + 1 < len(items):
                sav_scale_tuples.append((items[i], items[i + 1]))

    # Now write the scale.py
    class_name = ""
    for b in text.splitlines():
        m = re.search(r"'code': '(\w+Region)'", b)
        if m:
            class_name = m.group(1)
            break

    if not class_name:
        class_name = region_name.capitalize() + "Region"

    code = "from decimal import Decimal\nfrom typing import List, Tuple\nfrom src.tax_compliance.regions.base import BaseRegion\n\n"
    code += f"class {class_name}(BaseRegion):\n"

    if gen_scale_tuples:
        code += "    @staticmethod\n"
        code += "    def get_general_scale() -> List[Tuple[Decimal, Decimal]]:\n"
        code += "        return [\n"
        for limit, rate in gen_scale_tuples:
            if limit == "Infinity":
                code += f"            (Decimal('Infinity'), Decimal('{rate}')),\n"
            else:
                code += f"            (Decimal('{limit}'), Decimal('{rate}')),\n"
        code += "        ]\n\n"

    if sav_scale_tuples:
        code += "    @staticmethod\n"
        code += "    def get_savings_scale() -> List[Tuple[Decimal, Decimal]]:\n"
        code += "        return [\n"
        for limit, rate in sav_scale_tuples:
            if limit == "Infinity":
                code += f"            (Decimal('Infinity'), Decimal('{rate}')),\n"
            else:
                code += f"            (Decimal('{limit}'), Decimal('{rate}')),\n"
        code += "        ]\n\n"

    if pm_val:
        code += "    @staticmethod\n"
        code += "    def get_personal_minimum() -> Decimal:\n"
        code += f"        return Decimal('{pm_val}')\n\n"

    if age_vals:
        code += "    @staticmethod\n"
        code += "    def get_age_supplements() -> Tuple[Decimal, Decimal]:\n"
        code += f"        return Decimal('{age_vals[0]}'), Decimal('{age_vals[1]}')\n\n"

    # Write to file
    out_path = f"c:/rentawallstreet/src/tax_compliance/regions/{region_name}/scale.py"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Reconstructed {region_name} scale.py!")


regions = [
    "asturias",
    "baleares",
    "canarias",
    "cantabria",
    "castilla_la_mancha",
    "castilla_leon",
    "cataluna",
    "ceuta",
    "extremadura",
    "galicia",
    "la_rioja",
    "madrid",
    "melilla",
    "murcia",
    "valenciana",
]
for r in regions:
    reconstruct_scale(r)
