#!/usr/bin/env python3
"""EXP97 — mountain-aware sideways exits, complete causal strategy reruns.

Research only. Predeclared alternatives:
BASELINE: EXP83 unchanged.
SIDEWAYS_EXIT: EXP93 unchanged.
MOUNTAIN_12: sideways warning + 12-bar upward move and 12-bar close
             in upper half of recent range.
MOUNTAIN_24: same using 24 completed same-session candles.
MOUNTAIN_36: same using 36 completed same-session candles.
These are exploratory hypotheses, NOT fitted to the 10 known events.

The original ST/RSI/stop/session exits remain in every run. Signals use
completed bars and fill at next same-session open. No production changes.
"""
import csv
import json
from collections import Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp93_sideways_research as exp93

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp97_mountain_exit_test"
VARIANTS=("BASELINE","SIDEWAYS_EXIT","MOUNTAIN_12","MOUNTAIN_24","MOUNTAIN_36")
WINDOWS={"MOUNTAIN_12":12,"MOUNTAIN_24":24,"MOUNTAIN_36":36}

def geometry(rows,i,w):
    if i-w+1<0:
        return None
    part=rows[i-w+1:i+1]
    if any(str(r["timestamp"])[:10]!=str(rows[i]["timestamp"])[:10] for r in part):
        return None
    first=float(part[0]["close"])
    last=float(part[-1]["close"])
    high=max(float(r["high"]) for r in part)
    low=min(float(r["low"]) for r in part)
    return {"net_pct":100*(last/first-1),
            "close_position":(last-low)/(high-low) if high>low else 0.5}

