from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?TACCESO=COLAB&EJER=2025")
    page.wait_for_load_state("networkidle")

    page.locator("button:has-text('Nueva declaración')").first.click()
    page.wait_for_timeout(3000)

    inputs = page.locator("input").all()
    print("Inputs found:")
    for el in inputs:
        print(f"Title: {el.get_attribute('title')}, Type: {el.get_attribute('type')}")

    selects = page.locator("select").all()
    print("\nSelects found:")
    for el in selects:
        print(f"Title: {el.get_attribute('title')}")

    browser.close()
