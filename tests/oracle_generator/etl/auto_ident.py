from playwright.sync_api import sync_playwright
import time


def fill_identification():
    with sync_playwright() as p:
        try:
            print("Conectando a la sesión de Chrome...")
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            page = browser.contexts[0].pages[0]

            print("Esperando a que cargue la identificación...")
            page.wait_for_selector("input[title*='NIF']", timeout=30000)

            print("Rellenando NIF y Nombre...")
            page.locator("input[title*='NIF']").fill("12345678Z")
            page.locator("input[title*='Apellidos']").fill("PRUEBA ORACULO")

            # Pulsar Aceptar para pasar a la siguiente parte de la identificación
            page.locator("button:has-text('Aceptar')").first.click()
            time.sleep(2)

            print("Configurando Estado Civil y Región...")
            # Estado Civil: Soltero (suele ser el primero o por texto)
            # Comunidad: Cataluña (09)
            # Fecha Nacimiento: 01/01/1980

            # Fecha Nacimiento
            page.locator("input[title*='nacimiento']").fill("01011980")

            # Sexo: Hombre
            page.locator("text=Hombre").click()

            # Comunidad Autónoma: Cataluña
            # Buscamos el combo de comunidad
            page.locator("xpath=//select | //input[contains(@title, 'Comunidad')]").first.click()
            page.keyboard.type("09")
            page.keyboard.press("Enter")

            print("Finalizando identificación...")
            page.locator("button:has-text('Aceptar')").last.click()

            print("¡IDENTIFICACIÓN COMPLETADA!")

        except Exception as e:
            print(f"Error en identificación: {e}")


if __name__ == "__main__":
    fill_identification()
