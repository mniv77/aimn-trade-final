#!/usr/bin/env python3
"""EXP40-AB: frozen historical robustness test; no orders or production writes."""
import hashlib, json, sys, platform
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'kiss/results/exp40ab_historical_robustness'
HASHES={'aimn_exp40aa_reverse_transition_replay.py': '45aaab70cd3436b2dac18988dd7d0abbbdb2a09c47a9857c3d8fdda542b100b6',
 'aimn_exp40b_causal_replay.py': 'f43fb8b676bb48b2ecbc77477ae775a1079095feb5b35347d3697cb4c8c22651',
 'aimn_exp40c_trajectory_forensics.py': '8aa1f6361efdc8fb17b19594a8fe4470d5de52c170fff30fa21181310f7bcba4',
 'aimn_exp40d_deceleration_replay.py': '7faa4f24454fcbce64f5dd1ab016322c472622185f89200bb9995ae3fb0e88b3',
 'aimn_exp40e_adaptive_trajectory.py': '3db3ba5947c4848daedc3837fd3de37ab34aa1014463bfb43c3a8a09775b8ada',
 'aimn_exp40f_opening_session_forensics.py': '075c3eee0a345f465e3ad092c13fa87825818acd3e47a387ec3d5fe2b8a44cf0',
 'aimn_exp40g_prior_session_replay.py': '75a192b814df8e01a76993ddb800a7a8182c092720bbd4f916234d0a11c06206',
 'aimn_exp40h_session_protection.py': '7f546b190ddb76aeb0b7244f17ddcd7c5c6d57a5c1eaed83e660c160380535a6',
 'aimn_exp40i_profit_preservation.py': 'a86572dbea2b61bc618e91ba3259b609b911bf555330fc5e2963d83f267efa9e',
 'aimn_exp40j_reverse_transition_forensics.py': '472ab234a33dbe7588fd2fa8ef5fce1fd25221ced9a95e61fca8cd519a29bb39',
 'aimn_exp40k_structural_reversal_replay.py': '36bab76860e192d3d8529efa1ce6b90c1171cee238f992fc277bc193f98c2f1f',
 'aimn_exp40l_alpaca_validation_downloader.py': 'fe62b98873200dbc576d44a410c6166a78a395809aa893e65abbfbe3e70b3c20',
 'aimn_exp40l_independent_validation.py': '964e924ba5ef3a48dac8e16c6da3c1b0615a6b1a8038a04b6f4f3183a391ff0e',
 'aimn_exp40m_supertrend_forensics.py': '804e4c90b2993679638dc7ae1a2b99c89f1bd1ddc2dbb2e91e5f974bf0232e1b',
 'aimn_exp40n_supertrend_trajectory_forensics.py': '613fc04ad377b1c7af38a9f4c995ef0bf1271f8958da2c1f2a20be84810286a8',
 'aimn_exp40o_transition_recognition_forensics.py': 'c20a2872c8b3ff244dabe03ca8453e0518a9db2b92b181da8d13406068c389cd',
 'aimn_exp40p_transition_noise_forensics.py': '0f101ffbfd8a78108ff7e4ece12c85f14e83acc3a425e1ae4366cd1e0e4d86a3',
 'aimn_exp40q_combined_trajectory_forensics.py': 'ede4e39f98fd427165775cb5191dfe84e738c1a638ed7dbbbe72c86bc1f5b1b3',
 'aimn_exp40r_entry_timing_forensics.py': 'd6925c24e7c92da1f9e658948bedda0d983066380bc9ef4de1004d6d834e9664',
 'aimn_exp40s_opening_trajectory_forensics.py': 'bf32703dd21e908e043983b6467b0be9a29017338cfdc7db590c62b1b362af52',
 'aimn_exp40t_opening_selectivity.py': '6c3edd17cfe9bfa2a2d15157488fcab9ede062b605e857c3af5fcea68cdb5277',
 'aimn_exp40u_combined_causal_replay.py': '67ad4c4e6c6680ec5e611d408edb2197612d499e29aa6e3dbc0ec3d835b01657',
 'aimn_exp40v_transition_verification.py': '4e69c8528a4e64f0c082ef596c34f5a4b6ce8dd815fd4ee93f0f7fb08decad76',
 'aimn_exp40x_causal_invalidation_replay.py': '251f946917176eefda05ea38af37b72d5e3fd9f488d5e3bf56027e8cd0730664',
 'aimn_exp40z_reverse_transition_forensics.py': '97f3f71f972ea5c4594570d5df720fcceaa6eae446b5928db24b5a1febfb5ec4',
 'engine/kiss_backtest.py': '0131b7dfc5bcbd16439ba21ed22702fa3350776116918acbe0683bfbcc44c5b7',
 'kiss/kiss_exp53_supertrend.py': 'c1727a67c903fdc7dc0ca61562f233a07908aebb04347ce255f4e9fccede1749'}

def check_sources():
    for name,digest in HASHES.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise ValueError(f'Frozen source mismatch: {name}')

# Verify files before importing strategy modules.
check_sources()
import aimn_exp40aa_reverse_transition_replay as aa
import aimn_exp40l_independent_validation as v
from aimn_exp40u_combined_causal_replay import b,k,m
u,x=aa.u,aa.x

