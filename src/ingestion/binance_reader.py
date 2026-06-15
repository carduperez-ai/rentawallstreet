import os  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import subprocess  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import List, Dict, Tuple, Any  # noqa: E402
from decimal import Decimal  # noqa: E402


# =====================================================================
# 1. COMPROBADOR Y AUTO-INSTALADOR DE DEPENDENCIAS
# =====================================================================
def verificar_dependencias():
    librerias_requeridas = ["pandas", "openpyxl", "pdfplumber"]
    faltantes = []

    for lib in librerias_requeridas:
        try:
            __import__(lib)
        except ImportError:
            faltantes.append(lib)

    if faltantes:
        print(f"\n⚠️ Faltan librerías para leer los archivos: {', '.join(faltantes)}")
        respuesta = input("¿Deseas que el programa las instale automáticamente ahora? (s/n): ").strip().lower()
        if respuesta == "s":
            print("Instalando librerías, por favor espera...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", *faltantes])
                print("✅ Librerías instaladas con éxito.\n")
            except Exception as e:
                print(f"❌ Error al instalar: {e}")
                print(f"Ejecuta en tu terminal: pip install {' '.join(faltantes)}")
                sys.exit(1)
        else:
            print("❌ Abortando ejecución.")
            sys.exit(1)


# verificar_dependencias() eliminado: ejecutar input() y sys.exit() al importar
# un módulo bloquea el servidor Flask en producción. Las dependencias deben
# verificarse en el arranque del servidor, no en import-time.

import pandas as pd  # noqa: E402

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# IMPORTACIONES DE TU PROYECTO (Mantenidas intactas)
from src.domain.crypto_entities import Trade  # noqa: E402
from src.domain.fiscal_entities import Dividend  # noqa: E402
from src.accounting.currency_valuation import oracle  # noqa: E402


