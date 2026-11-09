
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-47
COMPLETE CROSS-SESSION EXCURSION AND EXIT AUDIT

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Research questions:
1. What favorable and adverse price movement occurred
   during each complete trade, including overnight holds?
2. How much favorable movement occurred before exit?
3. What price movement occurred after exit?
4. Which trades warrant closer entry or exit investigation?

MFE and MAE are hindsight candle-range measurements.
They are not guaranteed executable prices.

No file writes.
No filters approved.
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


def pct_change(new_value, old_value):
    if old_value is None or old_value == 0:
        return None

    return (
        new_value / old_value - 1.0
    ) * 100.0


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
        key=lambda row: parse_time(
            row["timestamp"]
        ),
    )

    timestamps = [
        parse_time(row["timestamp"])
        for row in rows
    ]

    assert len(timestamps) == len(set(timestamps)), (
        f"Duplicate timestamps: {path}"
    )

    return rows


def regular_candles(rows):
    candles = []

    for row in rows:
        stamp = parse_time(
            row["timestamp"]
        )

        if not (
            time(9, 30)
            <= stamp.time()
            < time(16, 0)
        ):
            continue

        candles.append({
            "time": stamp,
            "end": stamp + timedelta(
                minutes=5
            ),
            "date": stamp.date(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })

    return candles


def find_entry_candle(candles, entry):
    for candle in candles:
        if candle["time"] == entry:
            return candle

    raise ValueError(
        f"Entry candle missing: {entry}"
    )


def trade_candles(candles, entry, exit_time):
    return [
        candle
        for candle in candles
        if entry <= candle["time"] < exit_time
    ]


def after_exit_candles(
    candles,
    exit_time,
    next_entry=None,
):
    """
    Post-exit research window:

    Starts at the recorded exit timestamp.
    Stops at the next entry, if one exists.
    Stops at the end of the exit session.

    This prevents attributing later unrelated
    sessions to the original trade.
    """

    result = []

    for candle in candles:
        if candle["time"] < exit_time:
            continue

        if candle["date"] != exit_time.date():
            continue

        if (
            next_entry is not None
            and candle["time"] >= next_entry
        ):
            continue

        result.append(candle)

    return result


def excursion(candles, entry_price):
    if not candles:
        return {
            "mfe": None,
            "mae": None,
            "low": None,
            "high": None,
        }

    lowest = min(
        candle["low"]
        for candle in candles
    )

    highest = max(
        candle["high"]
        for candle in candles
    )

    return {
        "mfe": max(
            0.0,
            -pct_change(
                lowest,
                entry_price,
            ),
        ),
        "mae": max(
            0.0,
            pct_change(
                highest,
                entry_price,
            ),
        ),
        "low": lowest,
        "high": highest,
    }


def classify_mfe(value):
    if value is None:
        return "MFE_UNAVAILABLE"

    if value < 0.2:
        return "MFE_UNDER_0_2"

    if value < 0.5:
        return "MFE_0_2_TO_0_5"

    if value < 1.0:
        return "MFE_0_5_TO_1"

    return "MFE_1_PLUS"


def classify_capture(value):
    if value is None:
        return "CAPTURE_UNAVAILABLE"

    if value < 0:
        return "NEGATIVE_NET"

    if value < 25:
        return "CAPTURE_UNDER_25"

    if value < 50:
        return "CAPTURE_25_TO_50"

    if value < 75:
        return "CAPTURE_50_TO_75"

    return "CAPTURE_75_PLUS"


def summarize(records, field, title):
    print()
    print(title)

    groups = defaultdict(list)

    for record in records:
        groups[record[field]].append(
            record
        )

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
        f'EXIT={record["exit"]} '
        f'NET={record["net"]:+.6f}% '
        f'MFE={fmt(record["mfe"])} '
        f'MAE={fmt(record["mae"])} '
        f'CAPTURE={fmt(record["capture"])} '
        f'POST_EXIT_MFE={fmt(record["post_exit_mfe"])} '
        f'POST_EXIT_FROM_ENTRY={fmt(record["post_exit_from_entry"])} '
        f'TRADE_BARS={record["trade_bars"]} '
        f'SESSIONS={record["sessions"]} '
        f'POST_EXIT_BARS={record["post_exit_bars"]}'
    )


def report(name, records, details=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "mfe_class",
        "COMPLETE-TRADE MAXIMUM FAVORABLE EXCURSION",
    )

    summarize(
        records,
        "capture_class",
        "NET PROFIT AS PERCENTAGE OF MFE",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-47")
    print(
        "COMPLETE CROSS-SESSION "
        "EXCURSION AND EXIT AUDIT"
    )
    print("READ-ONLY OBSERVATIONAL RESEARCH")

    combined = []

    for name, (
        path,
        expected_count,
        expected_net,
    ) in DATASETS.items():

        rows = load_rows(path)
        candles = regular_candles(rows)

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

        trades = sorted(
            result["trades"],
            key=lambda trade: parse_time(
                trade["entry_time"]
            ),
        )

        records = []

        for index, trade in enumerate(trades):
            entry = parse_time(
                trade["entry_time"]
            )

            exit_time = parse_time(
                trade["exit_time"]
            )

            assert exit_time > entry, (
                f"Invalid exit: {entry}"
            )

            next_entry = (
                parse_time(
                    trades[index + 1]["entry_time"]
                )
                if index + 1 < len(trades)
                else None
            )

            entry_candle = find_entry_candle(
                candles, entry
            )

            entry_price = entry_candle["open"]

            held = trade_candles(
                candles,
                entry,
                exit_time,
            )

            held_excursion = excursion(
                held,
                entry_price,
            )

            after = after_exit_candles(
                candles,
                exit_time,
                next_entry,
            )

            after_excursion = excursion(
                after,
                entry_price,
            )

            exit_candle = next(
                (
                    candle
                    for candle in candles
                    if candle["time"] == exit_time
                ),
                None,
            )

            if exit_candle is not None:
                exit_reference = exit_candle["open"]
            else:
                exit_reference = None

            if after and exit_reference is not None:
                post_exit_mfe = max(
                    0.0,
                    -pct_change(
                        min(c["low"] for c in after),
                        exit_reference,
                    ),
                )
            else:
                post_exit_mfe = None

            mfe = held_excursion["mfe"]
            net = float(
                trade["net_pnl_pct"]
            )

            if mfe is not None and mfe > 0:
                capture = net / mfe * 100.0
            else:
                capture = None

            record = {
                "dataset": name,
                "entry": entry,
                "exit": exit_time,
                "net": net,
                "mfe": mfe,
                "mae": held_excursion["mae"],
                "capture": capture,
                "post_exit_mfe": post_exit_mfe,
                "post_exit_from_entry": (
                    after_excursion["mfe"]
                ),
                "trade_bars": len(held),
                "sessions": len({
                    c["date"] for c in held
                }),
                "post_exit_bars": len(after),
            }

            record["mfe_class"] = (
                classify_mfe(mfe)
            )

            record["capture_class"] = (
                classify_capture(capture)
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
        "MFE and MAE use five-minute candle "
        "highs/lows, not executable fills."
    )
    print(
        "Capture uses net P&L divided by "
        "gross price excursion; it is only "
        "a descriptive comparison."
    )
    print(
        "Post-exit analysis ends at the "
        "next entry or end of exit session."
    )
    print(
        "Intrabar high/low ordering is unknown."
    )
    print(
        "No filters approved. "
        "No file writes or V18 changes."
    )

    print("STEP 59F-5H-43K-47: PASS")


if __name__ == "__main__":
    main()
