
# aimn_exp151_step13_forward_data_audit.py
#!/usr/bin/env python3
"""
EXP151 STEP 13
Forward data intake and integrity audit.

READ ONLY.
NO FILE WRITES.
NO ORDERS.
NO PRODUCTION CHANGES.

Input: JSON list of 5-minute OHLCV candle objects.

The script validates candle structure, session coverage,
historical warmup and frozen research source integrity.

It does not fetch data, run trades or calculate P&L.
"""

import argparse
import hashlib
import inspect
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, date, time, timedelta
from pathlib import Path

import aimn_exp135_breakout_confirmation as e


FROZEN_START = date(2026, 11, 16)

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

SPEC_HASH = (
    "c9b0192890dd3cbee1c0c82d240ef7b5eaa0dc338074f2bb05134e9501cdca54"
)

SIM_HASH = (
    "b5567c79fdc9aa6e4b6a1df4c5ee8d530a37287688239be4b3a15fb6194d39e5"
)

PREP_HASH = (
    "595e3ea494d27f6c573a25870ed3ee4b11e5a1c9e65bf0a1eea006289b5a55cc"
)

REQUIRED_OPENING = {
    "09:35", "09:40", "09:45", "09:50", "10:00"
}

MIN_WARMUP_SESSIONS = 20

# Explicit known US market half-day dates in the
# initial forward-validation period.
# Extend only after checking the official exchange calendar.
KNOWN_HALF_DAYS = {
    date(2026, 11, 27),
    date(2026, 12, 24),
}


def banner(message):
    print("\n" + "=" * 96)
    print(message)
    print("=" * 96)


def sha(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def frozen_integrity():
    spec_hash = sha(
        json.dumps(
            SPEC,
            sort_keys=True,
            separators=(",", ":")
        )
    )

    sim_hash = sha(
        inspect.getsource(e.exp117.simulate)
    )

    prep_hash = sha(
        inspect.getsource(e.exp129.prepare)
    )

    print("SPEC SHA256:", spec_hash)
    print("SIMULATOR SHA256:", sim_hash)
    print("PREPARE SHA256:", prep_hash)

    assert spec_hash == SPEC_HASH, "FROZEN SPEC CHANGED"
    assert sim_hash == SIM_HASH, "SIMULATOR CHANGED"
    assert prep_hash == PREP_HASH, "PREPARE CHANGED"
    assert math.isclose(
        2 * float(e.exp79.FEE),
        0.2,
        abs_tol=1e-12
    ), "FEE CHANGED"

    assert SPEC["production_enabled"] is False

    print("FROZEN INTEGRITY: PASS")


def parse_timestamp(value):
    dt = datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )

    if dt.tzinfo is not None:
        raise ValueError(
            "Timezone-aware timestamps require explicit "
            "exchange-local normalization before this audit"
        )

    return dt


def expected_labels(day):
    start = datetime.combine(day, time(9, 30))

    # Normal regular session: 09:30 through 15:55.
    # Known half-day: 09:30 through 12:55.
    count = 42 if day in KNOWN_HALF_DAYS else 78

    return {
        start + timedelta(minutes=5 * i)
        for i in range(count)
    }


def load_and_validate(path):
    raw = json.loads(
        Path(path).read_text(encoding="utf-8")
    )

    if not isinstance(raw, list):
        raise ValueError("Input must be a JSON list")

    rows = []
    issues = Counter()
    examples = []

    previous = None
    seen = set()

    for position, item in enumerate(raw):
        try:
            if not isinstance(item, dict):
                raise ValueError("Not a candle object")

            dt = parse_timestamp(item["timestamp"])

            o, h, l, c = (
                float(item[key])
                for key in ("open", "high", "low", "close")
            )

            volume = float(item["volume"])

            if not all(
                math.isfinite(v)
                for v in (o, h, l, c, volume)
            ):
                raise ValueError("Nonfinite OHLCV")

            if not (
                0 < l <= min(o, c)
                and max(o, c) <= h
            ):
                raise ValueError("Invalid OHLC")

            if volume < 0:
                raise ValueError("Negative volume")

            if (
                dt.minute % 5 != 0
                or dt.second != 0
                or dt.microsecond != 0
            ):
                raise ValueError("Invalid 5-minute label")

            if dt in seen:
                issues["DUPLICATE_TIMESTAMP"] += 1

            if previous is not None and dt <= previous:
                issues["NON_ASCENDING_INPUT"] += 1

            if dt.weekday() >= 5:
                issues["WEEKEND_CANDLE"] += 1

            if not (
                time(9, 30) <= dt.time()
                <= time(15, 55)
            ):
                issues["OUTSIDE_REGULAR_HOURS"] += 1

            seen.add(dt)
            previous = dt

            rows.append({
                "timestamp": dt,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": volume,
            })

        except (KeyError, TypeError, ValueError) as exc:
            issues["INVALID_ROW"] += 1

            if len(examples) < 12:
                examples.append(
                    f"ROW {position}: {exc}"
                )

    rows.sort(key=lambda r: r["timestamp"])

    return rows, issues, examples


