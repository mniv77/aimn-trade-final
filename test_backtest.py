<<<<<<< HEAD
# test_backtest.py
"""
Unit tests for btc_backtest_demo backtest logic
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from app.indicators import AIMnIndicators
from app.position_manager import AIMnPositionManager
from app.scanner import AIMnScanner
from app.config import SYMBOL_PARAMS


def generate_sample_data(n=300):
    now = datetime.utcnow()
    data = {
        'datetime': [now - timedelta(minutes=i) for i in range(n)][::-1],
        'open': [100 + i*0.1 for i in range(n)],
        'high': [101 + i*0.1 for i in range(n)],
        'low': [99 + i*0.1 for i in range(n)],
        'close': [100 + i*0.1 for i in range(n)],
        'volume': [1000 + i for i in range(n)]
    }
    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)
    return df


def test_backtest_flow():
    symbol = "BTC/USD"
    params = SYMBOL_PARAMS.get(symbol, {})

    df = generate_sample_data()
    scanner = AIMnScanner(SYMBOL_PARAMS)
    manager = AIMnPositionManager(max_positions=1)

    trades = 0
    for i in range(100, len(df)):
        window = df.iloc[:i+1]
        indicators = AIMnIndicators.calculate_all_indicators(window.copy(), params)
        latest = indicators.iloc[-1:]
        market_data = {symbol: indicators}

        if not manager.has_position():
            opportunity = scanner.scan_all_symbols(market_data)
            if opportunity and opportunity['symbol'] == symbol:
                manager.enter_position(opportunity, shares=1, params=params)
        else:
            position = manager.positions.get(symbol)
            current_price = latest['close'].values[0]
            current_rsi = latest['rsi_real'].values[0]
            trade = manager.update_position(symbol, current_price, current_rsi)

            if trade:
                trades += 1

    assert trades >= 0
    stats = manager.get_statistics()
    assert stats['total_trades'] == trades
    assert stats['total_pnl'] != 0 or trades == 0
    print("✅ Backtest test ran successfully with", trades, "trades")
=======
# test_backtest.py
"""
Unit tests for btc_backtest_demo backtest logic
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
#from app.indicators import AIMnIndicators
#from app.config import SYMBOL_PARAMS
from indicators import AIMnIndicators
from position_manager import AIMnPositionManager
from scanner import AIMnScanner
from config import SYMBOL_PARAMS


def generate_sample_data(n=300):
    now = datetime.utcnow()
    data = {
        'datetime': [now - timedelta(minutes=i) for i in range(n)][::-1],
        'open': [100 + i*0.1 for i in range(n)],
        'high': [101 + i*0.1 for i in range(n)],
        'low': [99 + i*0.1 for i in range(n)],
        'close': [100 + i*0.1 for i in range(n)],
        'volume': [1000 + i for i in range(n)]
    }
    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)
    return df


def test_backtest_flow():
    symbol = "BTC/USD"
    params = SYMBOL_PARAMS.get(symbol, {})

    df = generate_sample_data()
    scanner = AIMnScanner(SYMBOL_PARAMS)
    manager = AIMnPositionManager(max_positions=1)

    trades = 0
    for i in range(100, len(df)):
        window = df.iloc[:i+1]
        indicators = AIMnIndicators.calculate_all_indicators(window.copy(), params)
        latest = indicators.iloc[-1:]
        market_data = {symbol: indicators}

        if not manager.has_position():
            opportunity = scanner.scan_all_symbols(market_data)
            if opportunity and opportunity['symbol'] == symbol:
                manager.enter_position(opportunity, shares=1, params=params)
        else:
            position = manager.positions.get(symbol)
            current_price = latest['close'].values[0]
            current_rsi = latest['rsi_real'].values[0]
            trade = manager.update_position(symbol, current_price, current_rsi)

            if trade:
                trades += 1

    assert trades >= 0
    stats = manager.get_statistics()
    assert stats['total_trades'] == trades
    assert stats['total_pnl'] != 0 or trades == 0
    print("✅ Backtest test ran successfully with", trades, "trades")
>>>>>>> 0c0df91 (Initial push)
