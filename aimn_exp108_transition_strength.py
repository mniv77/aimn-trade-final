#!/usr/bin/env python3
"""EXP108 — causal transition-strength audit across ALL V16 entry candidates.

Research only; no new rule or fitted threshold. Features use only completed
same-session bars through the signal candle. Outcomes are labeled hindsight.
Replays EXP93 baseline and entry-filter to verify candidate invariance.
"""
import csv
import json
from pathlib import Path
from collections import Counter,defaultdict
import aimn_exp83_v16_structural_exit as base
import aimn_exp93_sideways_research as exp93
import aimn_exp100_confirmed_swing_structure as exp100

OUT=Path(__file__).resolve().parent/"kiss/results/exp108_transition_strength"
WINDOWS=(3,6,12,24,36)

def write(path,records):
    if not records: return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader();w.writerows(records)

def features(rows,start,i,w):
    if i-w+1<start: return (None,None,None,None)
    part=rows[i-w+1:i+1]
    closes=[float(r["close"]) for r in part]
    hh=max(float(r["high"]) for r in part)
    ll=min(float(r["low"]) for r in part)
    net=closes[-1]-closes[0]
    path=sum(abs(closes[k]-closes[k-1]) for k in range(1,len(closes)))
    return (round(100*(closes[-1]/closes[0]-1),6) if closes[0] else None,
            round(abs(net)/path,6) if path else 0,
            round((closes[-1]-ll)/(hh-ll),6) if hh>ll else 0.5,
            round(sum(closes[k]<closes[k-1] for k in range(1,len(closes)))/(w-1),6))

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(set(times))!=len(times): raise AssertionError("Duplicate timestamps")
    index={t:i for i,t in enumerate(times)}
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    baseline,bc,_,baseaudit,_,_=exp93.simulate(rows,st,rsi,market,"BASELINE")
    filtered,fc,_,filteraudit,_,_=exp93.simulate(rows,st,rsi,market,"ENTRY_FILTER")
    expected,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    if baseline!=expected or bc!=fc: raise AssertionError(symbol+": baseline or candidate drift")
    if len(baseaudit)!=bc or len(filteraudit)!=fc: raise AssertionError("Candidate audit incomplete")
    accepted={r["signal_time"]:r for r in baseaudit if r["decision"]=="ACCEPTED"}
    filtered_by_time={r["signal_time"]:r for r in filteraudit}
    if set(filtered_by_time)!={r["signal_time"] for r in baseaudit}:
        raise AssertionError("Candidate timestamps drift")
    baseline_by_entry={t["entry_time"]:t for t in baseline}
    filtered_by_entry={t["entry_time"]:t for t in filtered}
    starts=exp100.get_session_starts(times)
    highs,lows,counts=exp100.confirmed_pivots(rows,times,starts)
    records=[]
    for event in baseaudit:
        signal=event["signal_time"]
        i=index[signal]
        next_entry=times[i+1] if i+1<len(rows) and times[i+1][:10]==signal[:10] else None
        original_trade=baseline_by_entry.get(next_entry)
        filtered_trade=filtered_by_entry.get(next_entry)
        state=exp100.structure(rows,times,starts,i,highs,lows,counts)
        m=exp93.metrics(rows,i)
        rec={
            "symbol":symbol,"signal_time":signal,
            "baseline_decision":event["decision"],
            "filtered_decision":filtered_by_time[signal]["decision"],
            "sideways_at_signal":exp93.is_sideways(m),
            "signal_close":closes[i],
            "st_at_signal":st[i],
            "rsi_at_signal":rsi[i],
            "market_state_at_signal":str(market[i]),
            "sideways_efficiency_12":round(m["efficiency"],6) if m else None,
            "sideways_displacement_12":round(m["displacement_fraction"],6) if m else None,
            "swing_state":state["structure_state"],
            "high_sequence":state["high_sequence"],
            "low_sequence":state["low_sequence"],
            "close_below_confirmed_low":state["close_below_last_confirmed_low"],
            "close_above_confirmed_high":state["close_above_last_confirmed_high"],
        }
        for w in WINDOWS:
            move,eff,pos,down=features(rows,starts[i],i,w)
            rec[f"move_{w}_pct"]=move
            rec[f"efficiency_{w}"]=eff
            rec[f"close_range_position_{w}"]=pos
            rec[f"down_close_fraction_{w}"]=down
        rec.update({
            "baseline_entry_time_hindsight":original_trade["entry_time"] if original_trade else None,
            "baseline_net_pct_hindsight":original_trade["net_pnl_pct"] if original_trade else None,
            "baseline_outcome_hindsight":(
                "WIN" if original_trade["net_pnl_pct"]>0 else "LOSS"
            ) if original_trade else "NO_BASELINE_TRADE",
            "filtered_entry_time_hindsight":filtered_trade["entry_time"] if filtered_trade else None,
            "filtered_net_pct_hindsight":filtered_trade["net_pnl_pct"] if filtered_trade else None,
        })
        if event["decision"]=="ACCEPTED" and not original_trade:
            raise AssertionError("Accepted signal missing baseline trade: "+signal)
        records.append(rec)
    write(OUT/(symbol.lower()+"_all_v16_candidates.csv"),records)
    accepted_records=[r for r in records if r["baseline_decision"]=="ACCEPTED"]
    blocked=[r for r in accepted_records if r["filtered_decision"]=="SIDEWAYS_FILTER"]
    if len(blocked)!=len(set(baseline_by_entry)-set(filtered_by_entry)):
        raise AssertionError(symbol+": blocked entry count mismatch")
    if set(filtered_by_entry)-set(baseline_by_entry):
        raise AssertionError(symbol+": unexpected replacement entries")
    write(OUT/(symbol.lower()+"_accepted_entry_features.csv"),accepted_records)
    write(OUT/(symbol.lower()+"_sideways_blocked_features.csv"),blocked)
    groups=[]
    for label,subset in (
        ("ALL_CANDIDATES",records),
        ("BASELINE_ACCEPTED",accepted_records),
        ("BASELINE_ACCEPTED_SIDEWAYS", [r for r in accepted_records if r["sideways_at_signal"]]),
        ("BASELINE_ACCEPTED_NOT_SIDEWAYS",[r for r in accepted_records if not r["sideways_at_signal"]]),
        ("SIDEWAYS_BLOCKED",blocked),
    ):
        labeled=[r for r in subset if r["baseline_outcome_hindsight"] in ("WIN","LOSS")]
        g={"group":label,"candidates":len(subset),"trades_with_known_outcomes":len(labeled),
           "wins":sum(r["baseline_outcome_hindsight"]=="WIN" for r in labeled),
           "losses":sum(r["baseline_outcome_hindsight"]=="LOSS" for r in labeled),
           "baseline_net_sum_pct":round(sum(r["baseline_net_pct_hindsight"] for r in labeled),6)}
        for w in (3,6,12):
            values=[r[f"move_{w}_pct"] for r in labeled if r[f"move_{w}_pct"] is not None]
            g[f"mean_move_{w}_pct"]=round(sum(values)/len(values),6) if values else None
            g[f"valid_move_{w}"]=len(values)
        groups.append(g)
    write(OUT/(symbol.lower()+"_descriptive_groups.csv"),groups)
    return {"candles":len(rows),"all_candidates":len(records),
            "accepted_entries":len(accepted_records),"sideways_blocked":len(blocked),
            "baseline_net_pct":round(sum(t["net_pnl_pct"] for t in baseline),6),
            "filtered_net_pct":round(sum(t["net_pnl_pct"] for t in filtered),6),
            "groups":groups,
            "blocked_cases":[{"time":r["signal_time"],"outcome":r["baseline_outcome_hindsight"],
                              "net":r["baseline_net_pct_hindsight"],
                              "move3":r["move_3_pct"],"move6":r["move_6_pct"],
                              "move12":r["move_12_pct"],
                              "range_position12":r["close_range_position_12"],
                              "swing":r["swing_state"]} for r in blocked]}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"experiment":"EXP108","research_only":True,
            "hypothesis":"Transition strength (3/6/12-bar direction and range location) may distinguish sideways breakout from noise.",
            "method":"Describe ALL V16 candidate signals, then accepted entries and eight blocked trades. No threshold selection or strategy modification.",
            "feature_timing":"Every feature calculated from completed candles at or before signal close; same-session windows only.",
            "limitations":[
                "Candidates rejected for ST/position/session constraints do not have realized trade outcomes.",
                "Accepted-trade outcomes are conditional on V16 selection and historical execution.",
                "Only NVDA/AAPL June-August 2026; no independent validation.",
                "Some 24/36-bar features unavailable early in sessions.",
                "No new strategy, parameter fitting, slippage or portfolio return."
            ],"symbols":{}}
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
    print("EXP108 — TRANSITION STRENGTH ACROSS ALL V16 CANDIDATES — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"candles:",s["candles"],"all candidates:",s["all_candidates"],
              "accepted:",s["accepted_entries"],"blocked:",s["sideways_blocked"])
        print(" baseline net:",s["baseline_net_pct"],"filtered net:",s["filtered_net_pct"])
        for g in s["groups"]:
            print(" GROUP",g)
        for c in s["blocked_cases"]:
            print(" BLOCKED",c)
    print("\nCSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
