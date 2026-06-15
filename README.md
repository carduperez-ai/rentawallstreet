# Renta Wall Street

Plataforma de orquestación y consolidación fiscal (Motor 2025). Transforma extracciones granulares de brokers (CSVs y PDFs de Degiro, Trading212, Binance, Kraken, eToro, etc.) en resúmenes listos para la liquidación del Impuesto sobre la Renta de las Personas Físicas (IRPF) en España, implementando metodologías FIFO, depuración de divisas, y de-duplicación de dividendos.

## Características
* Consolidación Multibróker y Cripto.
* Motor de asignación FIFO (First In, First Out).
* Filtrado y validación de dividendos contra informes fiscales base (PDF).
* Integración modular con especificidades por Comunidad Autónoma.

---

> [!CAUTION]
> # DESCARGO DE RESPONSABILIDAD LEGAL Y FISCAL
> 
> **EL PRESENTE SOFTWARE SE DISTRIBUYE "TAL CUAL" ("AS IS"), SIN GARANTÍA DE NINGÚN TIPO.**
> 
> 1. **No constituye asesoramiento financiero ni fiscal:** Esta herramienta es un proyecto de procesamiento de datos de carácter experimental. Los informes generados no sustituyen en ningún caso el criterio de un asesor fiscal colegiado ni la información oficial proporcionada por la Agencia Estatal de Administración Tributaria (AEAT).
> 2. **Exención de responsabilidad:** El autor original (Carlos Perez) y los contribuyentes del proyecto se eximen expresamente de **cualquier tipo de responsabilidad civil, penal o administrativa**, incluyendo, pero no limitándose a, sanciones de la AEAT, liquidaciones paralelas, recargos, o pérdidas económicas que pudieran derivarse directa o indirectamente de:
>    - Bugs, errores de cálculo o interpretación incorrecta de las leyes tributarias por parte del código fuente.
>    - Diferencias por redondeo en operaciones de divisas o fluctuaciones en la tasa de cambio.
>    - Decisiones tomadas por el usuario basándose en los datos arrojados por el software.
> 3. **Validación obligatoria:** El usuario asume plena y absoluta responsabilidad de auditar y contrastar matemáticamente y jurídicamente todas las casillas (rendimientos del capital mobiliario, ganancias y pérdidas patrimoniales, etc.) antes de registrar su autoliquidación del IRPF ante las administraciones públicas.
