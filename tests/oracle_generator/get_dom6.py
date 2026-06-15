from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?TACCESO=COLAB&EJER=2025")
    page.wait_for_load_state("networkidle")

    page.locator("button:has-text('Nueva declaración')").first.click()
    page.wait_for_timeout(2000)

    # NIF y Apellidos
    page.locator("input[title='NIF:']:visible").first.fill("87654321X")
    page.locator("input[title='Apellidos y nombre:']:visible").first.fill("PRUEBA TEST")
    page.wait_for_timeout(500)

    # Estado Civil - ArrowDown strategy
    ec = page.locator("xpath=//span[contains(text(), 'Estado Civil')]/following::input[1]")
    ec.focus()
    page.wait_for_timeout(500)
    ec.press("ArrowDown")
    page.wait_for_timeout(500)
    ec.press("ArrowDown")
    page.wait_for_timeout(500)
    ec.press("Enter")

    # Fecha de nacimiento
    page.locator("xpath=//span[contains(text(), 'Fecha de nacimiento')]/following::input[1]").fill("01/01/1980")

    # Sexo
    page.locator("xpath=//label[contains(text(), 'Hombre')]").click()

    # Comunidad Autonoma
    ca = page.locator("xpath=//span[contains(text(), 'Comunidad Autónoma')]/following::input[1]")
    ca.focus()
    page.wait_for_timeout(500)
    ca.press("ArrowDown")
    page.wait_for_timeout(500)
    ca.press("ArrowDown")  # Selecciona la primera o segunda
    page.wait_for_timeout(500)
    ca.press("Enter")

    page.locator("button:has-text('Aceptar')").first.click()

    try:
        page.wait_for_selector("button[title='Apartados declaración']", timeout=10000)
        print("SUCCESS! Llego a la siguiente pantalla.")
    except Exception as e:
        print(f"FAILED: {e}")

    browser.close()
