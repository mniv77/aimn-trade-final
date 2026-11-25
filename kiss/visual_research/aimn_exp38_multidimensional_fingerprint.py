"""EXP38: development-only threshold combinations; inherited EXP37 returns."""
import csv, itertools, statistics as st
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    with (ROOT/'aimn_exp37_transition_fingerprint_audit.csv').open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    assert len(rows)==130 and len({r['signal_time'] for r in rows})==130
    features=['prior_peak_rise','rsi14','peak_drawdown','short_15m','down_fraction','lower_high_proxy','peak_age_minutes','short_30m','rsi_change_15m']
    for r in rows:
        for k in features:r[k]=float(r[k]) if r[k] else None
        r['baseline_net_pct']=float(r['baseline_net_pct'])
        r['fingerprint_accept']=int(r['fingerprint_accept'])
    dev=[r for r in rows if r['split']=='DEVELOPMENT_JUN_JUL']; aug=[r for r in rows if r['split']!='DEVELOPMENT_JUN_JUL']
    assert all(r['signal_time'][5:7]=='08' for r in aug)
    labeled=[r for r in dev if r['label_RESEARCH_ONLY']!='UNRESOLVED']
    pos=[r for r in labeled if r['label_RESEARCH_ONLY']=='CONFIRMED']; neg=[r for r in labeled if r['label_RESEARCH_ONLY']=='LOCAL_REVERSE_FIRST']; assert len(pos)+len(neg)==len(labeled)
    def score(fn):
        tp=sum(map(fn,pos)); fp=sum(map(fn,neg))
        if tp<.4*len(pos) or tp+fp<.4*len(labeled):return -1
        return (tp/len(pos)+1-fp/len(neg))/2
    def vote(r,rule):
        k,t,s=rule; return r[k] is not None and s*(r[k]-t)>=0
    def fit(k):
        v=sorted(r[k] for r in labeled if r[k] is not None)
        ts=sorted(set(v[int((len(v)-1)*q)] for q in (.25,.5,.75)))
        return max((score(lambda r:vote(r,(k,t,s))),t,s) for t in ts for s in (-1,1))[1:]
    rules={k:(k,*fit(k)) for k in features}
    models={'MTF-0':lambda r:True,'MTF-1':lambda r:bool(r['fingerprint_accept'])}; descriptions={'MTF-0':'all','MTF-1':'EXP37 frozen'}
    for name,ks in [('MTF-2',['prior_peak_rise','rsi14']),('MTF-3',['peak_drawdown','short_15m']),('MTF-4',['down_fraction','lower_high_proxy','peak_age_minutes']),('MTF-5',['prior_peak_rise','rsi14','peak_drawdown','short_15m','down_fraction'])]:
        rr=[rules[k] for k in ks]
        n=max(range(1,len(rr)+1),key=lambda n:score(lambda r:sum(vote(r,x) for x in rr)>=n))
        models[name]=lambda r,rr=rr,n=n:sum(vote(r,x) for x in rr)>=n
        descriptions[name]=f'{n}/{len(rr)} votes: {rr}'
    out=[]
    for name,fn in models.items():
        print(name,descriptions[name])
        for group,g in [('DEV',dev),('AUG',aug),('ALL',rows)]:
            a=[r for r in g if fn(r)]; wins=sum(r['baseline_net_pct']>0 for r in a)
            print(group,len(g),len(a),wins,len(a)-wins,round(sum(r['baseline_net_pct'] for r in a)/len(g),6),round(st.mean(r['baseline_net_pct'] for r in a),6) if a else None, sum(r['label_RESEARCH_ONLY']=='CONFIRMED' for r in a),sum(r['label_RESEARCH_ONLY']=='LOCAL_REVERSE_FIRST' for r in a))
        for r in rows:out.append(dict(**r,strategy=name,accept=int(fn(r)),net_per_candidate=r['baseline_net_pct']*int(fn(r)),model=descriptions[name]))
    with (ROOT/'aimn_exp38_multidimensional_fingerprint_audit.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
if __name__=='__main__':main()
