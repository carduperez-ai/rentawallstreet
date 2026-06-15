from playwright.sync_api import sync_playwright


def get_dom():
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            print(f"Capturando DOM de: {page.title()}")
            content = page.content()
            with open("c:/rentawallstreet/tests/oracle_generator/etl/current_dom.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("DOM guardado en current_dom.html")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    get_dom()
