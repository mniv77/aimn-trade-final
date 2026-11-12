#!/usr/bin/env python3
"""EXP113 — post-profit reversal shape diagnostics, research only.

Read-only V16 baseline replay. Measure causal five-minute structure and
momentum after a SHORT first covers commissions. Compare winners and losing
givebacks without choosing thresholds or simulating an alternate strategy.
"""
import csv
import json
from collections import Counter
from pathlib import Path

import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as exp100

OUT=Path(__file__).resolve().parent/"kiss/results/exp113_reversal_shape"
FEE=2*exp79.FEE
WINDOWS=(3,6,12)

def write(path,records):
    if not records:return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)

def short_gross(entry,price):
    return 100*(entry/price-1)

def pct(a,b):
    return round(100*(a/b-1),6) if b else None

def shape(rows,closes,starts,i,w):
    if i-w+1<starts[i]:
        return {
            f"w{w}_close_move_pct":None,
            f"w{w}_efficiency":None,
            f"w{w}_up_close_fraction":None,
            f"w{w}_higher_low_fraction":None,
            f"w{w}_close_range_position":None,
        }
    start=i-w+1
    c=closes[start:i+1]
    lows=[float(rows[j]["low"]) for j in range(start,i+1)]
    highs=[float(rows[j]["high"]) for j in range(start,i+1)]
    changes=[c[j]-c[j-1] for j in range(1,len(c))]
    distance=sum(abs(d) for d in changes)
    high=max(highs);low=min(lows)
    return {
        f"w{w}_close_move_pct":pct(c[-1],c[0]),
        f"w{w}_efficiency":round(abs(c[-1]-c[0])/distance,6) if distance else 0,
        f"w{w}_up_close_fraction":round(sum(d>0 for d in changes)/len(changes),6),
        f"w{w}_higher_low_fraction":round(
            sum(lows[j]>lows[j-1] for j in range(1,len(lows)))/(len(lows)-1),6),
        f"w{w}_close_range_position":round((c[-1]-low)/(high-low),6) if high>low else 0.5,
    }

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    idx={t:i for i,t in enumerate(times)}
    if len(idx)!=len(times):raise AssertionError("Duplicate candle timestamps")
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    trades,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    starts=exp100.get_session_starts(times)
    ph,pl,counts=exp100.confirmed_pivots(rows,times,starts)
    all_candles=[]
    trade_summaries=[]
    for t in trades:
        ei=idx[t["entry_time"]];xi=idx[t["exit_time"]]
        if times[ei][:10]!=times[xi][:10]:raise AssertionError("Cross-session trade")
        entry=float(t["entry_price"])
        # For next-open exits or intrabar stops, exclude exit bar close.
        end=xi if t["exit_reason"] in ("SESSION_END","DATA_END") else xi-1
        observed=range(ei,end+1)
        first_fee=next((i for i in observed if short_gross(entry,closes[i])>FEE),None)
        if t["net_pnl_pct"]>0:
            group="WINNER_CONTROL"
        elif first_fee is None:
            group="NO_FEE_COVERING_CLOSE"
        else:
            group="LOSING_GIVEBACK"
        best=entry
        max_rebound=0.0
        observed_count=0
        for i in observed:
            best=min(best,closes[i])
            if first_fee is None or i<first_fee:continue
            state=exp100.structure(rows,times,starts,i,ph,pl,counts)
            rebound=pct(closes[i],best)
            max_rebound=max(max_rebound,rebound)
            previous_close=closes[i-1] if i>ei else None
            row={
                "symbol":symbol,"entry_time":t["entry_time"],"timestamp":times[i],
                "group_hindsight":group,"bars_since_entry":i-ei,
                "bars_since_fee_cover":i-first_fee,
                "close":closes[i],"short_gross_at_close_pct":round(short_gross(entry,closes[i]),6),
                "short_net_at_close_before_slippage_pct":round(short_gross(entry,closes[i])-FEE,6),
                "best_close_since_entry":best,"rebound_from_best_close_pct":rebound,
                "close_up_from_previous":closes[i]>previous_close if previous_close is not None else None,
                "confirmed_swing_state":state["structure_state"],
                "confirmed_high_sequence":state["high_sequence"],
                "confirmed_low_sequence":state["low_sequence"],
                "close_above_last_confirmed_high":state["close_above_last_confirmed_high"],
                "close_below_last_confirmed_low":state["close_below_last_confirmed_low"],
                "supertrend":st[i],"rsi":rsi[i],
                "original_exit_time_hindsight":t["exit_time"],
                "original_exit_reason_hindsight":t["exit_reason"],
                "original_net_pct_hindsight":t["net_pnl_pct"],
            }
            for w in WINDOWS:row.update(shape(rows,closes,starts,i,w))
            all_candles.append(row)
            observed_count+=1
        trade_summaries.append({
            "symbol":symbol,"entry_time":t["entry_time"],"exit_time":t["exit_time"],
            "exit_reason":t["exit_reason"],"original_net_pct":t["net_pnl_pct"],
            "group_hindsight":group,
            "first_fee_cover_time":times[first_fee] if first_fee is not None else None,
            "observed_post_fee_candles":observed_count,
            "maximum_completed_close_rebound_pct_hindsight":round(max_rebound,6),
        })
    write(OUT/(symbol.lower()+"_post_fee_candle_features.csv"),all_candles)
    write(OUT/(symbol.lower()+"_trade_groups.csv"),trade_summaries)
    groups=Counter(r["group_hindsight"] for r in trade_summaries)
    summary=[]
    for group in ("WINNER_CONTROL","LOSING_GIVEBACK","NO_FEE_COVERING_CLOSE"):
        members=[r for r in trade_summaries if r["group_hindsight"]==group]
        candle_rows=[r for r in all_candles if r["group_hindsight"]==group]
        item={"group":group,"trades":len(members),
              "net_sum_pct":round(sum(r["original_net_pct"] for r in members),6),
              "post_fee_candles":len(candle_rows),
              "mean_max_rebound_pct_hindsight":round(
                  sum(r["maximum_completed_close_rebound_pct_hindsight"] for r in members)/len(members),6
              ) if members else None}
        for w in WINDOWS:
            for metric in ("close_move_pct","efficiency","up_close_fraction",
                           "higher_low_fraction","close_range_position"):
                key=f"w{w}_{metric}"
                vals=[r[key] for r in candle_rows if r[key] is not None]
                item["mean_"+key]=round(sum(vals)/len(vals),6) if vals else None
                item["valid_"+key]=len(vals)
        summary.append(item)
    write(OUT/(symbol.lower()+"_descriptive_groups.csv"),summary)
    return {"trades":len(trades),"baseline_net_sum_pct":round(sum(t["net_pnl_pct"] for t in trades),6),
            "groups":dict(groups),"descriptive_groups":summary,
            "trade_summaries":trade_summaries}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP113","research_only":True,
        "goal":"Describe whether causal post-profit rebound shape differs for losing givebacks and winning controls.",
        "fee_cover_pct_gross":FEE,
        "windows":list(WINDOWS),
        "limitations":[
            "All windows use current and preceding completed same-session candles only.",
            "Group labels and actual exits are historical hindsight, never input features.",
            "Per-candle group averages overweight longer trades; do not interpret as independent samples.",
            "The first fee-cover candle is an observation, not a guaranteed executable profit.",
            "No exit threshold, new orders, alternative strategy simulation, or validation.",
            "Previously studied NVDA/AAPL sample only; summed returns are not compounded."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP113 — CAUSAL REVERSAL SHAPE AFTER PROFIT — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"trades:",s["trades"],"baseline net:",s["baseline_net_sum_pct"],
              "groups:",s["groups"])
        for g in s["descriptive_groups"]:print(" GROUP",g)
        for t in s["trade_summaries"]:
            print(" TRADE",t["entry_time"],t["group_hindsight"],
                  "net:",t["original_net_pct"],"first_fee:",t["first_fee_cover_time"],
                  "max_rebound:",t["maximum_completed_close_rebound_pct_hindsight"],
                  "exit:",t["exit_reason"])
    print("\nDetailed CSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
