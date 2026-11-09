
#!/usr/bin/env python3
"""
AIMn STEP 59F-5H-43K-33
OPENING SESSION AND PRIOR-DAY STRUCTURE

NVDA SHORT 5m / V18 baseline.

READ-ONLY OBSERVATIONAL RESEARCH.

Features:
- Previous completed regular session OHLC
- Opening gap vs previous close
- Entry price position vs previous-day range
- Opening move up to entry
- Completed current-session extremes
- Confirmed prior 30m swing structure
- Opening vs later entry comparison

NO FUTURE DATA.
NO FILE WRITES.
NO V18 MODIFICATIONS.
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

PRIORITY = {
    "2026-07-06",
    "2026-07-24",
    "2026-08-03",
    "2026-08-21",
    "2026-09-02",
}


def dt(value):
    return datetime.fromisoformat(str(value))


def pct(new, old):
    if old is None or old == 0:
        return None
    return (new / old - 1.0) * 100.0


def fmt(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def number(value):
    if value is None:
        return "NA"
    return f"{value:.4f}"


def load(path):
    obj = json.loads(path.read_text(encoding="utf-8"))
    rows = obj["candles"] if isinstance(obj, dict) else obj

    rows = sorted(rows, key=lambda r: dt(r["timestamp"]))

    stamps = [dt(r["timestamp"]) for r in rows]

    assert len(stamps) == len(set(stamps)), (
        "Duplicate candle timestamps"
    )

    return rows


def regular_sessions(rows):
    """
    Group regular-market 5m candles by session date.
    Exclude premarket and after-hours data.
    """

    sessions = defaultdict(list)

    for row in rows:
        stamp = dt(row["timestamp"])

        if time(9, 30) <= stamp.time() < time(16, 0):
            sessions[stamp.date()].append(row)

    return dict(sessions)


def session_ohlc(rows):
    if not rows:
        return None

    return {
        "open": float(rows[0]["open"]),
        "high": max(float(r["high"]) for r in rows),
        "low": min(float(r["low"]) for r in rows),
        "close": float(rows[-1]["close"]),
        "count": len(rows),
    }


def completed_previous_session(sessions, day):
    """
    Previous available full regular session.

    A full standard US stock session contains
    78 consecutive 5m candles.

    Partial days are excluded from the
    previous-session reference.
    """

    previous_days = sorted(
        d for d in sessions
        if d < day
    )

    for previous_day in reversed(previous_days):
        rows = sessions[previous_day]

        if len(rows) != 78:
            continue

        stamps = [
            dt(r["timestamp"])
            for r in rows
        ]

        if stamps[0].time() != time(9, 30):
            continue

        if stamps[-1].time() != time(15, 55):
            continue

        if any(
            stamps[i] - stamps[i - 1]
            != timedelta(minutes=5)
            for i in range(1, len(stamps))
        ):
            continue

        return previous_day, session_ohlc(rows)

    return None, None


def build_30m(rows):
    """
    Six consecutive 5m candles form one 30m bar.
    Only complete 30m bars are included.
    """

    groups = defaultdict(dict)

    for row in rows:
        stamp = dt(row["timestamp"])

        if not (
            time(9, 30) <= stamp.time() < time(16, 0)
        ):
            continue

        minutes = (
            (stamp.hour - 9) * 60
            + stamp.minute - 30
        )

        bucket = minutes // 30
        slot = (minutes % 30) // 5

        groups[(stamp.date(), bucket)][slot] = row

    bars = []

    for (day, bucket), slots in sorted(groups.items()):
        if set(slots) != set(range(6)):
            continue

        candles = [slots[i] for i in range(6)]

        start = dt(candles[0]["timestamp"])

        bars.append({
            "start": start,
            "end": start + timedelta(minutes=30),
            "high": max(float(c["high"]) for c in candles),
            "low": min(float(c["low"]) for c in candles),
            "close": float(candles[-1]["close"]),
        })

    return bars


def prior_30m_structure(bars, entry):
    """
    Classify confirmed 30m swing structure
    using completed bars strictly before entry.

    Swing confirmation requires one later
    completed 30m bar.
    """

    prior = [
        b for b in bars
        if b["end"] <= entry
    ][-20:]

    highs = []
    lows = []

    for i in range(1, len(prior) - 1):
        a = prior[i - 1]
        b = prior[i]
        c = prior[i + 1]

        if b["high"] > a["high"] and b["high"] > c["high"]:
            highs.append(b["high"])

        if b["low"] < a["low"] and b["low"] < c["low"]:
            lows.append(b["low"])

    if len(highs) < 2 or len(lows) < 2:
        return "INSUFFICIENT_SWINGS"

    high_pattern = (
        "HH" if highs[-1] > highs[-2]
        else "LH" if highs[-1] < highs[-2]
        else "EH"
    )

    low_pattern = (
        "HL" if lows[-1] > lows[-2]
        else "LL" if lows[-1] < lows[-2]
        else "EL"
    )

    if high_pattern == "HH" and low_pattern == "HL":
        return "BULLISH_HH_HL"

    if high_pattern == "LH" and low_pattern == "LL":
        return "BEARISH_LH_LL"

    if high_pattern == "LH" and low_pattern == "HL":
        return "CONTRACTING"

    if high_pattern == "HH" and low_pattern == "LL":
        return "EXPANDING"

    return "MIXED_TRANSITION"


def classify_gap(value):
    if value is None:
        return "UNKNOWN"

    if value >= 0.5:
        return "GAP_UP_0_50_PLUS"

    if value <= -0.5:
        return "GAP_DOWN_0_50_PLUS"

    return "SMALL_GAP"


def classify_position(value):
    if value is None:
        return "UNKNOWN"

    if value < 0.25:
        return "BELOW_LOWER_QUARTER"

    if value > 0.75:
        return "ABOVE_UPPER_QUARTER"

    return "MIDDLE_HALF"


def classify_open_move(value):
    if value is None:
        return "UNKNOWN"

    if value <= -0.5:
        return "DOWN_0_50_PLUS"

    if value <= -0.2:
        return "DOWN_0_20_TO_0_50"

    if value >= 0.2:
        return "UP_0_20_PLUS"

    return "NEAR_OPEN"


def classify_entry_time(entry):
    minutes = (
        (entry.hour - 9) * 60
        + entry.minute - 30
    )

    if minutes < 30:
        return "OPENING_30_MIN"

    if minutes < 60:
        return "OPENING_30_TO_60"

    return "AFTER_FIRST_HOUR"


def measure(rows, sessions, bars30, entry):
    day = entry.date()

    previous_day, previous = completed_previous_session(
        sessions,
        day,
    )

    today = sessions.get(day, [])

    # Only fully completed candles before entry.
    completed_today = [
        r for r in today
        if (
            dt(r["timestamp"]) + timedelta(minutes=5)
            <= entry
        )
    ]

    # The current session's opening price is
    # available from 09:30 onward.
    opening_price = (
        float(today[0]["open"])
        if today
        and dt(today[0]["timestamp"]).time() == time(9, 30)
        else None
    )

    entry_row = next(
        (
            r for r in today
            if dt(r["timestamp"]) == entry
        ),
        None,
    )

    assert entry_row is not None, (
        f"Entry candle missing: {entry}"
    )

    # Entry candle OPEN is available at entry.
    entry_open = float(entry_row["open"])

    gap = None
    previous_position = None
    previous_range = None

    if previous is not None:
        previous_range = (
            previous["high"] - previous["low"]
        )

        if opening_price is not None:
            gap = pct(
                opening_price,
                previous["close"],
            )

        if previous_range > 0:
            previous_position = (
                entry_open - previous["low"]
            ) / previous_range

    opening_move = (
        pct(entry_open, opening_price)
        if opening_price is not None
        else None
    )

    completed_high = (
        max(float(r["high"]) for r in completed_today)
        if completed_today else None
    )

    completed_low = (
        min(float(r["low"]) for r in completed_today)
        if completed_today else None
    )

    drop_from_completed_high = (
        100.0 * (
            completed_high - entry_open
        ) / completed_high
        if completed_high is not None
        else None
    )

    rise_from_completed_low = (
        pct(entry_open, completed_low)
        if completed_low is not None
        else None
    )

    return {
        "previous_day": (
            str(previous_day)
            if previous_day else "NONE"
        ),
        "previous_close": (
            previous["close"]
            if previous else None
        ),
        "gap": gap,
        "gap_class": classify_gap(gap),
        "position": previous_position,
        "position_class": classify_position(
            previous_position
        ),
        "opening_move": opening_move,
        "opening_class": classify_open_move(
            opening_move
        ),
        "completed_high": completed_high,
        "completed_low": completed_low,
        "drop_from_high": drop_from_completed_high,
        "rise_from_low": rise_from_completed_low,
        "completed_count": len(completed_today),
        "entry_period": classify_entry_time(entry),
        "structure30": prior_30m_structure(
            bars30,
            entry,
        ),
    }


def summarize(records, key, title):
    print()
    print(title)

    groups = defaultdict(list)

    for r in records:
        groups[r[key]].append(r)

    for label, group in sorted(groups.items()):
        winners = sum(r["net"] > 0 for r in group)
        losers = sum(r["net"] < 0 for r in group)
        net = sum(r["net"] for r in group)

        print(
            f"{label:32s} "
            f"N={len(group):2d} "
            f"W={winners:2d} "
            f"L={losers:2d} "
            f"NET={net:+.6f}%"
        )


def report(name, records, detailed=True):
    print()
    print("=" * 105)
    print(name)
    print("=" * 105)

    summarize(
        records,
        "entry_period",
        "ENTRY PERIOD",
    )

    summarize(
        records,
        "gap_class",
        "OPENING GAP",
    )

    summarize(
        records,
        "position_class",
        "ENTRY POSITION VS PREVIOUS-DAY RANGE",
    )

    summarize(
        records,
        "opening_class",
        "OPEN-TO-ENTRY PRICE MOVEMENT",
    )

    summarize(
        records,
        "structure30",
        "CONFIRMED 30M STRUCTURE AT ENTRY",
    )

    if detailed:
        print()
        print("TRADE AUDIT")

        for r in records:
            print(
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'PERIOD={r["entry_period"]} '
                f'PREV_DAY={r["previous_day"]} '
                f'GAP={fmt(r["gap"])} '
                f'POSITION={number(r["position"])} '
                f'OPEN_MOVE={fmt(r["opening_move"])} '
                f'FROM_HIGH={fmt(r["drop_from_high"])} '
                f'FROM_LOW={fmt(r["rise_from_low"])} '
                f'30M={r["structure30"]} '
                f'COMPLETED5M={r["completed_count"]}'
            )


def main():
    print("AIMn — STEP 59F-5H-43K-33")
    print("OPENING SESSION AND PRIOR-DAY STRUCTURE")
    print("READ-ONLY OBSERVATIONAL RESEARCH")

    combined = []

    for name, (
        path,
        expected_count,
        expected_net,
    ) in DATASETS.items():

        rows = load(path)

        result = engine.run(
            rows=rows,
            **PARAMS,
        )

        assert (
            result["trade_count"] == expected_count
        ), f"{name}: baseline trade count changed"

        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < 0.000002, (
            f"{name}: baseline net changed"
        )

        sessions = regular_sessions(rows)
        bars30 = build_30m(rows)

        records = []

        for trade in result["trades"]:
            entry = dt(trade["entry_time"])

            metrics = measure(
                rows,
                sessions,
                bars30,
                entry,
            )

            records.append({
                "dataset": name,
                "time": str(entry),
                "net": float(trade["net_pnl_pct"]),
                **metrics,
            })

        assert len(records) == expected_count

        report(name, records)
        combined.extend(records)

    assert len(combined) == 36

    assert abs(
        sum(r["net"] for r in combined)
        - 8.984294
    ) < 0.000002

    report(
        "COMBINED — DESCRIPTIVE ONLY",
        combined,
        detailed=False,
    )

    print()
    print("PRIORITY CASES")

    for r in combined:
        if r["time"][:10] in PRIORITY:
            print(
                f'{r["dataset"]:10s} '
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'PERIOD={r["entry_period"]} '
                f'GAP={fmt(r["gap"])} '
                f'POSITION={number(r["position"])} '
                f'OPEN_MOVE={fmt(r["opening_move"])} '
                f'FROM_HIGH={fmt(r["drop_from_high"])} '
                f'30M={r["structure30"]}'
            )

    print()
    print("LIMITATIONS:")
    print(
        "Previous-day reference requires a complete "
        "78-candle regular session."
    )
    print(
        "Early closes and incomplete sessions are "
        "excluded from the reference."
    )
    print(
        "Opening gap and entry price use available "
        "opening prices, not future candle closes."
    )
    print(
        "Only fully completed 5m and 30m bars "
        "are used for historical structure."
    )
    print(
        "No V18 changes or entry filters."
    )

    print("STEP 59F-5H-43K-33: PASS")


if __name__ == "__main__":
    main()
