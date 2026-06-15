from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?TACCESO=COLAB&EJER=2025")
    page.wait_for_load_state("networkidle")

    page.locator("button:has-text('Nueva declaración')").first.click()
    page.wait_for_timeout(2000)

    inputs = page.locator("input")

    # NIF y Apellidos
    inputs.nth(1).fill("11111111H")
    inputs.nth(2).fill("PRUEBA TEST")
    page.wait_for_timeout(500)

    # Estado Civil (nth=3)
    ec = inputs.nth(3)
    ec.focus()
    page.wait_for_timeout(300)
    ec.press("ArrowDown")
    page.wait_for_timeout(300)
    ec.press("ArrowDown")  # Soltero
    page.wait_for_timeout(300)
    ec.press("Enter")

    # Fecha de nacimiento (nth=4)
    inputs.nth(4).fill("01/01/1980")

    # Sexo Hombre (nth=5)
    inputs.nth(5).check()

    # Comunidad Autonoma (nth=8)
    ca = inputs.nth(8)
    ca.focus()
    page.wait_for_timeout(300)
    ca.press("ArrowDown")
    page.wait_for_timeout(300)
    ca.press("ArrowDown")  # Andalucía
    page.wait_for_timeout(300)
    ca.press("Enter")

    page.locator("button:has-text('Aceptar')").first.click()

    try:
        page.wait_for_selector("button[title='Apartados declaración']", timeout=5000)
        print("SUCCESS! Llego a la siguiente pantalla.")
    except Exception as e:
        print(f"FAILED: {e}")
        # Print modal texts to see if it failed because of NIF or Estado civil
        modals = page.locator(".z-messagebox").all_inner_texts()
        print("Modals:", modals)

    browser.close()
