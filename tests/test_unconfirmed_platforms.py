import pytest
import os
import pandas as pd
from decimal import Decimal
from datetime import datetime

from src.ingestion import coinbase_reader, etoro_reader, ibkr_reader, kraken_reader, kucoin_reader, revolut_reader
from src.accounting.interwallet_controller import InterwalletController
from src.tax_compliance.core.irpf_calculator import IRPFCalculator

def procesar_impuesto(trades, dividends):
    stock, crypto = [], []
    for t in trades:
        if getattr(t, 'asset_type', '').lower() == 'stock':
            stock.append(t)
        else:
            crypto.append(t)
    ctrl = InterwalletController(raw_crypto_trades=crypto, raw_stock_trades=stock)
    ce, se = ctrl.execute_pipeline(target_fiscal_year=2025)
    
    print("\n--- DEBUG ---")
    for e in ce + se:
        print(f"Event: {e.asset} {e.gain_loss_eur} EUR (Wash: {getattr(e, 'is_wash_sale', False)})")
    
    calc = IRPFCalculator(crypto_events=ce, stock_events=se, dividends=dividends, fiscal_year=2025)
    dto = calc.calculate()
    print(f"GPP Neto: {dto.raw_summary['gpp_neto']} | Base Ahorro: {dto.savings_taxable_base} | Cuota: {dto.final_result}")
    return dto.final_result

def test_coinbase_parser(tmp_path):
    mock_file = tmp_path / "coinbase_mock.csv"
    pd.DataFrame({"timestamp": ["2025-01-10T10:00:00Z", "2025-02-10T10:00:00Z"], "transaction type": ["Buy", "Sell"], "asset": ["BTC", "BTC"], "quantity transacted": [1.0, 1.0], "spot price currency": ["EUR", "EUR"], "spot price at transaction": [10000.0, 20000.0], "subtotal": [10000.0, 20000.0], "fees and/or spread": [10.0, 10.0], "total (inclusive of fees and/or spread)": [10010.0, 19990.0], "notes": ["", ""]}).to_csv(mock_file, index=False)
    trades, dividends = coinbase_reader.parse([str(mock_file)])
    
    cuota = procesar_impuesto(trades, dividends)
    print(f"\n[Coinbase] Impuesto (Cuota Final IRPF): {cuota:.2f} EUR")

def test_etoro_parser(tmp_path):
    mock_file = tmp_path / "etoro_mock.xlsx"
    with pd.ExcelWriter(mock_file) as writer:
        pd.DataFrame({"Date": ["10/01/2025 10:00:00", "20/01/2025 10:00:00"], "Type": ["Position closed", "Position closed"], "Amount": [10000.0, 20000.0], "Units": [1.0, -1.0], "Action": ["Buy Bitcoin", "Sell Bitcoin"], "Asset": ["BTC", "BTC"], "Spread": [10.0, 10.0], "Profit(USD)": [0.0, 10000.0], "ISIN": ["", ""]}).to_excel(writer, sheet_name="Closed Positions", index=False)
        pd.DataFrame({"Date": ["10/01/2025 10:00:00", "20/01/2025 10:00:00"], "Type": ["Deposit", "Withdrawal"], "Details": ["", ""], "Amount": [10000.0, -20000.0], "Realized Equity Change": [0.0, 10000.0], "Realized Equity": [10000.0, 20000.0], "Balance": [10000.0, 20000.0], "Position ID": ["1", "1"]}).to_excel(writer, sheet_name="Account Activity", index=False)
        pd.DataFrame({"Date of Payment": ["15/02/2025 10:00:00"], "Instrument Name": ["AAPL"], "Net Dividend Received (USD)": [5.0], "Withholding Tax Rate (%)": [15.0]}).to_excel(writer, sheet_name="Dividends", index=False)
    trades, dividends = etoro_reader.parse([str(mock_file)])
    
    cuota = procesar_impuesto(trades, dividends)
    print(f"\n[eToro] Impuesto (Cuota Final IRPF): {cuota:.2f} EUR")

def test_ibkr_parser(tmp_path):
    mock_file = tmp_path / "ibkr_mock.csv"
    pd.DataFrame({"BuySell": ["BUY", "SELL"], "Symbol": ["AAPL", "AAPL"], "Quantity": [100, -100], "TradePrice": [150.0, 250.0], "Proceeds": [-15000.0, 25000.0], "IBCommission": [-1.0, -1.0], "TradeDate": ["2025-01-10", "2025-02-10"], "Currency": ["EUR", "EUR"]}).to_csv(mock_file, index=False)
    trades, dividends = ibkr_reader.parse([str(mock_file)])
    
    cuota = procesar_impuesto(trades, dividends)
    print(f"\n[IBKR] Impuesto (Cuota Final IRPF): {cuota:.2f} EUR")

def test_kraken_parser(tmp_path):
    mock_file = tmp_path / "kraken_mock.csv"
    pd.DataFrame({"txid": ["t1", "t2"], "refid": ["r1", "r2"], "time": ["2025-01-10 10:00:00", "2025-02-10 10:00:00"], "type": ["trade", "trade"], "subtype": ["", ""], "aclass": ["currency", "currency"], "asset": ["XXBT", "XXBT"], "amount": [1.0, -1.0], "fee": [0.0, 0.0], "balance": [1.0, 0.0]}).to_csv(mock_file, index=False)
    trades, dividends = kraken_reader.parse([str(mock_file)])
    
    # Kraken depende del oráculo real para BTC, generará PnL en base al diferencial histórico
    cuota = procesar_impuesto(trades, dividends)
    print(f"\n[Kraken] Impuesto (Cuota Final IRPF): {cuota:.2f} EUR")

