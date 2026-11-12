#!/usr/bin/env python3
"""EXP100 — causal confirmed-swing structural audit (research only).

A pivot is known only after RIGHT subsequent completed candles; never
timestamp the confirmation as if it were known at the pivot candle.
Compute at every same-session candle, and annotate the five changed
EXP99 Mountain-24 exits using only confirmed pivots as of their signals.

This is descriptive feature research, not a fitted predictor or exit rule.
"""
import csv
import json
from pathlib import Path
from collections import Counter
import aimn_exp83_v16_structural_exit as base
import aimn_exp97_mountain_exit_test as exp97

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp100_confirmed_swing_structure"
LEFT=2
RIGHT=2
WINDOWS=(12,24,36)

def rounded(v):
    return round(v,6) if v is not None else None

def percent(a,b):
    return rounded(100*(a/b-1)) if b else None

def write_csv(path,rows):
    if not rows:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def get_session_starts(times):
    result=[]
    start=0
    for i,t in enumerate(times):
        if i and t[:10]!=times[i-1][:10]:
            start=i
        result.append(start)
    return result

def confirmed_pivots(rows,times,starts):
    """Return lists of pivots confirmed at each candle close.

    Strict local extrema avoid arbitrary tie-breaking. No future-session
    bars may confirm a pivot from an earlier session.
    """
    high=[float(r["high"]) for r in rows]
    low=[float(r["low"]) for r in rows]
    highs=[]
    lows=[]
    by_index=[]
    for i in range(len(rows)):
        pivot_i=i-RIGHT
        if pivot_i>=starts[i]+LEFT:
            region=range(pivot_i-LEFT,i+1)
            if all(high[pivot_i]>high[k] for k in region if k!=pivot_i):
                highs.append({"pivot_index":pivot_i,"pivot_time":times[pivot_i],
                              "confirmed_index":i,"confirmed_time":times[i],
                              "price":high[pivot_i]})
            if all(low[pivot_i]<low[k] for k in region if k!=pivot_i):
                lows.append({"pivot_index":pivot_i,"pivot_time":times[pivot_i],
                             "confirmed_index":i,"confirmed_time":times[i],
                             "price":low[pivot_i]})
        by_index.append((len(highs),len(lows)))
    return highs,lows,by_index

