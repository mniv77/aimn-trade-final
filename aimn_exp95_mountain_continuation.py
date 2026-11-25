#!/usr/bin/env python3
"""EXP95 — causal mountain continuation versus reversal evidence audit.

Research only. At each EXP93 sideways exit warning, compute ONLY completed
candles available at that signal. Compare those features to the EXP94
paired, realized exit outcome (hindsight LABEL, never a feature).
No threshold fitting, new exits, production changes or live orders.
"""
import csv
import json
from collections import Counter
from pathlib import Path

import aimn_exp83_v16_structural_exit as base
import aimn_exp93_sideways_research as exp93

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp95_mountain_continuation"
WINDOWS=(3,5,8,12)

def rounded(x):
    return round(x,6) if x is not None else None

def features(rows, i, entry_i, entry_price, lowest_close):
    day=str(rows[i]["timestamp"])[:10]
    c=[float(r["close"]) for r in rows]
    h=[float(r["high"]) for r in rows]
    l=[float(r["low"]) for r in rows]
    o=[float(r["open"]) for r in rows]
    result={}
    for w in WINDOWS:
        prefix=f"w{w}_"
        if i-w+1<0 or any(str(rows[k]["timestamp"])[:10]!=day for k in range(i-w+1,i+1)):
            for name in ("return_pct","up_candles","down_candles","higher_highs","higher_lows",
                         "lower_highs","lower_lows","range_pct","close_position","close_above_prior_high"):
                result[prefix+name]=None
            continue
        start=i-w+1
        hi=max(h[start:i+1])
        lo=min(l[start:i+1])
        result[prefix+"return_pct"]=rounded(100*(c[i]/c[start]-1))
        result[prefix+"up_candles"]=sum(c[k]>o[k] for k in range(start,i+1))
        result[prefix+"down_candles"]=sum(c[k]<o[k] for k in range(start,i+1))
        result[prefix+"higher_highs"]=sum(h[k]>h[k-1] for k in range(start+1,i+1))
        result[prefix+"higher_lows"]=sum(l[k]>l[k-1] for k in range(start+1,i+1))
        result[prefix+"lower_highs"]=sum(h[k]<h[k-1] for k in range(start+1,i+1))
        result[prefix+"lower_lows"]=sum(l[k]<l[k-1] for k in range(start+1,i+1))
        result[prefix+"range_pct"]=rounded(100*(hi/lo-1))
        result[prefix+"close_position"]=rounded((c[i]-lo)/(hi-lo)) if hi>lo else None
        # Prior high excludes current bar: causal resistance test.
        result[prefix+"close_above_prior_high"]=int(c[i]>max(h[start:i])) if w>1 else None
    result["entry_to_signal_close_gross_short_pct"]=rounded(100*(entry_price/c[i]-1))
    result["best_close_gross_short_pct"]=rounded(100*(entry_price/lowest_close-1))
    result["giveback_from_lowest_close_pct"]=rounded(100*(c[i]/lowest_close-1))
    result["bars_held_at_warning"]=i-entry_i+1
    result["signal_close"]=rounded(c[i])
    return result

