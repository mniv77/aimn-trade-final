
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-37
TRANSITION FOLLOW-THROUGH VS FAILED TRANSITION

NVDA SHORT 5m — READ-ONLY OBSERVATIONAL RESEARCH

Measure price follow-through after the most recent
confirmed 30m structural transition, using only
completed 30m and 5m candles available at entry.

No file writes.
No entry or exit changes.
No V18 modifications.
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
    "2026-08-03",
    "2026-08-21",
    "2026-09-02",
}

EPS = 1e-10


def parse_time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def pct(new, old):
    if old is None or abs(old) < EPS:
        return None
    return (new / old - 1.0) * 100.0


def fmt(value):
    return "NA" if value is None else f"{value:+.4f}%"


def load_rows(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["candles"] if isinstance(data, dict) else data

    rows = sorted(
        rows,
        key=lambda r: parse_time(r["timestamp"]),
    )

    stamps = [parse_time(r["timestamp"]) for r in rows]

    assert len(stamps) == len(set(stamps)), (
        f"Duplicate timestamps in {path}"
    )

    return rows


def regular_candles(rows):
    candles = []

    for r in rows:
        stamp = parse_time(r["timestamp"])

        if not time(9, 30) <= stamp.time() < time(16, 0):
            continue

        candles.append({
            "time": stamp,
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
        })

    return candles


def completed_5m(candles, entry):
    return [
        c for c in candles
        if c["time"] + timedelta(minutes=5) <= entry
    ]


def completed_30m(candles, entry):
    groups = defaultdict(list)

    for c in completed_5m(candles, entry):
        stamp = c["time"]
        minute = (stamp.minute // 30) * 30

        bucket = stamp.replace(
            minute=minute,
            second=0,
            microsecond=0,
        )

        groups[bucket].append(c)

    bars = []

    for start in sorted(groups):
        group = sorted(
            groups[start],
            key=lambda x: x["time"],
        )

        expected = [
            start + timedelta(minutes=5 * i)
            for i in range(6)
        ]

        if [c["time"] for c in group] != expected:
            continue

        end = start + timedelta(minutes=30)

        if end > entry:
            continue

        bars.append({
            "start": start,
            "end": end,
            "open": group[0]["open"],
            "high": max(c["high"] for c in group),
            "low": min(c["low"] for c in group),
            "close": group[-1]["close"],
        })

    return bars


def confirmed_swings(bars):
    highs = []
    lows = []

    for i in range(1, len(bars) - 1):
        left, middle, right = bars[i - 1:i + 2]

        if (
            middle["high"] > left["high"]
            and middle["high"] > right["high"]
        ):
            highs.append({
                "confirmed_index": i + 1,
                "price": middle["high"],
            })

        if (
            middle["low"] < left["low"]
            and middle["low"] < right["low"]
        ):
            lows.append({
                "confirmed_index": i + 1,
                "price": middle["low"],
            })

    return highs, lows


def structure_at(index, highs, lows):
    known_highs = [
        h for h in highs
        if h["confirmed_index"] <= index
    ]
    known_lows = [
        l for l in lows
        if l["confirmed_index"] <= index
    ]

    if len(known_highs) < 2 or len(known_lows) < 2:
        return "UNKNOWN"

    h0 = known_highs[-2]["price"]
    h1 = known_highs[-1]["price"]
    l0 = known_lows[-2]["price"]
    l1 = known_lows[-1]["price"]

    if h1 < h0 and l1 < l0:
        return "BEARISH"

    if h1 > h0 and l1 > l0:
        return "BULLISH"

    if h1 < h0 and l1 > l0:
        return "CONTRACTING"

    if h1 > h0 and l1 < l0:
        return "EXPANDING"

    return "MIXED"


def build_history(bars):
    highs, lows = confirmed_swings(bars)
    history = []

    previous = None

    for i, bar in enumerate(bars):
        state = structure_at(i, highs, lows)

        event = None

        if state != "UNKNOWN":
            if previous is not None and state != previous:
                event = {
                    "index": i,
                    "time": bar["end"],
                    "from": previous,
                    "to": state,
                }

            previous = state

        history.append({
            "index": i,
            "time": bar["end"],
            "state": state,
            "close": bar["close"],
            "event": event,
        })

    return history


def latest_transition(history):
    events = [
        row["event"]
        for row in history
        if row["event"] is not None
    ]

    return events[-1] if events else None


def direction_class(value):
    if value is None:
        return "NO_DATA"

    if value <= -0.50:
        return "DOWN_0_5_PLUS"

    if value <= -0.20:
        return "DOWN_0_2_TO_0_5"

    if value < 0.20:
        return "FLAT_UNDER_0_2"

    if value < 0.50:
        return "UP_0_2_TO_0_5"

    return "UP_0_5_PLUS"


def excursion_class(up, down):
    if up is None or down is None:
        return "NO_DATA"

    if up >= 0.50 and down >= 0.50:
        return "BOTH_DIRECTIONS_0_5_PLUS"

    if down >= 0.50:
        return "DOWN_EXCURSION_0_5_PLUS"

    if up >= 0.50:
        return "UP_EXCURSION_0_5_PLUS"

    return "NO_LARGE_EXCURSION"


def followthrough_class(state, move):
    if move is None:
        return "NO_DATA"

    if abs(move) < 0.20:
        return "NEUTRAL_MOVE"

    if state == "BEARISH":
        return (
            "BEARISH_CONFIRMED_DOWN"
            if move < 0
            else "BEARISH_CONTRADICTED_UP"
        )

    if state == "BULLISH":
        return (
            "BULLISH_CONFIRMED_UP"
            if move > 0
            else "BULLISH_CONTRADICTED_DOWN"
        )

    if state == "CONTRACTING":
        return (
            "CONTRACTING_MOVING_DOWN"
            if move < 0
            else "CONTRACTING_MOVING_UP"
        )

    if state == "EXPANDING":
        return (
            "EXPANDING_MOVING_DOWN"
            if move < 0
            else "EXPANDING_MOVING_UP"
        )

    return "OTHER_STRUCTURE"


def measure(candles, trade):
    entry = parse_time(trade["entry_time"])

    entry_candle = next(
        (c for c in candles if c["time"] == entry),
        None,
    )

    assert entry_candle is not None, (
        f"Missing entry candle: {entry}"
    )

    bars = completed_30m(candles, entry)
    history = build_history(bars)

    state = (
        history[-1]["state"]
        if history else "UNKNOWN"
    )

    event = latest_transition(history)

    path = (
        event["from"] + "_TO_" + event["to"]
        if event else "NO_TRANSITION"
    )

    age = (
        len(bars) - 1 - event["index"]
        if event else None
    )

    if event is not None:
        reference_close = bars[event["index"]]["close"]
        later_bars = bars[event["index"] + 1:]

        completed = completed_5m(candles, entry)

        post_event_5m = [
            c for c in completed
            if c["time"] >= event["time"]
        ]

        observed_closes = [reference_close]
        observed_closes.extend(
            c["close"] for c in post_event_5m
        )

        # Only completed candle closes.
        highest_close = max(observed_closes)
        lowest_close = min(observed_closes)

        entry_move = pct(
            entry_candle["open"],
            reference_close,
        )

        completed_move = (
            pct(observed_closes[-1], reference_close)
            if len(observed_closes) > 1
            else 0.0
        )

        upward_excursion = pct(
            highest_close,
            reference_close,
        )

        downward_excursion = -pct(
            lowest_close,
            reference_close,
        )

        # Maximum favorable/adverse excursion for SHORT
        # measured from transition reference, not entry.
        max_down = max(0.0, downward_excursion)
        max_up = max(0.0, upward_excursion)

        first_two = later_bars[:2]

        first_two_move = (
            pct(first_two[-1]["close"], reference_close)
            if first_two else None
        )

        last_two = later_bars[-2:]

        last_two_move = (
            pct(last_two[-1]["close"], reference_close)
            if last_two else None
        )

    else:
        reference_close = None
        entry_move = None
        completed_move = None
        max_down = None
        max_up = None
        first_two_move = None
        last_two_move = None

    # Local completed 5m price action before entry.
    local = [
        c for c in completed_5m(candles, entry)
        if c["time"].date() == entry.date()
    ]

    if len(local) >= 2:
        local_2_move = pct(
            local[-1]["close"],
            local[-2]["open"],
        )
    else:
        local_2_move = None

    if len(local) >= 3:
        local_3_move = pct(
            local[-1]["close"],
            local[-3]["open"],
        )
    else:
        local_3_move = None

    return {
        "entry": entry,
        "net": float(trade["net_pnl_pct"]),
        "state": state,
        "path": path,
        "age": age,
        "reference_close": reference_close,
        "entry_move": entry_move,
        "completed_move": completed_move,
        "first_two_move": first_two_move,
        "last_two_move": last_two_move,
        "max_down": max_down,
        "max_up": max_up,
        "entry_move_class": direction_class(entry_move),
        "followthrough": followthrough_class(
            state,
            entry_move,
        ),
        "excursion_class": excursion_class(
            max_up,
            max_down,
        ),
        "local_2_move": local_2_move,
        "local_3_move": local_3_move,
        "local_3_class": direction_class(local_3_move),
        "completed_30m": len(bars),
    }


def summarize(records, key, title):
    print()
    print(title)

    groups = defaultdict(list)

    for r in records:
        groups[r[key]].append(r)

    for label, group in sorted(groups.items()):
        wins = sum(r["net"] > 0 for r in group)
        losses = sum(r["net"] < 0 for r in group)
        net = sum(r["net"] for r in group)

        print(
            f"{str(label):42s} "
            f"N={len(group):2d} "
            f"W={wins:2d} "
            f"L={losses:2d} "
            f"NET={net:+.6f}%"
        )


def audit_line(r):
    return (
        f'{r["dataset"]:10s} '
        f'{r["entry"]} '
        f'NET={r["net"]:+.6f}% '
        f'STATE={r["state"]} '
        f'PATH={r["path"]} '
        f'AGE={r["age"]} '
        f'ENTRY_MOVE={fmt(r["entry_move"])} '
        f'COMPLETED_MOVE={fmt(r["completed_move"])} '
        f'FIRST_TWO_30M={fmt(r["first_two_move"])} '
        f'LAST_TWO_30M={fmt(r["last_two_move"])} '
        f'MAX_DOWN={fmt(r["max_down"])} '
        f'MAX_UP={fmt(r["max_up"])} '
        f'LOCAL_2={fmt(r["local_2_move"])} '
        f'LOCAL_3={fmt(r["local_3_move"])} '
        f'FOLLOW={r["followthrough"]} '
        f'EXCURSION={r["excursion_class"]}'
    )


def report(name, records, detailed=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "followthrough",
        "STRUCTURE VS PRICE FOLLOW-THROUGH",
    )

    summarize(
        records,
        "entry_move_class",
        "PRICE MOVE SINCE LATEST TRANSITION",
    )

    summarize(
        records,
        "excursion_class",
        "POST-TRANSITION PRICE EXCURSIONS",
    )

    summarize(
        records,
        "local_3_class",
        "LAST THREE COMPLETED 5M CANDLES",
    )

    if detailed:
        print()
        print("TRADE AUDIT")

        for r in records:
            print(audit_line(r))


def main():
    print("AIMn — STEP 59F-5H-43K-37")
    print("TRANSITION FOLLOW-THROUGH VS FAILED TRANSITION")
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

        assert result["trade_count"] == expected_count, (
            f"{name}: baseline trade count changed"
        )

        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < 0.000002, (
            f"{name}: baseline net changed"
        )

        candles = regular_candles(rows)
        records = []

        for trade in result["trades"]:
            r = measure(candles, trade)
            r["dataset"] = name
            records.append(r)

        assert len(records) == expected_count

        report(name, records)
        combined.extend(records)

    assert len(combined) == 36

    assert abs(
        sum(r["net"] for r in combined) - 8.984294
    ) < 0.000002

    report(
        "COMBINED — DESCRIPTIVE ONLY",
        combined,
        detailed=False,
    )

    print()
    print("PRIORITY CASES")

    for r in combined:
        if str(r["entry"].date()) in PRIORITY_DATES:
            print(audit_line(r))

    print()
    print("LIMITATIONS:")
    print(
        "Transition reference is the completed 30m "
        "close at the confirmed state change."
    )
    print(
        "Entry price position uses entry candle OPEN; "
        "current candle high/low/close are excluded."
    )
    print(
        "Post-transition excursions use only "
        "completed 5m candle closes."
    )
    print(
        "30m transitions can be old and can span "
        "multiple sessions."
    )
    print(
        "Descriptive analysis only; no filters approved."
    )
    print(
        "No file writes, no trading changes, "
        "no V18 modifications."
    )

    print("STEP 59F-5H-43K-37: PASS")


if __name__ == "__main__":
    main()
