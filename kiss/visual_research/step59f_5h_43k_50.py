
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-50
BEARISH CONTINUATION VS BULLISH RECOVERY
DECISION-TIME EVIDENCE AUDIT

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

All structural measurements use completed
candles strictly before the exit timestamp.

Future price movements are reported separately.

No strategy changes.
No file writes.
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
    "RESEARCH": (
        LAB / "aimn_nvda_candles.json",
        22,
        6.764673,
    ),
    "VALIDATION": (
        LAB / "nvda_sep_oct_2026_validation.json",
        14,
        2.219621,
    ),
}

EXPECTED_COMBINED_NET = 8.984294
TOLERANCE = 0.000002

PRIORITY_DATES = {
    "2026-07-13",
    "2026-07-24",
    "2026-07-28",
    "2026-08-03",
    "2026-08-10",
    "2026-08-21",
    "2026-08-28",
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

    return (
        (price / reference - 1.0) * 100.0
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
        key=lambda r: parse_time(
            r["timestamp"]
        ),
    )

    stamps = [
        parse_time(r["timestamp"])
        for r in rows
    ]

    assert len(stamps) == len(set(stamps)), (
        f"Duplicate timestamps: {path}"
    )

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


def completed_before_exit(
    candles,
    exit_time,
):
    """
    Only completed candles strictly before
    the exit timestamp.

    For a 5m candle timestamped at its open,
    this avoids reading the unfinished exit
    candle.
    """

    return [
        c
        for c in candles
        if c["time"] < exit_time
    ]


def decision_evidence(
    candles,
    exit_time,
):
    history = completed_before_exit(
        candles,
        exit_time,
    )

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

    recovery_from_low = pct(
        recent[-1]["close"],
        recent_low,
    )

    previous_swing_high = max(
        c["high"]
        for c in previous
    )

    current_close = recent[-1]["close"]

    swing_high_broken = (
        current_close > previous_swing_high
    )

    recent_high = max(
        c["high"]
        for c in recent
    )

    previous_swing_low = min(
        c["low"]
        for c in previous
    )

    lower_range = (
        recent_high < previous_swing_high
        and recent_low < previous_swing_low
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

    if swing_high_broken:
        label = "SWING_HIGH_BREAK"

    elif bullish_recovery:
        label = "BULLISH_RECOVERY"

    elif bearish_structure and lower_range:
        label = "BEARISH_CONTINUATION"

    elif bearish_structure:
        label = "BEARISH_BUT_UNCONFIRMED"

    else:
        label = "MIXED_UNCONFIRMED"

    return {
        "label": label,
        "bearish": bearish,
        "bullish": bullish,
        "lower_highs": lower_highs,
        "lower_lows": lower_lows,
        "recent_change": recent_change,
        "recovery_from_low": recovery_from_low,
        "swing_high_broken": swing_high_broken,
        "lower_range": lower_range,
        "previous_swing_high": previous_swing_high,
        "current_close": current_close,
    }


def future_candles(
    candles,
    exit_time,
    next_entry,
):
    """
    Observational only.

    Begins at exit-timestamp candle.
    Stops before next trade entry or at
    end of exit session.
    """

    return [
        c
        for c in candles
        if (
            c["time"] >= exit_time
            and c["time"].date()
                == exit_time.date()
            and (
                next_entry is None
                or c["time"] < next_entry
            )
        )
    ]


def future_measure(
    candles,
    reference,
    count,
):
    window = candles[:count]

    if not window or reference is None:
        return None

    return {
        "close": pct(
            window[-1]["close"],
            reference,
        ),
        "down": max(
            -pct(c["low"], reference)
            for c in window
        ),
        "up": max(
            pct(c["high"], reference)
            for c in window
        ),
    }


def exit_reason(trade):
    """
    Inspect available replay fields without
    inventing an exit reason.
    """

    candidates = (
        "exit_reason",
        "reason",
        "exit_type",
        "close_reason",
    )

    for key in candidates:
        value = trade.get(key)

        if value is not None:
            return str(value)

    return "NOT_RECORDED"


def summarize(records, field, title):
    groups = defaultdict(list)

    for record in records:
        groups[record[field]].append(record)

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
    parts = [
        record["dataset"],
        str(record["entry"]),
        f'EXIT={record["exit"]}',
        f'NET={record["net"]:+.6f}%',
        f'REASON={record["reason"]}',
        f'LABEL={record["label"]}',
        f'BEAR={record["bearish"]}',
        f'BULL={record["bullish"]}',
        f'LH={record["lower_highs"]}',
        f'LL={record["lower_lows"]}',
        f'CHANGE={fmt(record["recent_change"])}',
        f'RECOVERY={fmt(record["recovery_from_low"])}',
        f'SWING_BREAK={record["swing_high_broken"]}',
        f'LOWER_RANGE={record["lower_range"]}',
    ]

    for minutes in (5, 10, 15):
        result = record[f"f{minutes}"]

        if result is None:
            parts.append(
                f"F{minutes}=NA"
            )
        else:
            parts.append(
                f'F{minutes}_C={fmt(result["close"])}'
            )
            parts.append(
                f'F{minutes}_D={fmt(result["down"])}'
            )
            parts.append(
                f'F{minutes}_U={fmt(result["up"])}'
            )

    return " ".join(parts)


def report(name, records, details=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "label",
        "DECISION-TIME STRUCTURE",
    )

    summarize(
        records,
        "reason",
        "RECORDED EXIT REASONS",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-50")
    print(
        "BEARISH CONTINUATION VS "
        "BULLISH RECOVERY"
    )
    print("DECISION-TIME EVIDENCE AUDIT")
    print("READ-ONLY OBSERVATIONAL RESEARCH")

    combined = []

    for name, (
        path,
        expected_count,
        expected_net,
    ) in DATASETS.items():

        rows = load_rows(path)
        candles = regular_candles(rows)

        result = engine.run(
            rows=rows,
            **PARAMS,
        )

        assert (
            result["trade_count"]
            == expected_count
        ), (
            f"{name}: trade count changed"
        )

        assert abs(
            result["net_pnl_pct"]
            - expected_net
        ) < TOLERANCE, (
            f"{name}: baseline net changed"
        )

        trades = sorted(
            result["trades"],
            key=lambda t: parse_time(
                t["entry_time"]
            ),
        )

        records = []

        for index, trade in enumerate(trades):
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

            evidence = decision_evidence(
                candles,
                exit_time,
            )

            assert evidence is not None, (
                f"Insufficient history: {exit_time}"
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

            future = future_candles(
                candles,
                exit_time,
                next_entry,
            )

            record = {
                "dataset": name,
                "entry": entry,
                "exit": exit_time,
                "net": float(
                    trade["net_pnl_pct"]
                ),
                "reason": exit_reason(trade),
                **evidence,
            }

            for minutes in (5, 10, 15):
                record[f"f{minutes}"] = (
                    future_measure(
                        future,
                        reference,
                        minutes // 5,
                    )
                )

            records.append(record)

        assert len(records) == expected_count, (
            f"{name}: missing records"
        )

        report(name, records)
        combined.extend(records)

    assert len(combined) == 36

    assert abs(
        sum(r["net"] for r in combined)
        - EXPECTED_COMBINED_NET
    ) < TOLERANCE

    report(
        "COMBINED — DESCRIPTIVE ONLY",
        combined,
        details=False,
    )

    print()
    print("PRIORITY CASES")

    for record in combined:
        if (
            str(record["entry"].date())
            in PRIORITY_DATES
        ):
            print(audit_line(record))

    print()
    print("LIMITATIONS:")
    print(
        "Structural evidence uses only "
        "candles timestamped before exit."
    )
    print(
        "Swing breaks use a fixed prior "
        "five-candle high, not a confirmed "
        "major trend transition."
    )
    print(
        "Future movement is hindsight "
        "and is not used in labels."
    )
    print(
        "Exit-candle open is an approximate "
        "reference, not a verified fill."
    )
    print(
        "Exit reasons are reported only "
        "when present in replay records."
    )
    print(
        "No filters approved. "
        "No file writes or V18 changes."
    )

    print("STEP 59F-5H-43K-50: PASS")


if __name__ == "__main__":
    main()
