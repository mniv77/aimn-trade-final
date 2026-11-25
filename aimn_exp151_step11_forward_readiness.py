# aimn_exp151_step11_forward_readiness.py

#!/usr/bin/env python3
"""EXP151 Step 11: frozen-spec and forward-data readiness (read-only).

With no arguments, verifies the frozen specification and research source hashes.
With --nvda and/or --aapl, inspects new 5-minute OHLC files for
post-2026-11-16 higher-low observations. It does NOT infer entry eligibility,
original exits, actual fills, or strategy P&L from candles alone.
"""
import argparse
import hashlib
import inspect
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import aimn_exp135_breakout_confirmation as e

SPEC = {
    "experiment": "EXP151",
    "phase": "FORWARD_VALIDATION",
    "symbols": ["NVDA", "AAPL"],
    "direction": "SHORT",
    "timeframe_minutes": 5,
    "entry_clock": "09:35",
    "signal_offset_minutes": 15,
    "signal": "LOW_J_GT_LOW_J_MINUS_1_GT_LOW_J_MINUS_2",
    "execution_offset_from_signal_label_minutes": 10,
    "execution_price": "FOLLOWING_BAR_OPEN",
    "adverse_slippage_bps": 10,
    "fee_source": "EXISTING_EXP79_FEE",
    "original_exit_priority": "EARLIER_OR_EQUAL",
    "validation_start_date": "2026-11-16",
    "validation_end_date": None,
    "production_enabled": False,
}
SPEC_HASH = "c9b0192890dd3cbee1c0c82d240ef7b5eaa0dc338074f2bb05134e9501cdca54"
SIM_HASH = "b5567c79fdc9aa6e4b6a1df4c5ee8d530a37287688239be4b3a15fb6194d39e5"
PREP_HASH = "595e3ea494d27f6c573a25870ed3ee4b11e5a1c9e65bf0a1eea006289b5a55cc"

def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def check_frozen():
    actual = sha(json.dumps(SPEC, sort_keys=True, separators=(",", ":")))
    sim = sha(inspect.getsource(e.exp117.simulate))
    prep = sha(inspect.getsource(e.exp129.prepare))
    print("FROZEN SPEC SHA256:", actual)
    print("SIMULATOR SHA256:", sim)
    print("PREPARE SHA256:", prep)
    assert actual == SPEC_HASH, "FROZEN SPEC CHANGED: STOP"
    assert sim == SIM_HASH, "SIMULATOR SOURCE CHANGED: STOP"
    assert prep == PREP_HASH, "PREPARE SOURCE CHANGED: STOP"
    assert float(e.exp79.FEE) * 2 == 0.2, "FEE CHANGED: STOP"
    assert SPEC["production_enabled"] is False
    print("SOURCE / FROZEN SPEC INTEGRITY: PASS")

def parse_stamp(value):
    value = str(value).strip()
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        raise ValueError("Timezone-aware input: normalize and verify exchange-local bar labels separately")
    return dt

def load_rows(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Expected a JSON list of OHLCV candle objects")
    rows = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Row {index}: not an object")
        dt = parse_stamp(item["timestamp"])
        o, h, l, c = (float(item[k]) for k in ("open", "high", "low", "close"))
        if not (0 < l <= min(o, c) <= max(o, c) <= h):
            raise ValueError(f"Row {index}: invalid OHLC")
        if dt.minute % 5 != 0 or dt.second or dt.microsecond:
            raise ValueError(f"Row {index}: not a five-minute label")
        rows.append((dt, {"open": o, "high": h, "low": l, "close": c}))
    rows.sort(key=lambda x: x[0])
    if len({dt for dt, _ in rows}) != len(rows):
        raise ValueError("Duplicate timestamps")
    return rows

def audit_symbol(symbol, path):
    print("\n" + "-" * 90)
    print("SYMBOL:", symbol, "INPUT:", path)
    rows = load_rows(path)
    print("TOTAL CANDLES:", len(rows))
    if not rows:
        print("NO CANDLES: NO OBSERVATIONS")
        return
    print("FIRST LABEL:", rows[0][0].isoformat(sep=" "))
    print("LAST LABEL:", rows[-1][0].isoformat(sep=" "))
    index = dict(rows)
    dates = sorted({dt.date() for dt, _ in rows if dt.date().isoformat() >= SPEC["validation_start_date"]})

    counts = Counter()
    for day in dates:
        # Presumed exchange-local 5-minute bar-start labels.
        t35 = datetime.combine(
            day, datetime.strptime("09:35", "%H:%M").time()
        )
        t40 = t35 + timedelta(minutes=5)
        t45 = t35 + timedelta(minutes=10)
        t50 = t35 + timedelta(minutes=15)
        t1000 = t35 + timedelta(minutes=25)

        required = (t35, t40, t45, t50, t1000)
        counts["FORWARD_DATES"] += 1

        if any(t not in index for t in required):
            counts["INCOMPLETE_DATES"] += 1
            print(
                day,
                "INCOMPLETE: required opening labels not all present"
            )
            continue

        counts["COMPLETE_OPENING_WINDOWS"] += 1

        lows = [
            index[t]["low"]
            for t in (t40, t45, t50)
        ]

        signal = lows[0] < lows[1] < lows[2]

        if signal:
            counts["PATTERN_OBSERVATIONS"] += 1

        cover_open = index[t1000]["open"] * 1.001

        print(
            day,
            "PATTERN:", signal,
            "LOWS:", lows,
            "10:00_OPEN:", f'{index[t1000]["open"]:.6f}',
            "ADVERSE_10BPS_COVER:", f"{cover_open:.6f}",
            "ENTRY_ELIGIBILITY: UNKNOWN",
            "ORIGINAL_EXIT_PRIORITY: UNKNOWN"
        )

    print("SUMMARY:", dict(counts))
    print(
        "These are candle-pattern observations, "
        "NOT qualifying trade signals or P&L."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--nvda",
        help="New NVDA 5m candle JSON file"
    )
    parser.add_argument(
        "--aapl",
        help="New AAPL 5m candle JSON file"
    )

    args = parser.parse_args()

    print("=" * 90)
    print("EXP151 STEP 11 - FORWARD READINESS / CANDLE OBSERVATION")
    print("READ ONLY | NO ORDERS | NO WRITES | NO PRODUCTION CHANGES")
    print("=" * 90)

    check_frozen()

    if not args.nvda and not args.aapl:
        print("FORWARD INPUTS: NONE")
        print("STATUS: READY FOR DATA; NO FORWARD RESULTS CLAIMED")

    for symbol, path in (
        ("NVDA", args.nvda),
        ("AAPL", args.aapl)
    ):
        if path:
            audit_symbol(symbol, path)

    print(
        "\nIMPORTANT: timestamp timezone/bar-start convention "
        "is NOT independently verified."
    )
    print(
        "Forward trade outcomes require causal entry "
        "and original-exit replay."
    )
    print("FILES WRITTEN: NONE | ORDERS PLACED: NONE")


if __name__ == "__main__":
    main()