POLICIES={'AB0':'K3','AB1':'AA1','AB2':'AA4'}

def run(rows,start):
    feat,total=u.features(rows,start)
    s5=m.snapshots(rows,5)
    results={}
    for name in POLICIES.values():
        if name=='K3':
            t,ev,op,a=v.run(rows,'K3',start)
        else:
            entry,policy,extra,_=aa.POLICIES[name]
            t,ev,op,a=aa.replay(rows,True,u.gate_for(feat,entry),True,True,True,
                warning='bullish_upper_close',entry_detector=lambda i:i in feat,
                invalidation=x.invalidator(rows,s5,policy),supplemental=extra)
        if op is not None or any(r['signal_time']<start or r['entry_time']<start or r['overnight'] or r['entry_time'][:10]!=r['signal_time'][:10] or r['signal_time'][11:16]>='15:30' or r['exit_time'][11:16]>'15:55' for r in t):
            raise ValueError(f'Warm-up or session protection failure: {name}')
        a=[r for r in a if r['signal_time']>=start]
        results[name]=(t,a)
    return results,dict(two_step=total,focus=len(feat))

def metrics(t):
    s=b.summary(t)
    s['average_net_pct']=round(sum(r['net_pnl_pct'] for r in t)/len(t),6) if t else None
    s['extra_cost_net_pct']={f'{cost:.2f}':round(sum(r['net_pnl_pct']-cost for r in t),6) for cost in (.02,.05,.10)}
    return s

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    disc=m.load(b.DATA,b.DATA_HASH)
    warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec')
    nov=m.load(m.TEST,'eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d')
    target=ROOT/'kiss/visual_research/independent_holdout_exp127/nvda_sep_oct_2026_5m_iex.json'
    digest='3e944cd4cdeba1adb650804a0a3e81d5355c225d9ad05546176b1de8ef9e9718'
    test=m.load(target,digest)
    v.validate_rows(disc,4680,'2026-06-04 09:30:00','2026-08-28 15:55:00')
    v.validate_rows(warm,780,'2026-11-02 09:30:00','2026-11-13 15:55:00')
    v.validate_rows(nov,624,m.START,'2026-11-25 15:55:00')
    start='2026-09-01 09:30:00'
    days=v.validate_rows(test,3354,start,'2026-10-30 15:55:00')
    if len(days)!=43 or disc[-1]['timestamp']>=start: raise ValueError('Invalid evaluation boundary')
    expected={('DISCOVERY','K3'):(32,-.199296),('NOVEMBER','K3'):(3,-1.673977),('DISCOVERY','AA1'):(16,-.152856),('NOVEMBER','AA1'):(2,1.216933),('DISCOVERY','AA4'):(28,-.006064),('NOVEMBER','AA4'):(5,1.084956)}
    parity={}; references={}
    for period,rows,begin in [('DISCOVERY',disc,disc[0]['timestamp']),('NOVEMBER',warm+nov,m.START)]:
        res,_=run(rows,begin)
        for name,(t,a) in res.items():
            if name=='K3':
                folder=k.OUT if period=='DISCOVERY' else v.OUT
                prefix='K3_BULLISH_UPPER_CLOSE' if period=='DISCOVERY' else 'K3'
            else:
                folder=aa.OUT; prefix=f'{period}_{name}'
            for suffix,records in [('trades',t),('candidates',a)]:
                path=folder/f'{prefix}_{suffix}.csv'
                k.e.verify_csv(records,path)
                references[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
            s=b.summary(t)
            if (len(t),s['net_sum_pct'])!=expected[period,name]: raise ValueError(f'Benchmark mismatch: {period} {name}')
            parity[f'{period}_{name}']=s
    res,counts=run(disc+test,start)
    report=dict(notes=['Previously used September–October data: historical robustness only, not untouched validation.', 'Original June–August warm-up feed provenance is unverified; mixed feed may affect indicator values.', 'Frozen engines reused; no parameter tuning. No orders or production changes.', 'Net trade sums are not portfolio returns; extra round-trip costs are arithmetic sensitivity, not a fill simulation.'],source_hashes=HASHES,reference_hashes=references,benchmark_parity=parity,evaluation_sha256=digest,warmup_sha256=b.DATA_HASH,warmup_candles=len(disc),evaluation_candles=len(test),evaluation_sessions=days,environment=dict(python=sys.version,platform=platform.platform()),warning_counts=counts,variants={})
    for label,name in POLICIES.items():
        t,a=res[name]
        report['variants'][label]=dict(strategy=name,**metrics(t),candidates=len(a),candidate_statuses=dict(Counter(r['status'] for r in a)),overnight_trades=0,splits={month:metrics([r for r in t if r['signal_time'][5:7]==mm]) for month,mm in [('SEPTEMBER','09'),('OCTOBER','10')]})
    OUT.mkdir(parents=True,exist_ok=False)
    for label,name in POLICIES.items():
        t,a=res[name]; v.write_csv(OUT/f'{label}_trades.csv',t); v.write_csv(OUT/f'{label}_candidates.csv',a)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(benchmark_parity='PASSED',evaluation_sessions=len(days),warning_counts=counts,variants=report['variants']),indent=2,allow_nan=False))

if __name__=='__main__': main()
