# tests/test_irpf_calculator_unificado.py
"""
Tests for the unified IRPFCalculator.
Uses simple dataclass stubs so no real ingestion is needed.
"""

from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass


from src.tax_compliance.core.irpf_calculator import IRPFCalculator
from src.domain.fiscal_entities import Dividend, WorkIncome


# ---------------------------------------------------------------------------
# Minimal stubs — mirror the fiscally-relevant fields of both TaxEvent types
# ---------------------------------------------------------------------------


@dataclass
class _CryptoEvent:
    """Minimal stub for crypto_entities.TaxEvent"""

    asset: str
    asset_type: str
    gain_loss_eur: Decimal
    total_sale_eur: Decimal
    total_cost_eur: Decimal
    platform: str = "Binance"
    is_wash_sale: bool = False
    # no isin, no ticker — matches crypto_entities.TaxEvent


class _StockEvent:
    """Minimal stub for stock_entities.TaxEvent -- matches real entity field structure."""

    def __init__(
        self,
        asset,
        asset_type,
        gain_loss_eur,
        sale_proceeds_eur,
        acquisition_cost_eur,
        isin="US0231351067",
        ticker="AMZN",
        platform="DeGiro",
        is_wash_sale=False,
        buy_fee_eur=Decimal("0"),
        sell_fee_eur=Decimal("0"),
        date=None,
    ):
        self.asset = asset
        self.asset_type = asset_type
        self.gain_loss_eur = gain_loss_eur
        self.sale_proceeds_eur = sale_proceeds_eur
        self.acquisition_cost_eur = acquisition_cost_eur
        self.isin = isin
        self.ticker = ticker
        self.platform = platform
        self.is_wash_sale = is_wash_sale
        self.buy_fee_eur = buy_fee_eur
        self.sell_fee_eur = sell_fee_eur
        self.date = date or datetime.now()

    @property
    def total_sale_eur(self) -> Decimal:
        return self.sale_proceeds_eur - self.sell_fee_eur

    @property
    def total_cost_eur(self) -> Decimal:
        return self.acquisition_cost_eur + self.buy_fee_eur


