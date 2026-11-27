#!/usr/bin/env python3
"""EXP40-AJ: causal pending AE3 warnings; historical research only."""
import csv, json, hashlib
from pathlib import Path
from collections import Counter
from bisect import bisect_right
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'kiss/results/exp40aj_transition_monitoring_replay'
AI_HASH='a2af1e958a26bfd7696216180b4d8c7b4339de7f62126f27ffb6e3d3376aae65'
assert hashlib.sha256((ROOT/'aimn_exp40ai_early_transition_replay.py').read_bytes()).hexdigest()==AI_HASH
import aimn_exp40ai_early_transition_replay as ai
ab,aa,m,b,k,v,ae=ai.ab,ai.aa,ai.m,ai.b,ai.k,ai.v,ai.ae
VARIANTS=('AJ0','AJ1','AJ2','AJ3','AJ4')

def monitor(rows,early,s5,s30,name):
    """One pending warning; process each completed candle once in time order."""
    avail=[z['available_time'] for z in s30]
    signals={}; audit=[]; pending=None
    def resolve(status,i):
        nonlocal pending
        pending.update(status=status,resolution_time=rows[i]['timestamp'])
        pending=None
    for i,r in enumerate(rows):
        stamp=r['timestamp']; clock=stamp[11:16]
        had_pending=pending is not None
        if pending is not None:
            orig=pending['warning_index']; age=i-orig
            j=bisect_right(avail,s5[i]['available_time'])-1
            if stamp[:10]!=rows[orig]['timestamp'][:10] or clock>='15:30':
                resolve('SESSION_OR_CUTOFF',i)
            elif j<0 or s30[j]['st'] is None or s30[j]['trend']!='SHORT':
                resolve('MAJOR_CONTEXT_LOST',i)
            elif r['high']>=pending['original_peak']:
                resolve('PEAK_INVALIDATED',i)
            else:
                prev=rows[i-1]
                hh=r['high']<prev['high']; ll=r['low']<prev['low']; cc=r['close']<prev['close']
                yes=hh and (cc if name=='AJ1' else ll if name=='AJ2' else ll and cc)
                if yes:
                    signals[i]=dict(detector=name,warning_time=rows[orig]['timestamp'],delay_bars=age,st5=s5[i]['trend'],st30=s30[j]['trend'],major_available=s30[j]['available_time'])
                    pending['delay_bars']=age
                    resolve('AUTHORIZED',i)
                elif age>=(2 if name=='AJ4' else 1):
                    resolve('EXPIRED',i)
        if i in early:
            rec=dict(warning_time=stamp,warning_index=i,original_peak=rows[i-1]['high'],status='PENDING',resolution_time='',delay_bars=None)
            audit.append(rec)
            if clock>='15:30': rec.update(status='SESSION_OR_CUTOFF',resolution_time=stamp)
            elif had_pending: rec.update(status='OVERLAPPING_IGNORED',resolution_time=stamp)
            else: pending=rec
    if pending is not None: resolve('END_OF_DATA',len(rows)-1)
    assert len(audit)==len(early) and all(r['status']!='PENDING' for r in audit)
    assert len(signals)==sum(r['status']=='AUTHORIZED' for r in audit)
    return signals,audit

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    ab.check_sources()
    report=dict(notes=['All periods discovery; no orders or production changes.', 'AJ0 exact AI1 parity. AJ1-4 no post-entry W1/W3; frozen AA exits.', 'Pending monitoring independent of positions; engine blocks occupied authorization bars. Earliest pending warning owns window, even on resolution bar. No duplicate authorization.', 'Original peak touch cancels before confirmation; major ST must remain SHORT at each observed bar; local ST may turn SHORT. AJ4 second bar compares against immediately preceding bar.', 'All decisions use completed bars, next open execution; cutoff applies at authorization. Net trade sums not portfolio returns. Mixed warm-up feed provenance unverified.'],source_hashes={**ab.HASHES,**ai.HASHES,'aimn_exp40ai_early_transition_replay.py':AI_HASH},periods={},combined={})
    results={}; audits={}; prior=[]
    expected={'JUN_AUG':(104,75,-10.329582),'SEP_OCT':(57,32,-4.100103),'NOV':(13,11,-2.568494)}
    for period,src,sha,n,cp,tp,nc,nt,net in ae.ad.SETS:
        data=m.load(src,sha); v.validate_rows(data,n,data[0]['timestamp'],data[-1]['timestamp'])
        warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec') if period=='NOV' else prior
        rows=warm+data; start=data[0]['timestamp']; prior=rows
        assert [r['timestamp'] for r in rows]==sorted({r['timestamp'] for r in rows})
        s5=m.snapshots(rows,5); s30=m.snapshots(m.aggregate(rows),30); early=ai.focus(rows,start,s5)
        assert len(early)==expected[period][0]
        report['periods'][period]={}
        for name in VARIANTS:
            signals,audit=(early,[]) if name=='AJ0' else monitor(rows,early,s5,s30,name)
            t,ev,op,a=aa.replay(rows,True,lambda i:(True,dict(signals[i])),True,True,True,warning='bullish_upper_close',entry_detector=lambda i:i in signals,supplemental='higher_high')
            ai.check(t,a,op,start,{rows[i]['timestamp'] for i in signals})
            if name=='AJ0':
                for suffix,rr in [('trades',t),('candidates',a)]: k.e.verify_csv(rr,ai.OUT/f'{period}_AI1_{suffix}.csv')
                assert (len(t),b.summary(t)['net_sum_pct'])==expected[period][1:]
            results[period,name]=(t,a); audits[period,name]=audit
            report['periods'][period][name]=dict(**ab.metrics(t),authorizations=len(signals),warning_statuses=dict(Counter(z['status'] for z in audit)),candidate_statuses=dict(Counter(z['status'] for z in a)),events=ev)
        print(period,'AI1 parity PASSED',flush=True)
    for name in VARIANTS:
        t=[r for (p,n),(tt,a) in results.items() if n==name for r in tt]
        report['combined'][name]=dict(**ab.metrics(t),warning_statuses=dict(Counter(r['status'] for (p,n),rr in audits.items() if n==name for r in rr)))
    OUT.mkdir(parents=True,exist_ok=False)
    for (period,name),(t,a) in results.items():
        v.write_csv(OUT/f'{period}_{name}_trades.csv',t); v.write_csv(OUT/f'{period}_{name}_candidates.csv',a)
        if name!='AJ0': v.write_csv(OUT/f'{period}_{name}_warnings.csv',audits[period,name])
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    for period,group in report['periods'].items():
        for name,s in group.items(): print(period,name,json.dumps({key:s[key] for key in ('trades','winners','losers','net_sum_pct','authorizations','warning_statuses')}))
    print('COMBINED',json.dumps(report['combined'],indent=2)); print('Saved:',OUT)
if __name__=='__main__': main()
