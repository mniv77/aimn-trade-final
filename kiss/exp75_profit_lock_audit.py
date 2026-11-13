#!/usr/bin/env python3
"""EXP75: compare hybrid trailing against 1 percent profit-lock.

No broker orders. Summed trade percentages are not portfolio returns.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from engine.kiss_backtest import run_kiss_backtest as baseline
from kiss.exp73_kiss_two_close_engine import run_kiss_backtest as two_close
from kiss.exp74_kiss_hybrid_engine import run_kiss_backtest as hybrid
from kiss.exp75_kiss_profit_lock_engine import run_kiss_backtest as profit_lock


def run(rows, runner):
    return runner(rows, symbol="NVDA", direction="SHORT", timeframe="5m",
                  entry_mode="V15", trailing_minus_pct=0.50,
                  commission_pct=0.10, rsi_rescue_long=20, rsi_rescue_short=80)


def summarize(r):
    trades = r["trades"]
    return {"trades":len(trades),"winners":sum(t["net_pnl_pct"]>0 for t in trades),
            "net_pct_sum":round(sum(t["net_pnl_pct"] for t in trades),5),
            "exit_reasons":dict(Counter(t["exit_reason"] for t in trades)),
            "largest_loss_pct":round(min((t["net_pnl_pct"] for t in trades),default=0),5)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candles",default="kiss/visual_research/aimn_nvda_candles.json")
    p.add_argument("--output",default="/tmp/exp75_profit_lock.json")
    a=p.parse_args()
    rows=json.loads(Path(a.candles).read_text(encoding="utf-8"))
    results={"baseline":run(rows,baseline),"two_close":run(rows,two_close),"hybrid":run(rows,hybrid),"profit_lock":run(rows,profit_lock)}
    # The two engines share entry logic, but altered exits change which later
    # entries are available. Never describe trade counts as matched pairs.
    summary={name:summarize(result) for name,result in results.items()}
    by_entry={}
    for name,result in results.items():
        by_entry[name]={str(t["entry_time"]):t for t in result["trades"]}
    common=sorted(set(by_entry["baseline"]) & set(by_entry["two_close"]) & set(by_entry["hybrid"]) & set(by_entry["profit_lock"]))
    comparisons=[{
        "entry_time":ts,
        "baseline_exit":by_entry["baseline"][ts]["exit_time"],
        "filtered_exit":by_entry["two_close"][ts]["exit_time"],
        "baseline_net":by_entry["baseline"][ts]["net_pnl_pct"],
        "filtered_net":by_entry["two_close"][ts]["net_pnl_pct"],
        "net_difference":round(by_entry["two_close"][ts]["net_pnl_pct"]-
                               by_entry["baseline"][ts]["net_pnl_pct"],5),
        "baseline_reason":by_entry["baseline"][ts]["exit_reason"],
        "filtered_reason":by_entry["two_close"][ts]["exit_reason"],
        "hybrid_exit":by_entry["hybrid"][ts]["exit_time"],
        "hybrid_net":by_entry["hybrid"][ts]["net_pnl_pct"],
        "hybrid_reason":by_entry["hybrid"][ts]["exit_reason"],
        "profit_lock_exit":by_entry["profit_lock"][ts]["exit_time"],
        "profit_lock_net":by_entry["profit_lock"][ts]["net_pnl_pct"],
        "profit_lock_reason":by_entry["profit_lock"][ts]["exit_reason"]
    } for ts in common]
    payload={"summary":summary,"matched_entry_count":len(common),
             "matched_entries":comparisons,"trades":{k:v["trades"] for k,v in results.items()},
             "caveats":["V15 engine fills signals at the signal candle close; optimistic for a live strategy.",
                        "Baseline exit priority can select a profitable V before a same-bar protective stop.",
                        "Same-entry comparisons do not imply identical subsequent exposure."]}
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    for name,item in summary.items():print("EXP75",name,json.dumps(item,sort_keys=True))
    print("EXP74 matched entry count",len(common))
    print("Saved",out)


if __name__=="__main__":main()
