
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-36
ACTIVE TRANSITION LIFECYCLE

NVDA SHORT 5m — READ-ONLY RESEARCH

Reconstruct confirmed 30m structural states through time.
Compare lifecycle, transition age, and recent structure
sequence with existing SHORT trade outcomes.

No trading changes. No file writes.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, time
from collections import defaultdict, Counter

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

STATE_NAMES = {
    "BEARISH_LH_LL": "BEARISH",
    "BULLISH_HH_HL": "BULLISH",
    "CONTRACTING": "CONTRACTING",
    "EXPANDING": "EXPANDING",
    "EQUAL_OR_MIXED": "MIXED",
    "INSUFFICIENT_STRUCTURE": "UNKNOWN",
}


def parse_time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def pct(new, old):
    if old is None or old == 0:
        return None
    return (new / old - 1.0) * 100.0


def fmt_pct(value):
    if value is None:
        return "NA"
    return f"{value:+.4f}%"


def load_rows(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["candles"] if isinstance(data, dict) else data

    rows = sorted(
        rows,
        key=lambda r: parse_time(r["timestamp"]),
    )

    times = [parse_time(r["timestamp"]) for r in rows]
    assert len(times) == len(set(times)), (
        f"Duplicate timestamps: {path}"
    )
    return rows


def regular_candles(rows):
    output = []
    for row in rows:
        stamp = parse_time(row["timestamp"])
        if time(9, 30) <= stamp.time() < time(16, 0):
            output.append({
                "time": stamp,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })
    return output


def build_30m(candles, entry):
    groups = defaultdict(list)

    for c in candles:
        stamp = c["time"]

        if stamp + timedelta(minutes=5) > entry:
            continue

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
        a, b, c = bars[i - 1:i + 2]

        if b["high"] > a["high"] and b["high"] > c["high"]:
            highs.append({
                "index": i,
                "price": b["high"],
                "confirmed_index": i + 1,
                "confirmed_time": c["end"],
            })

        if b["low"] < a["low"] and b["low"] < c["low"]:
            lows.append({
                "index": i,
                "price": b["low"],
                "confirmed_index": i + 1,
                "confirmed_time": c["end"],
            })

    return highs, lows


def state_at(index, highs, lows):
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

    high_now = known_highs[-1]["price"]
    high_prev = known_highs[-2]["price"]
    low_now = known_lows[-1]["price"]
    low_prev = known_lows[-2]["price"]

    if high_now < high_prev and low_now < low_prev:
        return "BEARISH"

    if high_now > high_prev and low_now > low_prev:
        return "BULLISH"

    if high_now < high_prev and low_now > low_prev:
        return "CONTRACTING"

    if high_now > high_prev and low_now < low_prev:
        return "EXPANDING"

    return "MIXED"


def state_history(bars):
    highs, lows = confirmed_swings(bars)

    history = []

    for i, bar in enumerate(bars):
        history.append({
            "index": i,
            "time": bar["end"],
            "state": state_at(i, highs, lows),
            "close": bar["close"],
        })

    return history


def transitions(history):
    events = []

    previous = None

    for row in history:
        current = row["state"]

        if current == "UNKNOWN":
            continue

        if previous is None:
            previous = current
            continue

        if current != previous:
            events.append({
                "index": row["index"],
                "time": row["time"],
                "from": previous,
                "to": current,
            })

        previous = current

    return events


def classify_lifecycle(state, latest_event):
    if state == "BEARISH":
        if latest_event is None:
            return "BEARISH_NO_KNOWN_TRANSITION"
        if latest_event["to"] == "BEARISH":
            return "BEARISH_AFTER_TRANSITION"
        return "BEARISH_OTHER"

    if state == "BULLISH":
        return "BULLISH_STRUCTURE"

    if state == "CONTRACTING":
        return "CONTRACTING_STRUCTURE"

    if state == "EXPANDING":
        return "EXPANDING_STRUCTURE"

    return "UNKNOWN_OR_MIXED"


def classify_age(age):
    if age is None:
        return "NO_TRANSITION"

    if age <= 2:
        return "FRESH_0_TO_2"

    if age <= 6:
        return "RECENT_3_TO_6"

    return "OLD_7_PLUS"


def classify_transition_path(event):
    if event is None:
        return "NO_TRANSITION"

    return event["from"] + "_TO_" + event["to"]


def classify_recent_path(events):
    if not events:
        return "NO_TRANSITION"

    last = events[-2:]

    return " | ".join(
        e["from"] + ">" + e["to"]
        for e in last
    )


def measure(candles, trade):
    entry = parse_time(trade["entry_time"])

    entry_candle = next(
        (c for c in candles if c["time"] == entry),
        None,
    )
    assert entry_candle is not None, (
        f"Missing entry candle {entry}"
    )

    bars = build_30m(candles, entry)
    history = state_history(bars)
    events = transitions(history)

    state = history[-1]["state"] if history else "UNKNOWN"

    latest_event = events[-1] if events else None

    age = (
        len(bars) - 1 - latest_event["index"]
        if latest_event else None
    )

    bearish_events = [
        e for e in events if e["to"] == "BEARISH"
    ]

    last_bearish = (
        bearish_events[-1] if bearish_events else None
    )

    bearish_age = (
        len(bars) - 1 - last_bearish["index"]
        if last_bearish else None
    )

    completed_today = [
        c for c in candles
        if c["time"].date() == entry.date()
        and c["time"] + timedelta(minutes=5) <= entry
    ]

    if completed_today:
        last_5m = completed_today[-1]
        local_body = pct(
            last_5m["close"],
            last_5m["open"],
        )
    else:
        local_body = None

    return {
        "entry": entry,
        "net": float(trade["net_pnl_pct"]),
        "state": state,
        "lifecycle": classify_lifecycle(
            state,
            latest_event,
        ),
        "transition_path": classify_transition_path(
            latest_event
        ),
        "recent_path": classify_recent_path(events),
        "transition_age": age,
        "transition_age_class": classify_age(age),
        "last_bearish_age": bearish_age,
        "last_bearish_age_class": classify_age(
            bearish_age
        ),
        "local_body": local_body,
        "completed_30m": len(bars),
        "transition_count": len(events),
    }


def summarize(records, key, heading):
    print()
    print(heading)

    groups = defaultdict(list)

    for record in records:
        groups[record[key]].append(record)

    for label, group in sorted(groups.items()):
        winners = sum(r["net"] > 0 for r in group)
        losers = sum(r["net"] < 0 for r in group)
        net = sum(r["net"] for r in group)

        print(
            f"{str(label):44s} "
            f"N={len(group):2d} "
            f"W={winners:2d} "
            f"L={losers:2d} "
            f"NET={net:+.6f}%"
        )


def audit_line(r):
    return (
        f'{r["dataset"]:10s} '
        f'{r["entry"]} '
        f'NET={r["net"]:+.6f}% '
        f'STATE={r["state"]} '
        f'LIFECYCLE={r["lifecycle"]} '
        f'LAST_PATH={r["transition_path"]} '
        f'RECENT_PATH={r["recent_path"]} '
        f'AGE={r["transition_age"]} '
        f'BEARISH_AGE={r["last_bearish_age"]} '
        f'LAST_5M_BODY={fmt_pct(r["local_body"])} '
        f'TRANSITIONS={r["transition_count"]} '
        f'COMPLETED30M={r["completed_30m"]}'
    )


def report(name, records, detailed=True):
    print()
    print("=" * 108)
    print(name)
    print("=" * 108)

    summarize(
        records,
        "lifecycle",
        "ACTIVE STRUCTURAL LIFECYCLE",
    )

    summarize(
        records,
        "transition_path",
        "LATEST CONFIRMED STRUCTURAL TRANSITION",
    )

    summarize(
        records,
        "transition_age_class",
        "AGE OF LATEST STRUCTURAL TRANSITION",
    )

    summarize(
        records,
        "last_bearish_age_class",
        "AGE SINCE LAST TRANSITION INTO BEARISH",
    )

    if detailed:
        print()
        print("TRADE AUDIT")

        for record in records:
            print(audit_line(record))


def main():
    print("AIMn — STEP 59F-5H-43K-36")
    print("ACTIVE TRANSITION LIFECYCLE")
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
            record = measure(candles, trade)
            record["dataset"] = name
            records.append(record)

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

    for record in combined:
        if str(record["entry"].date()) in PRIORITY_DATES:
            print(audit_line(record))

    print()
    print("LIMITATIONS:")
    print(
        "Structural states use confirmed 30m swings "
        "with one completed right-hand bar."
    )
    print(
        "Transitions are state changes, not necessarily "
        "the exact price reversal candle."
    )
    print(
        "Transition ages count completed 30m bars "
        "and may span multiple sessions."
    )
    print(
        "No current entry candle high, low, or close "
        "is used."
    )
    print(
        "No new filters, no trading changes, "
        "no V18 modifications."
    )

    print("STEP 59F-5H-43K-36: PASS")


if __name__ == "__main__":
    main()
