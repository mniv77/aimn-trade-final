
#!/usr/bin/env python3
"""
AIMn STEP 59F-5H-43K-32
POST-TRANSITION PRICE BEHAVIOR

NVDA SHORT 5m — V18 baseline.

Classify completed 5m candles immediately before entry:
- DOWN_ACCELERATING
- DOWN_EXHAUSTING
- UP_RECOVERY
- FRESH_DOWN_LEG
- MIXED_OR_FLAT
- INSUFFICIENT

Additional measurements:
- Previous 3-candle and 6-candle close movement
- Last 3-candle movement vs preceding 3-candle movement
- Number of falling closes
- Position within recent completed 5m range

READ-ONLY RESEARCH.
NO FILE WRITES.
NO FUTURE DATA.
NO V18 MODIFICATIONS.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
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
    "2026-07-06",
    "2026-07-24",
    "2026-08-03",
    "2026-08-21",
    "2026-09-02",
}


def dt(value):
    return datetime.fromisoformat(str(value))


def pct(new, old):
    if old == 0:
        return None
    return (new / old - 1.0) * 100.0


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def load(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["candles"] if isinstance(data, dict) else data

    rows = sorted(
        rows,
        key=lambda r: dt(r["timestamp"]),
    )

    stamps = [
        dt(r["timestamp"])
        for r in rows
    ]

    assert len(stamps) == len(set(stamps)), (
        "Duplicate timestamps detected"
    )

    return rows


def classify_behavior(prior):
    """
    All input candles must be fully completed
    before the trade's entry timestamp.

    Require seven contiguous 5m candles
    for two non-overlapping 3-candle windows.

    Price change for a window is calculated
    from its starting close to its ending close.
    """

    result = {
        "behavior": "INSUFFICIENT",
        "move3": None,
        "move6": None,
        "previous3": None,
        "acceleration": None,
        "falling_closes": None,
        "range_position": None,
        "recent_peak_drop": None,
    }

    if len(prior) < 7:
        return result

    candles = prior[-7:]

    times = [
        dt(c["timestamp"])
        for c in candles
    ]

    for i in range(1, len(times)):
        if times[i] - times[i - 1] != timedelta(minutes=5):
            return result

    closes = [
        float(c["close"])
        for c in candles
    ]

    highs = [
        float(c["high"])
        for c in candles
    ]

    lows = [
        float(c["low"])
        for c in candles
    ]

    # Earlier three intervals:
    # closes[0] -> closes[3]
    previous3 = pct(closes[3], closes[0])

    # Latest three intervals:
    # closes[3] -> closes[6]
    move3 = pct(closes[6], closes[3])

    move6 = pct(closes[6], closes[0])

    # Negative acceleration means the latest
    # three intervals are more bearish.
    acceleration = move3 - previous3

    falling_closes = sum(
        closes[i] < closes[i - 1]
        for i in range(1, len(closes))
    )

    high = max(highs)
    low = min(lows)

    if high > low:
        range_position = (
            (closes[-1] - low) / (high - low)
        )
    else:
        range_position = 0.5

    recent_peak_drop = (
        (high - closes[-1]) / high * 100.0
    )

    # Classification thresholds are descriptive
    # research labels, not trading filters.
    threshold = 0.05

    if (
        previous3 > threshold
        and move3 < -threshold
    ):
        behavior = "FRESH_DOWN_LEG"

    elif (
        previous3 < -threshold
        and move3 < -threshold
        and move3 < previous3
    ):
        behavior = "DOWN_ACCELERATING"

    elif (
        previous3 < -threshold
        and move3 < 0
        and move3 >= previous3
    ):
        behavior = "DOWN_EXHAUSTING"

    elif (
        previous3 < -threshold
        and move3 > threshold
    ):
        behavior = "UP_RECOVERY"

    else:
        behavior = "MIXED_OR_FLAT"

    result.update({
        "behavior": behavior,
        "move3": move3,
        "move6": move6,
        "previous3": previous3,
        "acceleration": acceleration,
        "falling_closes": falling_closes,
        "range_position": range_position,
        "recent_peak_drop": recent_peak_drop,
    })

    return result


def classify_range(value):
    if value is None:
        return "UNKNOWN"

    if value < 0.25:
        return "LOWER_QUARTER"

    if value > 0.75:
        return "UPPER_QUARTER"

    return "MIDDLE_HALF"


def classify_drop(value):
    if value is None:
        return "UNKNOWN"

    if value < 0.25:
        return "UNDER_0_25"

    if value < 0.75:
        return "FROM_0_25_TO_0_75"

    return "AT_LEAST_0_75"


def summarize(records, key, title):
    print()
    print(title)

    groups = defaultdict(list)

    for row in records:
        groups[row[key]].append(row)

    for label, group in sorted(groups.items()):
        winners = sum(
            r["net"] > 0 for r in group
        )

        losers = sum(
            r["net"] < 0 for r in group
        )

        net = sum(
            r["net"] for r in group
        )

        print(
            f"{label:30s} "
            f"N={len(group):2d} "
            f"W={winners:2d} "
            f"L={losers:2d} "
            f"NET={net:+.6f}%"
        )


def report(name, records, detailed=True):
    print()
    print("=" * 105)
    print(name)
    print("=" * 105)

    summarize(
        records,
        "behavior",
        "PRE-ENTRY 5M PRICE BEHAVIOR",
    )

    summarize(
        records,
        "range_class",
        "POSITION IN RECENT 5M RANGE",
    )

    summarize(
        records,
        "drop_class",
        "DISTANCE BELOW RECENT 5M HIGH",
    )

    if detailed:
        print()
        print("TRADE AUDIT")

        for r in records:
            print(
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'BEHAVIOR={r["behavior"]} '
                f'PREVIOUS3={fmt(r["previous3"])} '
                f'MOVE3={fmt(r["move3"])} '
                f'MOVE6={fmt(r["move6"])} '
                f'ACCEL={fmt(r["acceleration"])} '
                f'FALLING={r["falling_closes"]} '
                f'RANGE={r["range_class"]} '
                f'PEAK_DROP={fmt(r["recent_peak_drop"])}'
            )


def main():
    print("AIMn — STEP 59F-5H-43K-32")
    print("POST-TRANSITION PRICE BEHAVIOR")
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

        index = {
            dt(r["timestamp"]): i
            for i, r in enumerate(rows)
        }

        records = []

        for trade in result["trades"]:
            entry = dt(trade["entry_time"])

            assert entry in index, (
                f"Entry timestamp missing: {entry}"
            )

            i = index[entry]

            # Exclude the entry candle entirely.
            # Its final OHLC was not known at entry.
            prior = rows[:i]

            metrics = classify_behavior(prior)

            record = {
                "dataset": name,
                "time": str(entry),
                "net": float(trade["net_pnl_pct"]),
                **metrics,
            }

            record["range_class"] = classify_range(
                record["range_position"]
            )

            record["drop_class"] = classify_drop(
                record["recent_peak_drop"]
            )

            records.append(record)

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
    print("PRIORITY CASES")

    for r in combined:
        if r["time"][:10] in PRIORITY:
            print(
                f'{r["dataset"]:10s} '
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'BEHAVIOR={r["behavior"]} '
                f'PREVIOUS3={fmt(r["previous3"])} '
                f'MOVE3={fmt(r["move3"])} '
                f'ACCEL={fmt(r["acceleration"])} '
                f'PEAK_DROP={fmt(r["recent_peak_drop"])}'
            )

    print()
    print("LIMITATIONS:")
    print(
        "Only completed 5m candles before entry used."
    )
    print(
        "Seven consecutive candles are required."
    )
    print(
        "Classification thresholds are descriptive."
    )
    print(
        "No future candles or trade outcomes used "
        "to classify entries."
    )
    print(
        "No V18 changes or entry filters."
    )

    print("STEP 59F-5H-43K-32: PASS")


if __name__ == "__main__":
    main()
