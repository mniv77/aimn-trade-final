#!/usr/bin/env python3
"""EXP102 — Session-clustered and month-level robustness of EXP101 rebound observations.

Research only. Each trading session is the unit of analysis. Grouping is
fixed from causal features; future close changes are used ONLY as labels.
No fitting, threshold tuning, strategy trade P&L or live changes.

For every structural group among negative 36-bar / positive 6-bar
countertrend rebounds, compare NVDA/AAPL future paths by session/month.
Produce non-overlapping EVENT START observations as an additional
sensitivity check, avoiding treating overlapping candles as independent.
"""
import csv
import json
from collections import defaultdict, Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp101_trajectory_rebound as exp101

OUT=Path(__file__).resolve().parent/"kiss/results/exp102_rebound_session_robustness"
HORIZONS=(3,6,12)
STRUCTURES=("ASCENDING_SWINGS","DESCENDING_SWINGS","MIXED_OR_INSUFFICIENT")

def write_csv(path,records):
    if not records:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]))
        writer.writeheader();writer.writerows(records)

def summarize(vals):
    if not vals:
        return {"observations":0,"up_rate":None,"mean_move_pct":None,"median_move_pct":None}
    sorted_vals=sorted(vals)
    n=len(vals)
    median=(sorted_vals[(n-1)//2]+sorted_vals[n//2])/2
    return {"observations":n,
            "up_rate":round(sum(x>0 for x in vals)/n,6),
            "mean_move_pct":round(sum(vals)/n,6),
            "median_move_pct":round(median,6)}

def summarize_sessions(records,h):
    sessions=defaultdict(list)
    key="f%d_close_move_pct"%h
    for r in records:
        if r.get(key) not in (None,""):
            sessions[r["session"]].append(float(r[key]))
    means={day:sum(vals)/len(vals) for day,vals in sessions.items()}
    if not means:
        return {"sessions":0,"session_weighted_mean_pct":None,
                "positive_session_share":None,"negative_session_share":None}
    return {"sessions":len(means),
            "session_weighted_mean_pct":round(sum(means.values())/len(means),6),
            "positive_session_share":round(sum(v>0 for v in means.values())/len(means),6),
            "negative_session_share":round(sum(v<0 for v in means.values())/len(means),6)}

def first_event_rows(records,h):
    """Collapse each contiguous qualifying streak to its first eligible bar.

    Any first observation without a full horizon is skipped, not replaced by
    the next bar, to avoid shifting event time toward known outcomes.
    """
    events=[]
    previous_qualified=False
    previous_session=None
    for r in records:
        is_qualified=(r["context"]=="DOWNWARD_36" and r["rebound"]=="UP_6")
        new_day=(r["session"]!=previous_session)
        if is_qualified and (not previous_qualified or new_day):
            if r.get("f%d_close_move_pct"%h) not in (None,""):
                events.append(r)
        previous_qualified=is_qualified
        previous_session=r["session"]
    return events

def read_csv(path):
    with path.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))

