#!/usr/bin/env python3
"""EXP103 — Chronological downtrend/rebound phase trajectories.

Research only. Reconstruct completed-candle phase sequences from EXP101
causal features. Use future paths solely as descriptive outcomes.
This is not an exit model, fitted classifier, or holdout validation.

Phases:
DOWN: negative 36-bar net movement, 6-bar movement <= 0
REBOUND: negative 36-bar net movement, 6-bar movement > 0
UP_CONTEXT: positive 36-bar net movement
FLAT_CONTEXT: zero 36-bar movement

A REBOUND episode starts at the first qualifying candle after a
non-REBOUND candle. Its end is the first later non-REBOUND candle.
If the session ends first, the episode is right-censored.
Classifications are assigned at episode end (hindsight), not entry.
"""
import csv
import json
from collections import defaultdict,Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp101_trajectory_rebound as exp101

OUT=Path(__file__).resolve().parent/"kiss/results/exp103_trajectory_phases"
HORIZONS=(3,6,12)

def read_csv(path):
    with path.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write_csv(path,records):
    if not records:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

def number(x):
    return float(x) if x not in (None,"") else None

def avg(values):
    return round(sum(values)/len(values),6) if values else None

def phase(r):
    if r["context"]=="DOWNWARD_36":
        return "REBOUND" if r["rebound"]=="UP_6" else "DOWN"
    if r["context"]=="UPWARD_36":
        return "UP_CONTEXT"
    return "FLAT_CONTEXT"

def classify_end(next_phase):
    if next_phase is None:
        return "SESSION_CENSORED"
    if next_phase=="DOWN":
        return "RESUMED_DOWN_CONTEXT"
    if next_phase=="UP_CONTEXT":
        return "TURNED_UP_CONTEXT"
    if next_phase=="FLAT_CONTEXT":
        return "FLAT_CONTEXT"
    raise AssertionError(next_phase)

