
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-44
OPENING REVERSAL AND SHORT ENTRY TIMING

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Questions:
1. Has an opening selloff already occurred?
2. Is price recovering from an opening low?
3. Has a completed 5m bearish reversal appeared?
4. Has a lower high been confirmed before entry?
5. How do July 24, July 28, and Aug 3 differ?

No lookahead.
No file writes.
No production or V18 changes.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, time
from collections import defaultdict

LAB = Path("kiss/visual_research")
sys.path.insert(0, str(LAB.resolve()))

import step59f_5h43c_flat_long_replay as engine


PARAMS = {
    "entry_cutoff": "15:45",
    "commission_pct": 0.01,
    "entry_slippage_pct": 0.02,
    "exit_slippage_pct": 0.02,
    "trailing_minus_pct": 1.5,
    "rsi_rescue_short": 80.0,
    "atr_exhaustion_filter": True,
    "flat_long_filter": True,
}

DATASETS = {
    "RESEARCH": (
        LAB / "aimn_nvda_candles.json",
        22,
        6.764673,
    ),
    "VALIDATION": (
        LAB / "nvda_sep_oct_2026_validation.json",
        14,
        2.219621,
    ),
}

PRIORITY_DATES = {
    "2026-07-24",
    "2026-07-28",
    "2026-08-03",
    "2026-08-21",
    "2026-09-02",
}

TOLERANCE = 0.000002


def parse_time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def pct(new_value, old_value):
    if old_value is None or old_value == 0:
        return None
    return (new_value / old_value - 1.0) * 100.0


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def load_rows(path):
    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    rows = (
        data["candles"]
        if isinstance(data, dict)
        else data
    )

    rows = sorted(
        rows,
        key=lambda r: parse_time(r["timestamp"]),
    )

    timestamps = [
        parse_time(r["timestamp"])
        for r in rows
    ]

    assert len(timestamps) == len(set(timestamps)), (
        f"Duplicate timestamps: {path}"
    )

    return rows


