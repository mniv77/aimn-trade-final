
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-41
FIRST DOWNWARD LEG VS CONTINUATION ENTRY

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Investigates:
- Latest confirmed 30m lower-high event
- Price decline after confirmation
- Lowest completed 5m price before entry
- Recovery from that low
- First-leg vs continuation characteristics

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


def percent(value, reference):
    if reference is None or reference == 0:
        return None
    return (value / reference - 1.0) * 100.0


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


def build_30m(candles):
    groups = defaultdict(list)

    for candle in candles:
        stamp = candle["time"]

        offset = (
            stamp.hour * 60
            + stamp.minute
            - 570
        )

        if 0 <= offset < 390:
            groups[
                (stamp.date(), offset // 30)
            ].append(candle)

    result = []

    for key in sorted(groups):
        group = sorted(
            groups[key],
            key=lambda c: c["time"],
        )

        if len(group) != 6:
            continue

        if any(
            group[i + 1]["time"] - group[i]["time"]
            != timedelta(minutes=5)
            for i in range(5)
        ):
            continue

        result.append({
            "time": group[0]["time"],
            "end": group[-1]["end"],
            "open": group[0]["open"],
            "high": max(
                c["high"] for c in group
            ),
            "low": min(
                c["low"] for c in group
            ),
            "close": group[-1]["close"],
        })

    return result


def confirmed_highs(bars, entry):
    eligible = [
        b for b in bars
        if b["end"] <= entry
    ]

    peaks = []

    for i in range(1, len(eligible) - 1):
        left = eligible[i - 1]
        middle = eligible[i]
        right = eligible[i + 1]

        if (
            middle["high"] > left["high"]
            and middle["high"] > right["high"]
        ):
            peaks.append({
                "time": middle["time"],
                "price": middle["high"],
                "confirmed_at": right["end"],
            })

    return peaks


def lower_high_events(highs):
    events = []

    for i in range(1, len(highs)):
        previous = highs[i - 1]
        current = highs[i]

        difference = percent(
            current["price"],
            previous["price"],
        )

        if difference is not None and difference < -0.10:
            events.append({
                "time": current["time"],
                "confirmed_at": current["confirmed_at"],
                "price": current["price"],
                "difference": difference,
            })

    return events


def decline_bucket(value):
    if value is None:
        return "NO_REFERENCE"

    if value < 0.5:
        return "DECLINE_UNDER_0_5"

    if value < 1.0:
        return "DECLINE_0_5_TO_1"

    if value < 2.0:
        return "DECLINE_1_TO_2"

    return "DECLINE_2_PLUS"


def recovery_bucket(value):
    if value is None:
        return "NO_REFERENCE"

    if value < 0.2:
        return "RECOVERY_UNDER_0_2"

    if value < 0.5:
        return "RECOVERY_0_2_TO_0_5"

    if value < 1.0:
        return "RECOVERY_0_5_TO_1"

    return "RECOVERY_1_PLUS"


def location_class(
    decline,
    recovery,
    bars_since_low,
):
    """
    Descriptive labels only.

    FIRST_LEG_CANDIDATE:
        Recent low, limited recovery.

    REBOUND_ENTRY:
        Material recovery from previous low.

    CONTINUATION_CANDIDATE:
        Low is older, limited recovery.

    These labels do not establish the
    true major market trend.
    """

    if (
        decline is None
        or recovery is None
        or bars_since_low is None
    ):
        return "NO_REFERENCE"

    if recovery >= 0.5:
        return "REBOUND_ENTRY"

    if bars_since_low <= 2:
        return "FIRST_LEG_CANDIDATE"

    return "CONTINUATION_CANDIDATE"


def analyze_entry(candles5, bars30, entry):
    completed5 = [
        c for c in candles5
        if c["end"] <= entry
    ]

    peaks30 = confirmed_highs(
        bars30,
        entry,
    )

    events = lower_high_events(
        peaks30
    )

    latest = events[-1] if events else None

    entry_candle = next(
        (
            c for c in candles5
            if c["time"] == entry
        ),
        None,
    )

    if entry_candle is None:
        raise ValueError(
            f"Missing entry candle: {entry}"
        )

    entry_price = entry_candle["open"]

    if latest is None:
        return {
            "entry": entry,
            "lower_high_time": None,
            "confirmation": None,
            "decline": None,
            "recovery": None,
            "bars_since_low": None,
            "lowest_time": None,
            "location": "NO_REFERENCE",
            "decline_bucket": "NO_REFERENCE",
            "recovery_bucket": "NO_REFERENCE",
            "event_status": "NO_LOWER_HIGH",
        }

    reference_time = latest["confirmed_at"]

    journey = [
        c for c in completed5
        if c["time"] >= reference_time
    ]

    if not journey:
        return {
            "entry": entry,
            "lower_high_time": latest["time"],
            "confirmation": reference_time,
            "decline": None,
            "recovery": None,
            "bars_since_low": None,
            "lowest_time": None,
            "location": "NO_REFERENCE",
            "decline_bucket": "NO_REFERENCE",
            "recovery_bucket": "NO_REFERENCE",
            "event_status": "NO_COMPLETED_POST_CONFIRMATION",
        }

    lowest_index = min(
        range(len(journey)),
        key=lambda i: journey[i]["low"],
    )

    lowest = journey[lowest_index]
    lowest_price = lowest["low"]

    reference_price = latest["price"]

    decline = max(
        0.0,
        -percent(
            lowest_price,
            reference_price,
        ),
    )

    recovery = max(
        0.0,
        percent(
            entry_price,
            lowest_price,
        ),
    )

    bars_since_low = (
        len(journey) - 1 - lowest_index
    )

    return {
        "entry": entry,
        "lower_high_time": latest["time"],
        "confirmation": reference_time,
        "decline": decline,
        "recovery": recovery,
        "bars_since_low": bars_since_low,
        "lowest_time": lowest["time"],
        "location": location_class(
            decline,
            recovery,
            bars_since_low,
        ),
        "decline_bucket": decline_bucket(
            decline
        ),
        "recovery_bucket": recovery_bucket(
            recovery
        ),
        "event_status": "POST_LOWER_HIGH",
    }


def summarize(records, field, title):
    print()
    print(title)

    groups = defaultdict(list)

    for record in records:
        groups[record[field]].append(record)

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
            f"{label:36s} "
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
        f'LOWER_HIGH={r["lower_high_time"]} '
        f'CONFIRMED={r["confirmation"]} '
        f'LOWEST={r["lowest_time"]} '
        f'DECLINE={fmt(r["decline"])} '
        f'RECOVERY={fmt(r["recovery"])} '
        f'BARS_AFTER_LOW={r["bars_since_low"]} '
        f'LOCATION={r["location"]}'
    )


