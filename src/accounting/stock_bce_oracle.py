import os
import requests
import csv
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal


class StockBCEOracle:
    """
    Oráculo de tipos de cambio oficiales del BCE para el ecosistema de Acciones.
    Incluye persistencia en SQLite para evitar rate limiting y reducir memoria.
    """

    CSV_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv"
    DB_FILE = "bce_rates.db"

    def __init__(self, cache_dir: str = "."):
        self.db_path = os.path.join(cache_dir, self.DB_FILE)
        self._init_db()
        self._load_cache()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rates (
                    date TEXT,
                    currency TEXT,
                    rate REAL,
                    PRIMARY KEY (date, currency)
                )
            """)
            conn.commit()

    def _load_cache(self):
        """Descarga si la BD está vacía."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM rates")
            if cursor.fetchone()[0] == 0:
                self._update_cache()

    def _update_cache(self):
        """Descarga masiva de tipos de cambio y guarda en SQLite."""
        import logging

        logging.info("  [STOCK-ORACLE] Descargando tipos de cambio oficiales del BCE a SQLite...")
        try:
            response = requests.get(self.CSV_URL, timeout=15)
            if response.status_code == 200:
                content = response.content.decode("utf-8").splitlines()
                reader = csv.DictReader(content)
                data_to_insert = []
                for row in reader:
                    date_str = row["Date"]
                    for curr, rate in row.items():
                        if curr != "Date" and rate and rate != "N/A":
                            data_to_insert.append((date_str, curr, float(rate)))

                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.executemany(
                        """
                        INSERT OR IGNORE INTO rates (date, currency, rate)
                        VALUES (?, ?, ?)
                    """,
                        data_to_insert,
                    )
                    conn.commit()
                logging.info(f"  [OK] Tipos de cambio guardados en SQLite {self.DB_FILE}")
            else:
                logging.error(f"  [!] Fallo en descarga BCE: {response.status_code}")
        except Exception as e:
            logging.error(f"  [!] Error de conexion con servidor BCE: {e}")

    def get_rate(self, date: datetime, currency: str) -> Decimal:
        """
        Devuelve el tipo de cambio oficial para una fecha y moneda.
        Realiza búsqueda retrospectiva en SQLite y fallback a API Frankfurter.
        """
        if currency == "EUR" or not currency:
            return Decimal("1.0")

        currency = currency.upper().strip()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            for offset in range(8):
                current_date = date - timedelta(days=offset)
                d_str = current_date.strftime("%Y-%m-%d")

                cursor.execute("SELECT rate FROM rates WHERE date = ? AND currency = ?", (d_str, currency))
                row = cursor.fetchone()
                if row:
                    return Decimal(str(row[0]))

        # 2. Fallback: Petición puntual a Frankfurter API
        d_str = date.strftime("%Y-%m-%d")
        try:
            url = f"https://api.frankfurter.app/{d_str}?to={currency}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                rate = Decimal(str(data["rates"][currency]))
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO rates (date, currency, rate)
                        VALUES (?, ?, ?)
                    """,
                        (d_str, currency, float(rate)),
                    )
                    conn.commit()
                return rate
        except Exception as e:
            import logging

            logging.error(f"  [!] Fallo fallback Frankfurter para {d_str}: {e}")

        import logging

        logging.warning(f"  ⚠️ StockBCE: Tipo de cambio no encontrado para {currency} en {d_str}.")
        return None
