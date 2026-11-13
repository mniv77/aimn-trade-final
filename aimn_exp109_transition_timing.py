#!/usr/bin/env python3
"""EXP109 — V16 SHORT transition timing and remaining opportunity.

Research only. Baseline V16 trade replay and accepted signal audit. Peak
references are strictly confirmed same-session pivots available at signal
close (EXP100's 2-right-bar confirmation). Hindsight excursions are labeled
and not used as entry features. No new rule, tuning, or production edits.
"""
import csv
import json
from pathlib import Path
from collections import Counter
import aimn_exp83_v16_structural_exit as base
import aimn_exp93_sideways_research as exp93
import aimn_exp100_confirmed_swing_structure as exp100

OUT=Path(__file__).resolve().parent/"kiss/results/exp109_transition_timing"

def pct(a,b):
    return round(100*(a/b-1),6) if b else None

def save(path,records):
    if not records:return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(times)!=len(set(times)):raise AssertionError("Duplicate timestamps")
    index={t:i for i,t in enumerate(times)}
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    trades,candidates,_,audit,_,_=exp93.simulate(rows,st,rsi,market,"BASELINE")
    expected,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    if trades!=expected:raise AssertionError(symbol+": V16 baseline drift")
    starts=exp100.get_session_starts(times)
    pivot_highs,pivot_lows,counts=exp100.confirmed_pivots(rows,times,starts)
    by_entry={t["entry_time"]:t for t in trades}
    accepted=[r for r in audit if r["decision"]=="ACCEPTED"]
    if len(accepted)!=len(trades):raise AssertionError(symbol+": accepted count != trades")
    records=[]
    for event in accepted:
        signal_i=index[event["signal_time"]]
        entry_i=signal_i+1
        if entry_i>=len(rows) or times[entry_i][:10]!=times[signal_i][:10]:
            raise AssertionError("Invalid next same-session entry")
        trade=by_entry.get(times[entry_i])
        if trade is None:raise AssertionError("Missing trade at "+times[entry_i])
        exit_i=index[trade["exit_time"]]
        if exit_i<entry_i:raise AssertionError("Exit before entry")
        state=exp100.structure(rows,times,starts,signal_i,pivot_highs,pivot_lows,counts)
        hcount,lcount=counts[signal_i]
        confirmed_highs=[p for p in pivot_highs[:hcount] if p["pivot_time"][:10]==times[signal_i][:10]]
        latest=confirmed_highs[-1] if confirmed_highs else None
        recent_high=max(highs[starts[signal_i]:signal_i+1])
        recent_high_i=max(range(starts[signal_i],signal_i+1),key=lambda j:highs[j])
        signal_close=closes[signal_i]
        entry_open=float(rows[entry_i]["open"])
        # Hindsight only: high/low of actual holding interval, including entry
        # and exit bars; OHLC extrema are NOT guaranteed executable fills.
        holding_lows=lows[entry_i:exit_i+1]
        best_low=min(holding_lows)
        best_low_i=entry_i+holding_lows.index(best_low)
        holding_high=max(highs[entry_i:exit_i+1])
        # Counterfactual opportunity within same session after entry:
        # includes bars after actual exit; not a realizable strategy return.
        last_session=entry_i
        while last_session+1<len(rows) and times[last_session+1][:10]==times[entry_i][:10]:
            last_session+=1
        full_lows=lows[entry_i:last_session+1]
        session_low=min(full_lows)
        session_low_i=entry_i+full_lows.index(session_low)
        rec={
            "symbol":symbol,"signal_time":times[signal_i],"entry_time":times[entry_i],
            "signal_close":signal_close,"entry_open":entry_open,
            "signal_st":st[signal_i],"signal_rsi":rsi[signal_i],
            "sideways_at_signal":event["sideways"],
            "swing_state":state["structure_state"],
            "high_sequence":state["high_sequence"],
            "low_sequence":state["low_sequence"],
            "confirmed_high_count":state["confirmed_high_count"],
            "latest_confirmed_high_pivot_time":latest["pivot_time"] if latest else None,
            "latest_confirmed_high_known_time":latest["confirmed_time"] if latest else None,
            "latest_confirmed_high_price":round(latest["price"],6) if latest else None,
            "bars_since_confirmed_high_pivot":signal_i-latest["pivot_index"] if latest else None,
            "bars_since_high_confirmation":signal_i-latest["confirmed_index"] if latest else None,
            "signal_decline_from_confirmed_high_pct":pct(latest["price"],signal_close) if latest else None,
            "entry_gap_from_signal_close_pct":pct(entry_open,signal_close),
            "prior_session_local_high_price":round(recent_high,6),
            "prior_session_local_high_time":times[recent_high_i],
            "bars_since_session_high":signal_i-recent_high_i,
            "signal_decline_from_session_high_pct":pct(recent_high,signal_close),
            "close_below_confirmed_low":state["close_below_last_confirmed_low"],
            "baseline_exit_time_hindsight":trade["exit_time"],
            "baseline_exit_reason_hindsight":trade["exit_reason"],
            "baseline_net_pct_hindsight":trade["net_pnl_pct"],
            "baseline_gross_pct_hindsight":trade["gross_pnl_pct"],
            "baseline_bars_held_hindsight":trade["bars_held"],
            "baseline_best_close_short_pct_hindsight":trade["best_close_short_pct"],
            "best_intrabar_low_during_hold_hindsight":round(best_low,6),
            "best_intrabar_low_during_hold_time_hindsight":times[best_low_i],
            "maximum_intrabar_favorable_excursion_hold_pct_hindsight":pct(entry_open,best_low),
            "maximum_intrabar_adverse_excursion_hold_pct_hindsight":pct(holding_high,entry_open),
            "session_low_after_entry_hindsight":round(session_low,6),
            "session_low_after_entry_time_hindsight":times[session_low_i],
            "maximum_intrabar_favorable_excursion_session_pct_hindsight":pct(entry_open,session_low),
            "session_low_after_actual_exit_hindsight":session_low_i>exit_i,
            "outcome_hindsight":"WIN" if trade["net_pnl_pct"]>0 else "LOSS",
        }
        records.append(rec)
    save(OUT/(symbol.lower()+"_all_entries_timing.csv"),records)
    for outcome in ("WIN","LOSS"):
        save(OUT/(symbol.lower()+"_"+outcome.lower()+"_timing.csv"),
             [r for r in records if r["outcome_hindsight"]==outcome])
    def avg(key,subset):
        v=[r[key] for r in subset if r[key] is not None]
        return round(sum(v)/len(v),6) if v else None
    summary=[]
    for name,subset in (
        ("ALL",records),
        ("WINNERS",[r for r in records if r["outcome_hindsight"]=="WIN"]),
        ("LOSERS",[r for r in records if r["outcome_hindsight"]=="LOSS"]),
        ("SIDEWAYS",[r for r in records if r["sideways_at_signal"]]),
        ("NOT_SIDEWAYS",[r for r in records if not r["sideways_at_signal"]]),
    ):
        summary.append({
            "group":name,"trades":len(subset),
            "net_sum_pct":round(sum(r["baseline_net_pct_hindsight"] for r in subset),6),
            "with_confirmed_high":sum(r["latest_confirmed_high_price"] is not None for r in subset),
            "mean_bars_since_confirmed_peak":avg("bars_since_confirmed_high_pivot",subset),
            "mean_signal_decline_from_confirmed_peak_pct":avg("signal_decline_from_confirmed_high_pct",subset),
            "mean_bars_since_session_high":avg("bars_since_session_high",subset),
            "mean_signal_decline_from_session_high_pct":avg("signal_decline_from_session_high_pct",subset),
            "mean_intrabar_favorable_excursion_hold_pct_hindsight":avg(
                "maximum_intrabar_favorable_excursion_hold_pct_hindsight",subset),
            "mean_intrabar_favorable_excursion_session_pct_hindsight":avg(
                "maximum_intrabar_favorable_excursion_session_pct_hindsight",subset),
        })
    save(OUT/(symbol.lower()+"_descriptive_groups.csv"),summary)
    return {"candles":len(rows),"candidate_signals":candidates,
            "accepted_trades":len(records),
            "baseline_net_sum_pct":round(sum(t["net_pnl_pct"] for t in trades),6),
            "groups":summary,
            "trades":[{"entry":r["entry_time"],"outcome":r["outcome_hindsight"],
                       "net":r["baseline_net_pct_hindsight"],
                       "peak_age":r["bars_since_confirmed_high_pivot"],
                       "confirmed_peak_decline":r["signal_decline_from_confirmed_high_pct"],
                       "session_high_age":r["bars_since_session_high"],
                       "session_high_decline":r["signal_decline_from_session_high_pct"],
                       "best_hold_excursion":r["maximum_intrabar_favorable_excursion_hold_pct_hindsight"],
                       "best_session_excursion":r["maximum_intrabar_favorable_excursion_session_pct_hindsight"]}
                      for r in records]}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"experiment":"EXP109","research_only":True,
            "purpose":"Describe whether accepted V16 SHORT entries arrive late relative to already confirmed peaks, and how much downward opportunity remains.",
            "causality":"Confirmed pivots require two right-side completed candles; only pivots confirmed at or before entry signal are used. Session-high is past-only. All subsequent lows and trade outcomes are hindsight.",
            "limitations":[
                "Intrabar high/low excursions are hypothetical extrema, not executable profits.",
                "Session-low-after-entry can occur after trade exit; not a strategy return.",
                "No slippage or gap modeling beyond the original V16 baseline.",
                "Small, previously studied NVDA/AAPL June-August 2026 sample.",
                "No optimized threshold, alternative trading rule, or independent validation.",
                "Summed trade returns are not compounded portfolio performance."
            ],"symbols":{}}
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
    print("EXP109 — CONFIRMED PEAK ENTRY TIMING — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"candles:",s["candles"],"candidates:",s["candidate_signals"],
              "trades:",s["accepted_trades"],"baseline net:",s["baseline_net_sum_pct"])
        for g in s["groups"]:print(" GROUP",g)
        for t in s["trades"]:
            print(" TRADE",t)
    print("\nDetailed files:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
