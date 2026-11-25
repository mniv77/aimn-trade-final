"""Independent candidate episode audit; no live trading changes."""
import csv,json,statistics as st
from pathlib import Path
from datetime import datetime,timedelta
from collections import defaultdict
ROOT=Path(__file__).resolve().parent

def main():
    def read(n):
        with (ROOT/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    b=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda r:r['timestamp'])
    t=[datetime.fromisoformat(r['timestamp']) for r in b]; keys=[x.strftime('%Y-%m-%d %H:%M') for x in t]; idx={k:i for i,k in enumerate(keys)}
    o,h,l,c=[[float(r[k]) for r in b] for k in ('open','high','low','close')]
    ref=read('aimn_exp19_trend_position_audit.csv'); prior=read('aimn_exp29_dual_trajectory_audit.csv'); audit=read('aimn_exp30_transition_quality_audit.csv')
    assert len(idx)==len(b)==len(ref)==4680
    assert all(k==r['timestamp_ny'] and abs(p-float(r['close']))<1e-8 for k,p,r in zip(keys,c,ref))
    days=defaultdict(list)
    for i,x in enumerate(t):days[x.date()].append(i)
    assert all(len(v)==78 and all(t[j]-t[j-1]==timedelta(minutes=5) for j in v[1:]) for v in days.values())
    events=defaultdict(list)
    for r in prior:
        i=idx[r['signal_time']]; assert abs(c[i]-float(r['signal_close']))<1e-8
        events[r['strategy'],r['direction'],t[i].date()].append(i)
    candidates=[r for r in prior if r['strategy']=='DTR-3']; old={(r['signal_time'],r['direction']):r for r in audit}
    assert len(candidates)==len(old)==260
    rows=[]
    for r in candidates:
        i=idx[r['signal_time']]; end=days[t[i].date()][-1]; e=i+1; d=r['direction']; s=1 if d=='LONG' else -1; opposite='SHORT' if s==1 else 'LONG'
        assert (r['signal_time'],d) in old
        def target(name):return min((j for j in events[name,opposite,t[i].date()] if j>i),default=end)
        for name in ('GT-0','GT-1','GT-2','GT-3','GT-4','GT-5'):
            row=dict(signal_time=keys[i],direction=d,split=r['split'],strategy=name,entry_time='',exit_time='',exit_reason='',net_pct='',mfe_gross_pct='',mae_gross_pct='',minutes_to_net_profit_close='',giveback_close_pct='',duration_minutes='')
            if e>end or (name=='GT-0' and i+6>end):rows.append(row);continue
            entry=o[e]; stop=entry*(1-s*.01)
            def gross(p):return s*(p-entry)/entry*100
            def net(p):return gross(p)-.10*(1+p/entry)
            signal= i+6 if name=='GT-0' else target({'GT-1':'DTR-1','GT-2':'DTR-3','GT-3':'DTR-2','GT-4':'DTR-3','GT-5':'DTR-3'}[name])
            exit_i=signal if name=='GT-0' or signal==end else signal+1
            at_open=name!='GT-0' and signal<end; price=o[exit_i] if at_open else c[exit_i]; reason='FIXED_30M' if name=='GT-0' else ('SESSION_CLOSE' if signal==end else 'OPPOSITE_TRANSITION')
            best_close=0.; mfe=0.; mae=0.; first=None
            for j in range(e,exit_i+1):
                # At an opening exit, do not inspect the rest of that candle.
                if j==exit_i and at_open:
                    mfe=max(mfe,gross(o[j]));mae=max(mae,-gross(o[j]));break
                if name in ('GT-4','GT-5') and (l[j]<=stop if s==1 else h[j]>=stop):
                    price=min(o[j],stop) if s==1 else max(o[j],stop);exit_i=j;at_open=False;reason='STOP';mae=max(mae,-gross(price));break
                mfe=max(mfe,gross(h[j] if s==1 else l[j]));mae=max(mae,-gross(l[j] if s==1 else h[j]));best_close=max(best_close,gross(c[j]))
                if first is None and net(c[j])>0:first=(j-e+1)*5
                if name=='GT-5' and net(c[j])>0 and best_close-gross(c[j])>=.15 and j<exit_i and j<end:
                    exit_i=j+1;price=o[exit_i];at_open=True;reason='PROFIT_GIVEBACK';mfe=max(mfe,gross(price));mae=max(mae,-gross(price));break
            value=net(price)
            if name=='GT-0':assert abs(value-float(old[keys[i],d]['next_open_30m_net_RESEARCH_ONLY']))<1e-8
            row.update(entry_time=keys[e],exit_time=keys[exit_i],exit_reason=reason,net_pct=value,mfe_gross_pct=mfe,mae_gross_pct=mae,minutes_to_net_profit_close=first if first is not None else '',giveback_close_pct=max(0,best_close-gross(price)),duration_minutes=(exit_i-e)*5+(0 if at_open else 5));rows.append(row)
    out=ROOT/'aimn_exp31_genuine_transition_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for name in ('GT-0','GT-1','GT-2','GT-3','GT-4','GT-5'):
        for d in ('SHORT','LONG'):
            g=[r for r in rows if r['strategy']==name and r['direction']==d and r['net_pct']!=''];v=[r['net_pct'] for r in g]; print(name,d,len(v),sum(x>0 for x in v),round(st.mean(v),4),round(st.median(r['duration_minutes'] for r in g),1),sum(r['minutes_to_net_profit_close']!='' for r in g),round(st.mean(r['giveback_close_pct'] for r in g),4))
    print('Saved',out)
if __name__=='__main__':main()
