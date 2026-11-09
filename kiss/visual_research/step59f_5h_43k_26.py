
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-26
Local Recovery Versus Major Trend Structure

READ-ONLY observational audit.
Uses the independent V18 baseline without modifying it.

Examines:
- Recent 5m recovery and pullback
- Completed 30m directional structure
- Agreement or disagreement between 5m and 30m
- Four priority research dates

No filters, no tuning, no file writes.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

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
    "2026-07-06",
    "2026-07-24",
    "2026-08-03",
    "2026-08-21",
}


def timestamp(value):
    return datetime.fromisoformat(str(value))


def change_pct(new, old):
    if old == 0:
        raise ValueError("Zero reference price")
    return (new / old - 1.0) * 100.0


def load_rows(path):
    data = json.loads(path.read_text(encoding="utf-8"))

    rows = (
        data["candles"]
        if isinstance(data, dict)
        else data
    )

    rows = sorted(
        rows,
        key=lambda r: timestamp(r["timestamp"]),
    )

    times = [timestamp(r["timestamp"]) for r in rows]
    assert len(times) == len(set(times)), "Duplicate timestamps"

    return rows


def completed_30m_bars(rows, entry):
    """
    Build 30m bars from exactly six consecutive 5m
    candles, aligned to regular US market sessions.

    Only bars completed at or before entry are used.
    Missing or incomplete blocks are discarded.
    """
    groups = defaultdict(list)

    for row in rows:
        t = timestamp(row["timestamp"])

        if t + timedelta(minutes=5) > entry:
            break

        minutes = t.hour * 60 + t.minute
        market_open = 9 * 60 + 30
        market_close = 16 * 60

        if not (market_open <= minutes < market_close):
            continue

        slot = (minutes - market_open) // 30
        key = (t.date(), slot)
        groups[key].append(row)

    bars = []

    for (day, slot), group in sorted(groups.items()):
        if len(group) != 6:
            continue

        start = datetime.combine(
            day,
            datetime.min.time(),
        ) + timedelta(
            minutes=9 * 60 + 30 + slot * 30
        )

        expected = [
            start + timedelta(minutes=5 * j)
            for j in range(6)
        ]

        actual = [
            timestamp(r["timestamp"])
            for r in group
        ]

        if actual != expected:
            continue

        bars.append({
            "start": start,
            "end": start + timedelta(minutes=30),
            "open": float(group[0]["open"]),
            "high": max(float(r["high"]) for r in group),
            "low": min(float(r["low"]) for r in group),
            "close": float(group[-1]["close"]),
        })

    return bars


def trend_30m(bars):
    """
    A descriptive three-bar trend, not a confirmed
    major LONG/SHORT reversal.
    """
    if len(bars) < 3:
        return "INSUFFICIENT_30M", None, None

    a, b, c = bars[-3:]

    first = change_pct(b["close"], a["close"])
    second = change_pct(c["close"], b["close"])

    if first > 0 and second > 0:
        label = "UP_CONTINUATION"
    elif first < 0 and second < 0:
        label = "DOWN_CONTINUATION"
    elif first > 0 and second < 0:
        label = "UP_TO_DOWN"
    elif first < 0 and second > 0:
        label = "DOWN_TO_UP"
    else:
        label = "FLAT_OR_MIXED"

    return label, first, second


def recent_5m_structure(prior):
    """
    Recent price movement using completed candles.

    The last five 5m bars provide a local window.
    No future candle is inspected.
    """
    if len(prior) < 5:
        return {
            "shape": "INSUFFICIENT_5M",
            "move": None,
            "recovery": None,
            "pullback": None,
        }

    window = prior[-5:]

    closes = [float(r["close"]) for r in window]
    highs = [float(r["high"]) for r in window]
    lows = [float(r["low"]) for r in window]

    move = change_pct(closes[-1], closes[0])

    local_high = max(highs)
    local_low = min(lows)

    recovery = change_pct(local_high, local_low)
    pullback = change_pct(local_high, closes[-1])

    if move < 0:
        shape = "LOCAL_DOWN"
    elif move > 0:
        shape = "LOCAL_UP"
    else:
        shape = "LOCAL_FLAT"

    return {
        "shape": shape,
        "move": move,
        "recovery": recovery,
        "pullback": pullback,
    }