def structure(rows,times,starts,i,highs,lows,counts):
    """Causal state from same-session confirmed pivots and current close."""
    hcount,lcount=counts[i]
    # Current session only. Pivots from prior days must not leak in.
    day=times[i][:10]
    ph=[p for p in highs[:hcount] if p["pivot_time"][:10]==day]
    pl=[p for p in lows[:lcount] if p["pivot_time"][:10]==day]
    last_h=ph[-1] if ph else None
    prior_h=ph[-2] if len(ph)>1 else None
    last_l=pl[-1] if pl else None
    prior_l=pl[-2] if len(pl)>1 else None
    c=float(rows[i]["close"])
    out={
        "confirmed_high_count":len(ph),
        "confirmed_low_count":len(pl),
        "latest_high_pivot_time":last_h["pivot_time"] if last_h else None,
        "latest_high_confirmed_time":last_h["confirmed_time"] if last_h else None,
        "latest_high_price":rounded(last_h["price"]) if last_h else None,
        "latest_low_pivot_time":last_l["pivot_time"] if last_l else None,
        "latest_low_confirmed_time":last_l["confirmed_time"] if last_l else None,
        "latest_low_price":rounded(last_l["price"]) if last_l else None,
        "high_sequence":"LOWER_HIGH" if prior_h and last_h["price"]<prior_h["price"] else
                        "HIGHER_HIGH" if prior_h and last_h["price"]>prior_h["price"] else
                        "NO_COMPARISON",
        "low_sequence":"LOWER_LOW" if prior_l and last_l["price"]<prior_l["price"] else
                       "HIGHER_LOW" if prior_l and last_l["price"]>prior_l["price"] else
                       "NO_COMPARISON",
        "close_above_last_confirmed_high":int(c>last_h["price"]) if last_h else None,
        "close_below_last_confirmed_low":int(c<last_l["price"]) if last_l else None,
        "close_to_last_high_pct":percent(c,last_h["price"]) if last_h else None,
        "close_to_last_low_pct":percent(c,last_l["price"]) if last_l else None,
    }
    if out["high_sequence"]=="LOWER_HIGH" and out["low_sequence"]=="LOWER_LOW":
        out["structure_state"]="DESCENDING_SWINGS"
    elif out["high_sequence"]=="HIGHER_HIGH" and out["low_sequence"]=="HIGHER_LOW":
        out["structure_state"]="ASCENDING_SWINGS"
    else:
        out["structure_state"]="MIXED_OR_INSUFFICIENT"
    for w in WINDOWS:
        if i-w+1<starts[i]:
            out[f"w{w}_net_close_move_pct"]=None
            out[f"w{w}_close_position"]=None
            continue
        part=rows[i-w+1:i+1]
        hh=max(float(r["high"]) for r in part)
        ll=min(float(r["low"]) for r in part)
        first=float(part[0]["close"])
        out[f"w{w}_net_close_move_pct"]=percent(c,first)
        out[f"w{w}_close_position"]=rounded((c-ll)/(hh-ll)) if hh>ll else 0.5
    return out

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    index={t:i for i,t in enumerate(times)}
    starts=get_session_starts(times)
    highs,lows,counts=confirmed_pivots(rows,times,starts)
    states=[structure(rows,times,starts,i,highs,lows,counts)
            for i in range(len(rows))]
    # Keep the full same-session state history for later independent studies.
    all_rows=[{"symbol":symbol,"timestamp":times[i],**s}
              for i,s in enumerate(states)]
    write_csv(OUT/f"{symbol.lower()}_all_causal_swing_states.csv",all_rows)
    close=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(close)
    market=[base.get_market_state(close,i) for i in range(len(rows))]
    original,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    baseline,_,_=exp97.simulate(rows,st,rsi,market,"BASELINE")
    mountain,events,_=exp97.simulate(rows,st,rsi,market,"MOUNTAIN_24")
    if original!=baseline:
        raise AssertionError(symbol+": EXP83 baseline drift")
    a={t["entry_time"]:t for t in baseline}
    b={t["entry_time"]:t for t in mountain}
    if set(a)!=set(b):
        raise AssertionError(symbol+": entries changed")
    event_map={e["entry_time"]:e for e in events}
    changed=[]
    for entry in sorted(a):
        x,y=a[entry],b[entry]
        if (x["exit_time"],x["exit_price"],x["exit_reason"])==(
                y["exit_time"],y["exit_price"],y["exit_reason"]):
            continue
        if entry not in event_map:
            raise AssertionError("Changed exit without event: "+entry)
        e=event_map[entry]
        signal_i=index[e["signal_time"]]
        entry_i=index[entry]
        best_close=min([float(y["entry_price"])]+close[entry_i:signal_i+1])
        delta=rounded(y["net_pnl_pct"]-x["net_pnl_pct"])
        changed.append({
            "symbol":symbol,"entry_time":entry,
            "signal_time":e["signal_time"],
            "early_exit_time":y["exit_time"],
            "original_exit_time_hindsight":x["exit_time"],
            "net_delta_pp_hindsight":delta,
            "outcome_hindsight":"HELPED" if delta>0 else "HURT" if delta<0 else "UNCHANGED",
            "short_gross_at_signal_pct":percent(float(y["entry_price"]),close[signal_i]),
            "rebound_from_best_close_pct":percent(close[signal_i],best_close),
            **states[signal_i],
        })
    write_csv(OUT/f"{symbol.lower()}_changed_exit_swing_audit.csv",changed)
    return {
        "candles":len(rows),"confirmed_high_pivots":len(highs),
        "confirmed_low_pivots":len(lows),
        "state_counts":dict(Counter(s["structure_state"] for s in states)),
        "changed_exits":len(changed),
        "helped":sum(r["outcome_hindsight"]=="HELPED" for r in changed),
        "hurt":sum(r["outcome_hindsight"]=="HURT" for r in changed),
        "records":changed,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP100","research_only":True,
        "pivot_definition":{"left_bars":LEFT,"right_confirmation_bars":RIGHT,
                            "strict_extrema":True,"same_session_only":True},
        "purpose":"Test whether confirmed swing structure at Mountain 24 exits differs between helped and hurt outcomes.",
        "limitations":[
            "Only five changed trades: descriptive evidence, not a trained model.",
            "Pivot is usable only at confirmation close, two candles after its extremum.",
            "No new exit rule or strategy rerun; no parameter optimization.",
            "Historical outcomes and original exit times are hindsight only.",
            "Current-day-only pivots may be unavailable early in a session.",
            "No independent holdout, slippage, LONG or portfolio test."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP100 — CONFIRMED SWING STRUCTURE — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"candles:",s["candles"],
              "confirmed highs:",s["confirmed_high_pivots"],
              "confirmed lows:",s["confirmed_low_pivots"],
              "states:",s["state_counts"])
        for r in s["records"]:
            print(" ",r["signal_time"],r["outcome_hindsight"],
                  "delta:",r["net_delta_pp_hindsight"],
                  "structure:",r["structure_state"],
                  "highs:",r["high_sequence"],
                  "lows:",r["low_sequence"],
                  "above_confirmed_high:",r["close_above_last_confirmed_high"],
                  "below_confirmed_low:",r["close_below_last_confirmed_low"],
                  "w24_move:",r["w24_net_close_move_pct"])
    print("\nDetailed reports:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