def _div(platform, asset, gross, wht_ext=Decimal("0"), wht_esp=Decimal("0"), dtype="dividend"):
    return Dividend(
        date=datetime(2025, 6, 1),
        platform=platform,
        asset=asset,
        isin="",
        gross_eur=gross,
        withholding_foreign_eur=wht_ext,
        withholding_spain_eur=wht_esp,
        type=dtype,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {
    "work_bruto",
    "work_gastos",
    "work_retenciones",
    "work_neto",
    "rental_bruto",
    "rental_gastos",
    "rental_neto",
    "other_bg",
    "base_general",
    "base_ahorro",
    "capital_yield_total",
    "dividendos_brutos",
    "retencion_dividendos",
    "deduccion_doble_imposicion",
    "cuota_liquida",
    "deducciones_ccaa",
    "resultado",
    "resultado_label",
    "remanente_gpp_futuro",
    "remanente_rcm_futuro",
    "cripto_aeat",
    "acciones_aeat",
    "iic_aeat",
    "otros_aeat",
    "inmuebles_aeat",
    "crypto_gain_loss",
    "custody_fees",
    "dividend_details",
    "interest_details",
}


def test_calculate_returns_all_required_keys():
    """Every key consumed by result.html must be present."""
    calc = IRPFCalculator()
    summary = calc.calculate().raw_summary
    missing = REQUIRED_KEYS - summary.keys()
    assert not missing, f"Missing keys: {missing}"


def test_inmuebles_aeat_is_empty_dict():
    calc = IRPFCalculator()
    summary = calc.calculate().raw_summary
    assert summary["inmuebles_aeat"] == {}


def test_crypto_gain_loss_counts_only_crypto_events():
    crypto_ev = _CryptoEvent("BTC", "crypto", Decimal("500"), Decimal("1500"), Decimal("1000"))
    stock_ev = _StockEvent(
        "AMZN", "stock", Decimal("300"), sale_proceeds_eur=Decimal("1300"), acquisition_cost_eur=Decimal("1000")
    )
    calc = IRPFCalculator(crypto_events=[crypto_ev], stock_events=[stock_ev])
    summary = calc.calculate().raw_summary
    assert summary["crypto_gain_loss"] == Decimal("500")


def test_group_aeat_events_crypto_uses_asset_as_key():
    """Crypto events have no isin — must fall back to asset name as key."""
    crypto_ev = _CryptoEvent("ETH", "crypto", Decimal("200"), Decimal("1200"), Decimal("1000"))
    calc = IRPFCalculator(crypto_events=[crypto_ev])
    summary = calc.calculate().raw_summary
    binance_group = summary["cripto_aeat"].get("Binance", {})
    assert "ETH" in binance_group


def test_group_aeat_events_stock_uses_isin_as_key():
    """Stock events have isin — must use it as key when len > 5."""
    stock_ev = _StockEvent(
        "Amazon.com Inc",
        "stock",
        Decimal("100"),
        sale_proceeds_eur=Decimal("1100"),
        acquisition_cost_eur=Decimal("1000"),
    )
    calc = IRPFCalculator(stock_events=[stock_ev])
    summary = calc.calculate().raw_summary
    degiro_group = summary["acciones_aeat"].get("DeGiro", {})
    assert "US0231351067" in degiro_group


def test_dividend_details_has_assets_subdict():
    """interest_details and dividend_details must have 'assets' sub-dict."""
    div = _div("Revolut", "AAPL", Decimal("50"), wht_ext=Decimal("7.50"))
    interest = _div("Revolut", "EUR_INTEREST", Decimal("10"), dtype="interest")
    calc = IRPFCalculator(dividends=[div, interest])
    summary = calc.calculate().raw_summary

    assert "assets" in summary["dividend_details"]["Revolut"]
    assert "assets" in summary["interest_details"]["Revolut"]


def test_custody_fees_accumulated():
    """Fees of type 'fee' must accumulate into custody_fees, not dividends."""
    fee = Dividend(
        date=datetime(2025, 1, 1),
        platform="DeGiro",
        asset="CUSTODY",
        isin="",
        gross_eur=Decimal("0"),
        withholding_foreign_eur=Decimal("0"),
        withholding_spain_eur=Decimal("0"),
        type="fee",
        custody_fee_eur=Decimal("12.50"),
    )
    calc = IRPFCalculator(dividends=[fee])
    summary = calc.calculate().raw_summary
    assert summary["custody_fees"] == Decimal("12.50")
    assert summary["capital_yield_total"] == Decimal("0")


def test_wash_sale_events_excluded_from_gpp():
    """Events flagged as wash sales must not contribute to base_ahorro."""
    normal = _StockEvent("AAPL", "stock", Decimal("500"), Decimal("1500"), Decimal("1000"))
    # Un wash sale es por definición una PÉRDIDA bloqueada. Si fuera ganancia, sí tributa.
    washed = _StockEvent("TSLA", "stock", Decimal("-300"), Decimal("700"), Decimal("1000"), is_wash_sale=True)
    calc = IRPFCalculator(stock_events=[normal, washed])
    summary = calc.calculate().raw_summary
    # Only the non-washed event's gain (500) should appear in base_ahorro
    assert summary["base_ahorro"] == Decimal("500")


def test_art49_cross_compensation_limit():
    """G/P losses can only offset up to 25% of RCM (Art. 49 LIRPF)."""
    loss_ev = _CryptoEvent("BTC", "crypto", Decimal("-400"), Decimal("600"), Decimal("1000"))
    div = _div("Binance", "BTC", Decimal("1000"))
    calc = IRPFCalculator(crypto_events=[loss_ev], dividends=[div])
    summary = calc.calculate().raw_summary
    # RCM compensación: min(400, 1000*0.25) = 250
    # base_ahorro = max(-400+250, 0) + max(1000-250, 0) = 0 + 750 = 750
    assert summary["base_ahorro"] == Decimal("750")


def test_work_income_art20_reduction_low_income():
    """Full Art. 20 reduction (7302€) applies when rnt_art20 ≤ 14852€ (2025 thresholds)."""
    work = WorkIncome(
        retribuciones_dinerarias=Decimal("14000"),
        retenciones=Decimal("2000"),
        gastos_deducibles=Decimal("500"),
    )
    calc = IRPFCalculator(work=work)
    summary = calc.calculate().raw_summary
    # rnt_art20 = 14000 - 500 = 13500  (≤ 14852 → reduccion = 7302)
    # rendimiento_neto_trabajo = 13500 - 2000 (gastos_art19_f) = 11500
    # work_neto = max(11500 - 7302, 0) = 4198
    assert summary["work_neto"] == Decimal("4198")
