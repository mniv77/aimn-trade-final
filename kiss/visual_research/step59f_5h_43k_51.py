
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-51

V_PROFIT EXIT QUALITY:
PROTECTIVE VS PREMATURE EXIT AUDIT


NVDA SHORT 5m

READ-ONLY OBSERVATIONAL RESEARCH

Objectives:
1. Preserve the established replay baseline.
2. Audit all V_PROFIT exits.
3. Compare future bearish continuation against
   future bullish recovery.
4. Measure both favorable and adverse excursions.
5. Separate decision-time evidence from hindsight.
6. Do not change any trading logic or files.

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

EXPECTED_TOTAL_TRADES = 36
EXPECTED_TOTAL_NET = 8.984294
EXPECTED_V_PROFIT = 31

TOLERANCE = 0.000002

PRIORITY_DATES = {
    "2026-07-13",
    "2026-07-28",
    "2026-07-29",
    "2026-08-10",
    "2026-08-19",
    "2026-08-21",
    "2026-08-28",
    "2026-09-08",
    "2026-10-08",
    "2026-10-14",
    "2026-10-15",
}


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
    result = []

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

        result.append({
            "time": stamp,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })

    return result


def pre_exit_evidence(candles, exit_time):
    history = [
        candle
        for candle in candles
        if candle["time"] < exit_time
    ]

    if len(history) < 10:
        return None

    recent = history[-5:]
    previous = history[-10:-5]

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

    recent_change = pct(
        recent[-1]["close"],
        recent[0]["close"],
    )

    recent_low = min(
        c["low"]
        for c in recent
    )

    recovery = pct(
        recent[-1]["close"],
        recent_low,
    )

    previous_high = max(
        c["high"]
        for c in previous
    )

    previous_low = min(
        c["low"]
        for c in previous
    )

    recent_high = max(
        c["high"]
        for c in recent
    )

    swing_break = (
        recent[-1]["close"] > previous_high
    )

    lower_range = (
        recent_high < previous_high
        and recent_low < previous_low
    )

    bearish_structure = (
        bearish >= 3
        and lower_lows >= 2
        and recent_change < 0
    )

    bullish_recovery = (
        bullish >= 3
        and recent_change > 0
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
        "label": label,
        "bearish": bearish,
        "bullish": bullish,
        "lower_highs": lower_highs,
        "lower_lows": lower_lows,
        "recent_change": recent_change,
        "recovery": recovery,
        "swing_break": swing_break,
        "lower_range": lower_range,
    }


def post_exit_path(
    candles,
    exit_time,
    next_entry,
):
    """
    Hindsight only.

    The window begins with the candle whose
    timestamp matches the exit timestamp.

    Stops at next trade entry or at the end
    of the exit session.
    """

    return [
        candle
        for candle in candles
        if (
            candle["time"] >= exit_time
            and candle["time"].date()
                == exit_time.date()
            and (
                next_entry is None
                or candle["time"] < next_entry
            )
        )
    ]


def measure_window(candles, reference, count):
    window = candles[:count]

    if not window or reference is None:
        return None

    down = max(
        -pct(c["low"], reference)
        for c in window
    )

    up = max(
        pct(c["high"], reference)
        for c in window
    )

    return {
        "close": pct(
            window[-1]["close"],
            reference,
        ),
        "down": down,
        "up": up,
    }


def classify_future(measure):
    """
    Descriptive hindsight classification.

    A 0.30% threshold is used for both
    directions, with an ambiguity category
    when both directions reach the threshold.

    No assumption is made about intrabar
    ordering.
    """

    if measure is None:
        return "NO_DATA"

    down = measure["down"]
    up = measure["up"]

    down_hit = down >= 0.30
    up_hit = up >= 0.30

    if down_hit and up_hit:
        return "BOTH_DIRECTIONS"

    if down_hit:
        return "DOWN_CONTINUATION"

    if up_hit:
        return "UP_RECOVERY"

    return "NEITHER_THRESHOLD"


def exit_quality(measure):
    """
    Descriptive only, not a judgment about
    the actual exit decision.
    """

    if measure is None:
        return "UNKNOWN"

    down = measure["down"]
    up = measure["up"]

    if down >= 0.50 and up < 0.30:
        return "CONTINUATION_CANDIDATE"

    if up >= 0.50 and down < 0.30:
        return "PROTECTION_CANDIDATE"

    if down >= 0.50 and up >= 0.30:
        return "TWO_SIDED_RISK"

    return "INCONCLUSIVE"


def summary(records, key, title):
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

        net = sum(
            r["net"]
            for r in group
        )

        print(
            f"{label:28s} "
            f"N={len(group):2d} "
            f"W={winners:2d} "
            f"L={losers:2d} "
            f"NET={net:+.6f}%"
        )