def simulate(rows,st,rsi,market,variant):
    if variant=="BASELINE":
        trades,_,_,_,_,_=exp93.simulate(rows,st,rsi,market,"BASELINE")
        return trades,[],Counter()
    if variant=="SIDEWAYS_EXIT":
        trades,_,_,_,events,_=exp93.simulate(rows,st,rsi,market,"SIDEWAYS_EXIT")
        return trades,events,Counter()
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    closes=[float(r["close"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    times=[str(r["timestamp"]) for r in rows]
    n=len(rows)
    sideways=[exp93.is_sideways(exp93.metrics(rows,i)) for i in range(n)]
    w=WINDOWS[variant]
    structures=[geometry(rows,i,w) for i in range(n)]
    pos=None
    pending=None
    trades=[]
    events=[]
    rejected=Counter()
    for i in range(35,n):
        day=times[i][:10]
        if day!=times[i-1][:10]:
            if pos is not None:
                trades.append(exp79.finish(pos,i-1,closes[i-1],"SESSION_END",times))
                pos=None
            pending=None
        exited_at_open=False
        if pending is not None:
            action=pending
            pending=None
            if action=="ENTER" and pos is None:
                pos={"entry_time":times[i],"entry_price":opens[i],
                     "entry_index":i,"lowest_close":opens[i],"last_new_low_i":i}
            elif action!="ENTER" and pos is not None:
                trades.append(exp79.finish(pos,i,opens[i],action,times))
                pos=None
                exited_at_open=True
        if pos is not None:
            stop_price=pos["entry_price"]*(1+exp79.STOP_PCT/100)
            if highs[i]>=stop_price:
                trades.append(exp79.finish(pos,i,max(stop_price,opens[i]),"STOP_LOSS",times))
                pos=None
                pending=None
            else:
                if closes[i]<pos["lowest_close"]:
                    pos["lowest_close"]=closes[i]
                    pos["last_new_low_i"]=i
                if i+1<n and times[i+1][:10]==day:
                    if st[i-1]=="SHORT" and st[i]=="LONG":
                        pending="ST_REVERSE"
                    elif rsi[i] is not None and rsi[i]>=exp79.RSI_LIMIT:
                        pending="RSI_RESCUE"
                    else:
                        armed=(pos["entry_price"]/pos["lowest_close"]-1)*100>exp93.PROFIT_ARM
                        stalled=i-pos["last_new_low_i"]>=exp93.MIN_STALL_BARS
                        two=i>0 and sideways[i] and sideways[i-1]
                        if armed and stalled and two:
                            g=structures[i]
                            if g is not None and g["net_pct"]>0 and g["close_position"]>0.5:
                                pending="MOUNTAIN_EXIT"
                                events.append({"entry_time":pos["entry_time"],
                                               "signal_time":times[i],
                                               "window":w,
                                               "net_pct":round(g["net_pct"],6),
                                               "close_position":round(g["close_position"],6)})
                            else:
                                rejected["SIDEWAYS_WITHOUT_UPWARD_MOUNTAIN_REVERSAL"]+=1
        signal=base.is_major_long_to_short_reversal(highs,lows,closes,market,i) is not None
        if signal:
            if pos is not None or exited_at_open or pending in ("ST_REVERSE","RSI_RESCUE","MOUNTAIN_EXIT"):
                pass
            elif pending=="ENTER":
                pass
            elif st[i]!="LONG":
                pass
            elif i+1>=n or times[i+1][:10]!=day:
                pass
            else:
                pending="ENTER"
    if pos is not None:
        trades.append(exp79.finish(pos,n-1,closes[-1],"DATA_END",times))
    return trades,events,rejected

def summary(trades):
    return {
        "trades":len(trades),
        "winners":sum(t["net_pnl_pct"]>0 for t in trades),
        "losers":sum(t["net_pnl_pct"]<=0 for t in trades),
        "gross_pct_sum":round(sum(t["gross_pnl_pct"] for t in trades),6),
        "commission_pct_sum":round(2*exp79.FEE*len(trades),6),
        "net_pct_sum":round(sum(t["net_pnl_pct"] for t in trades),6),
        "exit_reasons":dict(Counter(t["exit_reason"] for t in trades)),
        "worst_trade_net_pct":round(min((t["net_pnl_pct"] for t in trades),default=0),6),
    }

def save(path,items):
    if not items:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(items[0]))
        w.writeheader()
        w.writerows(items)

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    expected,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    report={}
    baseline_net=None
    for variant in VARIANTS:
        trades,events,rejected=simulate(rows,st,rsi,market,variant)
        if variant=="BASELINE":
            if trades!=expected:
                raise AssertionError(symbol+": EXP83 baseline changed")
            baseline_net=sum(t["net_pnl_pct"] for t in trades)
        if variant=="SIDEWAYS_EXIT":
            # EXP93 invariance is direct, not a trade-subset comparison.
            reference,_,_,_,_,_=exp93.simulate(rows,st,rsi,market,"SIDEWAYS_EXIT")
            if trades!=reference:
                raise AssertionError(symbol+": EXP93 sideways changed")
        save(OUT/f"{symbol.lower()}_{variant.lower()}_trades.csv",trades)
        save(OUT/f"{symbol.lower()}_{variant.lower()}_exit_events.csv",events)
        s=summary(trades)
        s["net_delta_vs_baseline_pp"]=round(sum(t["net_pnl_pct"] for t in trades)-baseline_net,6)
        s["mountain_exit_signals"]=len(events)
        s["sideways_warnings_without_confirmation"]=rejected["SIDEWAYS_WITHOUT_UPWARD_MOUNTAIN_REVERSAL"]
        report[variant]=s
    return {"candles":len(rows),"variants":report}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP97","research_only":True,
        "method":"Full causal V16 SHORT reruns; three predefined mountain confirmation windows.",
        "variants":list(VARIANTS),
        "mountain_rule":"EXP93 sideways/stall/profit warning AND positive net close move over 12/24/36 completed same-session candles AND close above midpoint of that window high-low range.",
        "safety":"Baseline ST/RSI rescue/1.5% stop/session close retained, 0.10% per side commission, no slippage.",
        "limitations":[
            "These windows are exploratory and not out-of-sample validated.",
            "Only NVDA and AAPL June-August 2026, SHORT only.",
            "Sums of trade percentages are not portfolio returns.",
            "No portfolio allocation, LONG test, or slippage.",
            "The 10 known warning events motivated the hypothesis, so in-sample gains would not establish predictive power.",
            "Future independent dates and symbols required before deployment."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP97 — MOUNTAIN CONFIRMATION EXIT — RESEARCH ONLY")
    for symbol,data in report["symbols"].items():
        print("\n"+symbol,"candles:",data["candles"])
        for variant,s in data["variants"].items():
            print(variant,"trades:",s["trades"],"wins:",s["winners"],
                  "losses:",s["losers"],"net:",s["net_pct_sum"],
                  "delta pp:",s["net_delta_vs_baseline_pp"],
                  "exit reasons:",s["exit_reasons"],
                  "warnings rejected:",s["sideways_warnings_without_confirmation"])
    print("\nFiles:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
