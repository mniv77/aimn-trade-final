#!/usr/bin/env python3
"""
AIMn EXP66 — Supertrend Flip
Research only. No live orders or production modifications.

SHORT entry: LONG -> SHORT Supertrend flip.
SHORT exit: SHORT -> LONG Supertrend flip.
Protection: 1.5% stop and RSI(14) >= 80.
ATR 10, multiplier 3.
Signals at completed candle close; fills at next candle open.
"""
import sys
import json
import csv
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kiss"))

from kiss_exp53_supertrend import calculate_supertrend

DATA = ROOT / "static/aimn_visual_lab/aimn_nvda_candles.json"
OUT = ROOT / "kiss/results/exp66_rsi_audit"

STOP_PCT = 1.5
RSI_LIMIT = 80.0
COMMISSION_PER_SIDE_PCT = 0.10
RSI_PERIOD = 14


def calculate_rsi(rows):
    closes = [float(x["close"]) for x in rows]
    result = [None] * len(closes)

    if len(closes) <= RSI_PERIOD:
        return result

    gains = []
    losses = []

    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    gain = sum(gains[:RSI_PERIOD]) / RSI_PERIOD
    loss = sum(losses[:RSI_PERIOD]) / RSI_PERIOD

    for i in range(RSI_PERIOD, len(closes)):
        if i > RSI_PERIOD:
            gain = (
                gain * (RSI_PERIOD - 1) + gains[i - 1]
            ) / RSI_PERIOD
            loss = (
                loss * (RSI_PERIOD - 1) + losses[i - 1]
            ) / RSI_PERIOD

        if gain == 0 and loss == 0:
            result[i] = 50.0
        elif loss == 0:
            result[i] = 100.0
        else:
            rs = gain / loss
            result[i] = 100.0 - 100.0 / (1.0 + rs)

    return result


def run():
    print("STEP 905 — AIMn EXP66 RSI AUDIT")
    print("=" * 70)

    rows = json.loads(DATA.read_text())
    df = calculate_supertrend(rows, atr_period=10, multiplier=3.0)

    rows = df.to_dict("records")
    rsi = calculate_rsi(rows)

    trades = []
    position = None
    pending = None

    def close_trade(price, timestamp, reason):
        nonlocal position

        entry = position["entry_price"]
        gross = (entry - price) / entry * 100.0
        commission = 2 * COMMISSION_PER_SIDE_PCT

        trade = {
            "trade_id": f"EXP66-RSI-{len(trades)+1:05d}",
            "symbol": "NVDA",
            "direction": "SHORT",
            "entry_time": position["entry_time"],
            "exit_time": timestamp,
            "entry_price": round(entry, 5),
            "exit_price": round(price, 5),
            "pnl_pct": round(gross, 6),
            "commission_pct": round(commission, 6),
            "net_pnl_pct": round(gross - commission, 6),
            "exit_reason": reason,
            "entry_transition": "SUPERTREND_LONG_TO_SHORT",
        }

        trades.append(trade)
        position = None

    for i, bar in enumerate(rows):
        timestamp = str(bar["timestamp"])
        opening = float(bar["open"])
        high = float(bar["high"])
        closing = float(bar["close"])

        # First process signals known at the PRIOR candle close.
        if pending in ("EXIT", "EXIT_RSI") and position is not None:
            reason = "RSI_RESCUE" if pending == "EXIT_RSI" else "ST_FLIP"
            close_trade(opening, timestamp, reason)

        elif pending == "ENTER" and position is None:
            position = {
                "entry_time": timestamp,
                "entry_price": opening,
            }

        pending = None

        # Protective stop applies to the current candle.
        # If the market gaps beyond the stop, fill at its open.
        if position is not None:
            stop = position["entry_price"] * (
                1.0 + STOP_PCT / 100.0
            )

            if opening >= stop:
                close_trade(
                    opening, timestamp, "STOP_GAP"
                )
            elif high >= stop:
                close_trade(
                    stop, timestamp, "STOP_LOSS"
                )

        # The current candle is now considered completed.
        # Its signal can only be filled on the NEXT candle.
        flip = str(bar.get("st_transition", ""))

        if position is not None:
            if flip == "SHORT->LONG":
                pending = "EXIT"
            elif (
                rsi[i] is not None
                and rsi[i] >= RSI_LIMIT
            ):
                pending = "EXIT_RSI"

        elif flip == "LONG->SHORT":
            pending = "ENTER"


    if position is not None:
        final = rows[-1]
        close_trade(
            float(final["close"]),
            str(final["timestamp"]),
            "END_OF_RESEARCH"
        )

    wins = [t for t in trades if t["net_pnl_pct"] > 0]
    losses = [t for t in trades if t["net_pnl_pct"] <= 0]
    total = sum(t["net_pnl_pct"] for t in trades)

    OUT.mkdir(parents=True, exist_ok=True)

    json_path = OUT / "nvda_exp66_trades.json"
    csv_path = OUT / "nvda_exp66_trades.csv"

    json_path.write_text(json.dumps(trades, indent=2))

    if trades:
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=list(trades[0].keys())
            )
            writer.writeheader()
            writer.writerows(trades)

    print("Historical candles:", len(rows))
    print("Trades:", len(trades))
    print("Winners:", len(wins))
    print("Losers:", len(losses))
    print(
        "Win rate:",
        f"{100*len(wins)/len(trades):.2f}%"
        if trades else "N/A"
    )
    print("Total net P&L sum:", f"{total:+.3f}%")
    print("Exit reasons:", dict(Counter(
        t["exit_reason"] for t in trades
    )))

    print("\nFIRST 10 TRADES")
    for t in trades[:10]:
        print(
            t["trade_id"],
            t["entry_time"],
            "->",
            t["exit_time"],
            f"{t['net_pnl_pct']:+.3f}%",
            t["exit_reason"]
        )

    print("\nSaved:", json_path)
    print("Saved:", csv_path)
    print("EXP66 RESEARCH COMPLETE")
    print("No production trading logic modified.")


if __name__ == "__main__":
    run()
