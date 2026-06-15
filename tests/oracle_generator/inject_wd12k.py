import asyncio
from playwright.async_api import async_playwright


async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("Abriendo aplicacion local...")
        await page.goto("http://127.0.0.1:8150/")

        # 1. Reiniciar Asistente (si existe el boton)
        try:
            await page.click("text=REINICIAR ASISTENTE", timeout=2000)
            print("Asistente reiniciado.")
        except Exception:
            pass

        # 2. Iniciar Asistente
        await page.click("text=COMENZAR ASISTENTE")

        # Paso 1: Madrid
        await page.click("text=Madrid")
        # Paso 2: Renta 2025
        await page.click("text=Renta 2025")
        # Paso 3: Edad 30
        await page.fill("#wizard-input", "30")
        await page.click("text=SIGUIENTE")
        # Paso 4: Alquiler No
        await page.click("text=No")
        # Paso 5: VPO No
        await page.click("text=No")
        # Paso 6: Discapacidad No
        await page.click("text=No")
        # Paso 7: Situacion familiar Ninguna
        await page.click("text=Ninguna")
        # Paso 8: Hijos 0
        await page.fill("#wizard-input", "0")
        await page.click("text=SIGUIENTE")
        # Paso 9: Celiaco No
        await page.click("text=No")
        # Paso 10: Gimnasio 0
        await page.fill("#wizard-input", "0")
        await page.click("text=SIGUIENTE")
        # Paso 11: Veterinario 0
        await page.fill("#wizard-input", "0")
        await page.click("text=SIGUIENTE")
        # Paso 12: Defensa juridica 0
        await page.fill("#wizard-input", "0")
        await page.click("text=SIGUIENTE")
        # Paso 13: Startup 0
        await page.fill("#wizard-input", "0")
        await page.click("text=SIGUIENTE")
        # Paso 14: Donativos 0
        await page.fill("#wizard-input", "0")
        await page.click("text=SIGUIENTE")
        # Paso 15: Mejora energetica No
        await page.click("text=No")

        print("Asistente completado.")

        # 3. Meter datos economicos Trabajo
        await page.fill('input[name="gross_income"]', "12000")
        await page.fill('input[name="withholdings_paid"]', "240")
        await page.fill('input[name="ss_employee"]', "762")

        # 4. Añadir Dividendos
        await page.click("text=Añadir rendimiento")
        await page.fill('input[name="rcm_nombre[]"]', "TEST DIVIDEND")
        await page.fill('input[name="rcm_importe[]"]', "1200")
        await page.fill('input[name="rcm_retencion[]"]', "228")

        print("Datos inyectados. Calculando...")

        # 5. Calcular
        await page.click("#btn-calc")

        # Esperar a los resultados
        await page.wait_for_selector(".badge-primary")

        resultado = await page.inner_text(".badge-primary")
        print(f"Resultado en pantalla: {resultado}")

        # Mantener el navegador abierto para que el usuario lo vea
        await asyncio.sleep(30)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_test())
