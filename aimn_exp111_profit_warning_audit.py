#!/usr/bin/env python3
"""EXP111 — causal warning chronology, winning controls, research only.

No alternative trades or tuned thresholds. For each original V16 trade,
identify first completed close covering round-trip fees, then observe
subsequent rebound and causal ST/RSI/confirmed-swing warnings. All
outcomes and exit comparisons are hindsight. Production unchanged.
"""
import csv,json
from pathlib import Path
from collections import Counter
import aimn_exp83_v16_structural_exit as base
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp79_v16_early_exit as engine

OUT=Path(__file__).resolve().parent/"kiss/results/exp111_profit_warning_audit"
FEE=2*engine.FEE

def write(path,records):
    if not records:return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)

def gross(entry,price):
    return 100*(entry/price-1)

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    idx={t:i for i,t in enumerate(times)}
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    trades,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    starts=swing.get_session_starts(times)
    ph,pl,counts=swing.confirmed_pivots(rows,times,starts)
    detail=[];summary=[]
    for t in trades:
        ei=idx[t["entry_time"]];xi=idx[t["exit_time"]]
        entry=float(t["entry_price"])
        # Stop-loss exits are intrabar and pending ST/RSI exits are next-open.
        # Their exit-bar closes are not observable before exit. Session-end
        # liquidation uses its final close; include that candle.
        end=xi if t["exit_reason"] in ("SESSION_END","DATA_END") else xi-1
        observable=list(range(ei,end+1))
        first=next((i for i in observable if gross(entry,closes[i])>FEE),None)
        if first is None:
            group="NO_FEE_COVERING_CLOSE"
        elif t["net_pnl_pct"]>0:
            group="WINNER_CONTROL"
        else:
            group="LOSING_GIVEBACK"
        best=entry
        first_rebound=None;first_st=None;first_rsi=None
        first_swing_high=None
        for i in observable:
            best=min(best,closes[i])
            if first is None or i<first:continue
            rebound=100*(closes[i]/best-1)
            st_reverse=(i>ei and st[i-1]=="SHORT" and st[i]=="LONG")
            rsi_rescue=(rsi[i] is not None and rsi[i]>=engine.RSI_LIMIT)
            structure=swing.structure(rows,times,starts,i,ph,pl,counts)
            above_high=structure["close_above_last_confirmed_high"]==1
            if first_rebound is None and rebound>0:first_rebound=i
            if first_st is None and st_reverse:first_st=i
            if first_rsi is None and rsi_rescue:first_rsi=i
            if first_swing_high is None and above_high:first_swing_high=i
            detail.append({
                "symbol":symbol,"entry_time":t["entry_time"],"timestamp":times[i],
                "group_hindsight":group,"bars_after_fee_cover":i-first,
                "close":closes[i],"short_gross_close_pct":round(gross(entry,closes[i]),6),
                "hypothetical_net_close_pct":round(gross(entry,closes[i])-FEE,6),
                "best_close_gross_so_far_pct":round(gross(entry,best),6),
                "rebound_from_best_close_pct":round(rebound,6),
                "st":st[i],"st_reverse_at_close":st_reverse,
                "rsi":rsi[i],"rsi_rescue_at_close":rsi_rescue,
                "swing_state":structure["structure_state"],
                "close_above_confirmed_high":structure["close_above_last_confirmed_high"],
                "close_below_confirmed_low":structure["close_below_last_confirmed_low"],
                "exit_time_hindsight":t["exit_time"],"exit_reason_hindsight":t["exit_reason"],
                "actual_net_hindsight":t["net_pnl_pct"],
            })
        summary.append({
            "symbol":symbol,"entry_time":t["entry_time"],"exit_time":t["exit_time"],
            "exit_reason":t["exit_reason"],"net_pct":t["net_pnl_pct"],
            "group_hindsight":group,"first_fee_cover_time":times[first] if first is not None else None,
            "first_fee_cover_gross_pct":round(gross(entry,closes[first]),6) if first is not None else None,
            "first_rebound_time":times[first_rebound] if first_rebound is not None else None,
            "first_st_reverse_time":times[first_st] if first_st is not None else None,
            "first_rsi_rescue_time":times[first_rsi] if first_rsi is not None else None,
            "first_close_above_confirmed_high_time":times[first_swing_high] if first_swing_high is not None else None,
            "observed_bars_after_fee_cover":len([i for i in observable if first is not None and i>=first]),
        })
    write(OUT/(symbol.lower()+"_all_trade_summary.csv"),summary)
    write(OUT/(symbol.lower()+"_post_fee_cover_candles.csv"),detail)
    counts=Counter(r["group_hindsight"] for r in summary)
    return {"trades":len(trades),"baseline_net_sum_pct":round(sum(t["net_pnl_pct"] for t in trades),6),
            "groups":dict(counts),"records":summary}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP111","research_only":True,
        "fee_cover_gross_pct":FEE,
        "objective":"Compare causal warning chronology for losing givebacks and winning controls, without fitting an exit.",
        "method":"Observe completed closes from entry until the original fill; exclude exit bar for next-open and stop exits. Record ST, RSI, confirmed swing, first rebound after fee-cover.",
        "limitations":[
            "First positive rebound is descriptive, not a threshold or validated exit trigger.",
            "ST and RSI events are computed at completed candle close, executable no earlier than next open.",
            "Confirmed pivots require two completed right-side bars.",
            "Close-price profit is not an executable next-open fill.",
            "Session-end final close is included as observable at liquidation, not as an earlier opportunity.",
            "No alternate exits, threshold optimization, holdout, slippage, or profitability claim.",
            "Sample is the same previously studied NVDA/AAPL candles."
        ],"symbols":{}}
    for symbol,path in base.DATA.items():report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
    print("EXP111 — PROFIT WARNING CHRONOLOGY WITH WINNER CONTROLS — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"trades:",s["trades"],"net:",s["baseline_net_sum_pct"],"groups:",s["groups"])
        for r in s["records"]:
            print(" TRADE",r["entry_time"],r["group_hindsight"],
                  "net:",r["net_pct"],"first_fee:",r["first_fee_cover_time"],
                  "first_rebound:",r["first_rebound_time"],
                  "ST:",r["first_st_reverse_time"],
                  "RSI:",r["first_rsi_rescue_time"],
                  "confirmed_high_break:",r["first_close_above_confirmed_high_time"],
                  "exit:",r["exit_reason"],r["exit_time"])
    print("\nDetailed CSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
