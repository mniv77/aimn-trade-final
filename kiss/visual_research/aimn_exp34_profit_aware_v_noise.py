"""EXP34: fixed-entry protected SHORT episode comparison, no live changes."""
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
    local={idx[r['signal_time']] for r in read('aimn_exp29_dual_trajectory_audit.csv') if r['strategy']=='DTR-1' and r['direction']=='LONG'}
    old=read('aimn_exp32_lost_profit_recovery_audit.csv'); baseline=[r for r in old if r['strategy']=='STOP_ONLY']; assert len(baseline)==130
    original={r['signal_time']:r for r in old if r['strategy']=='LPR-1'}
    events=defaultdict(set)
    for r in read('aimn_exp33_v_noise_anatomy_audit.csv'):events[r['signal_time']].add(idx[r['event_time']])
    rows=[]
    for r in baseline:
        e,x=idx[r['entry_time']],idx[r['exit_time']]; entry=o[e]; base=float(r['net_pct']); stop=entry*1.01
        def net(p):return (entry-p)/entry*100-.1*(1+p/entry)
        expected={j for j in range(e,x) if j in local}; assert expected==events[r['signal_time']]
        for mode in range(6):
            best=net(entry); worst=best; pending=None; first=None; low=c[e]; reason=r['exit_reason']; exit_i=x; value=base
            for j in range(e,x+1):
                if j==x and reason=='OPPOSITE_TRANSITION':break
                if h[j]>=stop:
                    value=net(max(o[j],stop)); exit_i=j; reason='STOP'; worst=min(worst,value);break
                n=net(c[j]); best=max(best,n); worst=min(worst,net(h[j])); low=min(low,c[j])
                if j>=x:break
                if mode==0:continue
                noise=j in local
                if noise and first is None:first=j
                trigger=None
                if noise and n>0:trigger='PROFITABLE_V'
                elif mode>=2:
                    if noise and pending is None:pending=j
                    if pending is not None:
                        age=j-pending
                        if n>0:trigger='PROFIT_RECOVERED'
                        elif mode<=4 and age>=mode-1:trigger='WAIT_EXPIRED'
                        elif mode==5:
                            # Adaptive: allow at most three bars; exit sooner on adverse structural break.
                            if j>pending and c[j]>max(c[pending:j]) and c[j]>=low*1.003:trigger='ADVERSE_STRUCTURE'
                            elif age>=3:trigger='WAIT_EXPIRED'
                if trigger:
                    exit_i=j+1; value=net(o[exit_i]); reason=trigger
                    # A gap through the stop fills at the same open, with stop priority.
                    if o[exit_i]>=stop:reason='STOP_GAP'
                    break
            if mode==0:assert abs(value-base)<1e-8
            if mode==1:assert abs(value-float(original[r['signal_time']]['net_pct']))<1e-8
            rows.append(dict(signal_time=r['signal_time'],split=r['split'],strategy=f'PVD-{mode}',entry_time=keys[e],exit_time=keys[exit_i],exit_reason=reason,first_v_time=keys[first] if first is not None else '',net_pct=value,baseline_net_pct=base,delta_pct=value-base,best_close_net_pct=best,giveback_pct=max(0,best-value),worst_observed_net_pct=min(worst,value),recovered=int(base<=0<value),sacrificed=int(base>0>=value)))
    assert len(rows)==780
    out=ROOT/'aimn_exp34_profit_aware_v_noise_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for mode in range(6):
        g=[r for r in rows if r['strategy']==f'PVD-{mode}']; v=[r['net_pct'] for r in g]
        print(mode,len(g),sum(x>0 for x in v),round(st.mean(v),4),sum(r['recovered'] for r in g),sum(r['sacrificed'] for r in g),round(min(v),4),round(st.mean(r['giveback_pct'] for r in g),4),*[round(st.mean(r['net_pct'] for r in g if r['split']==s),4) for s in sorted(set(r['split'] for r in g))])
    print('Saved',out)
if __name__=='__main__':main()
