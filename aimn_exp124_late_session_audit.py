#!/usr/bin/env python3
"""EXP124: session-boundary and late structural-warning diagnostic.

Read-only research. Reuses EXP121 trade replay and EXP122 signal audit.
No new rules, simulated fills, threshold selection or production edits.
All future observations are explicitly hindsight.
"""
import csv,json
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp117_full_swing_replay as exp117
import aimn_exp121_joint_momentum_replay as exp121

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp124_late_session_audit"
PREV=ROOT/"kiss/results/exp122_joint_signal_audit"

def pct(a,b):
    return round(100*(a/b-1),6) if b else None

def readcsv(p):
    if not p.exists():raise FileNotFoundError("Run EXP122 first: "+str(p))
    with p.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))

def writecsv(p,records,fields):
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(set(times))!=len(times):raise AssertionError("Duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    starts=swing.get_session_starts(times)
    ph,pl,counts=swing.confirmed_pivots(rows,times,starts)
    states=[swing.structure(rows,times,starts,i,ph,pl,counts) for i in range(len(rows))]
    original,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    baseline,_,_,_=exp117.simulate(rows,st,rsi,market,states,"BASELINE")
    if original!=baseline:raise AssertionError(symbol+" baseline parity failure")
    candidate,accepted,_,_,_=exp121.replay(rows,st,rsi,market,states,starts)
    a={t["entry_time"]:t for t in baseline}
    b={t["entry_time"]:t for t in candidate}
    if set(a)!=set(b):raise AssertionError(symbol+" entry set mismatch")
    idx={t:i for i,t in enumerate(times)}
    last_by_day={}
    for i,t in enumerate(times):last_by_day[t[:10]]=i
    warnings=readcsv(PREV/(symbol.lower()+"_all_joint_warnings.csv"))
    accepted_set={(e["entry_time"],e["signal_time"]) for e in accepted}
    records=[]
    for w in warnings:
        entry=w["entry_time"];signal=w["signal_time"];i=idx[signal]
        last=last_by_day[signal[:10]]
        remain=last-i
        baseline_t=a[entry];candidate_t=b[entry]
        baseline_exit_idx=idx[baseline_t["exit_time"]]
        candidate_exit_idx=idx[candidate_t["exit_time"]]
        # Count actual data candles, not assumed exchange closing time.
        after3=i+3 if remain>=3 else None
        after6=i+6 if remain>=6 else None
        # This is only a hypothetical next-open fill; may be preempted by
        # stop/RSI/ST and must not be treated as a replayed trade.
        delay3=i+4 if remain>=4 else None
        delay6=i+7 if remain>=7 else None
        entry_price=float(baseline_t["entry_price"])
        def delayed_net(j):
            return round(100*(entry_price/opens[j]-1)-2*exp79.FEE,6) if j is not None else None
        d3=delayed_net(delay3);d6=delayed_net(delay6)
        records.append({
            "symbol":symbol,"entry_time":entry,"signal_time":signal,
            "exp122_status":w["status"],
            "exp121_signal_accepted":(entry,signal) in accepted_set,
            "signal_w6_pct":w["w6_move_pct"],
            "signal_w12_pct":w["w12_move_pct"],
            "signal_giveback_pp":w["giveback_by_signal_pp"],
            "session_last_candle_time":times[last],
            "candles_remaining_after_signal":remain,
            "minutes_remaining_by_timestamps":
                round((__import__("datetime").datetime.fromisoformat(times[last])-
                       __import__("datetime").datetime.fromisoformat(signal)).total_seconds()/60,3),
            "next_open_same_session_available":remain>=1,
            "three_future_closes_available":remain>=3,
            "three_candle_delay_next_open_available":remain>=4,
            "six_future_closes_available":remain>=6,
            "six_candle_delay_next_open_available":remain>=7,
            "signal_to_last_close_move_pct_hindsight":pct(closes[last],closes[i]),
            "next_1_close_move_pct_hindsight":pct(closes[i+1],closes[i]) if remain>=1 else None,
            "next_3_close_move_pct_hindsight":pct(closes[after3],closes[i]) if after3 is not None else None,
            "next_6_close_move_pct_hindsight":pct(closes[after6],closes[i]) if after6 is not None else None,
            "baseline_exit_time_hindsight":baseline_t["exit_time"],
            "baseline_exit_reason_hindsight":baseline_t["exit_reason"],
            "baseline_net_pct_hindsight":baseline_t["net_pnl_pct"],
            "exp121_exit_time_hindsight":candidate_t["exit_time"],
            "exp121_exit_reason_hindsight":candidate_t["exit_reason"],
            "exp121_net_pct_hindsight":candidate_t["net_pnl_pct"],
            "exp121_delta_vs_baseline_pp_hindsight":
                round(candidate_t["net_pnl_pct"]-baseline_t["net_pnl_pct"],6),
            "hypothetical_delay3_exit_time_hindsight":times[delay3] if delay3 is not None else None,
            "hypothetical_delay3_net_pct_hindsight":d3,
            "hypothetical_delay3_minus_exp121_pp_hindsight":
                round(d3-candidate_t["net_pnl_pct"],6) if d3 is not None else None,
            "hypothetical_delay6_exit_time_hindsight":times[delay6] if delay6 is not None else None,
            "hypothetical_delay6_net_pct_hindsight":d6,
            "hypothetical_delay6_minus_exp121_pp_hindsight":
                round(d6-candidate_t["net_pnl_pct"],6) if d6 is not None else None,
            "baseline_position_active_at_delay3_hindsight":
                delay3 is not None and delay3<=baseline_exit_idx,
            "exp121_position_active_at_delay3_hindsight":
                delay3 is not None and delay3<=candidate_exit_idx,
        })
    fields=list(records[0]) if records else ["symbol","entry_time","signal_time"]
    writecsv(OUT/(symbol.lower()+"_late_session_warnings.csv"),records,fields)
    accepted_rows=[r for r in records if r["exp121_signal_accepted"]]
    writecsv(OUT/(symbol.lower()+"_accepted_late_session.csv"),accepted_rows,fields)
    return {"baseline_trades":len(baseline),"warnings":len(records),
            "accepted_signals":len(accepted_rows),
            "no_three_candle_delay_next_open":sum(not r["three_candle_delay_next_open_available"] for r in records),
            "no_six_candle_delay_next_open":sum(not r["six_candle_delay_next_open_available"] for r in records),
            "warnings_detail":[{
                "entry":r["entry_time"],"signal":r["signal_time"],
                "status":r["exp122_status"],"remaining":r["candles_remaining_after_signal"],
                "w12":r["signal_w12_pct"],
                "to_session_end_pct_hindsight":r["signal_to_last_close_move_pct_hindsight"],
                "delay3_available":r["three_candle_delay_next_open_available"],
                "delta_pp_hindsight":r["exp121_delta_vs_baseline_pp_hindsight"],
            } for r in records]}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP124","research_only":True,
        "scope":"Every EXP122 joint-swing warning in NVDA/AAPL baseline trades.",
        "session_end_definition":"Last timestamp present for each date in input candles, not an assumed exchange close.",
        "delay_definition":"Wait for 3 or 6 additional completed candles, then hypothetical next same-session open; requires 4 or 7 remaining candles.",
        "limitations":[
            "All future movement and delayed prices are hindsight; no delayed strategy replay.",
            "Delay comparisons ignore preemptive stops, RSI, ST and session exits.",
            "Warnings within the same trade are correlated.",
            "Only original in-sample NVDA/AAPL dates; no independent validation.",
            "No new exit restriction or production modification."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP124 — LATE SESSION REVERSAL AUDIT — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n",symbol,"trades:",s["baseline_trades"],
              "warnings:",s["warnings"],"accepted:",s["accepted_signals"],
              "3-bar delay unavailable:",s["no_three_candle_delay_next_open"],
              "6-bar delay unavailable:",s["no_six_candle_delay_next_open"])
        for r in s["warnings_detail"]:
            print(" ",r["entry"],r["signal"],r["status"],
                  "remaining candles:",r["remaining"],
                  "W12:",r["w12"],
                  "session-end move hindsight:",r["to_session_end_pct_hindsight"],
                  "3-bar delayed fill available:",r["delay3_available"],
                  "EXP121 delta pp:",r["delta_pp_hindsight"])
    print("\nReports:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
