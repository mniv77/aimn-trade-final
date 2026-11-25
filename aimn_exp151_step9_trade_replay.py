# aimn_exp151_step9_trade_replay.py
#!/usr/bin/env python3
"""
EXP151 STEP 9
Full trade-state replay and execution causality audit.

READ ONLY
NO FILE WRITES
NO ORDERS
NO PRODUCTION MODIFICATIONS

Compares completed trades from full-history simulation
against simulations stopped at historical checkpoints.

DATA_END is excluded because it is an artificial
end-of-input liquidation, not a real trading signal.
"""

from pathlib import Path
from collections import Counter
import hashlib
import inspect
import json
import textwrap
import traceback

import aimn_exp135_breakout_confirmation as e


ROOT = Path("kiss/visual_research")

DATASETS = [
    ("NVDA", "JUN_AUG",
     ROOT / "aimn_nvda_candles.json"),

    ("AAPL", "JUN_AUG",
     ROOT / "aimn_aapl_candles.json"),

    ("NVDA", "SEP_OCT",
     ROOT / "independent_holdout_exp127" /
     "nvda_sep_oct_2026_5m_iex.json"),

    ("AAPL", "SEP_OCT",
     ROOT / "independent_holdout_exp127" /
     "aapl_sep_oct_2026_5m_iex.json"),

    ("NVDA", "NOV",
     ROOT / "independent_holdout_exp144" /
     "nvda_nov_2026_5m_iex.json"),

    ("AAPL", "NOV",
     ROOT / "independent_holdout_exp144" /
     "aapl_nov_2026_5m_iex.json"),
]

EXPECTED_SIM_HASH = (
    "b5567c79fdc9aa6e4b6a1df4c5ee8d530a37287688239be4b3a15fb6194d39e5"
)

EXPECTED_PREPARE_HASH = (
    "595e3ea494d27f6c573a25870ed3ee4b11e5a1c9e65bf0a1eea006289b5a55cc"
)

VALIDATION_START = "2026-11-16"

print("=" * 100)
print("EXP151 STEP 9 - FULL TRADE-STATE REPLAY")
print("READ ONLY | NO ORDERS | NO FILE WRITES")
print("=" * 100)


def digest(source):
    return hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()


def prepare_rows(rows):
    times = [str(r["timestamp"]) for r in rows]
    closes = [float(r["close"]) for r in rows]

    starts = e.exp129.swing.get_session_starts(times)

    ph, pl, counts = e.exp129.swing.confirmed_pivots(
        rows, times, starts
    )

    states = [
        e.exp129.swing.structure(
            rows, times, starts, i, ph, pl, counts
        )
        for i in range(len(rows))
    ]

    st = e.exp129.base.calculate_supertrend(
        rows, atr_period=10, multiplier=3.0
    )["st_trend"].tolist()

    rsi = e.exp129.base.rsi_wilder(closes)

    market = [
        e.exp129.base.get_market_state(closes, i)
        for i in range(len(rows))
    ]

    return states, st, rsi, market


def build_research_simulator(source):
    """
    Reproduce the historical EXP151 research modification
    in memory, without editing the original module.
    """

    old = 'elif st[i]!="LONG":'
    new = 'elif False:'

    count = source.count(old)

    if count != 1:
        raise RuntimeError(
            "Expected exactly one research patch target; "
            f"found {count}"
        )

    patched_source = source.replace(old, new, 1)

    namespace = dict(e.exp117.simulate.__globals__)

    exec(
        compile(
            patched_source,
            "<EXP151_STEP9_MEMORY_ONLY>",
            "exec"
        ),
        namespace
    )

    return namespace["simulate"]