def audit_line(record):
    fields = [
        record["dataset"],
        str(record["entry"]),
        f'EXIT={record["exit"]}',
        f'NET={record["net"]:+.6f}%',
        f'PRE={record["pre_label"]}',
        f'BEAR={record["bearish"]}',
        f'BULL={record["bullish"]}',
        f'LH={record["lower_highs"]}',
        f'LL={record["lower_lows"]}',
        f'CHANGE={fmt(record["recent_change"])}',
        f'RECOVERY={fmt(record["recovery"])}',
        f'SWING_BREAK={record["swing_break"]}',
        f'LOWER_RANGE={record["lower_range"]}',
        f'FUTURE={record["future_label"]}',
        f'QUALITY={record["quality"]}',
    ]

    for minutes in (5, 10, 15):
        measure = record[f"f{minutes}"]

        if measure is None:
            fields.append(
                f"F{minutes}=NA"
            )

        else:
            fields.extend([
                f'F{minutes}_C={fmt(measure["close"])}',
                f'F{minutes}_D={fmt(measure["down"])}',
                f'F{minutes}_U={fmt(measure["up"])}',
            ])

    return " ".join(fields)


def report(name, records, details=True):
    print()
    print("=" * 110)
    print(name)
    print("=" * 110)

    summary(
        records,
        "pre_label",
        "PRE-EXIT STRUCTURE",
    )

    summary(
        records,
        "future_label",
        "POST-EXIT 15-MINUTE PATH",
    )

    summary(
        records,
        "quality",
        "EXIT QUALITY CANDIDATES",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-51")
    print(
        "V_PROFIT EXIT QUALITY — "
        "PROTECTIVE VS PREMATURE"
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
            result["net_pnl_pct"]
            - config["net"]
        ) < TOLERANCE, (
            f"{name}: baseline net changed"
        )

        trades = sorted(
            result["trades"],
            key=lambda t: parse_time(
                t["entry_time"]
            ),
        )

        total_trades += result["trade_count"]
        total_net += result["net_pnl_pct"]

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

            evidence = pre_exit_evidence(
                candles,
                exit_time,
            )

            assert evidence is not None, (
                f"Missing pre-exit evidence: "
                f"{exit_time}"
            )

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

            future = post_exit_path(
                candles,
                exit_time,
                next_entry,
            )

            measures = {
                minutes: measure_window(
                    future,
                    reference,
                    minutes // 5,
                )
                for minutes in (5, 10, 15)
            }

            record = {
                "dataset": name,
                "entry": entry,
                "exit": exit_time,
                "net": float(
                    trade["net_pnl_pct"]
                ),
                "pre_label": evidence["label"],
                "bearish": evidence["bearish"],
                "bullish": evidence["bullish"],
                "lower_highs": evidence["lower_highs"],
                "lower_lows": evidence["lower_lows"],
                "recent_change": evidence[
                    "recent_change"
                ],
                "recovery": evidence["recovery"],
                "swing_break": evidence[
                    "swing_break"
                ],
                "lower_range": evidence[
                    "lower_range"
                ],
                "future_label": classify_future(
                    measures[15]
                ),
                "quality": exit_quality(
                    measures[15]
                ),
                "f5": measures[5],
                "f10": measures[10],
                "f15": measures[15],
            }

            records.append(record)

        assert len(records) == config["v_profit"], (
            f"{name}: V_PROFIT count changed. "
            f"Expected {config['v_profit']}, "
            f"got {len(records)}"
        )

        report(name, records)
        all_records.extend(records)

    assert total_trades == EXPECTED_TOTAL_TRADES

    assert abs(
        total_net - EXPECTED_TOTAL_NET
    ) < TOLERANCE

    assert len(all_records) == EXPECTED_V_PROFIT

    report(
        "COMBINED V_PROFIT — DESCRIPTIVE ONLY",
        all_records,
        details=False,
    )

    print()
    print("PRIORITY CASES")

    for record in all_records:
        if (
            str(record["entry"].date())
            in PRIORITY_DATES
        ):
            print(audit_line(record))

    print()
    print("LIMITATIONS:")
    print(
        "Pre-exit evidence uses completed "
        "candles strictly before exit."
    )
    print(
        "Post-exit observations are hindsight."
    )
    print(
        "The exit-timestamp candle may include "
        "price action before the actual fill."
    )
    print(
        "The exit-candle open is not a "
        "verified execution price."
    )
    print(
        "The 0.30% and 0.50% thresholds "
        "are exploratory, not optimized."
    )
    print(
        "Intrabar ordering is unknown."
    )
    print(
        "Continuation and protection labels "
        "are not approved trading rules."
    )
    print(
        "No filters approved. "
        "No file writes or V18 changes."
    )

    print("STEP 59F-5H-43K-51: PASS")


if __name__ == "__main__":
    main()
