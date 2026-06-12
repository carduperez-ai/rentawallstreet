import json
import os
from .aeat_crawler import AEATCrawler
from .aeat_parser import AEATParser

def run_etl_pipeline():
    """Ejecuta el pipeline completo de extracción, transformación y carga."""
    print("Iniciando ETL de la AEAT...")
    
    # 1. Extracción
    crawler = AEATCrawler("https://sede.agenciatributaria.gob.es/")
    html_content = crawler.fetch_chapter("dummy_url_capitulo_3")
    raw_cases = crawler.extract_cases(html_content)
    
    # 2. Transformación
    parser = AEATParser()
    golden_cases = []
    
    for i, raw_case in enumerate(raw_cases, 1):
        parsed = parser.parse_case(
            case_id=f"CAP3_{i}",
            supuesto=raw_case['supuesto'],
            solucion=raw_case['solucion']
        )
        golden_cases.append(parsed)
        
    # 3. Carga
    # Ruta al archivo irpf_oracle_tests.json (asumiendo ejecución desde etl/)
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "irpf_oracle_tests.json")
    
    # Leer casos existentes si existen
    existing_cases = []
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            try:
                existing_cases = json.load(f)
            except json.JSONDecodeError:
                pass
                
    # Anexar o sobrescribir (aquí anexamos a los estáticos)
    # Evitar duplicados por nombre
    existing_names = {c["name"] for c in existing_cases}
    for new_case in golden_cases:
        if new_case["name"] not in existing_names:
            existing_cases.append(new_case)
            
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing_cases, f, indent=2, ensure_ascii=False)
        
    print(f"Carga completa. {len(golden_cases)} casos nuevos inyectados en {output_path}")

if __name__ == "__main__":
    run_etl_pipeline()
