#!/usr/bin/env python3
"""EXP77: causal V15/V16/V17 SHORT entries, EXP53 ST SHORT->LONG exits.
Research only; does not place orders or modify existing trading engines.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"kiss"))
from kiss_exp53_supertrend import calculate_supertrend
from exp74_kiss_hybrid_engine import (get_market_state,is_short_peak_reversal,
    is_major_long_to_short_reversal,is_early_v_short,rsi_wilder)

DATA=ROOT/"kiss/visual_research/aimn_nvda_candles.json"
OUT=ROOT/"kiss/results/exp77_early_entry_st_exit"
MODES=("V15","V16","V17")
FEE=0.10
STOP=1.5
RSI_RESCUE=80

def experiment(rows,mode):
    st=calculate_supertrend(rows,atr_period=10,multiplier=3.0)
    states=st["st_trend"].tolist()
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    times=[str(r["timestamp"]) for r in rows]
    market=[get_market_state(closes,i) for i in range(len(rows))]
    rsis=rsi_wilder(closes)
    records=[]
    missed=[]
    active=None
    pending=None
    candidates=0
    # Signal at candle close, execute at next candle open.
    for i in range(35,len(rows)):
        day=times[i][:10]
        if active is not None and day!=active["day"]:
            # This is a no-overnight experiment; compare ST exits separately.
            j=i-1
            records.append(close_trade(active,times[j],closes[j],"SESSION_END"))
            active=None
            pending=None
        if pending:
            action=pending
            pending=None
            if action=="ENTER" and active is None:
                active={"entry_time":times[i],"entry_price":opens[i],"day":day,
                        "entry_index":i}
            elif action=="ST_REVERSE" and active is not None:
                records.append(close_trade(active,times[i],opens[i],"ST_REVERSE"))
                active=None
            elif action=="RSI_RESCUE" and active is not None:
                records.append(close_trade(active,times[i],opens[i],"RSI_RESCUE"))
                active=None
        if active is not None:
            stop=active["entry_price"]*(1+STOP/100)
            if highs[i]>=stop:
                records.append(close_trade(active,times[i],max(stop,opens[i]),"STOP_LOSS"))
                active=None
                pending=None
            elif states[i-1]=="SHORT" and states[i]=="LONG":
                pending="ST_REVERSE"
            elif rsis[i] is not None and rsis[i]>=RSI_RESCUE:
                pending="RSI_RESCUE"
        if mode=="V15":
            signal=is_short_peak_reversal(highs,lows,closes,market,i)
        elif mode=="V16":
            signal=is_major_long_to_short_reversal(highs,lows,closes,market,i) is not None
        else:
            signal=is_early_v_short(highs,opens,closes,market,i) is not None
        if signal:
            candidates+=1
            reason=None
            if active is not None or pending in ("ST_REVERSE","RSI_RESCUE"):
                reason="ALREADY_IN_TRADE"
            elif pending=="ENTER":
                reason="ENTRY_ALREADY_QUEUED"
            elif states[i]!="LONG":
                reason="ST_NOT_LONG_AT_SIGNAL"
            elif i+1>=len(rows):
                reason="DATA_END"
            elif times[i+1][:10]!=day:
                reason="SESSION_END"
            else:
                pending="ENTER"
            if reason:
                missed.append(dict(time=times[i],mode=mode,reason=reason,
                                   close=closes[i],st_state=states[i]))
        if i+1<len(rows) and times[i+1][:10]!=day:
            # Do not queue an order across sessions.
            pending=None
    if active:
        records.append(close_trade(active,times[-1],closes[-1],"DATA_END"))
    return records,missed,candidates

def close_trade(active,when,price,reason):
    gross=(active["entry_price"]/price-1)*100
    return dict(entry_time=active["entry_time"],exit_time=when,
                entry_price=round(active["entry_price"],6),
                exit_price=round(price,6),exit_reason=reason,
                gross_pnl_pct=round(gross,6),
                net_pnl_pct=round(gross-2*FEE,6))

def write_csv(path,records,fields):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(records)

def main():
    rows=json.loads(DATA.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:r["timestamp"])
    OUT.mkdir(parents=True,exist_ok=True)
    summaries={}
    for mode in MODES:
        trades,missed,candidates=experiment(rows,mode)
        write_csv(OUT/(mode.lower()+"_trades.csv"),trades,
                  ["entry_time","exit_time","entry_price","exit_price",
                   "exit_reason","gross_pnl_pct","net_pnl_pct"])
        write_csv(OUT/(mode.lower()+"_missed_signals.csv"),missed,
                  ["time","mode","reason","close","st_state"])
        summaries[mode]=dict(candidates=candidates,trades=len(trades),
             winners=sum(t["net_pnl_pct"]>0 for t in trades),
             losers=sum(t["net_pnl_pct"]<=0 for t in trades),
             gross_pct_sum=round(sum(t["gross_pnl_pct"] for t in trades),3),
             net_pct_sum=round(sum(t["net_pnl_pct"] for t in trades),3),
             exits=dict(Counter(t["exit_reason"] for t in trades)),
             rejected_signals=dict(Counter(x["reason"] for x in missed)))
    result=dict(experiment="EXP77",symbol="NVDA",direction="SHORT",
        candles=len(rows),commission_per_side_pct=FEE,
        stop_loss_pct=STOP,rsi_rescue=RSI_RESCUE,
        assumptions="V15/V16/V17 causal close signals; next open fill; ST(10,3) SHORT->LONG exits; no overnight; no early-profit exit",
        results=summaries)
    (OUT/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
    print("Reports:",OUT)

if __name__=="__main__":
    main()
