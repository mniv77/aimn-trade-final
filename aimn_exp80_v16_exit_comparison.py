#!/usr/bin/env python3
"""EXP80: trade-by-trade comparison of EXP79 V16 SHORT exit variants.
Research-only audit. Reads existing CSVs; does not modify trading engines.
"""
import csv
import json
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parent
BASE=ROOT/"kiss/results/exp79_v16_early_exit"
OUT=ROOT/"kiss/results/exp80_v16_exit_comparison"
DATA=ROOT/"kiss/visual_research/aimn_nvda_candles.json"
VARIANTS={
    "A":"a_st_baseline_trades.csv",
    "B":"b_rebound_0_3_trades.csv",
    "C":"c_rebound_0_5_trades.csv",
}
def read_csv(path):
    with path.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))
def save_csv(path,rows,fields):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def fmt(v):
    return round(v,5)
def main():
    trades={k:read_csv(BASE/v) for k,v in VARIANTS.items()}
    candles=json.loads(DATA.read_text(encoding="utf-8"))
    candles.sort(key=lambda x:str(x["timestamp"]))
    times=[str(c["timestamp"]) for c in candles]
    index={t:i for i,t in enumerate(times)}
    if len(index)!=len(times):raise ValueError("Duplicate candle timestamps")
    for k,rows in trades.items():
        if len({r["entry_time"] for r in rows})!=len(rows):
            raise ValueError("Duplicate entries in variant "+k)
    lookup={k:{r["entry_time"]:r for r in rows} for k,rows in trades.items()}
    keys=sorted(set().union(*(set(x) for x in lookup.values())))
    OUT.mkdir(parents=True,exist_ok=True)
    comparison=[]
    for entry in keys:
        row={"entry_time":entry}
        for k in VARIANTS:
            t=lookup[k].get(entry)
            row[k+"_present"]=bool(t)
            row[k+"_exit_time"]=t["exit_time"] if t else ""
            row[k+"_exit_reason"]=t["exit_reason"] if t else ""
            row[k+"_net_pct"]=float(t["net_pnl_pct"]) if t else ""
        if all(lookup[k].get(entry) for k in VARIANTS):
            a,b,c=(lookup[k][entry] for k in ("A","B","C"))
            a_net=float(a["net_pnl_pct"])
            b_net=float(b["net_pnl_pct"])
            c_net=float(c["net_pnl_pct"])
            row["B_minus_A_pp"]=fmt(b_net-a_net)
            row["C_minus_A_pp"]=fmt(c_net-a_net)
            row["B_rescued_baseline_loser"]=a_net<=0 and b_net>0
            row["C_rescued_baseline_loser"]=a_net<=0 and c_net>0
            row["B_cut_profitable_trend"]=a_net>b_net and a_net>0
            row["C_cut_profitable_trend"]=a_net>c_net and a_net>0
            # If an early exit precedes the baseline exit, measure subsequent
            # same-session movement; this is hindsight, not a tradeable signal.
            for k,t in (("B",b),("C",c)):
                e=index.get(t["exit_time"]);end=index.get(a["exit_time"])
                if e is None or end is None:raise ValueError("Missing exit candle")
                if e<end and t["exit_time"][:10]==a["exit_time"][:10]:
                    after=candles[e+1:end+1]
                    if after:
                        low=min(float(x["low"]) for x in after)
                        high=max(float(x["high"]) for x in after)
                        exitprice=float(t["exit_price"])
                        row[k+"_future_low_below_exit_pct"]=fmt((exitprice/low-1)*100)
                        row[k+"_future_high_above_exit_pct"]=fmt((high/exitprice-1)*100)
                        row[k+"_baseline_close_after_early_exit_pct"]=fmt(
                            (float(a["exit_price"])/exitprice-1)*100)
                    else:
                        row[k+"_future_low_below_exit_pct"]=""
                        row[k+"_future_high_above_exit_pct"]=""
                        row[k+"_baseline_close_after_early_exit_pct"]=""
                else:
                    row[k+"_future_low_below_exit_pct"]=""
                    row[k+"_future_high_above_exit_pct"]=""
                    row[k+"_baseline_close_after_early_exit_pct"]=""
        else:
            for field in ("B_minus_A_pp","C_minus_A_pp","B_rescued_baseline_loser",
                          "C_rescued_baseline_loser","B_cut_profitable_trend",
                          "C_cut_profitable_trend"):
                row[field]=""
            for k in ("B","C"):
                for suffix in ("future_low_below_exit_pct",
                               "future_high_above_exit_pct",
                               "baseline_close_after_early_exit_pct"):
                    row[k+"_"+suffix]=""
        comparison.append(row)
    fields=list(comparison[0]) if comparison else ["entry_time"]
    save_csv(OUT/"trade_by_trade.csv",comparison,fields)
    matched=[r for r in comparison if all(r[k+"_present"] for k in VARIANTS)]
    results={}
    for k in ("B","C"):
        deltas=[r[k+"_minus_A_pp"] for r in matched]
        results[k]={
            "matched_trades":len(matched),
            "improved_vs_baseline":sum(x>0 for x in deltas),
            "worse_vs_baseline":sum(x<0 for x in deltas),
            "unchanged_vs_baseline":sum(x==0 for x in deltas),
            "net_difference_pp_sum":fmt(sum(deltas)),
            "rescued_baseline_losers":sum(bool(r[k+"_rescued_baseline_loser"]) for r in matched),
            "cut_profitable_trends":sum(bool(r[k+"_cut_profitable_trend"]) for r in matched),
            "early_exits":dict(Counter(t["exit_reason"] for t in trades[k])),
        }
    report={
        "experiment":"EXP80",
        "baseline_trades":len(trades["A"]),
        "B_trades":len(trades["B"]),
        "C_trades":len(trades["C"]),
        "matched_entries":len(matched),
        "all_entries_match":len(matched)==len(keys)==len(trades["A"]),
        "baseline_net_pct_sum":fmt(sum(float(x["net_pnl_pct"]) for x in trades["A"])),
        "results":results,
        "note":"Subsequent price lows/highs are hindsight observations and cannot establish a live exit rule. Compare exit prices and entry timestamps before interpreting.",
    }
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP80 — V16 EXIT TRADE-BY-TRADE AUDIT — RESEARCH ONLY")
    print(json.dumps(report,indent=2))
    print("Detailed trade comparison:",OUT/"trade_by_trade.csv")
if __name__=="__main__":main()
