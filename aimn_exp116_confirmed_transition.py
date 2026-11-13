#!/usr/bin/env python3
"""EXP116 — confirmed SHORT-to-LONG swing transition audit, research only.

Test causal swing structure after first fee-covering SHORT close. Pivots use
2 left / 2 right completed same-session candles; recognition occurs only at
confirmation close. Fixed-entry next-open comparisons, no strategy replay.
"""
import csv,json
from pathlib import Path
from collections import Counter
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as swing

OUT=Path(__file__).resolve().parent/"kiss/results/exp116_confirmed_transition"
FEE=2*exp79.FEE
RULES=("HIGHER_LOW","HIGH_BREAK","HIGHER_LOW_THEN_HIGH_BREAK",
       "HIGHER_LOW_AND_HIGH_BREAK","ASCENDING_SWINGS")

def write(path,records):
    if not records:return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]))
        writer.writeheader();writer.writerows(records)

def gross(entry,close):
    return 100*(entry/close-1)

def signal(rule,state,seen_higher_low):
    hl=state["low_sequence"]=="HIGHER_LOW"
    hb=state["close_above_last_confirmed_high"]==1
    if rule=="HIGHER_LOW":return hl
    if rule=="HIGH_BREAK":return hb
    if rule=="HIGHER_LOW_THEN_HIGH_BREAK":return seen_higher_low and hb
    if rule=="HIGHER_LOW_AND_HIGH_BREAK":return hl and hb
    if rule=="ASCENDING_SWINGS":return state["structure_state"]=="ASCENDING_SWINGS"
    raise ValueError(rule)

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    idx={t:i for i,t in enumerate(times)}
    if len(idx)!=len(times):raise AssertionError("Duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    starts=swing.get_session_starts(times)
    highs,lows,counts=swing.confirmed_pivots(rows,times,starts)
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    trades,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    per_trade=[];events=[];inventory=[]
    for trade in trades:
        ei=idx[trade["entry_time"]];xi=idx[trade["exit_time"]]
        if times[ei][:10]!=times[xi][:10]:raise AssertionError("Cross-session trade")
        entry=float(trade["entry_price"])
        # Original next-open exits and stops cannot use the exit candle close.
        end=xi if trade["exit_reason"] in ("SESSION_END","DATA_END") else xi-1
        first_fee=next((i for i in range(ei,end+1)
                        if gross(entry,closes[i])>FEE),None)
        group=("WINNER_CONTROL" if trade["net_pnl_pct"]>0 else
               "LOSING_GIVEBACK" if first_fee is not None else
               "NO_FEE_COVERING_CLOSE")
        inventory.append({
            "symbol":symbol,"entry_time":trade["entry_time"],
            "exit_time":trade["exit_time"],"exit_reason":trade["exit_reason"],
            "group_hindsight":group,"original_net_pct":trade["net_pnl_pct"],
            "first_fee_cover_time":times[first_fee] if first_fee is not None else None,
        })
        # Structure is checked on every post-entry completed close. A higher
        # low can be confirmed before the fee-cover close, but the exit
        # candidate is not armed until fee cover occurs.
        states={}
        if first_fee is not None:
            for i in range(ei,end+1):
                states[i]=swing.structure(rows,times,starts,i,highs,lows,counts)
        for rule in RULES:
            first=None
            seen_higher_low=False
            for i in range(ei,end+1) if first_fee is not None else ():
                state=states[i]
                if state["low_sequence"]=="HIGHER_LOW":
                    seen_higher_low=True
                if i<first_fee:continue
                if signal(rule,state,seen_higher_low):
                    first=i;break
            next_i=first+1 if first is not None else None
            # Exclude the original exit candle to avoid stop/open ambiguity
            # and prevent treating an identical exit as a distinct benefit.
            executable=(next_i is not None and next_i<xi and
                        next_i<len(rows) and
                        times[next_i][:10]==times[first][:10])
            net=gross(entry,opens[next_i])-FEE if executable else None
            state=states[first] if first is not None else None
            rec={
                "symbol":symbol,"rule":rule,"entry_time":trade["entry_time"],
                "group_hindsight":group,"original_exit_time":trade["exit_time"],
                "original_exit_reason":trade["exit_reason"],
                "original_net_pct":trade["net_pnl_pct"],
                "fee_cover_time":times[first_fee] if first_fee is not None else None,
                "first_signal_time":times[first] if first is not None else None,
                "bars_from_fee_to_signal":first-first_fee if first is not None else None,
                "signal_close_gross_pct":round(gross(entry,closes[first]),6)
                    if first is not None else None,
                "signal_close_still_fee_covered":
                    gross(entry,closes[first])>FEE if first is not None else None,
                "high_sequence":state["high_sequence"] if state else None,
                "low_sequence":state["low_sequence"] if state else None,
                "structure_state":state["structure_state"] if state else None,
                "latest_high_confirmed_time":
                    state["latest_high_confirmed_time"] if state else None,
                "latest_low_confirmed_time":
                    state["latest_low_confirmed_time"] if state else None,
                "next_open_before_original_exit":executable,
                "next_open_time":times[next_i] if executable else None,
                "next_open_net_pct":round(net,6) if executable else None,
                "delta_vs_original_pp_hindsight":
                    round(net-trade["net_pnl_pct"],6) if executable else None,
            }
            per_trade.append(rec)
            if first is not None:events.append(rec)
    write(OUT/(symbol.lower()+"_trade_inventory.csv"),inventory)
    write(OUT/(symbol.lower()+"_first_signal_by_trade.csv"),per_trade)
    write(OUT/(symbol.lower()+"_structural_events.csv"),events)
    groups=[]
    for rule in RULES:
        for group in ("WINNER_CONTROL","LOSING_GIVEBACK","NO_FEE_COVERING_CLOSE"):
            subset=[r for r in per_trade if r["rule"]==rule and r["group_hindsight"]==group]
            active=[r for r in subset if r["next_open_before_original_exit"]]
            diffs=[r["delta_vs_original_pp_hindsight"] for r in active]
            groups.append({
                "symbol":symbol,"rule":rule,"group":group,
                "group_trade_count":len(subset),
                "first_signal_count":sum(r["first_signal_time"] is not None for r in subset),
                "executable_count":len(active),
                "unexecutable_signal_count":sum(r["first_signal_time"] is not None and
                                              not r["next_open_before_original_exit"]
                                              for r in subset),
                "still_fee_covered_at_signal_count":sum(
                    r["signal_close_still_fee_covered"] is True for r in active),
                "helped_count_hindsight":sum(d>0 for d in diffs),
                "hurt_count_hindsight":sum(d<0 for d in diffs),
                "sum_delta_pp_hindsight":round(sum(diffs),6),
                "sum_next_open_net_triggered_pct":round(
                    sum(r["next_open_net_pct"] for r in active),6),
                "sum_original_net_triggered_pct":round(
                    sum(r["original_net_pct"] for r in active),6),
            })
    write(OUT/(symbol.lower()+"_rule_group_summary.csv"),groups)
    return {
        "trades":len(trades),
        "baseline_net_sum_pct":round(sum(t["net_pnl_pct"] for t in trades),6),
        "groups":dict(Counter(r["group_hindsight"] for r in inventory)),
        "rule_group_summary":groups,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP116","research_only":True,
        "pivot_confirmation":{"left":swing.LEFT,"right":swing.RIGHT,
                              "strict_extrema":True,"same_session":True},
        "rules":list(RULES),"fee_cover_gross_pct":FEE,
        "limitations":[
            "Higher-low state can persist after confirmation; signals are the first armed state, not necessarily the first transition event.",
            "HIGHER_LOW_THEN_HIGH_BREAK requires a higher low observed at or before the break; both may occur at the same close.",
            "No confirmed pivot exists early in many sessions; absence is not evidence of continued downtrend.",
            "Signals are causal, but winner/giveback labels and delta comparisons are retrospective.",
            "Original entries held fixed; alternative exits may change later entries.",
            "Only trades first covering commissions are armed; no-fee-cover entries are not fixed.",
            "Original exit candle excluded from hypothetical next-open comparisons.",
            "No full chronological replay, out-of-sample testing, slippage or portfolio modeling.",
            "The five structural definitions are descriptive candidates, not optimized or validated rules.",
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP116 — CONFIRMED SHORT-TO-LONG SWING TRANSITION — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n",symbol,"trades:",s["trades"],"baseline net:",s["baseline_net_sum_pct"],
              "groups:",s["groups"])
        for row in s["rule_group_summary"]:
            if row["group"]=="NO_FEE_COVERING_CLOSE":continue
            print(" RULE",row["rule"],row["group"],
                  "signals:",row["first_signal_count"],
                  "executable:",row["executable_count"],
                  "helped:",row["helped_count_hindsight"],
                  "hurt:",row["hurt_count_hindsight"],
                  "delta_pp:",row["sum_delta_pp_hindsight"],
                  "fee_covered:",row["still_fee_covered_at_signal_count"])
    print("\nCSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
