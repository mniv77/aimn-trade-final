"""EXP40-C: NVDA SHORT V17 causal entry forensics; no orders or production writes."""
import csv
import hashlib
import json
import math
import statistics as st
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'kiss/visual_research/aimn_nvda_candles.json'
B2 = ROOT / 'kiss/results/exp40b_causal_replay/B2_trades.csv'
SUMMARY = B2.parent / 'summary.json'
OUT = ROOT / 'kiss/results/exp40c_trajectory_forensics'
HASH = '020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50'
WINDOWS = (3, 6, 12, 30)


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def pct(a, b):
    return 100 * (a / b - 1)


def features(rows, i, starts, completed):
    # All fields use bars no later than the signal bar. Windows do not span sessions.
    r, p = rows[i], rows[i-1]
    start = starts[i]
    c, o, h, l = (float(r[k]) for k in ('close','open','high','low'))
    peak = float(p['high'])
    result = {'signal_pullback_pct': pct(peak, c),
              'signal_bearish_body_pct': pct(o,c),
              'signal_range_pct': pct(h,l),
              'signal_close_location': (c-l)/(h-l) if h>l else None,
              'session_bar': i-start+1}
    # Pre-reversal trajectory ends at the reference peak candle i-1.
    for n in WINDOWS:
        names = ('rise_pct','range_pct','efficiency','higher_high_fraction','higher_low_fraction','peak_from_floor_pct')
        if i-n < start:
            result.update({f'w{n}_{k}':None for k in names})
            continue
        w = rows[i-n:i]
        cs = [float(x['close']) for x in w]
        hs = [float(x['high']) for x in w]
        ls = [float(x['low']) for x in w]
        travel = sum(abs(b-a) for a,b in zip(cs,cs[1:]))
        vals = (pct(cs[-1],cs[0]), pct(max(hs),min(ls)),
                (cs[-1]-cs[0])/travel if travel else 0.,
                sum(b>a for a,b in zip(hs,hs[1:]))/(n-1),
                sum(b>a for a,b in zip(ls,ls[1:]))/(n-1), pct(peak,min(ls)))
        result.update({f'w{n}_{k}':v for k,v in zip(names,vals)})
    bars = completed[i]
    result['completed_30m_count'] = len(bars)
    result['mtf_last_body_pct'] = pct(bars[-1][1],bars[-1][0]) if bars else None
    result['mtf_2bar_close_change_pct'] = pct(bars[-1][1],bars[-2][1]) if len(bars)>=2 else None
    result['mtf_3bar_close_change_pct'] = pct(bars[-1][1],bars[-3][1]) if len(bars)>=3 else None
    return result


