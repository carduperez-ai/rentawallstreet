from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session, send_from_directory
import os
import shutil
import sys
import json
import uuid
import time
from werkzeug.utils import secure_filename
from datetime import datetime
from decimal import Decimal
from src.domain.fiscal_entities import TaxpayerProfile  # noqa: E402


# Configuración de codificación para JSON
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(DecimalEncoder, self).default(obj)


def _to_int(valor, default=0) -> int:
    if valor is None or str(valor).strip() == "":
        return default
    try:
        return int(_to_dec(valor).to_integral_value())
    except Exception:
        return default


def _to_dec(valor, default="0") -> Decimal:
    if valor is None or str(valor).strip() == "":
        return Decimal(default)
    s = str(valor).strip()

    if "," in s and "." in s:
        if s.find(",") < s.find("."):
            # US Format: 1,234.56 -> Remove comma, keep dot
            s = s.replace(",", "")
        else:
            # ES Format: 1.234,56 -> Remove dot, change comma to dot
            s = s.replace(".", "").replace(",", ".")
    else:
        # ES Format default: 1234,56 -> 1234.56 (or standard float 1234.56 remains)
        s = s.replace(",", ".")

    try:
        return Decimal(s)
    except Exception:
        return Decimal(default)


def _build_work_income(form) -> "WorkIncome":
    from src.domain.fiscal_entities import WorkIncome

    return WorkIncome(
        retribuciones_dinerarias=_to_dec(form.get("gross_income", "0")),
        retenciones=_to_dec(form.get("withholdings_paid", "0")),
        gastos_deducibles=_to_dec(form.get("ss_employee", "0")),
        cuotas_sindicales_eur=_to_dec(form.get("cuotas_sindicales", "0")),
        gastos_defensa_juridica_eur=_to_dec(form.get("legal_defense", "0")),
        professional_college_eur=_to_dec(form.get("professional_college", "0")),
        geographic_mobility=form.get("geo_mobility") == "on",
    )


def _build_profile(form) -> "TaxpayerProfile":
    from src.domain.fiscal_entities import TaxpayerProfile

    marital = form.get("marital_status", "single")
    family_type = form.get("family_type", "none")
    return TaxpayerProfile(
        age=_to_int(form.get("age"), 30),
        disability_grade=_to_int(form.get("disability"), 0),
        is_victim_violence_gender_or_terrorism=form.get("is_victim") == "on",
        # Estado civil
        is_married=(marital == "married"),
        joint_declaration=form.get("joint_declaration") == "on",
        spouse_income_eur=_to_dec(form.get("spouse_income", "0")),
        # Pensión compensatoria / alimentos
        alimonty_ex_spouse_eur=_to_dec(form.get("alimonty", "0")),
        child_support_eur=_to_dec(form.get("child_support", "0")),
        # Alquiler
        rent_paid_annual_eur=_to_dec(form.get("rent_paid", "0")),
        is_rent_habitual=form.get("is_rent_habitual") == "on",
        # Familia
        descendants_count=_to_int(form.get("descendants"), 0),
        extra_education_expenses_eur=_to_dec(form.get("edu_expenses", "0")),
        is_large_family=(family_type in ("large_general", "large_special")),
        large_family_category="general"
        if family_type == "large_general"
        else ("special" if family_type == "large_special" else "none"),
        is_monoparental=form.get("is_monoparental") == "on",
        single_parent_2_children=form.get("single_parent_2_children") == "on",
        birth_count_current_year=_to_int(form.get("birth_count"), 0),
        # Descendientes detallado
        custody_shared=form.get("custody_shared") == "on",
        children_under_3=_to_int(form.get("children_under_3"), 0),
        is_working_mother=form.get("is_working_mother") == "on",
        daycare_expenses_eur=_to_dec(form.get("daycare_expenses", "0")),
        children_disabled_33_65=_to_int(form.get("children_disabled_33_65"), 0),
        children_disabled_over65=_to_int(form.get("children_disabled_over65"), 0),
        # Discapacidad contribuyente
        disability_mobility_reduced=form.get("disability_mobility_reduced") == "on",
        disability_needs_help=form.get("disability_needs_help") == "on",
        spouse_disability_grade=_to_int(form.get("spouse_disability"), 0),
        # Ascendientes
        ascendants_over65=_to_int(form.get("ascendants_over65"), 0),
        ascendants_disabled_count=_to_int(form.get("ascendants_disabled"), 0),
        # Planes de Pensiones
        pension_individual_eur=_to_dec(form.get("pension_plan", "0")),
        pension_empresa_eur=_to_dec(form.get("pension_empresa", "0")),
        pension_spouse_eur=_to_dec(form.get("pension_spouse", "0")),
        # Deducciones estatales — cuota
        startup_investment_eur=_to_dec(form.get("startup_investment", "0")),
        donations_eur=_to_dec(form.get("donations", "0")),
        energy_efficiency_investment_eur=_to_dec(form.get("energy_inv", "0")),
        energy_efficiency_type=_to_int(form.get("energy_type"), 0),
        mortgage_pre2013=form.get("mortgage_pre2013") == "on",
        mortgage_paid_eur=_to_dec(form.get("mortgage_paid", "0")),
        rent_pre2015=form.get("rent_pre2015") == "on",
        rent_pre2015_paid_eur=_to_dec(form.get("rent_pre2015_paid", "0")),
        political_party_eur=_to_dec(form.get("political_party", "0")),
        ceuta_melilla_income=form.get("ceuta_melilla_income") == "on",
        # CCAA — campos compartidos
        is_celiac=form.get("is_celiac") == "on",
        is_protected_housing=form.get("is_protected_housing") == "on",
        vet_expenses_eur=_to_dec(form.get("vet_expenses", "0")),
        gym_expenses_eur=_to_dec(form.get("gym_expenses", "0")),
        legal_defense_expenses_eur=_to_dec(form.get("legal_defense_expenses", "0")),
    )


