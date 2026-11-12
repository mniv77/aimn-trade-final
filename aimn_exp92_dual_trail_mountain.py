#!/usr/bin/env python3
"""EXP92 — Dual-trail mountain geometry audit (research only).

READ ONLY: no orders, no production edits, no strategy optimization.
Replays the unchanged EXP83 V16/ST baseline, then measures causal geometry
at each accepted SHORT entry. Later outcomes are labeled AFTER the fact and
never used in a signal or decision.

Session-local windows do not cross overnight boundaries. A 12/20/30-candle
window may be unavailable early in the session; never fill it from yesterday.
"""
import csv
import json
import math
from collections import Counter
from pathlib import Path

import aimn_exp83_v16_structural_exit as exp83

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "kiss/results/exp92_dual_trail_mountain"
WINDOWS = (12, 20, 30)
FEE = 0.10

def safe_round(value):
    return round(value, 6) if value is not None and math.isfinite(value) else None

def pct(a, b):
    return 100.0 * (a / b - 1.0) if b else None

def geometry(rows, i, window):
    """All values use only candles through completed signal bar i."""
    if i < window - 1:
        return None
    section = rows[i-window+1:i+1]
    day = str(rows[i]["timestamp"])[:10]
    if any(str(r["timestamp"])[:10] != day for r in section):
        return None
    highs = [float(r["high"]) for r in section]
    lows = [float(r["low"]) for r in section]
    closes = [float(r["close"]) for r in section]
    top, bottom = max(highs), min(lows)
    width = pct(top, bottom)
    progress = pct(closes[-1], closes[0])
    traveled = sum(abs(pct(closes[j], closes[j-1])) for j in range(1, window))
    efficiency = abs(progress) / traveled if traveled else 0.0
    # Signed slope: negative means declining. Unlike a chart angle, this is
    # invariant to chart zoom and uses a fixed five-minute time interval.
    slope = progress / (window - 1)
    top_index = highs.index(top)
    bottom_index = lows.index(bottom)
    # Direction of the observed mountain is not assumed from its height.
    return {
        "height_pct": safe_round(width),
        "slope_pct_per_5m": safe_round(slope),
        "efficiency": safe_round(efficiency),
        "net_change_pct": safe_round(progress),
        "range_position": safe_round((closes[-1]-bottom)/(top-bottom)) if top > bottom else None,
        "top_age_bars": window-1-top_index,
        "bottom_age_bars": window-1-bottom_index,
        "top_price": safe_round(top),
        "bottom_price": safe_round(bottom),
    }

def future_short_move(rows, entry_i, horizon):
    """Outcome label ONLY. Not part of any entry/exit calculation."""
    day = str(rows[entry_i]["timestamp"])[:10]
    if entry_i + horizon >= len(rows):
        return None
    future = rows[entry_i+1:entry_i+horizon+1]
    if any(str(r["timestamp"])[:10] != day for r in future):
        return None
    entry = float(rows[entry_i]["open"])
    future_lows = [float(r["low"]) for r in future]
    future_highs = [float(r["high"]) for r in future]
    return {
        "best_decline_pct": safe_round(100*(entry/min(future_lows)-1)),
        "worst_rise_pct": safe_round(100*(max(future_highs)/entry-1)),
        "last_close_short_pct": safe_round(100*(entry/float(future[-1]["close"])-1)),
    }

def summarize_group(items):
    return {
        "trades": len(items),
        "winners": sum(t["net_pnl_pct"] > 0 for t in items),
        "losers": sum(t["net_pnl_pct"] <= 0 for t in items),
        "gross_pct_sum": safe_round(sum(t["gross_pnl_pct"] for t in items)),
        "commission_pct_sum": safe_round(2*FEE*len(items)),
        "net_pct_sum": safe_round(sum(t["net_pnl_pct"] for t in items)),
    }

