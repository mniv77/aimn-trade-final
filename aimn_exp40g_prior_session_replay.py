"""EXP40-G: previous-session direction for early NVDA SHORT signals.
Independent discovery replay; no production changes or orders.
"""
import csv
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
import aimn_exp40e_adaptive_trajectory as e
import aimn_exp40f_opening_session_forensics as f

d, b = e.d, e.b
OUT = b.ROOT / 'kiss/results/exp40g_prior_session_replay'
EXTRA = ('prev_30m_return_pct', 'prev_60m_return_pct', 'opening_policy')
POLICIES = ('G0_E1', 'G1_PRIOR_30M', 'G2_PRIOR_60M', 'G3_BOTH_NEGATIVE', 'G4_EITHER_NEGATIVE')


def prior_features(rows):
    """Match EXP40-F: previous closing window open to final close."""
    times = [datetime.fromisoformat(r['timestamp']) for r in rows]
    starts = []
    s = 0
    for i, t in enumerate(times):
        if i and t.date() != times[i-1].date():
            s = i
        starts.append(s)
    def get(i):
        p = starts[i] - 1
        values = dict(prev_30m_return_pct=None, prev_60m_return_pct=None)
        if p < 0 or times[p].strftime('%H:%M') != '15:55':
            return values
        for n in (6, 12):
            a = p-n+1
            if f.contiguous(rows, times, a, p):
                values[f'prev_{n*5}m_return_pct'] = f.pct(float(rows[p]['close']), float(rows[a]['open']))
        return values
    return get


def opening_decision(name, features):
    a, z = features['prev_30m_return_pct'], features['prev_60m_return_pct']
    # Require both features for a comparable opening sample across all variants.
    if name == 'G0_E1' or a is None or z is None:
        return False
    return {'G1_PRIOR_30M': a < 0, 'G2_PRIOR_60M': z < 0,
            'G3_BOTH_NEGATIVE': a < 0 and z < 0,
            'G4_EITHER_NEGATIVE': a < 0 or z < 0}[name]


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
    times = [datetime.fromisoformat(r['timestamp']) for r in rows]
    if len(rows) != 4680 or any(a >= z for a,z in zip(times,times[1:])):
        raise ValueError('Unexpected candle order/count')
    idx = {r['timestamp']:i for i,r in enumerate(rows)}
    for name, digest in [('E0_D3_candidates.csv','4819c84b70abeaf9071ae0b854fa05eadb190a33332737dc9463292037f52c5d'), ('E0_D3_trades.csv','25e517cd5dce97bcb307829a824f8541f0d3c036260d2bd9f669b2eb04f762d2')]:
        if hashlib.sha256((e.OUT/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'EXP40-F source mismatch: {name}')
    full, short, prior = d.features(rows), e.short_features(rows), prior_features(rows)
    opening = f.read_csv(f.OUT/'opening_forensics.csv')
    if len(opening) != 28 or len({r['signal_time'] for r in opening}) != 28:
        raise ValueError('Opening record count mismatch')
    for r in opening:
        values = prior(idx[r['signal_time']])
        for k,v in values.items():
            expected = float(r[k]) if r[k] else None
            if v != expected:
                raise ValueError(f'EXP40-F feature mismatch: {r["signal_time"]} {k}')
    report = {'notes': [
        'Discovery only; June-August already examined; no independent validation.',
        'Opening recovery applies to EARLIEST only; SHORT_ONLY stays rejected.',
        'Full-history D3 unchanged; both prior windows required for opening recovery.',
        'Previous-session direction uses zero boundary, not fitted cutoff.',
        'Same B2 execution and overnight exposure, 0.2% round-trip commission, no added slippage.',
        'Net sums are unweighted trade returns, not compounded portfolio returns.',
        'Splits by signal date; continuous replay.'
    ], 'feature_parity': len(opening), 'variants': {}}
    results = {}
    for name in POLICIES:
        def gate(i):
            x = {**full(i), **short(i)}
            allowed, policy = e.decision('E1_FULL_ONLY', x)
            kind = ('FULL' if x['rise_delta'] is not None else 'SHORT_ONLY' if x['short_rise_delta'] is not None else 'EARLIEST')
            x.update(history_type=kind, policy_used=policy)
            pv = prior(i)
            if kind == 'EARLIEST' and name != 'G0_E1':
                allowed = opening_decision(name, pv)
                x['policy_used'] = name
            x.update(**pv, opening_policy=name if kind == 'EARLIEST' else 'NOT_APPLICABLE')
            return allowed, x
        t, events, op, audit = d.replay(rows, True, gate)
        if len(audit) != 135 or len({r['signal_time'] for r in audit}) != 135:
            raise ValueError('Candidate parity count mismatch')
        if name == 'G0_E1':
            e.verify_csv(t,e.OUT/'E1_FULL_ONLY_trades.csv')
            e.verify_csv(audit,e.OUT/'E1_FULL_ONLY_candidates.csv',EXTRA)
            if len(t)!=25 or sum(r['net_pnl_pct']>0 for r in t)!=12 or round(sum(r['net_pnl_pct'] for r in t),6)!=-4.631843 or op is not None:
                raise ValueError('Frozen E1 aggregate mismatch')
            report['baseline_parity'] = dict(trades=len(t), candidates=len(audit))
        results[name] = (t,audit)
        lookup = {r['signal_time']:r for r in audit}
        groups = {}
        for kind in ('FULL','SHORT_ONLY','EARLIEST'):
            candidates = [r for r in audit if r['history_type']==kind]
            group = [r for r in t if lookup[r['signal_time']]['history_type']==kind]
            groups[kind] = dict(candidates=len(candidates), allowed=sum(r['allowed'] for r in candidates), **b.summary(group))
        report['variants'][name] = dict(**b.summary(t), events=events, open_position=op,
            history_groups=groups, splits={label:b.summary([r for r in t if (r['signal_time'][5:7]=='08')==aug]) for label,aug in [('JUN_JUL',False),('AUG',True)]})
    original = {r['signal_time']:r for r in results['G0_E1'][0]}
    early_original = {r['signal_time']:r for r in opening}
    for name,(t,audit) in results.items():
        current = {r['signal_time']:r for r in t}
        recovered = [r for k,r in current.items() if k in early_original]
        report['variants'][name].update(removed_vs_E1=b.summary([r for k,r in original.items() if k not in current]),
            added_vs_E1=b.summary([r for k,r in current.items() if k not in original]),
            recovered_original_opening=b.summary(recovered),
            original_opening_winners_recovered=sum(float(early_original[r['signal_time']]['net_pnl_pct'])>0 for r in recovered),
            original_opening_winners_not_recovered=sum(float(r['net_pnl_pct'])>0 for k,r in early_original.items() if k not in current))
    OUT.mkdir(parents=True,exist_ok=False)
    for name,(t,audit) in results.items():
        for suffix,records in [('trades',t),('candidates',audit)]:
            with (OUT/f'{name}_{suffix}.csv').open('x',newline='') as fp:
                if records:
                    w=csv.DictWriter(fp,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
