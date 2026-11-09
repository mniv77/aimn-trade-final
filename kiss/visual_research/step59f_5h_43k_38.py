
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-38
DOWNWARD LEG ORIGIN AND EXHAUSTION AUDIT

NVDA SHORT 5m — READ-ONLY RESEARCH

Study the current downward price leg before each
SHORT entry, using completed 5m candles only.

No file writes.
No entry or exit modifications.
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

EPS = 1e-10


def parse_time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def pct(new, old):
    if old is None or abs(old) < EPS:
        return None
    return (new / old - 1.0) * 100.0


def fmt(value):
    return "NA" if value is None else f"{value:+.4f}%"


def load_rows(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["candles"] if isinstance(data, dict) else data

    rows = sorted(
        rows,
        key=lambda r: parse_time(r["timestamp"]),
    )

    stamps = [parse_time(r["timestamp"]) for r in rows]

    assert len(stamps) == len(set(stamps)), (
        f"Duplicate timestamps: {path}"
    )

    return rows


def regular_candles(rows):
    candles = []

    for r in rows:
        stamp = parse_time(r["timestamp"])

        if not time(9, 30) <= stamp.time() < time(16, 0):
            continue

        candles.append({
            "time": stamp,
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
        })

    return candles


def completed_before_entry(candles, entry):
    return [
        c for c in candles
        if c["time"] + timedelta(minutes=5) <= entry
    ]


def local_peaks(candles):
    """
    A peak at i is confirmed only when candle i+1
    has fully completed.
    """
    peaks = []

    for i in range(1, len(candles) - 1):
        left = candles[i - 1]
        middle = candles[i]
        right = candles[i + 1]

        if (
            middle["high"] > left["high"]
            and middle["high"] > right["high"]
        ):
            peaks.append({
                "index": i,
                "price": middle["high"],
                "time": middle["time"],
                "confirmed_time": (
                    right["time"] + timedelta(minutes=5)
                ),
            })

    return peaks


def current_leg(candles, entry):
    completed = completed_before_entry(candles, entry)

    if not completed:
        return None

    peaks = local_peaks(completed)

    if not peaks:
        return {
            "peak_time": None,
            "peak_price": None,
            "peak_age": None,
            "leg_decline": None,
            "leg_low": None,
            "recovery": None,
            "leg_range": None,
            "first_half": None,
            "second_half": None,
            "speed_change": None,
            "new_low_recent": None,
        }

    peak = peaks[-1]
    origin_index = peak["index"]

    segment = completed[origin_index + 1:]

    if not segment:
        return None

    last_close = completed[-1]["close"]
    leg_low = min(c["low"] for c in segment)

    leg_decline = -pct(last_close, peak["price"])
    full_decline = -pct(leg_low, peak["price"])

    recovery = pct(last_close, leg_low)

    # Completed 5m candle count since peak candle.
    peak_age = len(completed) - 1 - origin_index

    half = max(1, len(segment) // 2)

    first_segment = segment[:half]
    second_segment = segment[half:]

    first_half = -pct(
        first_segment[-1]["close"],
        peak["price"],
    )

    second_half = (
        -pct(
            second_segment[-1]["close"],
            first_segment[-1]["close"],
        )
        if second_segment else None
    )

    first_speed = (
        first_half / len(first_segment)
        if first_half is not None else None
    )

    second_speed = (
        second_half / len(second_segment)
        if (
            second_half is not None
            and second_segment
        )
        else None
    )

    speed_change = (
        second_speed - first_speed
        if (
            first_speed is not None
            and second_speed is not None
        )
        else None
    )

    recent = segment[-3:]

    new_low_recent = any(
        abs(c["low"] - leg_low) < EPS
        for c in recent
    )

    return {
        "peak_time": peak["time"],
        "peak_price": peak["price"],
        "peak_age": peak_age,
        "leg_decline": leg_decline,
        "leg_low": leg_low,
        "recovery": recovery,
        "leg_range": full_decline,
        "first_half": first_half,
        "second_half": second_half,
        "speed_change": speed_change,
        "new_low_recent": new_low_recent,
    }


def decline_class(value):
    if value is None:
        return "NO_PEAK"

    if value < 0:
        return "ABOVE_PEAK"

    if value < 0.20:
        return "DECLINE_UNDER_0_2"

    if value < 0.50:
        return "DECLINE_0_2_TO_0_5"

    if value < 1.00:
        return "DECLINE_0_5_TO_1"

    return "DECLINE_1_PLUS"


def age_class(value):
    if value is None:
        return "NO_PEAK"

    if value <= 2:
        return "FRESH_1_TO_2"

    if value <= 5:
        return "RECENT_3_TO_5"

    return "MATURE_6_PLUS"


def recovery_class(value):
    if value is None:
        return "NO_PEAK"

    if value < 0.10:
        return "RECOVERY_UNDER_0_1"

    if value < 0.30:
        return "RECOVERY_0_1_TO_0_3"

    return "RECOVERY_0_3_PLUS"


def speed_class(value):
    if value is None:
        return "INSUFFICIENT_CANDLES"

    if value > 0.05:
        return "DECLINE_ACCELERATING"

    if value < -0.05:
        return "DECLINE_SLOWING"

    return "DECLINE_STEADY"


def measure(candles, trade):
    entry = parse_time(trade["entry_time"])

    leg = current_leg(candles, entry)

    assert leg is not None, (
        f"No completed candle before entry: {entry}"
    )

    return {
        "entry": entry,
        "net": float(trade["net_pnl_pct"]),
        **leg,
        "decline_class": decline_class(
            leg["leg_decline"]
        ),
        "age_class": age_class(
            leg["peak_age"]
        ),
        "recovery_class": recovery_class(
            leg["recovery"]
        ),
        "speed_class": speed_class(
            leg["speed_change"]
        ),
        "recent_low_class": (
            "RECENT_NEW_LOW"
            if leg["new_low_recent"] is True
            else (
                "NO_RECENT_NEW_LOW"
                if leg["new_low_recent"] is False
                else "NO_PEAK"
            )
        ),
    }


def summarize(records, key, title):
    print()
    print(title)

    groups = defaultdict(list)

    for r in records:
        groups[r[key]].append(r)

    for label, group in sorted(groups.items()):
        wins = sum(r["net"] > 0 for r in group)
        losses = sum(r["net"] < 0 for r in group)
        net = sum(r["net"] for r in group)

        print(
            f"{str(label):34s} "
            f"N={len(group):2d} "
            f"W={wins:2d} "
            f"L={losses:2d} "
            f"NET={net:+.6f}%"
        )


def audit_line(r):
    return (
        f'{r["dataset"]:10s} '
        f'{r["entry"]} '
        f'NET={r["net"]:+.6f}% '
        f'PEAK={r["peak_time"]} '
        f'AGE={r["peak_age"]} '
        f'DECLINE={fmt(r["leg_decline"])} '
        f'FULL_RANGE={fmt(r["leg_range"])} '
        f'RECOVERY={fmt(r["recovery"])} '
        f'FIRST_HALF={fmt(r["first_half"])} '
        f'SECOND_HALF={fmt(r["second_half"])} '
        f'SPEED_CHANGE={fmt(r["speed_change"])} '
        f'NEW_LOW={r["new_low_recent"]} '
        f'CLASS={r["decline_class"]} '
        f'SPEED={r["speed_class"]}'
    )


def report(name, records, detailed=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "decline_class",
        "DECLINE FROM LATEST CONFIRMED 5M PEAK",
    )

    summarize(
        records,
        "age_class",
        "AGE OF CURRENT DOWNWARD LEG",
    )

    summarize(
        records,
        "recovery_class",
        "RECOVERY FROM CURRENT LEG LOW",
    )

    summarize(
        records,
        "speed_class",
        "DECLINE ACCELERATION VS SLOWDOWN",
    )

    summarize(
        records,
        "recent_low_class",
        "NEW LOW IN LAST THREE COMPLETED CANDLES",
    )

    if detailed:
        print()
        print("TRADE AUDIT")

        for r in records:
            print(audit_line(r))


def main():
    print("AIMn — STEP 59F-5H-43K-38")
    print("DOWNWARD LEG ORIGIN AND EXHAUSTION AUDIT")
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

        assert result["trade_count"] == expected_count, (
            f"{name}: baseline trade count changed"
        )

        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < 0.000002, (
            f"{name}: baseline net changed"
        )

        candles = regular_candles(rows)
        records = []

        for trade in result["trades"]:
            r = measure(candles, trade)
            r["dataset"] = name
            records.append(r)

        assert len(records) == expected_count

        report(name, records)
        combined.extend(records)

    assert len(combined) == 36

    assert abs(
        sum(r["net"] for r in combined) - 8.984294
    ) < 0.000002

    report(
        "COMBINED — DESCRIPTIVE ONLY",
        combined,
        detailed=False,
    )

    print()
    print("PRIORITY CASES")

    for r in combined:
        if str(r["entry"].date()) in PRIORITY_DATES:
            print(audit_line(r))

    print()
    print("LIMITATIONS:")
    print(
        "Local peaks require one fully completed "
        "right-hand 5m candle."
    )
    print(
        "Current entry candle is excluded."
    )
    print(
        "Latest confirmed peak is not necessarily "
        "the major 30m swing high."
    )
    print(
        "Decline speed is descriptive and is "
        "not an entry filter."
    )
    print(
        "No file writes, no production changes, "
        "no V18 modifications."
    )

    print("STEP 59F-5H-43K-38: PASS")


if __name__ == "__main__":
    main()