def context(rows):
    starts, completed = [], []
    start=0; day=None; blocks=[]; group=[]; bucket=None
    for i,r in enumerate(rows):
        dt=datetime.fromisoformat(r['timestamp'])
        if dt.date()!=day:
            day=dt.date(); start=i; blocks=[]; group=[]; bucket=None
        starts.append(start)
        # Regular-session timestamps are assumed to mark the start of 5m bars.
        b=dt.replace(minute=(dt.minute//30)*30,second=0,microsecond=0)
        if b!=bucket:
            group=[]; bucket=b
        group.append((dt,r))
        if len(group)==6 and all(x[0]==b+timedelta(minutes=5*j) for j,x in enumerate(group)):
            blocks.append((float(group[0][1]['open']),float(group[-1][1]['close'])))
        completed.append(tuple(blocks))
    return starts,completed


def metrics(v):
    return {'trades':len(v),'winners':sum(x['net_pnl_pct']>0 for x in v),
            'net_sum_pct':round(sum(x['net_pnl_pct'] for x in v),6)}


def main():
    raw=DATA.read_bytes(); require(hashlib.sha256(raw).hexdigest()==HASH,'Candle hash mismatch')
    rows=json.loads(raw); require(len(rows)==4680,'Candle count mismatch')
    ts=[r['timestamp'] for r in rows]; require(all(a<b for a,b in zip(ts,ts[1:])),'Timestamp order mismatch')
    index={t:i for i,t in enumerate(ts)}
    with B2.open(newline='') as f: trades=list(csv.DictReader(f))
    prior=json.loads(SUMMARY.read_text()); require(prior['data_sha256']==HASH,'B2 data identity mismatch')
    expected=prior['variants']['B2']; require(len(trades)==expected['trades']==122,'Trade count mismatch')
    starts,completed=context(rows)
    audit=[]; seen=set()
    for t in trades:
        s,e,x=(index[t[k]] for k in ('signal_time','entry_time','exit_time'))
        require(s>=1 and e==s+1 and x>=e,'Signal/fill alignment mismatch')
        require(s not in seen,'Duplicate signal'); seen.add(s)
        require(abs(float(t['entry_price'])-float(rows[e]['open']))<1e-6,'Entry open mismatch')
        net=float(t['net_pnl_pct']); fee=float(t['commission_pct']); best=float(t['best_close_pct'])
        require(all(math.isfinite(v) for v in (net,fee,best)) and abs(fee-.2)<1e-8,'Invalid outcome/fee')
        record={**t,'net_pnl_pct':net,'split':'JUN_JUL' if t['signal_time'][:7] in ('2026-06','2026-07') else 'AUG',
                'outcome':'WINNER' if net>0 else 'LOSS_CLOSE_ABOVE_FEE' if best>fee else 'LOSS_CLOSE_NOT_ABOVE_FEE',
                **features(rows,s,starts,completed)}
        audit.append(record)
    actual=metrics(audit)
    require(actual['winners']==expected['winners']==41 and abs(actual['net_sum_pct']-expected['net_sum_pct'])<1e-6,'B2 outcome parity mismatch')
    feature_keys=list(features(rows,index[trades[0]['signal_time']],starts,completed))
    comparisons=[]
    for split in ('ALL','JUN_JUL','AUG'):
        subset=[x for x in audit if split=='ALL' or x['split']==split]
        for k in feature_keys:
            for outcome in ('WINNER','LOSS_CLOSE_ABOVE_FEE','LOSS_CLOSE_NOT_ABOVE_FEE'):
                group=[x for x in subset if x['outcome']==outcome]; vals=[x[k] for x in group if x[k] is not None]
                comparisons.append(dict(split=split,feature=k,outcome=outcome,trades=len(group),available=len(vals),mean=st.mean(vals) if vals else None,median=st.median(vals) if vals else None))
    # Previously observed B0 threshold: diagnostic only, no new optimization.
    # Use the original peak denominator to match B0's definition exactly.
    for x in audit:
        i=index[x['signal_time']]; x['b0_definition_pullback_pct']=100*(1-float(rows[i]['close'])/float(rows[i-1]['high']))
    report={'data_sha256':HASH,'b2_csv_sha256':hashlib.sha256(B2.read_bytes()).hexdigest(),
            'baseline':actual,'outcomes':{k:metrics([x for x in audit if x['outcome']==k]) for k in ('WINNER','LOSS_CLOSE_ABOVE_FEE','LOSS_CLOSE_NOT_ABOVE_FEE')},
            'splits':{},'notes':['Features use completed signal candles only; 30m uses six contiguous 5m bars with start timestamps.','Pre-peak windows are session-local and omit insufficient history.','Best-close outcomes are retrospective, not entry features.','June-August is discovery data, including August; no independent validation or policy replay.','Only executed B2 trades are studied; blocked candidates and EXP39 rejects require a separate audit.']}
    for split in ('ALL','JUN_JUL','AUG'):
        group=[x for x in audit if split=='ALL' or x['split']==split]
        report['splits'][split]={'all':metrics(group),'pullback_ge_0p75':metrics([x for x in group if x['b0_definition_pullback_pct']>=.75]),'pullback_lt_0p75':metrics([x for x in group if x['b0_definition_pullback_pct']<.75])}
    OUT.mkdir(parents=True,exist_ok=False)
    for name,records in [('entry_forensics.csv',audit),('feature_comparison.csv',comparisons)]:
        with (OUT/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
