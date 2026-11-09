
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-61
REVERSAL STRENGTH VERSUS BEARISH STRUCTURE AUDIT
NVDA SHORT 5m

READ-ONLY RESEARCH.
NO PRODUCTION CHANGES.
V18 UNCHANGED.

Measure the strength of the latest upward movement
relative to the preceding bearish movement.

Strictly use historical candles with timestamps
before the original exit timestamp.

No thresholds are optimized.
No trading decisions are changed.
No files are written.
"""

import sys
import math
from pathlib import Path
from collections import defaultdict
from datetime import timedelta

LAB = Path("kiss/visual_research")
sys.path.insert(0, str(LAB.resolve()))

import step59f_5h_43k_53 as step53
import step59f_5h_43k_54 as step54
import step59f_5h_43k_59 as step59

DELAYS = (5, 10, 15)

EXPECTED_TRADES = 36
EXPECTED_NET = 8.984294
EXPECTED_V_PROFIT = 31
EXPECTED_CANDIDATES = 16


def dt(value):
    return step59.dt(value)


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def avg(values):
    return (
        sum(values) / len(values)
        if values else None
    )


def pct(new, old):
    return 100.0 * (new / old - 1.0)


def reversal_features(history):
    """
    Input: all regular-session candles before exit.

    Only the most recent completed candles are
    used for price-structure measurements.
    """

    if len(history) < 21:
        return None

    recent = history[-21:]

    closes = [
        float(c["close"])
        for c in recent
    ]

    highs = [
        float(c["high"])
        for c in recent
    ]

    lows = [
        float(c["low"])
        for c in recent
    ]

    last_close = closes[-1]
    previous_close = closes[-2]

    one_bar = pct(
        last_close,
        previous_close,
    )

    three_bar = pct(
        last_close,
        closes[-4],
    )

    five_bar = pct(
        last_close,
        closes[-6],
    )

    prior_five = pct(
        closes[-2],
        closes[-7],
    )

    # Magnitude of the earlier five-bar decline.
    bearish_decline = max(
        0.0,
        -prior_five,
    )

    upward_move = max(
        0.0,
        one_bar,
    )

    # Ratio is deliberately left undefined when
    # there was no preceding bearish decline.
    recovery_ratio = (
        upward_move / bearish_decline
        if bearish_decline > 0
        else None
    )

    # Compare recent short-term movement with
    # the movement immediately preceding it.
    recent_two = pct(
        closes[-1],
        closes[-3],
    )

    previous_two = pct(
        closes[-3],
        closes[-5],
    )

    acceleration = (
        recent_two - previous_two
    )

    # Prior 10-bar range, excluding latest bar.
    prior_high = max(highs[-11:-1])
    prior_low = min(lows[-11:-1])

    range_width = (
        prior_high - prior_low
    )

    range_position = (
        100.0 * (
            last_close - prior_low
        ) / range_width
        if range_width > 0
        else None
    )

    # Current close compared with the prior
    # five-bar high, excluding latest candle.
    previous_five_high = max(
        highs[-6:-1]
    )

    distance_to_high = pct(
        last_close,
        previous_five_high,
    )

    # The original six-vote score is retained
    # only as a reference for comparison.
    original = step59.classify(
        history
    )

    return {
        "one_bar": one_bar,
        "three_bar": three_bar,
        "five_bar": five_bar,
        "prior_five": prior_five,
        "bearish_decline": bearish_decline,
        "upward_move": upward_move,
        "recovery_ratio": recovery_ratio,
        "acceleration": acceleration,
        "range_position": range_position,
        "distance_to_high": distance_to_high,
        "six_vote_score": original["score"],
        "six_vote_signal": original["signal"],
        "last_known": dt(
            history[-1]["time"]
        ),
    }


def describe(title, items):
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)
    print(f"CASES={len(items)}")

    for feature in (
        "one_bar",
        "three_bar",
        "five_bar",
        "prior_five",
        "bearish_decline",
        "recovery_ratio",
        "acceleration",
        "range_position",
        "distance_to_high",
    ):
        values = [
            item["features"][feature]
            for item in items
            if item["features"][feature]
            is not None
        ]

        print(
            f"{feature.upper()} "
            f"N={len(values)} "
            f"AVG={avg(values)}"
        )

    print()
    print("FUTURE OUTCOMES")

    for delay in DELAYS:
        results = [
            item["future"][delay]
            for item in items
        ]

        valid = [
            r for r in results
            if "incremental" in r
        ]

        values = [
            r["incremental"]
            for r in valid
        ]

        print(
            f"{delay}m "
            f"N={len(valid)} "
            f"AVG={fmt(avg(values))} "
            f"IMPROVED="
            f"{sum(v > 0 for v in values)} "
            f"WORSENED="
            f"{sum(v < 0 for v in values)} "
            f"STOP_TOUCH="
            f"{sum(r['status'] == 'STOP_TOUCHED' for r in results)}"
        )


def compare_outcomes(title, items):
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)

    for feature in (
        "one_bar",
        "recovery_ratio",
        "acceleration",
        "range_position",
        "distance_to_high",
    ):
        print()
        print(f"FEATURE={feature}")

        for delay in DELAYS:
            improved = []
            worsened = []

            for item in items:
                value = item["features"][feature]
                outcome = item["future"][delay]

                if (
                    value is None
                    or "incremental" not in outcome
                ):
                    continue

                if outcome["incremental"] > 0:
                    improved.append(value)
                elif outcome["incremental"] < 0:
                    worsened.append(value)

            print(
                f"  {delay}m "
                f"IMPROVED_N={len(improved)} "
                f"IMPROVED_FEATURE_AVG={avg(improved)} "
                f"WORSENED_N={len(worsened)} "
                f"WORSENED_FEATURE_AVG={avg(worsened)}"
            )


def main():
    print("AIMn — STEP 59F-5H-43K-61")
    print(
        "REVERSAL STRENGTH VERSUS BEARISH STRUCTURE AUDIT"
    )
    print("NVDA SHORT 5m — READ-ONLY")
    print(
        "CAUSAL_CUTOFF=STRICTLY_BEFORE_EXIT_TIMESTAMP"
    )
    print("EXIT_CANDLE_FINAL_OHLC=EXCLUDED")
    print("PREVIOUS_SESSIONS_ALLOWED")
    print("NO_OPTIMIZATION")
    print()

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
            key=lambda c: dt(c["time"]),
        )

        candle_map = {
            dt(c["time"]): c
            for c in candles
        }

        assert (
            len(candle_map) == len(candles)
        ), "Duplicate candle timestamps"

        trades = sorted(
            replay["trades"],
            key=lambda t: dt(
                t["entry_time"]
            ),
        )

        records_by_exit = {
            dt(r["exit"]): r
            for r in records
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
            )

            history = [
                candle
                for candle in candles
                if dt(candle["time"]) < exit_time
            ]

            features = reversal_features(
                history
            )

            assert (
                features is not None
            ), "Insufficient continuous history"

            assert (
                features["last_known"]
                < exit_time
            ), "Look-ahead detected"

            later_entries = [
                dt(t["entry_time"])
                for j, t in enumerate(trades)
                if (
                    j != index
                    and dt(t["entry_time"])
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

            record = records_by_exit[
                exit_time
            ]

            old_candidate = (
                record["two_bar_group"]
                == "TWO_BAR_DOWN"
                and record["structure_group"]
                == "BEARISH_INTACT"
            )

            dataset_items.append({
                "dataset": dataset,
                "exit": exit_time,
                "original_net": float(
                    trade["net_pnl_pct"]
                ),
                "features": features,
                "future": future,
                "old_candidate": old_candidate,
            })

        assert (
            len(dataset_items)
            == config["v_profit"]
        ), "Baseline mismatch"

        describe(
            dataset,
            dataset_items,
        )

        compare_outcomes(
            dataset + " FEATURE COMPARISON",
            dataset_items,
        )

        all_items.extend(
            dataset_items
        )

    assert total_trades == EXPECTED_TRADES
    assert (
        abs(total_net - EXPECTED_NET)
        < 0.000002
    )
    assert total_v_profit == EXPECTED_V_PROFIT

    assert (
        sum(
            item["old_candidate"]
            for item in all_items
        ) == EXPECTED_CANDIDATES
    )

    describe(
        "COMBINED",
        all_items,
    )

    print()
    print("=" * 96)
    print("TRADE-BY-TRADE FEATURE AUDIT")
    print("=" * 96)

    for item in all_items:
        f = item["features"]

        print()
        print(
            f'{item["dataset"]} '
            f'EXIT={item["exit"]} '
            f'ORIGINAL_NET={fmt(item["original_net"])} '
            f'SCORE={f["six_vote_score"]} '
            f'OLD_CANDIDATE={item["old_candidate"]}'
        )

        print(
            f'  ONE_BAR={fmt(f["one_bar"])} '
            f'THREE_BAR={fmt(f["three_bar"])} '
            f'FIVE_BAR={fmt(f["five_bar"])} '
            f'PRIOR_FIVE={fmt(f["prior_five"])}'
        )

        print(
            f'  RECOVERY_RATIO={f["recovery_ratio"]} '
            f'ACCELERATION={fmt(f["acceleration"])} '
            f'RANGE_POSITION={f["range_position"]} '
            f'DISTANCE_TO_HIGH='
            f'{fmt(f["distance_to_high"])} '
            f'LAST_KNOWN={f["last_known"]}'
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
        "Only historical candles before exit "
        "are used for features."
    )
    print(
        "Previous-session candles may contribute."
    )
    print(
        "The exit candle final OHLC is excluded."
    )
    print(
        "Feature comparisons are observational."
    )
    print(
        "Recovery ratio is undefined when the "
        "preceding decline is zero."
    )
    print(
        "Future outcomes are hypothetical."
    )
    print(
        "No stop fills or sequential replay."
    )
    print("No files written.")
    print("V18 unchanged.")
    print(
        "STEP 59F-5H-43K-61: PASS"
    )


if __name__ == "__main__":
    main()
