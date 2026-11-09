
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-40
MAJOR REVERSAL FRESHNESS VS LATE SHORT ENTRY

NVDA SHORT 5m — READ-ONLY RESEARCH

Study the relationship between:
1. Confirmed 30m structural high sequence.
2. Age of the latest confirmed lower high.
3. Price distance from that lower high.
4. Local 5m peak position.
5. Winning and losing SHORT trades.

No lookahead.
No file writes.
No production modifications.
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

TOLERANCE = 0.000002


def parse_time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def pct(value, reference):
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
    result = []

    for r in rows:
        stamp = parse_time(r["timestamp"])

        if not time(9, 30) <= stamp.time() < time(16, 0):
            continue

        result.append({
            "time": stamp,
            "end": stamp + timedelta(minutes=5),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
        })

    return result


def build_30m(candles):
    groups = defaultdict(list)

    for c in candles:
        stamp = c["time"]
        offset = (
            stamp.hour * 60
            + stamp.minute
            - (9 * 60 + 30)
        )

        if 0 <= offset < 390:
            key = (
                stamp.date(),
                offset // 30,
            )
            groups[key].append(c)

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
    """
    A swing high is confirmed only when
    the following bar has completed.
    """

    eligible = [
        b for b in bars
        if b["end"] <= entry
    ]

    result = []

    for i in range(1, len(eligible) - 1):
        left = eligible[i - 1]
        middle = eligible[i]
        right = eligible[i + 1]

        if (
            middle["high"] > left["high"]
            and middle["high"] > right["high"]
        ):
            result.append({
                "time": middle["time"],
                "price": middle["high"],
                "confirmed_at": right["end"],
            })

    return result


def completed_before(bars, entry):
    return [
        b for b in bars
        if b["end"] <= entry
    ]


def lower_high_events(highs):
    """
    Compare consecutive confirmed 30m highs.

    An event is a lower high if its price
    is at least 0.10% below the preceding
    confirmed swing high.
    """

    events = []

    for i in range(1, len(highs)):
        previous = highs[i - 1]
        current = highs[i]

        difference = pct(
            current["price"],
            previous["price"],
        )

        if difference is not None and difference < -0.10:
            events.append({
                "time": current["time"],
                "confirmed_at": current["confirmed_at"],
                "price": current["price"],
                "previous_price": previous["price"],
                "difference": difference,
            })

    return events


def age_in_completed_bars(bars, confirmation, entry):
    if confirmation is None:
        return None

    return sum(
        confirmation < b["end"] <= entry
        for b in bars
    )


def freshness_class(age):
    if age is None:
        return "NO_CONFIRMED_LOWER_HIGH"

    if age <= 2:
        return "FRESH_0_TO_2"

    if age <= 6:
        return "RECENT_3_TO_6"

    return "OLD_7_PLUS"


def decline_class(distance):
    if distance is None:
        return "NO_REFERENCE"

    if distance >= 0:
        return "ABOVE_REFERENCE_HIGH"

    decline = -distance

    if decline < 0.5:
        return "DOWN_UNDER_0_5"

    if decline < 1.0:
        return "DOWN_0_5_TO_1"

    if decline < 2.0:
        return "DOWN_1_TO_2"

    return "DOWN_2_PLUS"


def local_peak_relationship(local, major):
    if local is None or major is None:
        return "MISSING_PEAK"

    difference = pct(
        local["price"],
        major["price"],
    )

    if difference > 0.20:
        return "LOCAL_ABOVE_30M_HIGH"

    if difference < -0.20:
        return "LOCAL_BELOW_30M_HIGH"

    return "LOCAL_NEAR_30M_HIGH"


def phase_class(age, distance):
    """
    Descriptive combinations only.

    These are NOT confirmed market phases.
    """

    if age is None or distance is None:
        return "NO_LOWER_HIGH_REFERENCE"

    if age <= 2 and distance > -1.0:
        return "EARLY_NEAR_LOWER_HIGH"

    if age <= 2:
        return "EARLY_FAR_BELOW"

    if age <= 6 and distance > -1.0:
        return "RECENT_NEAR_LOWER_HIGH"

    if age <= 6:
        return "RECENT_FAR_BELOW"

    if distance > -1.0:
        return "OLD_NEAR_LOWER_HIGH"

    return "OLD_FAR_BELOW"


