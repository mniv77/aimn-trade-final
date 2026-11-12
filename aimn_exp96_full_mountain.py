#!/usr/bin/env python3
"""EXP96 — Full mountain geometry, pause and resumption research.

READ-ONLY. Uses completed same-session candles and unchanged EXP83/EXP93
strategy replays. Produces (1) every valid 12-candle window across all
sessions, (2) a chronological 5m trajectory for every baseline SHORT
trade, and (3) all EXP93 sideways exit warnings with pre-warning and
post-warning context. Future data are clearly labeled hindsight.
No new strategy, fitted thresholds, trading orders or production edits.
"""
import csv
import json
from collections import Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp93_sideways_research as exp93

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp96_full_mountain"
LOOKBACKS=(5,12,24,36)

def pct(a,b):
    return round(100*(a/b-1),6) if b else None

def save(path,items):
    if not items:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)

def geometry(rows,i,w,session_start):
    if i-w+1<session_start:
        return None
    part=rows[i-w+1:i+1]
    c=[float(r["close"]) for r in part]
    h=[float(r["high"]) for r in part]
    l=[float(r["low"]) for r in part]
    total=sum(abs(c[k]-c[k-1]) for k in range(1,len(c)))
    spread=max(h)-min(l)
    return {
        "net_move_pct":pct(c[-1],c[0]),
        "range_pct":pct(max(h),min(l)),
        "efficiency":round(abs(c[-1]-c[0])/total,6) if total else 0,
        "close_position_in_range":round((c[-1]-min(l))/spread,6) if spread else 0.5,
        "higher_lows":sum(l[k]>l[k-1] for k in range(1,len(l))),
        "lower_lows":sum(l[k]<l[k-1] for k in range(1,len(l))),
        "higher_highs":sum(h[k]>h[k-1] for k in range(1,len(h))),
        "lower_highs":sum(h[k]<h[k-1] for k in range(1,len(h))),
        "close_breaks_prior_high":int(c[-1]>max(h[:-1])),
        "close_breaks_prior_low":int(c[-1]<min(l[:-1])),
    }

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    idx={t:i for i,t in enumerate(times)}
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    expected,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    baseline,_,_,_,_,_=exp93.simulate(rows,st,rsi,market,"BASELINE")
    alternative,_,_,_,events,_=exp93.simulate(rows,st,rsi,market,"SIDEWAYS_EXIT")
    if expected!=baseline:
        raise AssertionError(symbol+": baseline mismatch")
    by_base={t["entry_time"]:t for t in baseline}
    by_alt={t["entry_time"]:t for t in alternative}
    if set(by_base)!=set(by_alt):
        raise AssertionError(symbol+": entry mismatch")
    session_start=[]
    start=0
    for i,t in enumerate(times):
        if i and t[:10]!=times[i-1][:10]:
            start=i
        session_start.append(start)
    geometry_by_bar=[]
    window_rows=[]
    for i,t in enumerate(times):
        measurements={w:geometry(rows,i,w,session_start[i]) for w in LOOKBACKS}
        geometry_by_bar.append(measurements)
        if measurements[12] is None:
            continue
        row={"symbol":symbol,"timestamp":t,"st_trend":st[i],
             "rsi":round(float(rsi[i]),6) if rsi[i] is not None else None,
             "exp93_sideways":int(exp93.is_sideways(exp93.metrics(rows,i)))}
        for w in LOOKBACKS:
            m=measurements[w]
            for key in ("net_move_pct","range_pct","efficiency",
                        "close_position_in_range","higher_lows","lower_lows",
                        "higher_highs","lower_highs","close_breaks_prior_high",
                        "close_breaks_prior_low"):
                row[f"w{w}_{key}"]=m[key] if m else None
        window_rows.append(row)
    save(OUT/f"{symbol.lower()}_all_session_windows.csv",window_rows)
    # Full observed baseline-trade trajectory, one row per completed bar.
    trajectory=[]
    for trade_number,t in enumerate(baseline,1):
        entry_i=idx[t["entry_time"]]
        exit_i=idx[t["exit_time"]]
        if exit_i<entry_i:
            raise AssertionError("Exit before entry")
        best=float(t["entry_price"])
        for i in range(entry_i,exit_i+1):
            best=min(best,closes[i])
            m=geometry_by_bar[i]
            row={"symbol":symbol,"trade_number":trade_number,
                 "entry_time":t["entry_time"],"timestamp":times[i],
                 "bar_since_entry":i-entry_i,
                 "close":closes[i],
                 "short_close_return_gross_pct":pct(float(t["entry_price"]),closes[i]),
                 "best_favorable_close_since_entry":round(best,6),
                 "rebound_from_best_close_pct":pct(closes[i],best),
                 "st_trend":st[i],
                 "rsi":round(float(rsi[i]),6) if rsi[i] is not None else None,
                 "sideways_at_close":int(exp93.is_sideways(exp93.metrics(rows,i))),
                 "eventual_baseline_exit_time_hindsight":t["exit_time"],
                 "eventual_baseline_net_pct_hindsight":t["net_pnl_pct"]}
            for w in LOOKBACKS:
                g=m[w]
                row[f"w{w}_net_move_pct"]=g["net_move_pct"] if g else None
                row[f"w{w}_higher_lows"]=g["higher_lows"] if g else None
                row[f"w{w}_lower_lows"]=g["lower_lows"] if g else None
                row[f"w{w}_close_position_in_range"]=g["close_position_in_range"] if g else None
            trajectory.append(row)
    save(OUT/f"{symbol.lower()}_baseline_mountain_trajectories.csv",trajectory)
    # Paired warnings; pre-signal features causal, later movement hindsight.
    warning_rows=[]
    for event in events:
        entry=event["entry_time"]
        a=by_base[entry]
        b=by_alt[entry]
        if b["exit_reason"]!="SIDEWAYS_EXIT":
            raise AssertionError("Unmatched warning")
        signal_i=idx[event["signal_time"]]
        exit_i=idx[b["exit_time"]]
        base_exit_i=idx[a["exit_time"]]
        if exit_i>base_exit_i:
            raise AssertionError("Exit order unexpected")
        entry_i=idx[entry]
        low_so_far=min([float(b["entry_price"])]+closes[entry_i:signal_i+1])
        after=rows[exit_i:base_exit_i+1]
        after_low=min(float(r["low"]) for r in after)
        after_high=max(float(r["high"]) for r in after)
        delta=round(b["net_pnl_pct"]-a["net_pnl_pct"],6)
        row={"symbol":symbol,"entry_time":entry,
             "signal_time":event["signal_time"],
             "early_exit_time":b["exit_time"],
             "baseline_exit_time_hindsight":a["exit_time"],
             "baseline_exit_reason_hindsight":a["exit_reason"],
             "label_hindsight":"EXIT_HELPED" if delta>0 else "EXIT_HURT" if delta<0 else "UNCHANGED",
             "paired_net_delta_pp_hindsight":delta,
             "entry_to_warning_gross_short_pct":pct(float(b["entry_price"]),closes[signal_i]),
             "best_short_close_pct_at_warning":pct(float(b["entry_price"]),low_so_far),
             "rebound_from_best_close_at_warning_pct":pct(closes[signal_i],low_so_far),
             "remaining_decline_extreme_pct_hindsight":pct(float(b["exit_price"]),after_low),
             "remaining_rebound_extreme_pct_hindsight":pct(after_high,float(b["exit_price"])),
             "sideways_efficiency_at_warning":event["efficiency"],
             "sideways_displacement_at_warning":event["displacement_fraction"]}
        for w in LOOKBACKS:
            g=geometry_by_bar[signal_i][w]
            for key in ("net_move_pct","range_pct","efficiency",
                        "close_position_in_range","higher_lows","lower_lows",
                        "higher_highs","lower_highs","close_breaks_prior_high",
                        "close_breaks_prior_low"):
                row[f"w{w}_{key}"]=g[key] if g else None
        warning_rows.append(row)
    warning_rows.sort(key=lambda x:x["signal_time"])
    save(OUT/f"{symbol.lower()}_warnings_full_mountain.csv",warning_rows)
    return {
        "candles":len(rows),"valid_12bar_windows":len(window_rows),
        "baseline_trades":len(baseline),"baseline_trajectory_bars":len(trajectory),
        "sideways_exit_warnings":len(warning_rows),
        "exit_helped":sum(x["label_hindsight"]=="EXIT_HELPED" for x in warning_rows),
        "exit_hurt":sum(x["label_hindsight"]=="EXIT_HURT" for x in warning_rows),
        "paired_delta_pp":round(sum(x["paired_net_delta_pp_hindsight"] for x in warning_rows),6),
        "baseline_net_pct_sum":round(sum(t["net_pnl_pct"] for t in baseline),6),
        "sideways_net_pct_sum":round(sum(t["net_pnl_pct"] for t in alternative),6),
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={
        "experiment":"EXP96","research_only":True,
        "description":"All same-session 12-bar windows, full baseline trade trajectories, and 10 paired sideways-warning mountain snapshots.",
        "causality":"All w5/w12/w24/w36 geometry and entry-to-warning features use completed bars at or before each timestamp. Future outcome columns explicitly marked hindsight.",
        "limits":[
            "Descriptive audit, not a new or validated exit strategy.",
            "Session-local windows only; no cross-session lookahead.",
            "The original V16 SHORT entry universe is small and selected; not a representative sample of all market transitions.",
            "Intrabar future extremes are diagnostic only and not guaranteed fills.",
            "No slippage, portfolio compounding, LONG trades or symbol switching.",
            "ST is the unchanged research baseline; no production changes."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        result["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("EXP96 — FULL MOUNTAIN / PAUSE / RESUMPTION — RESEARCH ONLY")
    for symbol,s in result["symbols"].items():
        print(symbol,"candles:",s["candles"],"12bar windows:",s["valid_12bar_windows"],
              "baseline trades:",s["baseline_trades"],
              "trajectory bars:",s["baseline_trajectory_bars"],
              "sideways warnings:",s["sideways_exit_warnings"],
              "helped:",s["exit_helped"],"hurt:",s["exit_hurt"],
              "paired delta pp:",s["paired_delta_pp"])
    print("Detailed files:",OUT)
    print("No trading logic changed.")

if __name__=="__main__":
    main()
