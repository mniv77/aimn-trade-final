
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-46
BEARISH LEG PROGRESS AND REMAINING OPPORTUNITY AUDIT

NVDA SHORT 5m
READ-ONLY OBSERVATIONAL RESEARCH

Entry-time measurements:
    - Decline from completed-session high
    - Recovery from completed-session low
    - Distance below recent six-bar high
    - Distance above recent six-bar low

Retrospective measurements:
    - Maximum favorable excursion (MFE)
    - Maximum adverse excursion (MAE)
    - Favorable excursion before actual exit
    - Potential favorable movement after exit
    - Profit capture versus maximum excursion

All future observations are labeled hindsight.
No future values are used to select entries.

No file writes.
No production or V18 changes.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, time
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

PRIORITY_DATES = {
    "2026-07-24",
    "2026-07-28",
    "2026-08-03",
    "2026-08-21",
    "2026-09-02",
}

TOLERANCE = 0.000002


def parse_time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def pct(new_value, old_value):
    if old_value is None or old_value == 0:
        return None
    return (new_value / old_value - 1.0) * 100.0


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
        key=lambda r: parse_time(r["timestamp"]),
    )

    timestamps = [
        parse_time(r["timestamp"])
        for r in rows
    ]

    assert len(timestamps) == len(set(timestamps)), (
        f"Duplicate timestamps: {path}"
    )

    return rows


def regular_candles(rows):
    result = []

    for row in rows:
        stamp = parse_time(row["timestamp"])

        if not time(9, 30) <= stamp.time() < time(16, 0):
            continue

        result.append({
            "time": stamp,
            "end": stamp + timedelta(minutes=5),
            "date": stamp.date(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })

    return result


def group_sessions(candles):
    sessions = defaultdict(list)

    for candle in candles:
        sessions[candle["date"]].append(candle)

    for day in sessions:
        sessions[day].sort(
            key=lambda c: c["time"]
        )

    return sessions


def completed_before_entry(session, entry):
    completed = [
        c for c in session
        if c["end"] <= entry
    ]

    result = []

    expected = datetime.combine(
        entry.date(),
        time(9, 30),
    )

    for candle in completed:
        if candle["time"] != expected:
            break

        result.append(candle)
        expected += timedelta(minutes=5)

    return result


def entry_context(session, entry):
    entry_candle = next(
        (
            c for c in session
            if c["time"] == entry
        ),
        None,
    )

    if entry_candle is None:
        raise ValueError(
            f"Entry candle missing: {entry}"
        )

    entry_price = entry_candle["open"]

    completed = completed_before_entry(
        session, entry
    )

    if not completed:
        return {
            "entry_price": entry_price,
            "completed_bars": 0,
            "decline_from_high": None,
            "recovery_from_low": None,
            "below_recent_high": None,
            "above_recent_low": None,
        }

    session_high = max(
        c["high"] for c in completed
    )

    session_low = min(
        c["low"] for c in completed
    )

    recent = completed[-6:]

    recent_high = max(
        c["high"] for c in recent
    )

    recent_low = min(
        c["low"] for c in recent
    )

    return {
        "entry_price": entry_price,
        "completed_bars": len(completed),
        "decline_from_high": max(
            0.0,
            -pct(entry_price, session_high),
        ),
        "recovery_from_low": max(
            0.0,
            pct(entry_price, session_low),
        ),
        "below_recent_high": max(
            0.0,
            -pct(entry_price, recent_high),
        ),
        "above_recent_low": max(
            0.0,
            pct(entry_price, recent_low),
        ),
    }


def future_excursions(
    session,
    entry,
    exit_time,
    entry_price,
):
    """
    HINDSIGHT ONLY.

    Intrabar highs and lows are used to describe
    opportunity and risk, not executable trades.

    Includes entry candle and candles beginning
    before the recorded exit time.

    The final candle may extend beyond the exact
    recorded exit instant; these are research
    envelopes, not realizable P&L.
    """

    during_trade = [
        c for c in session
        if entry <= c["time"] < exit_time
    ]

    after_exit = [
        c for c in session
        if exit_time <= c["time"]
    ]

    if during_trade:
        minimum = min(
            c["low"] for c in during_trade
        )

        maximum = max(
            c["high"] for c in during_trade
        )

        mfe = max(
            0.0,
            -pct(minimum, entry_price),
        )

        mae = max(
            0.0,
            pct(maximum, entry_price),
        )
    else:
        mfe = None
        mae = None

    if after_exit:
        after_low = min(
            c["low"] for c in after_exit
        )

        post_exit_favorable = max(
            0.0,
            -pct(after_low, entry_price),
        )
    else:
        post_exit_favorable = None

    return {
        "mfe": mfe,
        "mae": mae,
        "post_exit_favorable": post_exit_favorable,
        "observed_bars": len(during_trade),
        "after_exit_bars": len(after_exit),
    }


def classify_decline(value):
    if value is None:
        return "UNKNOWN"

    if value < 0.5:
        return "DECLINE_UNDER_0_5"

    if value < 1.0:
        return "DECLINE_0_5_TO_1"

    if value < 2.0:
        return "DECLINE_1_TO_2"

    return "DECLINE_2_PLUS"


def classify_recovery(value):
    if value is None:
        return "UNKNOWN"

    if value < 0.2:
        return "RECOVERY_UNDER_0_2"

    if value < 0.5:
        return "RECOVERY_0_2_TO_0_5"

    if value < 1.0:
        return "RECOVERY_0_5_TO_1"

    return "RECOVERY_1_PLUS"


def classify_mfe(value):
    if value is None:
        return "MFE_UNAVAILABLE"

    if value < 0.2:
        return "MFE_UNDER_0_2"

    if value < 0.5:
        return "MFE_0_2_TO_0_5"

    if value < 1.0:
        return "MFE_0_5_TO_1"

    return "MFE_1_PLUS"


def summarize(records, field, title):
    print()
    print(title)

    groups = defaultdict(list)

    for record in records:
        groups[record[field]].append(record)

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
            r["net"] for r in group
        )

        print(
            f"{label:36s} "
            f"N={len(group):2d} "
            f"W={winners:2d} "
            f"L={losers:2d} "
            f"NET={net:+.6f}%"
        )


