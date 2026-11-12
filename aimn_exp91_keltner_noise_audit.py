#!/usr/bin/env python3
"""EXP91 — Keltner Channel V16 SHORT noise diagnostic (research only).

Uses unchanged EXP83 V16/ST baseline trades on NVDA and AAPL.
At each completed V16 signal calculate EMA(20) of typical price and
Wilder ATR(10), Keltner envelopes +/-2 ATR. Outputs location relative to
EMA and bands, normalized channel distance, and descriptive group audits.
No filter is installed. Retained trade subsets are NOT new-system P&L.
"""
import csv
import json
from pathlib import Path
import aimn_exp83_v16_structural_exit as exp83

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp91_keltner_noise_audit"
EMA_PERIOD=20
ATR_PERIOD=10
MULT=2.0

def indicators(rows):
    n=len(rows)
    mid=[None]*n
    atr=[None]*n
    if n<max(EMA_PERIOD,ATR_PERIOD):return mid,atr
    tp=[(float(r["high"])+float(r["low"])+float(r["close"]))/3.0 for r in rows]
    seed=sum(tp[:EMA_PERIOD])/EMA_PERIOD
    mid[EMA_PERIOD-1]=seed
    alpha=2/(EMA_PERIOD+1)
    for i in range(EMA_PERIOD,n):
        seed=alpha*tp[i]+(1-alpha)*seed
        mid[i]=seed
    tr=[]
    for i,r in enumerate(rows):
        high=float(r["high"]);low=float(r["low"])
        pc=float(rows[i-1]["close"]) if i else None
        tr.append(max(high-low,abs(high-pc),abs(low-pc)) if pc is not None else high-low)
    smooth=sum(tr[:ATR_PERIOD])/ATR_PERIOD
    atr[ATR_PERIOD-1]=smooth
    for i in range(ATR_PERIOD,n):
        smooth=((ATR_PERIOD-1)*smooth+tr[i])/ATR_PERIOD
        atr[i]=smooth
    return mid,atr

def stats(trades):
    return {"trades":len(trades),
      "winners":sum(r["winner"] for r in trades),
      "losers":sum(not r["winner"] for r in trades),
      "sum_original_net_trade_pct":round(sum(r["net_trade_pct"] for r in trades),5)}

def write_csv(path,records):
    if not records:return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader();w.writerows(records)

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(set(times))!=len(times):raise ValueError("Duplicate timestamp")
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    st=exp83.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=exp83.rsi_wilder(closes)
    market=[exp83.get_market_state(closes,i) for i in range(len(rows))]
    trades,candidates,rejected,blocked=exp83.simulate(rows,st,rsi,market,None,False)
    if blocked:raise ValueError("Baseline structure gates unexpectedly active")
    mid,atr=indicators(rows)
    trade_by_entry={t["entry_time"]:t for t in trades}
    records=[]
    for i in range(35,len(rows)):
        if exp83.is_major_long_to_short_reversal(highs,lows,closes,market,i) is None:
            continue
        nt=times[i+1] if i+1<len(rows) else None
        t=trade_by_entry.get(nt) if nt and nt[:10]==times[i][:10] else None
        m=mid[i];a=atr[i];close=closes[i]
        norm=(close-m)/a if a and a>0 and m is not None else None
        category=("UNAVAILABLE" if norm is None else
           "BELOW_LOWER_2ATR" if norm< -MULT else
           "LOWER_HALF_CHANNEL" if norm<0 else
           "UPPER_HALF_CHANNEL" if norm<=MULT else
           "ABOVE_UPPER_2ATR")
        records.append({
          "symbol":symbol,"signal_time":times[i],
          "entry_time":t["entry_time"] if t else "",
          "accepted_baseline":t is not None,
          "baseline_winner":t["net_pnl_pct"]>0 if t else "",
          "baseline_net_pct":float(t["net_pnl_pct"]) if t else "",
          "channel_mid":round(m,5) if m is not None else "",
          "ATR10":round(a,5) if a is not None else "",
          "signal_close":round(close,5),
          "distance_from_ema_in_ATR":round(norm,5) if norm is not None else "",
          "channel_category":category,
          "within_channel":norm is not None and -MULT<=norm<=MULT,
          "below_ema":norm is not None and norm<0,
          "below_lower_band":norm is not None and norm<-MULT,
          "EMA20_slope_last_3_bars_in_ATR":round((m-mid[i-3])/a,5) if m is not None and i>=3 and mid[i-3] is not None and a and a>0 else "",
        })
    accepted=[r for r in records if r["accepted_baseline"]]
    if len(records)!=candidates or len(accepted)!=len(trades):
        raise ValueError(f"{symbol}: signal/trade mapping disagrees with baseline")
    for r in accepted:
        r["winner"]=bool(r["baseline_winner"])
        r["net_trade_pct"]=r["baseline_net_pct"]
    categories={}
    for category in ("BELOW_LOWER_2ATR","LOWER_HALF_CHANNEL","UPPER_HALF_CHANNEL","ABOVE_UPPER_2ATR","UNAVAILABLE"):
        categories[category]=stats([r for r in accepted if r["channel_category"]==category])
    gates={}
    for key in ("within_channel","below_ema","below_lower_band"):
        yes=[r for r in accepted if r[key]]
        no=[r for r in accepted if not r[key]]
        gates[key]={"retained_original":stats(yes),"skipped_original":stats(no)}
    write_csv(OUT/(symbol.lower()+"_signals.csv"),records)
    return {"V16_candidates":candidates,"baseline":stats(accepted),
      "rejected":rejected,"categories":categories,"fixed_diagnostics":gates}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={"experiment":"EXP91","research_only":True,
      "indicator":"Keltner EMA20 of typical price, ATR10 Wilder smoothing, bands +/-2 ATR",
      "scope":"Indicator values at completed V16 signal close. Continuous indicator warmup includes prior trading sessions, unlike EXP90 session-only CHOP.",
      "warning":"Diagnostic subsets of original trades are not a rerun of a filtered strategy. Small previously inspected sample; do not interpret as tested trading rules.",
      "symbols":{}}
    for symbol,path in exp83.DATA.items():
        result["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("EXP91 — KELTNER CHANNEL NOISE AUDIT — RESEARCH ONLY")
    print(json.dumps(result,indent=2))
    print("Detailed CSV:",OUT)
if __name__=="__main__":main()
