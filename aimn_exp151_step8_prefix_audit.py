#  aimn_exp151_step8_prefix_audit.py
from pathlib import Path
from collections import Counter
from datetime import datetime
import hashlib
import inspect
import json
import math
import textwrap

import aimn_exp135_breakout_confirmation as e

print("=" * 105)
print("EXP151 STEP 8 - DYNAMIC PREFIX STABILITY AND LOOKAHEAD AUDIT")
print("READ ONLY | NO ORDERS | NO FILE WRITES | NO STRATEGY CHANGES")
print("=" * 105)

ROOT = Path("kiss/visual_research")

DATASETS = [
    ("NVDA", "JUN_AUG", ROOT / "aimn_nvda_candles.json"),
    ("AAPL", "JUN_AUG", ROOT / "aimn_aapl_candles.json"),
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

def sha256(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()

def same(a, b):
    if a is None or b is None:
        return a is None and b is None

    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        if math.isnan(float(a)) or math.isnan(float(b)):
            return math.isnan(float(a)) and math.isnan(float(b))
        return math.isclose(
            float(a), float(b),
            rel_tol=1e-10, abs_tol=1e-10
        )

    if isinstance(a, dict) and isinstance(b, dict):
        return (
            a.keys() == b.keys()
            and all(same(a[k], b[k]) for k in a)
        )

    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return (
            len(a) == len(b)
            and all(same(x, y) for x, y in zip(a, b))
        )

    return a == b

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

    return times, states, st, rsi, market, counts

def checkpoint_indices(rows):
    n = len(rows)
    indices = set()

    # A range of global prefixes, including early history.
    for fraction in (
        0.05, 0.10, 0.20, 0.35,
        0.50, 0.65, 0.80, 0.95
    ):
        i = max(40, min(n - 2, int(n * fraction)))
        indices.add(i)

    # Opening checkpoints, including 09:35 and 09:50.
    for i, row in enumerate(rows):
        stamp = str(row["timestamp"])

        if stamp[11:16] in ("09:35", "09:50"):
            indices.add(i)

    # Include a sample of session-end checkpoints.
    session_ends = [
        i for i, row in enumerate(rows)
        if str(row["timestamp"])[11:16] == "15:55"
    ]

    if session_ends:
        stride = max(1, len(session_ends) // 10)
        indices.update(session_ends[::stride])

    return sorted(
        i for i in indices
        if 40 <= i < n
    )

def candidate_at(rows, market, i):
    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]
    closes = [float(r["close"]) for r in rows]

    return e.exp117.base.is_major_long_to_short_reversal(
        highs, lows, closes, market, i
    )

print("\n" + "=" * 105)
print("PART A - SOURCE INTEGRITY")
print("=" * 105)

sim_hash = sha256(
    inspect.getsource(e.exp117.simulate)
)

prepare_hash = sha256(
    inspect.getsource(e.exp129.prepare)
)

print("SIMULATOR:", sim_hash)
print("PREPARE:", prepare_hash)

assert sim_hash == EXPECTED_SIM_HASH
assert prepare_hash == EXPECTED_PREPARE_HASH

print("SOURCE INTEGRITY: PASS")

print("\n" + "=" * 105)
print("PART B - PREFIX STABILITY")
print("=" * 105)

totals = Counter()
examples = []
results = []

for symbol, period, path in DATASETS:
    print("\n" + "-" * 105)
    print("DATASET:", symbol, period)
    print("PATH:", path)

    with path.open("r", encoding="utf-8") as f:
        rows = json.load(f)

    rows.sort(key=lambda r: str(r["timestamp"]))

    assert len(rows) == len({
        str(r["timestamp"]) for r in rows
    })

    full_times, full_states, full_st, full_rsi, full_market, full_counts = (
        prepare_rows(rows)
    )

    checkpoints = checkpoint_indices(rows)
    issues = Counter()

    # Rebuild indicators using only candles through index i.
    for i in checkpoints:
        prefix = rows[:i + 1]

        (
            prefix_times,
            prefix_states,
            prefix_st,
            prefix_rsi,
            prefix_market,
            prefix_counts
        ) = prepare_rows(prefix)

        checks = {
            "TIMESTAMP": (
                prefix_times[i], full_times[i]
            ),
            "SWING_STRUCTURE": (
                prefix_states[i], full_states[i]
            ),
            "SUPERTREND": (
                prefix_st[i], full_st[i]
            ),
            "RSI": (
                prefix_rsi[i], full_rsi[i]
            ),
            "MARKET_STATE": (
                prefix_market[i], full_market[i]
            ),
            "CONFIRMED_PIVOT_COUNTS": (
                prefix_counts[i], full_counts[i]
            ),
            "ENTRY_CANDIDATE": (
                candidate_at(prefix, prefix_market, i),
                candidate_at(rows, full_market, i)
            ),
        }

        for name, (left, right) in checks.items():
            totals[name + "_CHECKS"] += 1

            if not same(left, right):
                issues[name] += 1
                totals[name + "_MISMATCHES"] += 1

                if len(examples) < 25:
                    examples.append({
                        "symbol": symbol,
                        "period": period,
                        "time": full_times[i],
                        "component": name,
                        "prefix": str(left)[:250],
                        "full": str(right)[:250],
                    })

    print("CANDLES:", len(rows))
    print("CHECKPOINTS:", len(checkpoints))
    print("MISMATCHES:", dict(issues))

    results.append({
        "symbol": symbol,
        "period": period,
        "checkpoints": len(checkpoints),
        "mismatches": sum(issues.values()),
    })

print("\n" + "=" * 105)
print("PART C - MISMATCH DETAILS")
print("=" * 105)

if not examples:
    print("NO PREFIX MISMATCHES DETECTED")
else:
    for item in examples:
        print(json.dumps(item, indent=2))

print("\n" + "=" * 105)
print("PART D - AGGREGATE RESULTS")
print("=" * 105)

for name in (
    "TIMESTAMP",
    "SWING_STRUCTURE",
    "SUPERTREND",
    "RSI",
    "MARKET_STATE",
    "CONFIRMED_PIVOT_COUNTS",
    "ENTRY_CANDIDATE",
):
    print(
        name,
        "CHECKS:", totals[name + "_CHECKS"],
        "MISMATCHES:", totals[name + "_MISMATCHES"]
    )

total_mismatches = sum(
    totals[name + "_MISMATCHES"]
    for name in (
        "TIMESTAMP",
        "SWING_STRUCTURE",
        "SUPERTREND",
        "RSI",
        "MARKET_STATE",
        "CONFIRMED_PIVOT_COUNTS",
        "ENTRY_CANDIDATE",
    )
)

print("\n" + "=" * 105)
print("FINAL VERDICT")
print("=" * 105)

print("DATASETS:", len(results))
print("TOTAL CHECKPOINTS:",
      sum(r["checkpoints"] for r in results))
print("TOTAL MISMATCHES:", total_mismatches)

if total_mismatches == 0:
    print("INDICATOR PREFIX STABILITY: PASS")
    print("ENTRY CANDIDATE PREFIX STABILITY: PASS")
else:
    print("PREFIX STABILITY: INVESTIGATION REQUIRED")

print("FULL TRADE-STATE REPLAY: NOT TESTED")
print("TIMESTAMP CONVENTION: NOT VERIFIED")
print("INDEPENDENT FORWARD RESULTS: NOT AVAILABLE")
print("FILES WRITTEN: NONE")
print("PRODUCTION CHANGES: NONE")
print("=" * 105)
