"""EXP40-E: adaptive pre-peak trajectory research; no production writes."""
import csv
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
import aimn_exp40d_deceleration_replay as d

b = d.b
OUT = b.ROOT / 'kiss/results/exp40e_adaptive_trajectory'


def short_features(rows):
    c = [float(r['close']) for r in rows]
    t = [datetime.fromisoformat(r['timestamp']) for r in rows]
    def measure(a, z):
        returns = [(c[j]/c[j-1]-1)*100 for j in range(a+1,z+1)]
        path = sum(abs(v) for v in returns)
        return (c[z]/c[a]-1)*100, sum(returns)/path if path else 0.0
    def get(i):
        end = i-1
        start, mid = end-6, end-3
        f = dict(short_earlier_rise=None, short_recent_rise=None,
                 short_earlier_eff=None, short_recent_eff=None,
                 short_rise_delta=None, short_eff_delta=None)
        if start < 0 or t[start].date() != t[i].date() or any(
                t[j]-t[j-1] != timedelta(minutes=5) for j in range(start+1,i+1)):
            return f
        e, ee = measure(start, mid)
        r, re = measure(mid, end)
        f.update(short_earlier_rise=e, short_recent_rise=r,
                 short_earlier_eff=ee, short_recent_eff=re,
                 short_rise_delta=r-e, short_eff_delta=re-ee)
        return f
    return get


def decision(name, f):
    if f['rise_delta'] is not None:
        return f['rise_delta'] < 0 and f['eff_delta'] < 0, 'FULL_6_PLUS_6'
    if name == 'E0_D3':
        return True, 'MISSING_PASS'
    if name == 'E1_FULL_ONLY':
        return False, 'MISSING_REJECT'
    if f['short_rise_delta'] is not None:
        return f['short_rise_delta'] < 0 and f['short_eff_delta'] < 0, 'SHORT_3_PLUS_3'
    return name == 'E3_ADAPT_PASS', 'EARLIEST_PASS' if name == 'E3_ADAPT_PASS' else 'EARLIEST_REJECT'


def verify_csv(records, path, extra=()):
    saved = list(csv.DictReader(path.open(newline='')))
    actual = [{k: '' if v is None else str(v) for k,v in r.items() if k not in extra} for r in records]
    if actual != saved:
        raise ValueError(f'Exact parity failed: {path}')


def main():
    raw = b.DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest() != b.DATA_HASH:
        raise ValueError('Candle hash mismatch')
    engine = Path(d.base.__file__).read_bytes()
    if hashlib.sha1(b'blob '+str(len(engine)).encode()+b'\0'+engine).hexdigest() != b.ENGINE_BLOB:
        raise ValueError('Engine mismatch')
    if hashlib.sha256((b.OUTPUT/'B2_trades.csv').read_bytes()).hexdigest() != d.B2_HASH:
        raise ValueError('B2 CSV mismatch')
    rows = json.loads(raw)
    full, short = d.features(rows), short_features(rows)
    results = {}
    report = {'notes': ['Discovery data only; no independent validation.',
        'Full history uses unchanged D3; short uses two consecutive three-return windows ending at pre-signal peak.',
        'Same-session contiguous candles required; reversal candle excluded.',
        'B2 execution, overnight exposure and fees unchanged; no extra slippage.',
        'Groups are by signal timestamp; net sums are not compounded portfolio returns.'], 'variants': {}}
    for name in ('E0_D3','E1_FULL_ONLY','E2_ADAPT_WAIT','E3_ADAPT_PASS'):
        def gate(i):
            f = {**full(i), **short(i)}
            allowed, policy = decision(name, f)
            f['history_type'] = ('FULL' if f['rise_delta'] is not None else
                                 'SHORT_ONLY' if f['short_rise_delta'] is not None else 'EARLIEST')
            f['policy_used'] = policy
            return allowed, f
        t,e,o,a = d.replay(rows,True,gate)
        if len(a) != 135:
            raise ValueError('Candidate count mismatch')
        if name == 'E0_D3':
            verify_csv(t,d.OUT/'D3_BOTH_trades.csv')
            extra = ('short_earlier_rise','short_recent_rise','short_earlier_eff','short_recent_eff',
                     'short_rise_delta','short_eff_delta','history_type','policy_used')
            verify_csv(a,d.OUT/'D3_BOTH_candidates.csv',extra)
            if len(t)!=64 or sum(x['net_pnl_pct']>0 for x in t)!=23 or round(sum(x['net_pnl_pct'] for x in t),6)!=-11.658255 or o is not None:
                raise ValueError('Frozen D3 aggregate mismatch')
            report['baseline_parity'] = {'trades':len(t),'candidates':len(a)}
        results[name] = (t,a)
        lookup = {x['signal_time']:x for x in a}
        groups = {}
        for label in ('FULL','SHORT_ONLY','EARLIEST'):
            candidates = [x for x in a if x['history_type']==label]
            group = [x for x in t if lookup[x['signal_time']]['history_type']==label]
            groups[label] = {'candidates':len(candidates), 'allowed':sum(x['allowed'] for x in candidates), **b.summary(group)}
        report['variants'][name] = {**b.summary(t),'events':e,'open_position':o,'history_groups':groups,
            'splits':{label:b.summary([x for x in t if (x['signal_time'][5:7]=='08')==aug])
                      for label,aug in [('JUN_JUL',False),('AUG',True)]}}
    original = {x['signal_time']:x for x in results['E0_D3'][0]}
    for name,(t,a) in results.items():
        current = {x['signal_time']:x for x in t}
        report['variants'][name].update(removed=b.summary([x for k,x in original.items() if k not in current]),
            added=b.summary([x for k,x in current.items() if k not in original]))
    OUT.mkdir(parents=True,exist_ok=False)
    for name,(t,a) in results.items():
        for suffix,records in [('trades',t),('candidates',a)]:
            with (OUT/f'{name}_{suffix}.csv').open('x',newline='') as f:
                if records:
                    w=csv.DictWriter(f,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
