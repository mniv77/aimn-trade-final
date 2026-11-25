#!/usr/bin/env python3
"""EXP81 — V16 rebound aftermath, paired with EXP79/EXP80 data.
Research-only. No engine modification or order placement.

Outputs an event-by-event CSV for all early exits, measuring what was
observable at the trigger close and what happened afterward. Future movements
are diagnostics, never inputs to an exit decision.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "kiss/visual_research/aimn_nvda_candles.json"
EXP79 = ROOT / "kiss/results/exp79_v16_early_exit"
OUT = ROOT / "kiss/results/exp81_rebound_aftermath"

VARIANTS = {
    "B_0_3": "b_rebound_0_3_trades.csv",
    "C_0_5": "c_rebound_0_5_trades.csv",
}
BASE = "a_st_baseline_trades.csv"

def load_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

def save_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

def change_pct(new_price, old_price):
    return (new_price / old_price - 1.0) * 100.0

def rnd(value):
    return round(value, 5)

def main():
    candles = json.loads(DATA.read_text(encoding="utf-8"))
    candles.sort(key=lambda row: str(row["timestamp"]))
    times = [str(row["timestamp"]) for row in candles]
    indexes = {value: idx for idx, value in enumerate(times)}
    if len(indexes) != len(times):
        raise ValueError("Duplicate candle timestamps")

    baseline = {row["entry_time"]: row for row in load_csv(EXP79 / BASE)}
    results = []
    for variant, filename in VARIANTS.items():
        for trade in load_csv(EXP79 / filename):
            if trade["exit_reason"] != "EARLY_REBOUND":
                continue
            b = baseline.get(trade["entry_time"])
            if b is None:
                raise ValueError("Baseline trade missing: " + trade["entry_time"])
            first = indexes[trade["entry_time"]]
            last = indexes[trade["exit_time"]]
            baseline_last = indexes[b["exit_time"]]
            if last < first or baseline_last < first:
                raise ValueError("Unexpected trade ordering")

            # The early exit was executed at the next opening price,
            # so the trigger close is the prior candle's close.
            trigger = last - 1
            if trigger < first:
                raise ValueError("Missing trigger candle")
            if times[trigger][:10] != times[last][:10]:
                raise ValueError("Cross-session early exit")
            entry = float(trade["entry_price"])
            exit_price = float(trade["exit_price"])
            base_exit = float(b["exit_price"])
            at_trigger = candles[trigger]
            completed = candles[first:trigger + 1]
            min_completed_close = min(float(row["close"]) for row in completed)
            if not completed:
                raise ValueError("Empty history")
            profit_at_trigger = change_pct(entry, float(at_trigger["close"]))  # negative = favorable for SHORT
            rebound_from_min = change_pct(float(at_trigger["close"]), min_completed_close)

            # After the actual early exit, stop at the baseline exit
            # if that exit happened later in the SAME SESSION.
            after = []
            if baseline_last > last and times[baseline_last][:10] == times[last][:10]:
                after = candles[last + 1:baseline_last + 1]

            # Avoid treating the price lows/highs after the baseline's
            # opening exit as part of a still-live baseline position.
            if b["exit_reason"] != "SESSION_END" and after:
                after = after[:-1]

            row = {
                "variant": variant,
                "entry_time": trade["entry_time"],
                "trigger_candle": times[trigger],
                "early_exit_time": trade["exit_time"],
                "baseline_exit_time": b["exit_time"],
                "baseline_exit_reason": b["exit_reason"],
                "early_net_pct": rnd(float(trade["net_pnl_pct"])),
                "baseline_net_pct": rnd(float(b["net_pnl_pct"])),
                "early_minus_baseline_pp": rnd(float(trade["net_pnl_pct"]) - float(b["net_pnl_pct"])),
                "rebound_at_signal_close_pct": rnd(rebound_from_min),
                "gross_short_profit_at_trigger_close_pct": rnd(-profit_at_trigger),
                "completed_candles_since_entry": trigger - first + 1,
                "baseline_exit_price_change_after_early_pct": rnd(change_pct(base_exit, exit_price)),
                "future_candles_before_baseline_exit": len(after),
                "future_low_below_early_exit_pct": rnd(change_pct(exit_price, min(float(x["low"]) for x in after))) if after else None,
                "future_high_above_early_exit_pct": rnd(change_pct(max(float(x["high"]) for x in after), exit_price)) if after else None,
                "baseline_loser_rescued": float(b["net_pnl_pct"]) <= 0 and float(trade["net_pnl_pct"]) > 0,
                "baseline_winner_cut_short": float(b["net_pnl_pct"]) > float(trade["net_pnl_pct"]) and float(b["net_pnl_pct"]) > 0,
            }
            results.append(row)

    OUT.mkdir(parents=True, exist_ok=True)
    columns = [
        "variant", "entry_time", "trigger_candle", "early_exit_time",
        "baseline_exit_time", "baseline_exit_reason", "early_net_pct",
        "baseline_net_pct", "early_minus_baseline_pp",
        "rebound_at_signal_close_pct", "gross_short_profit_at_trigger_close_pct",
        "completed_candles_since_entry", "baseline_exit_price_change_after_early_pct",
        "future_candles_before_baseline_exit",
        "future_low_below_early_exit_pct", "future_high_above_early_exit_pct",
        "baseline_loser_rescued", "baseline_winner_cut_short",
    ]
    save_csv(OUT / "rebound_events.csv", results, columns)
    report = {
        "experiment": "EXP81",
        "research_only": True,
        "event_count": len(results),
        "variants": {},
        "important": "Future paths are hindsight, not a validated predictive signal. Sample has only 11 baseline trades.",
    }
    for variant in VARIANTS:
        group = [item for item in results if item["variant"] == variant]
        report["variants"][variant] = {
            "early_exit_events": len(group),
            "rescued_baseline_losers": sum(item["baseline_loser_rescued"] for item in group),
            "baseline_winners_cut_short": sum(item["baseline_winner_cut_short"] for item in group),
            "sum_early_minus_baseline_pp": rnd(sum(item["early_minus_baseline_pp"] for item in group)),
            "rescued_event_times": [item["entry_time"] for item in group if item["baseline_loser_rescued"]],
            "cut_short_event_times": [item["entry_time"] for item in group if item["baseline_winner_cut_short"]],
        }
    (OUT / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("EXP81 — REBOUND AFTERMATH AUDIT — RESEARCH ONLY")
    print(json.dumps(report, indent=2))
    print("Detailed report:", OUT / "rebound_events.csv")

if __name__ == "__main__":
    main()
