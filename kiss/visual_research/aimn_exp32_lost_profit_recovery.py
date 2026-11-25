"""EXP32 independent SHORT episodes. No live trading changes."""
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
    prior=read('aimn_exp29_dual_trajectory_audit.csv'); old=read('aimn_exp31_genuine_transition_audit.csv')
    local={idx[r['signal_time']] for r in prior if r['strategy']=='DTR-1' and r['direction']=='LONG'}
    days=defaultdict(list)
    for i,k in enumerate(keys):days[k[:10]].append(i)
    rsi={}
    for day,ii in days.items():
        for j in ii[14:]:
            changes=[c[k]-c[k-1] for k in range(j-13,j+1)]; up=sum(max(x,0) for x in changes); down=sum(max(-x,0) for x in changes)
            rsi[j]=100*up/(up+down) if up+down else 50
    rows=[]
    for r in old:
        if r['strategy']!='GT-2' or r['direction']!='SHORT' or not r['net_pct']:continue
        e=idx[r['entry_time']]; end=days[keys[e][:10]][-1]; base=idx[r['exit_time']]; base_open=r['exit_reason']=='OPPOSITE_TRANSITION'; entry=o[e]
        def net(p):return (entry-p)/entry*100-.1*(1+p/entry)
        for name in ['LPR-0','STOP_ONLY','LPR-1','LPR-2','LPR-3','LPR-4','LPR-5','LPR-6']:
            price=o[base] if base_open else c[base]; x=base; reason=r['exit_reason']; best=net(entry); first=None; low=c[e]; stale=0; prev_pivot=None; higher=False
            for j in range(e,base+1):
                if j==base and base_open:break
                if name!='LPR-0' and h[j]>=entry*1.01:
                    price=max(o[j],entry*1.01); x=j; reason='STOP'; break
                n=net(c[j]); best=max(best,n)
                if n>0 and first is None:first=(j-e+1)*5
                if c[j]<low:low=c[j];stale=0
                else:stale+=1
                if j>=e+2 and c[j-1]<c[j-2] and c[j-1]<c[j]:
                    higher=prev_pivot is not None and c[j-1]>prev_pivot;prev_pivot=c[j-1]
                else:higher=False
                noise=j in local; failed=stale>=3 and (c[j]/low-1)*100>=.15
                rescue=j>e and rsi.get(j,0)>=80 and (c[j]/c[j-1]-1)*100>=.30
                adaptive=(n>0 and (noise or failed or higher)) or (n<=0 and failed and higher)
                tests={'LPR-1':noise and n>0,'LPR-2':failed,'LPR-3':higher,'LPR-4':adaptive,'LPR-5':rescue,'LPR-6':adaptive or rescue}
                if tests.get(name,False) and j<base and j<end:
                    x=j+1;price=o[x];reason='RSI_RESCUE' if rescue and name in ('LPR-5','LPR-6') else name;break
            value=net(price)
            if name=='LPR-0':assert abs(value-float(r['net_pct']))<1e-8
            rows.append(dict(signal_time=r['signal_time'],split=r['split'],strategy=name,entry_time=keys[e],exit_time=keys[x],exit_reason=reason,net_pct=value,baseline_net_pct=r['net_pct'],delta_pct=value-float(r['net_pct']),best_close_net_pct=best,minutes_to_profit=first if first is not None else '',baseline_lost_profit=int(bool(r['minutes_to_net_profit_close']) and float(r['net_pct'])<=0)))
    assert len(rows)==130*8
    out=ROOT/'aimn_exp32_lost_profit_recovery_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for name in dict.fromkeys(r['strategy'] for r in rows):
        g=[r for r in rows if r['strategy']==name]; v=[r['net_pct'] for r in g]; print(name,len(v),sum(x>0 for x in v),round(st.mean(v),4),'recovered',sum(r['baseline_lost_profit'] and r['net_pct']>0 for r in g),'lost winners',sum(float(r['baseline_net_pct'])>0 and r['net_pct']<=0 for r in g),'RSI',sum(r['exit_reason']=='RSI_RESCUE' for r in g),'split',*[round(st.mean(r['net_pct'] for r in g if r['split']==s),4) for s in sorted(set(r['split'] for r in g))])
    print('Saved',out)
if __name__=='__main__':main()
