
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-39
MAJOR PEAK VS MINOR PEAK — ENTRY LOCATION AUDIT

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Compare the latest confirmed 5m local peak
against confirmed 30m structural swing highs.

No lookahead.
No file writes.
No V18 modifications.
No production changes.
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

EPS = 1e-10


def parse_time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def pct(new, old):
    if old is None or abs(old) < EPS:
        return None
    return (new / old - 1.0) * 100.0


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def load_rows(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["candles"] if isinstance(data, dict) else data

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
    candles = []

    for r in rows:
        stamp = parse_time(r["timestamp"])

        if not time(9, 30) <= stamp.time() < time(16, 0):
            continue

        candles.append({
            "time": stamp,
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
        })

    return candles


def completed_5m(candles, entry):
    return [
        c for c in candles
        if c["time"] + timedelta(minutes=5) <= entry
    ]


def build_30m(candles):
    """
    Build 30m bars from exactly six consecutive
    regular-session 5m candles.

    Incomplete 30m bars are excluded.
    """

    groups = defaultdict(list)

    for c in candles:
        stamp = c["time"]
        minute = stamp.hour * 60 + stamp.minute
        session_start = 9 * 60 + 30

        offset = minute - session_start

        if not 0 <= offset < 390:
            continue

        bucket = offset // 30

        groups[(stamp.date(), bucket)].append(c)

    bars = []

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

        start = group[0]["time"]
        end = group[-1]["time"] + timedelta(minutes=5)

        bars.append({
            "time": start,
            "end": end,
            "open": group[0]["open"],
            "high": max(c["high"] for c in group),
            "low": min(c["low"] for c in group),
            "close": group[-1]["close"],
        })

    return bars


def confirmed_peaks(bars, duration_minutes):
    """
    A swing high is confirmed only after its
    right-hand bar has fully completed.

    The right-hand bar may belong to a later
    trading session.
    """

    peaks = []

    for i in range(1, len(bars) - 1):
        left = bars[i - 1]
        middle = bars[i]
        right = bars[i + 1]

        if (
            middle["high"] > left["high"]
            and middle["high"] > right["high"]
        ):
            peaks.append({
                "index": i,
                "time": middle["time"],
                "price": middle["high"],
                "confirmed_at": right.get(
                    "end",
                    right["time"] + timedelta(minutes=duration_minutes),
                ),
            })

    return peaks


def latest_peak_before(peaks, entry):
    valid = [
        p for p in peaks
        if p["confirmed_at"] <= entry
    ]

    return valid[-1] if valid else None


def peak_relationship(local, major):
    if local is None or major is None:
        return "MISSING_PEAK"

    difference = pct(
        local["price"],
        major["price"],
    )

    if difference is None:
        return "MISSING_PEAK"

    if difference > 0.20:
        return "LOCAL_ABOVE_MAJOR_0_2_PLUS"

    if difference < -0.20:
        return "LOCAL_BELOW_MAJOR_0_2_PLUS"

    return "LOCAL_NEAR_MAJOR"


def entry_distance_class(value):
    if value is None:
        return "NO_MAJOR_PEAK"

    if value > 0:
        return "ENTRY_ABOVE_MAJOR_PEAK"

    distance = -value

    if distance < 0.50:
        return "WITHIN_0_5_BELOW_MAJOR"

    if distance < 1.00:
        return "BELOW_MAJOR_0_5_TO_1"

    if distance < 2.00:
        return "BELOW_MAJOR_1_TO_2"

    return "BELOW_MAJOR_2_PLUS"


def major_age_class(value):
    if value is None:
        return "NO_MAJOR_PEAK"

    if value <= 2:
        return "MAJOR_RECENT_0_TO_2_BARS"

    if value <= 6:
        return "MAJOR_INTERMEDIATE_3_TO_6"

    return "MAJOR_OLD_7_PLUS"


def major_high_sequence(peaks, entry):
    valid = [
        p for p in peaks
        if p["confirmed_at"] <= entry
    ]

    if len(valid) < 2:
        return "INSUFFICIENT_MAJOR_HIGHS"

    previous = valid[-2]["price"]
    latest = valid[-1]["price"]

    difference = pct(latest, previous)

    if difference > 0.10:
        return "MAJOR_HIGHER_HIGH"

    if difference < -0.10:
        return "MAJOR_LOWER_HIGH"

    return "MAJOR_EQUAL_HIGH"


def entry_position(candles, bars30, entry):
    completed5 = completed_5m(candles, entry)

    if not completed5:
        raise ValueError(
            f"No completed 5m candle before {entry}"
        )

    local_peaks = confirmed_peaks(
        completed5,
        5,
    )

    major_peaks = confirmed_peaks(
        [
            b for b in bars30
            if b["end"] <= entry
        ],
        30,
    )

    local = latest_peak_before(
        local_peaks,
        entry,
    )

    major = latest_peak_before(
        major_peaks,
        entry,
    )

    entry_open = next(
        (
            c["open"]
            for c in candles
            if c["time"] == entry
        ),
        None,
    )

    if entry_open is None:
        raise ValueError(
            f"Missing entry candle: {entry}"
        )

    local_price = (
        local["price"]
        if local else None
    )

    major_price = (
        major["price"]
        if major else None
    )

    local_vs_major = (
        pct(local_price, major_price)
        if local_price is not None
        and major_price is not None
        else None
    )

    entry_vs_major = (
        pct(entry_open, major_price)
        if major_price is not None
        else None
    )

    entry_vs_local = (
        pct(entry_open, local_price)
        if local_price is not None
        else None
    )

    major_age = None

    if major is not None:
        completed30 = [
            b for b in bars30
            if b["end"] <= entry
        ]

        major_age = sum(
            b["end"] > major["confirmed_at"]
            for b in completed30
        )

    return {
        "entry": entry,
        "local_peak_time": (
            local["time"] if local else None
        ),
        "local_peak": local_price,
        "major_peak_time": (
            major["time"] if major else None
        ),
        "major_peak": major_price,
        "major_confirmed_at": (
            major["confirmed_at"] if major else None
        ),
        "local_vs_major": local_vs_major,
        "entry_vs_major": entry_vs_major,
        "entry_vs_local": entry_vs_local,
        "major_age": major_age,
        "relationship": peak_relationship(
            local,
            major,
        ),
        "distance_class": entry_distance_class(
            entry_vs_major
        ),
        "major_age_class": major_age_class(
            major_age
        ),
        "high_sequence": major_high_sequence(
            major_peaks,
            entry,
        ),
    }


def summarize(records, key, title):
    print()
    print(title)

    groups = defaultdict(list)

    for r in records:
        groups[r[key]].append(r)

    for label, group in sorted(groups.items()):
        wins = sum(
            r["net"] > 0 for r in group
        )

        losses = sum(
            r["net"] < 0 for r in group
        )

        net = sum(
            r["net"] for r in group
        )

        print(
            f"{label:36s} "
            f"N={len(group):2d} "
            f"W={wins:2d} "
            f"L={losses:2d} "
            f"NET={net:+.6f}%"
        )


def audit_line(r):
    return (
        f'{r["dataset"]:10s} '
        f'{r["entry"]} '
        f'NET={r["net"]:+.6f}% '
        f'LOCAL_TIME={r["local_peak_time"]} '
        f'MAJOR_TIME={r["major_peak_time"]} '
        f'MAJOR_CONFIRMED={r["major_confirmed_at"]} '
        f'LOCAL_VS_MAJOR={fmt(r["local_vs_major"])} '
        f'ENTRY_VS_MAJOR={fmt(r["entry_vs_major"])} '
        f'ENTRY_VS_LOCAL={fmt(r["entry_vs_local"])} '
        f'MAJOR_AGE={r["major_age"]} '
        f'RELATION={r["relationship"]} '
        f'HIGH_SEQUENCE={r["high_sequence"]}'
    )


def report(name, records, detailed=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "relationship",
        "LOCAL 5M PEAK VS CONFIRMED 30M HIGH",
    )

    summarize(
        records,
        "distance_class",
        "ENTRY DISTANCE FROM MAJOR HIGH",
    )

    summarize(
        records,
        "major_age_class",
        "AGE OF CONFIRMED MAJOR HIGH",
    )

    summarize(
        records,
        "high_sequence",
        "SEQUENCE OF CONFIRMED 30M HIGHS",
    )

    if detailed:
        print()
        print("TRADE AUDIT")

        for r in records:
            print(audit_line(r))


def main():
    print("AIMn — STEP 59F-5H-43K-39")
    print("MAJOR PEAK VS MINOR PEAK")
    print("ENTRY LOCATION AUDIT")
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

        assert result["trade_count"] == expected_count, (
            f"{name}: baseline trade count changed"
        )

        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < 0.000002, (
            f"{name}: baseline net changed"
        )

        candles = regular_candles(rows)
        bars30 = build_30m(candles)

        records = []

        for trade in result["trades"]:
            entry = parse_time(
                trade["entry_time"]
            )

            record = entry_position(
                candles,
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
    ) < 0.000002

    report(
        "COMBINED — DESCRIPTIVE ONLY",
        combined,
        detailed=False,
    )

    print()
    print("PRIORITY CASES")

    for r in combined:
        if str(r["entry"].date()) in PRIORITY_DATES:
            print(audit_line(r))

    print()
    print("LIMITATIONS:")
    print(
        "5m and 30m peaks require a fully "
        "completed right-hand candle."
    )
    print(
        "Entry candle OPEN is used only "
        "for entry position measurement."
    )
    print(
        "30m highs are confirmed local swings, "
        "not independently verified major reversals."
    )
    print(
        "Peak comparisons can span "
        "multiple trading sessions."
    )
    print(
        "Major-high age counts completed 30m "
        "bars after swing confirmation."
    )
    print(
        "Thresholds are descriptive only. "
        "No entry filters approved."
    )
    print(
        "No file writes, no production changes, "
        "no V18 modifications."
    )

    print("STEP 59F-5H-43K-39: PASS")


if __name__ == "__main__":
    main()
