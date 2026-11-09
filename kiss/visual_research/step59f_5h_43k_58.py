
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-58

RECORDED EXIT-TO-DELAYED EXIT REPRICING
NVDA SHORT 5m

READ-ONLY RESEARCH
No production changes. V18 unchanged.

For each V_PROFIT trade:
  - Start with the replay's recorded exit_price.
  - Compare with candle opens at exit +5/+10/+15 minutes.
  - Apply an additional 0.02% hypothetical exit
    slippage to the delayed SHORT cover.
  - Measure adverse highs relative to the
    recorded exit price.
  - Flag a 0.50% adverse threshold touch.
  - Flag unavailable bars and next-entry conflicts.
  - Keep research and validation separate.

Important:
  Recorded replay exit prices are not verified
  broker fills.

  An exit candle may contain movement occurring
  after the simulated original exit. OHLC alone
  cannot establish that intrabar sequence.

  A stop touch is NOT a simulated stop fill.

  These are price comparisons, not a full
  sequential backtest.
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


EXPECTED_TRADES = 36
EXPECTED_NET = 8.984294
EXPECTED_V_PROFIT = 31
EXPECTED_CANDIDATES = 16
EXPECTED_CONTROLS = 15

DELAYS = (5, 10, 15)
STOP_THRESHOLD_PCT = 0.50
EXTRA_EXIT_SLIPPAGE_PCT = 0.02

EPSILON = 1e-8


def as_time(value):
    if hasattr(value, "year") and hasattr(
        value, "hour"
    ):
        return value
    return step53.parse_time(value)


def valid_price(value):
    try:
        price = float(value)
        if math.isfinite(price) and price > 0:
            return price
    except (TypeError, ValueError):
        pass
    return None


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def pf(value):
    if value is None:
        return "NA"
    return f"{value:.6f}"


def is_candidate(record):
    return (
        record["two_bar_group"] == "TWO_BAR_DOWN"
        and record["structure_group"] == "BEARISH_INTACT"
    )


def index_candles(rows):
    regular = step53.regular_candles(rows)

    result = {}

    for candle in regular:
        timestamp = as_time(candle["time"])
        assert timestamp not in result, (
            "Duplicate candle timestamp"
        )
        result[timestamp] = candle

    return result


def find_next_entry(trades, current_index):
    current = trades[current_index]
    exit_time = as_time(current["exit_time"])

    later = []

    for index, trade in enumerate(trades):
        if index == current_index:
            continue

        entry_time = as_time(trade["entry_time"])

        if entry_time >= exit_time:
            later.append(entry_time)

    return min(later) if later else None


def evaluate_delay(
    exit_time,
    exit_price,
    next_entry,
    candle_index,
    delay_minutes,
):
    """
    Delayed SHORT cover at the candle OPEN
    exactly delay_minutes after the original
    recorded exit timestamp.

    This is a hypothetical execution convention.
    """

    target = exit_time + timedelta(
        minutes=delay_minutes
    )

    if target.date() != exit_time.date():
        return {
            "status": "SESSION_BOUNDARY",
            "delay": delay_minutes,
        }

    if target.hour > 15 or (
        target.hour == 15 and target.minute > 55
    ):
        return {
            "status": "SESSION_BOUNDARY",
            "delay": delay_minutes,
        }

    if (
        next_entry is not None
        and target >= next_entry
    ):
        return {
            "status": "NEXT_ENTRY_CONFLICT",
            "delay": delay_minutes,
        }

    target_candle = candle_index.get(target)

    if target_candle is None:
        return {
            "status": "MISSING_TARGET_CANDLE",
            "delay": delay_minutes,
        }

    # The exit candle itself is not used for
    # the definite post-exit stop test, because
    # its intrabar timing is unknown.
    #
    # Its high is reported separately as an
    # execution-timing ambiguity.
    exit_candle = candle_index.get(exit_time)

    exit_candle_high = (
        float(exit_candle["high"])
        if exit_candle is not None
        else None
    )

    exit_candle_adverse = (
        100.0 * (
            exit_candle_high / exit_price - 1.0
        )
        if exit_candle_high is not None
        else None
    )

    # Intermediate complete candles:
    # exit+5 through target-5.
    #
    # The target candle's opening price is the
    # hypothetical cover; its later high is not
    # included in the stop exposure.
    intermediate = []

    for minute in range(5, delay_minutes, 5):
        timestamp = exit_time + timedelta(
            minutes=minute
        )

        candle = candle_index.get(timestamp)

        if candle is None:
            return {
                "status": "MISSING_INTERMEDIATE_CANDLE",
                "delay": delay_minutes,
            }

        intermediate.append(candle)

    raw_cover = float(target_candle["open"])

    # SHORT buy-to-cover:
    # Higher cover price is worse.
    delayed_cover = raw_cover * (
        1.0 + EXTRA_EXIT_SLIPPAGE_PCT / 100.0
    )

    # Incremental SHORT return versus original
    # recorded cover price.
    #
    # The original recorded exit price is the
    # denominator, not the first future open.
    incremental = 100.0 * (
        exit_price - delayed_cover
    ) / exit_price

    # Also calculate raw price movement before
    # the additional hypothetical slippage.
    raw_change = 100.0 * (
        exit_price - raw_cover
    ) / exit_price

    # The first delayed open is already a possible
    # adverse excursion relative to original exit.
    observed_prices = [raw_cover]

    for candle in intermediate:
        observed_prices.append(
            float(candle["high"])
        )

    maximum_observed = max(observed_prices)

    max_adverse = max(
        0.0,
        100.0 * (
            maximum_observed / exit_price - 1.0
        ),
    )

    stop_touched = (
        max_adverse + EPSILON
        >= STOP_THRESHOLD_PCT
    )

    ambiguous_exit_candle_touch = (
        exit_candle_adverse is not None
        and exit_candle_adverse + EPSILON
        >= STOP_THRESHOLD_PCT
    )

    return {
        "status": (
            "STOP_TOUCHED"
            if stop_touched
            else "NO_POST_EXIT_STOP_TOUCH"
        ),
        "delay": delay_minutes,
        "target": target,
        "original_exit": exit_price,
        "raw_cover": raw_cover,
        "delayed_cover": delayed_cover,
        "raw_change": raw_change,
        "incremental": incremental,
        "max_adverse": max_adverse,
        "exit_candle_adverse": (
            exit_candle_adverse
        ),
        "exit_candle_ambiguous": (
            ambiguous_exit_candle_touch
        ),
        "stop_touched": stop_touched,
    }