def audit_symbol(symbol, path):
    banner(f"DATASET: {symbol}")

    print("FILE:", path)

    rows, issues, examples = load_and_validate(path)

    print("TOTAL CANDLES:", len(rows))

    if not rows:
        print("STATUS: NO CANDLES")
        return False

    print(
        "FIRST TIMESTAMP:",
        rows[0]["timestamp"].isoformat(sep=" ")
    )
    print(
        "LAST TIMESTAMP:",
        rows[-1]["timestamp"].isoformat(sep=" ")
    )

    sessions = defaultdict(list)

    for row in rows:
        sessions[row["timestamp"].date()].append(row)

    warmup_days = sorted(
        day for day in sessions
        if day < FROZEN_START
    )

    forward_days = sorted(
        day for day in sessions
        if day >= FROZEN_START
    )

    print("PRE-FORWARD SESSIONS:", len(warmup_days))
    print("FORWARD SESSIONS:", len(forward_days))

    if len(warmup_days) < MIN_WARMUP_SESSIONS:
        issues["INSUFFICIENT_WARMUP"] += 1

    print(
        "MINIMUM WARMUP SESSIONS:",
        MIN_WARMUP_SESSIONS
    )

    complete_forward = 0
    incomplete_forward = 0
    pattern_windows = 0

    for day in sorted(sessions):
        actual = {
            r["timestamp"]
            for r in sessions[day]
        }

        expected = expected_labels(day)

        missing = expected - actual
        unexpected = actual - expected

        if missing:
            issues["SESSIONS_WITH_MISSING_BARS"] += 1

        if unexpected:
            issues["SESSIONS_WITH_UNEXPECTED_BARS"] += 1

        if day < FROZEN_START:
            continue

        opening_times = {
            datetime.combine(
                day,
                datetime.strptime(clock, "%H:%M").time()
            )
            for clock in REQUIRED_OPENING
        }

        opening_complete = opening_times <= actual

        if opening_complete:
            pattern_windows += 1
        else:
            issues["INCOMPLETE_OPENING_WINDOW"] += 1

        if not missing and not unexpected:
            complete_forward += 1
            status = "COMPLETE"
        else:
            incomplete_forward += 1
            status = "INCOMPLETE"

        print(
            "FORWARD SESSION:",
            day,
            "STATUS:", status,
            "BARS:", len(sessions[day]),
            "EXPECTED:", len(expected),
            "MISSING:", len(missing),
            "UNEXPECTED:", len(unexpected),
            "OPENING_WINDOW:",
            "COMPLETE" if opening_complete else "INCOMPLETE"
        )

        if missing:
            print(
                "  FIRST MISSING:",
                sorted(missing)[0].isoformat(sep=" ")
            )

        if unexpected:
            print(
                "  FIRST UNEXPECTED:",
                sorted(unexpected)[0].isoformat(sep=" ")
            )

    print("COMPLETE FORWARD SESSIONS:", complete_forward)
    print("INCOMPLETE FORWARD SESSIONS:", incomplete_forward)
    print("COMPLETE OPENING WINDOWS:", pattern_windows)

    print("ISSUES:", dict(issues))

    for example in examples:
        print("EXAMPLE:", example)

    if not forward_days:
        print(
            "FORWARD DATA: NONE - HISTORICAL WARMUP ONLY"
        )

    if issues:
        print("DATA INTEGRITY: INVESTIGATE")
        return False

    print("DATA STRUCTURE INTEGRITY: PASS")

    if not forward_days:
        print("FORWARD STATUS: AWAITING NEW DATA")
    else:
        print(
            "FORWARD STATUS: STRUCTURALLY READY "
            "FOR CAUSAL TRADE EVALUATION"
        )

    return True


def main():
    parser = argparse.ArgumentParser(
        description="EXP151 read-only forward intake audit"
    )

    parser.add_argument(
        "--nvda",
        help="NVDA 5-minute OHLCV JSON path"
    )

    parser.add_argument(
        "--aapl",
        help="AAPL 5-minute OHLCV JSON path"
    )

    args = parser.parse_args()

    banner(
        "EXP151 STEP 13 - FORWARD DATA INTAKE AUDIT"
    )

    print(
        "READ ONLY | NO ORDERS | "
        "NO WRITES | NO STRATEGY CHANGES"
    )

    banner("PART A - FROZEN SOURCE INTEGRITY")
    frozen_integrity()

    banner("PART B - INPUT VALIDATION")

    supplied = [
        (symbol, path)
        for symbol, path in (
            ("NVDA", args.nvda),
            ("AAPL", args.aapl)
        )
        if path
    ]

    if not supplied:
        print("FORWARD INPUTS: NONE")
        print("STATUS: READY FOR DATA")
        print("NO FORWARD RESULTS CLAIMED")
    else:
        outcomes = []

        for symbol, path in supplied:
            outcomes.append(
                audit_symbol(symbol, path)
            )

        banner("PART C - FINAL VERDICT")

        if all(outcomes):
            print("SUPPLIED DATA STRUCTURE: PASS")
        else:
            print(
                "SUPPLIED DATA STRUCTURE: "
                "INVESTIGATION REQUIRED"
            )

    print()
    print(
        "LIMITATION: Provider timezone and "
        "bar-start convention are not verified."
    )
    print(
        "LIMITATION: Full exchange holiday/half-day "
        "calendar is not independently verified."
    )
    print(
        "LIMITATION: Warmup count does not prove "
        "indicator or position-state equivalence."
    )
    print(
        "LIMITATION: No trades or P&L evaluated."
    )
    print("FORWARD START:", FROZEN_START)
    print("FILES WRITTEN: NONE")
    print("ORDERS PLACED: NONE")


if __name__ == "__main__":
    main()
