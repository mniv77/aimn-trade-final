# aimn_exp151_step12_forward_evaluator.py
#!/usr/bin/env python3
"""EXP151 Step 12: read-only forward trade evaluator.

Inputs: JSON lists of 5-minute candles with timestamp/open/high/low/close.
Provide sufficient PRE-validation history for indicator warmup and state.
No orders, no writes, no changes to existing source or frozen parameters.
"""
import argparse
import hashlib
import inspect
import json
import math
import textwrap
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import aimn_exp135_breakout_confirmation as e

SPEC = {
    "experiment": "EXP151", "phase": "FORWARD_VALIDATION",
    "symbols": ["NVDA", "AAPL"], "direction": "SHORT",
    "timeframe_minutes": 5, "entry_clock": "09:35",
    "signal_offset_minutes": 15,
    "signal": "LOW_J_GT_LOW_J_MINUS_1_GT_LOW_J_MINUS_2",
    "execution_offset_from_signal_label_minutes": 10,
    "execution_price": "FOLLOWING_BAR_OPEN",
    "adverse_slippage_bps": 10,
    "fee_source": "EXISTING_EXP79_FEE",
    "original_exit_priority": "EARLIER_OR_EQUAL",
    "validation_start_date": "2026-11-16",
    "validation_end_date": None, "production_enabled": False,
}
EXPECTED_SPEC_HASH = "c9b0192890dd3cbee1c0c82d240ef7b5eaa0dc338074f2bb05134e9501cdca54"
EXPECTED_SIM_HASH = "b5567c79fdc9aa6e4b6a1df4c5ee8d530a37287688239be4b3a15fb6194d39e5"
EXPECTED_PREP_HASH = "595e3ea494d27f6c573a25870ed3ee4b11e5a1c9e65bf0a1eea006289b5a55cc"


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def check_integrity():
    spec_hash = sha(json.dumps(SPEC, sort_keys=True, separators=(",", ":")))
    sim_source = inspect.getsource(e.exp117.simulate)
    sim_hash = sha(sim_source)
    prep_hash = sha(inspect.getsource(e.exp129.prepare))
    print("SPEC SHA256:", spec_hash)
    print("SIMULATOR SHA256:", sim_hash)
    print("PREPARE SHA256:", prep_hash)
    assert spec_hash == EXPECTED_SPEC_HASH, "Frozen EXP151 specification changed"
    assert sim_hash == EXPECTED_SIM_HASH, "Simulator source changed"
    assert prep_hash == EXPECTED_PREP_HASH, "Preparation source changed"
    assert math.isclose(float(e.exp79.FEE) * 2, 0.2, abs_tol=1e-10)
    assert SPEC["production_enabled"] is False
    print("FROZEN INTEGRITY: PASS")
    return sim_source


def research_simulator(source):
    target = 'elif st[i]!="LONG":'
    assert source.count(target) == 1, "Research patch target changed"
    patched = textwrap.dedent(source).replace(target, 'elif False:', 1)
    namespace = dict(e.exp117.simulate.__globals__)
    exec(compile(patched, "<EXP151_IN_MEMORY_ONLY>", "exec"), namespace)
    return namespace["simulate"]


def parse_timestamp(value):
    dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        raise ValueError("Timezone-aware timestamps require separately verified normalization")
    if dt.minute % 5 or dt.second or dt.microsecond:
        raise ValueError("Non-5-minute timestamp: " + str(value))
    return dt


