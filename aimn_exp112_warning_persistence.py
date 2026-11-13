#!/usr/bin/env python3
"""EXP112 — warning persistence and executable next-open audit.

Research only. Uses unchanged EXP83 V16 baseline trades and compares all winners
with giveback losers. Fixed-entry, first-warning hypothetical exits are not a
full portfolio strategy replay: earlier exits can change later entry signals.
Signals are based only on completed candles. Hypothetical fills are next open,
within the same session, before the original exit, with known commissions.
"""

import csv
import json
from collections import Counter
from pathlib import Path

import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as exp100

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "kiss/results/exp112_warning_persistence"
FEE_ROUND_TRIP = 2 * exp79.FEE

# Definitions are diagnostic comparisons, not fitted thresholds.
# Rising-close windows require consecutive increases ending at signal close.
RULES = {
    "TWO_RISING_CLOSES": 2,
    "THREE_RISING_CLOSES": 3,
}


def short_gross(entry, exit_price):
    return 100.0 * (entry / exit_price - 1.0)


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def group_of(trade, first_profitable):
    if trade["net_pnl_pct"] > 0:
        return "WINNER_CONTROL"
    if first_profitable is not None:
        return "LOSING_GIVEBACK"
    return "NO_FEE_COVERING_CLOSE"


def analyze_symbol(symbol, path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r: str(r["timestamp"]))
    times = [str(r["timestamp"]) for r in rows]
    index = {t: i for i, t in enumerate(times)}
    if len(index) != len(times):
        raise AssertionError(symbol + ": duplicate candle times")
    closes = [float(r["close"]) for r in rows]
    opens = [float(r["open"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    st = base.calculate_supertrend(rows, atr_period=10, multiplier=3.0)["st_trend"].tolist()
    rsi = base.rsi_wilder(closes)
    market = [base.get_market_state(closes, i) for i in range(len(rows))]
    trades, _, _, _ = base.simulate(rows, st, rsi, market, None, False)
    session_starts = exp100.get_session_starts(times)
    pivot_highs, pivot_lows, pivot_counts = exp100.confirmed_pivots(rows, times, session_starts)

    trade_rows = []
    event_rows = []

    for trade in trades:
        entry_i = index[trade["entry_time"]]
        exit_i = index[trade["exit_time"]]
        if times[entry_i][:10] != times[exit_i][:10]:
            raise AssertionError(symbol + ": cross-session trade")
        entry = float(trade["entry_price"])
        # ST/RSI exits fill at the next bar open; stops can fill intrabar.
        # Never use their actual exit candle's completed close as a signal.
        end_i = exit_i if trade["exit_reason"] in ("SESSION_END", "DATA_END") else exit_i - 1
        completed = range(entry_i, end_i + 1)
        fee_i = next((i for i in completed
                      if short_gross(entry, closes[i]) > FEE_ROUND_TRIP), None)
        group = group_of(trade, fee_i)
        events = {}
        running_best = entry
        up_streak = 0

        for i in completed:
            if i > entry_i and closes[i] > closes[i - 1]:
                up_streak += 1
            else:
                up_streak = 0
            running_best = min(running_best, closes[i])
            if fee_i is None or i < fee_i:
                continue
            if i + 1 >= len(rows) or times[i + 1][:10] != times[i][:10]:
                continue

            next_i = i + 1
            # The hypothetical next-open exit must precede the baseline
            # exit, or beat a same-candle session-close/intrabar-stop exit.
            if next_i > exit_i:
                continue
            if next_i == exit_i and trade["exit_reason"] not in (
                "SESSION_END", "DATA_END", "STOP_LOSS"
            ):
                continue

            state = exp100.structure(
                rows, times, session_starts, i,
                pivot_highs, pivot_lows, pivot_counts
            )
            current_gross = short_gross(entry, closes[i])
            rebound = 100.0 * (closes[i] / running_best - 1.0)
            checks = {
                "TWO_RISING_CLOSES": up_streak >= 2,
                "THREE_RISING_CLOSES": up_streak >= 3,
                "CONFIRMED_HIGH_BREAK": state["close_above_last_confirmed_high"] == 1,
                "TWO_RISING_STILL_PROFITABLE":
                    up_streak >= 2 and current_gross > FEE_ROUND_TRIP,
                "THREE_RISING_STILL_PROFITABLE":
                    up_streak >= 3 and current_gross > FEE_ROUND_TRIP,
                "CONFIRMED_HIGH_BREAK_STILL_PROFITABLE":
                    state["close_above_last_confirmed_high"] == 1
                    and current_gross > FEE_ROUND_TRIP,
            }

            for rule, hit in checks.items():
                if not hit or rule in events:
                    continue
                simulated_exit_price = opens[next_i]
                hypothetical_gross = short_gross(entry, simulated_exit_price)
                hypothetical_net = hypothetical_gross - FEE_ROUND_TRIP
                delta = hypothetical_net - trade["net_pnl_pct"]
                event = {
                    "symbol": symbol,
                    "entry_time": trade["entry_time"],
                    "group_hindsight": group,
                    "rule": rule,
                    "first_fee_cover_time": times[fee_i],
                    "signal_time": times[i],
                    "hypothetical_exit_time": times[next_i],
                    "bars_after_fee_cover": i - fee_i,
                    "up_close_streak": up_streak,
                    "rebound_from_best_close_pct": round(rebound, 6),
                    "gross_at_signal_close_pct": round(current_gross, 6),
                    "gross_at_next_open_pct_hindsight": round(hypothetical_gross, 6),
                    "hypothetical_next_open_net_pct_hindsight": round(hypothetical_net, 6),
                    "original_exit_time": trade["exit_time"],
                    "original_exit_reason": trade["exit_reason"],
                    "original_net_pct": trade["net_pnl_pct"],
                    "difference_vs_original_pp_hindsight": round(delta, 6),
                    "original_winner_harmed_hindsight":
                        group == "WINNER_CONTROL" and delta < 0,
                    "original_loser_helped_hindsight":
                        group == "LOSING_GIVEBACK" and delta > 0,
                }
                events[rule] = event
                event_rows.append(event)

        trade_rows.append({
            "symbol": symbol, "entry_time": trade["entry_time"],
            "exit_time": trade["exit_time"],
            "exit_reason": trade["exit_reason"],
            "original_net_pct": trade["net_pnl_pct"],
            "group_hindsight": group,
            "first_fee_cover_time": times[fee_i] if fee_i is not None else None,
            **{rule + "_signal_time": events[rule]["signal_time"] if rule in events else None
               for rule in (
                   "TWO_RISING_CLOSES", "THREE_RISING_CLOSES",
                   "CONFIRMED_HIGH_BREAK", "TWO_RISING_STILL_PROFITABLE",
                   "THREE_RISING_STILL_PROFITABLE",
                   "CONFIRMED_HIGH_BREAK_STILL_PROFITABLE"
               )},
        })

    write_csv(OUT / (symbol.lower() + "_trade_controls.csv"), trade_rows)
    write_csv(OUT / (symbol.lower() + "_first_warning_events.csv"), event_rows)

    groups = dict(Counter(t["group_hindsight"] for t in trade_rows))
    rule_summaries = []
    for rule in (
        "TWO_RISING_CLOSES", "THREE_RISING_CLOSES",
        "CONFIRMED_HIGH_BREAK", "TWO_RISING_STILL_PROFITABLE",
        "THREE_RISING_STILL_PROFITABLE",
        "CONFIRMED_HIGH_BREAK_STILL_PROFITABLE"
    ):
        seen = [e for e in event_rows if e["rule"] == rule]
        for group in ("WINNER_CONTROL", "LOSING_GIVEBACK", "NO_FEE_COVERING_CLOSE"):
            subset = [e for e in seen if e["group_hindsight"] == group]
            rule_summaries.append({
                "rule": rule, "group": group,
                "group_trade_count": groups.get(group, 0),
                "first_actionable_warning_count": len(subset),
                "hypothetical_net_sum_of_triggered_trades_pct":
                    round(sum(e["hypothetical_next_open_net_pct_hindsight"]
                              for e in subset), 6),
                "difference_sum_vs_original_triggered_trades_pp_hindsight":
                    round(sum(e["difference_vs_original_pp_hindsight"]
                              for e in subset), 6),
                "helped_count_hindsight":
                    sum(e["difference_vs_original_pp_hindsight"] > 0 for e in subset),
                "hurt_count_hindsight":
                    sum(e["difference_vs_original_pp_hindsight"] < 0 for e in subset),
            })
    write_csv(OUT / (symbol.lower() + "_rule_group_descriptives.csv"), rule_summaries)
    return {
        "trades": len(trades),
        "baseline_net_sum_pct": round(sum(t["net_pnl_pct"] for t in trades), 6),
        "groups": groups,
        "rule_groups": rule_summaries,
        "events": event_rows,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "experiment": "EXP112",
        "research_only": True,
        "purpose": "Measure warning persistence versus winning controls, including executable next-open counterfactual prices.",
        "transaction_cost_pct_round_trip": FEE_ROUND_TRIP,
        "method": (
            "First completed close covering fees arms diagnostics; compare 2 or 3 consecutive "
            "rising closes, confirmed swing-high break, and variants requiring gross profit "
            "still exceeds fees. Signals use only completed-bar information, fill next "
            "same-session open before original exit; no full replay."
        ),
        "limitations": [
            "Fixed-entry counterfactuals are NOT independent strategy backtests.",
            "Exiting early could change later signal eligibility and the total trade set.",
            "Fixed predeclared rules are descriptive and already exposed to in-sample selection.",
            "A next-open fill is hypothetical; real spread/slippage and orders are absent.",
            "ST/RSI and stop priority of the original baseline are retained for comparisons.",
            "Small NVDA/AAPL sample; no independent holdout and no claim of improved profitability.",
            "Sum of trade returns is not compounded portfolio performance.",
        ],
        "symbols": {}
    }
    for symbol, path in base.DATA.items():
        report["symbols"][symbol] = analyze_symbol(symbol, path)
    (OUT / "summary.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("EXP112 — PERSISTENCE WARNING WITH WINNER CONTROLS — RESEARCH ONLY")
    for symbol, data in report["symbols"].items():
        print("\n", symbol, "trades:", data["trades"],
              "baseline net:", data["baseline_net_sum_pct"],
              "groups:", data["groups"])
        for row in data["rule_groups"]:
            if row["group_trade_count"]:
                print(" GROUP", row)
        for event in data["events"]:
            if event["group_hindsight"] == "LOSING_GIVEBACK":
                print(" GIVEBACK", event["entry_time"], event["rule"],
                      "signal:", event["signal_time"],
                      "next_open_net:", event["hypothetical_next_open_net_pct_hindsight"],
                      "delta:", event["difference_vs_original_pp_hindsight"])
    print("\nCSV and JSON:", OUT)
    print("Production code unchanged.")


if __name__ == "__main__":
    main()
