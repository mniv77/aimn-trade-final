<<<<<<< HEAD
 # main_v2.py

import time
import json
from config import settings
from symbol_strategy_selector import get_strategy_for_symbol
from market_data import get_latest_data
from indicators import analyze_market
from alpaca_connector import place_order
from trade_snapshot import save_trade_snapshot

TRADES_LOG_FILE = "aimn_trades.json"


def load_trades():
    try:
        with open(TRADES_LOG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_trade(trade):
    trades = load_trades()
    trades.append(trade)
    with open(TRADES_LOG_FILE, 'w') as f:
        json.dump(trades, f, indent=2)


def run_trading_loop():
    symbol = settings["SYMBOL"]
    strategy = get_strategy_for_symbol(symbol)

    if not strategy:
        print(f"[ERROR] No strategy found for symbol: {symbol}")
        return

    print(f"[INFO] Running strategy for {symbol}: {strategy.__name__}")

    while True:
        try:
            data = get_latest_data(symbol)
            signal = analyze_market(data, strategy)

            if signal in ["buy", "sell"]:
                print(f"[TRADE SIGNAL] {signal.upper()} for {symbol}")
                result = place_order(symbol, signal)
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

                trade = {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "signal": signal,
                    "result": result
                }
                save_trade(trade)
                save_trade_snapshot(trade)

            else:
                print(f"[INFO] No signal for {symbol}. Waiting...")

        except Exception as e:
            print(f"[ERROR] Exception in trading loop: {e}")

        time.sleep(settings.get("SLEEP_INTERVAL", 60))


if __name__ == "__main__":
    run_trading_loop()
=======
 # main_v2.py

import time
import json
from config import settings
from symbol_strategy_selector import get_strategy_for_symbol
from market_data import get_latest_data
from indicators import analyze_market
from alpaca_connector import place_order
from trade_snapshot import save_trade_snapshot

TRADES_LOG_FILE = "aimn_trades.json"


def load_trades():
    try:
        with open(TRADES_LOG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_trade(trade):
    trades = load_trades()
    trades.append(trade)
    with open(TRADES_LOG_FILE, 'w') as f:
        json.dump(trades, f, indent=2)


def run_trading_loop():
    symbol = settings["SYMBOL"]
    strategy = get_strategy_for_symbol(symbol)

    if not strategy:
        print(f"[ERROR] No strategy found for symbol: {symbol}")
        return

    print(f"[INFO] Running strategy for {symbol}: {strategy.__name__}")

    while True:
        try:
            data = get_latest_data(symbol)
            signal = analyze_market(data, strategy)

            if signal in ["buy", "sell"]:
                print(f"[TRADE SIGNAL] {signal.upper()} for {symbol}")
                result = place_order(symbol, signal)
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

                trade = {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "signal": signal,
                    "result": result
                }
                save_trade(trade)
                save_trade_snapshot(trade)

            else:
                print(f"[INFO] No signal for {symbol}. Waiting...")

        except Exception as e:
            print(f"[ERROR] Exception in trading loop: {e}")

        time.sleep(settings.get("SLEEP_INTERVAL", 60))


if __name__ == "__main__":
    run_trading_loop()
>>>>>>> 0c0df91 (Initial push)
