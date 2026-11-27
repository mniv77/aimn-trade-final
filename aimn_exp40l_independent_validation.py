"""EXP40-L: frozen temporal holdout replay. No orders or production writes."""
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
import aimn_exp40k_structural_reversal_replay as k

b,d,e,g = k.b,k.d,k.e,k.g
ROOT=b.ROOT
OUT=ROOT/'kiss/results/exp40l_independent_validation'
WARM=ROOT/'kiss/visual_research/independent_holdout_exp144/nvda_nov_2026_5m_iex.json'
TEST=ROOT/'kiss/visual_research/independent_holdout_exp40l/nvda_2026-11-16_2026-11-25_5m_iex.json'
START='2026-11-16 09:30:00'
HASHES={
'aimn_exp40b_causal_replay.py':'f43fb8b676bb48b2ecbc77477ae775a1079095feb5b35347d3697cb4c8c22651',
'aimn_exp40d_deceleration_replay.py':'7faa4f24454fcbce64f5dd1ab016322c472622185f89200bb9995ae3fb0e88b3',
'aimn_exp40e_adaptive_trajectory.py':'3db3ba5947c4848daedc3837fd3de37ab34aa1014463bfb43c3a8a09775b8ada',
'aimn_exp40f_opening_session_forensics.py':'075c3eee0a345f465e3ad092c13fa87825818acd3e47a387ec3d5fe2b8a44cf0',
'aimn_exp40g_prior_session_replay.py':'75a192b814df8e01a76993ddb800a7a8182c092720bbd4f916234d0a11c06206',
'aimn_exp40h_session_protection.py':'7f546b190ddb76aeb0b7244f17ddcd7c5c6d57a5c1eaed83e660c160380535a6',
'aimn_exp40k_structural_reversal_replay.py':'36bab76860e192d3d8529efa1ce6b90c1171cee238f992fc277bc193f98c2f1f'}

def checked(path, digest):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError(f'Frozen hash mismatch: {path}')
    return raw

def validate_rows(rows, count, first, last):
    if len(rows)!=count or rows[0]['timestamp']!=first or rows[-1]['timestamp']!=last:
        raise ValueError('Unexpected candle count or dates')
    sessions={}
    prev=None
    for r in rows:
        t=datetime.fromisoformat(r['timestamp'])
        if prev is not None and t<=prev: raise ValueError('Unsorted/duplicate candles')
        prev=t
        sessions.setdefault(t.date(),[]).append(t)
        o,h,l,c=(float(r[x]) for x in ('open','high','low','close'))
        if not(all(math.isfinite(v) and v>0 for v in (o,h,l,c)) and l<=min(o,c)<=max(o,c)<=h):
            raise ValueError('Invalid OHLC')
    for day,ts in sessions.items():
        if len(ts)!=78 or ts[0].strftime('%H:%M:%S')!='09:30:00' or ts[-1].strftime('%H:%M:%S')!='15:55:00' or any(z-a!=timedelta(minutes=5) for a,z in zip(ts,ts[1:])):
            raise ValueError(f'Unsupported session {day}')
    return [str(day) for day in sessions]

def gate_for(rows, start=None):
    full,short,prior=d.features(rows),e.short_features(rows),g.prior_features(rows)
    def gate(i):
        x={**full(i),**short(i)}
        allowed,policy=e.decision('E1_FULL_ONLY',x)
        kind='FULL' if x['rise_delta'] is not None else 'SHORT_ONLY' if x['short_rise_delta'] is not None else 'EARLIEST'
        x.update(history_type=kind,policy_used=policy)
        pv=prior(i)
        if kind=='EARLIEST':
            allowed=g.opening_decision('G1_PRIOR_30M',pv); x['policy_used']='G1_PRIOR_30M'
        x.update(**pv,opening_policy='G1_PRIOR_30M' if kind=='EARLIEST' else 'NOT_APPLICABLE')
        return allowed and (start is None or rows[i]['timestamp']>=start),x
    return gate

def run(rows, name, start=None):
    if name=='B2':
        # K's unchanged stop/exit path with unrestricted entries reproduces B2.
        # A gate suppresses warm-up entries without touching indicator history.
        return k.replay(rows,True,lambda i:(start is None or rows[i]['timestamp']>=start,{}))
    return k.replay(rows,True,gate_for(rows,start),True,True,True,
                    warning='bullish_upper_close' if name=='K3' else None)

