#!/usr/bin/env python3
"""EXP82: causal candle features at EXP81 rebound signals.
Research-only diagnostics, NOT a predictive strategy or live trading module.
Future trade outcome labels are used for analysis only, never signal features.
"""
import csv
import json
from pathlib import Path
from collections import defaultdict

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"kiss/visual_research/aimn_nvda_candles.json"
EVENTS=ROOT/"kiss/results/exp81_rebound_aftermath/rebound_events.csv"
OUT=ROOT/"kiss/results/exp82_causal_reversal_features"

def read_csv(path):
    with path.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))
def write_csv(path,rows,columns):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=columns)
        w.writeheader()
        w.writerows(rows)
def pchange(a,b):
    return (a/b-1)*100
def round5(v):
    return round(v,5) if v is not None else None
def main():
    candles=json.loads(DATA.read_text(encoding="utf-8"))
    candles.sort(key=lambda x:str(x["timestamp"]))
    timestamps=[str(x["timestamp"]) for x in candles]
    index={t:i for i,t in enumerate(timestamps)}
    if len(index)!=len(timestamps):
        raise ValueError("Duplicate candle timestamps")
    events=read_csv(EVENTS)
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for event in events:
        signal_time=event["trigger_candle"]
        entry_time=event["entry_time"]
        if signal_time not in index or entry_time not in index:
            raise ValueError("Missing timestamp: "+signal_time)
        i=index[signal_time];start=index[entry_time]
        if i<start or timestamps[i][:10]!=timestamps[start][:10]:
            raise ValueError("Cross-session or inverted event")
        completed=candles[start:i+1]
        close=float(candles[i]["close"])
        entry_open=float(candles[start]["open"])
        closes=[float(x["close"]) for x in completed]
        # Previous completed candles only; do not count the signal candle
        # itself in a swing-high breakout threshold.
        previous=candles[max(start,i-6):i]
        previous_high=max((float(x["high"]) for x in previous),default=None)
        previous_close_high=max((float(x["close"]) for x in previous),default=None)
        prior_closes=[float(x["close"]) for x in candles[max(start,i-3):i+1]]
        up_closes=sum(prior_closes[j]>prior_closes[j-1] for j in range(1,len(prior_closes)))
        up_consecutive=0
        for j in range(i,start,-1):
            if float(candles[j]["close"])>float(candles[j-1]["close"]):
                up_consecutive+=1
            else:
                break
        lower_closes=sum(closes[j]<closes[j-1] for j in range(1,len(closes)))
        elapsed=i-start+1
        lowest_close=min(closes)
        lowest_index=start+closes.index(lowest_close)
        # Outcome columns are hindsight labels only. Keep features separate.
        row={
            "variant":event["variant"],
            "entry_time":entry_time,
            "signal_time":signal_time,
            "exit_time":event["early_exit_time"],
            "bars_since_entry":elapsed,
            "bars_since_lowest_close":i-lowest_index,
            "prior_lower_close_count":lower_closes,
            "up_closes_last_3_transitions":up_closes,
            "consecutive_up_closes":up_consecutive,
            "rebound_from_lowest_close_pct":round5(pchange(close,lowest_close)),
            "gross_short_profit_at_signal_pct":round5(pchange(entry_open,close)),
            "breaks_prior_6bar_high":close>previous_high if previous_high is not None else None,
            "breaks_prior_6bar_close_high":close>previous_close_high if previous_close_high is not None else None,
            "distance_to_prior_6bar_high_pct":round5(pchange(close,previous_high)) if previous_high else None,
            "signal_body_pct":round5(pchange(float(candles[i]["close"]),float(candles[i]["open"]))),
            "signal_range_pct":round5(pchange(float(candles[i]["high"]),float(candles[i]["low"]))),
            "outcome_early_minus_baseline_pp":float(event["early_minus_baseline_pp"]),
            "outcome_helped":float(event["early_minus_baseline_pp"])>0,
            "outcome_rescued_baseline_loser":event["baseline_loser_rescued"].lower()=="true",
            "outcome_cut_baseline_winner":event["baseline_winner_cut_short"].lower()=="true",
        }
        rows.append(row)
    feature_fields=[
        "variant","entry_time","signal_time","exit_time",
        "bars_since_entry","bars_since_lowest_close",
        "prior_lower_close_count","up_closes_last_3_transitions",
        "consecutive_up_closes","rebound_from_lowest_close_pct",
        "gross_short_profit_at_signal_pct",
        "breaks_prior_6bar_high","breaks_prior_6bar_close_high",
        "distance_to_prior_6bar_high_pct","signal_body_pct","signal_range_pct",
    ]
    outcome_fields=[
        "outcome_early_minus_baseline_pp","outcome_helped",
        "outcome_rescued_baseline_loser","outcome_cut_baseline_winner",
    ]
    write_csv(OUT/"causal_features_with_hindsight_labels.csv",rows,
              feature_fields+outcome_fields)
    groups=defaultdict(list)
    for row in rows:
        groups[row["variant"]].append(row)
    summary={
        "experiment":"EXP82",
        "events":len(rows),
        "unique_entry_dates":len(set(row["entry_time"] for row in rows)),
        "variants":{},
        "critical_caveat":"Outcomes are hindsight labels, not signal inputs. Variants share trades, so events are not independent. No parameter optimization or predictive accuracy claim.",
    }
    for variant,group in sorted(groups.items()):
        summary["variants"][variant]={
            "events":len(group),
            "helped":sum(x["outcome_helped"] for x in group),
            "hurt":sum(x["outcome_early_minus_baseline_pp"]<0 for x in group),
            "unchanged":sum(x["outcome_early_minus_baseline_pp"]==0 for x in group),
            "rescued_losers":sum(x["outcome_rescued_baseline_loser"] for x in group),
            "cut_winners":sum(x["outcome_cut_baseline_winner"] for x in group),
            "features_for_helped":[{
                "entry":x["entry_time"],
                "bars":x["bars_since_entry"],
                "up_closes":x["consecutive_up_closes"],
                "break_high":x["breaks_prior_6bar_high"],
                "gross_profit_at_signal_pct":x["gross_short_profit_at_signal_pct"],
            } for x in group if x["outcome_helped"]],
            "features_for_hurt":[{
                "entry":x["entry_time"],
                "bars":x["bars_since_entry"],
                "up_closes":x["consecutive_up_closes"],
                "break_high":x["breaks_prior_6bar_high"],
                "gross_profit_at_signal_pct":x["gross_short_profit_at_signal_pct"],
            } for x in group if x["outcome_early_minus_baseline_pp"]<0],
        }
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print("EXP82 — CAUSAL REVERSAL FEATURES — RESEARCH ONLY")
    print(json.dumps(summary,indent=2))
    print("CSV:",OUT/"causal_features_with_hindsight_labels.csv")
if __name__=="__main__":
    main()
