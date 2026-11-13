#!/usr/bin/env python3
"""EXP123 — signal persistence and delayed-exit opportunity audit.

Research only. Uses EXP122's signal universe; measures 1/3/6-candle
persistence, next-open hypothetical short exits and their opportunity cost.
No live/replayed strategy changes. All post-signal measures are hindsight.
"""
import csv,json
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp122_joint_signal_audit as exp122

OUT=Path(__file__).resolve().parent/"kiss/results/exp123_signal_persistence"
SRC=exp122.OUT
HORIZONS=(1,3,6)
FIELDS=("symbol","entry_time","signal_time","status",
        "baseline_net_pct_hindsight","exp121_delta_vs_baseline_pp_hindsight",
        "w6_at_signal","w12_at_signal","signal_giveback_pp",
        "horizon_bars","future_close_time_hindsight",
        "future_close_move_pct_hindsight","future_up_closes_count_hindsight",
        "future_close_above_signal_count_hindsight",
        "future_closes_above_signal_high_count_hindsight",
        "all_future_closes_above_signal_close_hindsight",
        "future_close_above_signal_close_hindsight",
        "same_session_next_open_after_horizon",
        "hypothetical_delayed_exit_time_hindsight",
        "hypothetical_delayed_exit_net_pct_hindsight",
        "hypothetical_delay_minus_exp121_net_pp_hindsight",
        "hypothetical_delay_minus_baseline_net_pp_hindsight",
        "baseline_position_still_open_at_delayed_exit_hindsight",
        "exp121_position_still_open_at_delayed_exit_hindsight",
        "warning_not_independent")

def write(path,items):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        w.writeheader();w.writerows(items)

def pct(a,b):
    return round(100*(a/b-1),6) if b else None