def read_candles(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Input must be a JSON list of OHLCV candle objects")
    rows = []
    for n, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError("Non-object candle at row " + str(n))
        dt = parse_timestamp(item["timestamp"])
        o, h, l, c = [float(item[k]) for k in ("open", "high", "low", "close")]
        if not all(math.isfinite(v) for v in (o, h, l, c)):
            raise ValueError("Non-finite price at row " + str(n))
        if not (0 < l <= min(o, c) <= max(o, c) <= h):
            raise ValueError("Invalid OHLC at row " + str(n))
        rows.append((dt, item))
    rows.sort(key=lambda pair: pair[0])
    if len({dt for dt, _ in rows}) != len(rows):
        raise ValueError("Duplicate timestamps")
    return [item for _, item in rows], [dt for dt, _ in rows]


def prepare(rows):
    times = [str(r["timestamp"]) for r in rows]
    closes = [float(r["close"]) for r in rows]
    starts = e.exp129.swing.get_session_starts(times)
    ph, pl, counts = e.exp129.swing.confirmed_pivots(rows, times, starts)
    states = [e.exp129.swing.structure(rows, times, starts, i, ph, pl, counts)
              for i in range(len(rows))]
    st = e.exp129.base.calculate_supertrend(rows, atr_period=10, multiplier=3.0)["st_trend"].tolist()
    rsi = e.exp129.base.rsi_wilder(closes)
    market = [e.exp129.base.get_market_state(closes, i) for i in range(len(rows))]
    return states, st, rsi, market


def evaluate(symbol, path, simulator):
    print("\n" + "-" * 92)
    print("SYMBOL:", symbol, "FILE:", path)
    rows, dates = read_candles(path)
    if not rows:
        print("STATUS: NO CANDLES")
        return
    start = datetime.fromisoformat(SPEC["validation_start_date"])
    warmup = sum(dt < start for dt in dates)
    forward = sum(dt >= start for dt in dates)
    print("CANDLES:", len(rows), "PRE-VALIDATION:", warmup, "FORWARD:", forward)
    print("FIRST:", dates[0], "LAST:", dates[-1])
    if not forward:
        print("STATUS: NO FORWARD CANDLES; NO FORWARD RESULTS")
        return
    if warmup < 200:
        print("STATUS: BLOCKED - fewer than 200 pre-validation warmup candles")
        print("Supply a continuous source file with sufficient prior sessions.")
        return
    # Require every forward date with data to have a preceding bar in the file.
    # The simulator uses the whole supplied chronology to reconstruct state.
    states, st, rsi, market = prepare(rows)
    trades, events, candidates, rejected = simulator(rows, st, rsi, market, states, "JOINT_SWING")
    by_stamp = {dt: row for dt, row in zip(dates, rows)}
    stats = Counter()
    completed = []
    print("RESEARCH TRADES (ALL DATES):", len(trades))
    print("CANDIDATES:", candidates, "REJECTIONS:", rejected)
    for trade in trades:
        entry_dt = parse_timestamp(trade["entry_time"])
        if entry_dt < start or entry_dt.strftime("%H:%M") != "09:35":
            continue
        stats["FORWARD_OPENING_SHORT_ENTRIES"] += 1
        day = entry_dt.date()
        t40 = datetime.combine(day, datetime.strptime("09:40", "%H:%M").time())
        t45 = t40 + timedelta(minutes=5)
        t50 = t45 + timedelta(minutes=5)
        t1000 = t50 + timedelta(minutes=10)
        original_reason = str(trade.get("exit_reason", ""))
        exit_dt = parse_timestamp(trade["exit_time"])
        print("\nTRADE:", symbol, day, "ENTRY:", entry_dt,
              "ORIGINAL EXIT:", exit_dt, original_reason)
        if original_reason == "DATA_END":
            stats["UNRESOLVED_DATA_END"] += 1
            print("STATUS: UNRESOLVED - artificial DATA_END; no outcome counted")
            continue
        original_net = float(trade["net_pnl_pct"])
        if not math.isfinite(original_net):
            raise ValueError("Non-finite original net P&L")
        # If original exit precedes 09:55, the proposed signal is not
        # available while this trade remains open. Keep original exit.
        if exit_dt < t50 + timedelta(minutes=5):
            stats["ORIGINAL_EXIT_BEFORE_SIGNAL"] += 1
            new_net = original_net
            reason = "ORIGINAL_EXIT_BEFORE_SIGNAL"
            signal = "NOT_EVALUATED"
        elif not all(t in by_stamp for t in (t40, t45, t50)):
            stats["INCOMPLETE_SIGNAL_WINDOW"] += 1
            print("STATUS: INCOMPLETE - missing signal candles")
            continue
        else:
            lows = [float(by_stamp[t]["low"]) for t in (t40, t45, t50)]
            signal = lows[0] < lows[1] < lows[2]
            print("09:40/09:45/09:50 LOWS:", lows, "PATTERN:", signal)
            if not signal:
                stats["NO_PATTERN"] += 1
                new_net = original_net
                reason = "NO_PATTERN"
            else:
                stats["PATTERN_WHILE_OPEN_AT_SIGNAL"] += 1
                if exit_dt <= t1000:
                    stats["ORIGINAL_EXIT_PRIORITY"] += 1
                    new_net = original_net
                    reason = "ORIGINAL_EXIT_PRIORITY"
                elif t1000 not in by_stamp:
                    stats["MISSING_1000_BAR"] += 1
                    print("STATUS: INCOMPLETE - missing 10:00 execution candle")
                    continue
                else:
                    cover_open = float(by_stamp[t1000]["open"])
                    cover_price = cover_open * 1.001
                    entry_price = float(trade["entry_price"])
                    new_net = (entry_price / cover_price - 1.0) * 100 - 2 * float(e.exp79.FEE)
                    stats["HYPOTHETICAL_EXIT_APPLIED"] += 1
                    reason = "FROZEN_HIGHER_LOW_EXIT"
                    print("10:00 OPEN:", cover_open, "ADVERSE COVER:", cover_price)
        delta = new_net - original_net
        completed.append((original_net, new_net))
        stats["COMPLETED_EVALUATED"] += 1
        stats["ORIGINAL_WIN" if original_net > 0 else "ORIGINAL_NONWIN"] += 1
        stats["FROZEN_WIN" if new_net > 0 else "FROZEN_NONWIN"] += 1
        print("STATUS: COMPLETED", "SIGNAL:", signal, "DECISION:", reason)
        print("ORIGINAL NET: %+.6f%% | FROZEN NET: %+.6f%% | CHANGE: %+.6f pp" %
              (original_net, new_net, delta))
    print("\nFORWARD SUMMARY:", symbol)
    for key in sorted(stats):
        print(" ", key, stats[key])
    if completed:
        original_sum = sum(a for a, _ in completed)
        frozen_sum = sum(b for _, b in completed)
        print("SUM ORIGINAL NET: %+.6f%%" % original_sum)
        print("SUM FROZEN NET: %+.6f%%" % frozen_sum)
        print("SUM CHANGE: %+.6f percentage points" % (frozen_sum - original_sum))
        print("SUMS ARE NOT COMPOUNDED PORTFOLIO RETURNS")
    else:
        print("NO COMPLETED ELIGIBLE FORWARD TRADES")
    print("CAUTION: SOURCE PROVENANCE / BAR-START TIMEZONE NOT INDEPENDENTLY VERIFIED")
    print("CAUTION: SIMULATED FILL AND SLIPPAGE, NOT LIVE EXECUTION")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nvda", help="NVDA JSON 5-minute candles including warmup history")
    parser.add_argument("--aapl", help="AAPL JSON 5-minute candles including warmup history")
    args = parser.parse_args()
    print("=" * 92)
    print("EXP151 STEP 12 - CAUSAL FORWARD TRADE EVALUATOR")
    print("READ ONLY | NO FILE WRITES | NO ORDERS | NO PRODUCTION CHANGES")
    print("=" * 92)
    source = check_integrity()
    simulator = research_simulator(source)
    print("RESEARCH FILTER ADJUSTMENT: IN MEMORY ONLY")
    print("FORWARD START:", SPEC["validation_start_date"])
    if not args.nvda and not args.aapl:
        print("FORWARD INPUTS: NONE")
        print("STATUS: READY FOR FORWARD DATA; NO FORWARD RESULTS")
    for symbol, path in (("NVDA", args.nvda), ("AAPL", args.aapl)):
        if path:
            evaluate(symbol, path, simulator)
    print("\nFILES WRITTEN: NONE | ORDERS PLACED: NONE")


if __name__ == "__main__":
    main()
