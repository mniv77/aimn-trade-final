
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-52

DECISION-TIME RECOVERY STRENGTH
NOISE VS GENUINE REVERSAL

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Compare pre-exit recovery, momentum and
market structure against later price movement.

No strategy changes. V18 unchanged.
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
        22, 6.764673, 17
    ),
    "VALIDATION": (
        LAB / "nvda_sep_oct_2026_validation.json",
        14, 2.219621, 14
    ),
}

TOLERANCE = 0.000002

# Fixed descriptive bins, not trading thresholds.
RECOVERY_BINS = (
    (0.20, "UNDER_0.20"),
    (0.40, "0.20_TO_0.40"),
    (0.60, "0.40_TO_0.60"),
    (float("inf"), "OVER_0.60"),
)


def dt(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )


def pct(price, base):
    return 100.0 * (price / base - 1.0)


def load_candles(path):
    data = json.loads(
        path.read_text(encoding="utf-8")
    )
    rows = data["candles"] if isinstance(
        data, dict
    ) else data

    rows = sorted(
        rows, key=lambda x: dt(x["timestamp"])
    )

    times = [dt(x["timestamp"]) for x in rows]
    assert len(times) == len(set(times))

    candles = []
    for row in rows:
        stamp = dt(row["timestamp"])
        if time(9, 30) <= stamp.time() < time(16, 0):
            candles.append({
                "time": stamp,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })

    return rows, candles


def recovery_bin(value):
    for ceiling, name in RECOVERY_BINS:
        if value < ceiling:
            return name
    raise AssertionError("Recovery bin missing")


def pre_exit(candles, exit_time):
    history = [
        c for c in candles
        if c["time"] < exit_time
    ]
    assert len(history) >= 10

    recent = history[-5:]
    previous = history[-10:-5]

    low = min(c["low"] for c in recent)
    high = max(c["high"] for c in recent)

    previous_high = max(
        c["high"] for c in previous
    )
    previous_low = min(
        c["low"] for c in previous
    )

    bearish = sum(
        c["close"] < c["open"] for c in recent
    )
    bullish = sum(
        c["close"] > c["open"] for c in recent
    )
    lower_highs = sum(
        recent[i]["high"] < recent[i-1]["high"]
        for i in range(1, 5)
    )
    lower_lows = sum(
        recent[i]["low"] < recent[i-1]["low"]
        for i in range(1, 5)
    )

    change = pct(
        recent[-1]["close"],
        recent[0]["close"]
    )
    recovery = pct(recent[-1]["close"], low)
    last_change = pct(
        recent[-1]["close"],
        recent[-2]["close"]
    )

    swing_break = (
        recent[-1]["close"] > previous_high
    )
    lower_range = (
        high < previous_high
        and low < previous_low
    )

    bearish_structure = (
        bearish >= 3
        and lower_lows >= 2
        and change < 0
    )

    bullish_recovery = (
        bullish >= 3 and change > 0
    )

    if swing_break:
        label = "SWING_HIGH_BREAK"
    elif bullish_recovery:
        label = "BULLISH_RECOVERY"
    elif bearish_structure and lower_range:
        label = "BEARISH_CONTINUATION"
    elif bearish_structure:
        label = "BEARISH_UNCONFIRMED"
    else:
        label = "MIXED_UNCONFIRMED"

    return {
        "structure": label,
        "recovery": recovery,
        "recovery_bin": recovery_bin(recovery),
        "change": change,
        "last_change": last_change,
        "bearish": bearish,
        "bullish": bullish,
        "lower_highs": lower_highs,
        "lower_lows": lower_lows,
        "lower_range": lower_range,
        "swing_break": swing_break,
    }


def future_measure(
    candles, exit_time, next_entry
):
    """
    Hindsight only.
    Three 5-minute bars, beginning at
    exit timestamp, limited to same session.
    """
    window = [
        c for c in candles
        if c["time"] >= exit_time
        and c["time"].date() == exit_time.date()
        and (
            next_entry is None
            or c["time"] < next_entry
        )
    ][:3]

    if not window:
        return None

    reference = window[0]["open"]

    down = max(
        -pct(c["low"], reference)
        for c in window
    )
    up = max(
        pct(c["high"], reference)
        for c in window
    )
    close = pct(window[-1]["close"], reference)

    if down >= 0.50 and up < 0.30:
        quality = "CONTINUATION_CANDIDATE"
    elif up >= 0.50 and down < 0.30:
        quality = "PROTECTION_CANDIDATE"
    elif down >= 0.50 and up >= 0.30:
        quality = "TWO_SIDED_RISK"
    else:
        quality = "INCONCLUSIVE"

    return {
        "down": down,
        "up": up,
        "close": close,
        "quality": quality,
        "bars": len(window),
    }


def grouped_report(records, key):
    groups = defaultdict(list)
    for r in records:
        groups[r[key]].append(r)

    print()
    print(key.upper())

    for label, group in sorted(groups.items()):
        n = len(group)
        cont = sum(
            r["quality"] == "CONTINUATION_CANDIDATE"
            for r in group
        )
        protect = sum(
            r["quality"] == "PROTECTION_CANDIDATE"
            for r in group
        )
        mixed = n - cont - protect
        average = sum(
            r["recovery"] for r in group
        ) / n

        print(
            f"{label:27s} N={n:2d} "
            f"CONT={cont:2d} "
            f"PROTECT={protect:2d} "
            f"OTHER={mixed:2d} "
            f"AVG_RECOVERY={average:.4f}%"
        )


