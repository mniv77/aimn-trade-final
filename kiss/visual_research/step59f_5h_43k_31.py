
#!/usr/bin/env python3
"""
AIMn STEP 59F-5H-43K-31
STRUCTURAL TRANSITION TIMING

NVDA SHORT 5m / confirmed 30m swing structure.

Measures:
- Age of latest confirmed lower high
- Age of latest confirmed swing-low break
- Price displacement since the break
- Time since the latest structural event

READ-ONLY OBSERVATIONAL RESEARCH.
NO FUTURE DATA.
NO V18 MODIFICATIONS.
NO FILE WRITES.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, time
from collections import defaultdict

LAB = Path("kiss/visual_research")
sys.path.insert(0, str(LAB.resolve()))

import step59f_5h43c_flat_long_replay as engine

PARAMS = dict(
    entry_cutoff="15:45",
    commission_pct=0.01,
    entry_slippage_pct=0.02,
    exit_slippage_pct=0.02,
    trailing_minus_pct=1.5,
    rsi_rescue_short=80.0,
    atr_exhaustion_filter=True,
    flat_long_filter=True,
)

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
    if old is None or old == 0:
        return None
    return 100.0 * (new / old - 1.0)


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def load(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["candles"] if isinstance(data, dict) else data
    rows = sorted(rows, key=lambda r: dt(r["timestamp"]))

    stamps = [dt(r["timestamp"]) for r in rows]
    assert len(stamps) == len(set(stamps)), (
        "Duplicate candle timestamps"
    )

    return rows


def build_30m(rows):
    """
    Build 30-minute candles from six consecutive 5m bars.

    A 30m bar is included only if all six 5m slots
    exist and belong to the same trading session.
    """

    groups = defaultdict(dict)

    for row in rows:
        stamp = dt(row["timestamp"])

        if not (
            time(9, 30) <= stamp.time() < time(16, 0)
        ):
            continue

        minutes = (
            (stamp.hour - 9) * 60
            + stamp.minute - 30
        )

        bucket = minutes // 30
        slot = (minutes % 30) // 5

        groups[(stamp.date(), bucket)][slot] = row

    bars = []

    for (day, bucket), slots in sorted(groups.items()):
        if set(slots) != set(range(6)):
            continue

        candles = [slots[i] for i in range(6)]

        start = dt(candles[0]["timestamp"])

        bars.append({
            "start": start,
            "end": start + timedelta(minutes=30),
            "open": float(candles[0]["open"]),
            "high": max(
                float(c["high"]) for c in candles
            ),
            "low": min(
                float(c["low"]) for c in candles
            ),
            "close": float(candles[-1]["close"]),
        })

    return bars


def confirmed_swings(bars):
    """
    A swing requires one preceding and one following
    completed 30m candle.

    Its confirmation time is the END of the
    following candle.
    """

    highs = []
    lows = []

    for i in range(1, len(bars) - 1):
        previous = bars[i - 1]
        center = bars[i]
        following = bars[i + 1]

        if (
            center["high"] > previous["high"]
            and center["high"] > following["high"]
        ):
            highs.append({
                "index": i,
                "price": center["high"],
                "confirmed_at": following["end"],
            })

        if (
            center["low"] < previous["low"]
            and center["low"] < following["low"]
        ):
            lows.append({
                "index": i,
                "price": center["low"],
                "confirmed_at": following["end"],
            })

    return highs, lows


def classify_age(age):
    if age is None:
        return "NO_EVENT"
    if age <= 2:
        return "FRESH_0_TO_2"
    if age <= 6:
        return "RECENT_3_TO_6"
    return "OLD_7_PLUS"


def classify_displacement(value):
    if value is None:
        return "NO_BREAK"
    if value < 0:
        return "ABOVE_BREAK_LEVEL"
    if value < 0.25:
        return "BELOW_0_25"
    if value < 0.75:
        return "FROM_0_25_TO_0_75"
    return "AT_LEAST_0_75"


def measure_structure(all_bars, entry):
    """
    Use completed 30m candles before entry.

    The latest 20 bars define the structural window.
    Swing events and breaks must be observable
    within this window.
    """

    prior = [
        b for b in all_bars
        if b["end"] <= entry
    ]

    window = prior[-20:]

    result = {
        "lh_age": None,
        "break_age": None,
        "break_distance": None,
        "lh_class": "NO_EVENT",
        "break_class": "NO_EVENT",
        "distance_class": "NO_BREAK",
        "last_lh": None,
        "last_break_level": None,
        "bars30": len(window),
    }

    if len(window) < 4:
        return result

    highs, lows = confirmed_swings(window)

    # Find the latest confirmed lower high.
    lower_high_events = []

    for i in range(1, len(highs)):
        previous = highs[i - 1]
        current = highs[i]

        if current["price"] < previous["price"]:
            lower_high_events.append(current)

    if lower_high_events:
        event = lower_high_events[-1]

        result["lh_age"] = (
            len(window) - 1 - event["index"]
        )

        result["last_lh"] = event["price"]

    # Find confirmed swing-low breakdowns.
    #
    # A break occurs when a completed 30m close
    # crosses below an already confirmed swing low.
    # Count the first crossing for each low.
    break_events = []

    for low in lows:
        level = low["price"]
        confirmed_at = low["confirmed_at"]

        for i in range(1, len(window)):
            bar = window[i]
            previous = window[i - 1]

            if bar["end"] <= confirmed_at:
                continue

            if (
                previous["close"] >= level
                and bar["close"] < level
            ):
                break_events.append({
                    "index": i,
                    "level": level,
                    "close": bar["close"],
                })
                break

    if break_events:
        event = max(
            break_events,
            key=lambda e: e["index"],
        )

        result["break_age"] = (
            len(window) - 1 - event["index"]
        )

        result["last_break_level"] = event["level"]

        current_close = window[-1]["close"]

        # Positive means current price is BELOW
        # the broken support level.
        result["break_distance"] = (
            100.0 * (
                event["level"] - current_close
            ) / event["level"]
        )

    result["lh_class"] = classify_age(
        result["lh_age"]
    )

    result["break_class"] = classify_age(
        result["break_age"]
    )

    result["distance_class"] = classify_displacement(
        result["break_distance"]
    )

    return result


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
            f"{label:32s} "
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
        "lh_class",
        "LATEST LOWER HIGH — AGE IN 30M BARS",
    )

    summarize(
        records,
        "break_class",
        "LATEST CONFIRMED SWING-LOW BREAK — AGE",
    )

    summarize(
        records,
        "distance_class",
        "DISTANCE BELOW LATEST BREAK LEVEL",
    )

    if detailed:
        print()
        print("TRADE AUDIT")

        for r in records:
            print(
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'LH_AGE={r["lh_age"]} '
                f'BREAK_AGE={r["break_age"]} '
                f'BREAK_DISTANCE={fmt(r["break_distance"])} '
                f'LH={r["lh_class"]} '
                f'BREAK={r["break_class"]} '
                f'DISTANCE={r["distance_class"]}'
            )


def main():
    print("AIMn — STEP 59F-5H-43K-31")
    print("STRUCTURAL TRANSITION TIMING")
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
        ), f"{name}: trade count changed"

        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < 0.000002, (
            f"{name}: baseline net changed"
        )

        bars30 = build_30m(rows)

        index = {
            dt(r["timestamp"]): i
            for i, r in enumerate(rows)
        }

        records = []

        for trade in result["trades"]:
            entry = dt(trade["entry_time"])
            assert entry in index, (
                f"Missing entry candle: {entry}"
            )

            metrics = measure_structure(
                bars30,
                entry,
            )

            records.append({
                "dataset": name,
                "time": str(entry),
                "net": float(
                    trade["net_pnl_pct"]
                ),
                **metrics,
            })

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
                f'LH_AGE={r["lh_age"]} '
                f'BREAK_AGE={r["break_age"]} '
                f'BREAK_DISTANCE={fmt(r["break_distance"])}'
            )

    print()
    print("LIMITATIONS:")
    print(
        "Only completed 30m bars before entry used."
    )
    print(
        "Lower highs require subsequent swing confirmation."
    )
    print(
        "Break requires a completed 30m close below "
        "a previously confirmed swing low."
    )
    print(
        "Ages count completed 30m bars, not calendar time."
    )
    print(
        "The rolling 20-bar window can span sessions."
    )
    print(
        "No entry filters or V18 changes."
    )

    print("STEP 59F-5H-43K-31: PASS")


if __name__ == "__main__":
    main()
