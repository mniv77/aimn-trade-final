
"""AIMn Step 59F-5H-43K-24
Previous-day 30m context and market opening.
Read-only V18 research audit.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

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
        22, 6.764673
    ),
    "VALIDATION": (
        LAB / "nvda_sep_oct_2026_validation.json",
        14, 2.219621
    ),
}

def dt(value):
    return datetime.fromisoformat(str(value))

def percent(new, old):
    if old <= 0:
        return None
    return (new / old - 1) * 100

def fmt(value):
    return "N/A" if value is None else f"{value:+.4f}%"

def load_rows(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw["candles"] if isinstance(raw, dict) else raw
    rows = sorted(rows, key=lambda r: dt(r["timestamp"]))

    times = [dt(r["timestamp"]) for r in rows]
    assert len(times) == len(set(times)), "Duplicate timestamps"
    return rows

def session_rows(rows, date):
    return [
        r for r in rows
        if dt(r["timestamp"]).date() == date
    ]

def previous_session(rows, entry_time):
    dates = sorted({
        dt(r["timestamp"]).date()
        for r in rows
        if dt(r["timestamp"]).date() < entry_time.date()
    })
    if not dates:
        return None, []
    previous_date = dates[-1]
    return previous_date, session_rows(rows, previous_date)

def complete_30m(rows, cutoff=None):
    """Only full six-candle bars starting at 9:30.
    Timestamp represents the START of each 5m candle.
    """
    groups = {}

    for r in rows:
        t = dt(r["timestamp"])
        if cutoff is not None and t >= cutoff:
            continue

        minutes = t.hour * 60 + t.minute
        offset = minutes - (9 * 60 + 30)

        if offset < 0 or offset >= 390:
            continue

        start = t - timedelta(minutes=offset % 30)

        if cutoff is not None:
            if start + timedelta(minutes=30) > cutoff:
                continue

        groups.setdefault(start, []).append(r)

    bars = []

    for start in sorted(groups):
        group = sorted(
            groups[start],
            key=lambda r: dt(r["timestamp"])
        )

        expected = [
            start + timedelta(minutes=5*i)
            for i in range(6)
        ]

        actual = [dt(r["timestamp"]) for r in group]

        if actual != expected:
            continue

        bars.append({
            "start": start,
            "open": float(group[0]["open"]),
            "close": float(group[-1]["close"]),
            "high": max(float(r["high"]) for r in group),
            "low": min(float(r["low"]) for r in group),
        })

    return bars

def trend(bars):
    if len(bars) < 3:
        return "UNKNOWN", None

    closes = [b["close"] for b in bars[-3:]]
    a = percent(closes[1], closes[0])
    b = percent(closes[2], closes[1])

    if a > 0 and b > 0:
        return "UP_CONTINUATION", (a, b)
    if a < 0 and b < 0:
        return "DOWN_CONTINUATION", (a, b)
    if a > 0 and b < 0:
        return "UP_TO_DOWN", (a, b)
    if a < 0 and b > 0:
        return "DOWN_TO_UP", (a, b)

    return "FLAT_OR_MIXED", (a, b)

def gap_class(gap):
    if gap is None:
        return "GAP_UNKNOWN"
    if gap > 0:
        return "GAP_UP"
    if gap < 0:
        return "GAP_DOWN"
    return "GAP_FLAT"

def early_5m(rows, entry_time):
    prior = [
        r for r in rows
        if dt(r["timestamp"]) < entry_time
    ]

    if not prior:
        return "NO_COMPLETED_5M", None

    first = float(rows[0]["open"])
    latest = float(prior[-1]["close"])
    change = percent(latest, first)

    if change > 0:
        return "OPEN_TO_ENTRY_UP", change
    if change < 0:
        return "OPEN_TO_ENTRY_DOWN", change

    return "OPEN_TO_ENTRY_FLAT", change

def summarize(label, records):
    print("\n" + "=" * 105)
    print(label)
    print("=" * 105)

    for field in (
        "yesterday_trend",
        "gap_class",
        "today_30m",
        "opening_move",
    ):
        print("\n" + field.upper())

        for value in sorted(set(r[field] for r in records)):
            group = [
                r for r in records if r[field] == value
            ]

            wins = sum(r["net"] > 0 for r in group)
            losses = sum(r["net"] < 0 for r in group)
            net = sum(r["net"] for r in group)

            print(
                f"{value:28s} "
                f"N={len(group):2d} "
                f"W={wins:2d} L={losses:2d} "
                f"NET={net:+.6f}%"
            )

    print("\nOPENING / PREVIOUS-DAY COMBINATIONS")

    combinations = sorted({
        (r["yesterday_trend"], r["gap_class"])
        for r in records
    })

    for previous, gap in combinations:
        group = [
            r for r in records
            if r["yesterday_trend"] == previous
            and r["gap_class"] == gap
        ]

        wins = sum(r["net"] > 0 for r in group)
        losses = sum(r["net"] < 0 for r in group)

        print(
            f"{previous:22s} / {gap:10s} "
            f"N={len(group):2d} "
            f"W={wins:2d} L={losses:2d} "
            f"NET={sum(r['net'] for r in group):+.6f}%"
        )

    print("\nTRADE-BY-TRADE AUDIT")

    for r in records:
        print(
            r["entry"],
            f"NET={r['net']:+.6f}%",
            "PREV_DATE=" + str(r["previous_date"]),
            "PREV30=" + r["yesterday_trend"],
            "PREV_BARS=" + str(r["previous_bars"]),
            "GAP=" + fmt(r["gap_pct"]),
            "GAP_CLASS=" + r["gap_class"],
            "TODAY30=" + r["today_30m"],
            "OPEN_MOVE=" + r["opening_move"],
            "OPEN_CHANGE=" + fmt(r["opening_pct"]),
        )

def main():
    print("AIMn — STEP 59F-5H-43K-24")
    print("PREVIOUS-DAY 30M CONTEXT AND MARKET OPENING")
    print("READ-ONLY OBSERVATIONAL AUDIT")

    combined = []
    combined_net = 0.0

    for name, (path, expected_count, expected_net) in DATASETS.items():
        rows = load_rows(path)
        result = engine.run(rows=rows, **PARAMS)

        assert result["trade_count"] == expected_count
        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < 0.000002

        index = {
            dt(r["timestamp"]): i
            for i, r in enumerate(rows)
        }

        records = []

        for trade in result["trades"]:
            entry_time = dt(trade["entry_time"])
            assert entry_time in index

            i = index[entry_time]
            entry_open = float(rows[i]["open"])
            execution = float(trade["entry_price"])

            assert entry_open > 0 and execution > 0
            assert abs(
                (1 - execution / entry_open) * 100
                - PARAMS["entry_slippage_pct"]
            ) < 0.0001

            previous_date, yesterday = previous_session(
                rows, entry_time
            )

            today = [
                r for r in rows
                if dt(r["timestamp"]).date()
                == entry_time.date()
                and dt(r["timestamp"]) <= entry_time
            ]

            assert today, "Entry session missing"

            yesterday_bars = complete_30m(yesterday)
            today_bars = complete_30m(
                today, cutoff=entry_time
            )

            yesterday_state, yesterday_steps = trend(
                yesterday_bars
            )

            today_state, today_steps = trend(today_bars)

            gap = None
            if yesterday:
                prev_close = float(yesterday[-1]["close"])
                today_open = float(today[0]["open"])
                gap = percent(today_open, prev_close)

            opening_state, opening_pct = early_5m(
                today, entry_time
            )

            record = {
                "dataset": name,
                "entry": str(entry_time),
                "net": float(trade["net_pnl_pct"]),
                "previous_date": str(previous_date),
                "previous_bars": len(yesterday_bars),
                "yesterday_trend": yesterday_state,
                "yesterday_steps": yesterday_steps,
                "gap_pct": gap,
                "gap_class": gap_class(gap),
                "today_30m": today_state,
                "today_steps": today_steps,
                "opening_move": opening_state,
                "opening_pct": opening_pct,
            }

            records.append(record)

        assert len(records) == expected_count

        summarize(name, records)
        combined.extend(records)
        combined_net += result["net_pnl_pct"]

    assert len(combined) == 36
    assert abs(combined_net - 8.984294) < 0.000002

    summarize("COMBINED — DESCRIPTIVE ONLY", combined)

    print("\nIMPORTANT LIMITATIONS:")
    print("Previous-day context is not a confirmed major trend.")
    print("Opening gap is measured separately from intraday movement.")
    print("The last available prior date may be a dataset boundary.")
    print("Only completed pre-entry 5m and 30m bars are used.")
    print("No future candles used in entry classification.")
    print("No new filters or thresholds.")
    print("V18 unchanged. No files created or modified.")
    print("STEP 59F-5H-43K-24: PASS")

if __name__ == "__main__":
    main()