def analyze(symbol,path):
    input_path=exp101.OUT/(symbol.lower()+"_all_trajectory_observations.csv")
    if not path.exists():
        raise FileNotFoundError(str(path))
    if not input_path.exists():
        raise FileNotFoundError("Run EXP101 first: "+str(input_path))
    records=read_csv(input_path)
    if not records or any(r["symbol"]!=symbol for r in records):
        raise AssertionError("EXP101 records missing or wrong symbol: "+symbol)
    if any(records[i]["timestamp"]>=records[i+1]["timestamp"] for i in range(len(records)-1)):
        raise AssertionError("Input timestamps must be strictly increasing")
    for r in records:
        r["phase"]=phase(r)
    episodes=[]
    transitions=[]
    previous=None
    for i,r in enumerate(records):
        day=r["session"]
        prior=records[i-1] if i else None
        next_r=records[i+1] if i+1<len(records) and records[i+1]["session"]==day else None
        new_day=prior is None or prior["session"]!=day
        if new_day or prior["phase"]!=r["phase"]:
            transitions.append({"symbol":symbol,"timestamp":r["timestamp"],
                                "session":day,
                                "from_phase":prior["phase"] if not new_day else "SESSION_START",
                                "to_phase":r["phase"]})
        if r["phase"]!="REBOUND" or (not new_day and prior["phase"]=="REBOUND"):
            continue
        j=i
        while j+1<len(records) and records[j+1]["session"]==day and records[j+1]["phase"]=="REBOUND":
            j+=1
        successor=records[j+1] if j+1<len(records) and records[j+1]["session"]==day else None
        outcome=classify_end(successor["phase"] if successor else None)
        first=r
        end=records[j]
        episode={
            "symbol":symbol,"session":day,
            "start_time":first["timestamp"],"last_rebound_time":end["timestamp"],
            "first_non_rebound_time_hindsight":successor["timestamp"] if successor else None,
            "start_structure":first["structure_state"],
            "start_36_move_pct":number(first["w36_move_pct"]),
            "start_6_move_pct":number(first["w6_move_pct"]),
            "start_24_move_pct":number(first["w24_move_pct"]),
            "start_36_efficiency":number(first["w36_efficiency"]),
            "start_6_efficiency":number(first["w6_efficiency"]),
            "start_36_close_position":number(first["w36_close_position"]),
            "episode_bars_hindsight":j-i+1,
            "end_class_hindsight":outcome,
            "start_month":day[:7]
        }
        for h in HORIZONS:
            episode["start_future_%d_close_move_pct_hindsight"%h]=number(first.get("f%d_close_move_pct"%h))
        episodes.append(episode)
    write_csv(OUT/(symbol.lower()+"_phase_transitions.csv"),transitions)
    write_csv(OUT/(symbol.lower()+"_rebound_episodes.csv"),episodes)
    monthly=[]
    groups=[]
    for structure in ("ASCENDING_SWINGS","DESCENDING_SWINGS","MIXED_OR_INSUFFICIENT"):
        subset=[e for e in episodes if e["start_structure"]==structure]
        for month in sorted({e["start_month"] for e in subset}):
            ms=[e for e in subset if e["start_month"]==month]
            monthly.append({"symbol":symbol,"month":month,"start_structure":structure,
                "episodes":len(ms),
                "resumed_down":sum(e["end_class_hindsight"]=="RESUMED_DOWN_CONTEXT" for e in ms),
                "turned_up":sum(e["end_class_hindsight"]=="TURNED_UP_CONTEXT" for e in ms),
                "censored":sum(e["end_class_hindsight"]=="SESSION_CENSORED" for e in ms),
                "mean_future_12bar_pct":avg([e["start_future_12_close_move_pct_hindsight"]
                    for e in ms if e["start_future_12_close_move_pct_hindsight"] is not None])})
        groups.append({
            "symbol":symbol,"start_structure":structure,"episodes":len(subset),
            "resumed_down":sum(e["end_class_hindsight"]=="RESUMED_DOWN_CONTEXT" for e in subset),
            "turned_up":sum(e["end_class_hindsight"]=="TURNED_UP_CONTEXT" for e in subset),
            "flat":sum(e["end_class_hindsight"]=="FLAT_CONTEXT" for e in subset),
            "session_censored":sum(e["end_class_hindsight"]=="SESSION_CENSORED" for e in subset),
            "mean_episode_bars_hindsight":avg([e["episode_bars_hindsight"] for e in subset]),
            "mean_future_12bar_pct":avg([e["start_future_12_close_move_pct_hindsight"]
                for e in subset if e["start_future_12_close_move_pct_hindsight"] is not None])
        })
    write_csv(OUT/(symbol.lower()+"_episode_structure_summary.csv"),groups)
    write_csv(OUT/(symbol.lower()+"_episode_monthly_summary.csv"),monthly)
    return {"context_candles":len(records),"sessions":len(set(r["session"] for r in records)),
            "phase_counts":dict(Counter(r["phase"] for r in records)),
            "episodes":len(episodes),"transitions":len(transitions),
            "groups":groups,"monthly":monthly}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP103","research_only":True,
        "data_source":"EXP101 completed-candle causal feature CSV",
        "method":"Finite-state phase segmentation, first-bar event features, episode-end hindsight labels.",
        "limitations":[
            "Only 36-bar and 6-bar predeclared exploratory context definitions.",
            "Episode-end labels are not knowable at the episode start.",
            "A phase change to UP_CONTEXT is not proof of a durable trend reversal.",
            "Episodes from a single day can be dependent; no statistical significance inferred.",
            "Future 12-bar outcomes require enough same-session candles.",
            "June-August 2026 were previously inspected; not an independent holdout.",
            "No simulated entries, exits, commissions or profit; production untouched."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP103 — CHRONOLOGICAL TRAJECTORY PHASES — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"sessions:",s["sessions"],"context candles:",s["context_candles"],
              "rebound episodes:",s["episodes"],"phase transitions:",s["transitions"])
        print("  Phase counts:",s["phase_counts"])
        for g in s["groups"]:
            print(" ",g["start_structure"],"episodes:",g["episodes"],
                  "resumed_down:",g["resumed_down"],"turned_up:",g["turned_up"],
                  "flat:",g["flat"],"censored:",g["session_censored"],
                  "mean_12bar:",g["mean_future_12bar_pct"])
        for m in s["monthly"]:
            print("  month",m["month"],m["start_structure"],
                  "episodes:",m["episodes"],"resumed:",m["resumed_down"],
                  "turned_up:",m["turned_up"],"mean_12bar:",m["mean_future_12bar_pct"])
    print("\nDetailed files:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