def test_kucoin_parser(tmp_path):
    mock_file = tmp_path / "kucoin_mock.csv"
    pd.DataFrame({"Time": ["2025-01-10 10:00:00", "2025-02-10 10:00:00"], "Symbol": ["BTC-EUR", "BTC-EUR"], "Side": ["Buy", "Sell"], "Price": [10000.0, 20000.0], "Amount": [1.0, 1.0], "Fee": [10.0, 10.0], "Fee Coin": ["EUR", "EUR"]}).to_csv(mock_file, index=False)
    trades, dividends = kucoin_reader.parse([str(mock_file)])
    
    cuota = procesar_impuesto(trades, dividends)
    print(f"\n[KuCoin] Impuesto (Cuota Final IRPF): {cuota:.2f} EUR")

def test_revolut_parser(tmp_path):
    mock_file = tmp_path / "revolut_mock.csv"
    pd.DataFrame({"Type": ["BUY", "SELL"], "Date": ["2025-01-10T10:00:00Z", "2025-02-10T10:00:00Z"], "Ticker": ["AAPL", "AAPL"], "Quantity": [100, 100], "Price": [150.0, 250.0], "Total Amount": [15000.0, 25000.0], "Fee": [1.0, 1.0]}).to_csv(mock_file, index=False)
    trades, dividends = revolut_reader.parse(str(mock_file))
    print(f"\n[Revolut] Parsed Trades: {len(trades)}")
    
    cuota = procesar_impuesto(trades, dividends)
    print(f"\n[Revolut] Impuesto (Cuota Final IRPF): {cuota:.2f} EUR")

def test_interwallet_unconfirmed_platforms(tmp_path):
    """
    Integra datos mockeados limitados exclusivamente a:
    Coinbase, eToro, IBKR, Kraken, KuCoin, Revolut.
    Verifica que el InterwalletController los consolide sin excepciones de runtime.
    """
    # Usaremos las funciones del framework de los test individuales arriba
    # generando los mocks e ingiriendo cada uno.
    
    all_crypto = []
    all_stock = []
    
    def clasificar(trades):
        for t in trades:
            if getattr(t, 'asset_type', '').lower() == 'stock':
                all_stock.append(t)
            else:
                all_crypto.append(t)
                
    # Coinbase
    cf = tmp_path / "cb.csv"
    pd.DataFrame({"timestamp": ["2025-01-10T10:00:00Z"], "transaction type": ["Buy"], "asset": ["BTC"], "quantity transacted": [1.0], "spot price at transaction": [10000.0], "subtotal": [10000.0], "fees and/or spread": [10.0], "total (inclusive of fees and/or spread)": [10010.0], "notes": [""]}).to_csv(cf, index=False)
    t, _ = coinbase_reader.parse([str(cf)])
    clasificar(t)
    
    # eToro
    ef = tmp_path / "et.xlsx"
    with pd.ExcelWriter(str(ef)) as writer:
        pd.DataFrame({"Position ID": ["111"], "Action": ["Buy AAPL"], "Amount": [1000.0], "Units": [10.0], "Open Date": ["10/01/2025 10:00:00"], "Close Date": ["20/01/2025 10:00:00"], "Spread": [1.0], "Profit(USD)": [100.0]}).to_excel(writer, sheet_name="Closed Positions", index=False)
    t, _ = etoro_reader.parse([str(ef)])
    clasificar(t)
    
    # IBKR
    ibf = tmp_path / "ib.csv"
    pd.DataFrame({"BuySell": ["SELL"], "Symbol": ["AAPL"], "Quantity": [-10], "TradePrice": [160.0], "IBCommission": [-1.0], "TradeDate": ["2025-01-20"], "Currency": ["USD"]}).to_csv(ibf, index=False)
    t, _ = ibkr_reader.parse([str(ibf)])
    clasificar(t)
    
    # Kraken
    krf = tmp_path / "kr.csv"
    pd.DataFrame({"txid": ["tx1"], "refid": ["ref1"], "time": ["2025-01-10 10:00:00"], "type": ["trade"], "subtype": [""], "aclass": ["currency"], "asset": ["XXBT"], "amount": [-1.0], "fee": [0.0], "balance": [0.0]}).to_csv(krf, index=False)
    t, _ = kraken_reader.parse([str(krf)])
    clasificar(t)
    
    # KuCoin
    kuf = tmp_path / "ku.csv"
    pd.DataFrame({"Time": ["2025-01-15 10:00:00"], "Symbol": ["BTC-USDT"], "Side": ["Sell"], "Price": [15000.0], "Amount": [1.0], "Fee": [10.0], "Fee Coin": ["USDT"]}).to_csv(kuf, index=False)
    t, _ = kucoin_reader.parse([str(kuf)])
    clasificar(t)
    
    # Revolut
    rvf = tmp_path / "rv.csv"
    pd.DataFrame({"Type": ["BUY"], "Date": ["2025-01-10T10:00:00Z"], "Ticker": ["AAPL"], "Quantity": [10], "Price": [150.0], "Total": [1500.0], "Fee": [1.0]}).to_csv(rvf, index=False)
    t, _ = revolut_reader.parse(str(rvf))
    clasificar(t)
    
    all_stock.sort(key=lambda x: getattr(x, 'date'))
    all_crypto.sort(key=lambda x: getattr(x, 'date'))
    
    controller = InterwalletController(raw_crypto_trades=all_crypto, raw_stock_trades=all_stock)
    crypto_events, stock_events = controller.execute_pipeline(target_fiscal_year=2025)
    final_events = crypto_events + stock_events
    
    # Se esperan al menos ventas (Kraken sell BTC, Kucoin sell BTC, eToro close, IBKR sell AAPL)
    assert len(final_events) > 0
    # Valida que no hay excepciones al cruzar plataformas puramente no confirmadas
