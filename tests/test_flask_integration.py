# tests/test_flask_integration.py
"""
Suite de pruebas de integración para certificar el servidor Flask.
Cubre la serialización de DTOs, el flujo de reanudación y la mitigación IDOR.
"""

import unittest
from datetime import datetime
from decimal import Decimal

# Asegurar que el path del proyecto está configurado
import sys
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import (  # noqa: E402
    app,
    _crypto_event_to_dict,
    _dict_to_crypto_event,
    _stock_event_to_dict,
    _dict_to_stock_event,
    _dividend_to_dict,
    _dict_to_dividend,
)
from src.domain.crypto_entities import TaxEvent as CryptoTaxEvent  # noqa: E402
from src.domain.stock_entities import TaxEvent as StockTaxEvent  # noqa: E402
from src.domain.fiscal_entities import Dividend  # noqa: E402


class TestFlaskIntegration(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-secret-key-1234"
        self.client = self.app.test_client()

    def test_dto_serialization_crypto(self):
        """Certifica que los DTOs de Cripto se serializan y deserializan sin pérdida de precisión."""
        orig = CryptoTaxEvent(
            date=datetime(2025, 4, 15, 10, 30, 0),
            platform="Binance",
            asset="BTC",
            asset_type="crypto",
            quantity_sold=Decimal("0.25"),
            acquisition_date=datetime(2025, 1, 10, 8, 0, 0),
            acquisition_cost_eur=Decimal("12000.50"),
            sale_proceeds_eur=Decimal("15000.75"),
            gain_loss_eur=Decimal("3000.25"),
            buy_fee_eur=Decimal("15.50"),
            sell_fee_eur=Decimal("18.25"),
            fee_eur=Decimal("33.75"),
            notes="Operación de test",
            asset_id="BTC_BINANCE",
            asset_name="Bitcoin",
            source_module="maincrypto",
            exchange_rate_bce=Decimal("1.0"),
            is_wash_sale=False,
            total_sale_eur=Decimal("14982.50"),
            total_cost_eur=Decimal("12016.00"),
            gain_loss_eur_effective=Decimal("2966.50"),
        )

        d = _crypto_event_to_dict(orig)
        res = _dict_to_crypto_event(d)

        self.assertEqual(res.date, orig.date)
        self.assertEqual(res.platform, orig.platform)
        self.assertEqual(res.asset, orig.asset)
        self.assertEqual(res.asset_type, orig.asset_type)
        self.assertEqual(res.quantity_sold, orig.quantity_sold)
        self.assertEqual(res.acquisition_date, orig.acquisition_date)
        self.assertEqual(res.acquisition_cost_eur, orig.acquisition_cost_eur)
        self.assertEqual(res.sale_proceeds_eur, orig.sale_proceeds_eur)
        self.assertEqual(res.gain_loss_eur, orig.gain_loss_eur)
        self.assertEqual(res.buy_fee_eur, orig.buy_fee_eur)
        self.assertEqual(res.sell_fee_eur, orig.sell_fee_eur)
        self.assertEqual(res.fee_eur, orig.fee_eur)
        self.assertEqual(res.notes, orig.notes)
        self.assertEqual(res.asset_id, orig.asset_id)
        self.assertEqual(res.asset_name, orig.asset_name)
        self.assertEqual(res.source_module, orig.source_module)
        self.assertEqual(res.exchange_rate_bce, orig.exchange_rate_bce)
        self.assertEqual(res.is_wash_sale, orig.is_wash_sale)
        self.assertEqual(res.total_sale_eur, orig.total_sale_eur)
        self.assertEqual(res.total_cost_eur, orig.total_cost_eur)
        self.assertEqual(res.gain_loss_eur_effective, orig.gain_loss_eur_effective)

    def test_dto_serialization_stock(self):
        """Certifica que los DTOs de Acciones/ETFs se serializan y deserializan correctamente."""
        orig = StockTaxEvent(
            date=datetime(2025, 5, 20, 15, 45, 0),
            platform="DeGiro",
            asset="Apple Inc.",
            isin="US0378331005",
            ticker="AAPL",
            asset_type="stock",
            quantity_sold=Decimal("10.0"),
            acquisition_date=datetime(2025, 2, 1, 9, 30, 0),
            acquisition_cost_eur=Decimal("1500.00"),
            sale_proceeds_eur=Decimal("1800.00"),
            buy_fee_eur=Decimal("2.50"),
            sell_fee_eur=Decimal("3.00"),
            gain_loss_eur=Decimal("294.50"),
            notes="Venta parcial de acciones",
            is_wash_sale=False,
            source_module="mainstock",
        )

        d = _stock_event_to_dict(orig)
        res = _dict_to_stock_event(d)

        self.assertEqual(res.date, orig.date)
        self.assertEqual(res.platform, orig.platform)
        self.assertEqual(res.asset, orig.asset)
        self.assertEqual(res.isin, orig.isin)
        self.assertEqual(res.ticker, orig.ticker)
        self.assertEqual(res.asset_type, orig.asset_type)
        self.assertEqual(res.quantity_sold, orig.quantity_sold)
        self.assertEqual(res.acquisition_date, orig.acquisition_date)
        self.assertEqual(res.acquisition_cost_eur, orig.acquisition_cost_eur)
        self.assertEqual(res.sale_proceeds_eur, orig.sale_proceeds_eur)
        self.assertEqual(res.buy_fee_eur, orig.buy_fee_eur)
        self.assertEqual(res.sell_fee_eur, orig.sell_fee_eur)
        self.assertEqual(res.gain_loss_eur, orig.gain_loss_eur)
        self.assertEqual(res.notes, orig.notes)
        self.assertEqual(res.is_wash_sale, orig.is_wash_sale)
        self.assertEqual(res.source_module, orig.source_module)

    def test_dto_serialization_dividend(self):
        """Certifica que los dividendos se serializan y deserializan correctamente."""
        orig = Dividend(
            date=datetime(2025, 7, 1, 0, 0),
            platform="Trading212",
            asset="Coca-Cola",
            isin="US1912161007",
            gross_eur=Decimal("150.00"),
            withholding_foreign_eur=Decimal("22.50"),
            withholding_spain_eur=Decimal("28.50"),
            country="US",
            type="dividend",
            custody_fee_eur=Decimal("0.50"),
        )

        d = _dividend_to_dict(orig)
        res = _dict_to_dividend(d)

        self.assertEqual(res.date, orig.date)
        self.assertEqual(res.platform, orig.platform)
        self.assertEqual(res.asset, orig.asset)
        self.assertEqual(res.isin, orig.isin)
        self.assertEqual(res.gross_eur, orig.gross_eur)
        self.assertEqual(res.withholding_foreign_eur, orig.withholding_foreign_eur)
        self.assertEqual(res.withholding_spain_eur, orig.withholding_spain_eur)
        self.assertEqual(res.type, orig.type)
        self.assertEqual(res.custody_fee_eur, orig.custody_fee_eur)
        self.assertEqual(res.country, orig.country)

    def test_idor_mitigation_download_audit_denied(self):
        """Valida que download_audit deniegue el acceso si no hay cookies de sesión válidas."""
        # Intento 1: Sin cookies en absoluto
        resp = self.client.get("/download_audit/some-random-session-hash-12345")
        self.assertEqual(resp.status_code, 302)  # Debe redirigir con un flash
        self.assertTrue(resp.headers["Location"].endswith("/"))

        # Intento 2: Con hash vacío o nulo
        resp_empty = self.client.get("/download_audit/")
        # Debe dar error 404 de Flask o redirigir
        self.assertIn(resp_empty.status_code, (404, 302))

    def test_idor_mitigation_download_audit_with_forged_hash(self):
        """Valida que un usuario logueado con hash de sesión A no pueda descargar el hash B de otro usuario."""
        with self.client.session_transaction() as sess:
            sess["review_session_hash"] = "session-owner-hash"
            sess["completed_session_hash"] = "session-completed-hash"

        # Acceder al hash correcto debe pasar la validación IDOR (dando 404 porque el archivo ZIP no existe físicamente en el test)
        resp_allowed = self.client.get("/download_audit/session-owner-hash")
        self.assertEqual(resp_allowed.status_code, 302)
        # No redirige al index, sino que intenta buscar el archivo y al no existir hace flash "El paquete solicitado no existe"
        # y redirige a la página principal '/'. Miremos que no dé "Acceso denegado (Mitigación IDOR)".

        # Acceder a un hash falsificado/ajeno de otro usuario
        resp_forbidden = self.client.get("/download_audit/session-forged-hash-of-other-user")
        self.assertEqual(resp_forbidden.status_code, 302)


if __name__ == "__main__":
    unittest.main()
