"""Offline EXP21: fixed-entry, first-event exit policy comparison."""
import csv,json
from pathlib import Path
from datetime import datetime,timedelta
from statistics import mean
ROOT=Path(__file__).resolve().parent
FEE=.001; STOP=.01; REBOUND=.0015; STEP=timedelta(minutes=5)
POLICIES=('baseline','warning','higher_low','breakout','adaptive')
def net(p,q): return 100*(p-q-FEE*(p+q))/p

def main():
    bars=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda b:b['timestamp'])
    with (ROOT/'aimn_exp19_trend_position_audit.csv').open(newline='',encoding='utf-8-sig') as f: audit=list(csv.DictReader(f))
    ts=[datetime.fromisoformat(b['timestamp']) for b in bars]
    if len(bars)!=len(audit) or len(set(ts))!=len(ts): raise ValueError('Alignment error')
    for t,b,r in zip(ts,bars,audit):
        if t.strftime('%Y-%m-%d %H:%M')!=r['timestamp_ny'] or abs(float(b['close'])-float(r['close']))>1e-5: raise ValueError('Mismatch '+str(t))
    def v(i,k): return float(bars[i][k])
    signals=[i for i,r in enumerate(audit) if r['entry_signal']=='1']; rows=[]
    for n,s in enumerate(signals):
        e=s+1
        if e>=len(bars) or ts[e]-ts[s]!=STEP: continue
        end=e
        while end+1<len(bars) and ts[end+1]-ts[end]==STEP and (n+1==len(signals) or end+1<signals[n+1]): end+=1
        p=v(e,'open'); stop=p*(1+STOP); low=p; phase=0; peak=None; pull=None; exits={}; pending={}; best=p; events={}
        for i in range(e,end+1):
            o,h,l,c=(v(i,k) for k in ('open','high','low','close'))
            for policy in POLICIES:
                if policy in exits: continue
                if o>=stop: exits[policy]=(i,o,'STOP_GAP',best)
                elif policy in pending: exits[policy]=(i,o,pending[policy],min(best,o))
                elif h>=stop: exits[policy]=(i,stop,'STOP_TOUCH',best)
            if len(exits)==len(POLICIES): break
            best=min(best,l)
            warning=hl=br=False
            # A new low resets the pattern; do not infer intrabar ordering.
            if l<low:
                low=l; phase=0; peak=pull=None
            elif phase==0 and c>=low*(1+REBOUND):
                phase=1; peak=h; warning=True
            elif phase==1:
                if c<v(i-1,'close') and l>low:
                    phase=2; pull=l
                else: peak=max(peak,h)
            elif phase==2:
                pull=min(pull,l)
                if c>v(i-1,'high') and pull>low:
                    phase=3; hl=True
            elif phase==3 and c>peak:
                phase=4; br=True
            for label,flag in [('warning',warning),('higher_low',hl),('breakout',br)]:
                if flag: events.setdefault(label,audit[i]['timestamp_ny'])
            flags={'baseline':audit[i]['reverse_signal']=='1','warning':warning,'higher_low':hl,'breakout':br,'adaptive':br or ((warning or hl) and net(p,c)>0)}
            for policy,flag in flags.items():
                if policy not in exits and flag: pending.setdefault(policy,policy.upper())
            if i==end:
                for policy in POLICIES:
                    if policy not in exits: exits[policy]=(i,c,'SESSION_OR_NEXT_SIGNAL_BOUNDARY',best)
        row=dict(episode=n+1,split=audit[s]['split'],entry_signal_time=audit[s]['timestamp_ny'],entry_time=audit[e]['timestamp_ny'],entry_price=p)
        for label in ('warning','higher_low','breakout'): row[label+'_first_signal']=events.get(label,'')
        for policy,(i,q,reason,best_seen) in exits.items():
            row.update({policy+'_exit_time':audit[i]['timestamp_ny'],policy+'_reason':reason,policy+'_net_pct':net(p,q),policy+'_giveback_pct':max(0,net(p,best_seen)-net(p,q))})
        rows.append(row)
    if not rows: raise ValueError('No episodes')
    out=ROOT/'aimn_exp21_reverse_anatomy_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for label,g in [('ALL',rows)]+[(s,[r for r in rows if r['split']==s]) for s in sorted({r['split'] for r in rows})]:
        print(label,len(g))
        for k in POLICIES: print(k,round(mean(r[k+'_net_pct'] for r in g),4),sum(r[k+'_net_pct']>0 for r in g),round(mean(r[k+'_giveback_pct'] for r in g),4))
    print('Saved',out)
if __name__=='__main__': main()