def checkpoints(rows):
    n = len(rows)
    selected = set()

    # Distributed checkpoints.
    for fraction in (
        0.10, 0.20, 0.30, 0.40,
        0.50, 0.60, 0.70, 0.80,
        0.90, 0.98
    ):
        selected.add(
            max(40, min(n - 2, int(n * fraction)))
        )

    # Selected session openings and closes.
    opening = [
        i for i, row in enumerate(rows)
        if str(row["timestamp"])[11:16] == "09:50"
    ]

    closing = [
        i for i, row in enumerate(rows)
        if str(row["timestamp"])[11:16] == "15:55"
    ]

    for indices in (opening, closing):
        if indices:
            stride = max(1, len(indices) // 10)
            selected.update(indices[::stride])

    # The last candle is useful for end-of-data behavior.
    selected.add(n - 1)

    return sorted(
        i for i in selected
        if 40 <= i < n
    )


def normalize_trade(trade):
    """
    Use the actual execution fields rather than
    implementation-specific dictionary ordering.
    """

    fields = (
        "entry_time",
        "exit_time",
        "entry_price",
        "exit_price",
        "exit_reason",
        "gross_pnl_pct",
        "net_pnl_pct",
        "best_close_short_pct",
        "bars_held",
    )

    return tuple(
        (key, trade.get(key))
        for key in fields
    )


def completed_before(trades, cutoff):
    """
    Compare trades completed strictly before cutoff.

    Exclude DATA_END because truncating historical
    input creates an artificial liquidation.

    The strict cutoff also avoids treating the final
    candle as a fully observed future execution.
    """

    return [
        normalize_trade(trade)
        for trade in trades
        if (
            trade.get("exit_reason") != "DATA_END"
            and str(trade.get("exit_time", "")) < cutoff
        )
    ]


def run_simulator(
    simulator, rows, states, st, rsi, market
):
    result = simulator(
        rows,
        st,
        rsi,
        market,
        states,
        "JOINT_SWING"
    )

    trades, events, candidates, rejected = result

    return trades, events, candidates, rejected


def event_signature(event):
    return json.dumps(
        event,
        sort_keys=True,
        default=str
    )


def completed_events_before(events, cutoff):
    """
    Events are signals, not necessarily executed exits.
    Compare only events whose planned exit is earlier
    than the truncated dataset boundary.
    """

    return [
        event_signature(event)
        for event in events
        if str(event.get("planned_exit_time", "")) < cutoff
    ]


print("\nPART A - SOURCE INTEGRITY")

source = textwrap.dedent(
    inspect.getsource(e.exp117.simulate)
)

sim_hash = digest(
    inspect.getsource(e.exp117.simulate)
)

prepare_hash = digest(
    inspect.getsource(e.exp129.prepare)
)

print("SIMULATOR HASH:", sim_hash)
print("PREPARE HASH:", prepare_hash)

assert sim_hash == EXPECTED_SIM_HASH, (
    "Simulator source changed"
)

assert prepare_hash == EXPECTED_PREPARE_HASH, (
    "Prepare source changed"
)

research_simulator = build_research_simulator(source)

print("SOURCE INTEGRITY: PASS")
print("RESEARCH PATCH: MEMORY ONLY")
print("PRODUCTION FILE MODIFICATIONS: NONE")


print("\nPART B - REPLAY AUDIT")

modes = [
    ("ORIGINAL", e.exp117.simulate),
    ("RESEARCH_BASELINE", research_simulator),
]

total = Counter()
examples = []
summaries = []

for symbol, period, path in DATASETS:

    print("\n" + "-" * 100)
    print("DATASET:", symbol, period)

    with path.open("r", encoding="utf-8") as f:
        rows = json.load(f)

    rows.sort(key=lambda r: str(r["timestamp"]))

    assert len(rows) == len({
        str(r["timestamp"]) for r in rows
    })

    states, st, rsi, market = prepare_rows(rows)

    points = checkpoints(rows)

    print("CANDLES:", len(rows))
    print("CHECKPOINTS:", len(points))

    for mode_name, simulator in modes:

        full_trades, full_events, full_candidates, full_rejected = (
            run_simulator(
                simulator,
                rows,
                states,
                st,
                rsi,
                market
            )
        )

        issues = Counter()

        for i in points:
            cutoff = str(rows[i]["timestamp"])

            prefix_rows = rows[:i + 1]

            # Step 8 verified these indicator prefixes
            # against independent truncated recalculation.
            prefix_states = states[:i + 1]
            prefix_st = st[:i + 1]
            prefix_rsi = rsi[:i + 1]
            prefix_market = market[:i + 1]

            (
                prefix_trades,
                prefix_events,
                prefix_candidates,
                prefix_rejected
            ) = run_simulator(
                simulator,
                prefix_rows,
                prefix_states,
                prefix_st,
                prefix_rsi,
                prefix_market
            )

            expected_trades = completed_before(
                full_trades, cutoff
            )

            actual_trades = completed_before(
                prefix_trades, cutoff
            )

            total["TRADE_COMPARISONS"] += 1

            if actual_trades != expected_trades:
                issues["TRADES"] += 1
                total["TRADE_MISMATCHES"] += 1

                if len(examples) < 20:
                    examples.append({
                        "dataset": symbol + " " + period,
                        "mode": mode_name,
                        "cutoff": cutoff,
                        "component": "TRADES",
                        "expected_count": len(expected_trades),
                        "actual_count": len(actual_trades),
                        "expected_tail": str(
                            expected_trades[-2:]
                        )[:500],
                        "actual_tail": str(
                            actual_trades[-2:]
                        )[:500],
                    })

            expected_events = completed_events_before(
                full_events, cutoff
            )

            actual_events = completed_events_before(
                prefix_events, cutoff
            )

            total["EVENT_COMPARISONS"] += 1

            if actual_events != expected_events:
                issues["EVENTS"] += 1
                total["EVENT_MISMATCHES"] += 1

                if len(examples) < 20:
                    examples.append({
                        "dataset": symbol + " " + period,
                        "mode": mode_name,
                        "cutoff": cutoff,
                        "component": "EVENTS",
                        "expected_count": len(expected_events),
                        "actual_count": len(actual_events),
                    })

        print("MODE:", mode_name)
        print("FULL TRADES:", len(full_trades))
        print("FULL EVENTS:", len(full_events))
        print("FULL CANDIDATES:", full_candidates)
        print("FULL REJECTIONS:", full_rejected)
        print("MISMATCHES:", dict(issues))

        summaries.append({
            "dataset": symbol + " " + period,
            "mode": mode_name,
            "checkpoints": len(points),
            "trade_mismatches": issues["TRADES"],
            "event_mismatches": issues["EVENTS"],
        })


print("\n" + "=" * 100)
print("PART C - MISMATCH DETAILS")
print("=" * 100)

if not examples:
    print("NO COMPLETED-TRADE OR EVENT MISMATCHES")
else:
    for item in examples:
        print(json.dumps(item, indent=2))


print("\n" + "=" * 100)
print("PART D - SUMMARY")
print("=" * 100)

print("DATASETS:", len(DATASETS))
print("SIMULATOR MODES:", len(modes))

print(
    "TOTAL REPLAY CHECKPOINTS:",
    sum(item["checkpoints"] for item in summaries)
)

print(
    "TRADE COMPARISONS:",
    total["TRADE_COMPARISONS"]
)

print(
    "TRADE MISMATCHES:",
    total["TRADE_MISMATCHES"]
)

print(
    "EVENT COMPARISONS:",
    total["EVENT_COMPARISONS"]
)

print(
    "EVENT MISMATCHES:",
    total["EVENT_MISMATCHES"]
)

all_pass = (
    total["TRADE_MISMATCHES"] == 0
    and total["EVENT_MISMATCHES"] == 0
)

print("\nFINAL VERDICT")

if all_pass:
    print("COMPLETED TRADE REPLAY: PASS")
    print("COMPLETED EVENT REPLAY: PASS")
else:
    print("TRADE-STATE REPLAY: INVESTIGATION REQUIRED")

print("INTRABAR STOP EXECUTION: NOT INDEPENDENTLY VERIFIED")
print("PENDING STATE AT CUTOFF: NOT DIRECTLY COMPARED")
print("EXP151 HIGHER-LOW EXECUTION: NOT YET REPLAYED")
print("TIMESTAMP CONVENTION: NOT VERIFIED")
print("FORWARD VALIDATION START:", VALIDATION_START)
print("PRODUCTION CHANGES: NONE")
print("FILES WRITTEN: NONE")
print("=" * 100)
