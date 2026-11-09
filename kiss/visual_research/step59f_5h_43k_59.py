
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-59
CONTINUATION VERSUS REVERSAL DECISION AUDIT
NVDA SHORT 5m

READ-ONLY RESEARCH. V18 UNCHANGED.

At each original V_PROFIT exit:
  1. Observe only completed candles before exit.
  2. Describe momentum, structure, and RSI.
  3. Classify evidence as bearish continuation,
     reversal warning, or mixed.
  4. Compare afterward against the original
     exit-price-to-future-open outcomes.

Future candles NEVER determine the signal.
No new trading rule is approved.
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

DELAYS = (5, 10, 15)
EXTRA_SLIPPAGE = 0.02
ADVERSE_LIMIT = 0.50

EXPECTED_TRADES = 36
EXPECTED_NET = 8.984294
EXPECTED_V_PROFIT = 31


def dt(value):
    if hasattr(value, "year") and hasattr(value, "hour"):
        return value
    return step53.parse_time(value)


def pct(new, old):
    return 100.0 * (new / old - 1.0)


def fmt(value):
    return "NA" if value is None else f"{value:+.4f}%"


def mean(values):
    return sum(values) / len(values) if values else None


def rsi(closes, period=14):
    """Simple Wilder RSI, computed from historical closes."""
    if len(closes) < period + 1:
        return None

    changes = [
        closes[i] - closes[i - 1]
        for i in range(1, len(closes))
    ]

    gains = [max(x, 0.0) for x in changes]
    losses = [max(-x, 0.0) for x in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(changes)):
        avg_gain = (
            avg_gain * (period - 1) + gains[i]
        ) / period
        avg_loss = (
            avg_loss * (period - 1) + losses[i]
        ) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    return 100.0 - 100.0 / (
        1.0 + avg_gain / avg_loss
    )


def classify(past):
    """
    Strict causal cutoff: candle timestamp < exit time.

    This deliberately excludes the candle carrying
    the original exit timestamp, because its final
    OHLC may not have been known at decision time.
    """

    if len(past) < 21:
        return {
            "signal": "INSUFFICIENT_HISTORY",
            "score": None,
        }

    recent = past[-21:]
    closes = [float(x["close"]) for x in past]
    last = recent[-1]

    close = float(last["close"])
    previous_close = float(recent[-2]["close"])

    momentum_1 = pct(close, previous_close)
    momentum_3 = pct(
        close, float(recent[-4]["close"])
    )
    momentum_5 = pct(
        close, float(recent[-6]["close"])
    )

    old_low = min(
        float(x["low"]) for x in recent[-11:-1]
    )
    old_high = max(
        float(x["high"]) for x in recent[-11:-1]
    )

    ma5 = mean([
        float(x["close"]) for x in recent[-5:]
    ])
    ma20 = mean([
        float(x["close"]) for x in recent[-20:]
    ])

    last_rsi = rsi(closes)

    # Transparent descriptive votes, not an
    # optimized or production-approved strategy.
    votes = {
        "one_bar_down": momentum_1 < 0,
        "three_bar_down": momentum_3 < 0,
        "five_bar_down": momentum_5 < 0,
        "below_ma5": close < ma5,
        "ma5_below_ma20": ma5 < ma20,
        "below_prior_low": close < old_low,
    }

    bearish = sum(votes.values())

    if bearish >= 5:
        signal = "BEARISH_CONTINUATION"
    elif bearish <= 2:
        signal = "REVERSAL_WARNING"
    else:
        signal = "MIXED"

    return {
        "signal": signal,
        "score": bearish,
        "momentum_1": momentum_1,
        "momentum_3": momentum_3,
        "momentum_5": momentum_5,
        "rsi14": last_rsi,
        "close": close,
        "ma5": ma5,
        "ma20": ma20,
        "votes": votes,
        "last_known": dt(last["time"]),
        "history_count": len(past),
    }


