import sys
import time
from playwright.sync_api import sync_playwright

def monitor():
    print("Iniciando monitorización pasiva...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            
            while True:
                page.screenshot(path="c:/rentawallstreet/tests/oracle_generator/etl/monitor.png")
                print(f"[{time.strftime('%H:%M:%S')}] Captura actualizada.")
                time.sleep(5)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    monitor()
