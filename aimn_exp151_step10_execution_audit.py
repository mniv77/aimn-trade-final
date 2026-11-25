#  aimn_exp151_step10_execution_audit.py

#!/usr/bin/env python3
"""
EXP151 STEP 10
Execution priority and frozen higher-low audit.

READ ONLY. NO FILE WRITES. NO ORDERS.
NO CHANGES TO PRODUCTION OR FROZEN PARAMETERS.
"""

from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import inspect
import json
import textwrap

import aimn_exp135_breakout_confirmation as e

ROOT = Path("kiss/visual_research")

DATASETS = [
    ("NVDA", "JUN_AUG", ROOT / "aimn_nvda_candles.json"),
    ("AAPL", "JUN_AUG", ROOT / "aimn_aapl_candles.json"),
    ("NVDA", "SEP_OCT", ROOT /
     "independent_holdout_exp127" /
     "nvda_sep_oct_2026_5m_iex.json"),
    ("AAPL", "SEP_OCT", ROOT /
     "independent_holdout_exp127" /
     "aapl_sep_oct_2026_5m_iex.json"),
    ("NVDA", "NOV", ROOT /
     "independent_holdout_exp144" /
     "nvda_nov_2026_5m_iex.json"),
    ("AAPL", "NOV", ROOT /
     "independent_holdout_exp144" /
     "aapl_nov_2026_5m_iex.json"),
]

EXPECTED_SIM_HASH = (
    "b5567c79fdc9aa6e4b6a1df4c5ee8d530a37287688239be4b3a15fb6194d39e5"
)
EXPECTED_PREPARE_HASH = (
    "595e3ea494d27f6c573a25870ed3ee4b11e5a1c9e65bf0a1eea006289b5a55cc"
)

ENTRY_CLOCK = "09:35"
SIGNAL_CLOCK = "09:50"
EXECUTION_CLOCK = "10:00"
SLIPPAGE_BPS = 10
VALIDATION_START = "2026-11-16"

def banner(message):
    print("\n" + "=" * 100)
    print(message)
    print("=" * 100)

