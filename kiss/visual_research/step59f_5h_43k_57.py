
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-57

ACTUAL EXIT-PRICE AND TIMESTAMP ALIGNMENT AUDIT
NVDA SHORT 5m

READ-ONLY RESEARCH

Inspect:
- Original replay trade fields
- Recorded exit prices, if available
- Exit timestamps and candle alignment
- OHLC prices surrounding each exit
- First subsequent candle opening price
- Potential differences between original
  replay exit and Step 55's proxy reference

Do not invent missing execution prices.
Do not modify trading logic.
Do not write files.
V18 unchanged.
"""

import sys
import math
from pathlib import Path
from collections import Counter

LAB = Path("kiss/visual_research")
sys.path.insert(0, str(LAB.resolve()))

import step59f_5h_43k_53 as step53
import step59f_5h_43k_54 as step54


EXPECTED_TRADES = 36
EXPECTED_NET = 8.984294
EXPECTED_V_PROFIT = 31
EXPECTED_CANDIDATES = 16
TOLERANCE = 0.000002

EXIT_PRICE_KEYS = (
    "exit_price",
    "exit_fill_price",
    "fill_price",
    "exit_execution_price",
    "exit_px",
    "close_price",
)

ENTRY_PRICE_KEYS = (
    "entry_price",
    "entry_fill_price",
    "entry_px",
)

PRICE_KEYS = (
    "open",
    "high",
    "low",
    "close",
)


def pct(a, b):
    if a is None or b is None or b == 0:
        return None
    return 100.0 * (a - b) / b


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def pricefmt(value):
    if value is None:
        return "NA"
    return f"{value:.6f}"


def numeric(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        result = float(value)
        if not math.isfinite(result) or result <= 0:
            return None
        return result
    except (ValueError, TypeError):
        return None


def recorded_price(trade, keys):
    for key in keys:
        if key in trade:
            value = numeric(trade[key])
            if value is not None:
                return key, value
    return None, None


def candidate(record):
    return (
        record["two_bar_group"] == "TWO_BAR_DOWN"
        and record["structure_group"] == "BEARISH_INTACT"
    )


def candle_line(candle):
    if candle is None:
        return "NONE"

    return (
        f'TIME={candle["time"]} '
        f'O={pricefmt(candle["open"])} '
        f'H={pricefmt(candle["high"])} '
        f'L={pricefmt(candle["low"])} '
        f'C={pricefmt(candle["close"])}'
    )


def audit_trade(trade, record, candles):
    exit_time = step53.parse_time(trade["exit_time"])

    same_day = [
        candle for candle in candles
        if candle["time"].date() == exit_time.date()
    ]

    exact = next(
        (
            candle for candle in same_day
            if candle["time"] == exit_time
        ),
        None,
    )

    before = [
        candle for candle in same_day
        if candle["time"] < exit_time
    ]

    after = [
        candle for candle in same_day
        if candle["time"] > exit_time
    ]

    previous = before[-1] if before else None
    following = after[0] if after else None

    exit_key, exit_price = recorded_price(
        trade, EXIT_PRICE_KEYS
    )

    entry_key, entry_price = recorded_price(
        trade, ENTRY_PRICE_KEYS
    )

    reference = (
        following["open"]
        if following is not None
        else None
    )

    gap = None

    if following is not None:
        gap = (
            following["time"] - exit_time
        ).total_seconds() / 60.0

    alignment = (
        "EXACT_CANDLE"
        if exact is not None
        else "NO_EXACT_CANDLE"
    )

    reference_difference = (
        pct(reference, exit_price)
        if exit_price is not None
        else None
    )

    exit_within_exact = None

    if exit_price is not None and exact is not None:
        exit_within_exact = (
            exact["low"] - 1e-8
            <= exit_price
            <= exact["high"] + 1e-8
        )

    return {
        "trade": trade,
        "record": record,
        "exit_time": exit_time,
        "alignment": alignment,
        "previous": previous,
        "exact": exact,
        "following": following,
        "gap": gap,
        "exit_key": exit_key,
        "exit_price": exit_price,
        "entry_key": entry_key,
        "entry_price": entry_price,
        "reference": reference,
        "reference_difference": reference_difference,
        "exit_within_exact": exit_within_exact,
        "candidate": candidate(record),
    }


def print_detail(item):
    trade = item["trade"]

    print()
    print("-" * 100)

    print(
        f'ENTRY={trade.get("entry_time")} '
        f'EXIT={item["exit_time"]} '
        f'REASON={trade.get("exit_reason")} '
        f'GROUP={"CANDIDATE" if item["candidate"] else "CONTROL"}'
    )

    print(
        f'ORIGINAL_NET={fmt(trade.get("net_pnl_pct"))} '
        f'ALIGNMENT={item["alignment"]}'
    )

    print(
        "PREVIOUS: "
        + candle_line(item["previous"])
    )

    print(
        "EXACT:    "
        + candle_line(item["exact"])
    )

    print(
        "NEXT:     "
        + candle_line(item["following"])
    )

    print(
        f'RECORDED_ENTRY_PRICE_FIELD={item["entry_key"]} '
        f'VALUE={pricefmt(item["entry_price"])}'
    )

    print(
        f'RECORDED_EXIT_PRICE_FIELD={item["exit_key"]} '
        f'VALUE={pricefmt(item["exit_price"])}'
    )

    print(
        f'NEXT_OPEN_PROXY={pricefmt(item["reference"])} '
        f'GAP_MIN={item["gap"]}'
    )

    print(
        "NEXT_OPEN_MINUS_RECORDED_EXIT="
        + fmt(item["reference_difference"])
    )

    print(
        "RECORDED_EXIT_WITHIN_EXACT_CANDLE="
        + str(item["exit_within_exact"])
    )


def report_group(title, items):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    print(f"CASES={len(items)}")

    price_available = [
        item for item in items
        if item["exit_price"] is not None
    ]

    exact = sum(
        item["exact"] is not None
        for item in items
    )

    next_open = sum(
        item["reference"] is not None
        for item in items
    )

    gaps = Counter(
        item["gap"]
        for item in items
        if item["gap"] is not None
    )

    differences = [
        item["reference_difference"]
        for item in items
        if item["reference_difference"] is not None
    ]

    print(f"EXACT_CANDLE_MATCHES={exact}")
    print(f"NEXT_CANDLE_AVAILABLE={next_open}")
    print(f"RECORDED_EXIT_PRICES={len(price_available)}")

    print("NEXT_CANDLE_GAPS_MINUTES:")
    for gap, count in sorted(gaps.items()):
        print(f"  {gap}: {count}")

    if differences:
        print(
            "AVG_NEXT_OPEN_MINUS_RECORDED_EXIT="
            + fmt(sum(differences) / len(differences))
        )

        print(
            "MIN_DIFFERENCE="
            + fmt(min(differences))
        )

        print(
            "MAX_DIFFERENCE="
            + fmt(max(differences))
        )

    else:
        print(
            "ACTUAL_EXIT_PRICE_COMPARISON="
            "NOT_AVAILABLE"
        )

    within = Counter(
        str(item["exit_within_exact"])
        for item in items
    )

    print("EXIT_PRICE_WITHIN_EXACT_CANDLE:")
    for key, count in sorted(within.items()):
        print(f"  {key}: {count}")


def main():
    print("AIMn — STEP 59F-5H-43K-57")
    print("ACTUAL EXIT-PRICE AND TIMESTAMP ALIGNMENT AUDIT")
    print("NVDA SHORT 5m")
    print("READ-ONLY RESEARCH")

    all_items = []
    total_trades = 0
    total_net = 0.0

    for name, config in step54.DATASETS.items():
        print()
        print("#" * 100)
        print(f"DATASET={name}")
        print("#" * 100)

        replay, records = step54.load_dataset(
            name, config
        )

        total_trades += replay["trade_count"]
        total_net += replay["net_pnl_pct"]

        raw = step53.load_rows(config["path"])
        candles = step53.regular_candles(raw)

        print(f"REGULAR_CANDLES={len(candles)}")

        trades = [
            trade for trade in replay["trades"]
            if trade.get("exit_reason") == "V_PROFIT"
        ]

        print(
            "REPLAY_TRADE_FIELDS="
            + ", ".join(
                sorted(
                    set().union(
                        *(set(t.keys()) for t in trades)
                    )
                )
            )
        )

        records_by_exit = {}

        for record in records:
            key = step53.parse_time(record["exit"])
            assert key not in records_by_exit, (
                "Duplicate V_PROFIT exit timestamp"
            )
            records_by_exit[key] = record

        items = []

        for trade in trades:
            key = step53.parse_time(
                trade["exit_time"]
            )

            assert key in records_by_exit, (
                "Replay trade missing research record"
            )

            item = audit_trade(
                trade,
                records_by_exit[key],
                candles,
            )

            items.append(item)

        assert len(items) == config["v_profit"]

        report_group(
            name + " — CANDIDATE",
            [i for i in items if i["candidate"]],
        )

        report_group(
            name + " — CONTROL",
            [i for i in items if not i["candidate"]],
        )

        print()
        print("TRADE-BY-TRADE EXECUTION AUDIT")

        for item in items:
            print_detail(item)

        all_items.extend(items)

    assert total_trades == EXPECTED_TRADES
    assert abs(total_net - EXPECTED_NET) < TOLERANCE
    assert len(all_items) == EXPECTED_V_PROFIT

    candidates = [
        item for item in all_items
        if item["candidate"]
    ]

    controls = [
        item for item in all_items
        if not item["candidate"]
    ]

    assert len(candidates) == EXPECTED_CANDIDATES
    assert len(controls) == 15

    report_group(
        "COMBINED — CANDIDATE",
        candidates,
    )

    report_group(
        "COMBINED — CONTROL",
        controls,
    )

    print()
    print("=" * 100)
    print("BASELINE INTEGRITY")
    print("=" * 100)

    print(f"TRADES={total_trades}")
    print(f"NET_PNL={total_net:+.6f}%")
    print(f"V_PROFIT={len(all_items)}")
    print(f"CANDIDATES={len(candidates)}")
    print(f"CONTROLS={len(controls)}")

    print()
    print("METHODOLOGY")

    print(
        "Exact timestamp matches do not establish "
        "whether candle labels mean open or close."
    )

    print(
        "A replay exit price is not necessarily "
        "a broker execution fill."
    )

    print(
        "Missing recorded exit prices are "
        "reported as unavailable."
    )

    print(
        "Next-candle opens are proxies, "
        "not automatically original exit prices."
    )

    print(
        "OHLC candles do not establish "
        "intrabar execution order."
    )

    print(
        "No trading rules approved."
    )

    print("No files written.")
    print("V18 unchanged.")

    print()
    print("STEP 59F-5H-43K-57: PASS")


if __name__ == "__main__":
    main()
