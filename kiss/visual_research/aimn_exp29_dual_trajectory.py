"""EXP29: causal dual-level trajectory warnings; future outcomes only for audit."""
import csv,json,statistics
from pathlib import Path
from datetime import datetime
from collections import defaultdict
ROOT=Path(__file__).resolve().parent

def main():
    bars=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda b:b['timestamp'])
    with (ROOT/'aimn_exp19_trend_position_audit.csv').open() as f: ref=list(csv.DictReader(f))
    with (ROOT/'aimn_exp28_trajectory_quality_audit.csv').open() as f: prior=list(csv.DictReader(f))
    ts=[datetime.fromisoformat(b['timestamp']) for b in bars]; c=[float(b['close']) for b in bars]
    assert len(bars)==len(ref)==4680 and len(set(ts))==len(ts)
    assert all(t.strftime('%Y-%m-%d %H:%M')==r['timestamp_ny'] and abs(p-float(r['close']))<1e-8 for t,p,r in zip(ts,c,ref))
    days=defaultdict(list)
    for i,t in enumerate(ts): days[t.date()].append(i)
    rows=[]; reproduced=[]
    for day,ix in days.items():
        states={th:['SEEK',ix[0],ix[0],ix[0]] for th in (.003,.005)}
        pending=None; memory=set(); serial=0; emitted=set(); dayrows=[]
        def emit(strategy,i,d,pivot):
            sign=1 if d=='LONG' else -1
            row=dict(strategy=strategy,split=ref[i]['split'],signal_time=ref[i]['timestamp_ny'],direction=d,major_identity=serial,pivot_time=ref[pivot]['timestamp_ny'],signal_close=c[i],delay_minutes=(ts[i]-ts[pivot]).total_seconds()/60,forward_30m_gross_RESEARCH_ONLY=sign*(c[i+6]/c[i]-1)*100 if i+6<=ix[-1] else '',major_confirmation_minutes_RESEARCH_ONLY='',confirmed_before_local_reverse_RESEARCH_ONLY='')
            dayrows.append((i,row)); return row
        for i in ix:
            events={}
            for th,s in states.items():
                old,hi,lo,ex=s; new=old; pivot=None
                if old=='SEEK':
                    if c[i]>c[hi]: hi=i
                    if c[i]<c[lo]: lo=i
                    if c[i]/c[lo]-1>=th:new='LONG'
                    elif 1-c[i]/c[hi]>=th:new='SHORT'
                elif old=='LONG':
                    if c[i]>c[ex]:ex=i
                    if 1-c[i]/c[ex]>=th:new='SHORT';pivot=ex
                else:
                    if c[i]<c[ex]:ex=i
                    if c[i]/c[ex]-1>=th:new='LONG';pivot=ex
                if new!=old:ex=i
                states[th]=[new,hi,lo,ex]
                if new!=old:events[th]=(new,pivot)
                if pivot is not None:
                    reproduced.append((th*100,ref[i]['timestamp_ny'],new,ref[pivot]['timestamp_ny']))
                    emit('DTR-1' if th==.003 else 'DTR-2',i,new,pivot)
            if .005 in events:
                serial+=1; pending=None; emitted=set()
            if .003 in events:
                d,p=events[.003]; pending=None; emitted=set()
                if p is not None and states[.005][0] in ('LONG','SHORT') and d!=states[.005][0]:pending=(d,p,i)
            if pending:
                d,p,w=pending; sign=1 if d=='LONG' else -1
                # Structural break of previous three closes; recovery then renewed movement.
                structural=i>=ix[0]+3 and all(sign*(c[i]-c[j])>0 for j in range(i-3,i))
                recovery=i>=w+2 and any(sign*(c[j]-c[j-1])<0 for j in range(w+1,i)) and sign*(c[i]-c[w])>0 and sign*(c[i]-c[i-1])>0
                for name,ok in [('DTR-3',structural),('DTR-4',recovery),('DTR-5',structural and recovery and (serial,d) not in memory)]:
                    if ok and name not in emitted:
                        emit(name,i,d,p); emitted.add(name)
                        if name=='DTR-5':memory.add((serial,d))
        # Retrospective labels only; never feed these into recognition.
        for i,r in dayrows:
            if r['strategy']=='DTR-2':continue
            future=[(j,x) for j,x in dayrows if j>=i and x['strategy'] in ('DTR-1','DTR-2') and ((x['strategy']=='DTR-2' and x['direction']==r['direction']) or (x['strategy']=='DTR-1' and x['direction']!=r['direction']))]
            if future:
                j,x=min(future,key=lambda z:(z[0],z[1]['strategy']!='DTR-2'))
                r['confirmed_before_local_reverse_RESEARCH_ONLY']=int(x['strategy']=='DTR-2')
                if x['strategy']=='DTR-2':r['major_confirmation_minutes_RESEARCH_ONLY']=(ts[j]-ts[i]).total_seconds()/60
        rows.extend(r for _,r in dayrows)
    expected=[(float(r['threshold_pct']),r['signal_time'],r['direction'],r['pivot_time']) for r in prior if float(r['threshold_pct']) in (.3,.5)]
    assert sorted(reproduced)==sorted(expected),'EXP28 transition mismatch'
    out=ROOT/'aimn_exp29_dual_trajectory_audit.csv'
    with out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(len(bars),'candles',len(days),'sessions',len(reproduced),'EXP28 transitions reproduced')
    for name in ('DTR-1','DTR-2','DTR-3','DTR-4','DTR-5'):
        for d in ('SHORT','LONG'):
            g=[r for r in rows if r['strategy']==name and r['direction']==d]; f=[r['forward_30m_gross_RESEARCH_ONLY'] for r in g if r['forward_30m_gross_RESEARCH_ONLY']!='']; q=[r['confirmed_before_local_reverse_RESEARCH_ONLY'] for r in g if r['confirmed_before_local_reverse_RESEARCH_ONLY']!='']; lead=[r['major_confirmation_minutes_RESEARCH_ONLY'] for r in g if r['major_confirmation_minutes_RESEARCH_ONLY']!='']; print(name,d,len(g),len(f),round(statistics.mean(f),4) if f else '',sum(q),len(q),statistics.median(lead) if lead else '',statistics.median(r['delay_minutes'] for r in g) if g else '')
    print('Saved',out)
if __name__=='__main__':main()
