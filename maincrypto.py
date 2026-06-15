from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
import os
import sys
import json
import uuid
from werkzeug.utils import secure_filename
from werkzeug.wrappers import Response
from datetime import datetime
from typing import Union, Tuple
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(DecimalEncoder, self).default(obj)


def _to_dec(valor, default="0") -> Decimal:
    if valor is None or str(valor).strip() == "":
        return Decimal(default)
    s = str(valor).replace(",", ".")
    try:
        return Decimal(s)
    except:
        return Decimal(default)


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.accounting.fifo_calculator import TaxEngine
from src.accounting.stock_calculator import StockTaxEngine
from src.tax_compliance.core.irpf_calculator import IRPFCalculator
from src.domain.fiscal_entities import WorkIncome
from src.ingestion.file_classifier import FileClassifier

import dotenv

dotenv.load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


@app.errorhandler(413)
def request_entity_too_large(error) -> Union[Response, Tuple[str, int]]:
    flash("Error: El archivo subido excede el límite permitido de 16MB.", "danger")
    return redirect(url_for("index"))


secret_file = os.path.join(os.path.dirname(__file__), ".secret")
if os.path.exists(secret_file):
    with open(secret_file, "r") as f:
        default_secret = f.read().strip()
else:
    default_secret = os.urandom(24).hex()
    try:
        with open(secret_file, "w") as f:
            f.write(default_secret)
    except:
        pass
app.secret_key = os.getenv("FLASK_SECRET_KEY", default_secret)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def get_user_upload_folder():
    if "uid" not in session:
        session["uid"] = uuid.uuid4().hex
    user_folder = os.path.join(UPLOAD_FOLDER, session["uid"])
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    return user_folder


@app.route("/")
def index():
    user_folder = get_user_upload_folder()
    prefs = session.get("platform_prefs", {})
    inventory = FileClassifier.get_inventory(user_folder, prefs)
    mailbox = [{"name": f, "platform": prefs.get(f, "auto")} for f in inventory.keys()]
    return render_template("index.html", mailbox=mailbox, platform_prefs=prefs)


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return redirect(request.url)
    file = request.files["file"]
    if file.filename == "":
        return redirect(request.url)

    user_folder = get_user_upload_folder()
    safe_filename = secure_filename(file.filename)
    file.save(os.path.join(user_folder, safe_filename))
    return redirect(url_for("index"))


@app.route("/calculate", methods=["POST"])
def calculate():
    try:
        fiscal_year = int(request.form.get("year", 2025))
        region = request.form.get("region", "comun")
        income = _to_dec(request.form.get("income", "0"))
        ret = _to_dec(request.form.get("retention", "0"))
        ss = _to_dec(request.form.get("ss_expenses", "0"))

        from src.ingestion.binance_reader import BinanceIngestor
        from src.ingestion.universal_reader import UniversalHeuristicParser

        binance_ingestor = BinanceIngestor()
        universal_ingestor = UniversalHeuristicParser()
        prefs = session.get("platform_prefs", {})

        # --- RECOLECCIÓN INDEPENDIENTE ---
        all_trades = []
        all_dividends = []
        all_warnings = []
        stock_trades = []
        stock_dividends = []

        user_folder = get_user_upload_folder()
        inventory = FileClassifier.get_inventory(user_folder, prefs)

        for f, meta in inventory.items():
            f_path = os.path.join(user_folder, f)
            platform = str(prefs.get(f, "auto")).lower().strip()

            if "binance" in platform:
                binance_ingestor.process_file(f_path)
            elif "degiro" in platform:
                from src.ingestion.degiro_reader import parse as parse_degiro

                t, d = parse_degiro(f_path)
                stock_trades.extend(t)
                stock_dividends.extend(d)
            elif "t212" in platform or "trading" in platform:
                from src.ingestion.trading212_reader import parse as parse_t212

                t, d = parse_t212(f_path)
                stock_trades.extend(t)
                stock_dividends.extend(d)
            elif platform == "auto" or not platform:
                # Saltar archivos no confirmados por el usuario
                continue
            else:
                if universal_ingestor.process_file(f_path):
                    all_trades.extend(universal_ingestor.transactions)
                    all_dividends.extend(universal_ingestor.dividends)

        # --- MOTOR CRYPTO ---
        all_trades.extend(binance_ingestor.transactions)
        all_trades.sort(key=lambda x: x.date)
        all_dividends.extend(binance_ingestor.dividends)
        all_warnings.extend(binance_ingestor.warnings)

        engine = TaxEngine(tax_year=fiscal_year)
        engine.process_trades(all_trades)
        engine.process_dividends(all_dividends)
        work = WorkIncome(retribuciones_dinerarias=income, retenciones=ret, gastos_deducibles=ss)

        if stock_trades:
            stock_engine = StockTaxEngine(tax_year=fiscal_year)
            stock_engine.process_trades(stock_trades)
            stock_engine.process_dividends(stock_dividends)
            stock_engine.apply_wash_sale_rules()
            all_warnings.extend(stock_engine.warnings)
        else:
            stock_engine = None

        calculator = IRPFCalculator(
            crypto_events=engine.tax_events,
            stock_events=stock_engine.tax_events if stock_engine else [],
            dividends=engine.dividends + (stock_engine.dividends if stock_engine else []),
            work=work,
            region=region,
        )
        summary = calculator.calculate()

        # Generar Excel (opcional)
        # generate_audit_excel(engine.tax_events, engine.dividends, os.path.join(UPLOAD_FOLDER, "audit_crypto.xlsx"))
        # generate_stock_audit_excel(stock_engine.tax_events, stock_engine.dividends, os.path.join(UPLOAD_FOLDER, "audit_stock.xlsx"))

        return render_template(
            "result.html",
            summary=summary,
            warnings=all_warnings + engine.warnings,
        )
    except Exception as e:
        flash(f"Error en el cálculo: {str(e)}", "danger")
        return redirect(url_for("index"))


@app.route("/update_platform", methods=["POST"])
def update_platform():
    data = request.get_json()
    if "platform_prefs" not in session:
        session["platform_prefs"] = {}
    prefs = session["platform_prefs"]
    prefs[data["filename"]] = data["platform"]
    session["platform_prefs"] = prefs
    return jsonify({"status": "ok"})


@app.route("/delete/<path:filename>", methods=["POST"])
def delete_file(filename):
    user_folder = get_user_upload_folder()
    safe_filename = secure_filename(filename)
    path = os.path.join(user_folder, safe_filename)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8150, debug=True, use_reloader=False)
