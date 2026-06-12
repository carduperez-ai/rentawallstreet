from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
import os
import sys
import json
from datetime import datetime
from decimal import Decimal

# Configuración de codificación para JSON
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal): return float(obj)
        if isinstance(obj, datetime): return obj.isoformat()
        return super(DecimalEncoder, self).default(obj)

def _to_dec(valor, default='0') -> Decimal:
    if valor is None or str(valor).strip() == '': return Decimal(default)
    s = str(valor).replace(',', '.')
    try: return Decimal(s)
    except: return Decimal(default)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.accounting.fifo_calculator import TaxEngine, IRPFCalculator
from src.reporting.excel_generator import generate_audit_excel
from src.domain.fiscal_entities import WorkIncome

app = Flask(__name__)
app.secret_key = 'fiscal-pro-2025-surgical-key'

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
else:
    for f in os.listdir(UPLOAD_FOLDER):
        try: os.remove(os.path.join(UPLOAD_FOLDER, f))
        except: pass


@app.template_filter('euro')
def euro_format(value):
    if value is None: return "0,00 €"
    try:
        if not isinstance(value, Decimal): value = Decimal(str(value))
        return "{:,.2f} €".format(value).replace(',', 'X').replace('.', ',').replace('X', '.')
    except: return f"{value} €"

@app.route('/')
def index():
    files = []
    prefs = session.get('platform_prefs', {})
    if os.path.exists(UPLOAD_FOLDER):
        for f in os.listdir(UPLOAD_FOLDER):
            if f.lower().endswith(('csv', 'xlsx', 'xls', 'pdf')):
                files.append({"name": f, "platform": prefs.get(f, "auto")})
    return render_template('index.html', mailbox=files, now=datetime.now())

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' in request.files:
        for file in request.files.getlist('file'):
            if file.filename != '':
                file.save(os.path.join(UPLOAD_FOLDER, file.filename))
        flash("Archivos subidos correctamente", "success")
    return redirect(url_for('index'))

@app.route('/calculate', methods=['POST', 'GET'])
def calculate():
    try:
        # 1. Recoger datos del formulario
        region = request.form.get('region', 'andalucia')
        fiscal_year = int(request.form.get('fiscal_year', datetime.now().year - 1))
        income = _to_dec(request.form.get('gross_income'))
        ss = _to_dec(request.form.get('ss_employee'))
        ret = _to_dec(request.form.get('withholdings_paid'))
        
        # 2. Ingesta Multi-Plataforma
        from src.ingestion.binance_reader import BinanceIngestor
        from src.ingestion.binance_reader_pdf import BinancePDFReader
        from src.ingestion.universal_reader import UniversalHeuristicParser
        
        binance_ingestor = BinanceIngestor()
        pdf_reader = BinancePDFReader()
        universal_ingestor = UniversalHeuristicParser()
        prefs = session.get('platform_prefs', {})
        
        all_warnings = []
        all_trades = []
        all_dividends = []
        pdf_trades = []

        for f in os.listdir(UPLOAD_FOLDER):
            f_path = os.path.join(UPLOAD_FOLDER, f)
            platform = str(prefs.get(f, "auto")).lower().strip()
            
            print(f"DEBUG: Procesando {f} con plataforma seleccionada: {platform}")
            
            if "binance" in platform:
                print(f"\n>>> [CHIVATO] MOTOR BINANCE ACTIVADO PARA: {f}")
                if f.lower().endswith('.pdf'):
                    trades = pdf_reader.get_trades(f_path)
                    if trades:
                        pdf_trades.extend(trades)
                    else:
                        all_warnings.append(f"⚠️ Error: No se pudo extraer datos del PDF de Binance: {f}")
                else:
                    if binance_ingestor.process_file(f_path):
                        all_warnings.extend(binance_ingestor.warnings)
                    else:
                        all_warnings.append(f"⚠️ Error: El archivo {f} no tiene formato Binance válido.")
            elif "degiro" in platform:
                from src.ingestion.degiro_reader import parse as parse_degiro
                t, d = parse_degiro(f_path)
                if t or d:
                    all_trades.extend(t)
                    all_dividends.extend(d)
                else:
                    all_warnings.append(f"⚠️ Error: No se detectaron datos en el archivo de DeGiro: {f}")
            elif "t212" in platform or "trading" in platform:
                from src.ingestion.trading212_reader import parse as parse_t212
                t, d = parse_t212(f_path)
                if t or d:
                    all_trades.extend(t)
                    all_dividends.extend(d)
                else:
                    all_warnings.append(f"⚠️ Error: No se detectaron datos en el archivo de Trading 212: {f}")
            else:
                # Motor heurístico universal (Safety Net)
                print(f"DEBUG: Usando motor Universal para {f}")
                if universal_ingestor.process_file(f_path):
                    all_warnings.extend(universal_ingestor.warnings)
                else:
                    all_warnings.append(f"⚠️ No se pudo entender el formato del archivo: {f}")

        # 3. Consolidación Final de todos los motores
        # Recolectamos lo que los ingestores con estado (Binance, Universal) han acumulado
        all_trades.extend(binance_ingestor.transactions)
        all_trades.extend(universal_ingestor.transactions)
        all_trades.extend(pdf_trades)
        
        # Recolección de avisos tardía (para captar fallos de valoración en properties)
        all_warnings.extend(binance_ingestor.warnings)
        all_warnings.extend(universal_ingestor.warnings)
        
        # Ordenación Cronológica Crítica
        all_trades.sort(key=lambda x: x.date)
        
        all_dividends.extend(binance_ingestor.dividends)
        all_dividends.extend(universal_ingestor.dividends)
        
        # 3. Motor Contable (Basado en el año seleccionado)
        work = WorkIncome(retribuciones_dinerarias=income, retenciones=ret, gastos_deducibles=ss)
        engine = TaxEngine(tax_year=fiscal_year)
        engine.process_trades(all_trades)
        engine.process_dividends(all_dividends)
        
        # 4. Cálculo Fiscal y Mapeo para Web (items fix)
        calc = IRPFCalculator(engine.tax_events, engine.dividends, work, region=region)
        summary = calc.calculate()
        
        # 5. Generar Excel de Auditoría Detallado (Desactivado por petición de usuario)
        # excel_path = os.path.join(app.root_path, 'tests', 'Auditoria_Fiscal_Detallada.xlsx')
        # generate_audit_excel(engine.tax_events, engine.dividends, excel_path)

        return render_template('result.html', summary=summary, warnings=all_warnings + engine.warnings)
    except Exception as e:
        flash(f"Error en el cálculo: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/update_platform', methods=['POST'])
def update_platform():
    data = request.get_json()
    if 'platform_prefs' not in session: session['platform_prefs'] = {}
    prefs = session['platform_prefs']
    prefs[data['filename']] = data['platform']
    session['platform_prefs'] = prefs
    return jsonify({"status": "ok"})

@app.route('/delete/<path:filename>')
def delete_file(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(path): os.remove(path)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8150, debug=True, use_reloader=False)