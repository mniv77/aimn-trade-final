#!/usr/bin/env python3
"""EXP98 — Mountain 24 generalization and paired trade audit.

Research only. Compare complete EXP97 BASELINE and MOUNTAIN_24 reruns.
Attribute realized trade-return differences by matching entry timestamps.
Report per-month performance, concentration, entry-set invariance and
whether changed exits improved net return. All decisions are unchanged
from EXP97. NO parameter fitting or live changes.
"""
import csv
import json
from collections import defaultdict,Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp97_mountain_exit_test as exp97

OUT=Path(__file__).resolve().parent/"kiss/results/exp98_mountain_generalization"

def save_csv(path,records):
    if not records:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)

def rnd(value):
    return round(float(value),6)

def monthly(trades):
    by=defaultdict(list)
    for t in trades:
        by[str(t["entry_time"])[:7]].append(t)
    return {m:{"trades":len(ts),"winners":sum(t["net_pnl_pct"]>0 for t in ts),
               "net_pct_sum":rnd(sum(t["net_pnl_pct"] for t in ts))}
            for m,ts in sorted(by.items())}

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    expected,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    baseline,_,_=exp97.simulate(rows,st,rsi,market,"BASELINE")
    mountain,events,rejected=exp97.simulate(rows,st,rsi,market,"MOUNTAIN_24")
    if expected!=baseline:
        raise AssertionError(symbol+": baseline drift")
    # A mismatch in entries is a legitimate possibility after an early exit.
    # Never silently pair different entry sets or pretend full-strategy deltas
    # can be attributed to matched trades only.
    a={t["entry_time"]:t for t in baseline}
    b={t["entry_time"]:t for t in mountain}
    if len(a)!=len(baseline) or len(b)!=len(mountain):
        raise AssertionError(symbol+": duplicate entry timestamps")
    common=sorted(set(a)&set(b))
    only_base=sorted(set(a)-set(b))
    only_mountain=sorted(set(b)-set(a))
    paired=[]
    for entry in common:
        x,y=a[entry],b[entry]
        delta=rnd(y["net_pnl_pct"]-x["net_pnl_pct"])
        changed=(x["exit_time"]!=y["exit_time"] or
                 x["exit_reason"]!=y["exit_reason"] or
                 x["exit_price"]!=y["exit_price"])
        paired.append({
            "symbol":symbol,"entry_time":entry,"entry_month":entry[:7],
            "baseline_exit_time":x["exit_time"],
            "mountain_exit_time":y["exit_time"],
            "baseline_exit_reason":x["exit_reason"],
            "mountain_exit_reason":y["exit_reason"],
            "baseline_net_pct":x["net_pnl_pct"],
            "mountain_net_pct":y["net_pnl_pct"],
            "mountain_minus_baseline_pp":delta,
            "exit_changed":int(changed),
            "result":"HELPED" if delta>0 else "HURT" if delta<0 else "UNCHANGED",
        })
    save_csv(OUT/f"{symbol.lower()}_paired_trades.csv",paired)
    save_csv(OUT/f"{symbol.lower()}_baseline_trades.csv",baseline)
    save_csv(OUT/f"{symbol.lower()}_mountain24_trades.csv",mountain)
    save_csv(OUT/f"{symbol.lower()}_mountain24_signals.csv",events)
    # Every row below is an actual realized trade; monthly grouping is by
    # entry month, never the hindsight-selected 'best' month.
    month_records=[]
    base_month=monthly(baseline)
    mountain_month=monthly(mountain)
    for month in sorted(set(base_month)|set(mountain_month)):
        x=base_month.get(month,{"trades":0,"winners":0,"net_pct_sum":0})
        y=mountain_month.get(month,{"trades":0,"winners":0,"net_pct_sum":0})
        month_records.append({
            "symbol":symbol,"entry_month":month,
            "baseline_trades":x["trades"],"mountain_trades":y["trades"],
            "baseline_winners":x["winners"],"mountain_winners":y["winners"],
            "baseline_net_pct_sum":x["net_pct_sum"],
            "mountain_net_pct_sum":y["net_pct_sum"],
            "delta_pp":rnd(y["net_pct_sum"]-x["net_pct_sum"])
        })
    save_csv(OUT/f"{symbol.lower()}_monthly.csv",month_records)
    base_total=sum(t["net_pnl_pct"] for t in baseline)
    mountain_total=sum(t["net_pnl_pct"] for t in mountain)
    full_delta=rnd(mountain_total-base_total)
    paired_delta=rnd(sum(t["mountain_minus_baseline_pp"] for t in paired))
    unpaired_delta=rnd(
        sum(b[t]["net_pnl_pct"] for t in only_mountain)-
        sum(a[t]["net_pnl_pct"] for t in only_base))
    if abs(full_delta-paired_delta-unpaired_delta)>0.00001:
        raise AssertionError(symbol+": attribution reconciliation failed")
    changed=[t for t in paired if t["exit_changed"]]
    benefits=sorted((t["mountain_minus_baseline_pp"] for t in paired if t["mountain_minus_baseline_pp"]>0),reverse=True)
    losses=sorted((t["mountain_minus_baseline_pp"] for t in paired if t["mountain_minus_baseline_pp"]<0))
    return {
        "baseline":exp97.summary(baseline),
        "mountain24":exp97.summary(mountain),
        "full_strategy_delta_pp":full_delta,
        "paired_delta_pp":paired_delta,
        "unpaired_delta_pp":unpaired_delta,
        "matched_entries":len(common),
        "baseline_only_entries":only_base,
        "mountain_only_entries":only_mountain,
        "changed_exit_count":len(changed),
        "changed_exit_helped":sum(t["result"]=="HELPED" for t in changed),
        "changed_exit_hurt":sum(t["result"]=="HURT" for t in changed),
        "largest_help_pp":rnd(benefits[0]) if benefits else None,
        "largest_hurt_pp":rnd(losses[0]) if losses else None,
        "top_two_help_sum_pp":rnd(sum(benefits[:2])),
        "mountain_exit_signals":len(events),
        "rejected_warning_evaluations":rejected["SIDEWAYS_WITHOUT_UPWARD_MOUNTAIN_REVERSAL"],
        "monthly":month_records,
        "paired_trades":paired,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP98",
        "research_only":True,
        "question":"Does Mountain 24 generalize across NVDA and AAPL, or depend on a few exits?",
        "method":"Unchanged EXP97 full causal reruns, exact baseline invariant, entry-time matching, month-by-month realized return and complete attribution.",
        "cautions":[
            "This is an in-sample forensic and temporal stability audit, NOT out-of-sample validation.",
            "24 bars was chosen after seeing EXP97 results; monthly comparisons cannot undo that selection bias.",
            "All sums are percentage points across trades, NOT compounded portfolio return.",
            "Entry mismatches, if any, are reported and reconciled rather than discarded.",
            "Rejected warning evaluations are not unique trade opportunities.",
            "Only NVDA and AAPL historical SHORT data; slippage, portfolio allocation and LONG not modeled.",
            "Do not deploy a rule on this evidence."
        ],
        "symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP98 — MOUNTAIN 24 GENERALIZATION AUDIT — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,
              "baseline:",s["baseline"]["net_pct_sum"],
              "mountain24:",s["mountain24"]["net_pct_sum"],
              "delta pp:",s["full_strategy_delta_pp"])
        print("matched entries:",s["matched_entries"],
              "baseline-only:",len(s["baseline_only_entries"]),
              "mountain-only:",len(s["mountain_only_entries"]))
        print("changed exits:",s["changed_exit_count"],
              "helped:",s["changed_exit_helped"],
              "hurt:",s["changed_exit_hurt"],
              "largest help:",s["largest_help_pp"],
              "largest hurt:",s["largest_hurt_pp"])
        print("paired delta:",s["paired_delta_pp"],
              "unpaired delta:",s["unpaired_delta_pp"])
        for m in s["monthly"]:
            print(" ",m["entry_month"],
                  "baseline:",m["baseline_net_pct_sum"],
                  "mountain:",m["mountain_net_pct_sum"],
                  "delta:",m["delta_pp"],
                  "trades:",m["baseline_trades"],"/",m["mountain_trades"])
    print("\nFiles:",OUT)
    print("No trading logic changed.")

if __name__=="__main__":
    main()
