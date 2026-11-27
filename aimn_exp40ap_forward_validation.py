#!/usr/bin/env python3
"""EXP40-AP: frozen AM3, benchmark first; fixed 20-session forward cohort."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'kiss/results/exp40ap_forward_validation'
AM_PATH = ROOT / 'aimn_exp40am_relative_trajectory_replay.py'
REF = ROOT / 'kiss/results/exp40am_relative_trajectory_replay'
DATA = ROOT / 'kiss/visual_research/independent_holdout_exp40l'
AM_HASH = 'f19067752e1a917da0a277a9bf4e363e57632b9fced7eac8ce4f28a0c382b79f'
REF_HASH = '55a3bf0e544ae668ed4b147e837ec01187dc336cec60e04dcb46dca0119bc547'
WARM_HASH = 'd038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec'
START = date(2026, 11, 30)
LAST = date(2026, 12, 29)
EXCLUDED = {date(2026, 12, 24), date(2026, 12, 25)}
DATES = [(START + timedelta(days=i)).isoformat() for i in range((LAST-START).days+1)
         if (START+timedelta(days=i)).weekday()<5 and START+timedelta(days=i) not in EXCLUDED]
assert len(DATES)==20

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(path, expected):
    if digest(path)!=expected:
        raise ValueError(f'Fingerprint mismatch: {path}')

verify(AM_PATH, AM_HASH)
verify(REF/'summary.json', REF_HASH)
import aimn_exp40am_relative_trajectory_replay as am
ai, ab, aa, m, b, k, v, ae = am.ai, am.ab, am.aa, am.m, am.b, am.k, am.v, am.ae
aj, ak = am.aj, am.ak


def run(rows, start):
    stamps=[r['timestamp'] for r in rows]
    assert stamps==sorted(set(stamps))
    s5=m.snapshots(rows,5)
    s30=m.snapshots(m.aggregate(rows),30)
    early=ai.focus(rows,start,s5)
    signals,warnings=aj.monitor(rows,early,s5,s30,'AJ1')
    features=am.features(rows,signals)
    selected={}; gate=[]
    for i,s in signals.items():
        val=features[i][12]
        status='MISSING' if val is None else 'PASS' if val>=.60 else 'BELOW_THRESHOLD'
        gate.append(dict(signal_time=rows[i]['timestamp'],warning_time=s['warning_time'],w6=features[i][6],w12=val,decision=status))
        if status=='PASS': selected[i]=dict(s)
    t,ev,op,a=aa.replay(rows,True,lambda i:(True,dict(selected[i])),True,True,True,
        warning='bullish_upper_close',entry_detector=lambda i:i in selected,supplemental='higher_high')
    ai.check(t,a,op,start,{rows[i]['timestamp'] for i in selected})
    return t,a,gate,warnings,ev


def benchmark():
    ab.check_sources()
    assert am.POLICIES['AM3']==(12,.6)
    warm=m.load(m.WARM,WARM_HASH)
    v.validate_rows(warm,780,'2026-11-02 09:30:00','2026-11-13 15:55:00')
    prior=[]; combined=[]; november=None
    expected={'JUN_AUG':(11,6,5,.18122),'SEP_OCT':(5,4,1,.322873),'NOV':(1,1,0,.442076)}
    for period,src,sha,n,cp,tp,nc,nt,net in ae.ad.SETS:
        data=m.load(src,sha)
        v.validate_rows(data,n,data[0]['timestamp'],data[-1]['timestamp'])
        rows=(warm if period=='NOV' else prior)+data
        prior=rows
        t,a,g,w,ev=run(rows,data[0]['timestamp'])
        for suffix,records in [('trades',t),('candidates',a),('gate',g)]:
            k.e.verify_csv(records,REF/f'{period}_AM3_{suffix}.csv')
        s=ab.metrics(t)
        assert tuple(s[key] for key in ('trades','winners','losers','net_sum_pct'))==expected[period]
        combined.extend(t)
        if period=='NOV': november=rows
        print(period,'AM3 exact trade/candidate/gate parity PASSED',flush=True)
    s=ab.metrics(combined)
    assert tuple(s[key] for key in ('trades','winners','losers','net_sum_pct'))==(17,11,6,.946169)
    print('BENCHMARK PASSED: 17 trades, 11 winners, 6 losers, +0.946169%')
    return november,s


def load_forward():
    rows=[]; manifests=[]
    for day in DATES:
        stem=f'nvda_{day}_{day}_5m_iex'
        p=DATA/(stem+'.json'); mp=DATA/(stem+'_manifest.json')
        if not p.is_file() or not mp.is_file():
            raise FileNotFoundError(f'Fixed cohort incomplete: {day}; no evaluation performed')
        info=json.loads(mp.read_text())
        expected=dict(symbol='NVDA',feed='iex',adjustment='raw',timeframe='5m',timezone='America/New_York',candles=78,sessions=1,first=day+' 09:30:00',last=day+' 15:55:00')
        for key,val in expected.items():
            if info.get(key)!=val: raise ValueError(f'Manifest mismatch: {day} {key}')
        data=m.load(p,info['sha256'])
        v.validate_rows(data,78,expected['first'],expected['last'])
        rows.extend(data)
        manifests.append(dict(date=day,data_sha256=info['sha256'],manifest_sha256=digest(mp),collected_utc=info['collected_utc']))
    assert len(rows)==1560
    return rows,manifests


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluate',action='store_true',help='Score the complete fixed cohort only; default is benchmark only')
    args=parser.parse_args()
    warm,baseline=benchmark()
    print('Frozen cohort:',', '.join(DATES))
    if not args.evaluate:
        print('BENCHMARK ONLY — no forward data scored or output written.')
        return
    if OUT.exists(): raise FileExistsError(OUT)
    data,manifests=load_forward()
    assert warm[-1]['timestamp']<data[0]['timestamp']
    t,a,g,w,ev=run(warm+data,data[0]['timestamp'])
    report=dict(experiment='EXP40-AP', frozen_am_sha256=AM_HASH, historical_summary_sha256=REF_HASH,
        threshold=.60, benchmark=baseline, forward=ab.metrics(t), authorizations=len(a),
        gate_statuses=dict(Counter(r['decision'] for r in g)), events=ev,
        sessions=DATES, manifests=manifests, collected_report_utc=datetime.now(timezone.utc).isoformat(),
        notes=['Fixed 20-session evaluation; no interim scoring or threshold selection.',
        'Warm-up uses Nov 2–25 regular sessions only; Nov 27 shortened session omitted from both scoring and warm-up.',
        'Feed IEX; net sums are not portfolio returns. Historical benchmark is discovery.',
        'Data date separation does not itself prove absence of prior human inspection.',
        'No orders or production changes.'])
    OUT.mkdir(parents=True,exist_ok=False)
    for name,records in [('trades',t),('candidates',a),('gate',g),('warnings',w)]:
        v.write_csv(OUT/f'{name}.csv',records)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('FORWARD',json.dumps(report['forward'],indent=2))
    print('Saved:',OUT)

if __name__=='__main__': main()
