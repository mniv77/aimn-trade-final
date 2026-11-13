#!/usr/bin/env python3
"""EXP99 — Mountain exit failure forensic, not a new strategy.

Audit every trade whose realized exit differs between EXP97 BASELINE and
MOUNTAIN_24. Completed-candle price geometry at the exit signal is
separated from later diagnostic movement and realized outcome. In
particular inspect the single large AAPL harmful exit without using its
outcome to define a new threshold.

All computations are read-only, and the production engine is untouched.
"""
import csv
import json
from pathlib import Path
from collections import defaultdict
import aimn_exp83_v16_structural_exit as base
import aimn_exp97_mountain_exit_test as exp97
import aimn_exp93_sideways_research as exp93

OUT=Path(__file__).resolve().parent/"kiss/results/exp99_mountain_exit_forensics"
WINDOWS=(5,12,24,36)

def p(a,b):
    return round(100*(a/b-1),6) if b else None

def geometry(rows,i,w,day_start):
    if i-w+1<day_start:
        return None
    part=rows[i-w+1:i+1]
    cs=[float(r["close"]) for r in part]
    hs=[float(r["high"]) for r in part]
    ls=[float(r["low"]) for r in part]
    high=max(hs); low=min(ls)
    denom=sum(abs(cs[k]-cs[k-1]) for k in range(1,w))
    return {
        "move_pct":p(cs[-1],cs[0]),
        "range_pct":p(high,low),
        "efficiency":round(abs(cs[-1]-cs[0])/denom,6) if denom else 0,
        "range_close_fraction":round((cs[-1]-low)/(high-low),6) if high>low else 0.5,
        "higher_lows":sum(ls[k]>ls[k-1] for k in range(1,w)),
        "lower_lows":sum(ls[k]<ls[k-1] for k in range(1,w)),
        "lower_highs":sum(hs[k]<hs[k-1] for k in range(1,w)),
        "higher_highs":sum(hs[k]>hs[k-1] for k in range(1,w)),
        "close_break_prior_high":int(cs[-1]>max(hs[:-1])),
        "close_break_prior_low":int(cs[-1]<min(ls[:-1])),
    }

def write(path,items):
    if not items:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(items[0]))
        writer.writeheader();writer.writerows(items)