def report(name, records, details=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "location",
        "FIRST LEG VS CONTINUATION LOCATION",
    )

    summarize(
        records,
        "decline_bucket",
        "DECLINE FROM CONFIRMED LOWER HIGH",
    )

    summarize(
        records,
        "recovery_bucket",
        "RECOVERY FROM LOW BEFORE ENTRY",
    )

    summarize(
        records,
        "event_status",
        "LOWER-HIGH REFERENCE AVAILABILITY",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-41")
    print("FIRST DOWNWARD LEG")
    print("VS CONTINUATION ENTRY")
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
            result["trade_count"] == expected_count
        ), f"{name}: trade count changed"

        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < TOLERANCE, (
            f"{name}: baseline net changed"
        )

        candles5 = regular_candles(rows)
        bars30 = build_30m(candles5)

        records = []

        for trade in result["trades"]:
            entry = parse_time(
                trade["entry_time"]
            )

            record = analyze_entry(
                candles5,
                bars30,
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
        if str(record["entry"].date()) in PRIORITY_DATES:
            print(audit_line(record))

    print()
    print("LIMITATIONS:")
    print(
        "Confirmed lower highs are structural "
        "proxies, not verified major reversals."
    )
    print(
        "The journey begins at swing confirmation, "
        "not the earlier swing-high candle."
    )
    print(
        "Completed 5m lows may include price "
        "movement across multiple sessions."
    )
    print(
        "Entry candle open is used as the "
        "entry-location reference."
    )
    print(
        "No lookahead, no approved filters, "
        "no file writes, no V18 changes."
    )

    print("STEP 59F-5H-43K-41: PASS")


if __name__ == "__main__":
    main()