def write_csv(path, items):
    if not items:
        return
    columns = list(items[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(items)

def run(symbol, path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r: str(r["timestamp"]))
    closes = [float(r["close"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]
    st = exp83.calculate_supertrend(rows, atr_period=10, multiplier=3.0)["st_trend"].tolist()
    rsi = exp83.rsi_wilder(closes)
    market = [exp83.get_market_state(closes, i) for i in range(len(rows))]
    trades, candidates, rejected, _ = exp83.simulate(rows, st, rsi, market, None, False)
    # Entry is at next bar OPEN after the completed signal.
    index_by_time = {str(r["timestamp"]): i for i, r in enumerate(rows)}
    audit = []
    for t in trades:
        entry_i = index_by_time[t["entry_time"]]
        signal_i = entry_i - 1
        if signal_i < 0 or str(rows[signal_i]["timestamp"])[:10] != str(rows[entry_i]["timestamp"])[:10]:
            raise ValueError("Entry has no same-session signal candle: " + t["entry_time"])
        signal = exp83.is_major_long_to_short_reversal(highs, lows, closes, market, signal_i)
        if signal is None:
            raise ValueError("EXP83 entry could not be matched to V16 signal: " + t["entry_time"])
        peak_i = signal["peak_i"]
        peak = float(signal["peak_high"])
        left_rise = pct(peak, float(signal["prior_low"]))
        entry_delay = 100.0 * (peak / float(t["entry_price"]) - 1.0)
        record = {
            "symbol": symbol, "entry_time": t["entry_time"],
            "exit_time": t["exit_time"], "exit_reason": t["exit_reason"],
            "gross_pnl_pct": t["gross_pnl_pct"],
            "commission_pct": 2*FEE, "net_pnl_pct": t["net_pnl_pct"],
            "bars_held": t["bars_held"],
            "signal_time": str(rows[signal_i]["timestamp"]),
            "peak_time": str(rows[peak_i]["timestamp"]),
            "peak_age_bars": signal["peak_age"],
            "left_rise_from_prior_low_pct": safe_round(left_rise),
            "entry_distance_below_peak_pct": safe_round(entry_delay),
        }
        for w in WINDOWS:
            g = geometry(rows, signal_i, w)
            for field in ("height_pct", "slope_pct_per_5m", "efficiency",
                          "net_change_pct", "range_position", "top_age_bars",
                          "bottom_age_bars"):
                record[f"w{w}_{field}"] = g[field] if g else None
        for horizon in (3, 6, 12):
            f = future_short_move(rows, entry_i, horizon)
            for field in ("best_decline_pct", "worst_rise_pct", "last_close_short_pct"):
                record[f"future_{horizon}_{field}"] = f[field] if f else None
        audit.append(record)
    write_csv(OUT / (symbol.lower() + "_entry_geometry.csv"), audit)
    # Descriptive only; categories do not imply executable filters.
    categories = {}
    for w in WINDOWS:
        key = f"w{w}_height_pct"
        valid = [r for r in audit if r[key] is not None]
        missing = [r for r in audit if r[key] is None]
        categories[f"window_{w}"] = {
            "available": len(valid), "unavailable": len(missing),
            "height_pct_min": safe_round(min((r[key] for r in valid), default=float("nan"))),
            "height_pct_max": safe_round(max((r[key] for r in valid), default=float("nan"))),
            "available_trade_outcomes": summarize_group(valid),
            "unavailable_trade_outcomes": summarize_group(missing),
            "entries": [
                {"entry_time": r["entry_time"], "height_pct": r[key],
                 "slope_pct_per_5m": r[f"w{w}_slope_pct_per_5m"],
                 "efficiency": r[f"w{w}_efficiency"],
                 "net_pnl_pct": r["net_pnl_pct"]}
                for r in audit
            ],
        }
    return {
        "candles": len(rows), "v16_candidates": candidates,
        "rejected_signals": rejected,
        "baseline": summarize_group(trades),
        "baseline_exit_reasons": dict(Counter(t["exit_reason"] for t in trades)),
        "geometry": categories,
    }

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "experiment": "EXP92",
        "research_only": True,
        "description": "Dual-trail high/low range, signed slope, path efficiency and V16 peak geometry at completed SHORT entry signals",
        "execution": "Unchanged EXP83 V16 SHORT + ST exit; signals at close, next open entry; stop and session liquidation as EXP83",
        "limitations": [
            "All geometry is observational; NO new filter, trade or performance improvement is claimed.",
            "Forward 3/6/12-bar outcomes are hindsight labels only, not signals.",
            "Early-session windows unavailable; do not mix overnight candles.",
            "No LONG engine or TSLA/MSFT candles tested; those require a separate baseline/data check.",
            "Small sample; no out-of-sample validation. Percentage sums are not compounded portfolio returns.",
            "Round-trip commissions 0.20%; slippage excluded."
        ],
        "symbols": {},
    }
    for symbol, path in exp83.DATA.items():
        result["symbols"][symbol] = run(symbol, path)
    (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("EXP92 — DUAL-TRAIL MOUNTAIN GEOMETRY — RESEARCH ONLY")
    for symbol, report in result["symbols"].items():
        print("\n", symbol, "baseline:", report["baseline"])
        print("V16 candidates:", report["v16_candidates"], "rejected:", report["rejected_signals"])
        for w, details in report["geometry"].items():
            print(w, "available:", details["available"], "unavailable:", details["unavailable"],
                  "height range:", details["height_pct_min"], "to", details["height_pct_max"])
            for item in details["entries"]:
                print(" ", item)
    print("\nFull summary and per-entry CSV:", OUT)
    print("No trading rule has been changed.")

if __name__ == "__main__":
    main()
