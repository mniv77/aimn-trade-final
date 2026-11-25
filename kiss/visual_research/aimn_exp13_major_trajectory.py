"""EXP13: causal session trajectory prototype; offline signal audit only."""
import csv,json,sys
from pathlib import Path
from datetime import datetime,timedelta
from collections import Counter,defaultdict
from statistics import mean
ROOT=Path(__file__).resolve().parent

def pct(a,b): return 100*(a/b-1)

def main():
    source=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'aimn_nvda_candles.json'
    base=ROOT/'aimn_exp5_continuous_transition_audit.csv'
    candles=sorted(json.loads(source.read_text(encoding='utf-8-sig')),key=lambda x:x['timestamp'])
    times=[datetime.fromisoformat(x['timestamp']) for x in candles]
    assert len(set(times))==len(times), 'Duplicate timestamps'
    with base.open(newline='',encoding='utf-8-sig') as f: baseline={r['timestamp_ny']:r for r in csv.DictReader(f)}
    rows=[]; history=[]; state='WARMUP'; peak=None; peak_i=0
    for i,(t,c) in enumerate(zip(times,candles)):
        if i==0 or t.date()!=times[i-1].date() or t-times[i-1]!=timedelta(minutes=5):
            history=[]; state='WARMUP'; peak=None
        history.append(c); p=float(c['close']); h=float(c['high']); before=state; signal=0; reason=''; rise24=rise6=age=dd=''
        if len(history)>=25:
            rise24=pct(p,float(history[-25]['close'])); rise6=pct(p,float(history[-7]['close']))
            if state=='WARMUP': state='SEEK'
            if state in ('SEEK','SHORT') and rise24>=0.75 and rise6>=0.15:
                state='LONG'; peak=h; peak_i=i; reason='ESTABLISHED_RISE'
            elif state in ('LONG','TRANSITION'):
                if h>peak: peak=h; peak_i=i; state='LONG'; reason='NEW_HIGH'
                age=i-peak_i; dd=100*(peak-p)/peak
                if age>12: state='SEEK'; reason='EXPIRED'
                elif age>=1 and dd>=0.20 and rise6<=0: state='TRANSITION'; reason='WEAKENING'
                if state=='TRANSITION' and age<=4 and dd>=0.30 and p<min(float(x['low']) for x in history[-4:-1]):
                    state='SHORT'; signal=1; reason='STRUCTURAL_BREAK'
        key=t.strftime('%Y-%m-%d %H:%M'); b=baseline.get(key,{})
        if b and abs(float(b['close'])-p)>0.00001: raise ValueError('Baseline price mismatch '+key)
        rows.append(dict(timestamp_ny=key,split='EVALUATION_AUG' if t.month==8 else 'DEVELOPMENT_JUN_JUL',close=p,state_before=before,state_after=state,reason=reason,rise24_pct=rise24,rise6_pct=rise6,peak_age=age,drawdown_pct=dd,exp13_signal=signal,v5_signal=int(b.get('v5_signal',0)),teacher_entry=int(b.get('teacher_entry',0))))
    # Outcomes computed only after all causal decisions are finished.
    for i,r in enumerate(rows):
        r['forward_60m_pct_AUDIT_ONLY']=''
        if i+12<len(rows) and times[i+12].date()==times[i].date() and all(times[i+j]-times[i]==timedelta(minutes=5*j) for j in range(1,13)):
            r['forward_60m_pct_AUDIT_ONLY']=100*(r['close']-rows[i+12]['close'])/r['close']
    out=ROOT/'aimn_exp13_major_trajectory_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print('Candles',len(rows),'sessions',len({t.date() for t in times}))
    for split in sorted({r['split'] for r in rows}):
        group=[r for r in rows if r['split']==split]; print(split,Counter(r['state_after'] for r in group))
        for k in ('v5_signal','exp13_signal'):
            s=[r for r in group if r[k]]; v=[r['forward_60m_pct_AUDIT_ONLY'] for r in s if r['forward_60m_pct_AUDIT_ONLY']!='']; print(k,len(s),'outcomes',len(v),'positive',sum(x>0 for x in v),'mean',mean(v) if v else None,'teacher exact',sum(r['teacher_entry'] for r in s))
    print('Saved',out)
if __name__=='__main__': main()
