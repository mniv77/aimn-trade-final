# /home/MeirNiv/aimn-trade-final/engine/tuning/run_tuning_crypto.py
# AiMN V3.1 - Crypto-Specific Tuning Runner
# Runs separately from ETF/stock tuner - crypto only

import sys
sys.path.insert(0, '/home/MeirNiv/aimn-trade-final')
from engine.tuning.auto_tuner_crypto import tune_crypto_strategy, log
from db import get_db_connection
from datetime import datetime

# Crypto symbols and timeframes
CRYPTO_SYMBOLS = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'LINK/USD']
DIRECTIONS     = ['LONG', 'SHORT']
CRYPTO_TFS = [
    {'tf': '1hr',  'candle_time': '1hr',  'bar_minutes': 60,  'bars': 8000},
    {'tf': '30m',  'candle_time': '30m',  'bar_minutes': 30,  'bars': 8000},
]

def main():
    start = datetime.now()
    log("=" * 60)
    log("AiMN V3.1 - CRYPTO STRATEGY TUNER")
    log("Symbols: BTC, ETH, SOL, LINK")
    log("Strategy: Trend-following with RSI bounce + volume")
    log("=" * 60)

    total = 0
    saved = 0

    for symbol in CRYPTO_SYMBOLS:
        for direction in DIRECTIONS:
            for tf in CRYPTO_TFS:
                total += 1
                log(f"\n▶ {symbol} {direction} [{tf['tf']}]")
                try:
                    tune_crypto_strategy(
                        symbol, direction, tf['tf'],
                        cfg={'bars': tf['bars'], 'bar_minutes': tf['bar_minutes']}
                    )
                    saved += 1
                except Exception as e:
                    log(f"ERROR: {e}")

    elapsed = (datetime.now() - start).seconds // 60
    log(f"\n{'='*60}")
    log(f"CRYPTO TUNING COMPLETE")
    log(f"Total combinations: {total}")
    log(f"Elapsed: {elapsed} minutes")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()