def summarize(title, items):
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)
    print(f"CASES={len(items)}")

    for delay in DELAYS:
        results = [
            item["delays"][delay]
            for item in items
        ]

        statuses = Counter(
            result["status"]
            for result in results
        )

        complete = [
            result for result in results
            if result.get("incremental") is not None
        ]

        no_touch = [
            result for result in complete
            if not result["stop_touched"]
        ]

        touched = [
            result for result in complete
            if result["stop_touched"]
        ]

        print()
        print(f"DELAY={delay} MIN")
        print(f"  CASES={len(results)}")

        for status, count in sorted(
            statuses.items()
        ):
            print(f"  {status}={count}")

        print(
            f"  COMPLETE_PRICE_PATHS={len(complete)}"
        )

        if not complete:
            print(
                "  AVG_REPRICED_INCREMENTAL=NA"
            )
            continue

        values = [
            result["incremental"]
            for result in complete
        ]

        avg = sum(values) / len(values)

        print(
            "  AVG_REPRICED_INCREMENTAL="
            + fmt(avg)
        )

        print(
            "  SUM_REPRICED_INCREMENTAL="
            + fmt(sum(values))
        )

        print(
            "  IMPROVED="
            + str(sum(x > 0 for x in values))
        )

        print(
            "  WORSENED="
            + str(sum(x < 0 for x in values))
        )

        print(
            "  MAX_OBSERVED_ADVERSE="
            + fmt(
                max(
                    result["max_adverse"]
                    for result in complete
                )
            )
        )

        print(
            "  POST_EXIT_STOP_TOUCHES="
            + str(len(touched))
        )

        print(
            "  NO_TOUCH_PATHS="
            + str(len(no_touch))
        )

        ambiguous = sum(
            result["exit_candle_ambiguous"]
            for result in complete
        )

        print(
            "  EXIT_CANDLE_HIGH_AMBIGUOUS="
            + str(ambiguous)
        )

        if no_touch:
            print(
                "  AVG_NO_TOUCH_INCREMENTAL="
                + fmt(
                    sum(
                        result["incremental"]
                        for result in no_touch
                    ) / len(no_touch)
                )
            )

        print(
            "  NOTE=STOP_TOUCH_NOT_EXECUTED"
        )

        print(
            "  NOTE=NOT_SEQUENTIAL_PORTFOLIO_PNL"
        )


def detail(items):
    print()
    print("=" * 96)
    print("CANDIDATE TRADE DETAIL")
    print("=" * 96)

    for item in items:
        if not item["candidate"]:
            continue

        print()
        print(
            f'{item["dataset"]} '
            f'EXIT={item["exit_time"]} '
            f'ORIGINAL_EXIT_PRICE={pf(item["exit_price"])} '
            f'ORIGINAL_NET={fmt(item["original_net"])}'
        )

        for delay in DELAYS:
            result = item["delays"][delay]

            if result.get("incremental") is None:
                print(
                    f'  {delay}m '
                    f'STATUS={result["status"]}'
                )
                continue

            print(
                f'  {delay}m '
                f'STATUS={result["status"]} '
                f'RAW_OPEN={pf(result["raw_cover"])} '
                f'ADJUSTED_COVER={pf(result["delayed_cover"])} '
                f'INCREMENTAL={fmt(result["incremental"])} '
                f'MAX_ADVERSE={fmt(result["max_adverse"])} '
                f'EXIT_BAR_AMBIGUOUS='
                f'{result["exit_candle_ambiguous"]}'
            )


