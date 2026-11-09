
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-43
OVERNIGHT GAP AND OPENING SHORT ENTRY AUDIT

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Research questions:
1. Was the overnight gap upward or downward?
2. Was the previous session ending upward or downward?
3. How far had price moved after today's open?
4. Did the SHORT entry follow a decline or rebound?
5. What distinguishes July 24, July 28, and Aug 3?

Only completed historical candles and the entry
candle OPEN are used.

No future candles.
No changes to trades.
No file writes.
No V18 changes.
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
        f"Duplicate timestamps in {path}"
    )

    return rows


def regular_candles(rows):
    candles = []

    for row in rows:
        stamp = parse_time(row["timestamp"])

        if not time(9, 30) <= stamp.time() < time(16, 0):
            continue

        candles.append({
            "time": stamp,
            "end": stamp + timedelta(minutes=5),
            "date": stamp.date(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })

    return candles


def group_sessions(candles):
    sessions = defaultdict(list)

    for candle in candles:
        sessions[candle["date"]].append(candle)

    for day in sessions:
        sessions[day].sort(
            key=lambda c: c["time"]
        )

    return sessions


def gap_class(gap):
    if gap is None:
        return "NO_GAP_REFERENCE"

    if gap <= -0.50:
        return "GAP_DOWN_LARGE"

    if gap <= -0.10:
        return "GAP_DOWN_SMALL"

    if gap < 0.10:
        return "GAP_FLAT"

    if gap < 0.50:
        return "GAP_UP_SMALL"

    return "GAP_UP_LARGE"


def opening_class(move):
    if move is None:
        return "NO_OPENING_REFERENCE"

    if move <= -0.50:
        return "OPENING_DOWN_LARGE"

    if move <= -0.10:
        return "OPENING_DOWN_SMALL"

    if move < 0.10:
        return "OPENING_FLAT"

    if move < 0.50:
        return "OPENING_UP_SMALL"

    return "OPENING_UP_LARGE"


def previous_close_direction(move):
    if move is None:
        return "NO_PREVIOUS_SESSION"

    if move <= -0.20:
        return "PREVIOUS_CLOSE_DOWN"

    if move >= 0.20:
        return "PREVIOUS_CLOSE_UP"

    return "PREVIOUS_CLOSE_FLAT"


def entry_phase(minutes):
    if minutes < 30:
        return "OPEN_FIRST_30M"

    if minutes < 60:
        return "OPEN_30_TO_60M"

    return "AFTER_FIRST_HOUR"


def analyze_entry(
    sessions,
    entry,
):
    day = entry.date()

    current = sessions.get(day, [])

    if not current:
        raise ValueError(
            f"Missing entry session: {entry}"
        )

    entry_candle = next(
        (
            c for c in current
            if c["time"] == entry
        ),
        None,
    )

    if entry_candle is None:
        raise ValueError(
            f"Missing entry candle: {entry}"
        )

    # Use only a valid regular-session opening
    # candle beginning at 09:30.
    opening_candle = next(
        (
            c for c in current
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

    previous_dates = sorted(
        d for d in sessions
        if d < day
    )

    previous = (
        sessions[previous_dates[-1]]
        if previous_dates
        else []
    )

    # Previous-session close must be a
    # completed 15:55 regular-session candle.
    previous_final = next(
        (
            c for c in previous
            if c["time"].time() == time(15, 55)
        ),
        None,
    )

    previous_close = (
        previous_final["close"]
        if previous_final is not None
        else None
    )

    # Previous-session final 30 minutes:
    # six completed candles, 15:30–16:00.
    last_six = [
        c for c in previous
        if time(15, 30)
        <= c["time"].time()
        <= time(15, 55)
    ]

    valid_final_30m = (
        len(last_six) == 6
        and all(
            last_six[i + 1]["time"]
            - last_six[i]["time"]
            == timedelta(minutes=5)
            for i in range(5)
        )
    )

    previous_final_move = (
        pct(
            last_six[-1]["close"],
            last_six[0]["open"],
        )
        if valid_final_30m
        else None
    )

    gap = (
        pct(opening_price, previous_close)
        if (
            opening_price is not None
            and previous_close is not None
        )
        else None
    )

    opening_move = (
        pct(entry_price, opening_price)
        if opening_price is not None
        else None
    )

    # Only candles completed before entry.
    completed_today = [
        c for c in current
        if c["end"] <= entry
    ]

    # Highest/lowest observed since today's
    # regular-session open, before entry.
    # The entry candle's high/low are excluded.
    prior_high = (
        max(c["high"] for c in completed_today)
        if completed_today
        else None
    )

    prior_low = (
        min(c["low"] for c in completed_today)
        if completed_today
        else None
    )

    distance_from_high = (
        max(0.0, -pct(entry_price, prior_high))
        if prior_high is not None
        else None
    )

    rebound_from_low = (
        max(0.0, pct(entry_price, prior_low))
        if prior_low is not None
        else None
    )

    minutes = int(
        (entry - datetime.combine(
            day, time(9, 30)
        )).total_seconds() / 60
    )

    return {
        "entry": entry,
        "minutes": minutes,
        "phase": entry_phase(minutes),
        "previous_final_move": previous_final_move,
        "previous_direction": previous_close_direction(
            previous_final_move
        ),
        "gap": gap,
        "gap_class": gap_class(gap),
        "opening_move": opening_move,
        "opening_class": opening_class(
            opening_move
        ),
        "distance_from_high": distance_from_high,
        "rebound_from_low": rebound_from_low,
        "completed_bars": len(completed_today),
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
        f'PREV30={fmt(record["previous_final_move"])} '
        f'GAP={fmt(record["gap"])} '
        f'OPEN_MOVE={fmt(record["opening_move"])} '
        f'DOWN_FROM_HIGH={fmt(record["distance_from_high"])} '
        f'REBOUND_FROM_LOW={fmt(record["rebound_from_low"])} '
        f'BARS={record["completed_bars"]} '
        f'GAP_CLASS={record["gap_class"]} '
        f'OPEN_CLASS={record["opening_class"]}'
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
        "gap_class",
        "OVERNIGHT GAP CLASSIFICATION",
    )

    summarize(
        records,
        "previous_direction",
        "PREVIOUS SESSION FINAL 30M",
    )

    summarize(
        records,
        "opening_class",
        "OPENING MOVEMENT TO ENTRY",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-43")
    print("OVERNIGHT GAP AND OPENING SHORT ENTRY AUDIT")
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

        candles = regular_candles(rows)
        sessions = group_sessions(candles)

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
        "Regular-session candles only; "
        "no premarket or after-hours prices."
    )
    print(
        "Opening gap is measured from the "
        "previous regular-session close."
    )
    print(
        "Only completed pre-entry candles "
        "and entry candle open are used."
    )
    print(
        "Opening classifications are "
        "descriptive, not approved filters."
    )
    print(
        "No file writes. "
        "No production or V18 changes."
    )

    print("STEP 59F-5H-43K-43: PASS")


if __name__ == "__main__":
    main()
