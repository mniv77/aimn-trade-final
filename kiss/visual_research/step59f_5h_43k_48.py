
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-48
POST-EXIT PRICE PATH AND REVERSAL SEQUENCE AUDIT

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Questions:
1. Did price initially rise or fall after exit?
2. Did adverse recovery occur before later decline?
3. How quickly did a new bearish move appear?
4. Did the exit protect against a substantial recovery?
5. Which cases merit further trend-transition research?

All post-exit observations are hindsight only.
No file writes, filters, or V18 changes.
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
    "2026-10-14",
}

TOLERANCE = 0.000002
BAR_MINUTES = 5
CONTINUATION_THRESHOLD = 0.5
RECOVERY_THRESHOLD = 0.5


def parse_time(value):
    if isinstance(value, datetime):
        return value

    return datetime.fromisoformat(str(value))


def pct(new_price, reference):
    return (
        (new_price / reference - 1.0) * 100.0
        if reference
        else None
    )


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
        stamp = parse_time(row["timestamp"])

        if not (
            time(9, 30)
            <= stamp.time()
            < time(16, 0)
        ):
            continue

        candles.append({
            "time": stamp,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })

    return candles


def post_exit_window(
    candles,
    exit_time,
    next_entry,
):
    """
    Start at exit candle timestamp.
    End before next entry or end of exit day.
    """

    return [
        candle
        for candle in candles
        if (
            candle["time"] >= exit_time
            and candle["time"].date()
                == exit_time.date()
            and (
                next_entry is None
                or candle["time"] < next_entry
            )
        )
    ]


def first_threshold_event(
    candles,
    reference,
):
    """
    Find first 0.5% favorable SHORT decline
    and first 0.5% adverse upward recovery.

    If both occur within the same candle,
    ordering is unknown.
    """

    down_index = None
    up_index = None

    for index, candle in enumerate(candles):
        down_move = -pct(
            candle["low"],
            reference,
        )

        up_move = pct(
            candle["high"],
            reference,
        )

        if (
            down_index is None
            and down_move >= CONTINUATION_THRESHOLD
        ):
            down_index = index

        if (
            up_index is None
            and up_move >= RECOVERY_THRESHOLD
        ):
            up_index = index

    if (
        down_index is None
        and up_index is None
    ):
        sequence = "NEITHER_THRESHOLD"

    elif down_index is None:
        sequence = "RECOVERY_ONLY"

    elif up_index is None:
        sequence = "DECLINE_ONLY"

    elif down_index < up_index:
        sequence = "DECLINE_FIRST"

    elif up_index < down_index:
        sequence = "RECOVERY_FIRST"

    else:
        sequence = "SAME_BAR_UNKNOWN_ORDER"

    return down_index, up_index, sequence


def classify_initial(candles, reference):
    if not candles:
        return "NO_POST_EXIT_BARS"

    first = candles[0]

    change = pct(
        first["close"],
        reference,
    )

    if change < -0.05:
        return "INITIAL_DOWN"

    if change > 0.05:
        return "INITIAL_UP"

    return "INITIAL_FLAT"


def summarize(records, key, title):
    print()
    print(title)

    groups = defaultdict(list)

    for record in records:
        groups[record[key]].append(record)

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
            f"{label:34s} "
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
        f'INITIAL={record["initial"]} '
        f'SEQUENCE={record["sequence"]} '
        f'DOWN={fmt(record["best_down"])} '
        f'UP={fmt(record["worst_up"])} '
        f'DOWN_BAR={record["down_bar"]} '
        f'UP_BAR={record["up_bar"]} '
        f'BARS={record["post_bars"]}'
    )


def report(name, records, details=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "initial",
        "INITIAL POST-EXIT DIRECTION",
    )

    summarize(
        records,
        "sequence",
        "FIRST 0.5% MOVE AFTER EXIT",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-48")
    print(
        "POST-EXIT PRICE PATH "
        "AND REVERSAL SEQUENCE AUDIT"
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

            next_entry = (
                parse_time(
                    trades[index + 1]["entry_time"]
                )
                if index + 1 < len(trades)
                else None
            )

            window = post_exit_window(
                candles,
                exit_time,
                next_entry,
            )

            exit_candle = next(
                (
                    candle
                    for candle in candles
                    if candle["time"] == exit_time
                ),
                None,
            )

            reference = (
                exit_candle["open"]
                if exit_candle is not None
                else None
            )

            if reference is None:
                initial = "NO_EXIT_REFERENCE"
                sequence = "NO_EXIT_REFERENCE"
                best_down = None
                worst_up = None
                down_bar = None
                up_bar = None

            else:
                initial = classify_initial(
                    window,
                    reference,
                )

                down_bar, up_bar, sequence = (
                    first_threshold_event(
                        window,
                        reference,
                    )
                )

                best_down = (
                    max(
                        -pct(c["low"], reference)
                        for c in window
                    )
                    if window
                    else None
                )

                worst_up = (
                    max(
                        pct(c["high"], reference)
                        for c in window
                    )
                    if window
                    else None
                )

            record = {
                "dataset": name,
                "entry": entry,
                "exit": exit_time,
                "net": float(
                    trade["net_pnl_pct"]
                ),
                "initial": initial,
                "sequence": sequence,
                "best_down": best_down,
                "worst_up": worst_up,
                "down_bar": down_bar,
                "up_bar": up_bar,
                "post_bars": len(window),
            }

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
        "Post-exit observations are hindsight, "
        "not information available at exit."
    )
    print(
        "A 0.5% move is a research threshold, "
        "not a trading rule."
    )
    print(
        "Intrabar high/low order is unknown."
    )
    print(
        "Post-exit analysis stops at the "
        "next entry or end of exit session."
    )
    print(
        "This study measures price movement, "
        "not confirmed major trend reversals."
    )
    print(
        "No filters approved. "
        "No file writes or V18 changes."
    )

    print("STEP 59F-5H-43K-48: PASS")


if __name__ == "__main__":
    main()
