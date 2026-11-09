
#!/usr/bin/env python3
"""
AIMn STEP 59F-5H-43K-34
OPENING TRANSITION TIMING AUDIT

NVDA SHORT 5m / unchanged V18 baseline.

Research questions:
1. Did price already fall substantially before entry?
2. Was price recovering upward at entry?
3. How many completed bearish candles preceded entry?
4. Was entry close to the opening-session low?
5. How does the actual entry price differ from
   the entry candle opening price?
6. Can opening winners and losers be distinguished
   using only information available at entry?

READ-ONLY.
NO FILE WRITES.
NO FUTURE CANDLE INFORMATION.
NO V18 CHANGES.
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

PRIORITY = {
    "2026-07-24",
    "2026-08-03",
    "2026-08-21",
    "2026-09-02",
}


def dt(value):
    return datetime.fromisoformat(str(value))


def pct(new, old):
    if old is None or old == 0:
        return None
    return (new / old - 1.0) * 100.0


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def load(path):
    obj = json.loads(path.read_text(encoding="utf-8"))
    rows = obj["candles"] if isinstance(obj, dict) else obj

    rows = sorted(rows, key=lambda r: dt(r["timestamp"]))

    stamps = [dt(r["timestamp"]) for r in rows]

    assert len(stamps) == len(set(stamps)), (
        "Duplicate candle timestamps"
    )

    return rows


def regular_sessions(rows):
    sessions = defaultdict(list)

    for row in rows:
        stamp = dt(row["timestamp"])

        if time(9, 30) <= stamp.time() < time(16, 0):
            sessions[stamp.date()].append(row)

    return dict(sessions)


def candle_direction(row):
    op = float(row["open"])
    cl = float(row["close"])

    if cl < op:
        return "DOWN"

    if cl > op:
        return "UP"

    return "FLAT"


def classify_decline(value):
    if value is None:
        return "UNKNOWN"

    if value >= 1.0:
        return "DECLINE_1_PLUS"

    if value >= 0.5:
        return "DECLINE_0_5_TO_1"

    if value >= 0.2:
        return "DECLINE_0_2_TO_0_5"

    return "SMALL_OR_NONE"


def classify_recovery(value):
    if value is None:
        return "UNKNOWN"

    if value >= 0.5:
        return "RECOVERY_0_5_PLUS"

    if value >= 0.2:
        return "RECOVERY_0_2_TO_0_5"

    return "RECOVERY_UNDER_0_2"


def classify_opening_pattern(directions):
    """
    Describe the last two completed candle bodies.

    Do not inspect the entry candle's future close.
    """

    if not directions:
        return "NO_COMPLETED_CANDLES"

    if len(directions) == 1:
        return "ONE_" + directions[-1]

    last_two = directions[-2:]

    if last_two == ["DOWN", "DOWN"]:
        return "DOWN_DOWN"

    if last_two == ["DOWN", "UP"]:
        return "DOWN_UP"

    if last_two == ["UP", "DOWN"]:
        return "UP_DOWN"

    if last_two == ["UP", "UP"]:
        return "UP_UP"

    return "MIXED_FLAT"


def measure(sessions, trade):
    entry = dt(trade["entry_time"])
    day = entry.date()

    today = sessions.get(day, [])

    entry_row = next(
        (
            r for r in today
            if dt(r["timestamp"]) == entry
        ),
        None,
    )

    assert entry_row is not None, (
        f"Entry candle missing: {entry}"
    )

    opening_row = next(
        (
            r for r in today
            if dt(r["timestamp"]).time() == time(9, 30)
        ),
        None,
    )

    assert opening_row is not None, (
        f"Opening candle missing: {day}"
    )

    opening_price = float(opening_row["open"])
    entry_candle_open = float(entry_row["open"])
    actual_entry = float(trade["entry_price"])

    completed = [
        r for r in today
        if (
            dt(r["timestamp"]) + timedelta(minutes=5)
            <= entry
        )
    ]

    # The entry candle's open is known at entry.
    # Its high, low and close are deliberately
    # excluded from every feature.

    directions = [
        candle_direction(r)
        for r in completed
    ]

    bearish_count = directions.count("DOWN")
    bullish_count = directions.count("UP")

    trailing_down = 0

    for direction in reversed(directions):
        if direction != "DOWN":
            break
        trailing_down += 1

    trailing_up = 0

    for direction in reversed(directions):
        if direction != "UP":
            break
        trailing_up += 1

    high = (
        max(float(r["high"]) for r in completed)
        if completed else None
    )

    low = (
        min(float(r["low"]) for r in completed)
        if completed else None
    )

    # Include today's known opening price as
    # an observation even for the 09:30 entry.
    known_high = max(
        opening_price,
        high if high is not None else opening_price,
        entry_candle_open,
    )

    known_low = min(
        opening_price,
        low if low is not None else opening_price,
        entry_candle_open,
    )

    decline_from_high = (
        (known_high - entry_candle_open)
        / known_high * 100.0
    )

    recovery_from_low = pct(
        entry_candle_open,
        known_low,
    )

    move_from_open = pct(
        entry_candle_open,
        opening_price,
    )

    execution_difference = pct(
        actual_entry,
        entry_candle_open,
    )

    # Maximum observed opening decline using
    # only fully completed candles and the
    # current entry candle's known open.
    max_opening_decline = (
        (opening_price - known_low)
        / opening_price * 100.0
    )

    # Candle body of the first 09:30 candle
    # is only known after 09:35.
    first_body = None

    if completed:
        first = completed[0]

        if (
            dt(first["timestamp"]).time()
            == time(9, 30)
        ):
            first_body = pct(
                float(first["close"]),
                float(first["open"]),
            )

    # Last completed candle close relative
    # to its open.
    last_body = None

    if completed:
        last = completed[-1]

        last_body = pct(
            float(last["close"]),
            float(last["open"]),
        )

    return {
        "entry": entry,
        "net": float(trade["net_pnl_pct"]),
        "entry_price": actual_entry,
        "entry_candle_open": entry_candle_open,
        "execution_difference": execution_difference,
        "opening_price": opening_price,
        "first_body": first_body,
        "last_body": last_body,
        "completed_count": len(completed),
        "bearish_count": bearish_count,
        "bullish_count": bullish_count,
        "trailing_down": trailing_down,
        "trailing_up": trailing_up,
        "pattern": classify_opening_pattern(directions),
        "move_from_open": move_from_open,
        "decline_from_high": decline_from_high,
        "recovery_from_low": recovery_from_low,
        "max_opening_decline": max_opening_decline,
        "decline_class": classify_decline(
            decline_from_high
        ),
        "recovery_class": classify_recovery(
            recovery_from_low
        ),
    }


def entry_period(entry):
    minutes = (
        (entry.hour - 9) * 60
        + entry.minute - 30
    )

    if minutes < 30:
        return "OPENING_30_MIN"

    if minutes < 60:
        return "OPENING_30_TO_60"

    return "AFTER_FIRST_HOUR"


def summarize(records, key, title):
    print()
    print(title)

    groups = defaultdict(list)

    for r in records:
        groups[r[key]].append(r)

    for label, group in sorted(groups.items()):
        winners = sum(r["net"] > 0 for r in group)
        losers = sum(r["net"] < 0 for r in group)
        net = sum(r["net"] for r in group)

        print(
            f"{label:32s} "
            f"N={len(group):2d} "
            f"W={winners:2d} "
            f"L={losers:2d} "
            f"NET={net:+.6f}%"
        )


def audit_line(r):
    return (
        f'{r["dataset"]:10s} '
        f'{r["entry"]} '
        f'NET={r["net"]:+.6f}% '
        f'PERIOD={r["period"]} '
        f'PATTERN={r["pattern"]} '
        f'FIRST_BODY={fmt(r["first_body"])} '
        f'LAST_BODY={fmt(r["last_body"])} '
        f'OPEN_MOVE={fmt(r["move_from_open"])} '
        f'DECLINE={fmt(r["decline_from_high"])} '
        f'RECOVERY={fmt(r["recovery_from_low"])} '
        f'MAX_OPEN_DECLINE={fmt(r["max_opening_decline"])} '
        f'DOWN_STREAK={r["trailing_down"]} '
        f'UP_STREAK={r["trailing_up"]} '
        f'ENTRY_OPEN_DIFF={fmt(r["execution_difference"])} '
        f'COMPLETED={r["completed_count"]}'
    )


def report(name, records, detailed=True):
    print()
    print("=" * 110)
    print(name)
    print("=" * 110)

    summarize(
        records,
        "period",
        "ENTRY PERIOD",
    )

    summarize(
        records,
        "pattern",
        "LAST TWO COMPLETED CANDLE DIRECTIONS",
    )

    summarize(
        records,
        "decline_class",
        "DECLINE FROM KNOWN SESSION HIGH",
    )

    summarize(
        records,
        "recovery_class",
        "RECOVERY FROM KNOWN SESSION LOW",
    )

    if detailed:
        print()
        print("TRADE AUDIT")

        for r in records:
            print(audit_line(r))


def main():
    print("AIMn — STEP 59F-5H-43K-34")
    print("OPENING TRANSITION TIMING AUDIT")
    print("READ-ONLY OBSERVATIONAL RESEARCH")

    combined = []

    for name, (
        path,
        expected_count,
        expected_net,
    ) in DATASETS.items():

        rows = load(path)

        result = engine.run(
            rows=rows,
            **PARAMS,
        )

        assert (
            result["trade_count"] == expected_count
        ), f"{name}: baseline trade count changed"

        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < 0.000002, (
            f"{name}: baseline net changed"
        )

        sessions = regular_sessions(rows)

        records = []

        for trade in result["trades"]:
            r = measure(sessions, trade)
            r["dataset"] = name
            r["period"] = entry_period(r["entry"])
            records.append(r)

        assert len(records) == expected_count

        report(name, records)
        combined.extend(records)

    assert len(combined) == 36

    assert abs(
        sum(r["net"] for r in combined)
        - 8.984294
    ) < 0.000002

    report(
        "COMBINED — DESCRIPTIVE ONLY",
        combined,
        detailed=False,
    )

    print()
    print("OPENING-HOUR TRADE AUDIT")

    opening = [
        r for r in combined
        if r["period"] != "AFTER_FIRST_HOUR"
    ]

    for r in opening:
        print(audit_line(r))

    print()
    print("PRIORITY CASES")

    for r in combined:
        if str(r["entry"].date()) in PRIORITY:
            print(audit_line(r))

    print()
    print("LIMITATIONS:")
    print(
        "Only completed 5m candles and the known "
        "entry candle OPEN are used."
    )
    print(
        "Entry candle high, low, and close are excluded."
    )
    print(
        "Execution difference is descriptive, "
        "not an entry timing signal."
    )
    print(
        "Opening extremes are measured only "
        "through entry time."
    )
    print(
        "No trading filters or V18 modifications."
    )

    print("STEP 59F-5H-43K-34: PASS")


if __name__ == "__main__":
    main()
