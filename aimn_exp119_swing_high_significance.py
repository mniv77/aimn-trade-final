#!/usr/bin/env python3
"""EXP119 — causal swing-high significance audit of EXP117 changed exits.

Research only. No new rule, threshold optimization, or production changes.
All structural measurements at the signal use only confirmed same-session
pivots and completed candles. Future baseline results are hindsight labels.
"""
import csv,json
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp117_full_swing_replay as exp117

OUT=Path(__file__).resolve().parent/"kiss/results/exp119_swing_high_significance"

def write(path,items):
    if not items:return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(items[0]))
        w.writeheader();w.writerows(items)

def rnd(x):
    return round(x,6) if x is not None else None

def pct(a,b):
    return rnd(100*(a/b-1)) if b is not None and b!=0 else None

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    idx={t:i for i,t in enumerate(times)}
    if len(idx)!=len(times):raise AssertionError("Duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    starts=swing.get_session_starts(times)
    ph,pl,counts=swing.confirmed_pivots(rows,times,starts)
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    reference,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    original,_,_,_=exp117.simulate(rows,st,rsi,market,None,"BASELINE")
    if original!=reference:raise AssertionError(symbol+" baseline parity failure")
    states=[swing.structure(rows,times,starts,i,ph,pl,counts)
            for i in range(len(rows))]
    candidate,events,_,_=exp117.simulate(rows,st,rsi,market,states,"JOINT_SWING")
    a={t["entry_time"]:t for t in original}
    b={t["entry_time"]:t for t in candidate}
    if set(a)!=set(b):raise AssertionError(symbol+" changed entry set")
    by_event={e["entry_time"]:e for e in events}
    records=[]
    for entry in sorted(a):
        x=a[entry];y=b[entry]
        if (x["exit_time"],x["exit_price"],x["exit_reason"])==(
            y["exit_time"],y["exit_price"],y["exit_reason"]):continue
        event=by_event.get(entry)
        if event is None:raise AssertionError("Missing signal event "+entry)
        si=idx[event["signal_time"]];ei=idx[entry]
        s=states[si]
        hc,lc=counts[si]
        day=times[si][:10]
        known_h=[p for p in ph[:hc] if p["pivot_time"][:10]==day]
        known_l=[p for p in pl[:lc] if p["pivot_time"][:10]==day]
        if len(known_h)<1 or len(known_l)<2:
            raise AssertionError("Joint signal lacks expected pivots")
        h=known_h[-1];hprev=known_h[-2] if len(known_h)>1 else None
        lo=known_l[-1];loprev=known_l[-2]
        if s["low_sequence"]!="HIGHER_LOW" or s["close_above_last_confirmed_high"]!=1:
            raise AssertionError("Signal no longer satisfies joint condition")
        # Latest confirmed high can be an old local peak. Identify
        # preceding confirmed lows only, never future lows.
        lows_before_high=[p for p in known_l if p["confirmed_index"]<=h["confirmed_index"]]
        preceding_low=lows_before_high[-1] if lows_before_high else None
        confirmed_high_to_low=(pct(h["price"],lo["price"])
                               if lo["pivot_index"]>h["pivot_index"] else None)
        prior_window={}
        for w in (6,12,24,36):
            if si-w+1<starts[si]:
                prior_window[f"w{w}_close_move_pct"]=None
                prior_window[f"w{w}_close_position"]=None
                continue
            part=rows[si-w+1:si+1]
            hh=max(float(r["high"]) for r in part)
            ll=min(float(r["low"]) for r in part)
            prior_window[f"w{w}_close_move_pct"]=pct(closes[si],float(part[0]["close"]))
            prior_window[f"w{w}_close_position"]=rnd(
                (closes[si]-ll)/(hh-ll)) if hh>ll else 0.5
        delta=rnd(y["net_pnl_pct"]-x["net_pnl_pct"])
        records.append({
            "symbol":symbol,"entry_time":entry,
            "signal_time":times[si],
            "candidate_exit_time":y["exit_time"],
            "baseline_exit_time_hindsight":x["exit_time"],
            "baseline_net_pct_hindsight":x["net_pnl_pct"],
            "candidate_net_pct":y["net_pnl_pct"],
            "delta_pp_hindsight":delta,
            "effect_hindsight":"HELPED" if delta>0 else "HURT" if delta<0 else "UNCHANGED",
            "bars_entry_to_signal":si-ei,
            "signal_close":closes[si],
            "signal_short_gross_pct":pct(float(x["entry_price"]),closes[si]),
            "broken_high_pivot_time":h["pivot_time"],
            "broken_high_confirmation_time":h["confirmed_time"],
            "broken_high_price":h["price"],
            "broken_high_age_from_pivot_bars":si-h["pivot_index"],
            "broken_high_age_from_confirmation_bars":si-h["confirmed_index"],
            "break_above_high_pct":pct(closes[si],h["price"]),
            "prior_confirmed_high_price":hprev["price"] if hprev else None,
            "prior_confirmed_high_time":hprev["pivot_time"] if hprev else None,
            "latest_high_vs_prior_high_pct":
                pct(h["price"],hprev["price"]) if hprev else None,
            "latest_confirmed_low_price":lo["price"],
            "latest_confirmed_low_pivot_time":lo["pivot_time"],
            "latest_confirmed_low_confirmation_time":lo["confirmed_time"],
            "latest_low_age_from_confirmation_bars":si-lo["confirmed_index"],
            "prior_confirmed_low_price":loprev["price"],
            "higher_low_pct":pct(lo["price"],loprev["price"]),
            "latest_high_to_latest_low_decline_pct":
                pct(lo["price"],h["price"]) if lo["pivot_index"]>h["pivot_index"] else None,
            "latest_high_to_latest_low_order_valid":
                lo["pivot_index"]>h["pivot_index"],
            "latest_high_to_low_rebound_pct":
                pct(closes[si],lo["price"]) if lo["pivot_index"]>h["pivot_index"] else None,
            "prior_confirmed_low_before_high_price":
                preceding_low["price"] if preceding_low else None,
            "prior_confirmed_low_before_high_time":
                preceding_low["pivot_time"] if preceding_low else None,
            "signal_rsi":rnd(float(rsi[si])) if rsi[si] is not None else None,
            "signal_st":st[si],
            **prior_window,
        })
    write(OUT/(symbol.lower()+"_changed_exit_structure.csv"),records)
    helped=[r for r in records if r["effect_hindsight"]=="HELPED"]
    hurt=[r for r in records if r["effect_hindsight"]=="HURT"]
    return {
        "changed":len(records),"helped":len(helped),"hurt":len(hurt),
        "net_delta_pp":rnd(sum(r["delta_pp_hindsight"] for r in records)),
        "records":records,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP119","research_only":True,
        "purpose":"Measure the structural significance of confirmed-high breaks in the seven changed EXP117 exits.",
        "definitions":{
            "pivot":"strict two-left two-right, known only at confirmation close",
            "breakout":"completed close percent above latest confirmed swing high",
            "high_age":"bars since high pivot and since confirmation",
            "higher_low":"latest confirmed low percent above preceding confirmed low",
            "high_to_low":"measured only if latest confirmed low pivot follows latest confirmed high pivot",
            "windows":"6,12,24,36 same-session completed candle measurements",
        },
        "limitations":[
            "Seven previously selected changed trades; exploratory, no independent holdout.",
            "Hindsight outcome labels must not enter trading decisions.",
            "Confirmed pivots and window features are causal; no future swing points used.",
            "A high-to-low decline is undefined when latest low predates latest high.",
            "No new entry or exit rule, no optimization, no portfolio/slippage model.",
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP119 — CONFIRMED HIGH SIGNIFICANCE — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n",symbol,"changed:",s["changed"],
              "helped:",s["helped"],"hurt:",s["hurt"],
              "total delta pp:",s["net_delta_pp"])
        for r in s["records"]:
            print(" ",r["entry_time"],r["effect_hindsight"],
                  "delta:",r["delta_pp_hindsight"],
                  "high age:",r["broken_high_age_from_confirmation_bars"],
                  "break %:",r["break_above_high_pct"],
                  "higher low %:",r["higher_low_pct"],
                  "high-to-low decline %:",r["latest_high_to_latest_low_decline_pct"],
                  "w12:",r["w12_close_move_pct"],
                  "w24:",r["w24_close_move_pct"])
    print("\nCSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