def audit_symbol(symbol,path):
    input_path=exp101.OUT/(symbol.lower()+"_all_trajectory_observations.csv")
    if not input_path.exists():
        raise FileNotFoundError("Run EXP101 first: "+str(input_path))
    records=read_csv(input_path)
    # Match expected data asset presence; no rewriting or mutation.
    if not path.exists():
        raise FileNotFoundError(str(path))
    if any(r.get("symbol")!=symbol for r in records):
        raise AssertionError("EXP101 symbol mismatch: "+symbol)
    sessions=sorted({r["session"] for r in records})
    grouped=[]
    monthly=[]
    session_rows=[]
    event_rows=[]
    for h in HORIZONS:
        group_events=first_event_rows(records,h)
        for structure in STRUCTURES:
            selected=[r for r in records if r["context"]=="DOWNWARD_36" and
                      r["rebound"]=="UP_6" and r["structure_state"]==structure and
                      r.get("f%d_close_move_pct"%h) not in (None,"")]
            values=[float(r["f%d_close_move_pct"%h]) for r in selected]
            per_sessions=summarize_sessions(selected,h)
            # The first bar of each contiguous qualifying event is selected
            # independent of subsequent prices, though events may still overlap.
            independentish=[r for r in group_events if r["structure_state"]==structure]
            event_values=[float(r["f%d_close_move_pct"%h]) for r in independentish]
            grouped.append({
                "symbol":symbol,"horizon_bars":h,"structure":structure,
                **summarize(values),**per_sessions,
                "first_event_n":len(event_values),
                "first_event_up_rate":summarize(event_values)["up_rate"],
                "first_event_mean_pct":summarize(event_values)["mean_move_pct"]})
            by_session=defaultdict(list)
            by_month=defaultdict(list)
            for r in selected:
                by_session[r["session"]].append(float(r["f%d_close_move_pct"%h]))
                by_month[r["session"][:7]].append(float(r["f%d_close_move_pct"%h]))
            for day,vals in sorted(by_session.items()):
                session_rows.append({"symbol":symbol,"horizon_bars":h,
                    "structure":structure,"session":day,**summarize(vals)})
            for month,vals in sorted(by_month.items()):
                sess_count=len({r["session"] for r in selected if r["session"][:7]==month})
                monthly.append({"symbol":symbol,"horizon_bars":h,"structure":structure,
                    "month":month,"sessions":sess_count,**summarize(vals)})
            for r in independentish:
                event_rows.append({"symbol":symbol,"horizon_bars":h,
                    "structure":structure,"timestamp":r["timestamp"],
                    "session":r["session"],"future_move_pct":r["f%d_close_move_pct"%h]})
    write_csv(OUT/(symbol.lower()+"_group_robustness.csv"),grouped)
    write_csv(OUT/(symbol.lower()+"_monthly_robustness.csv"),monthly)
    write_csv(OUT/(symbol.lower()+"_session_means.csv"),session_rows)
    write_csv(OUT/(symbol.lower()+"_rebound_event_starts.csv"),event_rows)
    return {"records_from_exp101":len(records),"sessions_with_36bar_context":len(sessions),
            "groups":grouped,"monthly":monthly}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP102","research_only":True,
        "data_dependency":"EXP101 existing CSV files (full candle-level context)",
        "analyses":"Session-equal-weight averages, month breakdown, contiguous-rebound first-event sensitivity.",
        "limitations":[
            "Groups and horizons remain historical; no independent holdout.",
            "First-event observations can still overlap in future windows and are not statistically independent.",
            "First-event sampling is defined as first qualifying 36down/6up candle per contiguous streak, without future-label selection.",
            "Monthly statistics may have very few sessions and are descriptive only.",
            "No uncertainty estimates, bootstrap, or significance claims.",
            "Forward path movements are not executable trading profits.",
            "No tuning, entry or exit changes; production unchanged."
        ],"symbols":{}}
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=audit_symbol(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP102 — SESSION-LEVEL REBOUND ROBUSTNESS — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"EXP101 records:",s["records_from_exp101"],
              "sessions:",s["sessions_with_36bar_context"])
        for g in s["groups"]:
            if g["horizon_bars"]==12:
                print(" ",g["structure"],"h12 n:",g["observations"],
                      "sessions:",g["sessions"],
                      "candle mean:",g["mean_move_pct"],
                      "session mean:",g["session_weighted_mean_pct"],
                      "positive sessions:",g["positive_session_share"],
                      "event starts:",g["first_event_n"],
                      "event mean:",g["first_event_mean_pct"])
        for m in s["monthly"]:
            if m["horizon_bars"]==12:
                print("  month",m["month"],m["structure"],
                      "n:",m["observations"],"sessions:",m["sessions"],
                      "mean:",m["mean_move_pct"])
    print("\nDetailed reports:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
