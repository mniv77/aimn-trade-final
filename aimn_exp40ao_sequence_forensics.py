#!/usr/bin/env python3
"""EXP40-AO: descriptive directional sequence audit; no trading changes."""
import csv
import json
import hashlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'kiss/results/exp40an_acceleration_forensics/acceleration_audit.csv'
OUT = ROOT / 'kiss/results/exp40ao_sequence_forensics'
PERIODS = ('JUN_AUG', 'SEP_OCT', 'NOV')
LABELS = ('WIN', 'NO_FEE_CLOSE', 'GIVEBACK', 'UNTRADED')
FORMS = ('AO1', 'AO2', 'AO3', 'AO4')

def number(s):
    return None if s in ('', None, 'None') else float(s)

def classify(r):
    a, b = (number(r[k]) for k in ('early3_velocity', 'recent3_velocity'))
    if a is None or b is None:
        return 'AO4', 'MISSING'
    if a < 0 and b > 0:
        return 'AO1', 'SHORT_LONG'
    if a > 0 and b > 0:
        return 'AO2', 'LONG_LONG'
    if a > 0 and b < 0:
        return 'AO3', 'LONG_SHORT'
    return 'AO4', 'SHORT_SHORT' if a < 0 and b < 0 else 'ZERO_VELOCITY'

def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    with SRC.open(newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 65
    assert len({(r['period'], r['signal_time']) for r in rows}) == 65
    assert Counter(r['period'] for r in rows) == dict(zip(PERIODS, (38,20,7)))
    assert Counter(r['aj1_outcome'] for r in rows) == dict(zip(LABELS,(25,25,8,7)))
    assert Counter(r['am3_outcome'] for r in rows) == dict(zip(LABELS,(11,5,1,48)))
    assert round(sum(number(r['am3_net_pct']) or 0 for r in rows),6) == .946169
    for r in rows:
        assert r['peak_time'] < r['warning_time'] < r['signal_time']
        r['formation'], r['formation_detail'] = classify(r)
    report = []
    for period in ('ALL', *PERIODS):
        group = [r for r in rows if period == 'ALL' or r['period'] == period]
        for form in FORMS:
            rr = [r for r in group if r['formation'] == form]
            item = dict(period=period, formation=form, authorizations=len(rr), details=dict(Counter(r['formation_detail'] for r in rr)))
            for strategy in ('aj1','am3'):
                c = Counter(r[strategy+'_outcome'] for r in rr)
                item[strategy] = {k:c[k] for k in LABELS}
                n = c['WIN'] + c['NO_FEE_CLOSE'] + c['GIVEBACK']
                item[strategy]['win_rate_pct'] = round(100*c['WIN']/n, 4) if n else None
            item['am3_net_pct'] = round(sum(number(r['am3_net_pct']) or 0 for r in rr),6)
            item['am3_gate_pass'] = sum(r['am3_gate']=='PASS' for r in rr)
            report.append(item)
            print(period,form,'AUTH',len(rr),'AJ1 W/N/G/U',*(item['aj1'][k] for k in LABELS),'AM3 W/N/G/U',*(item['am3'][k] for k in LABELS),'AM3 net',item['am3_net_pct'])
    OUT.mkdir(parents=True,exist_ok=False)
    with (OUT/'sequence_audit.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (OUT/'summary.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),notes=['Discovery only. Signs of adjacent three-change close velocity windows ending at original peak. Final SHORT refers to detected warning, not verified future trend. Zero and missing history separate in AO4 detail. Outcomes are from existing sequential replays, not new strategy tests. AJ1 net P&L absent from source; only AM3 net reported.'],groups=report),indent=2,allow_nan=False)+'\n')
    print('PASS: 65 authorizations, 58 AJ1 trades, 17 AM3 trades')
    print('Saved:',OUT)

if __name__ == '__main__':
    main()
