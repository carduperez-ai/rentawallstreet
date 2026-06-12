from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?TACCESO=COLAB&EJER=2025")
    page.wait_for_load_state("networkidle")
    
    page.locator("button:has-text('Nueva declaración')").first.click()
    page.wait_for_timeout(3000)
    
    # Pruebas de XPath
    ec = page.locator("xpath=//span[contains(text(), 'Estado Civil')]/following::input[1]").count()
    fn = page.locator("xpath=//span[contains(text(), 'Fecha de nacimiento')]/following::input[1]").count()
    ca = page.locator("xpath=//span[contains(text(), 'Comunidad Autónoma')]/following::input[1]").count()
    
    print(f"Estado Civil: {ec}")
    print(f"Fecha Nacimiento: {fn}")
    print(f"Comunidad Autonoma: {ca}")

    browser.close()
