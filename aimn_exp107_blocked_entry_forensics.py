#!/usr/bin/env python3
"""EXP107 — Eight sideways-blocked V16 SHORT trades: causal entry forensics.

Read-only research. Reproduce EXP106 baseline and entry-filter trades, verify
exactly which baseline entries were directly blocked, and print entry-time
features next to hindsight trade outcomes. Do NOT fit a new rule on eight
already-observed cases. No production changes.
"""
import csv
import json
from pathlib import Path
from collections import Counter
import aimn_exp83_v16_structural_exit as base
import aimn_exp93_sideways_research as exp93
import aimn_exp100_confirmed_swing_structure as exp100

OUT=Path(__file__).resolve().parent/"kiss/results/exp107_blocked_entry_forensics"
WINDOWS=(12,24,36)

def pct(a,b):
    return round(100*(a/b-1),6) if b else None

def save(path,items):
    if not items: return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(items[0]))
        w.writeheader();w.writerows(items)

def past_window(rows,starts,i,n):
    if i-n+1<starts[i]:
        return {"move_pct":None,"efficiency":None,"range_position":None,
                "max_high_pct_from_close":None,"min_low_pct_from_close":None}
    part=rows[i-n+1:i+1]
    c=[float(r["close"]) for r in part]
    h=max(float(r["high"]) for r in part)
    l=min(float(r["low"]) for r in part)
    net=abs(c[-1]-c[0])
    path=sum(abs(c[k]-c[k-1]) for k in range(1,len(c)))
    return {"move_pct":pct(c[-1],c[0]),
            "efficiency":round(net/path,6) if path else 0,
            "range_position":round((c[-1]-l)/(h-l),6) if h>l else 0.5,
            "max_high_pct_from_close":pct(h,c[-1]),
            "min_low_pct_from_close":pct(l,c[-1])}

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(times)!=len(set(times)): raise AssertionError("Duplicate timestamps")
    index={t:i for i,t in enumerate(times)}
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    original,_,_,original_audit,_,_=exp93.simulate(rows,st,rsi,market,"BASELINE")
    filtered,_,_,filtered_audit,_,_=exp93.simulate(rows,st,rsi,market,"ENTRY_FILTER")
    expected,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    if original!=expected: raise AssertionError(symbol+": EXP83 baseline drift")
    a={t["entry_time"]:t for t in original}
    b={t["entry_time"]:t for t in filtered}
    removed=sorted(set(a)-set(b))
    added=sorted(set(b)-set(a))
    accepted={r["signal_time"]:r for r in original_audit if r["decision"]=="ACCEPTED"}
    blocked={r["signal_time"]:r for r in filtered_audit if r["decision"]=="SIDEWAYS_FILTER"}
    starts=exp100.get_session_starts(times)
    highs,lows,counts=exp100.confirmed_pivots(rows,times,starts)
    records=[]
    for entry in removed:
        entry_i=index[entry]
        signal_i=entry_i-1
        if signal_i<0 or times[signal_i][:10]!=entry[:10]:
            raise AssertionError("Entry is not next same-session candle: "+entry)
        signal=times[signal_i]
        if signal not in accepted or signal not in blocked:
            raise AssertionError("Removed entry not directly blocked: "+entry)
        g=exp93.metrics(rows,signal_i)
        if not exp93.is_sideways(g):
            raise AssertionError("Blocked entry not sideways: "+entry)
        structure=exp100.structure(rows,times,starts,signal_i,highs,lows,counts)
        trade=a[entry]
        record={
            "symbol":symbol,"signal_time":signal,"entry_time":entry,
            "signal_close":closes[signal_i],
            "entry_open_hindsight":float(rows[entry_i]["open"]),
            "signal_st":st[signal_i],
            "signal_rsi":rsi[signal_i],
            "market_state_at_signal":str(market[signal_i]),
            "sideways_efficiency_12":round(g["efficiency"],6),
            "sideways_displacement_fraction_12":round(g["displacement_fraction"],6),
            "sideways_height_pct_12":round(g["height_pct"],6),
            "swing_state":structure["structure_state"],
            "high_sequence":structure["high_sequence"],
            "low_sequence":structure["low_sequence"],
            "confirmed_high_count":structure["confirmed_high_count"],
            "confirmed_low_count":structure["confirmed_low_count"],
            "close_below_last_confirmed_low":structure["close_below_last_confirmed_low"],
            "close_above_last_confirmed_high":structure["close_above_last_confirmed_high"],
        }
        for n in WINDOWS:
            for key,value in past_window(rows,starts,signal_i,n).items():
                record[f"past_{n}_{key}"]=value
        record.update({
            "baseline_exit_time_hindsight":trade["exit_time"],
            "baseline_exit_reason_hindsight":trade["exit_reason"],
            "baseline_net_pct_hindsight":round(trade["net_pnl_pct"],6),
            "baseline_gross_pct_hindsight":round(trade["gross_pnl_pct"],6),
            "baseline_bars_held_hindsight":trade["bars_held"],
            "baseline_best_close_short_pct_hindsight":trade["best_close_short_pct"],
            "outcome_hindsight":"MISSED_WINNER" if trade["net_pnl_pct"]>0 else "AVOIDED_LOSER"
        })
        records.append(record)
    save(OUT/(symbol.lower()+"_blocked_trade_entry_features.csv"),records)
    write_summary={
        "baseline_trades":len(original),"filtered_trades":len(filtered),
        "directly_blocked_trades":len(records),"replacement_entries":len(added),
        "missed_winners":sum(r["outcome_hindsight"]=="MISSED_WINNER" for r in records),
        "avoided_losers":sum(r["outcome_hindsight"]=="AVOIDED_LOSER" for r in records),
        "net_effect_pp":round(sum(t["net_pnl_pct"] for t in filtered)-
                              sum(t["net_pnl_pct"] for t in original),6),
        "cases":records
    }
    return write_summary

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"experiment":"EXP107","research_only":True,
            "purpose":"Compare signal-time causal features of EXP106 blocked winners and losers.",
            "feature_timing":"All features use completed candles at or before signal_time. Entry fill and trade outcome are hindsight.",
            "limitations":[
                "Only eight blocked trades in two symbols, June-August 2026.",
                "No parameter tuning, new filter, holdout validation or trading changes.",
                "Causal feature availability does not establish predictive value.",
                "Past 36-bar windows may be unavailable near session open.",
                "Original trade outcomes use historical fills without slippage.",
                "V16 strategy is SHORT-only; percentages are per-trade, not portfolio."
            ],"symbols":{}}
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
    print("EXP107 — BLOCKED SIDEWAYS ENTRY FORENSICS — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"baseline:",s["baseline_trades"],
              "filtered:",s["filtered_trades"],
              "blocked:",s["directly_blocked_trades"],
              "missed winners:",s["missed_winners"],
              "avoided losers:",s["avoided_losers"],
              "net delta pp:",s["net_effect_pp"])
        for r in s["cases"]:
            print(" ",r["signal_time"],r["outcome_hindsight"],
                  "net:",r["baseline_net_pct_hindsight"],
                  "past12:",r["past_12_move_pct"],
                  "past24:",r["past_24_move_pct"],
                  "past36:",r["past_36_move_pct"],
                  "structure:",r["swing_state"],
                  "highs:",r["high_sequence"],
                  "lows:",r["low_sequence"],
                  "below_confirmed_low:",r["close_below_last_confirmed_low"])
    print("\nDetailed CSVs and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
