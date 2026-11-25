"""EXP37: causal close-only fingerprint, chronological development/evaluation."""
import csv, statistics as st, math
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent

def read(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    candles=read('aimn_exp19_trend_position_audit.csv'); keys=[r['timestamp_ny'] for r in candles]; c=[float(r['close']) for r in candles]; idx={k:i for i,k in enumerate(keys)}
    assert len(idx)==len(c)==4680 and keys==sorted(keys)
    dtr={r['signal_time']:r for r in read('aimn_exp29_dual_trajectory_audit.csv') if r['strategy']=='DTR-3' and r['direction']=='SHORT'}
    base=[r for r in read('aimn_exp36_early_transition_validation_audit.csv') if r['strategy']=='ETV-0']; assert len(base)==130 and len({r['signal_time'] for r in base})==130
    rows=[]
    for r in base:
        k=r['signal_time']; i=idx[k]; d=dtr[k]; assert abs(float(d['signal_close'])-c[i])<1e-8 and r['split']==candles[i]['split']==d['split']
        start=i
        while start>0 and keys[start-1][:10]==k[:10]:start-=1
        p=idx[d['pivot_time']]; assert start<=p<=i
        def ret(a,b):return 100*(c[b]/c[a]-1)
        def rsi(j):
            if j-start<14:return None
            dif=[c[t]-c[t-1] for t in range(j-13,j+1)]; up=sum(max(x,0) for x in dif); dn=sum(max(-x,0) for x in dif)
            return 100*up/(up+dn) if up+dn else 50.
        a=max(start,p-12); w=max(start,i-3); z=max(start,i-6)
        f=dict(prior_peak_rise=ret(a,p) if p>a else None,peak_drawdown=-ret(p,i),peak_age_minutes=(i-p)*5,short_15m=-ret(w,i) if i-w==3 else None,short_30m=-ret(z,i) if i-z==6 else None,down_fraction=sum(c[t]<c[t-1] for t in range(p+1,i+1))/(i-p) if i>p else None,lower_high_proxy=float(max(c[i-2:i+1])<max(c[i-5:i-2])) if i-start>=5 else None,rsi14=rsi(i),rsi_change_15m=rsi(i)-rsi(i-3) if rsi(i) is not None and rsi(i-3) is not None else None)
        rows.append(dict(signal_time=k,split=r['split'],label_RESEARCH_ONLY=r['first_event_RESEARCH_ONLY'],baseline_net_pct=float(r['net_pct']),**f))
    features=list(f); dev=[r for r in rows if r['split']=='DEVELOPMENT_JUN_JUL']; test=[r for r in rows if r['split']!='DEVELOPMENT_JUN_JUL']; assert len(dev)+len(test)==130
    # Fit single-feature threshold on development labels only; require >= 40% acceptance and >= 40% confirmed recall. Rank by balanced accuracy.
    labeled=[r for r in dev if r['label_RESEARCH_ONLY']!='UNRESOLVED']; pos=sum(r['label_RESEARCH_ONLY']=='CONFIRMED' for r in labeled); neg=len(labeled)-pos
    def accept(r,k,t,s):return r[k] is not None and s*(r[k]-t)>=0
    candidates=[]
    for k in features:
        vals=sorted({r[k] for r in labeled if r[k] is not None})
        for t in [(a+b)/2 for a,b in zip(vals,vals[1:])]:
            for s in (-1,1):
                tp=sum(accept(r,k,t,s) and r['label_RESEARCH_ONLY']=='CONFIRMED' for r in labeled); fp=sum(accept(r,k,t,s) and r['label_RESEARCH_ONLY']!='CONFIRMED' for r in labeled)
                if tp+fp>=.4*len(labeled) and tp>=.4*pos:candidates.append(((tp/pos+1-fp/neg)/2,k,t,s))
    score,k,t,s=max(candidates); print('RULE',score,k,t,s)
    for r in rows:
        r['fingerprint_accept']=int(accept(r,k,t,s));r['filtered_net_per_candidate']=r['baseline_net_pct']*r['fingerprint_accept'];r['rule_feature']=k;r['rule_threshold']=t;r['rule_sign']=s
    for name,g in [('DEV',dev),('AUG',test),('ALL',rows)]:
        a=[r for r in g if r['fingerprint_accept']]; print(name,len(g),Counter(r['label_RESEARCH_ONLY'] for r in g),len(a),Counter(r['label_RESEARCH_ONLY'] for r in a),sum(r['baseline_net_pct']>0 for r in g),sum(r['baseline_net_pct']>0 for r in a),st.mean(r['baseline_net_pct'] for r in g),st.mean(r['filtered_net_per_candidate'] for r in g),st.mean(r['baseline_net_pct'] for r in a) if a else None)
    for k in features:
        print(k,*[(len(v),round(st.median(v),4) if v else None) for label in ('CONFIRMED','LOCAL_REVERSE_FIRST') for v in [[r[k] for r in dev if r['label_RESEARCH_ONLY']==label and r[k] is not None]]])
    out=ROOT/'aimn_exp37_transition_fingerprint_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
if __name__=='__main__':main()
