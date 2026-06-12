import time
from playwright.sync_api import sync_playwright

def get_work_dom():
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            
            print("Pulsando 'Apartados declaración'...")
            page.evaluate("""() => {
                const btn = Array.from(document.querySelectorAll('button, span')).find(el => el.innerText.includes('Apartados declaración'));
                if (btn) btn.click();
            }""")
            time.sleep(3)
            
            print("Entrando en Rendimientos del trabajo...")
            page.evaluate("""() => {
                const link = Array.from(document.querySelectorAll('a, span')).find(el => el.innerText.includes('Rendimientos del trabajo'));
                if (link) link.click();
            }""")
            time.sleep(3)
            
            print("Capturando DOM de la tabla...")
            with open("c:/rentawallstreet/tests/oracle_generator/etl/work_table_dom.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            
            page.screenshot(path="c:/rentawallstreet/tests/oracle_generator/etl/work_table.png")
            print("Hecho. DOM en work_table_dom.html y captura en work_table.png")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    get_work_dom()
