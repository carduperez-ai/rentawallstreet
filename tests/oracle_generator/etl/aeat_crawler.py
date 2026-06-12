import requests
import re
import json

class AEATCrawler:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def fetch_chapter(self, url: str) -> str:
        """Descarga el contenido HTML de un capítulo."""
        # En un entorno real se usaría:
        # response = requests.get(url)
        # response.raise_for_status()
        # return response.text
        
        # Para la prueba de concepto, simulamos el HTML del Caso Práctico 1 del Capítulo 3
        return """
        <html>
            <body>
                <div class="caso-practico">
                    <h2>Supuesto Práctico 1</h2>
                    <p>El contribuyente reside en Andalucía. Tiene 30 años y es soltero.</p>
                    <p>Ha percibido en concepto de sueldo íntegro 30.000 euros. Las retenciones practicadas ascienden a 4.500 euros. Sus gastos de Seguridad Social son 1.905 euros.</p>
                </div>
                <div class="solucion">
                    <h3>Solución:</h3>
                    <p>Rendimiento neto: 23.595,00 euros.</p>
                    <p>Base imponible general: 23.595,00 euros.</p>
                    <p>Cuota íntegra estatal: 2.800,00 euros.</p>
                </div>
            </body>
        </html>
        """

    def extract_cases(self, html: str) -> list:
        """Extrae los bloques de texto de los casos prácticos y sus soluciones usando regex (PoC sin bs4)."""
        cases = []
        
        # Regex básico para extraer contenido de tags <div> específicos
        caso_match = re.search(r'<div class="caso-practico">(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        solucion_match = re.search(r'<div class="solucion">(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        
        if caso_match and solucion_match:
            # Limpiar tags HTML simples
            supuesto_limpio = re.sub(r'<[^>]+>', ' ', caso_match.group(1)).strip()
            solucion_limpia = re.sub(r'<[^>]+>', ' ', solucion_match.group(1)).strip()
            
            # Limpiar espacios múltiples
            supuesto_limpio = re.sub(r'\s+', ' ', supuesto_limpio)
            solucion_limpia = re.sub(r'\s+', ' ', solucion_limpia)
            
            cases.append({
                'supuesto': supuesto_limpio,
                'solucion': solucion_limpia
            })
            
        return cases

if __name__ == "__main__":
    crawler = AEATCrawler("https://sede.agenciatributaria.gob.es/")
    html = crawler.fetch_chapter("dummy_url")
    cases = crawler.extract_cases(html)
    print(json.dumps(cases, indent=2, ensure_ascii=False))
