#!/usr/bin/env python3
"""EXP104 — Causal trajectory phase state and pre-registered descriptive audit.

Research-only. Two separations:
(1) At each completed five-minute candle, what phase is already confirmed?
(2) What occurs *later*? Outcomes never become inputs to phase decisions.

Consumes EXP101 candle-level data and EXP103 episode files. Verifies that
their episode counts and phase definitions agree. Captures phase transition
paths, rebound durations, and price moves without devising an exit rule.
No optimization, holdout claims, or production updates.
"""
import csv
import json
from pathlib import Path
from collections import defaultdict,Counter
import aimn_exp83_v16_structural_exit as base
import aimn_exp101_trajectory_rebound as exp101
import aimn_exp103_trajectory_phases as exp103

OUT=Path(__file__).resolve().parent/"kiss/results/exp104_phase_transition_integrity"
HORIZONS=(3,6,12)

def read_csv(p):
    with p.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write_csv(p,rows):
    if not rows: return
    with p.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)

def mean(xs):
    return round(sum(xs)/len(xs),6) if xs else None

def val(x):
    return float(x) if x not in (None,"") else None

def audit(symbol,path):
    source=exp101.OUT/(symbol.lower()+"_all_trajectory_observations.csv")
    ep_path=exp103.OUT/(symbol.lower()+"_rebound_episodes.csv")
    if not path.exists() or not source.exists() or not ep_path.exists():
        raise FileNotFoundError("Requires candle data, completed EXP101 and EXP103: "+symbol)
    rows=read_csv(source)
    episodes=read_csv(ep_path)
    if any(r["symbol"]!=symbol for r in rows+episodes):
        raise AssertionError("Symbol mismatch: "+symbol)
    for r in rows: r["phase"]=exp103.phase(r)
    byday=defaultdict(list)
    for r in rows: byday[r["session"]].append(r)
    rebuilt=[]
    # Evaluate every rebound event without using a retrospective label in the features.
    for day,dayrows in sorted(byday.items()):
        i=0
        while i<len(dayrows):
            r=dayrows[i]
            if r["phase"]!="REBOUND":
                i+=1
                continue
            j=i
            while j+1<len(dayrows) and dayrows[j+1]["phase"]=="REBOUND": j+=1
            successor=dayrows[j+1] if j+1<len(dayrows) else None
            end_class=exp103.classify_end(successor["phase"] if successor else None)
            future={f"f{h}_move_at_start_hindsight":val(r.get(f"f{h}_close_move_pct"))
                    for h in HORIZONS}
            record={
                "symbol":symbol,"session":day,"start_time":r["timestamp"],
                "start_structure":r["structure_state"],
                "start_w6_move_pct":val(r["w6_move_pct"]),
                "start_w36_move_pct":val(r["w36_move_pct"]),
                "start_w24_move_pct":val(r["w24_move_pct"]),
                "start_w6_efficiency":val(r["w6_efficiency"]),
                "start_w36_efficiency":val(r["w36_efficiency"]),
                "last_rebound_time_hindsight":dayrows[j]["timestamp"],
                "duration_bars_hindsight":j-i+1,
                "next_phase_time_hindsight":successor["timestamp"] if successor else "",
                "end_class_hindsight":end_class,
                **future
            }
            rebuilt.append(record)
            i=j+1
    if len(rebuilt)!=len(episodes):
        raise AssertionError(f"{symbol}: episode counts differ {len(rebuilt)} != {len(episodes)}")
    prior_by_start={e["start_time"]:e for e in episodes}
    if len(prior_by_start)!=len(episodes):
        raise AssertionError("Duplicate EXP103 episode start")
    for ep in rebuilt:
        prior=prior_by_start.get(ep["start_time"])
        if not prior:
            raise AssertionError("Missing EXP103 episode "+ep["start_time"])
        if (prior["end_class_hindsight"]!=ep["end_class_hindsight"] or
            int(prior["episode_bars_hindsight"])!=ep["duration_bars_hindsight"] or
            prior["last_rebound_time"]!=ep["last_rebound_time_hindsight"]):
            raise AssertionError("EXP103 episode mismatch "+ep["start_time"])
    write_csv(OUT/(symbol.lower()+"_verified_episode_transitions.csv"),rebuilt)
    by_structure=defaultdict(list)
    by_month=defaultdict(list)
    session_rebound_counts=Counter()
    for r in rebuilt:
        by_structure[r["start_structure"]].append(r)
        by_month[(r["session"][:7],r["start_structure"])].append(r)
        session_rebound_counts[r["session"]]+=1
    groups=[]
    for structure,eps in sorted(by_structure.items()):
        for h in HORIZONS:
            xs=[e[f"f{h}_move_at_start_hindsight"] for e in eps
                if e[f"f{h}_move_at_start_hindsight"] is not None]
            groups.append({
                "symbol":symbol,"start_structure":structure,"horizon_bars":h,
                "episodes":len(eps),"sessions":len(set(e["session"] for e in eps)),
                "outcome_available_n":len(xs),
                "future_up_rate_hindsight":round(sum(x>0 for x in xs)/len(xs),6) if xs else None,
                "future_move_mean_pct_hindsight":mean(xs),
                "future_move_median_pct_hindsight":sorted(xs)[len(xs)//2] if xs else None,
                "resumed_down_hindsight":sum(e["end_class_hindsight"]=="RESUMED_DOWN_CONTEXT" for e in eps),
                "turned_up_hindsight":sum(e["end_class_hindsight"]=="TURNED_UP_CONTEXT" for e in eps),
                "session_censored_hindsight":sum(e["end_class_hindsight"]=="SESSION_CENSORED" for e in eps)
            })
    monthly=[]
    for (month,structure),eps in sorted(by_month.items()):
        monthly.append({
            "symbol":symbol,"month":month,"start_structure":structure,
            "episodes":len(eps),
            "resumed_down_hindsight":sum(e["end_class_hindsight"]=="RESUMED_DOWN_CONTEXT" for e in eps),
            "turned_up_hindsight":sum(e["end_class_hindsight"]=="TURNED_UP_CONTEXT" for e in eps),
            "session_censored_hindsight":sum(e["end_class_hindsight"]=="SESSION_CENSORED" for e in eps),
            "mean_duration_bars_hindsight":mean([e["duration_bars_hindsight"] for e in eps]),
            "mean_f12_hindsight":mean([e["f12_move_at_start_hindsight"] for e in eps
                if e["f12_move_at_start_hindsight"] is not None])})
    write_csv(OUT/(symbol.lower()+"_phase_outcome_summary.csv"),groups)
    write_csv(OUT/(symbol.lower()+"_month_phase_summary.csv"),monthly)
    return {
        "source_candles":len(rows),
        "verified_episodes":len(rebuilt),
        "sessions_with_episodes":len(session_rebound_counts),
        "max_episodes_one_session":max(session_rebound_counts.values()) if session_rebound_counts else 0,
        "end_classes":dict(Counter(e["end_class_hindsight"] for e in rebuilt)),
        "group_summary":groups,
        "monthly":monthly
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP104","research_only":True,
        "purpose":"Verify EXP103 episode reconstruction independently and stratify event-start future paths.",
        "limitations":[
            "Future outcomes and duration are hindsight and cannot be used to make decisions at episode start.",
            "Context is a finite-window net move, not a validated major trend.",
            "Repeated rebound episodes within a session can be strongly correlated.",
            "This is in-sample June-August 2026, no untouched validation.",
            "No strategy backtest, stops, fees, LONG testing, or live changes."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=audit(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP104 — TRAJECTORY PHASE INTEGRITY AND OUTCOME AUDIT — RESEARCH ONLY")
    for symbol,r in report["symbols"].items():
        print("\n"+symbol,"verified episodes:",r["verified_episodes"],
              "sessions:",r["sessions_with_episodes"],
              "max episodes/session:",r["max_episodes_one_session"],
              "end classes:",r["end_classes"])
        for g in r["group_summary"]:
            if g["horizon_bars"]==12:
                print(" ",g["start_structure"],"episodes:",g["episodes"],
                      "sessions:",g["sessions"],"h12 n:",g["outcome_available_n"],
                      "h12 up rate:",g["future_up_rate_hindsight"],
                      "h12 mean:",g["future_move_mean_pct_hindsight"])
        for m in r["monthly"]:
            print("  month",m["month"],m["start_structure"],
                  "n:",m["episodes"],
                  "resumed:",m["resumed_down_hindsight"],
                  "turned_up:",m["turned_up_hindsight"],
                  "duration:",m["mean_duration_bars_hindsight"])
    print("\nDetailed files:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
