import json
import os
import sys
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright no está instalado.")
    exit(1)

JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "irpf_oracle_tests.json")
SCREENSHOT_PATH = os.path.join(os.path.dirname(__file__), "monitor.png")

def process_aeat_cases(json_path=None):
    if json_path is None:
        json_path = JSON_PATH

    with open(json_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    pending_cases = [
        c for c in cases 
        if c.get("status") == "pending"
    ]
    
    if not pending_cases:
        print("No hay casos pendientes en el JSON.")
        return

    with sync_playwright() as p:
        try:
            print("Conectando a Chrome (9222)...")
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            
            # Buscamos la página que REALMENTE tiene el simulador abierto
            aeat_pages = [pg for pg in context.pages if "agenciatributaria.gob.es" in pg.url and "RW25" in pg.url]
            
            if not aeat_pages:
                print("Error: No se encontró la pestaña activa del simulador Renta 2025.")
                return
            
            # Si hay varias, intentamos buscar la que NO esté vacía o la más reciente
            page = aeat_pages[-1] 
            print(f"Sincronizado con pestaña: {page.title()} ({page.url[:50]}...)")
            
            # Tomamos una captura inicial para 'monitorizar'
            page.screenshot(path=SCREENSHOT_PATH)
            print(f"  [MONITOR] Captura guardada en {SCREENSHOT_PATH}")

            last_res = None
            for idx, case in enumerate(pending_cases, 1):
                print(f"\n[{idx}/{len(pending_cases)}] PROCESANDO: {case['name']}...")
                
                # Resincronizar en cada iteración por si se abrió otra pestaña
                page.bring_to_front()
                _clear_popups(page)
                
                # Inyección con Fuerza Bruta y Feedback Visual
                _inject_trabajo_visual(page, case['input'])
                
                # Ir a Resumen y asegurar que carga
                print("  - Navegando a Resumen...")
                _force_click_visual(page, "Resumen")
                page.wait_for_timeout(5000)
                
                # Verificar si realmente estamos en Resumen
                is_resumen = page.evaluate("() => document.body.innerText.includes('Resultado de la declaración')")
                if not is_resumen:
                    print("    [!] No se detecta página de Resumen. Re-intentando click...")
                    _force_click_visual(page, "Resumen de declaraciones")
                    page.wait_for_timeout(8000)

                print("  - Calculando (10s)...")
                time.sleep(10)
                
                results = _extract_results(page)
                
                # Verificación de datos estáticos/congelados
                if idx > 1 and results.get('resultado_declaracion') == last_res:
                    print("    [!] Resultado idéntico detectado. Re-calculando (5s)...")
                    time.sleep(5)
                    results = _extract_results(page)
                
                last_res = results.get('resultado_declaracion')
                case["expected_results"].update(results)
                case["status"] = "verified"
                print(f"  [OK] Resultado: {results.get('resultado_declaracion')}")
                _save_json(json_path, cases)
                
                # Volver a Apartados
                _force_click_visual(page, "Apartados")
                time.sleep(2)

        except Exception as e:
            print(f"Error: {e}")

def _clear_popups(page):
    # Cierra avisos pero NO formularios de datos
    page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button, a, span'));
        const closeBtn = btns.find(b => {
            const isAction = ['Aceptar', 'Continuar', 'Cerrar', 'Ok'].some(txt => b.innerText.includes(txt));
            const isInsidePopup = b.closest('.z-window') || b.closest('.z-messagebox');
            const hasInputs = b.closest('.z-window') && b.closest('.z-window').querySelectorAll('input').length > 1;
            
            return isAction && isInsidePopup && !hasInputs && !b.innerText.includes('Resumen');
        });
        if (closeBtn) closeBtn.click();
    }""")
    time.sleep(1)

def _force_click_visual(page, text: str):
    print(f"    - Clicando: {text}")
    page.evaluate(f"""(txt) => {{
        const el = Array.from(document.querySelectorAll('button, u, span')).find(e => 
            (e.innerText && e.innerText.includes(txt)) || (e.title && e.title.includes(txt))
        );
        if (el) {{
            el.style.border = '3px solid red';
            el.click();
            el.dispatchEvent(new Event('mousedown', {{ bubbles: true }}));
            el.dispatchEvent(new Event('mouseup', {{ bubbles: true }}));
        }}
    }}""", text)

def _inject_trabajo_visual(page, inp: dict):
    print("  - Navegando a la sección de Trabajo...")
    
    # 1. Navegar a Apartados
    page.evaluate("""() => {
        const btn = Array.from(document.querySelectorAll('button, a')).find(el => el.innerText.includes('Apartados declaración'));
        if (btn) btn.click();
    }""")
    page.wait_for_timeout(2000)
    
    # 2. Entrar en Trabajo
    page.evaluate("""() => {
        const link = Array.from(document.querySelectorAll('a, span, li')).find(el => 
            el.innerText.trim() === 'Rendimientos del trabajo (sueldos, nóminas, pensiones, etc.)'
        );
        if (link) link.click();
    }""")
    page.wait_for_timeout(2500)

    # 3. EDITAR: Buscar el lápiz de la casilla 0003 específicamente
    print("  - Buscando lápiz de la casilla 0003...")
    found = page.evaluate("""() => {
        const span = Array.from(document.querySelectorAll('span')).find(el => el.innerText.trim() === '0003');
        if (span) {
            const parent = span.closest('.z-hlayout') || span.parentElement.parentElement;
            const btn = parent.querySelector('button.botonLanzaVentana') || parent.querySelector('button');
            if (btn) {
                btn.click();
                return true;
            }
        }
        return false;
    }""")
    
    if not found:
        print("    - No se encontró lápiz de 0003. Intentando Alta...")
        _force_click_visual(page, "Alta")
    
    page.wait_for_timeout(3000)

    # 4. Inyección: BORRAR y luego ESCRIBIR
    vals = {
        "mporte": inp.get('gross_income', 0),
        "etención": inp.get('withholdings_paid', 0),
        "eguridad Social": inp.get('ss_employee', 0)
    }
    
    for fragment, val in vals.items():
        val_str = str(val).replace('.', ',')
        print(f"    - Sobre-escribiendo {fragment} -> {val_str}")
        
        # Localizar, Limpiar y Escribir
        page.evaluate(f"""() => {{
            const inputs = Array.from(document.querySelectorAll('input:not([readonly])'));
            const input = inputs.find(i => i.title && i.title.includes('{fragment}'));
            if (input) {{
                input.focus();
                input.value = ''; // Limpieza JS
            }}
        }}""")
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(val_str, delay=40)
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
        val_str = str(val).replace('.', ',')
        print(f"    - Campo {fragment} -> {val_str}")
        
        # Localizar el input
        page.evaluate(f"""() => {{
            const input = Array.from(document.querySelectorAll('input:not([readonly])')).find(i => i.title && i.title.includes('{fragment}'));
            if (input) {{
                input.focus();
                input.select(); // Seleccionar todo para borrar al escribir
            }}
        }}""")
        page.wait_for_timeout(300)
        
        # Borrar contenido previo
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        
        # Escribir carácter a carácter
        page.keyboard.type(val_str, delay=50)
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)

    # Clic en Aceptar del MODAL específicamente
    page.evaluate("""() => {
        const modal = document.querySelector('.z-window-highlighted, .z-window-modal');
        if (modal) {
            const btn = Array.from(modal.querySelectorAll('button')).find(b => b.innerText.includes('Aceptar'));
            if (btn) btn.click();
        }
    }""")
    page.wait_for_timeout(3000)

def _extract_results(page):
    # Extracción vía JS para evitar problemas de visibilidad
    return page.evaluate("""() => {
        const getV = (id) => {
            const el = document.querySelector(`button#${id}`);
            return el ? parseFloat(el.innerText.replace(/\\./g, '').replace(',', '.')) : 0.0;
        };
        return {
            "resultado_declaracion": getV('RESINGDEV'),
            "base_imponible_general": getV('BIGRALH'),
            "ingresos_integros": getV('TINCOMT') 
        };
    }""")

def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    process_aeat_cases()