def regular_candles(rows):
    result = []

    for row in rows:
        stamp = parse_time(row["timestamp"])

        if not time(9, 30) <= stamp.time() < time(16, 0):
            continue

        result.append({
            "time": stamp,
            "end": stamp + timedelta(minutes=5),
            "date": stamp.date(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })

    return result


def group_sessions(candles):
    sessions = defaultdict(list)

    for candle in candles:
        sessions[candle["date"]].append(candle)

    for day in sessions:
        sessions[day].sort(
            key=lambda c: c["time"]
        )

    return sessions


def opening_phase(minutes):
    if minutes < 30:
        return "FIRST_30M"

    if minutes < 60:
        return "SECOND_30M"

    return "AFTER_FIRST_HOUR"


def selloff_class(value):
    if value is None:
        return "NO_SELLOFF_REFERENCE"

    if value >= 1.00:
        return "SELLOFF_1_PLUS"

    if value >= 0.50:
        return "SELLOFF_0_5_TO_1"

    if value >= 0.20:
        return "SELLOFF_0_2_TO_0_5"

    return "SELLOFF_UNDER_0_2"


def recovery_class(value):
    if value is None:
        return "NO_RECOVERY_REFERENCE"

    if value >= 1.00:
        return "RECOVERY_1_PLUS"

    if value >= 0.50:
        return "RECOVERY_0_5_TO_1"

    if value >= 0.20:
        return "RECOVERY_0_2_TO_0_5"

    return "RECOVERY_UNDER_0_2"


def candle_direction(candle):
    if candle["close"] > candle["open"]:
        return "UP"

    if candle["close"] < candle["open"]:
        return "DOWN"

    return "FLAT"


def detect_reversal(completed):
    """
    Observational three-candle pattern:

    A bearish reversal is identified when:
    - Candle A rises.
    - Candle B forms a higher high.
    - Candle C closes below candle B's low.

    The signal is known only after C completes.
    """

    for i in range(2, len(completed)):
        a = completed[i - 2]
        b = completed[i - 1]
        c = completed[i]

        if (
            a["close"] > a["open"]
            and b["high"] > a["high"]
            and c["close"] < b["low"]
        ):
            return c["end"]

    return None


def detect_lower_high(completed):
    """
    Confirmed local pivot-high proxy.

    A pivot high at B requires:
    A.high < B.high > C.high.

    B is known as a pivot only when C completes.
    Two confirmed pivot highs are required to
    identify a lower high.
    """

    pivots = []

    for i in range(1, len(completed) - 1):
        a = completed[i - 1]
        b = completed[i]
        c = completed[i + 1]

        if (
            b["high"] > a["high"]
            and b["high"] > c["high"]
        ):
            pivots.append({
                "price": b["high"],
                "confirmed": c["end"],
            })

    if len(pivots) < 2:
        return None

    for i in range(1, len(pivots)):
        if pivots[i]["price"] < pivots[i - 1]["price"]:
            return pivots[i]["confirmed"]

    return None


def analyze_entry(sessions, entry):
    day = entry.date()
    session = sessions.get(day, [])

    entry_candle = next(
        (
            c for c in session
            if c["time"] == entry
        ),
        None,
    )

    if entry_candle is None:
        raise ValueError(
            f"Entry candle missing: {entry}"
        )

    opening_candle = next(
        (
            c for c in session
            if c["time"].time() == time(9, 30)
        ),
        None,
    )

    opening_price = (
        opening_candle["open"]
        if opening_candle is not None
        else None
    )

    entry_price = entry_candle["open"]

    completed = [
        c for c in session
        if c["end"] <= entry
    ]

    # Only the continuous sequence from 09:30.
    opening_completed = []

    expected_time = datetime.combine(
        day, time(9, 30)
    )

    for candle in completed:
        if candle["time"] != expected_time:
            break

        opening_completed.append(candle)

        expected_time += timedelta(minutes=5)

    opening_high = (
        max(c["high"] for c in opening_completed)
        if opening_completed
        else None
    )

    opening_low = (
        min(c["low"] for c in opening_completed)
        if opening_completed
        else None
    )

    selloff = (
        max(0.0, -pct(entry_price, opening_high))
        if opening_high is not None
        else None
    )

    recovery = (
        max(0.0, pct(entry_price, opening_low))
        if opening_low is not None
        else None
    )

    opening_move = (
        pct(entry_price, opening_price)
        if opening_price is not None
        else None
    )

    reversal_time = detect_reversal(
        opening_completed
    )

    lower_high_time = detect_lower_high(
        opening_completed
    )

    if reversal_time is None:
        reversal_state = "NO_CONFIRMED_REVERSAL"
    else:
        reversal_state = "REVERSAL_CONFIRMED"

    if lower_high_time is None:
        lower_high_state = "NO_CONFIRMED_LOWER_HIGH"
    else:
        lower_high_state = "LOWER_HIGH_CONFIRMED"

    minutes = int(
        (
            entry - datetime.combine(
                day, time(9, 30)
            )
        ).total_seconds() / 60
    )

    return {
        "entry": entry,
        "phase": opening_phase(minutes),
        "completed_bars": len(opening_completed),
        "opening_move": opening_move,
        "selloff": selloff,
        "selloff_class": selloff_class(selloff),
        "recovery": recovery,
        "recovery_class": recovery_class(recovery),
        "reversal_state": reversal_state,
        "reversal_time": reversal_time,
        "lower_high_state": lower_high_state,
        "lower_high_time": lower_high_time,
    }


def summarize(records, field, title):
    print()
    print(title)

    groups = defaultdict(list)

    for record in records:
        groups[record[field]].append(record)

    for label, group in sorted(groups.items()):
        winners = sum(
            r["net"] > 0
            for r in group
        )

        losers = sum(
            r["net"] < 0
            for r in group
        )

        net = sum(
            r["net"]
            for r in group
        )

        print(
            f"{label:36s} "
            f"N={len(group):2d} "
            f"W={winners:2d} "
            f"L={losers:2d} "
            f"NET={net:+.6f}%"
        )


def audit_line(record):
    return (
        f'{record["dataset"]:10s} '
        f'{record["entry"]} '
        f'NET={record["net"]:+.6f}% '
        f'PHASE={record["phase"]} '
        f'BARS={record["completed_bars"]} '
        f'OPEN_MOVE={fmt(record["opening_move"])} '
        f'SELLOFF={fmt(record["selloff"])} '
        f'RECOVERY={fmt(record["recovery"])} '
        f'REVERSAL={record["reversal_state"]} '
        f'REVERSAL_TIME={record["reversal_time"]} '
        f'LOWER_HIGH={record["lower_high_state"]} '
        f'LOWER_HIGH_TIME={record["lower_high_time"]}'
    )


def report(name, records, details=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "phase",
        "ENTRY SESSION PHASE",
    )

    summarize(
        records,
        "selloff_class",
        "OPENING SELLOFF BEFORE ENTRY",
    )

    summarize(
        records,
        "recovery_class",
        "RECOVERY FROM OPENING LOW",
    )

    summarize(
        records,
        "reversal_state",
        "COMPLETED 5M BEARISH REVERSAL",
    )

    summarize(
        records,
        "lower_high_state",
        "CONFIRMED 5M LOWER HIGH",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-44")
    print("OPENING REVERSAL AND SHORT ENTRY TIMING")
    print("READ-ONLY OBSERVATIONAL RESEARCH")

    combined = []

    for name, (
        path,
        expected_count,
        expected_net,
    ) in DATASETS.items():

        rows = load_rows(path)

        result = engine.run(
            rows=rows,
            **PARAMS,
        )

        assert (
            result["trade_count"]
            == expected_count
        ), f"{name}: trade count changed"

        assert abs(
            result["net_pnl_pct"]
            - expected_net
        ) < TOLERANCE, (
            f"{name}: baseline net changed"
        )

        sessions = group_sessions(
            regular_candles(rows)
        )

        records = []

        for trade in result["trades"]:
            entry = parse_time(
                trade["entry_time"]
            )

            record = analyze_entry(
                sessions,
                entry,
            )

            record["dataset"] = name
            record["net"] = float(
                trade["net_pnl_pct"]
            )

            records.append(record)

        assert len(records) == expected_count

        report(name, records)
        combined.extend(records)

    assert len(combined) == 36

    assert abs(
        sum(r["net"] for r in combined)
        - 8.984294
    ) < TOLERANCE

    report(
        "COMBINED — DESCRIPTIVE ONLY",
        combined,
        details=False,
    )

    print()
    print("PRIORITY CASES")

    for record in combined:
        if (
            str(record["entry"].date())
            in PRIORITY_DATES
        ):
            print(audit_line(record))

    print()
    print("LIMITATIONS:")
    print(
        "Opening patterns use only completed "
        "same-session 5m candles."
    )
    print(
        "Reversal and lower-high definitions "
        "are observational proxies."
    )
    print(
        "At 09:35 only one 5m candle is "
        "available; multi-candle confirmation "
        "is impossible."
    )
    print(
        "No filters approved. "
        "No file writes or V18 changes."
    )

    print("STEP 59F-5H-43K-44: PASS")


if __name__ == "__main__":
    main()
