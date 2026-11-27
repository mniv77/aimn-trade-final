#!/usr/bin/env python3
"""EXP40-AM: causal AJ1 retracement gate; research only."""
import json, hashlib
from pathlib import Path
from collections import Counter, defaultdict
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'kiss/results/exp40am_relative_trajectory_replay'
HASHES={'aimn_exp40aj_transition_monitoring_replay.py':'b6dc48d9f33b59f4f2ea6f388357d1ddb34138ba80dfec3649f5043f74f9a05f','aimn_exp40ak_relative_v_leg_forensics.py':'7caf8f2ef059179348754f75c16111429228b7f5c1d0657dc5e45fe0d4ab9e9f','aimn_exp40al_trajectory_discrimination.py':'b5e7760020314ee1ebdd23d23c99358db97c880b74f4637b48fa5133d7efe5ac'}
for name,h in HASHES.items(): assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
import aimn_exp40aj_transition_monitoring_replay as aj
import aimn_exp40ak_relative_v_leg_forensics as ak
ai,ab,aa,m,b,k,v,ae=aj.ai,aj.ab,aj.aa,aj.m,aj.b,aj.k,aj.v,aj.ae
POLICIES={'AM0':None,'AM1':(6,.6),'AM2':(12,.5),'AM3':(12,.6),'AM4':(12,.7)}

def features(rows,signals):
    days=defaultdict(list); index={}
    for r in rows:
        day=days[r['timestamp'][:10]]; index[r['timestamp']]=(day,len(day)); day.append(r)
    out={}
    for i,s in signals.items():
        day,j=index[rows[i]['timestamp']]; dd,w=index[s['warning_time']]
        assert day is dd and j==w+1 and w>=1
        out[i]={n:ak.features(day,w-1,j,n)['retracement'] for n in (6,12)}
    return out

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    ab.check_sources()
    reference=ak.read(ak.OUT/'v_leg_audit.csv')
    assert len(reference)==174
    report={'notes':['All periods discovery; thresholds selected from AL historical subsets. No orders or production changes.','AM0 exact AJ1 parity. AM1-4 filter all AJ1 authorizations using completed authorization candle; missing history rejected. Frozen AA exits, next open execution, no W1/W3. Pending monitor independent of position.','Net trade sums are not portfolio returns; warm-up feed provenance unverified.'], 'source_hashes':{**ab.HASHES,**ai.HASHES,**ak.HASHES,**HASHES},'periods':{},'combined':{}}
    results={}; gates={}; prior=[]
    expected={'JUN_AUG':(104,38,34,-4.827365),'SEP_OCT':(57,20,17,-.243471),'NOV':(13,7,7,-2.107753)}
    for period,src,sha,n,cp,tp,nc,nt,net in ae.ad.SETS:
        data=m.load(src,sha); v.validate_rows(data,n,data[0]['timestamp'],data[-1]['timestamp'])
        warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec') if period=='NOV' else prior
        rows=warm+data; prior=rows; start=data[0]['timestamp']
        assert [r['timestamp'] for r in rows]==sorted({r['timestamp'] for r in rows})
        s5=m.snapshots(rows,5); s30=m.snapshots(m.aggregate(rows),30); early=ai.focus(rows,start,s5)
        signals,audit=aj.monitor(rows,early,s5,s30,'AJ1'); f=features(rows,signals)
        assert (len(early),len(signals))==expected[period][:2]
        k.e.verify_csv(audit,aj.OUT/f'{period}_AJ1_warnings.csv')
        ref={r['resolution_time']:r for r in reference if r['period']==period and r['status']=='AUTHORIZED'}
        assert set(ref)=={rows[i]['timestamp'] for i in signals}
        for i,vals in f.items():
            for w,val in vals.items():
                old=ref[rows[i]['timestamp']][f'AUTH_W{w}_retracement']
                assert (val is None and old=='') or (val is not None and old!='' and abs(val-float(old))<1e-12)
        report['periods'][period]={}
        for name,rule in POLICIES.items():
            selected={}; gateaudit=[]
            for i,s in signals.items():
                value=f[i][rule[0]] if rule else None
                status='PASS' if not rule or (value is not None and value>=rule[1]) else 'MISSING' if value is None else 'BELOW_THRESHOLD'
                gateaudit.append(dict(signal_time=rows[i]['timestamp'],warning_time=s['warning_time'],w6=f[i][6],w12=f[i][12],decision=status))
                if status=='PASS': selected[i]=dict(s)
            t,ev,op,a=aa.replay(rows,True,lambda i:(True,dict(selected[i])),True,True,True,warning='bullish_upper_close',entry_detector=lambda i:i in selected,supplemental='higher_high')
            ai.check(t,a,op,start,{rows[i]['timestamp'] for i in selected})
            if name=='AM0':
                for suffix,rr in [('trades',t),('candidates',a)]: k.e.verify_csv(rr,aj.OUT/f'{period}_AJ1_{suffix}.csv')
                assert (len(t),b.summary(t)['net_sum_pct'])==expected[period][2:]
            results[period,name]=(t,a); gates[period,name]=gateaudit
            report['periods'][period][name]=dict(**ab.metrics(t),authorizations=len(selected),gate_statuses=dict(Counter(r['decision'] for r in gateaudit)),candidate_statuses=dict(Counter(r['status'] for r in a)),events=ev)
        print(period,'AJ1 and AK feature parity PASSED',flush=True)
    for name in POLICIES:
        t=[r for (p,n),(tt,a) in results.items() if n==name for r in tt]
        report['combined'][name]=dict(**ab.metrics(t),gate_statuses=dict(Counter(r['decision'] for (p,n),rr in gates.items() if n==name for r in rr)))
    assert report['combined']['AM0']['net_sum_pct']==-7.178589
    OUT.mkdir(parents=True,exist_ok=False)
    for (period,name),(t,a) in results.items():
        v.write_csv(OUT/f'{period}_{name}_trades.csv',t); v.write_csv(OUT/f'{period}_{name}_candidates.csv',a); v.write_csv(OUT/f'{period}_{name}_gate.csv',gates[period,name])
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    for period,group in report['periods'].items():
        for name,s in group.items(): print(period,name,json.dumps({key:s[key] for key in ('trades','winners','losers','net_sum_pct','authorizations','gate_statuses')}))
    print('COMBINED',json.dumps(report['combined'],indent=2)); print('Saved:',OUT)
if __name__=='__main__': main()
