#!/usr/bin/env python3
"""AIMn Experiment 6: diagnose V5 teacher-entry misses (research only).
Usage: python aimn_exp6_missed_teacher_audit.py V5_AUDIT.csv OUTPUT.csv
Reads the original V5 audit; never changes trading signals or engine files.
Teacher labels are hindsight annotations, NOT causal model inputs.
"""
import csv
import sys
from datetime import datetime
from pathlib import Path


def analyze(rows):
    output = []
    for index, row in enumerate(rows):
        if row['teacher_entry'] != '1':
            continue
        date = row['timestamp_ny'][:10]
        prior = [(j, r) for j, r in enumerate(rows[:index])
                 if r['timestamp_ny'][:10] == date and r['v5_signal'] == '1']
        next_signals = [(j, r) for j, r in enumerate(rows[index + 1:], index + 1)
                        if r['timestamp_ny'][:10] == date and r['v5_signal'] == '1']
        latest = prior[-1][1] if prior else None
        nxt = next_signals[0][1] if next_signals else None
        state = row['state_before']
        if row['v5_signal'] == '1':
            diagnosis = 'EXACT_MATCH'
        elif state == 'LOCKED':
            diagnosis = 'LOCKED_BEFORE_TEACHER'
        elif state == 'TRACK':
            diagnosis = 'TRACK_NO_CONFIRMATION'
        elif state == 'SEEK':
            diagnosis = 'SEEK_NO_ACTIVE_EPISODE'
        else:
            diagnosis = 'OTHER'
        def minutes_between(a, b):
            if not a or not b:
                return ''
            fmt = '%Y-%m-%d %H:%M'
            return int((datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds() / 60)
        output.append({
            'teacher_timestamp_ny': row['timestamp_ny'],
            'teacher_confidence': row['teacher_confidence'],
            'teacher_close': row['close'],
            'v5_exact_match': row['v5_signal'],
            'state_before': state,
            'state_after': row['state_after'],
            'diagnosis': diagnosis,
            'episode_id': row['episode_id'],
            'candles_since_peak': row['candles_since_peak'],
            'drawdown_from_peak_pct': row['drawdown_from_peak_pct'],
            'weakening_count': row['weakening_count'],
            'structural_break_count': row['structural_break_count'],
            'change1_pct': row['change1_pct'],
            'change3_pct': row['change3_pct'],
            'latest_prior_signal_same_day': latest['timestamp_ny'] if latest else '',
            'prior_signal_reason': latest['v5_reason'] if latest else '',
            'minutes_since_prior_signal': minutes_between(latest['timestamp_ny'], row['timestamp_ny']) if latest else '',
            'next_signal_same_day': nxt['timestamp_ny'] if nxt else '',
            'minutes_until_next_signal': minutes_between(row['timestamp_ny'], nxt['timestamp_ny']) if nxt else '',
            'prior_signals_same_day': len(prior),
            'forward_12_candle_short_pct_RESEARCH_ONLY': row['forward_12_candle_short_pct_RESEARCH_ONLY'],
        })
    return output


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python aimn_exp6_missed_teacher_audit.py V5_AUDIT.csv OUTPUT.csv')
    with open(sys.argv[1], newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    result = analyze(rows)
    if not result:
        raise SystemExit('No teacher entries found in V5 audit')
    with open(sys.argv[2], 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    from collections import Counter
    print('Teacher entries:', len(result))
    print('Diagnosis:', dict(Counter(x['diagnosis'] for x in result)))
    print('Research-only: no changes to live trading or V5 signals')


if __name__ == '__main__':
    main()
