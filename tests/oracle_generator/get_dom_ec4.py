from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?TACCESO=COLAB&EJER=2025")
    page.wait_for_load_state("networkidle")
    page.locator("button:has-text('Nueva declaración')").first.click()
    page.wait_for_timeout(2000)

    html = page.evaluate("""() => {
        let inputs = Array.from(document.querySelectorAll('input.z-combobox-input'));
        return inputs.map(i => i.outerHTML).join('\\n');
    }""")
    print("Comboboxes:")
    print(html)
    browser.close()
