#!/usr/bin/env python3
"""EXP118 — explain all changed EXP117 exits without choosing a new rule.

Recompute EXP83 baseline and EXP117 chronological candidate. For each changed
matched entry, inspect only completed candles through the candidate signal,
and separately label future outcomes as hindsight. Research only.
"""
import csv,json
from collections import Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp117_full_swing_replay as exp117

OUT=Path(__file__).resolve().parent/"kiss/results/exp118_changed_exit_audit"

def write(path,items):
    if not items:return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(items[0]))
        w.writeheader();w.writerows(items)

def pct(a,b):
    return round(100*(a/b-1),6) if b else None

def short_gross(entry,price):
    return round(100*(entry/price-1),6)

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    index={t:i for i,t in enumerate(times)}
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    starts=swing.get_session_starts(times)
    ph,pl,counts=swing.confirmed_pivots(rows,times,starts)
    states=[swing.structure(rows,times,starts,i,ph,pl,counts)
            for i in range(len(rows))]
    reference,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    baseline,_,_,_=exp117.simulate(rows,st,rsi,market,states,"BASELINE")
    if reference!=baseline:raise AssertionError(symbol+" baseline parity failure")
    candidate,events,_,_=exp117.simulate(rows,st,rsi,market,states,"JOINT_SWING")
    b={t["entry_time"]:t for t in baseline}
    c={t["entry_time"]:t for t in candidate}
    if set(b)!=set(c):raise AssertionError(symbol+" changed entry set; review before comparison")
    e={v["entry_time"]:v for v in events}
    changed=[];paths=[]
    for entry in sorted(b):
        a=b[entry];z=c[entry]
        if (a["exit_time"],a["exit_price"],a["exit_reason"])==(
            z["exit_time"],z["exit_price"],z["exit_reason"]):
            continue
        if entry not in e:raise AssertionError(symbol+" changed exit missing structural event "+entry)
        ev=e[entry]
        ei=index[entry];si=index[ev["signal_time"]];ci=index[z["exit_time"]]
        bi=index[a["exit_time"]]
        if not (ei<=si<ci<=bi):raise AssertionError("Unexpected exit chronology "+entry)
        entry_price=float(a["entry_price"])
        # Information available as of the signal close only.
        pre=closes[ei:si+1]
        min_close=min([entry_price]+pre)
        best_i=min(range(ei,si+1),key=lambda j:closes[j])
        first_fee=next((i for i in range(ei,si+1)
                        if short_gross(entry_price,closes[i])>2*exp79.FEE),None)
        state=states[si]
        latest_high=state["latest_high_price"]
        latest_low=state["latest_low_price"]
        delta=round(z["net_pnl_pct"]-a["net_pnl_pct"],6)
        changed.append({
            "symbol":symbol,"entry_time":entry,
            "entry_price":entry_price,
            "baseline_exit_time_hindsight":a["exit_time"],
            "baseline_exit_reason_hindsight":a["exit_reason"],
            "baseline_exit_price_hindsight":a["exit_price"],
            "baseline_net_pct_hindsight":a["net_pnl_pct"],
            "candidate_signal_time":ev["signal_time"],
            "candidate_exit_time":z["exit_time"],
            "candidate_exit_price":z["exit_price"],
            "candidate_net_pct":z["net_pnl_pct"],
            "net_delta_pp_hindsight":delta,
            "effect_hindsight":"HELPED" if delta>0 else "HURT" if delta<0 else "UNCHANGED",
            "baseline_winner_hindsight":a["net_pnl_pct"]>0,
            "candidate_winner":z["net_pnl_pct"]>0,
            "bars_from_entry_to_signal":si-ei,
            "bars_from_signal_to_baseline_exit_hindsight":bi-si,
            "first_fee_cover_time":times[first_fee] if first_fee is not None else None,
            "bars_since_first_fee_cover":si-first_fee if first_fee is not None else None,
            "best_close_time_through_signal":times[best_i],
            "best_close_short_gross_pct_through_signal":short_gross(entry_price,min_close),
            "signal_close_short_gross_pct":short_gross(entry_price,closes[si]),
            "signal_close_net_if_filled_at_close_pct":
                round(short_gross(entry_price,closes[si])-2*exp79.FEE,6),
            "giveback_from_best_close_to_signal_pp":
                round(short_gross(entry_price,min_close)-
                      short_gross(entry_price,closes[si]),6),
            "candidate_net_vs_best_close_gross_pp":
                round(short_gross(entry_price,min_close)-z["gross_pnl_pct"],6),
            "signal_close_above_latest_confirmed_high":
                state["close_above_last_confirmed_high"],
            "latest_confirmed_high_price":latest_high,
            "latest_confirmed_high_time":state["latest_high_confirmed_time"],
            "latest_confirmed_low_price":latest_low,
            "latest_confirmed_low_time":state["latest_low_confirmed_time"],
            "high_sequence":state["high_sequence"],
            "low_sequence":state["low_sequence"],
            "structure_state":state["structure_state"],
            "signal_close_to_confirmed_high_pct":pct(closes[si],latest_high),
            "signal_close_to_confirmed_low_pct":pct(closes[si],latest_low),
            "rsi_at_signal":round(float(rsi[si]),6) if rsi[si] is not None else None,
            "supertrend_at_signal":st[si],
            "w12_close_move_pct":state["w12_net_close_move_pct"],
            "w12_close_position":state["w12_close_position"],
            "w24_close_move_pct":state["w24_net_close_move_pct"],
            "w24_close_position":state["w24_close_position"],
        })
        # Only completed closes through signal; baseline later path is
        # separately included as hindsight for visual research.
        for i in range(ei,bi+1):
            phase=("AT_ENTRY" if i==ei else
                   "PRE_SIGNAL" if i<si else
                   "SIGNAL" if i==si else
                   "AFTER_SIGNAL_HINDSIGHT")
            paths.append({
                "symbol":symbol,"entry_time":entry,"time":times[i],
                "phase":phase,"bar_index_since_entry":i-ei,
                "open":rows[i]["open"],"high":rows[i]["high"],
                "low":rows[i]["low"],"close":rows[i]["close"],
                "short_gross_at_close_pct":short_gross(entry_price,closes[i]),
                "st":st[i],"rsi":round(float(rsi[i]),6) if rsi[i] is not None else None,
                "candidate_signal_time":ev["signal_time"],
                "candidate_exit_time":z["exit_time"],
                "baseline_exit_time_hindsight":a["exit_time"],
            })
    write(OUT/(symbol.lower()+"_changed_exits.csv"),changed)
    write(OUT/(symbol.lower()+"_changed_exit_paths.csv"),paths)
    helped=[x for x in changed if x["effect_hindsight"]=="HELPED"]
    hurt=[x for x in changed if x["effect_hindsight"]=="HURT"]
    return {
        "baseline_trades":len(baseline),"candidate_trades":len(candidate),
        "baseline_net_pct_sum":round(sum(x["net_pnl_pct"] for x in baseline),6),
        "candidate_net_pct_sum":round(sum(x["net_pnl_pct"] for x in candidate),6),
        "changed_exit_count":len(changed),
        "helped_count":len(helped),"hurt_count":len(hurt),
        "helped_sum_delta_pp":round(sum(x["net_delta_pp_hindsight"] for x in helped),6),
        "hurt_sum_delta_pp":round(sum(x["net_delta_pp_hindsight"] for x in hurt),6),
        "changed_exit_total_delta_pp":round(sum(x["net_delta_pp_hindsight"] for x in changed),6),
        "changed_exits":changed,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP118","research_only":True,
        "purpose":"Explain seven changed exits in EXP117, not develop or fit an exit rule.",
        "causality":"Signal features computed from completed candles at or before signal; later baseline exits labeled hindsight.",
        "limitations":[
            "Only the seven previously observed changed trades; no holdout.",
            "The structural rule was selected after examining earlier experiments.",
            "Best close through signal is diagnostic, not an executable price.",
            "Candidate exit is next open; signal-close profit is hypothetical only.",
            "Future baseline path is for explanation, never signal generation.",
            "No slippage, short borrow cost, compounding, or LONG trades.",
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP118 — SEVEN CHANGED EXIT DIAGNOSTIC — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n",symbol,"changed:",s["changed_exit_count"],
              "helped:",s["helped_count"],"hurt:",s["hurt_count"],
              "helped sum:",s["helped_sum_delta_pp"],
              "hurt sum:",s["hurt_sum_delta_pp"],
              "total delta pp:",s["changed_exit_total_delta_pp"])
        for x in s["changed_exits"]:
            print(" ",x["entry_time"],x["effect_hindsight"],
                  "delta:",x["net_delta_pp_hindsight"],
                  "baseline:",x["baseline_net_pct_hindsight"],
                  "candidate:",x["candidate_net_pct"],
                  "signal:",x["candidate_signal_time"],
                  "best gross by signal:",x["best_close_short_gross_pct_through_signal"],
                  "giveback at signal:",x["giveback_from_best_close_to_signal_pp"],
                  "w12 move:",x["w12_close_move_pct"],
                  "w24 move:",x["w24_close_move_pct"])
    print("\nDetailed CSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
