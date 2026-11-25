"""EXP33: diagnostic V events within protected GT-2 SHORT episodes; no live changes."""
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
    old=read('aimn_exp32_lost_profit_recovery_audit.csv')
    days=defaultdict(list)
    for i,k in enumerate(keys):days[k[:10]].append(i)
    rows=[]
    for r in old:
        if r['strategy']!='STOP_ONLY':continue
        e,x=idx[r['entry_time']],idx[r['exit_time']]; day=days[keys[e][:10]]; start,end=day[0],day[-1]; entry=o[e]
        def net(p):return (entry-p)/entry*100-.1*(1+p/entry)
        low=c[e]; pivot=e; prev_pivot=None; last_pivot=None; best=net(entry)
        for j in range(e,x+1):
            if j==x and r['exit_reason'] in ('STOP','OPPOSITE_TRANSITION'):break
            if c[j]<low:low=c[j];pivot=j
            best=max(best,net(c[j]))
            if j>=e+2 and c[j-1]<c[j-2] and c[j-1]<c[j]:prev_pivot,last_pivot=last_pivot,c[j-1]
            if j not in local or j>=end or j>=x:continue
            def rsi(k):
                if k-start<14:return None
                d=[c[t]-c[t-1] for t in range(k-13,k+1)]; a=sum(max(v,0) for v in d); z=sum(abs(v) for v in d)
                return 100*a/z if z else 50
            a,z=rsi(j),rsi(j-1)
            row=dict(signal_time=r['signal_time'],split=r['split'],event_time=keys[j],event_close=c[j],entry_time=keys[e],net_at_event_close=net(c[j]),best_close_net=best,recovery_pct=100*(c[j]/low-1),minutes_since_low=5*(j-pivot),recovery_per_bar_pct=100*(c[j]/low-1)/max(1,j-pivot),higher_low=int(prev_pivot is not None and last_pivot>prev_pivot),rsi=a,rsi_change=a-z if a is not None and z is not None else None,baseline_net_pct=r['net_pct'],immediate_exit_net=net(o[j+1]))
            for n in (3,6,12):row[f'prior_{n*5}m_short_pct']=100*(1-c[j]/c[j-n]) if j-n>=start else None
            for n in (1,2,3,6):
                # compare next-open execution after waiting n completed bars, capped by stop/reference exit
                t=j+1+n; value=None
                if t<=end:
                    value=float(r['net_pct']) if t>=x else net(o[t])
                row[f'wait_{n*5}m_net']=value
                row[f'wait_{n*5}m_delta']=value-row['immediate_exit_net'] if value is not None else None
            # independent retrospective close-path label; not a real-time decision or ground truth
            label='INCOMPLETE'
            if j+6<=end:
                label='MIXED'
                for k in range(j+1,j+7):
                    if c[k]<=c[j]*.997:label='CONTINUATION_FIRST';break
                    if c[k]>=c[j]*1.003:label='ADVERSE_FIRST';break
            row['future_label_RESEARCH_ONLY']=label
            rows.append(row)
    assert rows
    out=ROOT/'aimn_exp33_v_noise_anatomy_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('Events',len(rows),'episodes',len(set(r['signal_time'] for r in rows)),'unique timestamps',len(set(r['event_time'] for r in rows)))
    for label in sorted(set(r['future_label_RESEARCH_ONLY'] for r in rows)):
        g=[r for r in rows if r['future_label_RESEARCH_ONLY']==label];print(label,len(g), 'median recovery',round(st.median(r['recovery_pct'] for r in g),4))
    for name,g in [('profitable',[r for r in rows if r['net_at_event_close']>0]),('not profitable',[r for r in rows if r['net_at_event_close']<=0])]:
        print(name,len(g))
        for n in (5,10,15,30):
            v=[r[f'wait_{n}m_delta'] for r in g if r[f'wait_{n}m_delta'] is not None];print(n,len(v),round(st.mean(v),4) if v else None,sum(t>0 for t in v),sum(t<0 for t in v))
    print('Saved',out)
if __name__=='__main__':main()
