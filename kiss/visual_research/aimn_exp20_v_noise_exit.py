"""Offline EXP20: matched exit-event audit, not a portfolio backtest."""
import csv,json
from pathlib import Path
from datetime import datetime,timedelta
from collections import Counter
from statistics import mean
ROOT=Path(__file__).resolve().parent
STEP=timedelta(minutes=5)
FEE=.001
STOP=.01
STAGES={'V_NOISE_CANDIDATE','POTENTIAL_EXHAUSTION','REVERSE_TRANSITION'}
def net(p,q): return 100*(p-q-FEE*(p+q))/p

def main():
    bars=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda b:b['timestamp'])
    with (ROOT/'aimn_exp19_trend_position_audit.csv').open(newline='',encoding='utf-8-sig') as f: audit=list(csv.DictReader(f))
    times=[datetime.fromisoformat(b['timestamp']) for b in bars]
    if len(bars)!=len(audit) or len(set(times))!=len(times): raise ValueError('Invalid alignment')
    for t,b,r in zip(times,bars,audit):
        if t.strftime('%Y-%m-%d %H:%M')!=r['timestamp_ny'] or abs(float(b['close'])-float(r['close']))>1e-5: raise ValueError('Mismatch '+str(t))
    def contiguous(i,j): return j<len(bars) and all(times[k]-times[k-1]==STEP for k in range(i+1,j+1))
    def price(i,k): return float(bars[i][k])
    rows=[]; entry=None; stopped=False; counts=Counter(); episode=0; first=False
    for i,r in enumerate(audit):
        if i==0 or not contiguous(i-1,i): entry=None
        if r['entry_signal']=='1':
            episode+=1; entry=i+1 if contiguous(i,i+1) else None; stopped=False; first=True
            continue
        if entry is None or i<entry: continue
        p=price(entry,'open'); level=p*(1+STOP)
        if price(i,'high')>=level: stopped=True
        stage=r['stage']
        if stage in STAGES:
            counts['observed']+=1
            if stopped: counts['prior_stop']+=1
            elif not contiguous(i,i+3): counts['incomplete']+=1
            else:
                mark=net(p,price(i,'close'))
                row=dict(timestamp_ny=r['timestamp_ny'],split=r['split'],episode=episode,first_eligible_event=int(first),stage=stage,entry_timestamp_ny=audit[entry]['timestamp_ny'],entry_price=p,decision_close=price(i,'close'),decision_net_pct=mark,net_profitable=int(mark>0),stop_pct=100*STOP)
                first=False
                for wait in range(3):
                    j=i+1+wait; q=price(j,'open'); reason='NEXT_OPEN'
                    for k in range(i+1,j+1):
                        if price(k,'open')>=level: q=price(k,'open'); reason='STOP_GAP'; break
                        if k<j and price(k,'high')>=level: q=level; reason='STOP_TOUCH'; break
                    row[f'wait{wait}_net_pct']=net(p,q); row[f'wait{wait}_reason']=reason
                row['wait1_delta_pct']=row['wait1_net_pct']-row['wait0_net_pct']; row['wait2_delta_pct']=row['wait2_net_pct']-row['wait0_net_pct']
                # Profit-sensitive policy: genuine reversal or positive mark exits now.
                wait=0 if stage=='REVERSE_TRANSITION' or mark>0 else 1
                row['adaptive_wait_bars']=wait; row['adaptive_net_pct']=row[f'wait{wait}_net_pct']
                row['adaptive_delta_pct']=row['adaptive_net_pct']-row['wait0_net_pct']
                rows.append(row)
        if r['reverse_signal']=='1': entry=None
    if not rows: raise ValueError('No eligible events')
    out=ROOT/'aimn_exp20_v_noise_exit_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print('Candles',len(bars),'episodes',episode,'counts',dict(counts),'eligible',len(rows))
    for label,g in [('ALL',rows),('FIRST',[r for r in rows if r['first_eligible_event']])]+[(s,[r for r in rows if r['split']==s]) for s in sorted({r['split'] for r in rows})]+[(s,[r for r in rows if r['stage']==s]) for s in sorted(STAGES)]+[(f'PROFIT={v}',[r for r in rows if r['net_profitable']==v and r['stage']!='REVERSE_TRANSITION']) for v in (0,1)]:
        if g: print(label,len(g),'episodes',len({r['episode'] for r in g}), 'means',*[round(mean(r[k] for r in g),4) for k in ('wait0_net_pct','wait1_net_pct','wait2_net_pct','adaptive_net_pct')], 'wait1 better/worse',sum(r['wait1_delta_pct']>0 for r in g),sum(r['wait1_delta_pct']<0 for r in g))
    print('Saved',out)
if __name__=='__main__': main()
