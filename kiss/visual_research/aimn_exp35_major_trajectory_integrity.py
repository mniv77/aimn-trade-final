"""EXP35: fixed SHORT entries, causal structural exits, independent stop."""
import csv,json,statistics as st
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parent

def read(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    b=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda r:r['timestamp'])
    keys=[r['timestamp'][:16] for r in b]; idx={k:i for i,k in enumerate(keys)}
    o,h,l,c=[[float(r[k]) for r in b] for k in ('open','high','low','close')]
    ref=read('aimn_exp19_trend_position_audit.csv'); assert len(idx)==len(ref)==4680
    assert all(k==r['timestamp_ny'] and abs(p-float(r['close']))<1e-8 for k,p,r in zip(keys,c,ref))
    prior=read('aimn_exp29_dual_trajectory_audit.csv'); signals=defaultdict(set)
    for r in prior:signals[r['strategy'],r['direction']].add(idx[r['signal_time']])
    days=defaultdict(list)
    for i,k in enumerate(keys):days[k[:10]].append(i)
    # Reconstruct major state including initial SEEK confirmation, absent from DTR-2 audit.
    major={}; flips=set()
    for day,ii in days.items():
        state='SEEK'; hi=lo=ex=ii[0]; serial=0
        for j in ii:
            old=state
            if state=='SEEK':
                if c[j]>c[hi]:hi=j
                if c[j]<c[lo]:lo=j
                if c[j]/c[lo]-1>=.005:state='LONG'
                elif 1-c[j]/c[hi]>=.005:state='SHORT'
            elif state=='LONG':
                if c[j]>c[ex]:ex=j
                if 1-c[j]/c[ex]>=.005:state='SHORT'
            else:
                if c[j]<c[ex]:ex=j
                if c[j]/c[ex]-1>=.005:state='LONG'
            if state!=old:
                serial+=1;ex=j
                if old!='SEEK':flips.add((j,state))
            major[j]=(state,serial)
    assert flips=={(j,d) for d in ('LONG','SHORT') for j in signals['DTR-2',d]}
    baseline=[r for r in read('aimn_exp34_profit_aware_v_noise_audit.csv') if r['strategy']=='PVD-0']; assert len(baseline)==130
    rows=[]
    for r in baseline:
        e=idx[r['entry_time']]; end=days[keys[e][:10]][-1]; entry=o[e]; stop=entry*1.01; base=float(r['net_pct']); s=idx[r['signal_time']]
        def net(p):return (entry-p)/entry*100-.1*(1+p/entry)
        for mode in range(6):
            pending=None; best=net(entry); low=entry; highs=[]; lows=[]; armed=None; first_v=None; reason='SESSION_CLOSE'; price=c[end]; x=end
            for j in range(e,end+1):
                if pending:
                    x=j;price=o[j];reason='STOP_GAP' if o[j]>=stop else pending;break
                if h[j]>=stop:
                    x=j;price=max(o[j],stop);reason='STOP';break
                n=net(c[j]);best=max(best,n);low=min(low,c[j]); state,identity=major[j]
                if state=='SHORT' and armed is None:armed=identity
                if j>=e+2:
                    if c[j-1]>c[j-2] and c[j-1]>c[j]:highs.append(c[j-1])
                    if c[j-1]<c[j-2] and c[j-1]<c[j]:lows.append(c[j-1])
                local=j in signals['DTR-1','LONG']; warning=j in signals['DTR-3','LONG']; major_long=j in signals['DTR-2','LONG']
                if local and first_v is None:first_v=j
                structural=len(highs)>=2 and len(lows)>=2 and highs[-1]>highs[-2] and lows[-1]>lows[-2] and c[j]>highs[-1]
                lost=armed is not None and state=='LONG' and identity!=armed
                intact=state=='SHORT' and not structural
                if mode==0:trigger='OPPOSITE_TRANSITION' if warning else None
                elif mode==1:trigger='STRUCTURAL_BREAK' if structural else ('MAJOR_LONG' if major_long else None)
                elif mode==2:trigger='IDENTITY_LOST' if lost else ('OPPOSITE_TRANSITION' if warning and armed is None else None)
                elif mode==3:trigger='MAJOR_LONG' if major_long else ('OPPOSITE_TRANSITION' if warning and not intact else None)
                elif mode==4:trigger='PROFIT_STRUCTURE' if n>0 and (structural or (warning and not intact)) else ('MAJOR_LONG' if major_long else ('OPPOSITE_TRANSITION' if warning and armed is None else None))
                else:trigger='STRUCTURAL_BREAK' if structural else ('IDENTITY_LOST' if lost else ('OPPOSITE_TRANSITION' if warning and not intact else None))
                if trigger and j<end:pending=trigger
            value=net(price)
            if mode==0:assert abs(value-base)<1e-8,(r,value,reason)
            rows.append(dict(signal_time=r['signal_time'],split=r['split'],strategy=f'MTI-{mode}',entry_time=keys[e],exit_time=keys[x],exit_reason=reason,first_v_time=keys[first_v] if first_v is not None else '',entry_major_state=major[s][0],entry_major_identity=major[s][1],exit_major_state=major[x-1 if pending else x][0],net_pct=value,baseline_net_pct=base,delta_pct=value-base,best_close_net_pct=best,giveback_pct=max(0,best-value),recovered=int(base<=0<value),sacrificed=int(base>0>=value)))
    assert len(rows)==780
    out=ROOT/'aimn_exp35_major_trajectory_integrity_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for mode in range(6):
        g=[r for r in rows if r['strategy']==f'MTI-{mode}'];v=[r['net_pct'] for r in g]
        print(mode,len(g),sum(x>0 for x in v),round(st.mean(v),4),sum(r['recovered'] for r in g),sum(r['sacrificed'] for r in g),round(min(v),4),sum(r['exit_reason'].startswith('STOP') for r in g),*[round(st.mean(r['net_pct'] for r in g if r['split']==s),4) for s in sorted(set(r['split'] for r in g))])
    print('Saved',out)
if __name__=='__main__':main()
