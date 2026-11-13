#!/usr/bin/env python3
"""EXP73: same V15 entries, baseline vs two-close trailing confirmation.

No broker orders. Summed trade percentages are not portfolio returns.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from engine.kiss_backtest import run_kiss_backtest as baseline
from kiss.exp73_kiss_two_close_engine import run_kiss_backtest as two_close


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
    p.add_argument("--output",default="/tmp/exp73_trailing_confirmation.json")
    a=p.parse_args()
    rows=json.loads(Path(a.candles).read_text(encoding="utf-8"))
    results={"baseline":run(rows,baseline),"two_close":run(rows,two_close)}
    # The two engines share entry logic, but altered exits change which later
    # entries are available. Never describe trade counts as matched pairs.
    summary={name:summarize(result) for name,result in results.items()}
    by_entry={}
    for name,result in results.items():
        by_entry[name]={str(t["entry_time"]):t for t in result["trades"]}
    common=sorted(set(by_entry["baseline"]) & set(by_entry["two_close"]))
    comparisons=[{
        "entry_time":ts,
        "baseline_exit":by_entry["baseline"][ts]["exit_time"],
        "filtered_exit":by_entry["two_close"][ts]["exit_time"],
        "baseline_net":by_entry["baseline"][ts]["net_pnl_pct"],
        "filtered_net":by_entry["two_close"][ts]["net_pnl_pct"],
        "net_difference":round(by_entry["two_close"][ts]["net_pnl_pct"]-
                               by_entry["baseline"][ts]["net_pnl_pct"],5),
        "baseline_reason":by_entry["baseline"][ts]["exit_reason"],
        "filtered_reason":by_entry["two_close"][ts]["exit_reason"]
    } for ts in common]
    payload={"summary":summary,"matched_entry_count":len(common),
             "matched_entries":comparisons,"trades":{k:v["trades"] for k,v in results.items()},
             "caveats":["V15 engine fills signals at the signal candle close; optimistic for a live strategy.",
                        "Baseline exit priority can select a profitable V before a same-bar protective stop.",
                        "Same-entry comparisons do not imply identical subsequent exposure."]}
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    for name,item in summary.items():print("EXP73",name,json.dumps(item,sort_keys=True))
    print("EXP73 matched entry count",len(common))
    print("Saved",out)


if __name__=="__main__":main()