def combined_structure(local, major):
    if local == "INSUFFICIENT_5M":
        return "LOCAL_UNKNOWN"

    if major == "INSUFFICIENT_30M":
        return "MAJOR_UNKNOWN"

    if local == "LOCAL_DOWN":
        if major in (
            "DOWN_CONTINUATION",
            "UP_TO_DOWN",
        ):
            return "DOWN_WITH_30M_SUPPORT"

        if major in (
            "UP_CONTINUATION",
            "DOWN_TO_UP",
        ):
            return "LOCAL_DOWN_AGAINST_30M_UP"

    if local == "LOCAL_UP":
        if major in (
            "UP_CONTINUATION",
            "DOWN_TO_UP",
        ):
            return "UP_WITH_30M_SUPPORT"

        if major in (
            "DOWN_CONTINUATION",
            "UP_TO_DOWN",
        ):
            return "LOCAL_UP_AGAINST_30M_DOWN"

    return "MIXED_STRUCTURE"


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def summarize(title, records, key):
    print("\n" + title)

    labels = sorted({r[key] for r in records})

    for label in labels:
        group = [r for r in records if r[key] == label]

        wins = sum(r["net"] > 0 for r in group)
        losses = sum(r["net"] < 0 for r in group)
        net = sum(r["net"] for r in group)

        print(
            f"{label:36s} "
            f"N={len(group):2d} "
            f"W={wins:2d} "
            f"L={losses:2d} "
            f"NET={net:+.6f}%"
        )


def report(name, records):
    print("\n" + "=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        "COMPLETED 30M STRUCTURE",
        records,
        "major",
    )

    summarize(
        "RECENT 5M STRUCTURE",
        records,
        "local",
    )

    summarize(
        "5M / 30M RELATIONSHIP",
        records,
        "relationship",
    )

    print("\nTRADE-BY-TRADE AUDIT")

    for r in records:
        print(
            f'{r["time"]} '
            f'NET={r["net"]:+.6f}% '
            f'30M={r["major"]} '
            f'5M={r["local"]} '
            f'REL={r["relationship"]} '
            f'5M_MOVE={fmt(r["move"])} '
            f'5M_RANGE={fmt(r["recovery"])} '
            f'5M_PULLBACK={fmt(r["pullback"])} '
            f'30M_STEP1={fmt(r["step1"])} '
            f'30M_STEP2={fmt(r["step2"])} '
            f'30M_BARS={r["bar_count"]}'
        )


def main():
    print("AIMn — STEP 59F-5H-43K-26")
    print("LOCAL RECOVERY VS MAJOR TREND STRUCTURE")
    print("READ-ONLY OBSERVATIONAL AUDIT")

    all_records = []
    by_dataset = {}

    for name, (path, expected_count, expected_net) in (
        DATASETS.items()
    ):
        rows = load_rows(path)
        result = engine.run(rows=rows, **PARAMS)

        assert result["trade_count"] == expected_count
        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < 0.000002

        time_index = {
            timestamp(row["timestamp"]): i
            for i, row in enumerate(rows)
        }

        records = []

        for trade in result["trades"]:
            entry = timestamp(trade["entry_time"])
            i = time_index[entry]

            prior = [
                row
                for row in rows[:i]
                if timestamp(row["timestamp"]).date()
                    == entry.date()
                and timestamp(row["timestamp"])
                    + timedelta(minutes=5) <= entry
            ]

            bars30 = completed_30m_bars(
                rows[:i],
                entry,
            )

            major, step1, step2 = trend_30m(bars30)
            local_data = recent_5m_structure(prior)

            local = local_data["shape"]

            relationship = combined_structure(
                local,
                major,
            )

            records.append({
                "dataset": name,
                "time": str(entry),
                "net": float(trade["net_pnl_pct"]),
                "major": major,
                "local": local,
                "relationship": relationship,
                "move": local_data["move"],
                "recovery": local_data["recovery"],
                "pullback": local_data["pullback"],
                "step1": step1,
                "step2": step2,
                "bar_count": len(bars30),
            })

        assert len(records) == expected_count

        report(name, records)
        by_dataset[name] = records
        all_records.extend(records)

    assert len(all_records) == 36
    assert abs(
        sum(r["net"] for r in all_records) - 8.984294
    ) < 0.000002

    report("COMBINED — DESCRIPTIVE ONLY", all_records)

    print("\n" + "=" * 108)
    print("PRIORITY CASES")
    print("=" * 108)

    for r in all_records:
        if r["time"][:10] in PRIORITY_DATES:
            print(
                f'{r["dataset"]:10s} '
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'30M={r["major"]} '
                f'5M={r["local"]} '
                f'REL={r["relationship"]} '
                f'5M_MOVE={fmt(r["move"])} '
                f'PULLBACK={fmt(r["pullback"])}'
            )

    print("\nIMPORTANT LIMITATIONS:")
    print("30M classification uses three completed bars.")
    print("This does not prove a major trend transition.")
    print("30M context may cross previous sessions.")
    print("5M range measures price excursion, not event order.")
    print("All classification uses pre-entry candles only.")
    print("No new filters or thresholds approved.")
    print("No files created or modified.")
    print("V18 unchanged.")
    print("STEP 59F-5H-43K-26: PASS")


if __name__ == "__main__":
    main()
