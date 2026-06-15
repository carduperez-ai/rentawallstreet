from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?TACCESO=COLAB&EJER=2025")
    page.wait_for_load_state("networkidle")

    page.locator("button:has-text('Nueva declaración')").first.click()
    page.wait_for_timeout(3000)

    page.locator("input[title='NIF:']").first.fill("12345678Z")
    page.locator("input[title='Apellidos y nombre:']").first.fill("PRUEBA TEST")
    page.locator("input[title='Apellidos y nombre:']").first.press("Tab")
    page.wait_for_timeout(1000)

    # Estado Civil
    page.locator("xpath=//span[contains(text(), 'Estado Civil')]/following::input[1]").fill("Soltero/a")
    page.locator("xpath=//span[contains(text(), 'Estado Civil')]/following::input[1]").press("Tab")

    # Fecha de nacimiento
    page.locator("xpath=//span[contains(text(), 'Fecha de nacimiento')]/following::input[1]").fill("01/01/1980")
    page.locator("xpath=//span[contains(text(), 'Fecha de nacimiento')]/following::input[1]").press("Tab")

    # Sexo
    page.locator("xpath=//label[contains(text(), 'Hombre')]").click()

    # Comunidad Autonoma
    page.locator("xpath=//span[contains(text(), 'Comunidad Autónoma')]/following::input[1]").fill("Andalucía")
    page.locator("xpath=//span[contains(text(), 'Comunidad Autónoma')]/following::input[1]").press("Tab")

    page.locator("button:has-text('Aceptar')").first.click()

    try:
        page.wait_for_selector("button[title='Apartados declaración']", timeout=10000)
        print("SUCCESS! Llego a la siguiente pantalla.")
    except Exception as e:
        print(f"FAILED: {e}")

    browser.close()
