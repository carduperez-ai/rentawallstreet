from playwright.sync_api import sync_playwright
import re

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?TACCESO=COLAB&EJER=2025")
    page.wait_for_load_state("networkidle")
    
    page.locator("button:has-text('Nueva declaración')").first.click()
    page.wait_for_timeout(3000)
    
    print("Testing get_by_label...")
    try:
        print("Estado Civil loc:", page.get_by_label("Estado Civil", exact=False).count())
    except:
        pass
        
    # Get all inputs and their surrounding text in parent node
    inputs = page.locator("input").all()
    for el in inputs:
        try:
            parent_text = el.locator("xpath=..").text_content()
            print(f"Input Type: {el.get_attribute('type')}, Parent Text: {parent_text.strip()[:50] if parent_text else 'None'}")
        except:
            pass

    browser.close()
