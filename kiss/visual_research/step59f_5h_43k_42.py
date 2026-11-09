
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-42
DOWNWARD MOMENTUM:
ACCELERATING VS EXHAUSTING

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Measures at each existing SHORT entry:
- Last 3 completed 5m close-to-close returns
- Earlier 3-bar vs latest 3-bar momentum
- Downward acceleration or deceleration
- Recent bearish candle count
- Recent lower-low count
- Distance from recent low
- Short-term trajectory classification

No lookahead.
No file writes.
No production changes.
No V18 modifications.
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
    if not old_value:
        return None
    return (
        new_value / old_value - 1.0
    ) * 100.0


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

    stamps = [
        parse_time(r["timestamp"])
        for r in rows
    ]

    assert len(stamps) == len(set(stamps)), (
        f"Duplicate timestamps: {path}"
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
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })

    return candles


def momentum_class(
    earlier,
    latest,
    delta,
):
    if (
        earlier is None
        or latest is None
        or delta is None
    ):
        return "INSUFFICIENT_DATA"

    # All thresholds are descriptive research
    # categories, not approved trading rules.

    if latest >= 0.10:
        return "UPWARD_REVERSAL"

    if latest > -0.10:
        return "DOWNWARD_STALL"

    if delta <= -0.15:
        return "DOWNWARD_ACCELERATING"

    if delta >= 0.15:
        return "DOWNWARD_DECELERATING"

    return "DOWNWARD_STEADY"


def low_structure_class(
    lower_lows,
    bearish_count,
):
    if lower_lows >= 3 and bearish_count >= 4:
        return "STRONG_BEARISH_STRUCTURE"

    if lower_lows >= 2 and bearish_count >= 3:
        return "MODERATE_BEARISH_STRUCTURE"

    if lower_lows <= 1 and bearish_count <= 2:
        return "WEAK_BEARISH_STRUCTURE"

    return "MIXED_STRUCTURE"


def analyze_entry(candles, entry):
    completed = [
        c for c in candles
        if c["end"] <= entry
    ]

    entry_candle = next(
        (
            c for c in candles
            if c["time"] == entry
        ),
        None,
    )

    if entry_candle is None:
        raise ValueError(
            f"Missing entry candle: {entry}"
        )

    # Use only six immediately preceding,
    # completed and contiguous 5m candles.
    # Do not bridge overnight gaps.

    window = completed[-6:]

    contiguous = (
        len(window) == 6
        and all(
            window[i + 1]["time"]
            - window[i]["time"]
            == timedelta(minutes=5)
            for i in range(5)
        )
        and window[-1]["end"] == entry
    )

    if not contiguous:
        return {
            "entry": entry,
            "earlier": None,
            "latest": None,
            "delta": None,
            "lower_lows": None,
            "bearish_count": None,
            "distance_low": None,
            "momentum": "INSUFFICIENT_DATA",
            "structure": "INSUFFICIENT_DATA",
        }

    # Two non-overlapping three-candle periods.
    # Each period includes its three complete
    # candles, using first open to last close.
    first = window[:3]
    second = window[3:]

    earlier = pct(
        first[-1]["close"],
        first[0]["open"],
    )

    latest = pct(
        second[-1]["close"],
        second[0]["open"],
    )

    delta = latest - earlier

    bearish_count = sum(
        c["close"] < c["open"]
        for c in window
    )

    lower_lows = sum(
        window[i]["low"]
        < window[i - 1]["low"]
        for i in range(1, 6)
    )

    recent_low = min(
        c["low"] for c in window
    )

    distance_low = max(
        0.0,
        pct(
            entry_candle["open"],
            recent_low,
        ),
    )

    return {
        "entry": entry,
        "earlier": earlier,
        "latest": latest,
        "delta": delta,
        "lower_lows": lower_lows,
        "bearish_count": bearish_count,
        "distance_low": distance_low,
        "momentum": momentum_class(
            earlier,
            latest,
            delta,
        ),
        "structure": low_structure_class(
            lower_lows,
            bearish_count,
        ),
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
        f'EARLIER={fmt(record["earlier"])} '
        f'LATEST={fmt(record["latest"])} '
        f'DELTA={fmt(record["delta"])} '
        f'LOWER_LOWS={record["lower_lows"]} '
        f'BEARISH={record["bearish_count"]} '
        f'DIST_LOW={fmt(record["distance_low"])} '
        f'MOMENTUM={record["momentum"]} '
        f'STRUCTURE={record["structure"]}'
    )


def report(name, records, details=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "momentum",
        "DOWNWARD MOMENTUM CLASSIFICATION",
    )

    summarize(
        records,
        "structure",
        "RECENT 5M PRICE STRUCTURE",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-42")
    print("DOWNWARD MOMENTUM")
    print("ACCELERATING VS EXHAUSTING")
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
        records = []

        for trade in result["trades"]:
            entry = parse_time(
                trade["entry_time"]
            )

            record = analyze_entry(
                candles,
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
        "Momentum uses six contiguous "
        "completed 5m candles only."
    )
    print(
        "Opening entries without six "
        "same-session candles are "
        "classified INSUFFICIENT_DATA."
    )
    print(
        "Momentum differences are "
        "descriptive, not proof "
        "of exhaustion."
    )
    print(
        "Entry location uses entry "
        "candle open, not simulated fill."
    )
    print(
        "No new filters approved. "
        "No file writes or V18 changes."
    )

    print("STEP 59F-5H-43K-42: PASS")


if __name__ == "__main__":
    main()
