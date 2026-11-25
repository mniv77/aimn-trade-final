"""EXP36: matched candidate early versus confirmed SHORT entries; no live changes."""
import csv,json,statistics as st
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parent

def read(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    b=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda r:r['timestamp'])
    keys=[r['timestamp'][:16] for r in b]; idx={k:i for i,k in enumerate(keys)}
    o,h,l,c=[[float(r[k]) for r in b] for k in ('open','high','low','close')]
    ref=read('aimn_exp19_trend_position_audit.csv'); assert len(idx)==len(ref)==4680
    assert all(k==r['timestamp_ny'] and abs(p-float(r['close']))<1e-8 for k,p,r in zip(keys,c,ref))
    signals=defaultdict(set)
    for r in read('aimn_exp29_dual_trajectory_audit.csv'):
        j=idx[r['signal_time']]; assert abs(c[j]-float(r['signal_close']))<1e-8
        signals[r['strategy'],r['direction']].add(j)
    days=defaultdict(list)
    for i,k in enumerate(keys):days[k[:10]].append(i)
    baseline=[r for r in read('aimn_exp35_major_trajectory_integrity_audit.csv') if r['strategy']=='MTI-0']; assert len(baseline)==130
    rows=[]
    for r in baseline:
        s=idx[r['signal_time']]; e=idx[r['entry_time']]; end=days[keys[e][:10]][-1]; assert e==s+1 and s in signals['DTR-3','SHORT']
        confirm=signals['DTR-2','SHORT']; fail=signals['DTR-1','LONG']; reverse=signals['DTR-3','LONG']
        event=next((j for j in range(s+1,end+1) if j in confirm or j in fail),None)
        label='UNRESOLVED' if event is None else ('CONFIRMED' if event in confirm else 'LOCAL_REVERSE_FIRST')
        base=float(r['net_pct']); early=o[e]
        def net(p,entry):return (entry-p)/entry*100-.1*(1+p/entry)
        for mode in range(5):
            start=e; reason='SESSION_CLOSE'; x=end; price=c[end]; pending=None; validated=False
            if mode==1:
                # Wait only until first confirmation or local invalidation; no entry at session end.
                start=None
                for j in range(s+1,end):
                    if j in confirm:start=j+1;break
                    if j in fail:break
            if start is None:
                value=0.; reason='NO_ENTRY'; x=None; price=None
            else:
                entry=o[start]; stop=entry*1.01; validated=mode==1; running_low=entry
                for j in range(start,end+1):
                    if pending:
                        x=j;price=o[j];reason='STOP_GAP' if o[j]>=stop else pending;break
                    if h[j]>=stop:
                        x=j;price=max(o[j],stop);reason='STOP';break
                    running_low=min(running_low,c[j]); validated=validated or j in confirm
                    trigger=None
                    if j in reverse:trigger='OPPOSITE_TRANSITION'
                    elif not validated and mode>=2:
                        if j in fail:trigger='LOCAL_INVALIDATION'
                        elif mode==3 and j-s>=3:trigger='CONFIRMATION_TIMEOUT'
                        elif mode==4 and c[j]/running_low-1>=.003 and c[j]>c[s]:trigger='ADVERSE_STRUCTURE'
                    if trigger and j<end:pending=trigger
                value=net(price,entry)
            if mode==0:assert abs(value-base)<1e-8,(r,value,reason)
            # Retrospective diagnostics, not used by early-entry rules.
            window=range(e,(event if event is not None else end)+1)
            rows.append(dict(signal_time=keys[s],split=r['split'],strategy=f'ETV-{mode}',entry_time=keys[start] if start is not None else '',exit_time=keys[x] if x is not None else '',exit_reason=reason,net_pct=value,baseline_net_pct=base,delta_pct=value-base,first_event_RESEARCH_ONLY=label,event_time_RESEARCH_ONLY=keys[event] if event is not None else '',event_delay_minutes_RESEARCH_ONLY=(event-s)*5 if event is not None else '',early_net_at_event_close_RESEARCH_ONLY=net(c[event],early) if event is not None else '',early_best_close_net_until_event_RESEARCH_ONLY=max(net(c[j],early) for j in window),early_worst_close_net_until_event_RESEARCH_ONLY=min(net(c[j],early) for j in window)))
    out=ROOT/'aimn_exp36_early_transition_validation_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for mode in range(5):
        g=[r for r in rows if r['strategy']==f'ETV-{mode}']; v=[r['net_pct'] for r in g]; traded=[r for r in g if r['entry_time']]
        print(mode,len(traded),sum(x>0 for x in v),sum(x<0 for x in v),round(st.mean(v),4),round(st.mean(r['net_pct'] for r in traded),4),sum(r['baseline_net_pct']<=0<r['net_pct'] for r in g),sum(r['baseline_net_pct']>0>=r['net_pct'] for r in g),*[round(st.mean(r['net_pct'] for r in g if r['split']==s),4) for s in sorted({r['split'] for r in g})])
    g=[r for r in rows if r['strategy']=='ETV-0'];print(Counter(r['first_event_RESEARCH_ONLY'] for r in g))
    for label in sorted({r['first_event_RESEARCH_ONLY'] for r in g}):
        a=[r for r in g if r['first_event_RESEARCH_ONLY']==label];print(label,len(a),sum(r['net_pct']>0 for r in a),round(st.mean(r['net_pct'] for r in a),4),st.median([r['event_delay_minutes_RESEARCH_ONLY'] for r in a if r['event_delay_minutes_RESEARCH_ONLY']!='']) if label!='UNRESOLVED' else '',sum(r['early_best_close_net_until_event_RESEARCH_ONLY']>0 for r in a))
    print('Saved',out,len(rows))
if __name__=='__main__':main()
