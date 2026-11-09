
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-56

EXECUTION TIMING AND PROTECTIVE EXIT AUDIT

NVDA SHORT — 5-minute candles

READ-ONLY RESEARCH

Purpose:
1. Audit candle timestamps and continuity.
2. Inspect original exit versus next candle.
3. Test hypothetical 5/10/15-minute delays.
4. Detect adverse excursions of 0.50%.
5. Detect overlap with the next trade.
6. Compare research and validation.

IMPORTANT:
This is NOT a live-execution simulation.

A candle high can establish that a
hypothetical stop level was touched,
but OHLC data cannot establish exact
intrabar execution order or fill price.

No files written.
No trading logic changed.
V18 unchanged.
"""

import sys
from pathlib import Path
from collections import defaultdict
from datetime import timedelta

LAB = Path("kiss/visual_research")
sys.path.insert(0, str(LAB.resolve()))

import step59f_5h_43k_53 as step53
import step59f_5h_43k_54 as step54


BAR_MINUTES = 5
DELAYS = (5, 10, 15)

ADVERSE_STOP_PCT = 0.50
EXTRA_SLIPPAGE_PCT = 0.02

EXPECTED_TRADES = 36
EXPECTED_NET = 8.984294
EXPECTED_V_PROFIT = 31
EXPECTED_CANDIDATES = 16

TOLERANCE = 0.000002


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def candidate(record):
    return (
        record["two_bar_group"] == "TWO_BAR_DOWN"
        and record["structure_group"] == "BEARISH_INTACT"
    )


def timestamp_audit(candles):
    """
    Check chronological order, duplicate times,
    regular-session grid and missing intervals.

    This cannot establish whether a timestamp
    denotes the candle OPEN or CLOSE.
    """

    times = [c["time"] for c in candles]

    assert len(times) == len(set(times)), (
        "Duplicate regular-session timestamps"
    )

    assert times == sorted(times), (
        "Candles not chronologically ordered"
    )

    off_grid = []
    gaps = []
    first_by_day = {}
    last_by_day = {}

    previous = None

    for candle in candles:
        timestamp = candle["time"]
        day = timestamp.date()

        if (
            timestamp.minute % BAR_MINUTES != 0
            or timestamp.second != 0
            or timestamp.microsecond != 0
        ):
            off_grid.append(timestamp)

        first_by_day.setdefault(day, timestamp)
        last_by_day[day] = timestamp

        if (
            previous is not None
            and previous.date() == day
        ):
            gap = (
                timestamp - previous
            ).total_seconds() / 60.0

            if abs(gap - BAR_MINUTES) > 0.01:
                gaps.append(
                    (previous, timestamp, gap)
                )

        previous = timestamp

    print()
    print("TIMESTAMP AUDIT")
    print("-" * 90)
    print(f"REGULAR_CANDLES={len(candles)}")
    print(f"SESSIONS={len(first_by_day)}")
    print(f"OFF_GRID={len(off_grid)}")
    print(f"INTRADAY_GAPS={len(gaps)}")

    first_counts = defaultdict(int)
    last_counts = defaultdict(int)

    for value in first_by_day.values():
        first_counts[value.strftime("%H:%M")] += 1

    for value in last_by_day.values():
        last_counts[value.strftime("%H:%M")] += 1

    print("FIRST_CANDLE_TIMES:")
    for key, count in sorted(first_counts.items()):
        print(f"  {key}: {count}")

    print("LAST_CANDLE_TIMES:")
    for key, count in sorted(last_counts.items()):
        print(f"  {key}: {count}")

    for item in off_grid[:10]:
        print(f"OFF_GRID_EXAMPLE={item}")

    for start, end, minutes in gaps[:10]:
        print(
            f"GAP={start} -> {end} "
            f"MINUTES={minutes:.1f}"
        )

    print(
        "TIMESTAMP_CONVENTION="
        "UNVERIFIED_FROM_OHLC_ALONE"
    )

    return {
        "off_grid": len(off_grid),
        "gaps": len(gaps),
    }


def subsequent_candles(
    candles,
    exit_time,
    next_entry,
):
    """
    Only candles strictly after recorded exit.
    Same date and continuous five-minute grid.

    Do not include any candle whose timestamp
    reaches or passes the next entry.

    This is a conservative research boundary,
    not proof of real execution timing.
    """

    selected = [
        candle
        for candle in candles
        if (
            candle["time"] > exit_time
            and candle["time"].date()
                == exit_time.date()
            and (
                next_entry is None
                or candle["time"] < next_entry
            )
        )
    ]

    selected.sort(key=lambda c: c["time"])

    continuous = []
    previous_time = None

    for candle in selected:
        if previous_time is not None:
            gap = (
                candle["time"] - previous_time
            ).total_seconds() / 60.0

            if abs(gap - BAR_MINUTES) > 0.01:
                break

        continuous.append(candle)
        previous_time = candle["time"]

        if len(continuous) >= 4:
            break

    return continuous


def assess_delay(
    candles,
    exit_time,
    next_entry,
    delay_minutes,
):
    """
    Reference: first subsequent candle OPEN.
    Delayed exit: later candle OPEN.

    For a SHORT, higher price is adverse.

    If the stop level is touched before
    the delayed exit, report STOP_TOUCHED.
    Do NOT invent a stop execution price.

    If the later candle is unavailable,
    report INSUFFICIENT_DATA.

    Exact OHLC timestamps and real fills
    remain unverified.
    """

    bars = delay_minutes // BAR_MINUTES

    required_time = (
        exit_time
        + timedelta(
            minutes=(bars + 1) * BAR_MINUTES
        )
    )

    if (
        next_entry is not None
        and required_time >= next_entry
    ):
        return {
            "status": "NEXT_ENTRY_CONFLICT",
            "net_proxy": None,
            "adverse": None,
            "stop_touched": False,
        }

    future = subsequent_candles(
        candles,
        exit_time,
        next_entry,
    )

    if len(future) <= bars:
        return {
            "status": "INSUFFICIENT_DATA",
            "net_proxy": None,
            "adverse": None,
            "stop_touched": False,
        }

    reference_time = future[0]["time"]
    delayed_time = future[bars]["time"]

    expected_gap = bars * BAR_MINUTES

    actual_gap = (
        delayed_time - reference_time
    ).total_seconds() / 60.0

    if abs(actual_gap - expected_gap) > 0.01:
        return {
            "status": "TIMESTAMP_GAP",
            "net_proxy": None,
            "adverse": None,
            "stop_touched": False,
        }

    reference_price = future[0]["open"]
    delayed_price = future[bars]["open"]

    if reference_price <= 0:
        return {
            "status": "INVALID_PRICE",
            "net_proxy": None,
            "adverse": None,
            "stop_touched": False,
        }

    window = future[:bars]

    highest = max(c["high"] for c in window)
    lowest = min(c["low"] for c in window)

    adverse = max(
        0.0,
        100.0 * (
            highest - reference_price
        ) / reference_price,
    )

    favorable = max(
        0.0,
        100.0 * (
            reference_price - lowest
        ) / reference_price,
    )

    stop_price = (
        reference_price
        * (1.0 + ADVERSE_STOP_PCT / 100.0)
    )

    stop_touched = any(
        candle["high"] >= stop_price
        for candle in window
    )

    gross = (
        100.0
        * (reference_price - delayed_price)
        / reference_price
    )

    net_proxy = gross - EXTRA_SLIPPAGE_PCT

    return {
        "status": (
            "STOP_TOUCHED"
            if stop_touched
            else "NO_STOP_TOUCH"
        ),
        "net_proxy": net_proxy,
        "gross": gross,
        "adverse": adverse,
        "favorable": favorable,
        "stop_touched": stop_touched,
        "reference_time": reference_time,
        "delayed_time": delayed_time,
    }


def report_group(title, records):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)
    print(f"CASES={len(records)}")

    for delay in DELAYS:
        statuses = defaultdict(int)
        safe_values = []
        all_values = []
        adverse_values = []

        for record in records:
            result = record["delays"][delay]
            statuses[result["status"]] += 1

            if result["net_proxy"] is not None:
                all_values.append(
                    result["net_proxy"]
                )

                adverse_values.append(
                    result["adverse"]
                )

                if not result["stop_touched"]:
                    safe_values.append(
                        result["net_proxy"]
                    )

        print()
        print(f"DELAY={delay} MIN")

        for status, count in sorted(
            statuses.items()
        ):
            print(f"  {status}={count}")

        print(
            f"  COMPLETE_PRICE_PATHS="
            f"{len(all_values)}"
        )

        print(
            f"  NO_STOP_TOUCH_PATHS="
            f"{len(safe_values)}"
        )

        if all_values:
            print(
                "  AVG_UNPROTECTED_NET_PROXY="
                + fmt(
                    sum(all_values)
                    / len(all_values)
                )
            )

            print(
                "  MAX_ADVERSE="
                + fmt(max(adverse_values))
            )

        if safe_values:
            print(
                "  AVG_NO_STOP_TOUCH_NET_PROXY="
                + fmt(
                    sum(safe_values)
                    / len(safe_values)
                )
            )

        print(
            "  NOTE: Stop-touched paths have "
            "no simulated stop fill."
        )


def report_trade_details(records):
    print()
    print("=" * 100)
    print("CANDIDATE TRADE DETAILS")
    print("=" * 100)

    for record in records:
        if not record["candidate"]:
            continue

        print()
        print(
            f'{record["dataset"]} '
            f'EXIT={record["exit"]} '
            f'NEXT_ENTRY={record["next_entry"]} '
            f'TWO_BAR={fmt(record["two_bar"])} '
            f'ORIGINAL_NET={fmt(record["original_net"])}'
        )

        for delay in DELAYS:
            result = record["delays"][delay]

            print(
                f"  {delay}m "
                f'STATUS={result["status"]} '
                f'NET_PROXY={fmt(result["net_proxy"])} '
                f'ADVERSE={fmt(result["adverse"])}'
            )


def main():
    print("AIMn — STEP 59F-5H-43K-56")
    print(
        "EXECUTION TIMING AND "
        "PROTECTIVE EXIT AUDIT"
    )
    print("NVDA SHORT 5m")
    print("READ-ONLY RESEARCH")

    print()
    print(
        f"ADVERSE_STOP_THRESHOLD="
        f"{ADVERSE_STOP_PCT:.2f}%"
    )

    print(
        f"EXTRA_EXIT_SLIPPAGE="
        f"{EXTRA_SLIPPAGE_PCT:.2f}%"
    )

    all_records = []
    total_trades = 0
    total_net = 0.0

    for name, config in step54.DATASETS.items():
        print()
        print("#" * 100)
        print(f"DATASET={name}")
        print("#" * 100)

        replay, original_records = (
            step54.load_dataset(
                name,
                config,
            )
        )

        total_trades += replay["trade_count"]
        total_net += replay["net_pnl_pct"]

        raw = step53.load_rows(
            config["path"]
        )

        candles = step53.regular_candles(
            raw
        )

        timestamp_audit(candles)

        trades = sorted(
            replay["trades"],
            key=lambda trade: step53.parse_time(
                trade["entry_time"]
            ),
        )

        next_entries = {}

        for index, trade in enumerate(trades):
            if trade.get("exit_reason") != "V_PROFIT":
                continue

            exit_time = step53.parse_time(
                trade["exit_time"]
            )

            next_entry = None

            if index + 1 < len(trades):
                next_entry = step53.parse_time(
                    trades[index + 1]["entry_time"]
                )

            next_entries[exit_time] = next_entry

        records = []

        for original in original_records:
            exit_time = original["exit"]
            next_entry = next_entries[exit_time]

            record = {
                "dataset": name,
                "exit": exit_time,
                "next_entry": next_entry,
                "candidate": candidate(original),
                "two_bar": original["two_bar"],
                "original_net": original["net"],
                "delays": {},
            }

            for delay in DELAYS:
                record["delays"][delay] = (
                    assess_delay(
                        candles,
                        exit_time,
                        next_entry,
                        delay,
                    )
                )

            records.append(record)

        assert len(records) == config["v_profit"]

        report_group(
            name + " — CANDIDATE",
            [
                r for r in records
                if r["candidate"]
            ],
        )

        report_group(
            name + " — CONTROL",
            [
                r for r in records
                if not r["candidate"]
            ],
        )

        all_records.extend(records)

    assert total_trades == EXPECTED_TRADES

    assert abs(
        total_net - EXPECTED_NET
    ) < TOLERANCE

    assert len(all_records) == EXPECTED_V_PROFIT

    candidates = [
        r for r in all_records
        if r["candidate"]
    ]

    controls = [
        r for r in all_records
        if not r["candidate"]
    ]

    assert (
        len(candidates) == EXPECTED_CANDIDATES
    )

    report_group(
        "COMBINED — CANDIDATE",
        candidates,
    )

    report_group(
        "COMBINED — CONTROL",
        controls,
    )

    report_trade_details(all_records)

    print()
    print("=" * 100)
    print("BASELINE INTEGRITY")
    print("=" * 100)

    print(f"TRADES={total_trades}")
    print(f"NET_PNL={total_net:+.6f}%")
    print(f"V_PROFIT={len(all_records)}")
    print(f"CANDIDATES={len(candidates)}")
    print(f"CONTROLS={len(controls)}")

    print()
    print("IMPORTANT LIMITATIONS")

    print(
        "Candle timestamp convention is "
        "not established by this audit."
    )

    print(
        "Stop touches are identified "
        "from candle highs only."
    )

    print(
        "No stop execution price "
        "or fill is assumed."
    )

    print(
        "Price proxies reference "
        "the first subsequent candle open."
    )

    print(
        "The exit-to-reference interval "
        "is not repriced."
    )

    print(
        "No complete sequential "
        "trade replay is performed."
    )

    print(
        "Trade conflicts and missing "
        "observations are not assumed safe."
    )

    print(
        "Research and validation are "
        "reported separately."
    )

    print(
        "No trading rule approved."
    )

    print(
        "No files written."
    )

    print(
        "V18 unchanged."
    )

    print()
    print("STEP 59F-5H-43K-56: PASS")


if __name__ == "__main__":
    main()