def evaluate(symbol,path):
    source=SRC/(symbol.lower()+"_all_joint_warnings.csv")
    if not source.exists():
        raise FileNotFoundError("Run EXP122 first: "+str(source))
    with source.open(encoding="utf-8",newline="") as f:
        signals=list(csv.DictReader(f))
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    index={t:i for i,t in enumerate(times)}
    if len(index)!=len(times):raise AssertionError("Duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    results=[]
    for sig in signals:
        i=index[sig["signal_time"]]
        ei=index[sig["entry_time"]]
        entry_price=opens[ei]
        # Entry price is the next-open entry used in the baseline; the
        # baseline trade file is used to validate exact modeled fill.
        baseline_path=Path(__file__).resolve().parent/"kiss/results/exp121_joint_momentum_replay"/(symbol.lower()+"_baseline.csv")
        candidate_path=Path(__file__).resolve().parent/"kiss/results/exp121_joint_momentum_replay"/(symbol.lower()+"_exp121.csv")
        if not baseline_path.exists() or not candidate_path.exists():
            raise FileNotFoundError("Run EXP121 first")
        with baseline_path.open(encoding="utf-8",newline="") as f:
            baseline={r["entry_time"]:r for r in csv.DictReader(f)}
        with candidate_path.open(encoding="utf-8",newline="") as f:
            candidate={r["entry_time"]:r for r in csv.DictReader(f)}
        bt=baseline[sig["entry_time"]];ct=candidate[sig["entry_time"]]
        entry_price=float(bt["entry_price"])
        if abs(entry_price-opens[ei])>1e-6:
            raise AssertionError("Entry fill mismatch")
        for h in HORIZONS:
            j=i+h
            if j>=len(rows) or times[j][:10]!=times[i][:10]:
                continue
            future=closes[i+1:j+1]
            same_next=j+1<len(rows) and times[j+1][:10]==times[i][:10]
            delayed_time=times[j+1] if same_next else None
            delayed_net=(100*(entry_price/opens[j+1]-1)-0.2) if same_next else None
            results.append({
                "symbol":symbol,"entry_time":sig["entry_time"],
                "signal_time":sig["signal_time"],"status":sig["status"],
                "baseline_net_pct_hindsight":float(bt["net_pnl_pct"]),
                "exp121_delta_vs_baseline_pp_hindsight":
                    round(float(ct["net_pnl_pct"])-float(bt["net_pnl_pct"]),6),
                "w6_at_signal":sig["w6_move_pct"],
                "w12_at_signal":sig["w12_move_pct"],
                "signal_giveback_pp":sig["giveback_by_signal_pp"],
                "horizon_bars":h,
                "future_close_time_hindsight":times[j],
                "future_close_move_pct_hindsight":pct(closes[j],closes[i]),
                "future_up_closes_count_hindsight":
                    sum(closes[k]>closes[k-1] for k in range(i+1,j+1)),
                "future_close_above_signal_count_hindsight":
                    sum(closes[k]>closes[i] for k in range(i+1,j+1)),
                "future_closes_above_signal_high_count_hindsight":
                    sum(closes[k]>highs[i] for k in range(i+1,j+1)),
                "all_future_closes_above_signal_close_hindsight":
                    all(x>closes[i] for x in future),
                "future_close_above_signal_close_hindsight":closes[j]>closes[i],
                "same_session_next_open_after_horizon":same_next,
                "hypothetical_delayed_exit_time_hindsight":delayed_time,
                "hypothetical_delayed_exit_net_pct_hindsight":
                    round(delayed_net,6) if delayed_net is not None else None,
                "hypothetical_delay_minus_exp121_net_pp_hindsight":
                    round(delayed_net-float(ct["net_pnl_pct"]),6)
                    if delayed_net is not None else None,
                "hypothetical_delay_minus_baseline_net_pp_hindsight":
                    round(delayed_net-float(bt["net_pnl_pct"]),6)
                    if delayed_net is not None else None,
                "baseline_position_still_open_at_delayed_exit_hindsight":
                    delayed_time is not None and delayed_time<=bt["exit_time"],
                "exp121_position_still_open_at_delayed_exit_hindsight":
                    delayed_time is not None and delayed_time<=ct["exit_time"],
                "warning_not_independent":True,
            })
    write(OUT/(symbol.lower()+"_signal_persistence.csv"),results)
    summary={}
    for h in HORIZONS:
        group=[r for r in results if r["horizon_bars"]==h]
        summary[str(h)]={
            "signals_with_horizon":len(group),
            "positive_future_close_move":
                sum(r["future_close_move_pct_hindsight"]>0 for r in group),
            "negative_or_flat_future_close_move":
                sum(r["future_close_move_pct_hindsight"]<=0 for r in group),
            "all_future_closes_above_signal":
                sum(r["all_future_closes_above_signal_close_hindsight"] for r in group),
            "hypothetical_delayed_next_open_available":
                sum(r["same_session_next_open_after_horizon"] for r in group),
        }
    print("\n",symbol,"source warnings:",len(signals))
    for r in results:
        if r["horizon_bars"]==3:
            print(" ",r["entry_time"],r["signal_time"],r["status"],
                  "3-bar future %:",r["future_close_move_pct_hindsight"],
                  "up bars:",r["future_up_closes_count_hindsight"],
                  "above signal close:",r["future_close_above_signal_count_hindsight"],
                  "delay minus EXP121 pp:",r["hypothetical_delay_minus_exp121_net_pp_hindsight"])
    return {"warnings":len(signals),"horizon_summary":summary}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP123","research_only":True,
        "goal":"Characterize 1/3/6-bar post-signal persistence and hypothetical delay costs.",
        "causal_vs_hindsight":"W6/W12 and giveback at the original signal are causal; every future and delayed-exit field is hindsight.",
        "execution_warning":"Hypothetical delayed exits are not a chronological strategy replay. Existing stop, RSI, ST, and session-end exits can preempt them.",
        "limitations":[
            "Same selected EXP122 warnings; no independent validation.",
            "Repeated warnings on one trade are correlated.",
            "Future persistence cannot be known at the original signal.",
            "Next-open delayed-exit comparisons do not model competing safety exits.",
            "No thresholds optimized or production code changed.",
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=evaluate(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("\nFiles:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
