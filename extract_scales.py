import re

with open("c:/rentawallstreet/restored_consts_utf8.txt", "r", encoding="utf-8") as f:
    text = f.read()

blocks = text.split("===")
for i in range(1, len(blocks) - 1, 2):
    filename_block = blocks[i]
    content_block = blocks[i + 1]

    if "scale.cpython" in filename_block:
        m = re.search(r"regions[\\/](.*?)[\\/]__pycache__", filename_block)
        if not m:
            continue
        region = m.group(1)

        if "get_general_scale" in content_block:
            print(f"Region: {region} HAS GET_GENERAL_SCALE")
            # find all Decimal-like strings in the get_general_scale part
            # It's tricky to isolate just get_general_scale, let's just dump it to a file
            with open(f"c:/rentawallstreet/scale_{region}.txt", "w", encoding="utf-8") as out:
                out.write(content_block)
        else:
            print(f"Region: {region} DOES NOT HAVE GET_GENERAL_SCALE")
