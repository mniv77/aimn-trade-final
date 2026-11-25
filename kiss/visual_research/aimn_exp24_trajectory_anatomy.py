"""EXP24 offline diagnostic. No trading signals or live changes."""
import csv,json
from pathlib import Path
from statistics import median,mean
from collections import Counter
from datetime import datetime,timedelta
ROOT=Path(__file__).resolve().parent
FEE=.001

def main():
    bars=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda b:b['timestamp'])
    times=[datetime.fromisoformat(b['timestamp']) for b in bars]
    keys=[t.strftime('%Y-%m-%d %H:%M') for t in times]; idx={k:i for i,k in enumerate(keys)}
    if len(idx)!=len(bars): raise ValueError('Duplicate timestamps')
    with (ROOT/'aimn_exp23_failed_continuation_quality_audit.csv').open(encoding='utf-8-sig',newline='') as f: source=list(csv.DictReader(f))
    def v(i,k): return float(bars[i][k])
    rows=[]
    for r in source:
        s,e,x=(idx[r[k]] for k in ('entry_signal_time','entry_time','quality_profit_exit_time'))
        p=float(r['entry_price']); net=float(r['quality_profit_net_pct']); gb=float(r['quality_profit_giveback_pct']); reason=r['quality_profit_reason']
        if not (s+1==e<=x) or abs(p-v(e,'open'))>1e-6 or times[s].date()!=times[x].date(): raise ValueError('Episode alignment '+r['episode'])
        q=(p*(1-FEE)-p*net/100)/(1+FEE)
        expected=v(x,'close') if reason=='SESSION_OR_NEXT_SIGNAL_BOUNDARY' else p*1.01 if reason=='STOP_TOUCH' else v(x,'open')
        if abs(q-expected)>1e-6: raise ValueError('Exit mismatch '+r['episode'])
        start=s
        while start>0 and times[start]-times[start-1]==timedelta(minutes=5): start-=1
        def change(n): return 100*(v(s,'close')/v(s-n,'close')-1) if s-n>=start else None
        window=range(max(start,s-12),s+1); peak=max(window,key=lambda i:v(i,'high'))
        changes=[v(i,'close')-v(i-1,'close') for i in range(s-13,s+1)] if s-14>=start else []
        total=sum(abs(z) for z in changes); rsi=100*sum(max(z,0) for z in changes)/total if total else None
        # Full bars before exit only; boundary close includes the full exit bar.
        full=range(e,x+int(reason=='SESSION_OR_NEXT_SIGNAL_BOUNDARY'))
        low=min([p,q]+[v(i,'low') for i in full]); high=max([p,q]+[v(i,'high') for i in full])
        best=100*(p-low-FEE*(p+low))/p
        if abs(max(0,best-net)-gb)>1e-6: raise ValueError('Giveback mismatch '+r['episode'])
        outcome='WIN' if net>0 else 'LOSS' if net<0 else 'FLAT'
        diagnosis='WIN' if net>0 else 'NO_OBSERVED_NET_PROFIT' if best<=0 else 'NET_PROFIT_GIVEN_BACK'
        rows.append(dict(episode=r['episode'],split=r['split'],signal_time=keys[s],entry_time=keys[e],exit_time=keys[x],entry_price=p,exit_price=q,exit_reason=reason,outcome=outcome,net_pct=net,prior_30m_pct=change(6),prior_60m_pct=change(12),peak_distance_pct=100*(1-v(s,'close')/v(peak,'high')),peak_age_minutes=(s-peak)*5,rsi14=rsi,observed_mfe_pct=100*(p-low)/p,observed_mae_pct=100*(high-p)/p,best_observed_net_pct=best,giveback_pct=gb,diagnosis=diagnosis,exit_bar_intrabar_unknown=int(reason=='STOP_TOUCH')))
    out=ROOT/'aimn_exp24_trajectory_anatomy_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for group in ('WIN','LOSS','FLAT'):
        g=[r for r in rows if r['outcome']==group]
        if not g: continue
        print(group,len(g),'mean net',mean(r['net_pct'] for r in g),Counter(r['diagnosis'] for r in g),Counter(r['exit_reason'] for r in g))
        for k in ('prior_30m_pct','prior_60m_pct','peak_distance_pct','peak_age_minutes','rsi14','observed_mfe_pct','observed_mae_pct','giveback_pct'):
            a=[r[k] for r in g if r[k] is not None];print(k,round(median(a),4) if a else None,'n=',len(a))
    print('Saved',out)
if __name__=='__main__': main()
