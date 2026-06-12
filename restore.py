import glob
import marshal
import types
import os

def extract_consts(code):
    consts = []
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            consts.append({"code": const.co_name, "consts": extract_consts(const)})
        else:
            consts.append(const)
    return consts

for f in glob.glob('src/tax_compliance/regions/*/__pycache__/*.pyc'):
    with open(f, 'rb') as pyc_file:
        pyc_file.read(16)
        try:
            code = marshal.load(pyc_file)
            print(f"=== {f} ===")
            import pprint
            pprint.pprint(extract_consts(code))
        except Exception as e:
            print(f"Error parsing {f}: {e}")