def audit_symbol(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    idx={t:i for i,t in enumerate(times)}
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    state=[base.get_market_state(closes,i) for i in range(len(rows))]
    a,_,_=exp97.simulate(rows,st,rsi,state,"BASELINE")
    b,events,_=exp97.simulate(rows,st,rsi,state,"MOUNTAIN_24")
    truth,_,_,_=base.simulate(rows,st,rsi,state,None,False)
    if a!=truth:
        raise AssertionError(symbol+" EXP83 baseline mismatch")
    amap={x["entry_time"]:x for x in a}
    bmap={x["entry_time"]:x for x in b}
    if set(amap)!=set(bmap):
        raise AssertionError(symbol+" entry sets different; audit pairing invalid")
    eventmap={x["entry_time"]:x for x in events}
    starts=[]
    daystart=0
    for i,t in enumerate(times):
        if i and t[:10]!=times[i-1][:10]:
            daystart=i
        starts.append(daystart)
    items=[]
    for entry in sorted(amap):
        original=amap[entry];new=bmap[entry]
        if original["exit_time"]==new["exit_time"] and original["exit_price"]==new["exit_price"] and original["exit_reason"]==new["exit_reason"]:
            continue
        if entry not in eventmap:
            raise AssertionError("Changed trade without mountain event: "+entry)
        event=eventmap[entry]
        signal_i=idx[event["signal_time"]]
        entry_i=idx[entry]
        exit_i=idx[new["exit_time"]]
        original_exit_i=idx[original["exit_time"]]
        if original_exit_i<exit_i:
            raise AssertionError("Mountain exit later than baseline")
        close=closes[signal_i]
        entry_price=float(new["entry_price"])
        best_close=min([entry_price]+closes[entry_i:signal_i+1])
        before=rows[entry_i:signal_i+1]
        high_since_entry=max(float(x["high"]) for x in before)
        low_since_entry=min(float(x["low"]) for x in before)
        later=rows[exit_i:original_exit_i+1]
        future_low=min(float(x["low"]) for x in later)
        future_high=max(float(x["high"]) for x in later)
        net_delta=round(new["net_pnl_pct"]-original["net_pnl_pct"],6)
        record={
            "symbol":symbol,"entry_time":entry,
            "signal_time":event["signal_time"],"mountain_exit_time":new["exit_time"],
            "baseline_exit_time_hindsight":original["exit_time"],
            "baseline_exit_reason_hindsight":original["exit_reason"],
            "baseline_net_pct_hindsight":original["net_pnl_pct"],
            "mountain_net_pct_hindsight":new["net_pnl_pct"],
            "net_delta_pp_hindsight":net_delta,
            "label_hindsight":"HELPED" if net_delta>0 else "HURT" if net_delta<0 else "UNCHANGED",
            "bars_held_at_signal":signal_i-entry_i+1,
            "signal_close":round(close,6),
            "gross_short_at_signal_pct":p(entry_price,close),
            "best_short_close_profit_pct":p(entry_price,best_close),
            "giveback_from_best_close_pct":p(close,best_close),
            "high_since_entry_pct":p(high_since_entry,entry_price),
            "low_since_entry_pct":p(low_since_entry,entry_price),
            "exp93_sideways_at_signal":int(exp93.is_sideways(exp93.metrics(rows,signal_i))),
            "future_low_from_mountain_fill_pct_hindsight":p(float(new["exit_price"]),future_low),
            "future_high_from_mountain_fill_pct_hindsight":p(future_high,float(new["exit_price"])),
            "baseline_exit_close_hindsight":closes[original_exit_i],
            "mountain_fill_price":new["exit_price"]
        }
        for w in WINDOWS:
            g=geometry(rows,signal_i,w,starts[signal_i])
            for key in ("move_pct","range_pct","efficiency","range_close_fraction",
                        "higher_lows","lower_lows","lower_highs","higher_highs",
                        "close_break_prior_high","close_break_prior_low"):
                record["w"+str(w)+"_"+key]=g[key] if g else None
        items.append(record)
    write(OUT/(symbol.lower()+"_changed_exit_forensics.csv"),items)
    return {
        "total_baseline_trades":len(a),
        "changed_exits":len(items),
        "helped":sum(x["label_hindsight"]=="HELPED" for x in items),
        "hurt":sum(x["label_hindsight"]=="HURT" for x in items),
        "sum_changed_exit_delta_pp":round(sum(x["net_delta_pp_hindsight"] for x in items),6),
        "events":items
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP99","research_only":True,
        "description":"All changed Mountain 24 exits with their pre-signal mountain context and subsequent hindsight path.",
        "method":"Complete unchanged EXP97 BASELINE and MOUNTAIN_24 reruns; paired by exact entry; features from completed same-session candles.",
        "cautions":[
            "Only five changed trades, not sufficient for fitting new predictive thresholds.",
            "Outcomes, future highs/lows and baseline exit details are hindsight, never exit-rule inputs.",
            "Future extremes are not achievable fills or a profit forecast.",
            "Full-history inspection is in-sample; further unseen dates needed.",
            "No slippage, no portfolio return estimation, no live trades."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=audit_symbol(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP99 — MOUNTAIN 24 EXIT FORENSICS — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"changed:",s["changed_exits"],
              "helped:",s["helped"],"hurt:",s["hurt"],
              "delta pp:",s["sum_changed_exit_delta_pp"])
        for e in s["events"]:
            print(" ",e["entry_time"],"signal:",e["signal_time"],
                  e["label_hindsight"],"delta:",e["net_delta_pp_hindsight"],
                  "gross_at_signal:",e["gross_short_at_signal_pct"],
                  "giveback:",e["giveback_from_best_close_pct"],
                  "w12_move:",e["w12_move_pct"],
                  "w24_move:",e["w24_move_pct"],
                  "w36_move:",e["w36_move_pct"],
                  "w24_position:",e["w24_range_close_fraction"],
                  "future_low_pct:",e["future_low_from_mountain_fill_pct_hindsight"])
    print("\nReports:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
