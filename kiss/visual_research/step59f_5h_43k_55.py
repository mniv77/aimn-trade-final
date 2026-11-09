
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-55

CONTROLLED EXIT-DELAY COUNTERFACTUAL AUDIT

NVDA SHORT — 5-minute candles

READ-ONLY RESEARCH

Compare original V_PROFIT exits against
hypothetical 5, 10 and 15 minute delays.

Candidate:
    TWO_BAR_DOWN + BEARISH_INTACT

Controls:
    All other V_PROFIT exits.

IMPORTANT:
This is an observational counterfactual,
NOT an executable backtest.

The original exit execution price is not
reconstructed. The first candle strictly
after the recorded exit is used as a
common reference price.

Costs and risk are estimated separately.
No production code is modified.
V18 remains unchanged.
"""

import sys
from pathlib import Path
from collections import defaultdict

LAB = Path("kiss/visual_research")
sys.path.insert(0, str(LAB.resolve()))

import step59f_5h_43k_54 as step54
import step59f_5h_43k_53 as step53


DELAYS = (1, 2, 3)

# Five-minute candles.
BAR_MINUTES = 5

# Additional hypothetical execution costs.
# Round-trip costs already present in the
# original replay must not be counted again.
EXTRA_EXIT_SLIPPAGE_PCT = 0.02

# Illustrative adverse-excursion threshold.
# This is an audit threshold, not a stop order.
ADVERSE_LIMIT_PCT = 0.50

EXPECTED_TRADES = 36
EXPECTED_NET = 8.984294
EXPECTED_V_PROFIT = 31
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


def future_candles(candles, exit_time, next_entry):
    """
    Strictly later candle timestamps.
    Same session only.
    Never cross into the next trade.

    Requires a continuous five-minute
    timestamp sequence.
    """

    available = [
        c for c in candles
        if (
            c["time"] > exit_time
            and c["time"].date()
                == exit_time.date()
            and (
                next_entry is None
                or c["time"] < next_entry
            )
        )
    ]

    available.sort(key=lambda c: c["time"])

    continuous = []
    previous_time = None

    for candle in available:
        if previous_time is not None:
            gap = (
                candle["time"] - previous_time
            ).total_seconds() / 60.0

            if abs(gap - BAR_MINUTES) > 0.01:
                break

        continuous.append(candle)
        previous_time = candle["time"]

        if len(continuous) == max(DELAYS) + 1:
            break

    return continuous


def evaluate_delay(future, delay_bars):
    """
    Common reference:
        first subsequent candle OPEN.

    Delayed exit:
        OPEN of candle at delay_bars.

    Example:
        5 minutes = next candle OPEN.

    Uses the first delay_bars candles
    for adverse and favorable excursions.

    SHORT incremental price improvement:
        100 * (reference - delayed) / reference

    This is a proxy, not actual fill P&L.
    """

    if len(future) <= delay_bars:
        return None

    reference = future[0]["open"]
    delayed_price = future[delay_bars]["open"]

    if reference <= 0:
        return None

    window = future[:delay_bars]

    highest = max(c["high"] for c in window)
    lowest = min(c["low"] for c in window)

    gross_improvement = (
        100.0
        * (reference - delayed_price)
        / reference
    )

    net_incremental_proxy = (
        gross_improvement
        - EXTRA_EXIT_SLIPPAGE_PCT
    )

    adverse = (
        100.0
        * (highest - reference)
        / reference
    )

    favorable = (
        100.0
        * (reference - lowest)
        / reference
    )

    return {
        "gross": gross_improvement,
        "net": net_incremental_proxy,
        "adverse": max(0.0, adverse),
        "favorable": max(0.0, favorable),
        "adverse_breach": (
            adverse >= ADVERSE_LIMIT_PCT
        ),
    }


def summarize(records, delay):
    evaluated = [
        r for r in records
        if r["delays"][delay] is not None
    ]

    missing = len(records) - len(evaluated)

    print()
    print(
        f"DELAY={delay * BAR_MINUTES} MIN "
        f"ELIGIBLE={len(records)} "
        f"EVALUATED={len(evaluated)} "
        f"MISSING={missing}"
    )

    if not evaluated:
        return

    values = [
        r["delays"][delay]
        for r in evaluated
    ]

    n = len(values)

    gross = sum(v["gross"] for v in values)
    net = sum(v["net"] for v in values)

    improved = sum(
        v["net"] > 0
        for v in values
    )

    worsened = sum(
        v["net"] < 0
        for v in values
    )

    adverse_breaches = sum(
        v["adverse_breach"]
        for v in values
    )

    worst = min(v["net"] for v in values)
    best = max(v["net"] for v in values)

    maximum_adverse = max(
        v["adverse"] for v in values
    )

    print(
        f"AVG_GROSS={fmt(gross / n)} "
        f"AVG_NET_PROXY={fmt(net / n)}"
    )

    print(
        f"SUM_INCREMENTAL_PROXY={fmt(net)} "
        f"IMPROVED={improved} "
        f"WORSENED={worsened}"
    )

    print(
        f"BEST={fmt(best)} "
        f"WORST={fmt(worst)} "
        f"MAX_ADVERSE={fmt(maximum_adverse)} "
        f"ADVERSE_BREACHES={adverse_breaches}"
    )

    print(
        "NOTE: SUM_INCREMENTAL_PROXY is "
        "not portfolio P&L."
    )


def report_group(title, records):
    print()
    print("=" * 105)
    print(title)
    print("=" * 105)

    print(f"CASES={len(records)}")

    for delay in DELAYS:
        summarize(records, delay)


def print_details(records):
    print()
    print("=" * 105)
    print("TRADE-BY-TRADE AUDIT")
    print("=" * 105)

    for record in records:
        print()
        print(
            f'{record["dataset"]} '
            f'EXIT={record["exit"]} '
            f'GROUP={record["group"]} '
            f'QUALITY={record["quality"]} '
            f'ORIGINAL_NET={fmt(record["original_net"])} '
            f'TWO_BAR={fmt(record["two_bar"])} '
            f'STRUCTURE={record["structure"]}'
        )

        for delay in DELAYS:
            value = record["delays"][delay]

            if value is None:
                print(
                    f"  {delay * BAR_MINUTES}m: "
                    "INSUFFICIENT_DATA"
                )
                continue

            print(
                f"  {delay * BAR_MINUTES}m: "
                f'GROSS={fmt(value["gross"])} '
                f'NET_PROXY={fmt(value["net"])} '
                f'ADVERSE={fmt(value["adverse"])} '
                f'FAVORABLE={fmt(value["favorable"])} '
                f'ADVERSE_BREACH={value["adverse_breach"]}'
            )


def main():
    print("AIMn — STEP 59F-5H-43K-55")
    print("CONTROLLED EXIT-DELAY COUNTERFACTUAL")
    print("NVDA SHORT 5m")
    print("READ-ONLY RESEARCH")

    print()
    print("CANDIDATE:")
    print("TWO_BAR_DOWN + BEARISH_INTACT")

    print()
    print("HYPOTHETICAL DELAYS: 5, 10, 15 MIN")
    print(
        "ADDITIONAL EXIT SLIPPAGE: "
        f"{EXTRA_EXIT_SLIPPAGE_PCT:.4f}%"
    )
    print(
        "ADVERSE EXCURSION THRESHOLD: "
        f"{ADVERSE_LIMIT_PCT:.4f}%"
    )

    all_records = []
    total_trades = 0
    total_net = 0.0

    for name, config in step54.DATASETS.items():
        result, original_records = (
            step54.load_dataset(name, config)
        )

        total_trades += result["trade_count"]
        total_net += result["net_pnl_pct"]

        rows = step53.load_rows(config["path"])
        candles = step53.regular_candles(rows)

        trades = sorted(
            result["trades"],
            key=lambda t: step53.parse_time(
                t["entry_time"]
            ),
        )

        next_entry_by_exit = {}

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

            next_entry_by_exit[exit_time] = next_entry

        records = []

        for original in original_records:
            exit_time = original["exit"]

            next_entry = next_entry_by_exit[
                exit_time
            ]

            future = future_candles(
                candles,
                exit_time,
                next_entry,
            )

            is_candidate = candidate(original)

            record = {
                "dataset": name,
                "exit": exit_time,
                "group": (
                    "CANDIDATE"
                    if is_candidate
                    else "CONTROL"
                ),
                "quality": original["quality"],
                "original_net": original["net"],
                "two_bar": original["two_bar"],
                "structure":
                    original["structure_group"],
                "delays": {
                    delay: evaluate_delay(
                        future,
                        delay,
                    )
                    for delay in DELAYS
                },
            }

            records.append(record)

        assert len(records) == config["v_profit"]

        report_group(
            name + " — CANDIDATE",
            [
                r for r in records
                if r["group"] == "CANDIDATE"
            ],
        )

        report_group(
            name + " — CONTROL",
            [
                r for r in records
                if r["group"] == "CONTROL"
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
        if r["group"] == "CANDIDATE"
    ]

    controls = [
        r for r in all_records
        if r["group"] == "CONTROL"
    ]

    assert len(candidates) == 16, (
        "Candidate count differs from Step 54"
    )

    assert len(controls) == 15, (
        "Control count differs from Step 54"
    )

    report_group(
        "COMBINED — CANDIDATE",
        candidates,
    )

    report_group(
        "COMBINED — CONTROL",
        controls,
    )

    print_details(all_records)

    print()
    print("=" * 105)
    print("BASELINE INTEGRITY")
    print("=" * 105)

    print(f"TRADES={total_trades}")
    print(f"NET_PNL={total_net:+.6f}%")
    print(f"V_PROFIT={len(all_records)}")
    print(f"CANDIDATES={len(candidates)}")
    print(f"CONTROLS={len(controls)}")

    print()
    print("METHODOLOGY LIMITATIONS")

    print(
        "Original exits are not repriced "
        "using actual fill prices."
    )

    print(
        "The first subsequent candle open "
        "is the common proxy reference."
    )

    print(
        "Delayed exits use later candle opens."
    )

    print(
        "Additional slippage is hypothetical; "
        "original replay costs are unchanged."
    )

    print(
        "Adverse threshold breaches are "
        "measured, not executed as stop orders."
    )

    print(
        "A breach may occur before a "
        "hypothetical delayed exit."
    )

    print(
        "Candle timestamp and actual "
        "execution conventions are unverified."
    )

    print(
        "Intrabar price ordering is unknown."
    )

    print(
        "Missing future candles are excluded, "
        "never assumed favorable."
    )

    print(
        "Delayed exits can affect later entries; "
        "the full trade sequence is not replayed."
    )

    print(
        "Candidate selection comes from "
        "previous research on these data."
    )

    print(
        "This is not out-of-sample proof "
        "of profitability."
    )

    print(
        "No live trading rule approved."
    )

    print(
        "No files written. V18 unchanged."
    )

    print()
    print("STEP 59F-5H-43K-55: PASS")


if __name__ == "__main__":
    main()
