#!/usr/bin/env python3
"""AIMn research-only SHORT continuation backtest."""

import json
from pathlib import Path
from continuation_detector import short_continuation
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from exp56_symmetric_transition_engine import get_market_state

DATA_FILE = Path("kiss/visual_research/aimn_nvda_candles.json")
STOP_LOSS_PCT = 0.015
COMMISSION_PCT_PER_SIDE = 0.001
MAX_HOLD_CANDLES = 6

def load_candles():
    with DATA_FILE.open() as f:
        return json.load(f)

def main():
    candles = load_candles()
    print("AIMn SHORT Continuation Backtest")
    print("Candles loaded:", len(candles))
    print("First:", candles[0]["timestamp"])
    print("Last:", candles[-1]["timestamp"])
    closes = [x["close"] for x in candles]
    states = [get_market_state(closes, i) for i in range(len(candles))]
    print("SHORT candles:", states.count("SHORT"))
    signals = [i for i in range(len(candles)) if short_continuation(candles, states, i) and candles[i]["timestamp"][:10] == candles[i-1]["timestamp"][:10]]
    print("Continuation signals:", len(signals))

if __name__ == "__main__":
    main()
