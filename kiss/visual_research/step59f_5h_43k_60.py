
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-60

CONTINUOUS HISTORICAL CONTEXT AUDIT
NVDA SHORT 5m

READ-ONLY RESEARCH.
NO PRODUCTION CHANGES.
V18 UNCHANGED.

Purpose:
  Re-evaluate the 31 V_PROFIT exits from Step 59
  using completed historical candles across
  trading sessions.

Keep unchanged:
  - Six bearish evidence votes
  - Classification thresholds
  - Original recorded exit-price reference
  - 5/10/15-minute evaluation horizons
  - 0.02% hypothetical exit slippage
  - 0.50% adverse threshold

Important:
  - Historical candles must precede exit time.
  - Exit candle final OHLC is excluded.
  - Previous-session candles are allowed.
  - Future candles evaluate outcomes only.
  - No stop fills are simulated.
  - No sequential strategy replay.
"""

import sys
import math
from pathlib import Path
from collections import Counter
from datetime import timedelta

LAB = Path("kiss/visual_research")
sys.path.insert(0, str(LAB.resolve()))

import step59f_5h_43k_53 as step53
import step59f_5h_43k_54 as step54
import step59f_5h_43k_59 as step59


EXPECTED_TRADES = 36
EXPECTED_NET = 8.984294
EXPECTED_V_PROFIT = 31
EXPECTED_CANDIDATES = 16

DELAYS = (5, 10, 15)


def dt(value):
    return step59.dt(value)


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def average(values):
    if not values:
        return None
    return sum(values) / len(values)


def classify_with_continuous_history(
    candles,
    exit_time,
):
    """
    Use historical regular-session candles,
    including previous sessions.

    Strict cutoff:
        candle timestamp < exit timestamp

    The original exit candle is excluded.
    """

    history = [
        candle
        for candle in candles
        if dt(candle["time"]) < exit_time
    ]

    decision = step59.classify(history)

    if decision["score"] is not None:
        assert (
            decision["last_known"] < exit_time
        ), "Look-ahead detected"

        assert (
            decision["history_count"] >= 21
        ), "Insufficient historical context"

    return decision


def old_same_session_classification(
    candles,
    exit_time,
):
    history = [
        candle
        for candle in candles
        if (
            dt(candle["time"]) < exit_time
            and dt(candle["time"]).date()
            == exit_time.date()
        )
    ]

    decision = step59.classify(history)

    if decision["score"] is not None:
        all_history = [
            candle
            for candle in candles
            if dt(candle["time"]) < exit_time
        ]

        closes = [
            float(candle["close"])
            for candle in all_history
        ]

        decision["rsi14"] = step59.rsi(
            closes
        )

    return decision


def summarize(title, items):
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)

    print(f"CASES={len(items)}")

    old_counts = Counter(
        item["old"]["signal"]
        for item in items
    )

    new_counts = Counter(
        item["new"]["signal"]
        for item in items
    )

    print()
    print("OLD_CLASSIFICATION")

    for name, count in sorted(
        old_counts.items()
    ):
        print(f"  {name}={count}")

    print()
    print("NEW_CLASSIFICATION")

    for name, count in sorted(
        new_counts.items()
    ):
        print(f"  {name}={count}")

    recovered = [
        item
        for item in items
        if (
            item["old"]["signal"]
            == "INSUFFICIENT_HISTORY"
            and item["new"]["signal"]
            != "INSUFFICIENT_HISTORY"
        )
    ]

    print()
    print(
        f"RECOVERED_EARLY_EXITS={len(recovered)}"
    )

    for signal in (
        "BEARISH_CONTINUATION",
        "MIXED",
        "REVERSAL_WARNING",
        "INSUFFICIENT_HISTORY",
    ):
        group = [
            item
            for item in items
            if item["new"]["signal"] == signal
        ]

        print()
        print(
            f"SIGNAL={signal} CASES={len(group)}"
        )

        if not group:
            continue

        for delay in DELAYS:
            results = [
                item["future"][delay]
                for item in group
            ]

            complete = [
                result
                for result in results
                if "incremental" in result
            ]

            values = [
                result["incremental"]
                for result in complete
            ]

            improved = sum(
                value > 0
                for value in values
            )

            worsened = sum(
                value < 0
                for value in values
            )

            touches = sum(
                result["status"] == "STOP_TOUCHED"
                for result in results
            )

            print(
                f"  {delay}m "
                f"N={len(complete)} "
                f"AVG={fmt(average(values))} "
                f"IMPROVED={improved} "
                f"WORSENED={worsened} "
                f"STOP_TOUCH={touches} "
                f"UNAVAILABLE="
                f"{len(results) - len(complete)}"
            )


def main():
    print("AIMn — STEP 59F-5H-43K-60")
    print("CONTINUOUS HISTORICAL CONTEXT AUDIT")
    print("NVDA SHORT 5m")
    print("READ-ONLY RESEARCH")
    print()
    print(
        "HISTORY=PREVIOUS_REGULAR_SESSIONS_ALLOWED"
    )
    print(
        "CAUSAL_CUTOFF=STRICTLY_BEFORE_EXIT_TIMESTAMP"
    )
    print(
        "EXIT_CANDLE_FINAL_OHLC=EXCLUDED"
    )
    print(
        "SIX_VOTES=UNCHANGED_FROM_STEP59"
    )
    print(
        "CLASSIFICATION_THRESHOLDS=UNCHANGED"
    )

    all_items = []

    total_trades = 0
    total_net = 0.0
    total_v_profit = 0

    for dataset, config in step54.DATASETS.items():

        replay, records = step54.load_dataset(
            dataset,
            config,
        )

        total_trades += replay["trade_count"]
        total_net += replay["net_pnl_pct"]

        candles = sorted(
            step53.regular_candles(
                step53.load_rows(config["path"])
            ),
            key=lambda candle: dt(
                candle["time"]
            ),
        )

        candle_map = {
            dt(candle["time"]): candle
            for candle in candles
        }

        assert (
            len(candle_map) == len(candles)
        ), "Duplicate candle timestamps"

        trades = sorted(
            replay["trades"],
            key=lambda trade: dt(
                trade["entry_time"]
            ),
        )

        records_by_exit = {
            dt(record["exit"]): record
            for record in records
        }

        dataset_items = []

        for index, trade in enumerate(trades):

            if (
                trade.get("exit_reason")
                != "V_PROFIT"
            ):
                continue

            total_v_profit += 1

            exit_time = dt(
                trade["exit_time"]
            )

            exit_price = float(
                trade["exit_price"]
            )

            assert math.isfinite(exit_price)
            assert exit_price > 0

            assert (
                exit_time in records_by_exit
            ), "Missing classification record"

            record = records_by_exit[
                exit_time
            ]

            old_decision = (
                old_same_session_classification(
                    candles,
                    exit_time,
                )
            )

            new_decision = (
                classify_with_continuous_history(
                    candles,
                    exit_time,
                )
            )

            later_entries = [
                dt(other["entry_time"])
                for j, other in enumerate(trades)
                if (
                    j != index
                    and dt(other["entry_time"])
                    >= exit_time
                )
            ]

            next_entry = (
                min(later_entries)
                if later_entries
                else None
            )

            future = {
                delay: step59.evaluate_future(
                    exit_time,
                    exit_price,
                    next_entry,
                    candle_map,
                    delay,
                )
                for delay in DELAYS
            }

            old_candidate = (
                record["two_bar_group"]
                == "TWO_BAR_DOWN"
                and record["structure_group"]
                == "BEARISH_INTACT"
            )

            item = {
                "dataset": dataset,
                "exit": exit_time,
                "entry": dt(
                    trade["entry_time"]
                ),
                "old": old_decision,
                "new": new_decision,
                "future": future,
                "old_candidate": old_candidate,
                "original_net": float(
                    trade["net_pnl_pct"]
                ),
            }

            dataset_items.append(item)

        assert (
            len(dataset_items)
            == config["v_profit"]
        ), "Baseline V_PROFIT mismatch"

        summarize(
            dataset,
            dataset_items,
        )

        all_items.extend(
            dataset_items
        )

    assert (
        total_trades == EXPECTED_TRADES
    ), "Baseline trade count changed"

    assert (
        abs(total_net - EXPECTED_NET)
        < 0.000002
    ), "Baseline net changed"

    assert (
        total_v_profit
        == EXPECTED_V_PROFIT
    ), "V_PROFIT count changed"

    assert (
        sum(
            item["old_candidate"]
            for item in all_items
        ) == EXPECTED_CANDIDATES
    ), "Candidate count changed"

    summarize(
        "COMBINED",
        all_items,
    )

    print()
    print("=" * 96)
    print("CLASSIFICATION TRANSITIONS")
    print("=" * 96)

    transitions = Counter(
        (
            item["old"]["signal"],
            item["new"]["signal"],
        )
        for item in all_items
    )

    for (old, new), count in sorted(
        transitions.items()
    ):
        print(
            f"{old} -> {new}: {count}"
        )

    print()
    print("=" * 96)
    print("TRADE-BY-TRADE AUDIT")
    print("=" * 96)

    for item in all_items:

        decision = item["new"]

        print()
        print(
            f'{item["dataset"]} '
            f'EXIT={item["exit"]} '
            f'OLD={item["old"]["signal"]} '
            f'NEW={decision["signal"]} '
            f'SCORE={decision["score"]} '
            f'OLD_CANDIDATE={item["old_candidate"]} '
            f'ORIGINAL_NET='
            f'{fmt(item["original_net"])}'
        )

        if decision["score"] is not None:

            print(
                f'  LAST_KNOWN='
                f'{decision["last_known"]} '
                f'MOMENTUM_1='
                f'{fmt(decision["momentum_1"])} '
                f'MOMENTUM_3='
                f'{fmt(decision["momentum_3"])} '
                f'MOMENTUM_5='
                f'{fmt(decision["momentum_5"])} '
                f'RSI14='
                f'{decision["rsi14"]:.2f}'
            )

            print(
                "  VOTES="
                + ",".join(
                    name
                    for name, active
                    in decision["votes"].items()
                    if active
                )
            )

        for delay in DELAYS:

            result = item["future"][delay]

            print(
                f'  {delay}m '
                f'STATUS={result["status"]} '
                f'INCREMENTAL='
                f'{fmt(result.get("incremental"))} '
                f'ADVERSE='
                f'{fmt(result.get("adverse"))}'
            )

    print()
    print("=" * 96)
    print("BASELINE INTEGRITY")
    print("=" * 96)

    print(f"TRADES={total_trades}")
    print(
        f"NET_PNL={total_net:+.6f}%"
    )
    print(
        f"V_PROFIT={total_v_profit}"
    )

    print(
        "OLD_CANDIDATES="
        + str(
            sum(
                item["old_candidate"]
                for item in all_items
            )
        )
    )

    print()
    print("IMPORTANT LIMITATIONS")
    print(
        "Previous-session historical candles are "
        "used only when timestamp < exit time."
    )
    print(
        "Exit candle final OHLC is excluded."
    )
    print(
        "Same six votes and thresholds as Step59."
    )
    print(
        "The classifier is exploratory, not approved."
    )
    print(
        "RSI14 is descriptive, not a trading rule."
    )
    print(
        "Future candles are evaluation-only."
    )
    print(
        "Stop touches are not executed stop fills."
    )
    print(
        "No sequential strategy replay."
    )
    print("No files written.")
    print("V18 unchanged.")
    print(
        "STEP 59F-5H-43K-60: PASS"
    )


if __name__ == "__main__":
    main()