def evaluate_entry(candles5, bars30, entry):
    eligible5 = completed_before(
        candles5,
        entry,
    )

    eligible30 = completed_before(
        bars30,
        entry,
    )

    local_highs = confirmed_highs(
        candles5,
        entry,
    )

    major_highs = confirmed_highs(
        bars30,
        entry,
    )

    local = (
        local_highs[-1]
        if local_highs else None
    )

    major = (
        major_highs[-1]
        if major_highs else None
    )

    events = lower_high_events(
        major_highs
    )

    latest_event = (
        events[-1]
        if events else None
    )

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

    event_price = (
        latest_event["price"]
        if latest_event else None
    )

    event_confirmation = (
        latest_event["confirmed_at"]
        if latest_event else None
    )

    age = age_in_completed_bars(
        eligible30,
        event_confirmation,
        entry,
    )

    distance = (
        pct(entry_price, event_price)
        if event_price is not None
        else None
    )

    major_sequence = "INSUFFICIENT_HIGHS"

    if len(major_highs) >= 2:
        change = pct(
            major_highs[-1]["price"],
            major_highs[-2]["price"],
        )

        if change < -0.10:
            major_sequence = "LATEST_LOWER_HIGH"
        elif change > 0.10:
            major_sequence = "LATEST_HIGHER_HIGH"
        else:
            major_sequence = "LATEST_EQUAL_HIGH"

    latest_event_is_current = (
        latest_event is not None
        and major is not None
        and latest_event["time"] == major["time"]
    )

    local_vs_event = (
        pct(local["price"], event_price)
        if local is not None
        and event_price is not None
        else None
    )

    return {
        "entry": entry,
        "entry_price": entry_price,
        "major_high_time": (
            major["time"] if major else None
        ),
        "major_sequence": major_sequence,
        "lower_high_time": (
            latest_event["time"]
            if latest_event else None
        ),
        "lower_high_confirmed": event_confirmation,
        "lower_high_age": age,
        "distance_from_lower_high": distance,
        "local_high_time": (
            local["time"] if local else None
        ),
        "local_vs_lower_high": local_vs_event,
        "freshness": freshness_class(age),
        "decline": decline_class(distance),
        "phase": phase_class(age, distance),
        "event_status": (
            "LATEST_HIGH_IS_LOWER_HIGH"
            if latest_event_is_current
            else "OLDER_LOWER_HIGH"
            if latest_event is not None
            else "NO_LOWER_HIGH"
        ),
        "local_relation": local_peak_relationship(
            local,
            latest_event,
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
        f'LATEST_30M={r["major_sequence"]} '
        f'LOWER_HIGH={r["lower_high_time"]} '
        f'CONFIRMED={r["lower_high_confirmed"]} '
        f'AGE={r["lower_high_age"]} '
        f'DISTANCE={fmt(r["distance_from_lower_high"])} '
        f'LOCAL_VS_LH={fmt(r["local_vs_lower_high"])} '
        f'EVENT={r["event_status"]} '
        f'PHASE={r["phase"]}'
    )


def report(name, records, details=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "major_sequence",
        "LATEST CONFIRMED 30M HIGH SEQUENCE",
    )

    summarize(
        records,
        "event_status",
        "LATEST LOWER HIGH VS OLDER LOWER HIGH",
    )

    summarize(
        records,
        "freshness",
        "AGE OF MOST RECENT CONFIRMED LOWER HIGH",
    )

    summarize(
        records,
        "decline",
        "ENTRY DISTANCE FROM LOWER HIGH",
    )

    summarize(
        records,
        "phase",
        "FRESHNESS AND DISTANCE COMBINED",
    )

    summarize(
        records,
        "local_relation",
        "LOCAL 5M PEAK VS LOWER HIGH",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-40")
    print("MAJOR REVERSAL FRESHNESS")
    print("VS LATE SHORT ENTRY")
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

            record = evaluate_entry(
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
        "A confirmed 30m lower high is a "
        "structural proxy, not proof of "
        "a major reversal."
    )
    print(
        "Latest lower-high event can be older "
        "than the latest confirmed 30m high."
    )
    print(
        "30m swing confirmation requires "
        "a completed right-hand 30m bar."
    )
    print(
        "The entry candle is not used "
        "to confirm swing highs."
    )
    print(
        "Entry distance uses entry candle "
        "open, not simulated fill price."
    )
    print(
        "No new trading filters are approved."
    )
    print(
        "No file writes, no production changes, "
        "no V18 modifications."
    )

    print("STEP 59F-5H-43K-40: PASS")


if __name__ == "__main__":
    main()