def write_csv(path,items):
    if not items:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(items[0]))
        w.writeheader()
        w.writerows(items)

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    idx={t:i for i,t in enumerate(times)}
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    original,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    baseline,_,_,_,_,_=exp93.simulate(rows,st,rsi,market,"BASELINE")
    sideways,_,_,_,events,_=exp93.simulate(rows,st,rsi,market,"SIDEWAYS_EXIT")
    if original!=baseline:
        raise AssertionError(symbol+": baseline drift")
    a={t["entry_time"]:t for t in baseline}
    b={t["entry_time"]:t for t in sideways}
    if set(a)!=set(b):
        raise AssertionError(symbol+": paired entries changed")
    records=[]
    for event in events:
        entry=event["entry_time"]
        orig=a[entry]
        alt=b[entry]
        if alt["exit_reason"]!="SIDEWAYS_EXIT":
            raise AssertionError(symbol+": unmatched sideways event "+entry)
        signal_i=idx[event["signal_time"]]
        entry_i=idx[entry]
        baseline_exit_i=idx[orig["exit_time"]]
        sideways_exit_i=idx[alt["exit_time"]]
        if baseline_exit_i<sideways_exit_i:
            raise AssertionError("Baseline exit precedes alternative exit")
        # Reconstruct best completed closing price through the warning.
        lowest_close=min([float(rows[entry_i]["open"])] +
                         [float(rows[k]["close"]) for k in range(entry_i,signal_i+1)])
        entry_price=float(alt["entry_price"])
        feat=features(rows,signal_i,entry_i,entry_price,lowest_close)
        delta=rounded(alt["net_pnl_pct"]-orig["net_pnl_pct"])
        # Label depends on later realized fills; never used to choose features.
        label="EXIT_HELPED" if delta>0 else "EXIT_HURT" if delta<0 else "UNCHANGED"
        later=rows[sideways_exit_i:baseline_exit_i+1]
        later_low=min(float(r["low"]) for r in later)
        later_high=max(float(r["high"]) for r in later)
        record={
            "symbol":symbol,"entry_time":entry,"signal_time":event["signal_time"],
            "sideways_exit_time":alt["exit_time"],"baseline_exit_time":orig["exit_time"],
            "baseline_exit_reason":orig["exit_reason"],
            "label_hindsight":label,"net_exit_delta_pp_hindsight":delta,
            "baseline_net_pct_hindsight":orig["net_pnl_pct"],
            "sideways_net_pct_hindsight":alt["net_pnl_pct"],
            "future_max_decline_pct_hindsight":rounded(100*(float(alt["exit_price"])/later_low-1)),
            "future_max_rebound_pct_hindsight":rounded(100*(later_high/float(alt["exit_price"])-1)),
            "sideways_efficiency":event["efficiency"],
            "sideways_displacement_fraction":event["displacement_fraction"],
            **feat,
        }
        records.append(record)
    records.sort(key=lambda x:x["signal_time"])
    write_csv(OUT/f"{symbol.lower()}_event_features.csv",records)
    return {
        "events":len(records),
        "helped":sum(r["label_hindsight"]=="EXIT_HELPED" for r in records),
        "hurt":sum(r["label_hindsight"]=="EXIT_HURT" for r in records),
        "sum_delta_pp":rounded(sum(r["net_exit_delta_pp_hindsight"] for r in records)),
        "records":records,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP95","research_only":True,
        "question":"At a sideways warning, do completed-candle trend structure and countertrend strength differ between exits that later helped and exits that hurt?",
        "method":"Causal completed-candle features at signal time; paired EXP93 strategy reruns; hindsight outcomes used for analysis only.",
        "cautions":[
            "Only 10 selected sideways warnings across NVDA/AAPL. This is descriptive, not predictive validation.",
            "No new exit policy is tested or optimized. No threshold should be chosen from these cases alone.",
            "High/low counts are consecutive-bar comparisons, not confirmed swing pivots.",
            "A prior-high breakout is evaluated at candle close using earlier candles only.",
            "Hindsight intrabar extremes are not executable returns.",
            "Session-local windows are unavailable when insufficient same-day bars exist.",
            "No LONG or multi-symbol portfolio logic. No slippage.",
        ],
        "symbols":{},
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP95 — MOUNTAIN CONTINUATION / REVERSAL FEATURES — RESEARCH ONLY")
    for symbol,data in report["symbols"].items():
        print("\n",symbol,"warnings:",data["events"],
              "helped:",data["helped"],"hurt:",data["hurt"],
              "paired delta pp:",data["sum_delta_pp"])
        for r in data["records"]:
            print(" ",r["signal_time"],r["label_hindsight"],
                  "delta:",r["net_exit_delta_pp_hindsight"],
                  "3bar_return:",r["w3_return_pct"],
                  "5bar_return:",r["w5_return_pct"],
                  "8bar_return:",r["w8_return_pct"],
                  "5bar_higher_lows:",r["w5_higher_lows"],
                  "5bar_lower_lows:",r["w5_lower_lows"],
                  "5bar_breakout:",r["w5_close_above_prior_high"],
                  "giveback:",r["giveback_from_lowest_close_pct"])
    print("\nDetailed feature CSV and JSON:",OUT)
    print("No trading logic changed.")

if __name__=="__main__":
    main()
