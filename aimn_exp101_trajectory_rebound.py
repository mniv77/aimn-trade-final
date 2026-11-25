#!/usr/bin/env python3
"""EXP101 — Causal trajectory vs countertrend rebound study.

Research only. Descriptive forward-path outcomes are NEVER used as
features or live decision inputs. Same-session complete windows only.
No strategy changes, fitting, or future-looking swing pivots.
"""
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp100_confirmed_swing_structure as exp100

OUT=Path(__file__).resolve().parent/"kiss/results/exp101_trajectory_rebound"
LOOKBACKS=(6,12,24,36)
HORIZONS=(3,6,12)

def pct(a,b):
    return round(100*(a/b-1),6) if b else None

def write_csv(path,records):
    if not records:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]))
        writer.writeheader();writer.writerows(records)

def state_features(rows,i,start,swings):
    close=float(rows[i]["close"])
    out={"structure_state":swings["structure_state"],
         "high_sequence":swings["high_sequence"],
         "low_sequence":swings["low_sequence"],
         "above_confirmed_high":swings["close_above_last_confirmed_high"]}
    for w in LOOKBACKS:
        if i-w+1<start:
            return None
        part=rows[i-w+1:i+1]
        first=float(part[0]["close"])
        closes=[float(r["close"]) for r in part]
        highs=[float(r["high"]) for r in part]
        lows=[float(r["low"]) for r in part]
        high=max(highs);low=min(lows)
        travel=sum(abs(closes[k]-closes[k-1]) for k in range(1,len(closes)))
        out["w%d_move_pct"%w]=pct(close,first)
        out["w%d_efficiency"%w]=round(abs(close-first)/travel,6) if travel else 0.0
        out["w%d_close_position"%w]=round((close-low)/(high-low),6) if high>low else 0.5
        out["w%d_range_pct"%w]=pct(high,low)
    out["context"]="DOWNWARD_36" if out["w36_move_pct"]<0 else "UPWARD_36" if out["w36_move_pct"]>0 else "FLAT_36"
    out["rebound"]="UP_6" if out["w6_move_pct"]>0 else "DOWN_6" if out["w6_move_pct"]<0 else "FLAT_6"
    out["countertrend_rebound"]=int(out["context"]=="DOWNWARD_36" and out["rebound"]=="UP_6")
    out["rebound_strength_ratio"]=round(max(0,out["w6_move_pct"])/abs(out["w36_move_pct"]),6) if out["w36_move_pct"] else None
    return out

def future_features(rows,i,end):
    close=float(rows[i]["close"])
    out={}
    for h in HORIZONS:
        if i+h>=end:
            for k in ("close_move_pct","max_up_pct","max_down_pct","outcome"):
                out["f%d_"%h+k]=None
            continue
        future=rows[i+1:i+h+1]
        f_close=float(future[-1]["close"])
        high=max(float(x["high"]) for x in future)
        low=min(float(x["low"]) for x in future)
        change=pct(f_close,close)
        out["f%d_close_move_pct"%h]=change
        out["f%d_max_up_pct"%h]=pct(high,close)
        out["f%d_max_down_pct"%h]=pct(low,close)
        out["f%d_outcome"%h]="UP" if change>0 else "DOWN" if change<0 else "FLAT"
    return out

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda x:str(x["timestamp"]))
    times=[str(x["timestamp"]) for x in rows]
    starts=exp100.get_session_starts(times)
    ends=[len(rows)]*len(rows)
    for i in range(len(rows)-2,-1,-1):
        ends[i]=ends[i+1] if times[i][:10]==times[i+1][:10] else i+1
    highs,lows,counts=exp100.confirmed_pivots(rows,times,starts)
    records=[]
    for i in range(len(rows)):
        swings=exp100.structure(rows,times,starts,i,highs,lows,counts)
        features=state_features(rows,i,starts[i],swings)
        if features is None:
            continue
        future=future_features(rows,i,ends[i])
        records.append({"symbol":symbol,"timestamp":times[i],
                        "session":times[i][:10],**features,**future})
    write_csv(OUT/(symbol.lower()+"_all_trajectory_observations.csv"),records)
    groups=defaultdict(list)
    for r in records:
        for h in HORIZONS:
            if r["f%d_outcome"%h] is None:
                continue
            # No future labels in group keys; group only by causal state.
            groups[(r["context"],r["rebound"],r["structure_state"],h)].append(r)
    summary=[]
    for (context,rebound,structure,h),rs in sorted(groups.items()):
        changes=[r["f%d_close_move_pct"%h] for r in rs]
        up=sum(x>0 for x in changes)
        down=sum(x<0 for x in changes)
        summary.append({
            "symbol":symbol,"context":context,"short_term":rebound,
            "structure":structure,"horizon_bars":h,
            "observations":len(rs),"future_up":up,"future_down":down,
            "future_flat":len(rs)-up-down,
            "future_up_rate":round(up/len(rs),6),
            "mean_future_close_move_pct":round(sum(changes)/len(changes),6),
            "mean_future_max_up_pct":round(sum(r["f%d_max_up_pct"%h] for r in rs)/len(rs),6),
            "mean_future_max_down_pct":round(sum(r["f%d_max_down_pct"%h] for r in rs)/len(rs),6),
        })
    write_csv(OUT/(symbol.lower()+"_group_summary.csv"),summary)
    rebound=[r for r in records if r["countertrend_rebound"]]
    by_session=Counter(r["session"] for r in rebound)
    return {
        "candles":len(rows),"complete_36bar_context_observations":len(records),
        "countertrend_rebound_observations":len(rebound),
        "countertrend_rebound_sessions":len(by_session),
        "warning":"Adjacent 5-minute observations overlap and are not independent trials.",
        "groups":summary
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"experiment":"EXP101","research_only":True,
            "definition":"36-candle negative close move with 6-candle positive close move denotes a countertrend rebound; not a trade signal.",
            "lookbacks":list(LOOKBACKS),"forward_horizons_bars":list(HORIZONS),
            "limitations":[
                "Forward paths are descriptive hindsight outcomes, not trade returns.",
                "No transaction costs or stop handling; no simulated strategy.",
                "Overlapping observations are strongly dependent; group counts are not independent samples.",
                "Only completed same-session candles; no overnight predictions.",
                "Historical same-period observations are in-sample and not validation.",
                "The 36/6 lookbacks are exploratory, not optimized or approved trading rules.",
                "No future candle or unconfirmed pivot enters the causal features."
            ],"symbols":{}}
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP101 — MAJOR TREND VS MINOR REBOUND — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"candles:",s["candles"],
              "valid context bars:",s["complete_36bar_context_observations"],
              "countertrend rebound bars:",s["countertrend_rebound_observations"],
              "sessions:",s["countertrend_rebound_sessions"])
        for g in s["groups"]:
            if g["context"]=="DOWNWARD_36" and g["short_term"]=="UP_6":
                print(" ",g["structure"],"horizon:",g["horizon_bars"],
                      "bars; n:",g["observations"],
                      "future up rate:",g["future_up_rate"],
                      "mean future move:",g["mean_future_close_move_pct"])
    print("\nFiles:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