def report(name, records):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    assert records

    for key in (
        "quality",
        "recovery_bin",
        "structure",
        "momentum",
        "lower_high_group",
        "lower_low_group",
    ):
        grouped_report(records, key)

    print()
    print("TRADE-BY-TRADE AUDIT")

    for r in records:
        print(
            f'{r["entry"]} EXIT={r["exit"]} '
            f'NET={r["net"]:+.6f}% '
            f'QUALITY={r["quality"]} '
            f'PRE={r["structure"]} '
            f'RECOVERY={r["recovery"]:.4f}% '
            f'BIN={r["recovery_bin"]} '
            f'CHANGE={r["change"]:+.4f}% '
            f'LAST={r["last_change"]:+.4f}% '
            f'BEAR={r["bearish"]} '
            f'BULL={r["bullish"]} '
            f'LH={r["lower_highs"]} '
            f'LL={r["lower_lows"]} '
            f'DOWN={r["down"]:.4f}% '
            f'UP={r["up"]:.4f}% '
            f'F15_CLOSE={r["future_close"]:+.4f}% '
            f'BARS={r["bars"]}'
        )


def main():
    print("AIMn — STEP 59F-5H-43K-52")
    print("DECISION-TIME RECOVERY STRENGTH")
    print("NOISE VS GENUINE REVERSAL")
    print("READ-ONLY OBSERVATIONAL RESEARCH")

    all_records = []
    total_trades = 0
    total_net = 0.0

    for name, config in DATASETS.items():
        path, expected_trades, expected_net, expected_v = config

        rows, candles = load_candles(path)

        result = engine.run(
            rows=rows,
            **PARAMS
        )

        assert result["trade_count"] == expected_trades
        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < TOLERANCE

        total_trades += result["trade_count"]
        total_net += result["net_pnl_pct"]

        trades = sorted(
            result["trades"],
            key=lambda t: dt(t["entry_time"])
        )

        records = []

        for i, trade in enumerate(trades):
            if trade.get("exit_reason") != "V_PROFIT":
                continue

            entry = dt(trade["entry_time"])
            exit_time = dt(trade["exit_time"])

            next_entry = (
                dt(trades[i+1]["entry_time"])
                if i+1 < len(trades)
                else None
            )

            pre = pre_exit(candles, exit_time)
            future = future_measure(
                candles, exit_time, next_entry
            )

            assert future is not None, (
                f"No future candles for {exit_time}"
            )

            momentum = (
                "LAST_UP"
                if pre["last_change"] > 0
                else "LAST_DOWN"
                if pre["last_change"] < 0
                else "LAST_FLAT"
            )

            record = {
                **pre,
                "dataset": name,
                "entry": entry,
                "exit": exit_time,
                "net": float(trade["net_pnl_pct"]),
                "momentum": momentum,
                "lower_high_group": (
                    "LH_3_OR_4"
                    if pre["lower_highs"] >= 3
                    else "LH_0_TO_2"
                ),
                "lower_low_group": (
                    "LL_3_OR_4"
                    if pre["lower_lows"] >= 3
                    else "LL_0_TO_2"
                ),
                "quality": future["quality"],
                "down": future["down"],
                "up": future["up"],
                "future_close": future["close"],
                "bars": future["bars"],
            }

            records.append(record)

        assert len(records) == expected_v, (
            f"{name}: expected {expected_v} "
            f"V_PROFIT, got {len(records)}"
        )

        report(name, records)
        all_records.extend(records)

    assert total_trades == 36
    assert abs(total_net - 8.984294) < TOLERANCE
    assert len(all_records) == 31

    report("COMBINED — DESCRIPTIVE ONLY", all_records)

    print()
    print("CROSS-GROUP EVIDENCE")

    for quality in (
        "CONTINUATION_CANDIDATE",
        "PROTECTION_CANDIDATE",
    ):
        print()
        print(quality)

        for name in DATASETS:
            subset = [
                r for r in all_records
                if r["dataset"] == name
                and r["quality"] == quality
            ]

            if not subset:
                print(f"{name}: N=0")
                continue

            recoveries = sorted(
                r["recovery"] for r in subset
            )
            changes = sorted(
                r["change"] for r in subset
            )

            print(
                f"{name}: N={len(subset)} "
                f"RECOVERY_MIN={recoveries[0]:.4f}% "
                f"RECOVERY_MAX={recoveries[-1]:.4f}% "
                f"CHANGE_MIN={changes[0]:+.4f}% "
                f"CHANGE_MAX={changes[-1]:+.4f}%"
            )

    print()
    print("LIMITATIONS")
    print(
        "All pre-exit features use candles "
        "timestamped strictly before exit."
    )
    print(
        "Future quality labels use hindsight "
        "and cannot be trading inputs."
    )
    print(
        "Exit candle open is a price proxy, "
        "not a verified execution fill."
    )
    print(
        "The first future candle may contain "
        "movement before the actual fill."
    )
    print(
        "Intrabar price ordering is unknown."
    )
    print(
        "Fixed recovery bins are descriptive "
        "and are not optimized trading rules."
    )
    print(
        "Small sample sizes limit conclusions."
    )
    print(
        "No filters approved. No file writes. "
        "V18 unchanged."
    )
    print("STEP 59F-5H-43K-52: PASS")


if __name__ == "__main__":
    main()
