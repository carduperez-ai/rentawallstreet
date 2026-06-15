import asyncio
from playwright.async_api import async_playwright


async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("Abriendo aplicacion local...")
            await page.goto("http://127.0.0.1:8150/")

            # 1. Limpiar localStorage para asegurar un inicio limpio
            await page.evaluate("localStorage.clear()")
            await page.reload()

            print("Iniciando Asistente...")
            await page.wait_for_selector("text=COMENZAR ASISTENTE", timeout=5000)
            await page.click("text=COMENZAR ASISTENTE")

            # Navegación Wizard (Madrid, 2025, 30 años, No, No, No, Ninguna, 0, No, 0, 0, 0, 0, 0, No)
            steps = [
                ("text=Madrid", "choice"),
                ("text=Renta 2025", "choice"),
                ("#wizard-input", "type", "30"),
                ("text=SIGUIENTE", "click"),
                ("text=No", "choice"),  # Alquiler
                ("text=No", "choice"),  # VPO
                ("text=No", "choice"),  # Discapacidad
                ("text=Ninguna", "choice"),  # Familia
                ("#wizard-input", "type", "0"),  # Hijos
                ("text=SIGUIENTE", "click"),
                ("text=No", "choice"),  # Celiaco
                ("#wizard-input", "type", "0"),  # Gym
                ("text=SIGUIENTE", "click"),
                ("#wizard-input", "type", "0"),  # Vet
                ("text=SIGUIENTE", "click"),
                ("#wizard-input", "type", "0"),  # Defensa
                ("text=SIGUIENTE", "click"),
                ("#wizard-input", "type", "0"),  # Startup
                ("text=SIGUIENTE", "click"),
                ("#wizard-input", "type", "0"),  # Donaciones
                ("text=SIGUIENTE", "click"),
                ("text=No", "choice"),  # Energia
            ]

            for selector, action, *args in steps:
                await page.wait_for_selector(selector, timeout=5000)
                if action == "choice":
                    await page.click(selector)
                elif action == "type":
                    await page.fill(selector, args[0])
                elif action == "click":
                    await page.click(selector)
                await asyncio.sleep(0.3)

            print("Asistente completado. Inyectando datos economicos...")

            await page.fill('input[name="gross_income"]', "12000")
            await page.fill('input[name="withholdings_paid"]', "240")
            await page.fill('input[name="ss_employee"]', "762")

            await page.click("text=Añadir rendimiento")
            await page.fill('input[name="rcm_nombre[]"]', "TEST DIVIDEND")
            await page.fill('input[name="rcm_importe[]"]', "1200")
            await page.fill('input[name="rcm_retencion[]"]', "228")

            print("Calculando...")
            await page.click("#btn-calc")

            await page.wait_for_selector(".badge-primary", timeout=10000)
            resultado = await page.inner_text(".badge-primary")
            print(f"RESULTADO OBTENIDO: {resultado}")

            await asyncio.sleep(30)

        except Exception as e:
            print(f"ERROR: {e}")
            await asyncio.sleep(30)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_test())
