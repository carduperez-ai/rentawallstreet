from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?TACCESO=COLAB&EJER=2025")
    page.wait_for_load_state("networkidle")
    page.locator("button:has-text('Nueva declaración')").first.click()
    page.wait_for_timeout(2000)

    # Rellenar comboboxes
    combos = page.locator("input.z-combobox-input:not([disabled])")

    # 1. Estado Civil
    ec = combos.nth(0)
    ec.click(force=True)  # Click para abrir desplegable
    page.wait_for_timeout(500)
    # Seleccionamos texto visible en la lista
    page.locator("li:has-text('Soltero/a')").first.click(force=True)

    page.wait_for_timeout(500)

    # 2. CCAA
    ca = combos.nth(1)
    ca.click(force=True)
    page.wait_for_timeout(500)
    page.locator("li:has-text('Andalucía')").first.click(force=True)

    page.wait_for_timeout(1000)

    # Verify they have value
    print("EC val:", ec.get_attribute("value"))
    print("CA val:", ca.get_attribute("value"))

    browser.close()