def sha(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()

def stamp(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

def net_short(entry, exit_price, fee):
    return (entry / exit_price - 1.0) * 100.0 - 2.0 * fee

def prepare(rows):
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

banner("EXP151 STEP 10 - EXECUTION AND FROZEN EXIT AUDIT")
print("READ ONLY | NO ORDERS | NO FILE WRITES")

banner("PART A - SOURCE AND PARAMETER INTEGRITY")

original_source = inspect.getsource(e.exp117.simulate)
prepare_source = inspect.getsource(e.exp129.prepare)

print("SIMULATOR HASH:", sha(original_source))
print("PREPARE HASH:", sha(prepare_source))

assert sha(original_source) == EXPECTED_SIM_HASH
assert sha(prepare_source) == EXPECTED_PREPARE_HASH

assert original_source.count('elif st[i]!="LONG":') == 1

patched = textwrap.dedent(original_source).replace(
    'elif st[i]!="LONG":', 'elif False:', 1
)
namespace = dict(e.exp117.simulate.__globals__)
exec(compile(patched, "<EXP151_MEMORY_ONLY>", "exec"), namespace)
research_simulator = namespace["simulate"]

fee = float(e.exp79.FEE)
stop_pct = float(e.exp79.STOP_PCT)

print("RESEARCH SIMULATOR: MEMORY ONLY")
print("ROUNDTRIP FEE PCT:", 2 * fee)
print("ORIGINAL STOP PCT:", stop_pct)
print("SLIPPAGE BPS:", SLIPPAGE_BPS)
print("FROZEN VALIDATION START:", VALIDATION_START)

banner("PART B - SIMULATOR EXECUTION PRIORITY")

lines = textwrap.dedent(original_source).splitlines()

for number, line in enumerate(lines, 1):
    if any(token in line for token in (
        'if pending is not None:',
        'if action=="ENTER"',
        'elif action!="ENTER"',
        'if pos is not None:',
        'if highs[i]>=stop:',
        'if i+1<n',
        'if candidate:',
        'pending="ENTER"',
        'DATA_END',
        'SESSION_END',
    )):
        print(f"{number:03d}: {line.strip()}")

priority_checks = {
    "PENDING_BEFORE_STOP": (
        original_source.index("if pending is not None:")
        < original_source.index("if highs[i]>=stop:")
    ),
    "STOP_BEFORE_EXIT_SIGNAL": (
        original_source.index("if highs[i]>=stop:")
        < original_source.index('pending="ST_REVERSE"')
    ),
    "STOP_USES_CANDLE_HIGH": (
        "highs[i]>=stop" in original_source
    ),
    "STOP_PRICE_ACCOUNTS_FOR_GAP": (
        "max(stop,opens[i])" in original_source
    ),
    "PENDING_EXIT_USES_OPEN": (
        "exp79.finish(pos,i,opens[i],action,times)"
        in original_source
    ),
    "END_OF_DATA_LIQUIDATION": (
        '"DATA_END"' in original_source
    ),
}

for name, passed in priority_checks.items():
    print(name, "PASS" if passed else "REVIEW")

assert all(priority_checks.values()), (
    "Simulator execution priority differs from audited source"
)

banner("PART C - FROZEN OPENING SHORT RECONSTRUCTION")

totals = Counter()
opening_trades = []
all_results = []
violations = []

for symbol, period, path in DATASETS:
    with path.open("r", encoding="utf-8") as f:
        rows = json.load(f)

    rows.sort(key=lambda r: str(r["timestamp"]))
    times = [str(r["timestamp"]) for r in rows]
    index = {t: i for i, t in enumerate(times)}

    assert len(index) == len(rows), "Duplicate timestamps"

    states, st, rsi, market = prepare(rows)
    trades, events, candidates, rejected = research_simulator(
        rows, st, rsi, market, states, "JOINT_SWING"
    )

    selected = [
        trade for trade in trades
        if str(trade["entry_time"])[11:16] == ENTRY_CLOCK
    ]

    print(
        symbol, period,
        "ALL_RESEARCH_TRADES:", len(trades),
        "OPENING_SHORTS:", len(selected)
    )

    for trade in selected:
        entry_time = str(trade["entry_time"])
        original_exit_time = str(trade["exit_time"])
        entry_price = float(trade["entry_price"])
        original_net = float(trade["net_pnl_pct"])
        day = entry_time[:10]

        totals["OPENING_TRADES"] += 1

        if entry_time not in index:
            violations.append((symbol, day, "ENTRY_NOT_FOUND"))
            continue

        entry_i = index[entry_time]

        # Exact same-session candle labels are required.
        signal_time = day + " " + SIGNAL_CLOCK + ":00"
        execution_time = day + " " + EXECUTION_CLOCK + ":00"

        signal_i = index.get(signal_time)
        execution_i = index.get(execution_time)

        if signal_i is None or execution_i is None:
            violations.append(
                (symbol, day, "MISSING_SIGNAL_OR_EXECUTION_BAR")
            )
            continue

        if not (
            entry_i < signal_i < execution_i
            and stamp(signal_time) + timedelta(minutes=5)
                <= stamp(execution_time)
        ):
            violations.append(
                (symbol, day, "INVALID_TEMPORAL_ORDER")
            )
            continue

        # The 09:50 candle is presumed to close at 09:55.
        # Compare the lows of 09:40, 09:45 and 09:50.
        low_indices = [
            signal_i - 2,
            signal_i - 1,
            signal_i,
        ]

        expected_labels = [
            day + " 09:40:00",
            day + " 09:45:00",
            day + " 09:50:00",
        ]

        if [times[i] for i in low_indices] != expected_labels:
            violations.append(
                (symbol, day, "LOW_CANDLE_ALIGNMENT")
            )
            continue

        lows = [
            float(rows[i]["low"]) for i in low_indices
        ]

        triggered = lows[0] < lows[1] < lows[2]

        # Earlier or equal original exit always wins.
        original_exit_first = (
            stamp(original_exit_time) <= stamp(execution_time)
        )

        result = {
            "symbol": symbol,
            "period": period,
            "date": day,
            "entry": entry_time,
            "original_exit": original_exit_time,
            "original_reason": trade["exit_reason"],
            "original_net": original_net,
            "lows": lows,
            "triggered": triggered,
            "original_exit_first": original_exit_first,
            "applied": False,
            "new_net": original_net,
            "delta": 0.0,
        }

        if triggered:
            totals["SIGNALS"] += 1

            if original_exit_first:
                totals["ORIGINAL_EXIT_PRIORITY"] += 1
            else:
                # For a SHORT, adverse slippage increases
                # the buy-to-cover execution price.
                raw_open = float(rows[execution_i]["open"])
                adjusted_exit = raw_open * (
                    1.0 + SLIPPAGE_BPS / 10000.0
                )

                result["applied"] = True
                result["raw_open"] = raw_open
                result["adjusted_exit"] = adjusted_exit
                result["new_net"] = net_short(
                    entry_price, adjusted_exit, fee
                )
                result["delta"] = (
                    result["new_net"] - original_net
                )

                totals["APPLIED"] += 1

        opening_trades.append(trade)
        all_results.append(result)

banner("PART D - TRADE-BY-TRADE RESULTS")

for result in all_results:
    print(
        result["symbol"],
        result["date"],
        "ORIGINAL:", f'{result["original_net"]:+.6f}%',
        "SIGNAL:", result["triggered"],
        "APPLIED:", result["applied"],
        "NEW:", f'{result["new_net"]:+.6f}%',
        "DELTA:", f'{result["delta"]:+.6f}pp',
        "REASON:", result["original_reason"],
    )
    if result["triggered"]:
        print(
            "   LOWS:", result["lows"],
            "ORIGINAL_EXIT_FIRST:",
            result["original_exit_first"],
        )

banner("PART E - AGGREGATE OUTCOME")

original_sum = sum(
    r["original_net"] for r in all_results
)
new_sum = sum(
    r["new_net"] for r in all_results
)
delta_sum = new_sum - original_sum

print("OPENING TRADES:", totals["OPENING_TRADES"])
print("EVALUATED TRADES:", len(all_results))
print("HIGHER-LOW SIGNALS:", totals["SIGNALS"])
print("ORIGINAL EXIT PRIORITY:",
      totals["ORIGINAL_EXIT_PRIORITY"])
print("HYPOTHETICAL EXITS APPLIED:", totals["APPLIED"])
print("ORIGINAL NET SUM:", f"{original_sum:+.6f}%")
print("FROZEN NET SUM:", f"{new_sum:+.6f}%")
print("CHANGE:", f"{delta_sum:+.6f} percentage points")
print("VIOLATIONS:", len(violations))

for item in violations:
    print("VIOLATION:", item)

banner("PART F - INDEPENDENT EXECUTION LIMITATIONS")

print(
    "CANDLE LABELS: PRESUMED BAR STARTS; "
    "PROVIDER METADATA NOT VERIFIED"
)
print(
    "09:50 SIGNAL: AVAILABLE AFTER PRESUMED 09:55 CLOSE"
)
print(
    "10:00 EXECUTION: NEXT SCHEDULED 10:00 BAR OPEN"
)
print(
    "STOP PRIORITY: SOURCE ORDER VERIFIED; "
    "INTRABAR PRICE PATH UNKNOWN"
)
print(
    "PENDING STATE: SOURCE REVIEWED; "
    "NOT INSTRUMENTED BAR BY BAR"
)
print(
    "SLIPPAGE: FROZEN 10 BPS ASSUMPTION, "
    "NOT OBSERVED LIVE FILL"
)
print(
    "TRADE SUM: SUM OF PERCENT RETURNS, "
    "NOT COMPOUNDED PORTFOLIO PERFORMANCE"
)

banner("FINAL VERDICT")

expected = (
    totals["OPENING_TRADES"] == 13
    and len(all_results) == 13
    and totals["SIGNALS"] == 4
    and totals["APPLIED"] == 3
    and len(violations) == 0
)

print(
    "HISTORICAL BASELINE REPRODUCTION:",
    "PASS" if expected else "INVESTIGATE"
)

print(
    "EXECUTION SOURCE PRIORITY:",
    "PASS" if all(priority_checks.values()) else "INVESTIGATE"
)

print("EXPECTED ORIGINAL SUM: +0.297857%")
print("EXPECTED FROZEN SUM: +1.085384%")
print("EXPECTED CHANGE: +0.787527 percentage points")
print("OBSERVED ORIGINAL SUM:", f"{original_sum:+.6f}%")
print("OBSERVED FROZEN SUM:", f"{new_sum:+.6f}%")

numeric_match = (
    abs(original_sum - 0.297857) < 0.0001
    and abs(new_sum - 1.085384) < 0.0001
    and abs(delta_sum - 0.787527) < 0.0001
)

print(
    "FROZEN NUMERIC REPRODUCTION:",
    "PASS" if numeric_match else "INVESTIGATE"
)

print("FORWARD VALIDATION START:", VALIDATION_START)
print("PRODUCTION CHANGES: NONE")
print("FILES WRITTEN: NONE")
print("ORDERS PLACED: NONE")
print("=" * 100)
