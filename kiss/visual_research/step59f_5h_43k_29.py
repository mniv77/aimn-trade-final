
#!/usr/bin/env python3
"""
AIMn STEP 59F-5H-43K-29
MAJOR 30M STRUCTURE VS LOCAL 5M PEAK

READ-ONLY RESEARCH.
NO STRATEGY CHANGES.
NO FILE WRITES.
NO FUTURE CANDLES.
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
    "2026-07-06",
    "2026-07-24",
    "2026-08-03",
    "2026-08-21",
    "2026-09-02",
}


def dt(value):
    return datetime.fromisoformat(str(value))


def pct(a, b):
    if b == 0:
        return None
    return (a / b - 1.0) * 100.0


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def load(path):
    obj = json.loads(path.read_text(encoding="utf-8"))

    rows = (
        obj["candles"]
        if isinstance(obj, dict)
        else obj
    )

    rows = sorted(
        rows,
        key=lambda r: dt(r["timestamp"]),
    )

    timestamps = [
        dt(r["timestamp"])
        for r in rows
    ]

    assert len(timestamps) == len(set(timestamps)), (
        "Duplicate candle timestamps"
    )

    return rows


def build_30m(rows):
    """
    Build complete 30-minute bars.

    Each bar requires six consecutive 5m candles.
    Sessions start at 09:30.
    Incomplete 30m bars are excluded.
    No grouping across session boundaries.
    """

    groups = defaultdict(dict)

    for row in rows:
        stamp = dt(row["timestamp"])

        if not (
            time(9, 30) <= stamp.time()
            < time(16, 0)
        ):
            continue

        minute = (
            (stamp.hour - 9) * 60
            + stamp.minute - 30
        )

        bucket = minute // 30
        slot = minute % 30 // 5

        groups[
            (stamp.date(), bucket)
        ][slot] = row

    bars = []

    for (day, bucket), slots in sorted(groups.items()):
        if set(slots) != set(range(6)):
            continue

        candles = [
            slots[i]
            for i in range(6)
        ]

        start = dt(candles[0]["timestamp"])
        end = start + timedelta(minutes=30)

        bars.append({
            "start": start,
            "end": end,
            "open": float(candles[0]["open"]),
            "high": max(
                float(c["high"])
                for c in candles
            ),
            "low": min(
                float(c["low"])
                for c in candles
            ),
            "close": float(candles[-1]["close"]),
        })

    return bars


def structure_30m(bars, entry):
    """
    Evaluate completed 30m bars only.

    Use the latest six completed bars to describe
    larger structure.

    Three completed bars are required for
    directional classification.

    This is a structural proxy, not proof of
    a major reversal.
    """

    prior = [
        b for b in bars
        if b["end"] <= entry
    ]

    if len(prior) < 3:
        return {
            "structure": "INSUFFICIENT_30M",
            "location": "UNKNOWN",
            "move": None,
            "high_distance": None,
            "low_distance": None,
            "bars30": len(prior),
        }

    window = prior[-6:]
    recent = prior[-3:]

    highs = [b["high"] for b in window]
    lows = [b["low"] for b in window]

    highest = max(highs)
    lowest = min(lows)
    current = window[-1]["close"]

    position = (
        (current - lowest) / (highest - lowest)
        if highest > lowest
        else None
    )

    if position is None:
        location = "UNKNOWN"
    elif position <= 0.25:
        location = "LOWER_QUARTER"
    elif position >= 0.75:
        location = "UPPER_QUARTER"
    else:
        location = "MIDDLE_HALF"

    c0, c1, c2 = [
        b["close"]
        for b in recent
    ]

    if c0 > c1 > c2:
        structure = "30M_FALLING"

    elif c0 < c1 < c2:
        structure = "30M_RISING"

    elif c0 < c1 and c2 < c1:
        structure = "30M_UP_TO_DOWN"

    elif c0 > c1 and c2 > c1:
        structure = "30M_DOWN_TO_UP"

    else:
        structure = "30M_MIXED"

    return {
        "structure": structure,
        "location": location,
        "move": pct(
            current,
            window[0]["open"],
        ),
        "high_distance": pct(
            current,
            highest,
        ),
        "low_distance": pct(
            current,
            lowest,
        ),
        "bars30": len(prior),
    }


def local_5m(rows, entry):
    """
    Evaluate completed same-day 5m candles.

    A local peak must have a subsequent completed
    lower close before it is recognized.
    """

    prior = [
        r for r in rows
        if (
            dt(r["timestamp"]).date()
            == entry.date()
            and dt(r["timestamp"])
            + timedelta(minutes=5) <= entry
        )
    ]

    closes = [
        float(r["close"])
        for r in prior
    ]

    if len(closes) < 3:
        return {
            "local": "NO_LOCAL_PEAK",
            "decline": None,
            "peak_age": None,
        }

    peaks = [
        j
        for j in range(1, len(closes) - 1)
        if (
            closes[j] > closes[j - 1]
            and closes[j] > closes[j + 1]
        )
    ]

    if not peaks:
        return {
            "local": "NO_LOCAL_PEAK",
            "decline": None,
            "peak_age": None,
        }

    j = peaks[-1]

    decline = pct(
        closes[j],
        closes[-1],
    )

    age = len(closes) - 1 - j

    if decline >= 1.0:
        label = "LOCAL_EXTENDED_DOWN"

    elif decline >= 0.5:
        label = "LOCAL_MODERATE_DOWN"

    elif decline > 0:
        label = "LOCAL_EARLY_DOWN"

    else:
        label = "LOCAL_RECOVERING"

    return {
        "local": label,
        "decline": decline,
        "peak_age": age,
    }


def relationship(local, structure):
    if local == "NO_LOCAL_PEAK":
        return "LOCAL_UNKNOWN"

    if structure == "INSUFFICIENT_30M":
        return "30M_UNKNOWN"

    if structure in (
        "30M_FALLING",
        "30M_UP_TO_DOWN",
    ):
        return "SHORT_WITH_30M_DOWN"

    if structure in (
        "30M_RISING",
        "30M_DOWN_TO_UP",
    ):
        return "SHORT_AGAINST_30M_UP"

    return "MIXED_STRUCTURE"


def summarize(records, key, heading):
    print()
    print(heading)

    groups = defaultdict(list)

    for r in records:
        groups[r[key]].append(r)

    for name, items in sorted(groups.items()):
        winners = sum(
            r["net"] > 0
            for r in items
        )

        losers = sum(
            r["net"] < 0
            for r in items
        )

        net = sum(
            r["net"]
            for r in items
        )

        print(
            f"{name:36s} "
            f"N={len(items):2d} "
            f"W={winners:2d} "
            f"L={losers:2d} "
            f"NET={net:+.6f}%"
        )


def report(name, records, details=True):
    print()
    print("=" * 105)
    print(name)
    print("=" * 105)

    summarize(
        records,
        "structure",
        "30M STRUCTURE",
    )

    summarize(
        records,
        "location",
        "30M RANGE LOCATION",
    )

    summarize(
        records,
        "relationship",
        "LOCAL 5M VS 30M STRUCTURE",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for r in records:
            print(
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'30M={r["structure"]} '
                f'LOC={r["location"]} '
                f'5M={r["local"]} '
                f'MOVE30={fmt(r["move"])} '
                f'FROM_HIGH={fmt(r["high_distance"])} '
                f'ABOVE_LOW={fmt(r["low_distance"])} '
                f'LOCAL_DROP={fmt(r["decline"])} '
                f'AGE={r["peak_age"]}'
            )


def main():
    print("AIMn — STEP 59F-5H-43K-29")
    print("MAJOR STRUCTURE VS LOCAL PEAK")
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
            result["trade_count"]
            == expected_count
        ), f"{name}: trade count changed"

        assert abs(
            result["net_pnl_pct"]
            - expected_net
        ) < 0.000002, (
            f"{name}: baseline net changed"
        )

        bars30 = build_30m(rows)

        index = {
            dt(row["timestamp"]): i
            for i, row in enumerate(rows)
        }

        records = []

        for trade in result["trades"]:
            entry = dt(
                trade["entry_time"]
            )

            i = index[entry]

            # Only rows before the entry candle.
            prior5 = rows[:i]

            major = structure_30m(
                bars30,
                entry,
            )

            local = local_5m(
                prior5,
                entry,
            )

            relation = relationship(
                local["local"],
                major["structure"],
            )

            record = {
                "dataset": name,
                "time": str(entry),
                "net": float(
                    trade["net_pnl_pct"]
                ),
                "relationship": relation,
                **major,
                **local,
            }

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
        details=False,
    )

    print()
    print("PRIORITY CASES")

    for r in combined:
        if r["time"][:10] in PRIORITY:
            print(
                f'{r["dataset"]:10s} '
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'30M={r["structure"]} '
                f'LOC={r["location"]} '
                f'5M={r["local"]} '
                f'FROM_HIGH={fmt(r["high_distance"])} '
                f'ABOVE_LOW={fmt(r["low_distance"])} '
                f'LOCAL_DROP={fmt(r["decline"])}'
            )

    print()
    print("LIMITATIONS:")
    print(
        "30m structure uses completed bars only."
    )
    print(
        "30m directional pattern is not proof "
        "of a major reversal."
    )
    print(
        "The 30m window may include prior sessions."
    )
    print(
        "Incomplete 30m bars are excluded."
    )
    print(
        "5m local peaks use completed candles only."
    )
    print(
        "No future candles or entry candle "
        "used for classification."
    )
    print(
        "No new filters, no file writes, "
        "no V18 changes."
    )

    print(
        "STEP 59F-5H-43K-29: PASS"
    )


if __name__ == "__main__":
    main()
