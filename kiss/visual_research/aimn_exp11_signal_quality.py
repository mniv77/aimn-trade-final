"""AIMn EXP11: offline timestamp and recovery audit. No trading actions."""
import csv
from pathlib import Path
from collections import defaultdict
from statistics import mean
from datetime import datetime

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'aimn_exp10_recovery_aware_transition_audit.csv'
OUTPUT = ROOT / 'aimn_exp11_signal_quality_audit.csv'

def main():
    with SOURCE.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: r['timestamp_ny'])
    assert len({r['timestamp_ny'] for r in rows}) == len(rows), 'Duplicate timestamps'
    out = []
    recovery = None
    day = None
    for r in rows:
        t = datetime.fromisoformat(r['timestamp_ny'])
        if t.date() != day:
            day, recovery = t.date(), None
        if r['event'] == 'RECOVERY_REARM_NEW_HIGH':
            recovery = (t, r['episode_id'])
        a, b = int(r['v5_signal_BASELINE_ONLY']), int(r['exp10_signal'])
        if not (a or b):
            continue
        category = 'RETAINED' if a and b else 'NEW' if b else 'REMOVED'
        rec = recovery if recovery and recovery[1] == r['episode_id'] else None
        out.append(dict(r, category=category,
            recovery_episode=int(bool(rec)),
            minutes_since_recovery=(t-rec[0]).total_seconds()/60 if rec else '',
            possible_shift_partner_AUDIT_ONLY='', shift_minutes_AUDIT_ONLY=''))
    # Pair unmatched timestamps greedily by smallest same-day distance, <=30 min.
    # This is a retrospective proximity heuristic, not proof of the same reversal.
    pairs = []
    for i, a in enumerate(out):
        if a['category'] != 'REMOVED': continue
        ta = datetime.fromisoformat(a['timestamp_ny'])
        for j, b in enumerate(out):
            if b['category'] != 'NEW': continue
            tb = datetime.fromisoformat(b['timestamp_ny'])
            delta = (tb-ta).total_seconds()/60
            if ta.date() == tb.date() and abs(delta) <= 30:
                pairs.append((abs(delta), i, j, delta))
    used = set()
    for _, i, j, delta in sorted(pairs):
        if i in used or j in used: continue
        used.update((i,j))
        for x,y in [(i,j),(j,i)]:
            out[x]['possible_shift_partner_AUDIT_ONLY'] = out[y]['timestamp_ny']
            out[x]['shift_minutes_AUDIT_ONLY'] = delta
    with OUTPUT.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)
    groups = defaultdict(list)
    for r in out: groups[r['split'],r['category']].append(r)
    for key, group in sorted(groups.items()):
        vals = [float(r['forward_12_candle_short_pct_AUDIT_ONLY']) for r in group if r['forward_12_candle_short_pct_AUDIT_ONLY'] != '']
        print(*key, 'signals',len(group),'outcomes',len(vals),'positive',sum(v>0 for v in vals),'mean',round(mean(vals),4) if vals else None,'recovery',sum(r['recovery_episode'] for r in group))
    print('Possible shifted pairs:',len(used)//2)
    print('Saved:', OUTPUT)

if __name__ == '__main__':
    main()
