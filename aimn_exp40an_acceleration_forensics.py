#!/usr/bin/env python3
"""EXP40-AN: descriptive pre-peak acceleration, no trading changes."""
import json
from pathlib import Path
from collections import Counter, defaultdict
from statistics import median
import aimn_exp40ak_relative_v_leg_forensics as ak
ROOT=Path(__file__).resolve().parent
AM=ROOT/'kiss/results/exp40am_relative_trajectory_replay'
OUT=ROOT/'kiss/results/exp40an_acceleration_forensics'
HASHES={'aimn_exp40am_relative_trajectory_replay.py':'f19067752e1a917da0a277a9bf4e363e57632b9fced7eac8ce4f28a0c382b79f','aimn_exp40ak_relative_v_leg_forensics.py':'7caf8f2ef059179348754f75c16111429228b7f5c1d0657dc5e45fe0d4ab9e9f'}

def features(day,p):
    keys=['early3_velocity','recent3_velocity','delta3_velocity','recent6_velocity','recent12_velocity','peak_range_pct','peak_range_ratio','prior12_efficiency','prior12_lower_high','prior12_lower_low']
    f=dict.fromkeys(keys)
    c=lambda j:day[j]['close']
    vel=lambda a,b:100*(c(b)/c(a)-1)/(b-a)
    span=lambda j:100*(day[j]['high']-day[j]['low'])/day[j]['open']
    f['peak_range_pct']=span(p)
    if p>=3: f['recent3_velocity']=vel(p-3,p)
    if p>=6:
        f['early3_velocity']=vel(p-6,p-3)
        f['delta3_velocity']=f['recent3_velocity']-f['early3_velocity']
        f['recent6_velocity']=vel(p-6,p)
        ref=median(span(j) for j in range(p-6,p))
        f['peak_range_ratio']=span(p)/ref if ref>0 else None
    if p>=12:
        f['recent12_velocity']=vel(p-12,p)
        f['prior12_efficiency']=ak.efficiency([c(j) for j in range(p-12,p+1)],1)
        a=day[p-12:p-6]; b=day[p-6:p]
        f['prior12_lower_high']=int(max(r['high'] for r in b)<max(r['high'] for r in a))
        f['prior12_lower_low']=int(min(r['low'] for r in b)<min(r['low'] for r in a))
    return f

def outcome(t):
    if t is None:return 'UNTRADED'
    return 'WIN' if float(t['net_pnl_pct'])>0 else 'GIVEBACK' if float(t['best_close_pct'])>.2 else 'NO_FEE_CLOSE'

def main():
    if OUT.exists():raise FileExistsError(OUT)
    for name,h in HASHES.items():assert ak.digest(ROOT/name)==h,name
    refpath=ak.OUT/'v_leg_audit.csv'; ref=ak.read(refpath); assert len(ref)==174
    audit=[]; hashes={str(refpath.relative_to(ROOT)):ak.digest(refpath)}
    for period,rel,h,n,nw,na,nt,net in ak.SETS:
        src=ak.D/rel; assert ak.digest(src)==h
        rows=json.loads(src.read_bytes()); assert len(rows)==n
        days=defaultdict(list)
        for r in rows:days[r['timestamp'][:10]].append(r)
        index={r['timestamp']:(d,i) for d in days.values() for i,r in enumerate(d)}
        paths=[AM/f'{period}_AM3_{s}.csv' for s in ('trades','candidates','gate')]
        t,c,g=map(ak.read,paths)
        hashes.update({str(p.relative_to(ROOT)):ak.digest(p) for p in [src,*paths]})
        tm={r['signal_time']:r for r in t}; cm={r['signal_time']:r for r in c}; gm={r['signal_time']:r for r in g}
        pool=[r for r in ref if r['period']==period and r['status']=='AUTHORIZED']
        assert len(pool)==len(gm)==len(g)==na
        assert set(gm)=={r['resolution_time'] for r in pool}
        assert set(cm)=={s for s,r in gm.items() if r['decision']=='PASS'} and len(cm)==len(c)
        assert set(tm)=={s for s,r in cm.items() if r['status']=='SCHEDULED'} and len(tm)==len(t)
        assert (len(t),round(sum(float(r['net_pnl_pct']) for r in t),6))=={'JUN_AUG':(11,.181220),'SEP_OCT':(5,.322873),'NOV':(1,.442076)}[period]
        for r in pool:
            stamp=r['resolution_time']; day,i=index[r['warning_time']]; dd,j=index[stamp]; p=i-1
            assert day is dd and j==i+1 and p>=0 and day[p]['high']==float(r['original_peak'])
            tr=tm.get(stamp)
            audit.append(dict(period=period,warning_time=r['warning_time'],peak_time=day[p]['timestamp'],signal_time=stamp,aj1_outcome=r['trade_outcome'],am3_gate=gm[stamp]['decision'],am3_outcome=outcome(tr),am3_net_pct=float(tr['net_pnl_pct']) if tr else None,am3_best_close_pct=float(tr['best_close_pct']) if tr else None,w12_retracement=r['AUTH_W12_retracement'],**features(day,p)))
    assert len(audit)==65
    assert Counter(r['am3_outcome'] for r in audit)=={'WIN':11,'NO_FEE_CLOSE':5,'GIVEBACK':1,'UNTRADED':48}
    assert Counter(r['aj1_outcome'] for r in audit)=={'WIN':25,'NO_FEE_CLOSE':25,'GIVEBACK':8,'UNTRADED':7}
    groups=[]; keys=list(features([{'open':1,'high':1,'low':1,'close':1}],0))
    for strategy in ('aj1','am3'):
        for period in ('ALL','JUN_AUG','SEP_OCT','NOV'):
            for label in ('WIN','NO_FEE_CLOSE','GIVEBACK'):
                rr=[r for r in audit if r[strategy+'_outcome']==label and (period=='ALL' or r['period']==period)]
                stats={}
                for key in keys:
                    vals=[r[key] for r in rr if r[key] is not None]
                    stats[key]={'n':len(vals),'median':round(median(vals),6) if vals else None}
                groups.append(dict(strategy=strategy,period=period,outcome=label,count=len(rr),features=stats))
                if rr:print(strategy,period,label,len(rr),json.dumps({k:stats[k] for k in ('early3_velocity','recent3_velocity','delta3_velocity','peak_range_ratio','recent12_velocity')}))
    OUT.mkdir(parents=True,exist_ok=False); ak.write(OUT/'acceleration_audit.csv',audit)
    (OUT/'summary.json').write_text(json.dumps(dict(notes=['Discovery only. All 65 AJ1 authorizations; outcomes from separate actual AJ1 and AM3 replays.','Velocities are close-to-close percent per bar, ending at original peak. Two adjacent three-change windows share only boundary close. No cross-session history. Peak range normalized by median prior six candle ranges. Structural flags compare two preceding six-bar blocks excluding peak. Missing history is not imputed. No thresholds or new trades.'],source_hashes={**HASHES,**hashes},groups=groups),indent=2,allow_nan=False)+'\n')
    print('PASS: 65 authorizations, 58 AJ1 trades, 17 AM3 trades'); print('Saved:',OUT)
if __name__=='__main__':main()
