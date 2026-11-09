
#!/usr/bin/env python3
"""
AIMn STEP 59F-5H-43K-30
MAJOR SWING STRUCTURE RECOGNITION

NVDA SHORT 5m / completed 30m swing highs and lows.

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
    if not b:
        return None
    return (a / b - 1.0) * 100.0


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


def build_30m(rows):
    """
    Six consecutive 5m candles form a completed 30m bar.
    Sessions are aligned to 09:30 market time.
    No incomplete bars or session-crossing groups.
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
        end = start + timedelta(minutes=30)

        bars.append({
            "start": start,
            "end": end,
            "open": float(candles[0]["open"]),
            "high": max(float(c["high"]) for c in candles),
            "low": min(float(c["low"]) for c in candles),
            "close": float(candles[-1]["close"]),
        })

    return bars


def confirmed_swings(bars):
    """
    A 30m swing at index i requires:
      - one bar before it
      - one bar after it

    The swing becomes known only when the following
    30m bar is complete.

    High: center high strictly exceeds both neighbors.
    Low: center low strictly below both neighbors.
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
                "time": center["end"],
                "confirmed_at": following["end"],
                "price": center["high"],
            })

        if (
            center["low"] < previous["low"]
            and center["low"] < following["low"]
        ):
            lows.append({
                "time": center["end"],
                "confirmed_at": following["end"],
                "price": center["low"],
            })

    return highs, lows


def swing_structure(bars, entry):
    """
    Use at most 20 completed 30m bars before entry.
    Require two confirmed swing highs and two
    confirmed swing lows for structural classification.
    """

    prior = [b for b in bars if b["end"] <= entry]
    window = prior[-20:]

    highs, lows = confirmed_swings(window)

    result = {
        "structure": "INSUFFICIENT_SWINGS",
        "high_pattern": "UNKNOWN",
        "low_pattern": "UNKNOWN",
        "last_high": None,
        "last_low": None,
        "from_high": None,
        "above_low": None,
        "bars30": len(window),
        "swing_high_count": len(highs),
        "swing_low_count": len(lows),
    }

    if highs:
        result["last_high"] = highs[-1]["price"]

    if lows:
        result["last_low"] = lows[-1]["price"]

    if not window:
        return result

    current = window[-1]["close"]

    if result["last_high"] is not None:
        result["from_high"] = pct(
            current,
            result["last_high"],
        )

    if result["last_low"] is not None:
        result["above_low"] = pct(
            current,
            result["last_low"],
        )

    if len(highs) < 2 or len(lows) < 2:
        return result

    h0 = highs[-2]["price"]
    h1 = highs[-1]["price"]

    l0 = lows[-2]["price"]
    l1 = lows[-1]["price"]

    if h1 > h0:
        high_pattern = "HH"
    elif h1 < h0:
        high_pattern = "LH"
    else:
        high_pattern = "EH"

    if l1 > l0:
        low_pattern = "HL"
    elif l1 < l0:
        low_pattern = "LL"
    else:
        low_pattern = "EL"

    if high_pattern == "HH" and low_pattern == "HL":
        structure = "BULLISH_HH_HL"

    elif high_pattern == "LH" and low_pattern == "LL":
        structure = "BEARISH_LH_LL"

    elif high_pattern == "LH" and low_pattern == "HL":
        structure = "CONTRACTING"

    elif high_pattern == "HH" and low_pattern == "LL":
        structure = "EXPANDING"

    else:
        structure = "MIXED_TRANSITION"

    result.update({
        "structure": structure,
        "high_pattern": high_pattern,
        "low_pattern": low_pattern,
    })

    return result


def local_5m(rows, entry):
    """
    Latest confirmed local 5m close peak.
    Uses completed same-day bars only.
    """

    prior = [
        r for r in rows
        if (
            dt(r["timestamp"]).date() == entry.date()
            and dt(r["timestamp"]) + timedelta(minutes=5)
            <= entry
        )
    ]

    closes = [float(r["close"]) for r in prior]

    peaks = [
        j for j in range(1, len(closes) - 1)
        if (
            closes[j] > closes[j - 1]
            and closes[j] > closes[j + 1]
        )
    ]

    if not peaks:
        return {
            "local_drop": None,
            "local_age": None,
            "local_class": "NO_LOCAL_PEAK",
        }

    j = peaks[-1]
    decline = pct(closes[j], closes[-1])
    age = len(closes) - 1 - j

    if decline >= 1.0:
        label = "EXTENDED_LOCAL_DROP"
    elif decline >= 0.5:
        label = "MODERATE_LOCAL_DROP"
    elif decline > 0:
        label = "EARLY_LOCAL_DROP"
    else:
        label = "LOCAL_RECOVERY"

    return {
        "local_drop": decline,
        "local_age": age,
        "local_class": label,
    }


def summarize(records, key, title):
    print()
    print(title)

    groups = defaultdict(list)

    for r in records:
        groups[r[key]].append(r)

    for label, items in sorted(groups.items()):
        wins = sum(r["net"] > 0 for r in items)
        losses = sum(r["net"] < 0 for r in items)
        net = sum(r["net"] for r in items)

        print(
            f"{label:34s} "
            f"N={len(items):2d} "
            f"W={wins:2d} "
            f"L={losses:2d} "
            f"NET={net:+.6f}%"
        )


def report(name, records, detailed=True):
    print()
    print("=" * 105)
    print(name)
    print("=" * 105)

    summarize(
        records,
        "structure",
        "30M MAJOR SWING STRUCTURE",
    )

    summarize(
        records,
        "high_pattern",
        "SWING HIGH PATTERN",
    )

    summarize(
        records,
        "low_pattern",
        "SWING LOW PATTERN",
    )

    summarize(
        records,
        "local_class",
        "LOCAL 5M PEAK CLASS",
    )

    if detailed:
        print()
        print("TRADE AUDIT")

        for r in records:
            print(
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'STRUCTURE={r["structure"]} '
                f'HIGH={r["high_pattern"]} '
                f'LOW={r["low_pattern"]} '
                f'SWINGS={r["swing_high_count"]}/'
                f'{r["swing_low_count"]} '
                f'FROM_HIGH={fmt(r["from_high"])} '
                f'ABOVE_LOW={fmt(r["above_low"])} '
                f'LOCAL={r["local_class"]} '
                f'LOCAL_DROP={fmt(r["local_drop"])}'
            )


def main():
    print("AIMn — STEP 59F-5H-43K-30")
    print("MAJOR SWING STRUCTURE RECOGNITION")
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

        assert result["trade_count"] == expected_count, (
            f"{name}: baseline trade count changed"
        )

        assert abs(
            result["net_pnl_pct"] - expected_net
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
            entry = dt(trade["entry_time"])
            i = index[entry]

            # Only pre-entry 5m candles.
            prior5 = rows[:i]

            major = swing_structure(
                bars30,
                entry,
            )

            local = local_5m(
                prior5,
                entry,
            )

            record = {
                "dataset": name,
                "time": str(entry),
                "net": float(trade["net_pnl_pct"]),
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
                f'STRUCTURE={r["structure"]} '
                f'HIGH={r["high_pattern"]} '
                f'LOW={r["low_pattern"]} '
                f'FROM_HIGH={fmt(r["from_high"])} '
                f'ABOVE_LOW={fmt(r["above_low"])} '
                f'LOCAL_DROP={fmt(r["local_drop"])}'
            )

    print()
    print("LIMITATIONS:")
    print("Swing confirmation requires a following completed 30m bar.")
    print("Only confirmed swings available before entry are used.")
    print("The 20-bar window can span previous sessions.")
    print("A swing pattern is not proof of a major reversal.")
    print("Incomplete 30m bars are excluded.")
    print("No filters, no file writes, no V18 changes.")

    print("STEP 59F-5H-43K-30: PASS")


if __name__ == "__main__":
    main()
