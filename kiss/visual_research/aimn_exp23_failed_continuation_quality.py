"""Offline EXP23: failed continuation quality; fixed EXP22 execution model."""
import csv,json
from pathlib import Path
from datetime import datetime,timedelta
from statistics import mean
ROOT=Path(__file__).resolve().parent
FEE=.001; STOP=.01; REBOUND=.0015; STEP=timedelta(minutes=5)
POLICIES=('baseline','warning','higher_low','breakout','adaptive','fdc1','fdc2','fdc3','fdc4','fdc5','quality_rebound','quality_higher_low','quality_profit','quality_rsi')
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
        p=v(e,'open'); stop=p*(1+STOP); low=p; phase=0; peak=None; pull=None; exits={}; pending={}; best=p; events={}; last_low=e; attempts=0; in_pullback=False; attempt_lows=[]; event_features={}
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
            # Count distinct downward attempts after a recovery, using closed bars only.
            if l<low:
                last_low=i; attempts=0; in_pullback=False; attempt_lows=[]
            elif i>e:
                if c>v(i-1,'close'):
                    in_pullback=False
                elif c<v(i-1,'close') and not in_pullback and l<=low*1.003:
                    attempts+=1; in_pullback=True; attempt_lows.append(l)
                elif in_pullback and attempt_lows and c<v(i-1,'close'):
                    attempt_lows[-1]=min(attempt_lows[-1],l)
            age=i-last_low
            rebound=c>=min(low,l)*(1+REBOUND)
            fdc1=age>=2
            fdc2=age>=3
            fdc3=attempts>=2
            fdc4=age>=2 and rebound
            recovery_pct=100*(c/min(low,l)-1)
            higher_attempt=len(attempt_lows)>=2 and attempt_lows[-1]>attempt_lows[-2]
            changes=[v(j,'close')-v(j-1,'close') for j in range(max(1,i-13),i+1)] if i>=14 else []
            gains=sum(max(0,x) for x in changes); losses=sum(max(0,-x) for x in changes)
            rsi=100*gains/(gains+losses) if gains+losses else 50
            acceleration=100*((c-v(i-1,'close'))-(v(i-1,'close')-v(i-2,'close')))/v(i-1,'close') if i>=2 else 0
            if fdc3 and not event_features:
                event_features=dict(first_fdc3_time=audit[i]['timestamp_ny'],first_fdc3_recovery_pct=recovery_pct,first_fdc3_age=age,first_fdc3_higher_attempt=int(higher_attempt),first_fdc3_rsi=rsi,first_fdc3_acceleration_pct=acceleration,first_fdc3_net_pct=net(p,c))
            fdc5=(fdc4 and net(p,c)>0) or (fdc3 and rebound) or (age>=3 and rebound)
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
            flags.update(fdc1=fdc1,fdc2=fdc2,fdc3=fdc3,fdc4=fdc4,fdc5=fdc5,quality_rebound=fdc3 and rebound,quality_higher_low=fdc3 and higher_attempt and rebound,quality_profit=fdc3 and (net(p,c)>0 or rebound),quality_rsi=fdc3 and rebound and rsi>=40)
            for policy,flag in flags.items():
                if policy not in exits and flag: pending.setdefault(policy,policy.upper())
            if i==end:
                for policy in POLICIES:
                    if policy not in exits: exits[policy]=(i,c,'SESSION_OR_NEXT_SIGNAL_BOUNDARY',best)
        row=dict(episode=n+1,split=audit[s]['split'],entry_signal_time=audit[s]['timestamp_ny'],entry_time=audit[e]['timestamp_ny'],entry_price=p)
        row.update({k:event_features.get(k,'') for k in ('first_fdc3_time','first_fdc3_recovery_pct','first_fdc3_age','first_fdc3_higher_attempt','first_fdc3_rsi','first_fdc3_acceleration_pct','first_fdc3_net_pct')})
        for label in ('warning','higher_low','breakout'): row[label+'_first_signal']=events.get(label,'')
        for policy in POLICIES:
            i,q,reason,best_seen=exits[policy]
            row.update({policy+'_exit_time':audit[i]['timestamp_ny'],policy+'_reason':reason,policy+'_net_pct':net(p,q),policy+'_giveback_pct':max(0,net(p,best_seen)-net(p,q))})
        rows.append(row)
    if not rows: raise ValueError('No episodes')
    out=ROOT/'aimn_exp23_failed_continuation_quality_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for label,g in [('ALL',rows)]+[(s,[r for r in rows if r['split']==s]) for s in sorted({r['split'] for r in rows})]:
        print(label,len(g))
        for k in POLICIES: print(k,round(mean(r[k+'_net_pct'] for r in g),4),sum(r[k+'_net_pct']>0 for r in g),round(mean(r[k+'_giveback_pct'] for r in g),4),sum(r[k+'_reason'].startswith('STOP') for r in g))
    print('Saved',out)
if __name__=='__main__': main()
