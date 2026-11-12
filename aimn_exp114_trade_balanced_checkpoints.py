#!/usr/bin/env python3
"""EXP114 — trade-balanced causal post-profit checkpoints (research only).

Each trade contributes at most one observation per predeclared checkpoint:
first fee-cover close and +3/+6/+12 completed 5m candles. Features use only
completed same-session candles. Group labels use eventual outcome only for
retrospective comparison. No fitted threshold or strategy simulation.
"""
import csv,json
from pathlib import Path
from collections import Counter
import statistics

import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as exp100

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp114_trade_balanced_checkpoints"
FEE=2*exp79.FEE
CHECKPOINTS=(0,3,6,12)
WINDOWS=(3,6,12)
FEATURES=("close_move_pct","up_close_fraction","higher_low_fraction",
          "directional_efficiency","close_range_position")

def gross(entry,price):
    return 100*(entry/price-1)

def write(path,rows):
    if not rows:return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)

def snapshot(rows,closes,session_start,i,w):
    if i-w+1<session_start[i]:return None
    begin=i-w+1
    segment=closes[begin:i+1]
    lows=[float(rows[k]["low"]) for k in range(begin,i+1)]
    highs=[float(rows[k]["high"]) for k in range(begin,i+1)]
    changes=[segment[k]-segment[k-1] for k in range(1,w)]
    travel=sum(abs(x) for x in changes)
    span=max(highs)-min(lows)
    return {
        "close_move_pct":100*(segment[-1]/segment[0]-1),
        "up_close_fraction":sum(x>0 for x in changes)/(w-1),
        "higher_low_fraction":sum(lows[k]>lows[k-1] for k in range(1,w))/(w-1),
        "directional_efficiency":abs(segment[-1]-segment[0])/travel if travel else 0,
        "close_range_position":(segment[-1]-min(lows))/span if span else 0.5,
    }

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    idx={t:i for i,t in enumerate(times)}
    if len(idx)!=len(times):raise AssertionError("Duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    trades,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    starts=exp100.get_session_starts(times)
    ph,pl,counts=exp100.confirmed_pivots(rows,times,starts)
    observations=[];trade_records=[]
    for t in trades:
        ei=idx[t["entry_time"]];xi=idx[t["exit_time"]]
        if times[ei][:10]!=times[xi][:10]:raise AssertionError("Cross-session trade")
        entry=float(t["entry_price"])
        # The exit candle close cannot be known for next-open exits or stops.
        end=xi if t["exit_reason"] in ("SESSION_END","DATA_END") else xi-1
        fee_i=next((i for i in range(ei,end+1)
                    if gross(entry,closes[i])>FEE),None)
        group=("WINNER_CONTROL" if t["net_pnl_pct"]>0 else
               "LOSING_GIVEBACK" if fee_i is not None else
               "NO_FEE_COVERING_CLOSE")
        trade_records.append({
            "symbol":symbol,"entry_time":t["entry_time"],
            "exit_time":t["exit_time"],"exit_reason":t["exit_reason"],
            "group_hindsight":group,"original_net_pct":t["net_pnl_pct"],
            "first_fee_cover_time":times[fee_i] if fee_i is not None else None,
            "available_completed_bars_after_fee":
                max(0,end-fee_i+1) if fee_i is not None else 0
        })
        if fee_i is None:continue
        for step in CHECKPOINTS:
            i=fee_i+step
            if i>end:continue
            current_gross=gross(entry,closes[i])
            state=exp100.structure(rows,times,starts,i,ph,pl,counts)
            # Next-open hypothetical close can only be compared when it
            # occurs before original exit. Exclude simultaneous stop/open
            # timing ambiguity and all simultaneous original exits.
            next_open_i=i+1
            executable=(next_open_i<len(rows) and
                        times[next_open_i][:10]==times[i][:10] and
                        next_open_i<xi)
            rec={
                "symbol":symbol,"entry_time":t["entry_time"],
                "group_hindsight":group,"checkpoint_bars_after_fee":step,
                "checkpoint_time":times[i],"bars_since_entry":i-ei,
                "original_exit_time_hindsight":t["exit_time"],
                "original_net_pct_hindsight":t["net_pnl_pct"],
                "gross_at_checkpoint_close_pct":round(current_gross,6),
                "net_at_checkpoint_close_before_slippage_pct":round(current_gross-FEE,6),
                "still_above_fee_at_close":current_gross>FEE,
                "confirmed_swing_state":state["structure_state"],
                "close_above_confirmed_high":state["close_above_last_confirmed_high"],
                "close_below_confirmed_low":state["close_below_last_confirmed_low"],
                "next_open_precedes_original_exit":executable,
                "next_open_time":times[next_open_i] if executable else None,
                "next_open_net_hypothetical_pct":round(gross(entry,opens[next_open_i])-FEE,6)
                    if executable else None,
                "next_open_difference_vs_original_pp_hindsight":
                    round(gross(entry,opens[next_open_i])-FEE-t["net_pnl_pct"],6)
                    if executable else None,
            }
            for w in WINDOWS:
                snap=snapshot(rows,closes,starts,i,w)
                for key in FEATURES:
                    rec[f"w{w}_{key}"]=round(snap[key],6) if snap else None
            observations.append(rec)
    write(OUT/(symbol.lower()+"_trade_inventory.csv"),trade_records)
    write(OUT/(symbol.lower()+"_checkpoint_features.csv"),observations)
    summary=[]
    for step in CHECKPOINTS:
        for group in ("WINNER_CONTROL","LOSING_GIVEBACK","NO_FEE_COVERING_CLOSE"):
            candidates=[r for r in trade_records if r["group_hindsight"]==group]
            obs=[r for r in observations
                 if r["checkpoint_bars_after_fee"]==step and
                    r["group_hindsight"]==group]
            item={
                "symbol":symbol,"checkpoint_bars_after_fee":step,
                "group":group,"group_trades":len(candidates),
                "observed_trades":len(obs),
                "missing_due_to_short_hold_or_no_fee_cover":len(candidates)-len(obs),
                "still_above_fee_count":sum(r["still_above_fee_at_close"] for r in obs),
                "mean_gross_at_checkpoint_close_pct":
                    round(statistics.mean(r["gross_at_checkpoint_close_pct"] for r in obs),6)
                    if obs else None,
                "actionable_next_open_before_original_exit_count":
                    sum(r["next_open_precedes_original_exit"] for r in obs),
                "mean_next_open_difference_vs_original_pp_hindsight":
                    round(statistics.mean(r["next_open_difference_vs_original_pp_hindsight"]
                        for r in obs if r["next_open_precedes_original_exit"]),6)
                    if any(r["next_open_precedes_original_exit"] for r in obs) else None,
            }
            for w in WINDOWS:
                for feature in FEATURES:
                    key=f"w{w}_{feature}"
                    vals=[r[key] for r in obs if r[key] is not None]
                    item["mean_"+key]=round(statistics.mean(vals),6) if vals else None
                    item["valid_"+key]=len(vals)
            summary.append(item)
    write(OUT/(symbol.lower()+"_balanced_group_summary.csv"),summary)
    return {
        "trades":len(trades),
        "baseline_net_sum_pct":round(sum(t["net_pnl_pct"] for t in trades),6),
        "groups":dict(Counter(r["group_hindsight"] for r in trade_records)),
        "balanced_checkpoint_groups":summary,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP114","research_only":True,
        "goal":"Compare structural features with one observation per trade at fixed causal post-fee checkpoints.",
        "round_trip_fee_pct":FEE,"checkpoints_bars":list(CHECKPOINTS),
        "feature_windows_bars":list(WINDOWS),
        "limitations":[
            "Checkpoint +3/+6/+12 observations condition on surviving in the original trade; attrition is reported.",
            "Eventual winner/giveback labels are hindsight and never used to construct features.",
            "Feature windows use completed same-session candles, including pre-entry history where available.",
            "No alternative exits are triggered; next-open outcomes are descriptive fixed-entry counterfactuals.",
            "Checkpoint-at-exit session close is observable but has no earlier actionable next-open.",
            "Only 20 historical trades across two previously researched symbols; no holdout.",
            "Summed returns are not compounded portfolio performance."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP114 — TRADE-BALANCED CAUSAL CHECKPOINT AUDIT — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"trades:",s["trades"],"baseline net:",s["baseline_net_sum_pct"],
              "groups:",s["groups"])
        for g in s["balanced_checkpoint_groups"]:
            if g["group"]=="NO_FEE_COVERING_CLOSE":continue
            print(" CHECKPOINT",g["checkpoint_bars_after_fee"],g["group"],
                  "observed:",g["observed_trades"],"/",g["group_trades"],
                  "still_above_fee:",g["still_above_fee_count"],
                  "next_open_possible:",g["actionable_next_open_before_original_exit_count"],
                  "w12_move:",g["mean_w12_close_move_pct"],
                  "w12_up_fraction:",g["mean_w12_up_close_fraction"],
                  "w12_efficiency:",g["mean_w12_directional_efficiency"],
                  "w12_close_range:",g["mean_w12_close_range_position"])
    print("\nCSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
