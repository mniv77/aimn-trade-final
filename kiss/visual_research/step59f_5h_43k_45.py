
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-45
REVERSAL FRESHNESS AND SHORT ENTRY DELAY

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Measures:
- Latest confirmed bearish reversal before entry
- Latest confirmed lower high before entry
- Minutes and completed bars since confirmation
- Fresh versus stale confirmation
- Entry position relative to recent price structure

No lookahead.
No file writes.
No production or V18 changes.
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
        f"Duplicate timestamps: {path}"
    )

    return rows


def regular_candles(rows):
    result = []

    for row in rows:
        stamp = parse_time(row["timestamp"])

        if not time(9, 30) <= stamp.time() < time(16, 0):
            continue

        result.append({
            "time": stamp,
            "end": stamp + timedelta(minutes=5),
            "date": stamp.date(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })

    return result


def group_sessions(candles):
    sessions = defaultdict(list)

    for candle in candles:
        sessions[candle["date"]].append(candle)

    for day in sessions:
        sessions[day].sort(
            key=lambda c: c["time"]
        )

    return sessions


def continuous_opening_candles(session, entry):
    completed = [
        c for c in session
        if c["end"] <= entry
    ]

    result = []

    expected = datetime.combine(
        entry.date(),
        time(9, 30),
    )

    for candle in completed:
        if candle["time"] != expected:
            break

        result.append(candle)
        expected += timedelta(minutes=5)

    return result


def bearish_reversals(candles):
    """
    A rises, B makes a higher high,
    C closes below B's low.

    The reversal is known only at C.end.
    Returns ALL confirmed occurrences.
    """

    events = []

    for i in range(2, len(candles)):
        a = candles[i - 2]
        b = candles[i - 1]
        c = candles[i]

        if (
            a["close"] > a["open"]
            and b["high"] > a["high"]
            and c["close"] < b["low"]
        ):
            events.append({
                "time": c["end"],
                "price": c["close"],
                "index": i,
            })

    return events


def confirmed_lower_highs(candles):
    """
    A pivot at B is confirmed when C completes.

    Two consecutive confirmed pivot highs
    are compared.

    A lower high is registered only when
    the newer pivot is below the prior pivot.
    """

    pivots = []

    for i in range(1, len(candles) - 1):
        a = candles[i - 1]
        b = candles[i]
        c = candles[i + 1]

        if (
            b["high"] > a["high"]
            and b["high"] > c["high"]
        ):
            pivots.append({
                "price": b["high"],
                "time": c["end"],
                "index": i + 1,
            })

    events = []

    for i in range(1, len(pivots)):
        previous = pivots[i - 1]
        current = pivots[i]

        if current["price"] < previous["price"]:
            events.append(current)

    return events


def freshness(event, entry):
    if event is None:
        return {
            "minutes": None,
            "bars": None,
            "class": "NO_CONFIRMATION",
        }

    minutes = int(
        (entry - event["time"]).total_seconds() / 60
    )

    assert minutes >= 0
    assert minutes % 5 == 0

    bars = minutes // 5

    if bars == 0:
        label = "FRESH_0_BARS"
    elif bars <= 2:
        label = "FRESH_1_TO_2"
    elif bars <= 6:
        label = "RECENT_3_TO_6"
    elif bars <= 12:
        label = "AGING_7_TO_12"
    else:
        label = "STALE_13_PLUS"

    return {
        "minutes": minutes,
        "bars": bars,
        "class": label,
    }


def analyze_entry(sessions, entry):
    session = sessions.get(
        entry.date(), []
    )

    entry_candle = next(
        (
            c for c in session
            if c["time"] == entry
        ),
        None,
    )

    if entry_candle is None:
        raise ValueError(
            f"Entry candle missing: {entry}"
        )

    completed = continuous_opening_candles(
        session, entry
    )

    reversals = bearish_reversals(completed)
    lower_highs = confirmed_lower_highs(completed)

    latest_reversal = (
        reversals[-1] if reversals else None
    )

    latest_lower_high = (
        lower_highs[-1] if lower_highs else None
    )

    reversal_age = freshness(
        latest_reversal, entry
    )

    lower_high_age = freshness(
        latest_lower_high, entry
    )

    entry_price = entry_candle["open"]

    if completed:
        last_close = completed[-1]["close"]
        recent_high = max(
            c["high"]
            for c in completed[-6:]
        )
        recent_low = min(
            c["low"]
            for c in completed[-6:]
        )
    else:
        last_close = None
        recent_high = None
        recent_low = None

    move_from_last_close = (
        pct(entry_price, last_close)
        if last_close is not None
        else None
    )

    below_recent_high = (
        max(0.0, -pct(entry_price, recent_high))
        if recent_high is not None
        else None
    )

    above_recent_low = (
        max(0.0, pct(entry_price, recent_low))
        if recent_low is not None
        else None
    )

    return {
        "entry": entry,
        "completed_bars": len(completed),
        "reversal_count": len(reversals),
        "lower_high_count": len(lower_highs),
        "reversal_class": reversal_age["class"],
        "reversal_age_bars": reversal_age["bars"],
        "reversal_age_minutes": reversal_age["minutes"],
        "reversal_time": (
            latest_reversal["time"]
            if latest_reversal else None
        ),
        "lower_high_class": lower_high_age["class"],
        "lower_high_age_bars": lower_high_age["bars"],
        "lower_high_age_minutes": lower_high_age["minutes"],
        "lower_high_time": (
            latest_lower_high["time"]
            if latest_lower_high else None
        ),
        "move_from_last_close": move_from_last_close,
        "below_recent_high": below_recent_high,
        "above_recent_low": above_recent_low,
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
        f'BARS={record["completed_bars"]} '
        f'REVERSALS={record["reversal_count"]} '
        f'REV_AGE={record["reversal_class"]} '
        f'REV_BARS={record["reversal_age_bars"]} '
        f'REV_TIME={record["reversal_time"]} '
        f'LOWER_HIGHS={record["lower_high_count"]} '
        f'LH_AGE={record["lower_high_class"]} '
        f'LH_BARS={record["lower_high_age_bars"]} '
        f'LH_TIME={record["lower_high_time"]} '
        f'FROM_LAST_CLOSE={fmt(record["move_from_last_close"])} '
        f'BELOW_RECENT_HIGH={fmt(record["below_recent_high"])} '
        f'ABOVE_RECENT_LOW={fmt(record["above_recent_low"])}'
    )


def report(name, records, details=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "reversal_class",
        "LATEST BEARISH REVERSAL FRESHNESS",
    )

    summarize(
        records,
        "lower_high_class",
        "LATEST CONFIRMED LOWER HIGH FRESHNESS",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-45")
    print("REVERSAL FRESHNESS AND SHORT ENTRY DELAY")
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

        sessions = group_sessions(
            regular_candles(rows)
        )

        records = []

        for trade in result["trades"]:
            entry = parse_time(
                trade["entry_time"]
            )

            record = analyze_entry(
                sessions, entry
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
        "Only completed same-session 5m candles "
        "are used."
    )
    print(
        "Reversal and lower-high signals are "
        "local structural proxies."
    )
    print(
        "Signal freshness does not prove "
        "major trend direction."
    )
    print(
        "No filters approved. "
        "No file writes or V18 changes."
    )

    print("STEP 59F-5H-43K-45: PASS")


if __name__ == "__main__":
    main()