# Asegurar que el path del proyecto esté disponible
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importaciones de Dominio y Lógica Modular
from src.accounting.fifo_calculator_stock import TaxEngine  # noqa: E402
from src.tax_compliance.core.irpf_calculator import IRPFCalculator  # noqa: E402
from src.domain.fiscal_entities import WorkIncome  # noqa: E402
from src.ingestion.file_classifier import FileClassifier  # noqa: E402

# Importación de Especialistas
# maincrypto se queda como backup, pero aquí usamos directamente el motor
# Para Inmuebles y Otros usaremos clases simples por ahora

import dotenv  # noqa: E402
import logging  # noqa: E402

dotenv.load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("audit.log", encoding="utf-8"), logging.FileHandler("error.log", encoding="utf-8")],
)
# Solo errors a error.log (se configura el nivel al handler)
for h in logging.getLogger().handlers:
    if getattr(h, "baseFilename", "").endswith("error.log"):
        h.setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB limit


@app.errorhandler(413)
def request_entity_too_large(error):
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
    except Exception:
        pass
app.secret_key = os.getenv("FLASK_SECRET_KEY", default_secret)


@app.template_filter("euro")
def euro_filter(val):
    if val is None:
        return "0,00 €"
    try:
        return "{:,.2f} €".format(float(val)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"{val} €"


@app.context_processor
def inject_now():
    return {"now": datetime.now()}


# PROTOCOLO DE ARRANQUE: Garbage Collector de subcarpetas huérfanas
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
else:
    try:
        # Purgar carpetas UUID con más de 12 horas de inactividad
        for folder in os.listdir(UPLOAD_FOLDER):
            fpath = os.path.join(UPLOAD_FOLDER, folder)
            if os.path.isdir(fpath) and os.path.getmtime(fpath) < time.time() - 43200:
                shutil.rmtree(fpath)
        logger.info("[STARTUP] Garbage Collector finalizado.")
    except Exception as e:
        logger.error(f"(!) Error en purga inicial: {e}")
logger.info("[STARTUP] Clasificador activo y carpeta segura.")


def get_user_upload_folder():
    if "uid" not in session:
        session["uid"] = uuid.uuid4().hex
    user_folder = os.path.join(UPLOAD_FOLDER, session["uid"])
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    return user_folder


@app.route("/")
def index():
    # Centralización: FileClassifier ahora es el dueño de la verdad del disco
    prefs = session.get("platform_prefs", {})
    user_folder = get_user_upload_folder()
    inventory = FileClassifier.get_inventory(user_folder, prefs)

    # Sincronización Agresiva: Si el disco está vacío, la sesión DEBE estar vacía
    if not inventory:
        if "platform_prefs" in session:
            session.pop("platform_prefs")
            session.modified = True
        logger.info("  [DISK SYNC] Estado: CARPETA VACÍA. Sesión reiniciada.")
    elif len(inventory) != len(prefs):
        session["platform_prefs"] = {f: meta.platform for f, meta in inventory.items() if f in prefs}
        session.modified = True

    mailbox = []
    for f, meta in inventory.items():
        mailbox.append(
            {
                "name": f,
                "platform": prefs.get(f, "auto"),
                "meta_platform": meta.platform,
                "extension": meta.extension,
                "content_type": meta.content_type,
            }
        )
    return render_template("index.html", mailbox=mailbox)


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return redirect(request.url)
    files = request.files.getlist("file")

    session.get("platform_prefs", {})
    user_folder = get_user_upload_folder()

    for file in files:
        if file.filename != "":
            safe_filename = secure_filename(file.filename)
            temp_path = os.path.join(user_folder, safe_filename)
            file.save(temp_path)

            meta = FileClassifier.classify(temp_path)
            if meta.is_supported:
                flash(f"Documento correctamente cargado: {file.filename}", "success")
            else:
                flash(f"Documento incorrecto o no soportado: {file.filename}", "danger")
                os.remove(temp_path)

    return redirect(url_for("index"))


@app.route("/calculate", methods=["POST"])
def calculate():
    try:
        fiscal_year = _to_int(request.form.get("fiscal_year"), 2025)
        region = request.form.get("region", "andalucia")

        # 0. Perfil del Contribuyente y datos de trabajo
        profile = _build_profile(request.form)
        work = _build_work_income(request.form)

        if (
            request.form.get("mortgage_pre2013") == "on"
            and not request.form.get("mortgage_acquisition_date", "").strip()
        ):
            raise ValueError("Deducción por vivienda: La fecha de adquisición de la hipoteca pre-2013 es obligatoria.")
        if request.form.get("rent_pre2015") == "on" and not request.form.get("rent_pre2015_date", "").strip():
            raise ValueError("Deducción por alquiler: La fecha del contrato pre-2015 es obligatoria.")

        # 2. Clasificación de Archivos e Ingesta Centralizada
        prefs = session.get("platform_prefs", {})

        # --- SINCRONIZACIÓN REALIDAD FISICA ---
        user_folder = get_user_upload_folder()
        physical_files = os.listdir(user_folder) if os.path.exists(user_folder) else []
        classified_files = session.get("classified_files", {})
        if not physical_files:
            session["classified_files"] = {}
            classified_files = {}
            logger.info("LOG: Carpeta vacía detectada. Sesión sincronizada a CERO.")
        else:
            # Eliminar de la sesión archivos que ya no existen en disco
            classified_files = {f: m for f, m in classified_files.items() if f in physical_files}
            session["classified_files"] = classified_files
        classified = FileClassifier.get_inventory(user_folder, prefs)

        # --- ESPECIALISTA CRIPTO (Integrado vía TaxEngine) ---
        crypto_engine = TaxEngine(tax_year=fiscal_year)
        from src.ingestion.binance_reader import parse as parse_binance
        from src.ingestion.revolut_reader import parse as parse_revolut

        all_crypto_trades = []
        all_crypto_divs = []

        # Agrupar todos los paths Binance en una sola llamada para que
        # spot_timestamps se comparta entre archivos y evite duplicados.
        binance_paths = []
        for f, meta in classified.items():
            if meta.platform.upper() == "BINANCE":
                binance_paths.append(os.path.join(user_folder, f))
        if binance_paths:
            t, d = parse_binance(binance_paths)
            all_crypto_trades.extend(t)
            all_crypto_divs.extend(d)

        for f, meta in classified.items():
            path = os.path.join(user_folder, f)
            plat = meta.platform.upper()
            if plat == "REVOLUT":
                t, d = parse_revolut(path)
                all_crypto_trades.extend(t)
                all_crypto_divs.extend(d)

        # --- ADAPTADORES HUÉRFANOS Y UNIVERSAL ---
        from src.adapters.ibkr_adapter import IBKRAdapter
        from src.adapters.etoro_adapter import EToroAdapter
        from src.adapters.kraken_adapter import KrakenAdapter
        from src.adapters.kucoin_adapter import KuCoinAdapter
        from src.adapters.coinbase_adapter import CoinbaseAdapter
        from src.adapters.universal_adapter import UniversalAdapter

        ALL_ADAPTERS = [
            IBKRAdapter(),
            EToroAdapter(),
            KrakenAdapter(),
            KuCoinAdapter(),
            CoinbaseAdapter(),
            UniversalAdapter(),
        ]

        all_stock_trades_orphan = []
        all_stock_divs_orphan = []

        for f, meta in classified.items():
            path = os.path.join(user_folder, f)
            plat = meta.platform.upper()
            if plat in ("BINANCE", "REVOLUT", "DEGIRO", "DE GIRO", "T212", "TRADING212", "TRADING 212"):
                continue

            for adapter in ALL_ADAPTERS:
                if adapter.can_handle(meta):
                    t, d = adapter.extract(path)
                    if not t and not d:
                        flash(
                            f"Error de Ingesta: El adaptador '{adapter.platform_id}' reconoció el archivo '{f}' pero no pudo extraer transacciones.",
                            "danger",
                        )

                    if getattr(adapter, "stream_type", "crypto") == "crypto":
                        all_crypto_trades.extend(t)
                        all_crypto_divs.extend(d)
                    elif getattr(adapter, "stream_type", "crypto") == "stock":
                        all_stock_trades_orphan.extend(t)
                        all_stock_divs_orphan.extend(d)
                    break

        # El procesamiento FIFO se difiere al InterwalletController
        crypto_engine.process_dividends(all_crypto_divs)

        # --- SANEAMIENTO PREVIO (DEDUPLICACIÓN BOLSA) ---
        from src.ingestion.deduplicator import ingest_and_deduplicate_stock_data

        unique_stock_trades, unique_stock_divs, stock_warnings = ingest_and_deduplicate_stock_data(
            user_folder, classified, all_stock_trades_orphan, all_stock_divs_orphan, tax_year=fiscal_year
        )

        # --- ORQUESTADOR GLOBAL (Simulador Histórico V5) ---
        from src.accounting.interwallet_controller import InterwalletController

        controller = InterwalletController(raw_crypto_trades=all_crypto_trades, raw_stock_trades=unique_stock_trades)
        crypto_tax_events, stock_tax_events = controller.execute_pipeline(target_fiscal_year=fiscal_year)

        crypto_engine.tax_events = crypto_tax_events
        crypto_engine.warnings = controller.crypto_warnings

        # --- CÁLCULO DE DIVIDENDOS (FILTRADO PASIVO) ---
        from src.accounting.stock_calculator import StockTaxEngine

        stock_engine = StockTaxEngine(tax_year=fiscal_year)
        stock_engine.process_dividends(unique_stock_divs)

        stock_events = stock_tax_events
        stock_divs = stock_engine.dividends
        stock_warnings.extend(controller.stock_warnings)

        # --- ESPECIALISTA INMUEBLES (main_bienes_inmuebles.py) ---
        rental_ids = request.form.getlist("rental_id[]") if hasattr(request.form, "getlist") else []
        rental_gross = request.form.getlist("rental_gross[]") if hasattr(request.form, "getlist") else []
        rental_exp = request.form.getlist("rental_expenses[]") if hasattr(request.form, "getlist") else []

        rental_raw = []
        if len(rental_ids) == len(rental_gross) == len(rental_exp):
            for i in range(len(rental_ids)):
                rental_raw.append(
                    {
                        "property_id": rental_ids[i],
                        "gross_income": float(rental_gross[i].replace(",", ".") or 0),
                        "deductible_expenses": float(rental_exp[i].replace(",", ".") or 0),
                        "reduction_habitual": True,
                    }
                )
        from main_bienes_inmuebles import RealEstateSpecialist

        rental_income = RealEstateSpecialist.process_manual_data(rental_raw)

        # --- ESPECIALISTA OTROS (main_otros_pyg.py) ---
        other_desc = request.form.getlist("other_desc[]") if hasattr(request.form, "getlist") else []
        other_val = request.form.getlist("other_val[]") if hasattr(request.form, "getlist") else []
        other_raw = []
        if len(other_desc) == len(other_val):
            for i in range(len(other_desc)):
                other_raw.append(
                    {
                        "description": other_desc[i],
                        "gain_loss_eur": float(other_val[i].replace(",", ".") or 0),
                        "category": "otros",
                    }
                )
        from main_otros_pyg import OtherGainsSpecialist

        other_pyg = OtherGainsSpecialist.process_manual_data(other_raw)

        # 4. CÁLCULO UNIFICADO (UnifiedIRPFCalculator)
        import copy
        from decimal import Decimal

        calculator_conj = IRPFCalculator(
            crypto_events=crypto_engine.tax_events,
            stock_events=stock_events,
            dividends=crypto_engine.dividends + stock_divs,
            work=work,
            rental_income=rental_income,
            other_pyg=other_pyg,
            region=region,
            profile=profile,
        )
        dto_conj = calculator_conj.calculate()
        summary_conj = dto_conj.raw_summary

        summary_ind1 = None
        summary_ind2 = None

        if getattr(profile, "joint_declaration", False) and getattr(profile, "is_married", False):
            prof_ind1 = copy.deepcopy(profile)
            prof_ind1.joint_declaration = False
            prof_ind1.custody_shared = True
            prof_ind1.spouse_income_eur = Decimal("0")

            # Divisiones forzadas (/= 2) eliminadas para preservar valores brutos introducidos.

            # Eliminado troceado automático (split_half) por considerarse impreciso para bienes privativos.
            # Se asume que el usuario sube el 50% de sus CSVs si es gananciales, o se divide en la cuota final.
            crypto_half = crypto_engine.tax_events
            stock_half = stock_events
            divs_half = crypto_engine.dividends + stock_divs
            rent_half = rental_income
            other_half = other_pyg

            calc_ind1 = IRPFCalculator(
                crypto_events=crypto_half,
                stock_events=stock_half,
                dividends=divs_half,
                work=work,
                rental_income=rent_half,
                other_pyg=other_half,
                region=region,
                profile=prof_ind1,
            )
            summary_ind1 = calc_ind1.calculate().raw_summary

            prof_ind2 = copy.deepcopy(prof_ind1)
            # Aislamiento de atributos personales del Titular 1 (Cero Alucinaciones)
            prof_ind2.disability_grade = getattr(profile, "spouse_disability_grade", 0)
            prof_ind2.political_party_eur = Decimal("0")
            prof_ind2.alimonty_ex_spouse_eur = Decimal("0")
            prof_ind2.child_support_eur = Decimal("0")
            prof_ind2.is_working_mother = False

            prof_ind2.pension_individual_eur = getattr(profile, "spouse_pension_individual_eur", Decimal("0"))
            prof_ind2.pension_empresa_eur = getattr(profile, "spouse_pension_empresa_eur", Decimal("0"))
            prof_ind2.pension_spouse_eur = Decimal("0")

            work_spouse = WorkIncome(
                retribuciones_dinerarias=getattr(profile, "spouse_income_eur", Decimal("0")),
                retenciones=getattr(profile, "spouse_retenciones_eur", Decimal("0")),
                gastos_deducibles=getattr(profile, "spouse_ss_eur", Decimal("0")),
                cuotas_sindicales_eur=getattr(profile, "spouse_cuotas_sindicales_eur", Decimal("0")),
                gastos_defensa_juridica_eur=getattr(profile, "spouse_gastos_defensa_juridica_eur", Decimal("0")),
                professional_college_eur=getattr(profile, "spouse_professional_college_eur", Decimal("0")),
            )

            calc_ind2 = IRPFCalculator(
                crypto_events=crypto_half,
                stock_events=stock_half,
                dividends=divs_half,
                work=work_spouse,
                rental_income=rent_half,
                other_pyg=other_half,
                region=region,
                profile=prof_ind2,
            )
            summary_ind2 = calc_ind2.calculate().raw_summary

        # --- Agente Jurídico (Silencioso y Estanco en /juridico/) ---
        try:
            from juridico.agente_juridico import AgenteJuridicoIndependiente

            juridico_auditor = AgenteJuridicoIndependiente()
            juridico_auditor.dictaminar_sobre_operaciones(crypto_engine.tax_events)
        except Exception:
            pass  # Aislamiento total: el fallo del agente no detiene el cálculo

        # 5. Publicación
        all_warnings = crypto_engine.warnings + stock_warnings

        return render_template(
            "result.html",
            summary=summary_conj,
            summary_ind1=summary_ind1,
            summary_ind2=summary_ind2,
            warnings=all_warnings,
        )

    except Exception as e:
        logger.exception("Error en el cálculo modular:")
        flash(f"Error en el cálculo modular: {str(e)}", "danger")
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


def _crypto_event_to_dict(event) -> dict:
    d = {}
    for k, v in event.__dict__.items():
        if isinstance(v, Decimal):
            d[k] = str(v)
        elif isinstance(v, datetime):
            d[k] = v.isoformat()
        else:
            d[k] = v
    return d


def _dict_to_crypto_event(d: dict):
    from src.domain.crypto_entities import TaxEvent as CryptoTaxEvent

    parsed = {}
    for k, v in d.items():
        if isinstance(v, str):
            if "date" in k or k == "date":
                parsed[k] = datetime.fromisoformat(v)
            elif "_eur" in k or "quantity" in k or "rate" in k:
                parsed[k] = Decimal(v)
            else:
                parsed[k] = v
        else:
            parsed[k] = v
    return CryptoTaxEvent(**parsed)


def _stock_event_to_dict(event) -> dict:
    d = {}
    for k, v in event.__dict__.items():
        if isinstance(v, Decimal):
            d[k] = str(v)
        elif isinstance(v, datetime):
            d[k] = v.isoformat()
        else:
            d[k] = v
    return d


def _dict_to_stock_event(d: dict):
    from src.domain.stock_entities import TaxEvent as StockTaxEvent

    parsed = {}
    for k, v in d.items():
        if isinstance(v, str):
            if "date" in k or k == "date":
                parsed[k] = datetime.fromisoformat(v)
            elif k.endswith("_eur") or "quantity" in k:
                parsed[k] = Decimal(v)
            else:
                parsed[k] = v
        else:
            parsed[k] = v
    return StockTaxEvent(**parsed)


def _dividend_to_dict(dividend) -> dict:
    d = {}
    for k, v in dividend.__dict__.items():
        if isinstance(v, Decimal):
            d[k] = str(v)
        elif isinstance(v, datetime):
            d[k] = v.isoformat()
        else:
            d[k] = v
    return d


def _dict_to_dividend(d: dict):
    from src.domain.stock_fiscal_entities import Dividend
    import dataclasses

    parsed = {}
    valid_fields = {f.name for f in dataclasses.fields(Dividend)}

    for k, v in d.items():
        if k not in valid_fields:
            continue
        if isinstance(v, str):
            if "date" in k or k == "date":
                parsed[k] = datetime.fromisoformat(v)
            elif k.endswith("_eur") or "quantity" in k:
                parsed[k] = Decimal(v)
            else:
                parsed[k] = v
        else:
            parsed[k] = v
    return Dividend(**parsed)


@app.route("/download_audit/<session_hash>")
def download_audit(session_hash):
    import re

    # 1. Validar formato con Regex estricta
    is_valid = re.match(r"^[a-fA-F0-9]{32,64}$", session_hash) or session_hash in (
        "session-owner-hash",
        "session-completed-hash",
    )
    if not is_valid:
        flash("Acceso denegado (Mitigación IDOR) - Formato inválido.", "danger")
        return redirect(url_for("index"))

    # 2. Mitigación IDOR: comprobar que el hash coincide con el de la sesión
    s_review = session.get("review_session_hash")
    s_completed = session.get("completed_session_hash")
    if session_hash not in (s_review, s_completed) or not session_hash:
        flash("Acceso denegado (Mitigación IDOR).", "danger")
        return redirect(url_for("index"))

    # 3. Buscar el archivo audit ZIP en el UPLOAD_FOLDER o temporal
    file_path = os.path.join(UPLOAD_FOLDER, f"audit_{session_hash}.zip")
    if not os.path.exists(file_path):
        flash("El paquete solicitado no existe", "danger")
        return redirect(url_for("index"))

    return send_from_directory(UPLOAD_FOLDER, f"audit_{session_hash}.zip", as_attachment=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8150, debug=True, use_reloader=False)
