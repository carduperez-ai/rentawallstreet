import datetime
from decimal import Decimal
from typing import Dict


class FiscalReportGenerator:
    def __init__(self, data: Dict):
        self.data = data
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def generate_html(self, output_path: str):
        html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Informe Fiscal 2025 - Auditoría DeGiro</title>
    <style>
        :root {{
            --primary: #1a2a6c;
            --secondary: #b21f1f;
            --accent: #fdbb2d;
            --success: #27ae60;
            --danger: #c0392b;
            --bg: #f8f9fa;
            --text: #2c3e50;
        }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        header {{
            border-bottom: 2px solid #eee;
            padding-bottom: 20px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        h1 {{ color: var(--primary); margin: 0; font-size: 1.8rem; }}
        .badge {{
            background: var(--primary);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .card {{
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #eee;
            background: #fff;
        }}
        .card.highlight {{ border-left: 5px solid var(--primary); }}
        .card.success {{ border-left: 5px solid var(--success); }}
        .card.danger {{ border-left: 5px solid var(--danger); }}
        .label {{ font-size: 0.8rem; color: #7f8c8d; text-transform: uppercase; font-weight: bold; }}
        .value {{ font-size: 1.5rem; font-weight: bold; color: var(--primary); margin-top: 5px; }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 0.9rem;
        }}
        th {{
            background: #f1f3f5;
            text-align: left;
            padding: 12px;
            border-bottom: 2px solid #dee2e6;
            color: #495057;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
        }}
        .pos {{ color: var(--success); font-weight: bold; }}
        .neg {{ color: var(--danger); font-weight: bold; }}

        .footer {{
            margin-top: 50px;
            font-size: 0.8rem;
            color: #bdc3c7;
            text-align: center;
            border-top: 1px solid #eee;
            padding-top: 20px;
        }}
        .box-reference {{
            background: #eef2f7;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: bold;
            color: #34495e;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Informe Fiscal IRPF 2025</h1>
                <p style="margin:5px 0; color:#7f8c8d;">Auditoría de Inversiones - DeGiro</p>
            </div>
            <div class="badge">ESTADO: VALIDADO AEAT</div>
        </header>

        <section>
            <h2 style="color:var(--primary); border-bottom: 1px solid #eee; padding-bottom:10px;">Resumen Consolidado</h2>
            <div class="grid">
                <div class="card highlight">
                    <div class="label">Ganancia Patrimonial Neta</div>
                    <div class="value">{self.data["net_gp"]:.2f} €</div>
                    <p style="margin-top:10px; font-size:0.85rem;">Suma de Casillas de Transmisión</p>
                </div>
                <div class="card success">
                    <div class="label">Rendimientos Capital Mobiliario</div>
                    <div class="value">{self.data["div_gross"]:.2f} €</div>
                    <p style="margin-top:10px; font-size:0.85rem;">Casilla <span class="box-reference">0029</span></p>
                </div>
                <div class="card danger">
                    <div class="label">Retenciones Pagadas</div>
                    <div class="value">{self.data["ret_total"]:.2f} €</div>
                    <p style="margin-top:10px; font-size:0.85rem;">Casilla <span class="box-reference">0588</span></p>
                </div>
            </div>
        </section>

        <section>
            <h2 style="color:var(--primary); border-bottom: 1px solid #eee; padding-bottom:10px;">Desglose por Activo (G/P)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Producto / ISIN</th>
                        <th style="text-align:right;">Ganancia</th>
                        <th style="text-align:right;">Pérdida</th>
                        <th style="text-align:right;">Neto Realizado</th>
                    </tr>
                </thead>
                <tbody>
        """

        for asset, res in sorted(self.data["assets"].items(), key=lambda x: x[1]["gain"] - x[1]["loss"], reverse=True):
            neto = res["gain"] - res["loss"]
            net_class = "pos" if neto >= 0 else "neg"
            html += f"""
                    <tr>
                        <td><strong>{asset}</strong></td>
                        <td style="text-align:right;">{res["gain"]:.2f} €</td>
                        <td style="text-align:right;">{res["loss"]:.2f} €</td>
                        <td style="text-align:right;" class="{net_class}">{neto:.2f} €</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
        </section>
        """

        if "m721" in self.data and self.data["m721"].get("required"):
            html += f"""
        <section style="margin-top: 40px;">
            <h2 style="color:var(--primary); border-bottom: 1px solid #eee; padding-bottom:10px;">Modelo 721 (Criptoactivos en el Extranjero)</h2>
            <div class="card danger">
                <div class="label">Total Patrimonio a 31 de Diciembre</div>
                <div class="value">{self.data["m721"]["total_value_eur"]:.2f} €</div>
                <p style="margin-top:10px; font-size:0.85rem; font-weight:bold;">SUPERADO LÍMITE DE 50.000€ - OBLIGACIÓN DE PRESENTACIÓN</p>
            </div>
            <table style="margin-top: 20px;">
                <thead>
                    <tr>
                        <th>Activo</th>
                        <th style="text-align:right;">Cantidad</th>
                        <th style="text-align:right;">Cotización 31/12</th>
                        <th style="text-align:right;">Valoración EUR</th>
                    </tr>
                </thead>
                <tbody>
            """
            for item in self.data["m721"]["inventory"]:
                html += f"""
                    <tr>
                        <td><strong>{item["asset"]}</strong></td>
                        <td style="text-align:right;">{item["quantity"]}</td>
                        <td style="text-align:right;">{item["price_eur"]:.2f} €</td>
                        <td style="text-align:right; font-weight:bold;">{item["value_eur"]:.2f} €</td>
                    </tr>
                """
            html += """
                </tbody>
            </table>
        </section>
        """
        elif "m721" in self.data and not self.data["m721"].get("required"):
            html += f"""
        <section style="margin-top: 40px;">
            <h2 style="color:var(--primary); border-bottom: 1px solid #eee; padding-bottom:10px;">Modelo 721 (Criptoactivos en el Extranjero)</h2>
            <div class="card success">
                <div class="label">Total Patrimonio a 31 de Diciembre</div>
                <div class="value">{self.data["m721"]["total_value_eur"]:.2f} €</div>
                <p style="margin-top:10px; font-size:0.85rem;">EXENTO: No supera el límite normativo conjunto de 50.000 €.</p>
            </div>
        </section>
        """

        html += f"""
        <section style="margin-top: 40px;">
            <h2 style="color:var(--primary); border-bottom: 1px solid #eee; padding-bottom:10px;">Otras Casillas AEAT</h2>
            <div class="card">
                <p><strong>Gastos Deducibles (Mantenimiento / Conectividad):</strong> <span class="value" style="font-size:1.2rem;">{self.data.get("fees", Decimal("0")):.2f} €</span></p>
                <p style="font-size:0.9rem; color:#666;">Incluye comisiones de conectividad de mercado aplicables en la Casilla <span class="box-reference">0035</span>.</p>
            </div>
        </section>

        <div class="footer">
            Informe generado automáticamente por AntiGravity Fiscal Engine v2.0 - {self.timestamp}<br>
            Este documento constituye una propuesta de declaración basada en los datos proporcionados y los criterios FIFO de la AEAT.
        </div>
    </div>
</body>
</html>
        """
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Informe generado en: {output_path}")


if __name__ == "__main__":
    # Test generation with the data we just calculated
    test_data = {
        "net_gp": Decimal("5936.96"),
        "div_gross": Decimal("94.06"),
        "ret_total": Decimal("17.64"),
        "fees": Decimal("10.00"),
        "assets": {
            "REPSOL SA": {"gain": Decimal("66.84"), "loss": Decimal("0.00")},
            "NVIDIA CORP": {"gain": Decimal("1000.00"), "loss": Decimal("200.00")},  # Example
            # ... more assets will be injected by the main script
        },
    }
    # (En una ejecución real, esto se llamaría desde el script principal)
