"""Offline EXP18: opening exhaustion and recovery, no live trading."""
import csv,json,statistics as st
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timedelta
ROOT=Path(__file__).resolve().parent
FEE=.001
STEP=timedelta(minutes=5)
def simulate(s,j,end,stop=None):
    p=float(s[j]['open']); q=float(s[end]['close']); hit=0
    path=s[j:end+1]
    mae=max(0,100*(max(float(b['high']) for b in path)/p-1))
    mfe=max(0,100*(1-min(float(b['low']) for b in path)/p))
    if stop is not None:
        level=p*(1+stop)
        for b in path:
            if float(b['high'])>=level:
                q=max(level,float(b['open'])); hit=1; break
    return 100*(p-q-FEE*(p+q))/p,hit,mae,mfe

def main():
    days=defaultdict(list)
    for c in sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda c:c['timestamp']):
        days[c['timestamp'][:10]].append(c)
    with (ROOT/'aimn_exp16_opening_transition_audit.csv').open(encoding='utf-8-sig',newline='') as f:
        audit={r['timestamp_ny'][:10]:r for r in csv.DictReader(f) if r['minutes_after_open']=='5'}
    rows=[]; prev=None
    for day,s in sorted(days.items()):
        r=audit[day]; c=float(s[0]['close']); o=float(s[0]['open'])
        if abs(c-float(r['close']))>1e-5: raise ValueError('Price mismatch '+day)
        if len(s)<13 or any(datetime.fromisoformat(s[i]['timestamp'])-datetime.fromisoformat(s[i-1]['timestamp'])!=STEP for i in range(1,13)): raise ValueError('Incomplete opening path '+day)
        candidate=int(r['short_reversal_candidate']); combined=None if prev is None else 100*(c/float(prev[-1]['close'])-1)
        peak=None if prev is None else max(float(b['high']) for b in prev[-24:]+s[:1])
        hist=(prev or [])[-14:]+s[:1]; changes=[float(b['close'])-float(a['close']) for a,b in zip(hist,hist[1:])]; gains=sum(max(x,0) for x in changes); losses=sum(max(-x,0) for x in changes)
        rsi=100*gains/(gains+losses) if len(changes)==14 and gains+losses else None
        row=dict(date=day,split=r['split'],candidate=candidate,overnight_gap_pct=r['overnight_gap_pct'],opening_move_pct=r['opening_move_pct'],combined_move_pct=combined,drawdown_from_recent_peak_pct=None if peak is None else 100*(1-c/peak),rsi14_simple=rsi,exhaustion_flag=int(combined is not None and combined<=-2),recovery_signal_time='',recovery_entry_time='')
        # Fixed exploratory rule: recover 0.3% from first close, then close below previous candle low; decide by 10:00.
        recovered=False; j=None
        for i in range(1,6):
            if recovered and float(s[i]['close'])<float(s[i-1]['low']): j=i+1; break
            if float(s[i]['close'])>=c*1.003: recovered=True
        if j is not None:
            row['recovery_signal_time']=s[j-1]['timestamp']; row['recovery_entry_time']=s[j]['timestamp']
        for name,entry in [('immediate',1),('recovery',j)]:
            for label,stop in [('none',None),('05',.005),('10',.01)]:
                result=simulate(s,entry,12,stop) if entry is not None else None
                row[name+'_net_'+label]=result[0] if result else None
                row[name+'_stop_'+label]=result[1] if result else None
                if label=='none':
                    row[name+'_mae']=result[2] if result else None; row[name+'_mfe']=result[3] if result else None
        # No trade = zero per candidate, not a winning trade.
        for label in ('none','05','10'):
            row['filtered_net_'+label]=0 if row['exhaustion_flag'] else row['immediate_net_'+label]
            row['wait_net_'+label]=((row['recovery_net_'+label] or 0) if row['exhaustion_flag'] else row['immediate_net_'+label])
        rows.append(row); prev=s
    out=ROOT/'aimn_exp18_opening_exhaustion_audit.csv'
    with out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('Sessions',len(rows))
    for split in ['ALL']+sorted({r['split'] for r in rows}):
        g=[r for r in rows if r['candidate'] and (split=='ALL' or r['split']==split)]
        if not g: continue
        print(split,len(g),'flagged',sum(r['exhaustion_flag'] for r in g),'flagged recovery',sum(bool(r['recovery_entry_time']) and r['exhaustion_flag'] for r in g))
        for label in ('none','05','10'):
            print(label,[(k,round(st.mean(r[k+'_net_'+label] for r in g),4)) for k in ('immediate','filtered','wait')])
    print('Saved',out)
if __name__=='__main__':main()
