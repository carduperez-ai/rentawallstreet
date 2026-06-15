from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?TACCESO=COLAB&EJER=2025")
    page.wait_for_load_state("networkidle")
    page.locator("button:has-text('Nueva declaración')").first.click()
    page.wait_for_timeout(2000)

    html = page.evaluate("""() => {
        let spans = Array.from(document.querySelectorAll('span'));
        let target = spans.find(s => s.innerText.includes('Estado Civil'));
        if (!target) return 'No span found';
        
        // Find the first input after the target span in the DOM tree
        // Simplest way is to get all elements, find target index, then find first input
        let allNodes = Array.from(document.querySelectorAll('*'));
        let spanIndex = allNodes.indexOf(target);
        let inputNode = null;
        for (let i = spanIndex + 1; i < allNodes.length; i++) {
            if (allNodes[i].tagName === 'INPUT') {
                inputNode = allNodes[i];
                break;
            }
        }
        
        if (!inputNode) return 'No input found';
        return inputNode.parentElement.innerHTML;
    }""")
    print("DOM of input's parent:")
    print(html)
    browser.close()
