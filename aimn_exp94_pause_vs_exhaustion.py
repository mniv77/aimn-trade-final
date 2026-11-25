#!/usr/bin/env python3
"""EXP94 — Sideways SHORT exit: pause versus exhaustion audit.

RESEARCH ONLY. Replays unchanged EXP93 BASELINE and SIDEWAYS_EXIT variants,
matches trades by identical entry timestamp, and examines price action after
the proposed sideways exit until the original baseline exit.

Hindsight observations are explicitly NOT trading signals. A future low/high
is not assumed executable. Entry/exit comparisons use recorded fills, fees,
and next-open exit mechanics of EXP93. No production modifications.
"""
import csv
import json
from pathlib import Path

import aimn_exp83_v16_structural_exit as base
import aimn_exp93_sideways_research as exp93

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "kiss/results/exp94_pause_vs_exhaustion"

def r6(x):
    return round(float(x),6) if x is not None else None

def write_csv(path, records):
    if not records:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    index={t:i for i,t in enumerate(times)}
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    original,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    baseline,_,_,_,_,_=exp93.simulate(rows,st,rsi,market,"BASELINE")
    if baseline != original:
        raise AssertionError(symbol+": EXP93 baseline differs from EXP83")
    candidate,_,_,_,events,_=exp93.simulate(rows,st,rsi,market,"SIDEWAYS_EXIT")
    baseline_by_entry={t["entry_time"]:t for t in baseline}
    candidate_by_entry={t["entry_time"]:t for t in candidate}
    if set(baseline_by_entry)!=set(candidate_by_entry):
        raise AssertionError(symbol+": entry sets changed; cannot make paired attribution")
    event_by_entry={e["entry_time"]:e for e in events}
    details=[]
    for entry_time,event in event_by_entry.items():
        a=baseline_by_entry[entry_time]
        b=candidate_by_entry[entry_time]
        if b["exit_reason"]!="SIDEWAYS_EXIT":
            raise AssertionError("Sideways event did not produce sideways exit: "+entry_time)
        exit_i=index[b["exit_time"]]
        base_exit_i=index[a["exit_time"]]
        if base_exit_i < exit_i:
            raise AssertionError("Baseline exit preceded sideways exit: "+entry_time)
        # This is retrospective diagnostic only, using completed candles after
        # the proposed exit through the original baseline exit, inclusive.
        follow=rows[exit_i:base_exit_i+1]
        low=min(float(r["low"]) for r in follow)
        high=max(float(r["high"]) for r in follow)
        p=float(b["exit_price"])
        continuation=100*(p/low-1)
        rebound=100*(high/p-1)
        # Price changes over follow-up path are not executable profits.
        saved=b["net_pnl_pct"]-a["net_pnl_pct"]
        if saved>0:
            label="EXIT_HELPED"
        elif saved<0:
            label="EXIT_HURT"
        else:
            label="NO_DIFFERENCE"
        signal_i=index[event["signal_time"]]
        record={
            "symbol":symbol,
            "entry_time":entry_time,
            "sideways_signal_time":event["signal_time"],
            "sideways_exit_time":b["exit_time"],
            "baseline_exit_time":a["exit_time"],
            "baseline_exit_reason":a["exit_reason"],
            "baseline_net_pct":a["net_pnl_pct"],
            "sideways_net_pct":b["net_pnl_pct"],
            "sideways_minus_baseline_pp":r6(saved),
            "outcome":label,
            "bars_from_sideways_exit_to_baseline_exit":base_exit_i-exit_i,
            "best_later_decline_from_sideways_exit_pct":r6(continuation),
            "worst_later_rebound_from_sideways_exit_pct":r6(rebound),
            "best_close_short_at_signal_pct":event["gross_best_close_pct"],
            "efficiency_at_signal":event["efficiency"],
            "displacement_fraction_at_signal":event["displacement_fraction"],
            "signal_close":r6(closes[signal_i]),
            "sideways_exit_price":b["exit_price"],
            "baseline_exit_price":a["exit_price"],
        }
        details.append(record)
    details.sort(key=lambda x:x["sideways_signal_time"])
    write_csv(OUT/f"{symbol.lower()}_sideways_event_audit.csv",details)
    write_csv(OUT/f"{symbol.lower()}_baseline_trades.csv",baseline)
    write_csv(OUT/f"{symbol.lower()}_sideways_exit_trades.csv",candidate)
    changed=[t for t in details if t["sideways_minus_baseline_pp"]!=0]
    return {
        "baseline_trades":len(baseline),
        "sideways_exit_trades":len(candidate),
        "sideways_exit_events":len(details),
        "exit_helped":sum(t["outcome"]=="EXIT_HELPED" for t in details),
        "exit_hurt":sum(t["outcome"]=="EXIT_HURT" for t in details),
        "unchanged":sum(t["outcome"]=="NO_DIFFERENCE" for t in details),
        "sum_event_delta_pp":r6(sum(t["sideways_minus_baseline_pp"] for t in details)),
        "full_strategy_baseline_net_pct":r6(sum(t["net_pnl_pct"] for t in baseline)),
        "full_strategy_sideways_net_pct":r6(sum(t["net_pnl_pct"] for t in candidate)),
        "full_strategy_delta_pp":r6(sum(t["net_pnl_pct"] for t in candidate)-sum(t["net_pnl_pct"] for t in baseline)),
        "events":details,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP94",
        "research_only":True,
        "purpose":"Identify which EXP93 sideways exits saved or sacrificed realized net trade return versus original V16/ST baseline.",
        "notes":[
            "Both variants fully rerun with completed-candle signals, next-open fills, 0.10% fee each side and unchanged stop/RSI/ST/session handling.",
            "Paired comparisons are valid only because entry sets are asserted identical.",
            "Subsequent lows/highs are hindsight diagnostics, NOT executable outcomes or entry signals.",
            "A sideways exit helping or hurting a past trade is not a predictive classifier.",
            "Only NVDA/AAPL SHORT historical samples; no portfolio reallocation or LONG strategy.",
            "Percentage-point sums are not compounded account returns; slippage excluded."
        ],
        "symbols":{},
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP94 — SIDEWAYS PAUSE VS EXHAUSTION — RESEARCH ONLY")
    for symbol,data in report["symbols"].items():
        print("\n",symbol,
              "baseline net:",data["full_strategy_baseline_net_pct"],
              "sideways net:",data["full_strategy_sideways_net_pct"],
              "delta pp:",data["full_strategy_delta_pp"])
        print("sideways exits:",data["sideways_exit_events"],
              "helped:",data["exit_helped"],
              "hurt:",data["exit_hurt"])
        for e in data["events"]:
            print(" ",e["entry_time"],"signal:",e["sideways_signal_time"],
                  "delta pp:",e["sideways_minus_baseline_pp"],
                  "outcome:",e["outcome"],
                  "later decline:",e["best_later_decline_from_sideways_exit_pct"],
                  "later rebound:",e["worst_later_rebound_from_sideways_exit_pct"],
                  "baseline exit:",e["baseline_exit_reason"])
    print("\nCSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