def write_csv(path, rows):
    with path.open('x',newline='') as fp:
        if rows:
            writer=csv.DictWriter(fp,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

def main():
    if OUT.exists(): raise FileExistsError(f'Refusing overwrite: {OUT}')
    for name,digest in HASHES.items(): checked(ROOT/name,digest)
    engine=Path(k.base.__file__).read_bytes()
    if hashlib.sha1(b'blob '+str(len(engine)).encode()+b'\0'+engine).hexdigest()!=b.ENGINE_BLOB:
        raise ValueError('Frozen engine mismatch')
    discovery=json.loads(checked(b.DATA,b.DATA_HASH))
    names=('B2','H4','K3')
    baseline={}
    for name in names:
        t,ev,op,a=run(discovery,name)
        if name=='B2':
            original,original_ev,original_op=b.replay(discovery,True)
            if t!=original or op!=original_op: raise ValueError('B2 engine parity failure')
            source=b.OUTPUT/'B2_trades.csv'
            checked(source,'47ab2a8fe9cd84d50ccad567397830ae9ffbd46cd6628f513bbff64ade14f109')
            e.verify_csv(t,source)
        else:
            prefix='K0_H4' if name=='H4' else 'K3_BULLISH_UPPER_CLOSE'
            e.verify_csv(t,k.OUT/f'{prefix}_trades.csv')
            e.verify_csv(a,k.OUT/f'{prefix}_candidates.csv')
            if name=='H4':
                source=k.baseline.OUT/'H4_CUTOFF_trades.csv'
                checked(source,'41fbfbc9ebc89b3a12febbced0277898f30ed35bd1f9b0cba14dbbc4f4e1de87')
                e.verify_csv(t,source)
        expected={'B2':(122,-30.391587),'H4':(32,-.672133),'K3':(32,-.199296)}[name]
        s=b.summary(t)
        if (s['trades'],s['net_sum_pct'])!=expected or op is not None: raise ValueError(f'{name} discovery parity failure')
        baseline[name]=s
    warm=json.loads(checked(WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec'))
    test=json.loads(checked(TEST,'eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d'))
    validate_rows(warm,780,'2026-11-02 09:30:00','2026-11-13 15:55:00')
    days=validate_rows(test,624,START,'2026-11-25 15:55:00')
    if days!=['2026-11-'+str(day) for day in (16,17,18,19,20,23,24,25)]: raise ValueError('Unexpected validation sessions')
    if discovery[-1]['timestamp']>=warm[0]['timestamp'] or warm[-1]['timestamp']>=START: raise ValueError('Date overlap')
    report={'notes':['Temporal holdout, prior research usage not independently verified; IEX feed comparability unverified.', 'No warm-up entries; indicators use all 780 warm-up bars.', 'B2 uses K replay with unrestricted validation entry gate, exact discovery parity against original B2.', 'Cost scenarios subtract additional round-trip percentage points from completed trades; not a fill/slippage simulation.', 'Open B2 exposure is reported separately, with mark to final close, not a claimed fill.', 'Trade sums are not portfolio returns. No parameter optimization.'], 'source_hashes':HASHES,'warmup_sha256':hashlib.sha256(WARM.read_bytes()).hexdigest(),'validation_sha256':hashlib.sha256(TEST.read_bytes()).hexdigest(),'discovery_parity':baseline,'validation_days':days,'variants':{}}
    results={}
    for name in names:
        t,ev,op,a=run(warm+test,name,START)
        if any(x['signal_time']<START or x['entry_time']<START for x in t) or (op and op['entry_time']<START): raise ValueError('Warm-up trade leak')
        if name!='B2' and (op or any(x['overnight'] or x['signal_time'][:10]!=x['entry_time'][:10] for x in t)): raise ValueError('Session protection failure')
        a=[x for x in a if x['signal_time']>=START]
        s=b.summary(t)
        costs={}
        for cost in (0,.02,.05,.10):
            vals=[x['net_pnl_pct']-cost for x in t]
            net=round(sum(vals),6)
            costs[f'{cost:.2f}']={'closed_net_sum_pct':net,'winners':sum(v>0 for v in vals),'break_even':sum(v==0 for v in vals),'losers':sum(v<0 for v in vals),'net_with_open_mark_pct':round(net+(op['marked_net_pct']-cost if op else 0),6)}
        report['variants'][name]={**s,'validation_candidates':len(a),'candidate_statuses':dict(k.Counter(x['status'] for x in a)),'overnight_trades':sum(x['overnight'] for x in t),'open_position':op,'additional_round_trip_cost_pct':costs}
        results[name]=(t,a)
    OUT.mkdir(parents=True,exist_ok=False)
    for name,(t,a) in results.items():
        write_csv(OUT/f'{name}_trades.csv',t); write_csv(OUT/f'{name}_candidates.csv',a)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
