# Renta Wall Street

Herramienta de procesamiento, auditoría y cálculo fiscal para la declaración de la Renta (AEAT) de operaciones financieras (Acciones, Criptomonedas, Inmuebles).

## Arquitectura Principal
* `main.py`, `maincrypto.py`, `mainstock.py`: Puntos de entrada para la ejecución del motor de cálculo según el tipo de activo.
* `src/`: Lógica central del motor de cálculo y parsing de datos.
* `renta_declaracion/`: Módulo de adaptación a la normativa fiscal y generación de resúmenes.
* `tests/`: Batería de pruebas (pytest) para validación de exactitud en los cálculos fiscales (FIFO, etc.).

## Instalación
1. Clonar el repositorio.
2. Instalar las dependencias: `pip install -r requirements.txt`.

## Uso
Ejecutar el pipeline principal o los scripts específicos por activo:
```bash
python main.py
python maincrypto.py
python mainstock.py
```

## Normativa Fiscal
El motor implementa las reglas de devengo y trazabilidad FIFO requeridas por la Agencia Tributaria Española (AEAT).