def evaluate_future(
    exit_time, exit_price, next_entry,
    candle_map, minutes
):
    target = exit_time + timedelta(
        minutes=minutes
    )

    if (
        target.date() != exit_time.date()
        or target.hour > 15
        or (
            target.hour == 15
            and target.minute > 55
        )
    ):
        return {"status": "SESSION_BOUNDARY"}

    if (
        next_entry is not None
        and target >= next_entry
    ):
        return {"status": "ENTRY_CONFLICT"}

    target_bar = candle_map.get(target)

    if target_bar is None:
        return {"status": "MISSING_TARGET"}

    intermediate = []

    for minute in range(5, minutes, 5):
        t = exit_time + timedelta(minutes=minute)
        bar = candle_map.get(t)

        if bar is None:
            return {"status": "MISSING_PATH"}

        intermediate.append(bar)

    cover = float(target_bar["open"])
    adjusted = cover * (
        1 + EXTRA_SLIPPAGE / 100
    )

    incremental = 100 * (
        exit_price - adjusted
    ) / exit_price

    observed = [cover] + [
        float(x["high"]) for x in intermediate
    ]

    adverse = max(
        0.0,
        pct(max(observed), exit_price),
    )

    # The original exit candle is excluded:
    # its intrabar event order is unknown.
    return {
        "status": (
            "STOP_TOUCHED"
            if adverse >= ADVERSE_LIMIT
            else "NO_STOP_TOUCH"
        ),
        "incremental": incremental,
        "adverse": adverse,
        "cover": adjusted,
    }


def summarize(title, items):
    print()
    print("=" * 90)
    print(title)
    print("=" * 90)
    print(f"CASES={len(items)}")

    for signal in (
        "BEARISH_CONTINUATION",
        "MIXED",
        "REVERSAL_WARNING",
        "INSUFFICIENT_HISTORY",
    ):
        group = [
            x for x in items
            if x["decision"]["signal"] == signal
        ]

        print()
        print(f"SIGNAL={signal} CASES={len(group)}")

        if not group:
            continue

        for minutes in DELAYS:
            results = [
                x["future"][minutes]
                for x in group
            ]

            valid = [
                r for r in results
                if "incremental" in r
            ]

            values = [
                r["incremental"] for r in valid
            ]

            statuses = Counter(
                r["status"] for r in results
            )

            print(
                f"  {minutes}m "
                f"N={len(valid)} "
                f"AVG={fmt(mean(values))} "
                f"IMPROVED={sum(v > 0 for v in values)} "
                f"WORSENED={sum(v < 0 for v in values)} "
                f"STOP_TOUCH={statuses['STOP_TOUCHED']} "
                f"MISSING_OR_BOUNDARY="
                f"{len(results) - len(valid)}"
            )


