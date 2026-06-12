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
    page.locator("input[title='Apellidos y nombre:']:visible").first.press("Tab")
    page.wait_for_timeout(1000)

    # Estado Civil (Click input -> Click list item)
    page.locator("xpath=//span[contains(text(), 'Estado Civil')]/following::input[1]").click()
    page.wait_for_timeout(500)
    page.locator("text='Soltero/a'").last.click() # last to avoid hitting the main text if any
    
    # Fecha de nacimiento
    page.locator("xpath=//span[contains(text(), 'Fecha de nacimiento')]/following::input[1]").fill("01/01/1980")
    page.locator("xpath=//span[contains(text(), 'Fecha de nacimiento')]/following::input[1]").press("Tab")
    
    # Sexo
    page.locator("xpath=//label[contains(text(), 'Hombre')]").click()
    
    # Comunidad Autonoma
    page.locator("xpath=//span[contains(text(), 'Comunidad Autónoma')]/following::input[1]").click()
    page.wait_for_timeout(500)
    page.locator("text='Andalucía'").last.click()
    
    page.locator("button:has-text('Aceptar')").first.click()
    
    try:
        page.wait_for_selector("button[title='Apartados declaración']", timeout=10000)
        print("SUCCESS! Llego a la siguiente pantalla.")
    except Exception as e:
        print(f"FAILED: {e}")

    browser.close()
