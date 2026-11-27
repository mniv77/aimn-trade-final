#!/usr/bin/env python3
"""EXP40-AI: causal AE3 entry replay, historical discovery only."""
import csv, json, hashlib
from pathlib import Path
from collections import Counter, defaultdict
from bisect import bisect_right
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'kiss/results/exp40ai_early_transition_replay'
HASHES={
 'aimn_exp40ab_historical_robustness.py':'fac91ea9ae3a84b3754881a29d6ad978af443168256d450d098234082295ecb4',
 'aimn_exp40ac_structural_position_forensics.py':'d116ea188cad9703eb7050b811156b798bad49d8063caccda0255a2eefeee85f',
 'aimn_exp40ad_sequential_trajectory_forensics.py':'d44e26696a89e94f0233bb612804a0d48b32fadf13451bf574d4126bfeb40380',
 'aimn_exp40ae_early_transition_forensics.py':'94fffebd4f8ac9be3436aced9cfe1b3e7526d37ca1eba18cd7522a7b27ade2f6'}
for name,sha in HASHES.items():
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:
        raise ValueError(f'Source mismatch: {name}')
import aimn_exp40ab_historical_robustness as ab
import aimn_exp40ae_early_transition_forensics as ae
from aimn_exp40ab_historical_robustness import aa,u,x,m,b,k,v
POLICIES={'AI1':None,'AI2':'W1','AI3':'W3'}

def focus(rows,start,s5):
    s30=m.snapshots(m.aggregate(rows),30)
    avail=[s['available_time'] for s in s30]
    days=defaultdict(list)
    for i,r in enumerate(rows):
        if r['timestamp']>=start: days[r['timestamp'][:10]].append(i)
    result={}
    for indices in days.values():
        day=[rows[i] for i in indices]
        for j,i in enumerate(indices):
            if 'AE3' not in ae.detectors(day,j): continue
            s=s5[i]; z=bisect_right(avail,s['available_time'])-1
            if s['st'] is not None and s['trend']=='LONG' and z>=0 and s30[z]['st'] is not None and s30[z]['trend']=='SHORT':
                result[i]=dict(detector='AE3',st5='LONG',st30='SHORT',major_available=s30[z]['available_time'])
    return result

def check(t,a,op,start,signals):
    assert op is None
    assert {r['signal_time'] for r in a}==signals and len(a)==len(signals)
    assert {r['signal_time'] for r in t}=={r['signal_time'] for r in a if r['status']=='SCHEDULED'}
    assert all(r['signal_time']>=start and r['entry_time']>=start and not r['overnight'] and r['signal_time'][:10]==r['entry_time'][:10] and r['signal_time'][11:16]<'15:30' and r['exit_time'][11:16]<='15:55' for r in t)

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    ab.check_sources()
    with (ae.OUT/'warning_audit.csv').open(newline='') as f:
        reference=[r for r in csv.DictReader(f) if r['detector']=='AE3' and r['context']=='LONG/SHORT']
    assert len(reference)==174
    report=dict(notes=['All periods are discovery; no orders or production changes.', 'AE3 does not use future matching, Q4 or AH filters. All exits and session protections are frozen AA logic.', 'Net trade sums are not portfolio returns. Extra costs are arithmetic sensitivity.', 'June–August warm-up feed provenance is unverified.'],source_hashes={**ab.HASHES,**HASHES},reference_hashes={},periods={},combined={})
    results={}; prior=[]
    for period,src,sha,n,cp,tp,nc,nt,net in ae.ad.SETS:
        data=m.load(src,sha)
        v.validate_rows(data,n,data[0]['timestamp'],data[-1]['timestamp'])
        warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec') if period=='NOV' else prior
        rows=warm+data; start=data[0]['timestamp']; prior=rows
        assert [r['timestamp'] for r in rows]==sorted({r['timestamp'] for r in rows})
        s5=m.snapshots(rows,5); feat,total=u.features(rows,start)
        entry,policy,extra,_=aa.POLICIES['AA1']
        t,ev,op,a=aa.replay(rows,True,u.gate_for(feat,entry),True,True,True,warning='bullish_upper_close',entry_detector=lambda i:i in feat,invalidation=x.invalidator(rows,s5,policy),supplemental=extra)
        check(t,a,op,start,{rows[i]['timestamp'] for i in feat})
        k.e.verify_csv(t,tp); k.e.verify_csv(a,cp)
        assert (len(t),b.summary(t)['net_sum_pct'])==(nt,net)
        for p in (cp,tp): report['reference_hashes'][str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        results[period,'AI0']=(t,a,ev)
        early=focus(rows,start,s5); stamps={rows[i]['timestamp'] for i in early}
        expected={r['signal_time'] for r in reference if r['period']==period}
        assert stamps==expected and len(stamps)=={'JUN_AUG':104,'SEP_OCT':57,'NOV':13}[period]
        for name,policy in POLICIES.items():
            t,ev,op,a=aa.replay(rows,True,lambda i:(True,dict(early[i])),True,True,True,warning='bullish_upper_close',entry_detector=lambda i:i in early,invalidation=x.invalidator(rows,s5,policy) if policy else None,supplemental='higher_high')
            check(t,a,op,start,stamps)
            results[period,name]=(t,a,ev)
        report['periods'][period]={}
        for name in ('AI0',*POLICIES):
            t,a,ev=results[period,name]
            report['periods'][period][name]=dict(**ab.metrics(t),candidates=len(a),statuses=dict(Counter(r['status'] for r in a)),events=ev,splits={mm:ab.metrics([r for r in t if r['signal_time'][5:7]==mm]) for mm in sorted({r['timestamp'][5:7] for r in data})})
        print(period,'benchmark parity PASSED; AE3 timestamp parity PASSED',len(stamps),flush=True)
    for name in ('AI0',*POLICIES):
        t=[r for (p,n),(tt,a,ev) in results.items() if n==name for r in tt]
        report['combined'][name]=ab.metrics(t)
    OUT.mkdir(parents=True,exist_ok=False)
    for (period,name),(t,a,ev) in results.items():
        v.write_csv(OUT/f'{period}_{name}_trades.csv',t); v.write_csv(OUT/f'{period}_{name}_candidates.csv',a)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    for period,group in report['periods'].items():
        for name,s in group.items(): print(period,name,json.dumps({key:s[key] for key in ('trades','winners','losers','net_sum_pct','gross_sum_pct','exits','extra_cost_net_pct')}))
    print('COMBINED',json.dumps(report['combined'],indent=2))
    print('Saved:',OUT)

if __name__=='__main__': main()
