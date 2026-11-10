#!/usr/bin/env python3
"""AIMn EXP70: Supertrend plateau + price reversal, research only.

Compare ST transitions, early reversal, and early exit without immediate reentry.
Signals use completed candle i; orders fill at candle i+1 OPEN.
No AI, no broker connection, no live orders.
"""
import argparse
import json
from pathlib import Path

from kiss.kiss_exp53_supertrend import calculate_supertrend


def signal(df, i, mode, flat_bars=2, confirm_bars=2):
    """Return LONG/SHORT regime request or None, with no future data."""
    if i < max(flat_bars + 3, confirm_bars + 3):
        return None
    now = df.iloc[i]
    prev = df.iloc[i - 1]
    state = now["st_trend"]
    if state not in ("LONG", "SHORT"):
        return None
    if mode == "transition":
        return state if state != prev["st_trend"] else None

    # Flat resistance/support after an earlier directional staircase.
    # All ST values are completed-candle values; do not use current chart hindsight.
    bands = [float(df.iloc[j]["supertrend"]) for j in range(i - flat_bars, i + 1)]
    if any(not (x == x and abs(x) < float("inf")) for x in bands):
        return None
    tolerance = max(0.00001, float(now["close"]) * 0.00015)
    flat = max(bands) - min(bands) <= tolerance
    earlier = float(df.iloc[i - flat_bars - 1]["supertrend"])
    if not flat or not (earlier == earlier):
        return state if state != prev["st_trend"] else None
    closes = [float(df.iloc[j]["close"]) for j in range(i - confirm_bars, i + 1)]
    # Reverse when price confirms against the current ST regime, before ST flips.
    if state == "SHORT" and earlier > bands[0] + tolerance:
        if closes[-1] > closes[-2] and closes[-1] > closes[0]:
            return "LONG"
    if state == "LONG" and earlier < bands[0] - tolerance:
        if closes[-1] < closes[-2] and closes[-1] < closes[0]:
            return "SHORT"
    # Fallback at the actual ST transition, so we never ignore a confirmed reversal.
    return state if state != prev["st_trend"] else None


def backtest(rows, mode, commission_pct=0.10, stop_pct=1.5):
    df = calculate_supertrend(rows, atr_period=10, multiplier=3.0)
    trades = []
    position = None
    pending = None
    for i in range(1, len(df)):
        candle = df.iloc[i]
        ts = str(candle["timestamp"])
        day = ts[:10]
        op = float(candle["open"])
        if pending is not None:
            desired, reason = pending
            pending = None
            if position and (desired == "FLAT" or position["side"] != desired):
                direction = 1 if position["side"] == "LONG" else -1
                gross = direction * (op / position["entry_price"] - 1) * 100
                trades.append({**position, "exit_time":ts, "exit_price":op,
                               "exit_reason":reason, "gross_pct":round(gross, 5),
                               "net_pct":round(gross - 2 * commission_pct, 5)})
                position = None
            if position is None and desired in ("LONG", "SHORT"):
                position = {"side":desired, "entry_time":ts, "entry_price":op}
        if position:
            direction = 1 if position["side"] == "LONG" else -1
            # Gap-aware protective stop; fill at open if already beyond stop.
            stop = position["entry_price"] * (1 - direction * stop_pct / 100)
            hit = float(candle["low"]) <= stop if direction == 1 else float(candle["high"]) >= stop
            if hit:
                fill = min(op, stop) if direction == 1 else max(op, stop)
                gross = direction * (fill / position["entry_price"] - 1) * 100
                trades.append({**position, "exit_time":ts, "exit_price":fill,
                               "exit_reason":"STOP", "gross_pct":round(gross, 5),
                               "net_pct":round(gross - 2 * commission_pct, 5)})
                position = None
        if i + 1 < len(df):
            next_day = str(df.iloc[i + 1]["timestamp"])[:10]
            # No overnight holdings: liquidate at last completed day's close.
            if next_day != day:
                if position:
                    close = float(candle["close"])
                    direction = 1 if position["side"] == "LONG" else -1
                    gross = direction * (close / position["entry_price"] - 1) * 100
                    trades.append({**position, "exit_time":ts, "exit_price":close,
                                   "exit_reason":"EOD", "gross_pct":round(gross, 5),
                                   "net_pct":round(gross - 2 * commission_pct, 5)})
                    position = None
                pending = None
                continue
            if mode == "exit_only":
                # Plateau warning may CLOSE a position, but never initiates
                # the opposite trade. New entries require an actual ST flip.
                st_request = signal(df, i, "transition")
                early_request = signal(df, i, "plateau")
                if position and early_request and early_request != position["side"]:
                    pending = ("FLAT", "EARLY_EXIT")
                elif st_request and (position is None or position["side"] != st_request):
                    pending = (st_request, "ST_TRANSITION")
            else:
                request = signal(df, i, mode)
                if request and (position is None or position["side"] != request):
                    pending = (request, "ST_TRANSITION" if mode == "transition" else "PLATEAU_OR_ST")
    return {"mode":mode, "trades":trades, "count":len(trades),
            "wins":sum(t["net_pct"] > 0 for t in trades),
            "net_pct_sum":round(sum(t["net_pct"] for t in trades), 5),
            "mean_net_pct":round(sum(t["net_pct"] for t in trades)/len(trades), 5) if trades else 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candles", default="kiss/visual_research/aimn_nvda_candles.json")
    parser.add_argument("--output", default="kiss/results/exp70_st_plateau_comparison.json")
    args = parser.parse_args()
    rows = json.loads(Path(args.candles).read_text(encoding="utf-8"))
    result = {mode:backtest(rows, mode) for mode in ("transition", "plateau", "exit_only")}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for mode, record in result.items():
        print(mode, "trades", record["count"], "wins", record["wins"],
              "net_pct_sum", record["net_pct_sum"], "mean_net_pct", record["mean_net_pct"])
    print("Saved", out)


if __name__ == "__main__":
    main()
