#!/usr/bin/env python3
"""EXP88 — session-safe V16 transition geometry stability audit.

Independent research script. Uses unchanged EXP83 V16/ST trades. Compares
EXP87-style 12-candle geometry with same-session-only geometry, reports which
signals lack 12 prior bars, and examines descriptive winner/loser separation.
No optimized thresholds, no backtested filter, no production changes.
"""
import csv
import json
from pathlib import Path
from collections import Counter
import aimn_exp83_v16_structural_exit as exp83

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp88_session_safe_geometry"
WIN=12
FEATURES=("peak_age_bars","peak_to_signal_drawdown_pct","prior_range_pct",
          "range_position","direction_changes","down_close_count",
          "up_close_count","down_motion_pct","up_motion_pct",
          "up_down_ratio")

def round5(x):
    return round(x,5) if x is not None else None

def geometry(rows,i,session_safe):
    start=max(0,i-WIN)
    if session_safe:
        day=str(rows[i]["timestamp"])[:10]
        while start<i and str(rows[start]["timestamp"])[:10]!=day:
            start+=1
    prior=rows[start:i]
    if not prior:return None
    segment=rows[start:i+1]
    c=[float(r["close"]) for r in segment]
    peak_i=max(range(start,i),key=lambda j:float(rows[j]["high"]))
    peak=float(rows[peak_i]["high"])
    lo=min(float(r["low"]) for r in prior)
    now=c[-1]
    up_count=0; down_count=0; changes=0; previous=0
    up_motion=0.0;down_motion=0.0
    for a,b in zip(c[:-1],c[1:]):
        sign=(1 if b>a else (-1 if b<a else 0))
        if sign>0:up_count+=1;up_motion+=b-a
        if sign<0:down_count+=1;down_motion+=a-b
        if sign and previous and sign!=previous:changes+=1
        if sign:previous=sign
    return {
      "bars_of_prior_context":len(prior),
      "peak_age_bars":i-peak_i,
      "peak_to_signal_drawdown_pct":round5(100*(peak/now-1)),
      "prior_range_pct":round5(100*(peak/lo-1)) if lo else None,
      "range_position":round5((now-lo)/(peak-lo)) if peak>lo else None,
      "direction_changes":changes,"down_close_count":down_count,
      "up_close_count":up_count,
      "down_motion_pct":round5(100*down_motion/now),
      "up_motion_pct":round5(100*up_motion/now),
      "up_down_ratio":round5(up_motion/down_motion) if down_motion else None,
    }

def avg(items,key):
    vals=[r[key] for r in items if r.get(key) is not None]
    return round5(sum(vals)/len(vals)) if vals else None

def group(items):
    return {"count":len(items),"mean_features":{key:avg(items,key) for key in FEATURES}}

def save(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r.keys()))
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(set(times))!=len(times):raise ValueError("duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    st=exp83.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=exp83.rsi_wilder(closes)
    market=[exp83.get_market_state(closes,i) for i in range(len(rows))]
    trades,candidates,rejected,blocked=exp83.simulate(rows,st,rsi,market,None,False)
    if blocked:raise ValueError("baseline structural block unexpected")
    by_entry={t["entry_time"]:t for t in trades}
    data=[]
    for i in range(35,len(rows)):
        if exp83.is_major_long_to_short_reversal(highs,lows,closes,market,i) is None:continue
        nt=times[i+1] if i+1<len(rows) else None
        match=by_entry.get(nt) if nt and nt[:10]==times[i][:10] else None
        same=geometry(rows,i,True)
        cross=geometry(rows,i,False)
        # A V16 signal on the first candle of a session has no same-day
        # predecessor. Keep the signal/trade mapping and record missing
        # geometry rather than silently dropping an accepted trade.
        rec={"symbol":symbol,"signal_time":times[i],"ST_signal":st[i],
          "accepted":match is not None,
          "net_trade_pct":match["net_pnl_pct"] if match else None,
          "winner":match["net_pnl_pct"]>0 if match else None,
          "has_full_session_window":same is not None and same["bars_of_prior_context"]==WIN,
          "prior_bars_same_session":same["bars_of_prior_context"] if same else 0,
          "window_crossed_session_in_exp87":same is None or same["bars_of_prior_context"]<WIN,
          "missing_same_session_geometry":same is None}
        if same is not None:
            rec.update(same)
        else:
            rec.update({key:None for key in FEATURES})
        for key in FEATURES:
            rec["exp87_"+key]=cross.get(key)
            v=same.get(key) if same else None; old=cross.get(key) if cross else None
            rec["changed_"+key]=(v!=old)
        data.append(rec)
    accepted=[r for r in data if r["accepted"]]
    if len(accepted)!=len(trades) or len(data)!=candidates:
        raise ValueError(f"{symbol}: candidate/entry mapping mismatch: {len(data)}/{candidates} candidates; {len(accepted)}/{len(trades)} trades")
    winners=[r for r in accepted if r["winner"]]
    losers=[r for r in accepted if not r["winner"]]
    complete=[r for r in accepted if r["has_full_session_window"]]
    complete_winners=[r for r in complete if r["winner"]]
    complete_losers=[r for r in complete if not r["winner"]]
    save(OUT/(symbol.lower()+"_signals.csv"),data)
    return {
      "baseline":{"candidates":candidates,"trades":len(trades),
          "winners":len(winners),"losers":len(losers),
          "net_pct_sum":round5(sum(t["net_pnl_pct"] for t in trades)),
          "rejected":rejected},
      "session_boundary":{"all_signals":len(data),
          "signals_with_incomplete_same_session_window":sum(not r["has_full_session_window"] for r in data),
          "accepted_with_incomplete_window":sum(not r["has_full_session_window"] for r in accepted),
          "accepted_with_no_same_session_predecessor":sum(r["missing_same_session_geometry"] for r in accepted),
          "accepted_with_any_geometry_change":sum(any(r["changed_"+k] for k in FEATURES) for r in accepted)},
      "same_session_all":{"winners":group(winners),"losers":group(losers)},
      "full_12bar_same_session_only":{"winners":group(complete_winners),
                                     "losers":group(complete_losers)},
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={"experiment":"EXP88","research_only":True,
      "note":"No new strategy or live code. Same-session feature calculations omit bars from prior sessions. Restricted full-window analysis is descriptive, not a trade filter.",
      "limitation":"Small in-sample cohort and predefined 12-bar window; statistics may not generalize.",
      "symbols":{}}
    for sym,p in exp83.DATA.items():result["symbols"][sym]=run(sym,p)
    (OUT/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("EXP88 — SESSION-SAFE V16 GEOMETRY — RESEARCH ONLY")
    print(json.dumps(result,indent=2))
    print("Detailed reports:",OUT)
if __name__=="__main__":main()