# =====================================================================
# 2. MOTOR PRINCIPAL: UNIVERSAL INGESTOR & FIAT MIRROR LEDGER
# =====================================================================
class BinanceIngestor:
    """
    Lector Nativo para Binance (Spot e Historial).
    Implementa arquitectura Fiat Mirror Ledger específica para Binance.
    """

    def __init__(self):
        self.processed_files: List[Dict] = []
        self.warnings: List[str] = []
        self.dividends: List[Dividend] = []

        self.spot_dfs: List[pd.DataFrame] = []
        self.trans_dfs: List[pd.DataFrame] = []
        self.spot_timestamps = set()
        self._ZERO = Decimal("0")

    def process_file(self, file_path: str, platform_hint: str = None) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)
        df = None

        try:
            # 1. MOTOR DE EXTRACCIÓN UNIVERSAL (Excel / CSV)
            header_idx = 0
            if ext in (".xlsx", ".xls"):
                df_raw = pd.read_excel(file_path, header=None)
                # Buscar la fila que parece ser el header
                for i in range(min(50, len(df_raw))):
                    row_vals = [str(x).lower() for x in df_raw.iloc[i].values if pd.notna(x)]
                    if (
                        sum(
                            1
                            for val in row_vals
                            if any(
                                k in val
                                for k in [
                                    "tiempo",
                                    "time",
                                    "fecha",
                                    "date",
                                    "moneda",
                                    "asset",
                                    "coin",
                                    "cambio",
                                    "change",
                                ]
                            )
                        )
                        >= 2
                    ):
                        header_idx = i
                        break
                df = pd.read_excel(file_path, header=header_idx)
                print(f">>> [CHIVATO] Cabecera encontrada en fila {header_idx} para {filename}")

            elif ext == ".csv":
                # Intentar detectar el header en CSV
                df_raw = pd.read_csv(
                    file_path, sep=None, engine="python", header=None, encoding="utf-8-sig", on_bad_lines="skip"
                )
                for i in range(min(20, len(df_raw))):
                    row_vals = [str(x).lower() for x in df_raw.iloc[i].values if pd.notna(x)]
                    if (
                        sum(
                            1
                            for val in row_vals
                            if any(
                                k in val
                                for k in [
                                    "tiempo",
                                    "time",
                                    "fecha",
                                    "date",
                                    "moneda",
                                    "asset",
                                    "coin",
                                    "cambio",
                                    "change",
                                ]
                            )
                        )
                        >= 2
                    ):
                        header_idx = i
                        break
                df = pd.read_csv(
                    file_path, sep=None, engine="python", header=header_idx, encoding="utf-8-sig", on_bad_lines="skip"
                )

            elif ext == ".pdf":
                all_rows = []
                import pdfplumber

                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if not text:
                            continue
                        for line in text.split("\n"):
                            line = line.strip()
                            if any(
                                h in line.lower()
                                for h in ["id de usuario", "historial de", "nombre:", "correo", "www.binance", "page "]
                            ):
                                continue
                            parts = re.split(r"  +", line)
                            if len(parts) >= 5 and re.match(r"^\d{7,}$", parts[0]):
                                if (
                                    re.match(r"^\d{2}-\d{2}-\d{2}$", parts[1])
                                    and len(parts) > 2
                                    and re.match(r"^\d{2}:\d{2}:\d{2}$", parts[2])
                                ):
                                    parts = [parts[0], parts[1] + " " + parts[2]] + parts[3:]
                                row = parts[:7] + ([""] * (7 - len(parts[:7])))
                                all_rows.append(row)
                if not all_rows:
                    self.warnings.append(f"No se pudo extraer contenido del PDF: {filename}")
                    return False
                df = pd.DataFrame(
                    all_rows,
                    columns=["id de usuario", "tiempo", "cuenta", "operacion", "moneda", "cambio", "observacion"],
                )
                header_idx = 0

            else:
                self.warnings.append(f"Formato no soportado: {ext}")
                return False

            # 2. NORMALIZACIÓN DE CABECERAS
            raw_headers = []
            for h in df.columns:
                if pd.isna(h) or str(h).startswith("Unnamed:"):
                    raw_headers.append("empty_col")
                else:
                    clean_h = str(h).strip().lower()
                    clean_h = re.sub(
                        r"[^a-z0-9_]",
                        "",
                        clean_h.replace(" ", "_").replace("ó", "o").replace("í", "i").replace("á", "a"),
                    )
                    raw_headers.append(clean_h if clean_h else "empty_col")

            headers = []
            for h in raw_headers:
                new_h = h
                count = 1
                while new_h in headers:
                    new_h = f"{h}_{count}"
                    count += 1
                headers.append(new_h)

            df.columns = headers
            data_df = df.reset_index(drop=True)

            # 3. IDENTIFICACIÓN DE PLATAFORMA
            if any(x in h for h in headers for x in ["par", "pair"]):
                self.spot_dfs.append(data_df)
                platform = "Binance Spot"
            else:
                self.trans_dfs.append(data_df)
                platform = "Binance History"
                self._process_raw_dividends(data_df)

            self.processed_files.append({"name": filename, "platform": platform, "tx_count": len(data_df)})
            return True

        except Exception as e:
            self.warnings.append(f"Error procesando {filename}: {str(e)}")
            return False

    def _process_raw_dividends(self, df: pd.DataFrame):
        pass  # Placeholder mantenido para tu arquitectura externa

    @property
    def transactions(self) -> List[Trade]:
        """Extrae todas las operaciones normalizadas de los archivos de Binance usando Consolidación Neta."""
        mirror_table = []
        self.spot_timestamps = set()

        # PRELOAD BATCH: Recopilar todos los timestamps y activos únicos
        datasets_to_preload = set()
        for df in self.spot_dfs:
            t_cols = [c for c in df.columns if any(x in c.lower() for x in ["tiempo", "time", "date"])]
            idx_t = t_cols[-1] if t_cols else "tiempo"
            idx_p = next((c for c in df.columns if any(x in c.lower() for x in ["par", "pair"])), "par")
            idx_fee_col = next(
                (c for c in df.columns if any(x in c.lower() for x in ["tarifa", "fee", "comisi"])), None
            )

            for _, row in df.iterrows():
                if pd.isna(row[idx_t]):
                    continue
                dt = self._parse_date(str(row[idx_t]))
                if dt:
                    pair = str(row[idx_p]).upper()
                    datasets_to_preload.add((self._extract_asset(pair), dt))
                    datasets_to_preload.add((self._extract_quote_asset(pair), dt))
                    if idx_fee_col and pd.notna(row.get(idx_fee_col)):
                        datasets_to_preload.add((self._extract_currency(str(row[idx_fee_col])), dt))

        for df in self.trans_dfs:
            idx_t = next(
                (c for c in df.columns if any(x in c.lower() for x in ["tiempo", "time", "fecha", "date"])), "tiempo"
            )
            idx_c = next((c for c in df.columns if any(x in c.lower() for x in ["moneda", "asset", "coin"])), "moneda")
            for _, row in df.iterrows():
                if pd.isna(row[idx_t]):
                    continue
                dt = self._parse_date(str(row[idx_t]))
                if dt:
                    datasets_to_preload.add((str(row[idx_c]).upper(), dt))

        if datasets_to_preload:
            oracle.preload_batch(datasets_to_preload)

        # 1. CARGA DE TRADES DESDE ARCHIVOS SPOT (Un Trade por fila, sin agrupar)
        for df in self.spot_dfs:
            t_cols = [c for c in df.columns if any(x in c.lower() for x in ["tiempo", "time", "date"])]
            idx_t = t_cols[-1] if t_cols else "tiempo"
            idx_p = next((c for c in df.columns if any(x in c.lower() for x in ["par", "pair"])), "par")
            idx_l = next((c for c in df.columns if any(x in c.lower() for x in ["lado", "side"])), "lado")
            idx_e = next((c for c in df.columns if any(x in c.lower() for x in ["ejecutado", "amount"])), "ejecutado")

            idx_tot_col = None
            for key in ["total", "importe", "cantidad"]:
                idx_tot_col = next((i for i, h in enumerate(df.columns) if key in h.lower()), None)
                if idx_tot_col is not None:
                    break

            col_tot = df.columns[idx_tot_col] if idx_tot_col is not None else "total"
            idx_fee_col = next(
                (c for c in df.columns if any(x in c.lower() for x in ["tarifa", "fee", "comisi"])), None
            )

            for _, row in df.iterrows():
                if pd.isna(row[idx_t]):
                    continue
                dt = self._parse_date(str(row[idx_t]))
                if dt is None:
                    continue  # Fecha inválida: descartar fila
                self.spot_timestamps.add(dt)

                pair = str(row[idx_p]).upper()
                qty = self._clean_val(row[idx_e])
                raw_val = self._clean_val(row[col_tot])

                quote_asset = self._extract_quote_asset(pair)
                val_eur = self._safe_convert(raw_val, quote_asset, dt)

                fee_eur = Decimal("0")
                if idx_fee_col and pd.notna(row.get(idx_fee_col)):
                    f_val = self._clean_val(row[idx_fee_col])
                    f_cur = self._extract_currency(str(row[idx_fee_col]))
                    fee_eur = self._safe_convert(f_val, f_cur, dt)

                mirror_table.append(
                    Trade(
                        date=dt,
                        asset=self._extract_asset(pair),
                        platform="Binance",
                        direction="buy" if any(x in str(row[idx_l]).upper() for x in ["BUY", "COMPRA"]) else "sell",
                        quantity=qty,
                        value_eur=val_eur,
                        fee_eur=fee_eur,
                        asset_type="crypto",
                        notes=f"SPOT | {pair}",
                    )
                )

        # 2. PROCESAMIENTO DE HISTORIAL CON CONSOLIDACIÓN NETA (Agrupación por ID o Ventana de 2s)
        all_history_lines = []
        for df in self.trans_dfs:
            idx_t = next(
                (c for c in df.columns if any(x in c.lower() for x in ["tiempo", "time", "fecha", "date"])), "tiempo"
            )
            idx_op = next(
                (c for c in df.columns if any(x in c.lower() for x in ["operacion", "type", "operation"])), "operacion"
            )
            idx_c = next((c for c in df.columns if any(x in c.lower() for x in ["moneda", "asset", "coin"])), "moneda")
            idx_ch = next(
                (c for c in df.columns if any(x in c.lower() for x in ["cambio", "change", "amount"])), "cambio"
            )
            idx_id = next((c for c in df.columns if any(x in c.lower() for x in ["txid", "transaction id"])), None)

            # Aplicar el robusto _parse_date a toda la columna de tiempo (Surgical Fix)
            df["dt_p"] = df[idx_t].apply(self._parse_date)

            df["chg_signed"] = df[idx_ch].apply(self._parse_decimal_signed)

            for _, row in df.iterrows():
                if pd.isna(row["dt_p"]):
                    continue
                op_raw = str(row[idx_op]).upper()
                # EXCLUSIÓN RADICAL: Ignorar movimientos internos (Staking, Earn, Savings, Fiat)
                # Permitimos DEPOSIT/WITHDRAW solo si son trades externos, pero el staking
                # debe ser transparente para el FIFO.
                asset_row = str(row[idx_c]).upper()
                # EXCLUSIÓN RADICAL: Ignorar movimientos internos
                if any(x in op_raw for x in ["FIAT OCBS", "CASH IN", "CASH OUT", "STAKING", "EARN", "SAVINGS"]):
                    if "STAKING" in op_raw or "EARN" in op_raw or "SAVINGS" in op_raw:
                        # Si es una compra por staking, mantenemos para FIFO si tiene coste real
                        if row["chg_signed"] <= 0:
                            continue
                    else:
                        continue

                # RECONOCIMIENTO DE REVENUE: Asegurar que se procesa como pierna de trade
                if "REVENUE" in op_raw or "BUY" in op_raw or "SOLD" in op_raw:
                    pass  # Permitido
                if any(x in op_raw for x in ["DEPOSIT", "WITHDRAW"]) and asset_row == "EUR":
                    continue

                all_history_lines.append(
                    {
                        "dt": row["dt_p"].replace(tzinfo=None),
                        "op": str(row[idx_op]).upper(),
                        "asset": str(row[idx_c]).upper(),
                        "qty": row["chg_signed"],
                        "tx_id": str(row[idx_id]) if idx_id and pd.notna(row[idx_id]) else None,
                    }
                )

        all_history_lines.sort(key=lambda x: x["dt"])
        groups = {}
        WINDOW_SEC = 2

        for line in all_history_lines:
            t = line["dt"]
            tx_id = line["tx_id"]
            matched_key = None

            if tx_id:
                matched_key = f"ID_{tx_id}"
            else:
                for k in groups.keys():
                    if not k.startswith("ID_"):
                        group_time = groups[k][0]["dt"]
                        if abs((t - group_time).total_seconds()) <= WINDOW_SEC:
                            matched_key = k
                            break

            if matched_key:
                groups[matched_key].append(line)
            else:
                groups[matched_key if matched_key else t.isoformat()] = [line]

        fiat_stables = {"EUR", "USD", "USDT", "USDC", "BUSD", "FDUSD", "DAI"}

        for k, lines in groups.items():
            ts = lines[0]["dt"]
            # Filtro anti-duplicados con SPOT
            if any(abs((ts - st).total_seconds()) < 1 for st in self.spot_timestamps):
                continue

            # A. Consolidación Neta por activo dentro del grupo
            net_by_asset = {}
            for i in lines:
                a = i["asset"]
                net_by_asset[a] = net_by_asset.get(a, Decimal("0")) + i["qty"]

            # B. Cálculo de Comisiones Totales (Multi-Asset)
            total_fee_eur = Decimal("0")
            for i in lines:
                op_up = i["op"]
                if any(x in op_up for x in ["FEE", "COMISI", "COMMISSION"]) or (
                    i["qty"] < 0 and i["asset"] == "BNB" and len(net_by_asset) > 2
                ):
                    total_fee_eur += self._safe_convert(abs(i["qty"]), i["asset"], ts)

            # C. Separación de activos Base y Contrapartida
            base_out = {a: abs(q) for a, q in net_by_asset.items() if q < 0 and a not in fiat_stables and a != "BNB"}
            base_in = {a: q for a, q in net_by_asset.items() if q > 0 and a not in fiat_stables}

            # Contrapartidas (ingresos y gastos fiat/stables)
            counter_in = {a: q for a, q in net_by_asset.items() if q > 0 and a in fiat_stables}
            counter_out = {a: abs(q) for a, q in net_by_asset.items() if q < 0 and a in fiat_stables}

            sum(self._safe_convert(q, a, ts) for a, q in counter_in.items())
            sum(self._safe_convert(q, a, ts) for a, q in counter_out.items())

            # D. Aplicación Estricta LIRPF (Art. 37.1.h y V0999-18)
            # 1. Calcular el valor de mercado individual de cada pata (Fiat + Crypto)
            val_out_eur = sum(self._safe_convert(q, a, ts) for a, q in counter_out.items()) + sum(
                self._safe_convert(q, a, ts) for a, q in base_out.items()
            )

            val_in_eur = sum(self._safe_convert(q, a, ts) for a, q in counter_in.items()) + sum(
                self._safe_convert(q, a, ts) for a, q in base_in.items()
            )

            # 2. Base Imponible: El Mayor de los dos valores (Regla de Permuta)
            swap_value_eur = max(val_out_eur, val_in_eur)

            # 3. Generación de Ventas (Base Out)
            for asset, qty in base_out.items():
                # Prorratear el swap_value_eur por el peso del activo en la salida total
                weight = (self._safe_convert(qty, asset, ts) / val_out_eur) if val_out_eur > 0 else Decimal("0")
                v = swap_value_eur * weight if val_out_eur > 0 else Decimal("0")

                mirror_table.append(
                    Trade(
                        date=ts,
                        asset=asset,
                        platform="Binance",
                        direction="sell",
                        quantity=qty,
                        value_eur=v,
                        fee_eur=total_fee_eur,  # Anti Double-Counting: Se asigna 100% a la primera venta
                        asset_type="crypto",
                        notes=f"History | Group: {k}",
                    )
                )
                total_fee_eur = Decimal("0")  # Solo se deduce una vez si hay multi-ventas

            # 4. Generación de Compras (Base In)
            for asset, qty in base_in.items():
                weight = (self._safe_convert(qty, asset, ts) / val_in_eur) if val_in_eur > 0 else Decimal("0")
                c = swap_value_eur * weight if val_in_eur > 0 else Decimal("0")

                mirror_table.append(
                    Trade(
                        date=ts,
                        asset=asset,
                        platform="Binance",
                        direction="buy",
                        quantity=qty,
                        value_eur=c,
                        fee_eur=Decimal("0"),  # Gasto asignado en Venta
                        asset_type="crypto",
                        notes=f"History | Group: {k}",
                    )
                )

            # 5. Generación del Evento 3 (Enajenación del Gasto en Especie - Anti Inventario Fantasma)
            # Detectamos los activos que fueron pagados como FEE en especie (ej. BNB)
            fee_assets_out = {
                i["asset"]: abs(i["qty"])
                for i in lines
                if i["qty"] < 0
                and (
                    any(x in i["op"] for x in ["FEE", "COMISI", "COMMISSION"])
                    or (i["asset"] == "BNB" and len(net_by_asset) > 2)
                )
            }

            for f_asset, f_qty in fee_assets_out.items():
                if f_asset not in fiat_stables and f_qty > 0:
                    # El coste del fee_eur ya se sumó al total_fee_eur que minora la permuta principal,
                    # pero legalmente el usuario enajenó este token, provocando otra plusvalía/minusvalía.
                    f_val_eur = self._safe_convert(f_qty, f_asset, ts)
                    mirror_table.append(
                        Trade(
                            date=ts,
                            asset=f_asset,
                            platform="Binance",
                            direction="sell",
                            quantity=f_qty,
                            value_eur=f_val_eur,
                            fee_eur=Decimal("0"),  # Su transmisión es el propio fee, no tiene sub-fee
                            asset_type="crypto",
                            notes=f"History | Fee Disposal: {k}",
                        )
                    )

        return sorted(mirror_table, key=lambda x: x.date)

    # =====================================================================
    # 3. UTILIDADES DE LIMPIEZA Y EXTRACCIÓN BLINDADAS
    # =====================================================================
    def _safe_convert(self, amount: Decimal, asset: str, dt: datetime, op: str = "") -> Decimal:
        """Versión segura que informa al usuario si hay fallos de conexión."""
        if amount == 0:
            return Decimal("0")
        try:
            result = self._convert_to_eur(amount, asset, dt)
            if result is None or result == 0:
                fecha_str = dt.strftime("%d/%m/%Y")
                msg = (
                    f"⚠️ FALLO DE CONEXIÓN: No se pudo obtener el precio de {asset} el {fecha_str}. "
                    f"Se ha usado 0.00€ por defecto. Comprueba tu internet o la API de Binance."
                )
                if msg not in self.warnings:
                    self.warnings.append(msg)
                return Decimal("0")
            return result
        except Exception:
            return Decimal("0")

    def _clean_val(self, val):
        if pd.isna(val):
            return Decimal("0")
        res = "".join([c for c in str(val) if c.isdigit() or c == "."])
        try:
            return Decimal(res) if res else Decimal("0")
        except Exception:
            return Decimal("0")

    def _parse_decimal_signed(self, val):
        if pd.isna(val):
            return Decimal("0")
        res = "".join([c for c in str(val) if c.isdigit() or c == "." or c == "-"])
        try:
            return Decimal(res) if res else Decimal("0")
        except Exception:
            return Decimal("0")

    def _split_pair(self, par: str) -> Tuple[str, str]:
        """Divide un par de Binance (ej: SHIBUSDC) en Base (SHIB) y Quote (USDC)."""
        s = str(par).upper().strip()
        # Lista de monedas cotizadas comunes en Binance (ordenadas por longitud desc para evitar falsos positivos)
        quotes = ["USDT", "USDC", "FDUSD", "BUSD", "TUSD", "EUR", "BTC", "ETH", "BNB", "DAI", "TRY"]

        for q in quotes:
            if s.endswith(q) and len(s) > len(q):
                return s[: -len(q)], q

        return s, "UNKNOWN"

    def _extract_asset(self, par):
        base, _ = self._split_pair(par)
        return base

    def _extract_quote_asset(self, par):
        _, quote = self._split_pair(par)
        return quote

    def _extract_currency(self, val_str):
        s = str(val_str).upper()
        # Lista estricta. Si no está aquí, no asume euros.
        for c in ["EUR", "USDC", "USDT", "FDUSD", "BUSD", "DAI", "BTC", "ETH", "BNB"]:
            if c in s:
                return c
        res = "".join([c for c in s if c.isalpha()])
        return res if res else "UNKNOWN"

    def _convert_to_eur(self, amount: Decimal, asset: str, dt: datetime) -> Decimal:
        asset = asset.upper().strip()
        if asset == "EUR":
            return amount

        # 1. Intentar conversión vía oráculo (Soberanía del dato)
        # Esto permite valorar comisiones en BNB, BTC, etc.
        price = oracle.get_price_eur(asset, dt)
        if price is not None:
            return amount * price

        # 2. Si es stablecoin y el oráculo falló, error crítico (prohibido 0.92)
        if asset in {"USDC", "USDT", "BUSD", "FDUSD", "DAI"}:
            raise ValueError(
                f"CRÍTICO: El oráculo falló para {asset} el {dt}. No se permiten estimaciones fijas (0.92) por ley."
            )

        # 3. Para pares crypto-crypto (en trades), coste directo = 0 (lo asume el FIFO)
        return Decimal("0")

    def _parse_date(self, s: Any) -> datetime:
        """
        Parseador robusto que prioriza los formatos de Binance para evitar ambigüedades
        heurísticas (como confundir 2022 con 2030).
        """
        if pd.isna(s) or str(s).strip() == "":
            return None  # Sin fallback: fecha inválida se descarta

        s_str = str(s).strip()

        # Lista de formatos específicos de Binance (Prioridad absoluta)
        # YY-MM-DD es el formato estándar en sus exportaciones CSV/XLSX
        formatos_estrictos = [
            "%y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%y-%m-%d",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ]

        for fmt in formatos_estrictos:
            try:
                dt = datetime.strptime(s_str, fmt)
                # Corrección de siglo: strptime asume 2000-2069 para %y
                if dt.year < 2000:
                    dt = dt.replace(year=dt.year + 2000)
                if ZoneInfo:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
                return dt
            except ValueError:
                continue

        try:
            dt_pd = pd.to_datetime(s_str, yearfirst=True, errors="coerce").to_pydatetime()
            if ZoneInfo:
                dt_pd = dt_pd.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
            else:
                dt_pd = dt_pd.replace(tzinfo=None)
            return dt_pd
        except Exception:
            return None  # Sin fallback: fecha inválida se descarta


def parse(file_paths: List[str]) -> Tuple[List[Trade], List[Dividend]]:
    ingestor = BinanceIngestor()
    for path in file_paths:
        ingestor.process_file(path)
    return ingestor.transactions, ingestor.dividends
