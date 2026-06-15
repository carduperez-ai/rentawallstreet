from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = browser.contexts[0].pages[0]
        buttons = page.evaluate("""() =>
            Array.from(document.querySelectorAll('button'))
                .map(b => `${b.id} | ${b.innerText.trim()}`)
                .filter(s => s.length > 5)
                .join('\\n')
        """)
        print("--- BOTONES DETECTADOS ---")
        print(buttons)
        browser.close()
except Exception as e:
    print(f"Error: {e}")
