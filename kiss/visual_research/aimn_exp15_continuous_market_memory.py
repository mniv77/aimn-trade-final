"""Offline EXP15. Fixed EXP13 rules, two history treatments; no orders."""
import csv,json,sys
from pathlib import Path
from datetime import datetime,timedelta
from statistics import mean
ROOT=Path(__file__).resolve().parent
STEP=timedelta(minutes=5)
def pct(a,b): return 100*(a/b-1)
def detect(candles,times,mode):
    history=[]; state='WARMUP'; peak=None; peak_i=0; scale=1.; gap=0.; result=[]
    for i,(t,c) in enumerate(zip(times,candles)):
        new=i==0 or t.date()!=times[i-1].date()
        if new:
            gap=pct(float(c['open']),float(candles[i-1]['close'])) if i else 0.
            if mode=='B' and i: scale*=float(candles[i-1]['close'])/float(c['open'])
            if mode=='BASE': history=[]; state='WARMUP'; peak=None
        elif t-times[i-1]!=STEP:
            history=[]; state='WARMUP'; peak=None
        q={k:float(c[k])*scale for k in ('open','high','low','close')}; history.append(q)
        p=q['close']; h=q['high']; before=state; signal=0; reason=''; r24=r6=age=dd=''
        if len(history)>=25:
            r24=pct(p,history[-25]['close']); r6=pct(p,history[-7]['close'])
            if state=='WARMUP': state='SEEK'
            if state in ('SEEK','SHORT') and r24>=.75 and r6>=.15:
                state='LONG'; peak=h; peak_i=i; reason='ESTABLISHED_RISE'
            elif state in ('LONG','TRANSITION'):
                if h>peak: peak=h; peak_i=i; state='LONG'; reason='NEW_HIGH'
                age=i-peak_i; dd=100*(peak-p)/peak
                if age>12: state='SEEK'; reason='EXPIRED'
                elif age>=1 and dd>=.20 and r6<=0: state='TRANSITION'; reason='WEAKENING'
                if state=='TRANSITION' and age<=4 and dd>=.30 and p<min(x['low'] for x in history[-4:-1]):
                    state='SHORT'; signal=1; reason='STRUCTURAL_BREAK'
        result.append(dict(state_before=before,state_after=state,signal=signal,reason=reason,rise24_pct=r24,rise6_pct=r6,peak_age=age,drawdown_pct=dd,gap_pct=gap))
    return result

def main():
    source=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'aimn_nvda_candles.json'
    candles=sorted(json.loads(source.read_text(encoding='utf-8-sig')),key=lambda c:c['timestamp']); times=[datetime.fromisoformat(c['timestamp']) for c in candles]
    if len(set(times))!=len(times): raise ValueError('Duplicate candles')
    with (ROOT/'aimn_exp13_major_trajectory_audit.csv').open(newline='',encoding='utf-8-sig') as f: baseline={r['timestamp_ny']:r for r in csv.DictReader(f)}
    if len(baseline)!=len(candles): raise ValueError('Baseline length mismatch')
    variants={m:detect(candles,times,m) for m in ('BASE','A','B')}; rows=[]
    for i,(t,c) in enumerate(zip(times,candles)):
        key=t.strftime('%Y-%m-%d %H:%M'); b=baseline[key]; p=float(c['close'])
        if abs(p-float(b['close']))>1e-5 or variants['BASE'][i]['signal']!=int(b['exp13_signal']): raise ValueError('Baseline mismatch '+key)
        row=dict(timestamp_ny=key,split=b['split'],close=p,teacher_entry=int(b['teacher_entry']),morning=int(t.hour*60+t.minute<690),overnight_gap_pct=variants['B'][i]['gap_pct'])
        for m,v in variants.items(): row.update({m+'_'+k:x for k,x in v[i].items()})
        row['forward_60m_pct_AUDIT_ONLY']=''
        if i+12<len(times) and times[i+12].date()==t.date() and all(times[i+j]-t==STEP*j for j in range(1,13)): row['forward_60m_pct_AUDIT_ONLY']=100*(p-float(candles[i+12]['close']))/p
        rows.append(row)
    out=ROOT/'aimn_exp15_continuous_market_memory_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print('Candles',len(rows),'sessions',len({t.date() for t in times}))
    for split in sorted({r['split'] for r in rows}):
        for m in variants:
            s=[r for r in rows if r['split']==split and r[m+'_signal']]; v=[r['forward_60m_pct_AUDIT_ONLY'] for r in s if r['forward_60m_pct_AUDIT_ONLY']!='']; print(split,m,len(s), 'morning',sum(r['morning'] for r in s),'outcomes',len(v),'positive',sum(x>0 for x in v),'mean',mean(v) if v else None,'exact',sum(r['teacher_entry'] for r in s))
    for r in rows:
        if r['teacher_entry'] and r['morning']:
            print('Morning teacher',r['timestamp_ny'],[(m,r[m+'_state_after'],r[m+'_signal']) for m in variants])
    print('Saved',out)
if __name__=='__main__': main()
