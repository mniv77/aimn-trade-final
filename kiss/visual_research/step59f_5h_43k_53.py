
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-53

RECOVERY ACCELERATION AND
STRUCTURAL CONFIRMATION AUDIT

NVDA SHORT 5m

READ-ONLY OBSERVATIONAL RESEARCH

Objectives:
1. Preserve the established replay baseline.
2. Audit all 31 V_PROFIT exits.
3. Measure pre-exit upward acceleration.
4. Examine consecutive bullish candles.
5. Examine bearish structural integrity.
6. Separate decision-time evidence from
   post-exit hindsight.
7. Exclude the exit-timestamp candle from
   the future observation window.
8. Keep research and validation separate.

No changes to strategy or production.
V18 remains unchanged.
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
    "RESEARCH": {
        "path": LAB / "aimn_nvda_candles.json",
        "trades": 22,
        "net": 6.764673,
        "v_profit": 17,
    },
    "VALIDATION": {
        "path": LAB / "nvda_sep_oct_2026_validation.json",
        "trades": 14,
        "net": 2.219621,
        "v_profit": 14,
    },
}

EXPECTED_TRADES = 36
EXPECTED_NET = 8.984294
EXPECTED_V_PROFIT = 31
TOLERANCE = 0.000002

# Exploratory descriptive thresholds.
# These are NOT trading rules.
CONTINUATION_DOWN = 0.50
PROTECTION_UP = 0.50
OPPOSITE_LIMIT = 0.30


def parse_time(value):
    if isinstance(value, datetime):
        return value

    return datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )


