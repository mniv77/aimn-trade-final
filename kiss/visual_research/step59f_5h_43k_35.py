
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-35
MAJOR TRANSITION VS LOCAL CANDLE MOVEMENT

NVDA SHORT 5m — READ-ONLY RESEARCH

Compare each existing V18 SHORT entry with:
- Confirmed 30m swing-high and swing-low structure
- Age of the latest confirmed 30m bearish support break
- Distance from the broken support at entry
- Recovery from the latest confirmed 30m swing low
- Latest completed 5m candle direction and body
- Agreement or disagreement between 5m and 30m

No new entries, no exits, no filters, no file writes.
All measurements use information available at entry.
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
    "2026-08-03",
    "2026-08-21",
    "2026-09-02",
}


def parse_time(value):
    return datetime.fromisoformat(str(value))


def percentage(new, old):
    if old is None or old == 0:
        return None
    return (new / old - 1.0) * 100.0


def format_pct(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def format_number(value):
    if value is None:
        return "NA"
    return f"{value:.4f}"


def load_candles(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["candles"] if isinstance(data, dict) else data

    rows = sorted(
        rows,
        key=lambda r: parse_time(r["timestamp"]),
    )

    timestamps = [
        parse_time(r["timestamp"]) for r in rows
    ]

    assert len(timestamps) == len(set(timestamps)), (
        "Duplicate candle timestamps"
    )

    return rows


def regular_5m(rows):
    output = []

    for row in rows:
        stamp = parse_time(row["timestamp"])

        if time(9, 30) <= stamp.time() < time(16, 0):
            output.append({
                "time": stamp,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })

    return output


def build_completed_30m(candles, entry):
    """
    Build 30m bars from six contiguous 5m bars.

    A bar is available only after its final 5m
    candle has completed.

    Never use the entry candle's future values.
    """
    groups = defaultdict(list)

    for candle in candles:
        stamp = candle["time"]

        if stamp + timedelta(minutes=5) > entry:
            continue

        bucket_minute = (
            (stamp.minute // 30) * 30
        )

        bucket = stamp.replace(
            minute=bucket_minute,
            second=0,
            microsecond=0,
        )

        groups[bucket].append(candle)

    bars = []

    for start in sorted(groups):
        group = sorted(
            groups[start],
            key=lambda c: c["time"],
        )

        if len(group) != 6:
            continue

        expected = [
            start + timedelta(minutes=5 * i)
            for i in range(6)
        ]

        if [c["time"] for c in group] != expected:
            continue

        if start + timedelta(minutes=30) > entry:
            continue

        bars.append({
            "start": start,
            "end": start + timedelta(minutes=30),
            "open": group[0]["open"],
            "high": max(c["high"] for c in group),
            "low": min(c["low"] for c in group),
            "close": group[-1]["close"],
        })

    return bars


def confirmed_swings(bars):
    """
    A swing at index i is confirmed only after
    the next completed 30m bar is available.

    This is a one-left, one-right confirmation.
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
                "center": center["start"],
                "confirmed": following["end"],
                "price": center["high"],
            })

        if (
            center["low"] < previous["low"]
            and center["low"] < following["low"]
        ):
            lows.append({
                "index": i,
                "center": center["start"],
                "confirmed": following["end"],
                "price": center["low"],
            })

    return highs, lows


def structural_state(highs, lows):
    if len(highs) < 2 or len(lows) < 2:
        return "INSUFFICIENT_STRUCTURE"

    last_high = highs[-1]["price"]
    previous_high = highs[-2]["price"]

    last_low = lows[-1]["price"]
    previous_low = lows[-2]["price"]

    if (
        last_high < previous_high
        and last_low < previous_low
    ):
        return "BEARISH_LH_LL"

    if (
        last_high > previous_high
        and last_low > previous_low
    ):
        return "BULLISH_HH_HL"

    if (
        last_high < previous_high
        and last_low > previous_low
    ):
        return "CONTRACTING"

    if (
        last_high > previous_high
        and last_low < previous_low
    ):
        return "EXPANDING"

    return "EQUAL_OR_MIXED"


def bearish_break_events(bars, lows):
    """
    Identify completed 30m bars that close
    below a previously confirmed swing low.

    Count the first crossing below a support
    level, not every subsequent bar below it.
    """
    events = []

    for i, bar in enumerate(bars):
        available = [
            low for low in lows
            if low["confirmed"] <= bar["start"]
        ]

        if not available or i == 0:
            continue

        support = available[-1]
        level = support["price"]

        previous_close = bars[i - 1]["close"]
        current_close = bar["close"]

        if previous_close >= level and current_close < level:
            events.append({
                "index": i,
                "time": bar["end"],
                "support": level,
                "close": current_close,
            })

    return events


def classify_break_age(age):
    if age is None:
        return "NO_CONFIRMED_BREAK"

    if age <= 2:
        return "FRESH_0_TO_2_BARS"

    if age <= 6:
        return "RECENT_3_TO_6_BARS"

    return "OLD_7_PLUS_BARS"


def classify_break_distance(distance):
    if distance is None:
        return "NO_CONFIRMED_BREAK"

    if distance < 0:
        return "ABOVE_BROKEN_SUPPORT"

    if distance < 0.5:
        return "BELOW_SUPPORT_UNDER_0_5"

    if distance < 1.0:
        return "BELOW_SUPPORT_0_5_TO_1"

    return "BELOW_SUPPORT_1_PLUS"


def classify_recovery(recovery):
    if recovery is None:
        return "NO_CONFIRMED_SWING_LOW"

    if recovery < 0.2:
        return "RECOVERY_UNDER_0_2"

    if recovery < 0.5:
        return "RECOVERY_0_2_TO_0_5"

    return "RECOVERY_0_5_PLUS"


def local_5m_state(candles, entry):
    completed = [
        c for c in candles
        if c["time"] + timedelta(minutes=5) <= entry
        and c["time"].date() == entry.date()
    ]

    if not completed:
        return {
            "direction": "NO_COMPLETED_5M",
            "body_pct": None,
            "streak": 0,
        }

    last = completed[-1]

    if last["close"] < last["open"]:
        direction = "DOWN"
    elif last["close"] > last["open"]:
        direction = "UP"
    else:
        direction = "FLAT"

    streak = 0

    for candle in reversed(completed):
        if direction == "DOWN":
            matches = candle["close"] < candle["open"]
        elif direction == "UP":
            matches = candle["close"] > candle["open"]
        else:
            matches = candle["close"] == candle["open"]

        if not matches:
            break

        streak += 1

    return {
        "direction": direction,
        "body_pct": percentage(
            last["close"],
            last["open"],
        ),
        "streak": streak,
    }


def classify_alignment(structure, local_direction):
    if structure == "BEARISH_LH_LL":
        if local_direction == "DOWN":
            return "BEARISH_WITH_DOWN_5M"
        if local_direction == "UP":
            return "BEARISH_WITH_UP_5M"
        return "BEARISH_WITH_FLAT_5M"

    if structure == "BULLISH_HH_HL":
        if local_direction == "DOWN":
            return "BULLISH_WITH_DOWN_5M"
        if local_direction == "UP":
            return "BULLISH_WITH_UP_5M"
        return "BULLISH_WITH_FLAT_5M"

    return "OTHER_STRUCTURE"


def measure(candles, trade):
    entry = parse_time(trade["entry_time"])

    entry_candle = next(
        (
            c for c in candles
            if c["time"] == entry
        ),
        None,
    )

    assert entry_candle is not None, (
        f"Missing entry candle: {entry}"
    )

    entry_open = entry_candle["open"]

    completed_30m = build_completed_30m(
        candles,
        entry,
    )

    highs, lows = confirmed_swings(completed_30m)

    structure = structural_state(highs, lows)

    events = bearish_break_events(
        completed_30m,
        lows,
    )

    last_break = events[-1] if events else None

    if last_break:
        age = (
            len(completed_30m) - 1
            - last_break["index"]
        )

        distance = (
            (last_break["support"] - entry_open)
            / last_break["support"] * 100.0
        )
    else:
        age = None
        distance = None

    last_low = lows[-1] if lows else None

    recovery = (
        percentage(
            entry_open,
            last_low["price"],
        )
        if last_low else None
    )

    local = local_5m_state(candles, entry)

    return {
        "entry": entry,
        "net": float(trade["net_pnl_pct"]),
        "entry_open": entry_open,
        "structure": structure,
        "completed_30m": len(completed_30m),
        "last_break_time": (
            last_break["time"] if last_break else None
        ),
        "break_age": age,
        "break_distance": distance,
        "break_age_class": classify_break_age(age),
        "break_distance_class": (
            classify_break_distance(distance)
        ),
        "swing_recovery": recovery,
        "swing_recovery_class": (
            classify_recovery(recovery)
        ),
        "local_direction": local["direction"],
        "local_body": local["body_pct"],
        "local_streak": local["streak"],
        "alignment": classify_alignment(
            structure,
            local["direction"],
        ),
    }


def summarize(records, key, title):
    print()
    print(title)

    groups = defaultdict(list)

    for record in records:
        groups[record[key]].append(record)

    for label, group in sorted(groups.items()):
        winners = sum(r["net"] > 0 for r in group)
        losers = sum(r["net"] < 0 for r in group)
        net = sum(r["net"] for r in group)

        print(
            f"{label:34s} "
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
        f'30M={r["structure"]} '
        f'5M={r["local_direction"]} '
        f'BODY={format_pct(r["local_body"])} '
        f'STREAK={r["local_streak"]} '
        f'BREAK_AGE={r["break_age"]} '
        f'BREAK_DISTANCE={format_pct(r["break_distance"])} '
        f'SWING_RECOVERY={format_pct(r["swing_recovery"])} '
        f'ALIGN={r["alignment"]} '
        f'COMPLETED30M={r["completed_30m"]}'
    )


def report(name, records, detailed=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "structure",
        "CONFIRMED 30M STRUCTURE",
    )

    summarize(
        records,
        "break_age_class",
        "AGE OF LAST CONFIRMED BEARISH SUPPORT BREAK",
    )

    summarize(
        records,
        "break_distance_class",
        "ENTRY DISTANCE FROM BROKEN SUPPORT",
    )

    summarize(
        records,
        "swing_recovery_class",
        "RECOVERY FROM LAST CONFIRMED 30M SWING LOW",
    )

    summarize(
        records,
        "alignment",
        "30M STRUCTURE VS LAST COMPLETED 5M CANDLE",
    )

    if detailed:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-35")
    print("MAJOR TRANSITION VS LOCAL CANDLE MOVEMENT")
    print("READ-ONLY OBSERVATIONAL RESEARCH")

    combined = []

    for name, (
        path,
        expected_count,
        expected_net,
    ) in DATASETS.items():

        rows = load_candles(path)

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

        candles = regular_5m(rows)

        records = []

        for trade in result["trades"]:
            record = measure(candles, trade)
            record["dataset"] = name
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

    for record in combined:
        if (
            str(record["entry"].date())
            in PRIORITY_DATES
        ):
            print(audit_line(record))

    print()
    print("LIMITATIONS:")
    print(
        "30m swings require one completed right-hand bar."
    )
    print(
        "Support breaks require a completed 30m close."
    )
    print(
        "The last confirmed break may be old; "
        "it is not necessarily the current trend."
    )
    print(
        "Entry candle OPEN is used for price position; "
        "entry candle high/low/close are excluded."
    )
    print(
        "30m bars are built from contiguous completed "
        "regular-session 5m candles."
    )
    print(
        "No entry filters, no exit changes, "
        "no V18 modifications."
    )

    print("STEP 59F-5H-43K-35: PASS")


if __name__ == "__main__":
    main()