def main():
    print("AIMn — STEP 59F-5H-43K-59")
    print("CONTINUATION VERSUS REVERSAL DECISION AUDIT")
    print("NVDA SHORT 5m — READ-ONLY")
    print("CAUSAL_CUTOFF=STRICTLY_BEFORE_EXIT_TIMESTAMP")
    print("EXIT_CANDLE_FINAL_OHLC=EXCLUDED")
    print("RSI_PERIOD=14")
    print("EXTRA_EXIT_SLIPPAGE=0.02%")
    print("ADVERSE_THRESHOLD=0.50%")

    all_items = []
    trade_count = 0
    net_pnl = 0.0
    v_profit_count = 0

    for name, config in step54.DATASETS.items():
        replay, records = step54.load_dataset(
            name, config
        )

        trade_count += replay["trade_count"]
        net_pnl += replay["net_pnl_pct"]

        candles = sorted(
            step53.regular_candles(
                step53.load_rows(config["path"])
            ),
            key=lambda x: dt(x["time"]),
        )

        candle_map = {
            dt(c["time"]): c for c in candles
        }

        assert len(candle_map) == len(candles)

        trades = sorted(
            replay["trades"],
            key=lambda x: dt(x["entry_time"]),
        )

        records_by_exit = {
            dt(r["exit"]): r for r in records
        }

        dataset_items = []

        for index, trade in enumerate(trades):
            if trade.get("exit_reason") != "V_PROFIT":
                continue

            v_profit_count += 1

            exit_time = dt(trade["exit_time"])
            exit_price = float(trade["exit_price"])

            assert math.isfinite(exit_price)
            assert exit_price > 0
            assert exit_time in records_by_exit

            record = records_by_exit[exit_time]

            # Only the previous 5m candles can
            # contribute to the decision.
            past = [
                c for c in candles
                if dt(c["time"]) < exit_time
                and dt(c["time"]).date()
                == exit_time.date()
            ]

            # RSI can use earlier regular sessions.
            # Structural votes remain same-session.
            all_past = [
                c for c in candles
                if dt(c["time"]) < exit_time
            ]

            decision = classify(past)

            if decision["signal"] != (
                "INSUFFICIENT_HISTORY"
            ):
                full_closes = [
                    float(c["close"])
                    for c in all_past
                ]
                decision["rsi14"] = rsi(full_closes)

            later_entries = [
                dt(t["entry_time"])
                for j, t in enumerate(trades)
                if j != index
                and dt(t["entry_time"]) >= exit_time
            ]

            next_entry = (
                min(later_entries)
                if later_entries else None
            )

            future = {
                minutes: evaluate_future(
                    exit_time,
                    exit_price,
                    next_entry,
                    candle_map,
                    minutes,
                )
                for minutes in DELAYS
            }

            item = {
                "dataset": name,
                "entry": dt(trade["entry_time"]),
                "exit": exit_time,
                "original_net": float(
                    trade["net_pnl_pct"]
                ),
                "decision": decision,
                "future": future,
                "old_candidate": (
                    record["two_bar_group"]
                    == "TWO_BAR_DOWN"
                    and record["structure_group"]
                    == "BEARISH_INTACT"
                ),
            }

            dataset_items.append(item)

        assert (
            len(dataset_items) == config["v_profit"]
        )

        summarize(name, dataset_items)
        all_items.extend(dataset_items)

    assert trade_count == EXPECTED_TRADES
    assert abs(net_pnl - EXPECTED_NET) < 0.000002
    assert v_profit_count == EXPECTED_V_PROFIT

    summarize("COMBINED", all_items)

    print()
    print("=" * 90)
    print("TRADE-BY-TRADE DECISION AUDIT")
    print("=" * 90)

    for item in all_items:
        d = item["decision"]

        print()
        print(
            f'{item["dataset"]} '
            f'EXIT={item["exit"]} '
            f'ORIGINAL_NET={fmt(item["original_net"])} '
            f'SIGNAL={d["signal"]} '
            f'SCORE={d["score"]} '
            f'OLD_CANDIDATE={item["old_candidate"]}'
        )

        if d["score"] is not None:
            print(
                f'  MOMENTUM_1={fmt(d["momentum_1"])} '
                f'MOMENTUM_3={fmt(d["momentum_3"])} '
                f'MOMENTUM_5={fmt(d["momentum_5"])} '
                f'RSI14={d["rsi14"]:.2f} '
                f'LAST_KNOWN={d["last_known"]}'
            )

            print(
                "  VOTES="
                + ",".join(
                    k for k, v in d["votes"].items()
                    if v
                )
            )

        for minutes in DELAYS:
            result = item["future"][minutes]

            print(
                f'  {minutes}m '
                f'STATUS={result["status"]} '
                f'INCREMENTAL='
                f'{fmt(result.get("incremental"))} '
                f'ADVERSE='
                f'{fmt(result.get("adverse"))}'
            )

    print()
    print("=" * 90)
    print("BASELINE INTEGRITY")
    print("=" * 90)

    print(f"TRADES={trade_count}")
    print(f"NET_PNL={net_pnl:+.6f}%")
    print(f"V_PROFIT={v_profit_count}")
    print(
        "OLD_CANDIDATES="
        + str(sum(x["old_candidate"] for x in all_items))
    )

    print()
    print("IMPORTANT LIMITATIONS")
    print(
        "Only candles strictly before the exit "
        "timestamp determine the signal."
    )
    print(
        "Early-session exits may have insufficient "
        "same-session history."
    )
    print(
        "Votes and thresholds are exploratory, "
        "not optimized or approved."
    )
    print(
        "Historical RSI14 is descriptive; it does "
        "not replace the engine's configured RSI."
    )
    print(
        "Future prices evaluate signals only."
    )
    print(
        "Stop touches do not imply executed fills."
    )
    print(
        "The original exit candle's intrabar "
        "sequence remains unknown."
    )
    print(
        "No sequential strategy replay performed."
    )
    print("No files written.")
    print("V18 unchanged.")
    print("STEP 59F-5H-43K-59: PASS")


if __name__ == "__main__":
    main()