def pct(price, reference):
    if reference is None or reference == 0:
        return None

    return 100.0 * (
        price / reference - 1.0
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

    assert len(timestamps) == len(
        set(timestamps)
    ), f"Duplicate timestamps: {path}"

    return rows


def regular_candles(rows):
    candles = []

    for row in rows:
        stamp = parse_time(
            row["timestamp"]
        )

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


def consecutive_bullish(candles):
    count = 0

    for candle in reversed(candles):
        if candle["close"] > candle["open"]:
            count += 1
        else:
            break

    return count


def pre_exit_evidence(candles, exit_time):
    """
    Completed candles strictly before exit.

    No exit-timestamp candle is included.
    """

    history = [
        candle
        for candle in candles
        if candle["time"] < exit_time
    ]

    if len(history) < 10:
        return None

    recent = history[-5:]
    previous = history[-10:-5]

    closes = [
        candle["close"]
        for candle in recent
    ]

    # Four consecutive close-to-close moves.
    changes = [
        pct(closes[i], closes[i - 1])
        for i in range(1, 5)
    ]

    last_change = changes[-1]
    previous_change = changes[-2]

    acceleration = (
        last_change - previous_change
    )

    last_two_change = pct(
        closes[-1],
        closes[-3],
    )

    five_candle_change = pct(
        closes[-1],
        closes[0],
    )

    recovery_low = min(
        candle["low"]
        for candle in recent
    )

    recovery = pct(
        closes[-1],
        recovery_low,
    )

    bullish = sum(
        candle["close"] > candle["open"]
        for candle in recent
    )

    bearish = sum(
        candle["close"] < candle["open"]
        for candle in recent
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

    previous_high = max(
        candle["high"]
        for candle in previous
    )

    previous_low = min(
        candle["low"]
        for candle in previous
    )

    recent_high = max(
        candle["high"]
        for candle in recent
    )

    recent_low = min(
        candle["low"]
        for candle in recent
    )

    swing_break = (
        closes[-1] > previous_high
    )

    lower_range = (
        recent_high < previous_high
        and recent_low < previous_low
    )

    bearish_structure = (
        bearish >= 3
        and lower_lows >= 2
        and five_candle_change < 0
    )

    bullish_recovery = (
        bullish >= 3
        and five_candle_change > 0
    )

    if swing_break:
        structure = "SWING_HIGH_BREAK"

    elif bullish_recovery:
        structure = "BULLISH_RECOVERY"

    elif bearish_structure and lower_range:
        structure = "BEARISH_CONTINUATION"

    elif bearish_structure:
        structure = "BEARISH_UNCONFIRMED"

    else:
        structure = "MIXED_UNCONFIRMED"

    if acceleration > 0:
        acceleration_group = "ACCELERATING_UP"
    elif acceleration < 0:
        acceleration_group = "DECELERATING_UP"
    else:
        acceleration_group = "UNCHANGED"

    if last_two_change > 0:
        two_candle_group = "TWO_BAR_UP"
    elif last_two_change < 0:
        two_candle_group = "TWO_BAR_DOWN"
    else:
        two_candle_group = "TWO_BAR_FLAT"

    consecutive = consecutive_bullish(
        recent
    )

    if consecutive >= 2:
        sequence_group = "TWO_PLUS_BULLISH"
    elif consecutive == 1:
        sequence_group = "ONE_BULLISH"
    else:
        sequence_group = "NO_BULLISH"

    if (
        lower_highs >= 3
        and lower_lows >= 3
        and not swing_break
    ):
        structural_group = "BEARISH_INTACT"

    elif swing_break:
        structural_group = "SWING_HIGH_BROKEN"

    else:
        structural_group = "STRUCTURE_WEAKENED"

    return {
        "structure": structure,
        "recovery": recovery,
        "last_change": last_change,
        "previous_change": previous_change,
        "acceleration": acceleration,
        "last_two_change": last_two_change,
        "five_candle_change": five_candle_change,
        "bullish": bullish,
        "bearish": bearish,
        "lower_highs": lower_highs,
        "lower_lows": lower_lows,
        "lower_range": lower_range,
        "swing_break": swing_break,
        "consecutive_bullish": consecutive,
        "acceleration_group": acceleration_group,
        "two_candle_group": two_candle_group,
        "sequence_group": sequence_group,
        "structural_group": structural_group,
    }


def post_exit_evidence(
    candles,
    exit_time,
    next_entry,
):
    """
    Hindsight only.

    Excludes the entire exit-timestamp candle.

    Uses up to the next three 5-minute candles,
    within the same session and before the
    next trade entry.

    Reference = first included candle open.
    This is NOT the actual exit fill.

    Therefore results describe later price
    behavior, not executable trade P&L.
    """

    future = [
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
    ][:3]

    if not future:
        return {
            "quality": "NO_FUTURE_DATA",
            "down": None,
            "up": None,
            "close": None,
            "bars": 0,
        }

    reference = future[0]["open"]

    down = max(
        -pct(candle["low"], reference)
        for candle in future
    )

    up = max(
        pct(candle["high"], reference)
        for candle in future
    )

    close = pct(
        future[-1]["close"],
        reference,
    )

    if (
        down >= CONTINUATION_DOWN
        and up < OPPOSITE_LIMIT
    ):
        quality = "CONTINUATION_CANDIDATE"

    elif (
        up >= PROTECTION_UP
        and down < OPPOSITE_LIMIT
    ):
        quality = "PROTECTION_CANDIDATE"

    elif (
        down >= CONTINUATION_DOWN
        and up >= OPPOSITE_LIMIT
    ):
        quality = "TWO_SIDED_RISK"

    else:
        quality = "INCONCLUSIVE"

    return {
        "quality": quality,
        "down": down,
        "up": up,
        "close": close,
        "bars": len(future),
    }


def summary(records, key):
    groups = defaultdict(list)

    for record in records:
        groups[record[key]].append(record)

    print()
    print(key.upper())

    for label, group in sorted(groups.items()):
        continuation = sum(
            r["quality"] == "CONTINUATION_CANDIDATE"
            for r in group
        )

        protection = sum(
            r["quality"] == "PROTECTION_CANDIDATE"
            for r in group
        )

        no_data = sum(
            r["quality"] == "NO_FUTURE_DATA"
            for r in group
        )

        other = (
            len(group)
            - continuation
            - protection
            - no_data
        )

        average_recovery = sum(
            r["recovery"]
            for r in group
        ) / len(group)

        average_acceleration = sum(
            r["acceleration"]
            for r in group
        ) / len(group)

        print(
            f"{label:28s} "
            f"N={len(group):2d} "
            f"CONT={continuation:2d} "
            f"PROTECT={protection:2d} "
            f"OTHER={other:2d} "
            f"NO_DATA={no_data:2d} "
            f"AVG_REC={average_recovery:+.4f}% "
            f"AVG_ACCEL={average_acceleration:+.4f}pp"
        )


def audit_line(record):
    fields = [
        record["dataset"],
        f'ENTRY={record["entry"]}',
        f'EXIT={record["exit"]}',
        f'NET={record["net"]:+.6f}%',
        f'QUALITY={record["quality"]}',
        f'STRUCTURE={record["structure"]}',
        f'RECOVERY={fmt(record["recovery"])}',
        f'LAST={fmt(record["last_change"])}',
        f'PREVIOUS={fmt(record["previous_change"])}',
        f'ACCEL={record["acceleration"]:+.4f}pp',
        f'TWO_BAR={fmt(record["last_two_change"])}',
        f'FIVE_BAR={fmt(record["five_candle_change"])}',
        f'CONSEC_BULL={record["consecutive_bullish"]}',
        f'BEAR={record["bearish"]}',
        f'BULL={record["bullish"]}',
        f'LH={record["lower_highs"]}',
        f'LL={record["lower_lows"]}',
        f'LOWER_RANGE={record["lower_range"]}',
        f'SWING_BREAK={record["swing_break"]}',
        f'ACCEL_GROUP={record["acceleration_group"]}',
        f'STRUCT_GROUP={record["structural_group"]}',
        f'FUTURE_BARS={record["bars"]}',
        f'FUTURE_DOWN={fmt(record["down"])}',
        f'FUTURE_UP={fmt(record["up"])}',
        f'FUTURE_CLOSE={fmt(record["future_close"])}',
    ]

    return " ".join(fields)


def report(name, records, details=True):
    print()
    print("=" * 110)
    print(name)
    print("=" * 110)

    for key in (
        "quality",
        "acceleration_group",
        "two_candle_group",
        "sequence_group",
        "structural_group",
        "structure",
    ):
        summary(records, key)

    if details:
        print()
        print("TRADE-BY-TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-53")
    print(
        "RECOVERY ACCELERATION AND "
        "STRUCTURAL CONFIRMATION"
    )
    print("READ-ONLY OBSERVATIONAL RESEARCH")

    all_records = []
    total_trades = 0
    total_net = 0.0

    for name, config in DATASETS.items():
        rows = load_rows(config["path"])
        candles = regular_candles(rows)

        result = engine.run(
            rows=rows,
            **PARAMS,
        )

        assert (
            result["trade_count"]
            == config["trades"]
        ), f"{name}: trade count changed"

        assert abs(
            result["net_pnl_pct"] - config["net"]
        ) < TOLERANCE, (
            f"{name}: baseline net changed"
        )

        total_trades += result["trade_count"]
        total_net += result["net_pnl_pct"]

        trades = sorted(
            result["trades"],
            key=lambda t: parse_time(
                t["entry_time"]
            ),
        )

        records = []

        for index, trade in enumerate(trades):
            if (
                trade.get("exit_reason")
                != "V_PROFIT"
            ):
                continue

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

            pre = pre_exit_evidence(
                candles,
                exit_time,
            )

            assert pre is not None, (
                f"Missing pre-exit evidence: "
                f"{exit_time}"
            )

            future = post_exit_evidence(
                candles,
                exit_time,
                next_entry,
            )

            record = {
                **pre,
                "dataset": name,
                "entry": entry,
                "exit": exit_time,
                "net": float(
                    trade["net_pnl_pct"]
                ),
                "quality": future["quality"],
                "down": future["down"],
                "up": future["up"],
                "future_close": future["close"],
                "bars": future["bars"],
            }

            records.append(record)

        assert (
            len(records) == config["v_profit"]
        ), (
            f"{name}: V_PROFIT count changed"
        )

        report(name, records)
        all_records.extend(records)

    assert total_trades == EXPECTED_TRADES

    assert abs(
        total_net - EXPECTED_NET
    ) < TOLERANCE

    assert (
        len(all_records)
        == EXPECTED_V_PROFIT
    )

    report(
        "COMBINED — DESCRIPTIVE ONLY",
        all_records,
        details=False,
    )

    print()
    print("CROSS-DATASET COMPARISON")

    for quality in (
        "CONTINUATION_CANDIDATE",
        "PROTECTION_CANDIDATE",
    ):
        print()
        print(quality)

        for dataset in DATASETS:
            subset = [
                r for r in all_records
                if (
                    r["dataset"] == dataset
                    and r["quality"] == quality
                )
            ]

            if not subset:
                print(f"{dataset}: N=0")
                continue

            avg_recovery = sum(
                r["recovery"]
                for r in subset
            ) / len(subset)

            avg_acceleration = sum(
                r["acceleration"]
                for r in subset
            ) / len(subset)

            avg_two_bar = sum(
                r["last_two_change"]
                for r in subset
            ) / len(subset)

            print(
                f"{dataset}: N={len(subset)} "
                f"AVG_REC={avg_recovery:+.4f}% "
                f"AVG_ACCEL={avg_acceleration:+.4f}pp "
                f"AVG_TWO_BAR={avg_two_bar:+.4f}%"
            )

    print()
    print("LIMITATIONS")

    print(
        "Pre-exit features use only candles "
        "timestamped strictly before exit."
    )
    print(
        "Future observations exclude the "
        "exit-timestamp candle entirely."
    )
    print(
        "Future reference is the first "
        "subsequent candle open, not the "
        "actual exit fill."
    )
    print(
        "The next three candles are observed "
        "only when available in the same "
        "session before the next entry."
    )
    print(
        "Timestamp convention and actual "
        "fill timing remain unverified."
    )
    print(
        "Intrabar ordering remains unknown."
    )
    print(
        "Hindsight classifications cannot "
        "be used as live trading inputs."
    )
    print(
        "Thresholds are exploratory and "
        "have not been optimized."
    )
    print(
        "No filters approved. "
        "No file writes. V18 unchanged."
    )

    print("STEP 59F-5H-43K-53: PASS")


if __name__ == "__main__":
    main()