def main():
    print("AIMn — STEP 59F-5H-43K-58")
    print("RECORDED EXIT-TO-DELAYED EXIT REPRICING")
    print("NVDA SHORT 5m")
    print("READ-ONLY RESEARCH")
    print()
    print(
        f"STOP_THRESHOLD={STOP_THRESHOLD_PCT:.2f}%"
    )
    print(
        f"EXTRA_EXIT_SLIPPAGE="
        f"{EXTRA_EXIT_SLIPPAGE_PCT:.2f}%"
    )

    all_items = []
    total_trades = 0
    total_net = 0.0
    total_v_profit = 0

    for name, config in step54.DATASETS.items():
        replay, records = step54.load_dataset(
            name, config
        )

        total_trades += replay["trade_count"]
        total_net += replay["net_pnl_pct"]

        rows = step53.load_rows(config["path"])
        candle_index = index_candles(rows)

        trades = sorted(
            replay["trades"],
            key=lambda t: as_time(
                t["entry_time"]
            ),
        )

        records_by_exit = {}

        for record in records:
            timestamp = as_time(record["exit"])
            assert timestamp not in records_by_exit
            records_by_exit[timestamp] = record

        dataset_items = []

        for index, trade in enumerate(trades):
            if trade.get("exit_reason") != "V_PROFIT":
                continue

            total_v_profit += 1

            exit_time = as_time(
                trade["exit_time"]
            )

            assert exit_time in records_by_exit, (
                "Missing research classification"
            )

            record = records_by_exit[exit_time]

            exit_price = valid_price(
                trade.get("exit_price")
            )

            assert exit_price is not None, (
                "Recorded exit price unavailable"
            )

            next_entry = find_next_entry(
                trades, index
            )

            result = {
                "dataset": name,
                "exit_time": exit_time,
                "exit_price": exit_price,
                "original_net": float(
                    trade["net_pnl_pct"]
                ),
                "candidate": is_candidate(record),
                "next_entry": next_entry,
                "delays": {},
            }

            for delay in DELAYS:
                result["delays"][delay] = (
                    evaluate_delay(
                        exit_time,
                        exit_price,
                        next_entry,
                        candle_index,
                        delay,
                    )
                )

            dataset_items.append(result)

        assert (
            len(dataset_items)
            == config["v_profit"]
        ), "V_PROFIT baseline mismatch"

        print()
        print("#" * 96)
        print(f"DATASET={name}")
        print("#" * 96)

        summarize(
            name + " — CANDIDATE",
            [
                item for item in dataset_items
                if item["candidate"]
            ],
        )

        summarize(
            name + " — CONTROL",
            [
                item for item in dataset_items
                if not item["candidate"]
            ],
        )

        all_items.extend(dataset_items)

    assert total_trades == EXPECTED_TRADES
    assert abs(
        total_net - EXPECTED_NET
    ) < 0.000002
    assert total_v_profit == EXPECTED_V_PROFIT

    candidates = [
        item for item in all_items
        if item["candidate"]
    ]

    controls = [
        item for item in all_items
        if not item["candidate"]
    ]

    assert len(candidates) == EXPECTED_CANDIDATES
    assert len(controls) == EXPECTED_CONTROLS

    summarize(
        "COMBINED — CANDIDATE",
        candidates,
    )

    summarize(
        "COMBINED — CONTROL",
        controls,
    )

    detail(all_items)

    print()
    print("=" * 96)
    print("BASELINE INTEGRITY")
    print("=" * 96)

    print(f"TRADES={total_trades}")
    print(f"NET_PNL={total_net:+.6f}%")
    print(f"V_PROFIT={total_v_profit}")
    print(f"CANDIDATES={len(candidates)}")
    print(f"CONTROLS={len(controls)}")

    print()
    print("IMPORTANT LIMITATIONS")
    print(
        "Recorded replay exit_price is the baseline."
    )
    print(
        "Delayed cover uses the specified future "
        "candle open plus extra slippage."
    )
    print(
        "The exit candle high is ambiguous because "
        "intrabar event order is unknown."
    )
    print(
        "Stop touches are measured, not filled."
    )
    print(
        "A delayed exit is not allowed to overlap "
        "a later baseline entry."
    )
    print(
        "The baseline entry sequence is not replayed."
    )
    print(
        "No production trading rule approved."
    )
    print("No files written.")
    print("V18 unchanged.")
    print(
        "STEP 59F-5H-43K-58: PASS"
    )


if __name__ == "__main__":
    main()
