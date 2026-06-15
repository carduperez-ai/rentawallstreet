from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?TACCESO=COLAB&EJER=2025")
    page.wait_for_load_state("networkidle")
    page.locator("button:has-text('Nueva declaración')").first.click()
    page.wait_for_timeout(2000)

    combos = page.locator("input.z-combobox-input:not([disabled])")

    # CCAA
    combos.nth(1).click(force=True)
    page.wait_for_timeout(1000)

    html = page.evaluate("""() => {
        let lis = Array.from(document.querySelectorAll('li'));
        return lis.map(li => li.innerText).join('\\n');
    }""")
    print("LI elements:")
    print(html)
    browser.close()
