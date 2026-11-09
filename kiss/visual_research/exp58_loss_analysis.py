import json
from collections import Counter
from kiss.visual_research.exp57_stop_priority_engine import run_kiss_backtest as bt
candles = json.load(open("kiss/visual_research/aimn_nvda_candles.json"))
trades = bt(candles,"NVDA","SHORT","5m",entry_mode="V17")["trades"]
winners = [t for t in trades if t["net_pnl_pct"] > 0]
losers = [t for t in trades if t["net_pnl_pct"] < 0]
print("WINNERS:",len(winners),"LOSERS:",len(losers))
print("WINNERS 60:",Counter(t["major_trend_short_alignment_60"] for t in winners))
print("WINNERS 120:",Counter(t["major_trend_short_alignment_120"] for t in winners))
print("LOSERS 60:",Counter(t["major_trend_short_alignment_60"] for t in losers))
print("LOSERS 120:",Counter(t["major_trend_short_alignment_120"] for t in losers))
print("ADVERSE 60 PNL:",round(sum(t["net_pnl_pct"] for t in trades if t["major_trend_short_alignment_60"]=="ADVERSE"),3))
print("MIXED 60 PNL:",round(sum(t["net_pnl_pct"] for t in trades if t["major_trend_short_alignment_60"]=="MIXED"),3))
print("FAVORABLE 60 PNL:",round(sum(t["net_pnl_pct"] for t in trades if t["major_trend_short_alignment_60"]=="FAVORABLE"),3))
print("120 PNL:",[(a,round(sum(t["net_pnl_pct"] for t in trades if t["major_trend_short_alignment_120"]==a),3)) for a in ("ADVERSE","MIXED","FAVORABLE")])
print("LOSER HOURS:",Counter(t["entry_time"][11:13] for t in losers))
print("WINNER HOURS:",Counter(t["entry_time"][11:13] for t in winners))
print("HOURLY PNL:",[(h,round(sum(t["net_pnl_pct"] for t in trades if t["entry_time"][11:13]==h),3)) for h in ("09","10","11","12","13","14","15")])
for t in trades: print(t["entry_time"],t["net_pnl_pct"],t["exit_reason"]) if t["entry_time"][11:13]=="11" else None
for t in losers: print(t["entry_time"],t.get("entry_peak_age_candles"),t.get("entry_pullback_from_peak_pct")) if t["entry_time"][11:13]=="11" else None
for t in winners: print(t["entry_time"],t.get("entry_peak_age_candles"),t.get("entry_pullback_from_peak_pct")) if t["entry_time"][11:13]=="11" else None
for t in trades: print(t["entry_time"],round(t["entry_rsi"],2),t["net_pnl_pct"]) if t["entry_time"][11:13]=="11" else None
for t in losers: print(t["entry_time"],t["max_favorable_pct"],t["max_adverse_pct"]) if t["entry_time"][11:13]=="11" else None
print([(t["entry_time"],t["max_favorable_pct"],t["max_adverse_pct"]) for t in winners if " 11:" in t["entry_time"]])
for t in trades: t["early_5m_pct"]=round((next(c["close"] for c in candles if c["timestamp"]>t["entry_time"])-t["entry_price"])/t["entry_price"]*100,3)
print("EARLY 5M:",[(name,round(sum(t["early_5m_pct"] for t in group)/len(group),3)) for name,group in [("WINNERS",winners),("LOSERS",losers)]])
print("WINNERS UP 0.3:",sum(t["early_5m_pct"]>=0.3 for t in winners))
print("LOSERS UP 0.3:",sum(t["early_5m_pct"]>=0.3 for t in losers))
print("EARLY EXITS:",sum(t["exit_time"]<=next(c["timestamp"] for c in candles if c["timestamp"]>t["entry_time"]) for t in trades))
print("EARLY EXIT DETAILS:",[(t["entry_time"],t["exit_time"],t["net_pnl_pct"]) for t in trades if t["exit_time"]<=next(c["timestamp"] for c in candles if c["timestamp"]>t["entry_time"])])
from datetime import datetime as dt; valid=[t for t in trades if (dt.fromisoformat(next(c["timestamp"] for c in candles if c["timestamp"]>t["entry_time"]))-dt.fromisoformat(t["entry_time"])).total_seconds()==300]; print("VALID 5M:",len(valid))
print("VALID SIGNAL:",[(name,sum(t["early_5m_pct"]>=0.3 for t in valid if t in group),sum(t in group for t in valid)) for name,group in [("WIN",winners),("LOSS",losers)]])
print("SIGNAL PNL:",round(sum(t["net_pnl_pct"] for t in valid if t["early_5m_pct"]>=0.3),3))
print("SIGNAL SPLIT:",[(n,round(sum(t["net_pnl_pct"] for t in valid if t in g and t["early_5m_pct"]>=0.3),3)) for n,g in [("WIN",winners),("LOSS",losers)]])
print("SIGNAL TRADES:",[(t["entry_time"],t["net_pnl_pct"]) for t in valid if t["early_5m_pct"]>=0.3])
print("NEXT OPEN:",[(t["entry_time"],next((candles[i+2]["open"] for i,c in enumerate(candles[:-2]) if c["timestamp"]==t["entry_time"]),None)) for t in valid if t["early_5m_pct"]>=0.3])
print("EARLY EXIT PNL:",round(sum((t["entry_price"]-next(candles[i+2]["open"] for i,c in enumerate(candles[:-2]) if c["timestamp"]==t["entry_time"]))/t["entry_price"]*100 for t in valid if t["early_5m_pct"]>=0.3),3))
print("TIMING:",[(t["entry_time"],candles[i+2]["timestamp"]) for t in valid if t["early_5m_pct"]>=0.3 for i,c in enumerate(candles[:-2]) if c["timestamp"]==t["entry_time"]])
print("ALREADY EXITED:",[(t["entry_time"],t["exit_time"]) for t in valid if t["early_5m_pct"]>=0.3 and t["exit_time"]<=next(candles[i+2]["timestamp"] for i,c in enumerate(candles[:-2]) if c["timestamp"]==t["entry_time"])])
print("EARLY EXIT DETAILS:",[(t["entry_time"],round(t["net_pnl_pct"],3),round((t["entry_price"]/next(candles[i+2]["open"] for i,c in enumerate(candles[:-2]) if c["timestamp"]==t["entry_time"])-1)*100,3)) for t in valid if t["early_5m_pct"]>=0.3])
print("WARNING STRENGTH:",[(t["entry_time"],t["early_5m_pct"],round(t["net_pnl_pct"],3)) for t in valid if t["early_5m_pct"]>=0.3])
print("STRONG WARNING:",[(t["entry_time"],t["early_5m_pct"],round(t["net_pnl_pct"],3)) for t in valid if t["early_5m_pct"]>=0.49])