def audit_line(record):
    return (
        f'{record["dataset"]:10s} '
        f'{record["entry"]} '
        f'EXIT={record["exit"]} '
        f'NET={record["net"]:+.6f}% '
        f'ENTRY_BARS={record["completed_bars"]} '
        f'DECLINE={fmt(record["decline_from_high"])} '
        f'RECOVERY={fmt(record["recovery_from_low"])} '
        f'RECENT_HIGH_DIST={fmt(record["below_recent_high"])} '
        f'RECENT_LOW_DIST={fmt(record["above_recent_low"])} '
        f'MFE={fmt(record["mfe"])} '
        f'MAE={fmt(record["mae"])} '
        f'POST_EXIT_FAVORABLE={fmt(record["post_exit_favorable"])} '
        f'TRADE_BARS={record["observed_bars"]} '
        f'POST_EXIT_BARS={record["after_exit_bars"]}'
    )


def report(name, records, details=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "decline_class",
        "ENTRY-TIME DECLINE FROM SESSION HIGH",
    )

    summarize(
        records,
        "recovery_class",
        "ENTRY-TIME RECOVERY FROM SESSION LOW",
    )

    summarize(
        records,
        "mfe_class",
        "HINDSIGHT MAXIMUM FAVORABLE EXCURSION",
    )

    if details:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-46")
    print(
        "BEARISH LEG PROGRESS AND "
        "REMAINING OPPORTUNITY AUDIT"
    )
    print("READ-ONLY OBSERVATIONAL RESEARCH")

    combined = []

    for name, (
        path,
        expected_count,
        expected_net,
    ) in DATASETS.items():

        rows = load_rows(path)

        result = engine.run(
            rows=rows,
            **PARAMS,
        )

        assert (
            result["trade_count"]
            == expected_count
        ), f"{name}: trade count changed"

        assert abs(
            result["net_pnl_pct"]
            - expected_net
        ) < TOLERANCE, (
            f"{name}: baseline net changed"
        )

        sessions = group_sessions(
            regular_candles(rows)
        )

        records = []

        for trade in result["trades"]:
            entry = parse_time(
                trade["entry_time"]
            )

            exit_time = parse_time(
                trade["exit_time"]
            )

            session = sessions.get(
                entry.date(), []
            )

            context = entry_context(
                session, entry
            )

            excursions = future_excursions(
                session=session,
                entry=entry,
                exit_time=exit_time,
                entry_price=context["entry_price"],
            )

            record = {
                **context,
                **excursions,
                "dataset": name,
                "entry": entry,
                "exit": exit_time,
                "net": float(
                    trade["net_pnl_pct"]
                ),
            }

            record["decline_class"] = (
                classify_decline(
                    record["decline_from_high"]
                )
            )

            record["recovery_class"] = (
                classify_recovery(
                    record["recovery_from_low"]
                )
            )

            record["mfe_class"] = (
                classify_mfe(
                    record["mfe"]
                )
            )

            records.append(record)

        assert len(records) == expected_count

        report(name, records)
        combined.extend(records)

    assert len(combined) == 36

    assert abs(
        sum(r["net"] for r in combined)
        - 8.984294
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
        "MFE and MAE are hindsight intrabar "
        "price envelopes, not executable P&L."
    )
    print(
        "Post-exit opportunity is measured "
        "against entry price, not exit price."
    )
    print(
        "Only same-session candles are included "
        "in excursion calculations."
    )
    print(
        "Trades crossing sessions may have "
        "incomplete excursion coverage."
    )
    print(
        "No filters approved. "
        "No file writes or V18 changes."
    )

    print("STEP 59F-5H-43K-46: PASS")


if __name__ == "__main__":
    main()
