#!/usr/bin/env python3
"""AIMn Experiment 7: compare V5 prior signals with hindsight teacher entries.
Research only. No broker calls, no parameter optimization, no model training.
Usage: python aimn_exp7_early_vs_teacher.py V5_AUDIT.csv EXP6_AUDIT.csv OUTPUT.csv
The prior signal is the latest V5 signal before the teacher entry on the same day.
Forward returns are descriptive only and are never signal inputs.
"""
import csv
import sys
from datetime import datetime
from pathlib import Path


def load(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def number(v):
    return float(v) if v not in ('', None) else None


def main():
    if len(sys.argv) != 4:
        raise SystemExit('Usage: python aimn_exp7_early_vs_teacher.py V5_AUDIT.csv EXP6_AUDIT.csv OUTPUT.csv')
    v5 = load(sys.argv[1])
    exp6 = load(sys.argv[2])
    by_time = {r['timestamp_ny']: r for r in v5}
    if len(by_time) != len(v5):
        raise ValueError('Duplicate timestamps in V5 audit')
    out = []
    for teacher in exp6:
        ts = teacher['teacher_timestamp_ny']
        current = by_time.get(ts)
        if current is None:
            raise ValueError('Missing teacher candle in V5 audit: ' + ts)
        prior_ts = teacher['latest_prior_signal_same_day']
        prior = by_time.get(prior_ts) if prior_ts else None
        if prior_ts and (prior is None or prior['v5_signal'] != '1' or prior_ts[:10] != ts[:10]):
            raise ValueError('Invalid prior V5 signal: ' + prior_ts)
        teacher_close = number(teacher['teacher_close'])
        current_close = number(current['close'])
        if abs(teacher_close-current_close) > 0.0001:
            raise ValueError('Teacher candle close mismatch: ' + ts)
        prior_close = number(prior['close']) if prior else None
        # For a short, higher earlier entry close is a price advantage.
        price_advantage = (100 * (prior_close / teacher_close - 1)) if prior_close is not None else None
        minutes = int((datetime.fromisoformat(ts) - datetime.fromisoformat(prior_ts)).total_seconds()/60) if prior_ts else None
        prior_forward = number(prior['forward_12_candle_short_pct_RESEARCH_ONLY']) if prior else None
        teacher_forward = number(current['forward_12_candle_short_pct_RESEARCH_ONLY'])
        out.append({
            'teacher_timestamp_ny': ts,
            'confidence': teacher['teacher_confidence'],
            'diagnosis': teacher['diagnosis'],
            'teacher_close': teacher_close,
            'prior_v5_timestamp_ny': prior_ts,
            'prior_v5_reason': prior['v5_reason'] if prior else '',
            'minutes_earlier': minutes if minutes is not None else '',
            'prior_v5_close': prior_close if prior_close is not None else '',
            'earlier_entry_price_advantage_pct': round(price_advantage, 4) if price_advantage is not None else '',
            'earlier_entry_higher_price': int(prior_close > teacher_close) if prior_close is not None else '',
            'prior_one_hour_gross_short_pct': prior_forward if prior_forward is not None else '',
            'teacher_one_hour_gross_short_pct': teacher_forward if teacher_forward is not None else '',
            'same_day_one_hour_comparison_available': int(prior_forward is not None and teacher_forward is not None),
            'note': 'Candle-close comparison only; no execution, stops, or drawdown simulation'
        })
    path = Path(sys.argv[3]); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    paired = [r for r in out if r['prior_v5_timestamp_ny']]
    better = [r for r in paired if r['earlier_entry_higher_price'] == 1]
    comparable = [r for r in paired if r['same_day_one_hour_comparison_available']]
    print('Teacher entries:', len(out))
    print('With earlier same-day V5 signal:', len(paired))
    print('Earlier signal has higher entry price:', len(better), '/', len(paired))
    print('Both one-hour outcomes observable:', len(comparable))
    print('Output:', path)
    print('CAUTION: Earlier signal price alone does not establish profitability or safety.')


if __name__ == '__main__':
    main()
