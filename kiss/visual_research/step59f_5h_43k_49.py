
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-49
EXIT-CANDLE STRUCTURE AND EARLY CONTINUATION AUDIT

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Separate:
A. Completed candle structure before exit
B. Subsequent price movement after exit

No filters, file writes, or V18 changes.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, time
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
    "2026-07-13",
    "2026-07-24",
    "2026-07-28",
    "2026-08-03",
    "2026-08-10",
    "2026-08-21",
    "2026-08-28",
    "2026-10-14",
}

TOLERANCE = 0.000002


def parse_time(value):
    if isinstance(value, datetime):
        return value

    return datetime.fromisoformat(str(value))


def pct(price, reference):
    return (
        (price / reference - 1.0) * 100.0
        if reference
        else None
    )


def fmt(value):
    return (
        "NA"
        if value is None
        else f"{value:+.4f}%"
    )


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
        f"Duplicate timestamps in {path}"
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


def structure_before_exit(candles, exit_time):
    """
    Five completed 5m candles before exit.
    Excludes the exit-timestamp candle to
    avoid using information not yet available.
    """

    history = [
        c
        for c in candles
        if c["time"] < exit_time
    ]

    recent = history[-5:]

    if len(recent) < 5:
        return None

    bearish = sum(
        c["close"] < c["open"]
        for c in recent
    )

    bullish = sum(
        c["close"] > c["open"]
        for c in recent
    )

    lower_highs = sum(
        recent[i]["high"]
        < recent[i - 1]["high"]
        for i in range(1, 5)
    )

    lower_lows = sum(
        recent[i]["low"]
        < recent[i - 1]["low"]
        for i in range(1, 5)
    )

    first_close = recent[0]["close"]
    last_close = recent[-1]["close"]

    recent_change = pct(
        last_close,
        first_close,
    )

    recent_low = min(
        c["low"]
        for c in recent
    )

    recovery_from_low = pct(
        last_close,
        recent_low,
    )

    if (
        bearish >= 3
        and lower_lows >= 2
        and recent_change < 0
    ):
        structure = "BEARISH_STRUCTURE"

    elif (
        bullish >= 3
        and recent_change > 0
    ):
        structure = "BULLISH_RECOVERY"

    else:
        structure = "MIXED_STRUCTURE"

    return {
        "structure": structure,
        "bearish": bearish,
        "bullish": bullish,
        "lower_highs": lower_highs,
        "lower_lows": lower_lows,
        "recent_change": recent_change,
        "recovery_from_low": recovery_from_low,
    }


def post_exit_candles(
    candles,
    exit_time,
    next_entry,
):
    return [
        c
        for c in candles
        if (
            c["time"] >= exit_time
            and c["time"].date()
                == exit_time.date()
            and (
                next_entry is None
                or c["time"] < next_entry
            )
        )
    ]


def forward_window(
    post,
    minutes,
):
    """
    First 1, 2, or 3 completed candles
    after exit timestamp.
    """

    count = minutes // 5
    return post[:count]


def forward_measure(window, reference):
    if not window or reference is None:
        return None

    return {
        "close_move": pct(
            window[-1]["close"],
            reference,
        ),
        "down_mfe": max(
            -pct(c["low"], reference)
            for c in window
        ),
        "up_mae": max(
            pct(c["high"], reference)
            for c in window
        ),
    }


def summarize(records, key, title):
    groups = defaultdict(list)

    for record in records:
        groups[record[key]].append(record)

    print()
    print(title)

    for label, group in sorted(groups.items()):
        winners = sum(
            r["net"] > 0
            for r in group
        )

        losers = sum(
            r["net"] < 0
            for r in group
        )

        total_net = sum(
            r["net"]
            for r in group
        )

        print(
            f"{label:28s} "
            f"N={len(group):2d} "
            f"W={winners:2d} "
            f"L={losers:2d} "
            f"NET={total_net:+.6f}%"
        )


def audit_line(record):
    parts = [
        record["dataset"],
        str(record["entry"]),
        f'EXIT={record["exit"]}',
        f'NET={record["net"]:+.6f}%',
        f'STRUCTURE={record["structure"]}',
        f'BEAR={record["bearish"]}',
        f'BULL={record["bullish"]}',
        f'LH={record["lower_highs"]}',
        f'LL={record["lower_lows"]}',
        f'CHANGE={fmt(record["recent_change"])}',
        f'RECOVERY={fmt(record["recovery_from_low"])}',
    ]

    for minutes in (5, 10, 15):
        measure = record[f"f{minutes}"]

        if measure is None:
            parts.append(
                f'F{minutes}=NA'
            )
        else:
            parts.append(
                f'F{minutes}_CLOSE='
                f'{fmt(measure["close_move"])}'
            )

            parts.append(
                f'F{minutes}_DOWN='
                f'{fmt(measure["down_mfe"])}'
            )

            parts.append(
                f'F{minutes}_UP='
                f'{fmt(measure["up_mae"])}'
            )

    return " ".join(parts)


def report(name, records, details=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "structure",
        "PRE-EXIT CANDLE STRUCTURE",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-49")
    print(
        "EXIT-CANDLE STRUCTURE "
        "AND EARLY CONTINUATION AUDIT"
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
            key=lambda t: parse_time(
                t["entry_time"]
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

            structure = structure_before_exit(
                candles,
                exit_time,
            )

            if structure is None:
                continue

            exit_candle = next(
                (
                    c
                    for c in candles
                    if c["time"] == exit_time
                ),
                None,
            )

            reference = (
                exit_candle["open"]
                if exit_candle
                else None
            )

            post = post_exit_candles(
                candles,
                exit_time,
                next_entry,
            )

            record = {
                "dataset": name,
                "entry": entry,
                "exit": exit_time,
                "net": float(
                    trade["net_pnl_pct"]
                ),
                **structure,
            }

            for minutes in (5, 10, 15):
                window = forward_window(
                    post,
                    minutes,
                )

                record[f"f{minutes}"] = (
                    forward_measure(
                        window,
                        reference,
                    )
                )

            records.append(record)

        assert len(records) == expected_count, (
            f"{name}: missing records"
        )

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
        "Pre-exit structure excludes the "
        "exit-timestamp candle."
    )
    print(
        "Forward windows begin at the "
        "exit-timestamp candle."
    )
    print(
        "The exit-candle open is a reference, "
        "not necessarily the actual fill."
    )
    print(
        "Forward highs/lows are hindsight "
        "and have unknown intrabar order."
    )
    print(
        "The structure labels are descriptive "
        "and are not approved trading rules."
    )
    print(
        "No filters approved. "
        "No file writes or V18 changes."
    )

    print("STEP 59F-5H-43K-49: PASS")


if __name__ == "__main__":
    main()
