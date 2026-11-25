#!/usr/bin/env python3
"""AIMn Experiment 4: causal two-path SHORT transition research.

Usage: python aimn_exp4_two_path_short.py CANDLES.json TEACHING.json OUTPUT.csv
No broker interaction. All signal features use current/past completed candles.
August is evaluation-only; thresholds are fixed, not optimized on August.
"""
import csv
import json
import sys
from collections import Counter


def pct(new, old):
    return 100.0 * (new / old - 1.0) if old else 0.0


def run(candles, lessons):
    candles = sorted(candles, key=lambda c: c['timestamp'])
    times = [c['timestamp'] for c in candles]
    if len(times) != len(set(times)):
        raise ValueError('Duplicate candle timestamps')
    teacher = {x['market_timestamp']: x for x in lessons if x['kind'] == 'ENTER_SHORT'}
    state, age, lock_age = 'SEEK_UPTREND', 0, 0
    day = None
    out = []
    for i, c in enumerate(candles):
        t = c['timestamp'][:16]
        current_day = t[:10]
        if current_day != day:
            state, age, lock_age = 'SEEK_UPTREND', 0, 0
            day = current_day
        if i < 24:
            continue
        prev = candles[i-1]
        prev12 = candles[i-12:i]
        prev6 = candles[i-6:i]
        recent_high = max(x['high'] for x in prev12)
        recent_low6 = min(x['low'] for x in prev6)
        rise12 = pct(prev['close'], candles[i-12]['close'])
        rise6 = pct(prev['close'], candles[i-6]['close'])
        change1 = pct(c['close'], prev['close'])
        change3 = pct(c['close'], candles[i-3]['close'])
        distance_peak = pct(recent_high, c['close'])
        body_pct = pct(c['close'], c['open'])
        upper_wick = max(0.0, c['high'] - max(c['open'], c['close']))
        candle_range = max(c['high'] - c['low'], 1e-9)
        wick_share = upper_wick / candle_range
        near_peak = distance_peak <= 0.70
        approach = rise12 >= 0.30 and rise6 >= 0.05
        weakening = change1 <= -0.08 or (body_pct < 0 and wick_share >= 0.30)
        structural_break = c['close'] < recent_low6 and change3 <= -0.18
        early = near_peak and weakening and change3 > -0.65
        confirmed = structural_break
        signal = 0
        path = ''
        state_before = state
        # One signal per episode. Fresh uptrend required after a locked episode.
        if state == 'SEEK_UPTREND':
            if approach and near_peak:
                state, age = 'ARMED', 0
        elif state == 'ARMED':
            age += 1
            if early or confirmed:
                signal = 1
                path = 'EARLY_PEAK' if early else 'CONFIRMED_BREAK'
                state, lock_age = 'LOCKED', 0
            elif age > 18 or distance_peak > 2.0:
                state, age = 'SEEK_UPTREND', 0
        else:
            lock_age += 1
            if lock_age >= 12 and approach and near_peak:
                state, age = 'ARMED', 0
        future = ''
        if i + 12 < len(candles) and candles[i+12]['timestamp'][:10] == current_day:
            future = round(-pct(candles[i+12]['close'], c['close']), 4)
        lesson = teacher.get(t)
        out.append({
            'timestamp_ny': t, 'split': 'EVALUATION_AUG' if t[:7] == '2026-08' else 'DEVELOPMENT_JUN_JUL',
            'close': c['close'], 'rise12_pct': round(rise12, 4),
            'rise6_pct': round(rise6, 4), 'change1_pct': round(change1, 4),
            'change3_pct': round(change3, 4), 'distance_peak_pct': round(distance_peak, 4),
            'wick_share': round(wick_share, 4), 'approach': int(approach),
            'early_condition': int(early), 'confirmed_condition': int(confirmed),
            'state_before': state_before, 'state_after': state,
            'v4_signal': signal, 'v4_path': path,
            'teacher_entry': int(lesson is not None),
            'teacher_confidence': lesson['confidence'] if lesson else '',
            'forward_12_candle_short_pct_RESEARCH_ONLY': future,
        })
    return out, teacher


def summary(rows, teacher):
    print('Causal Experiment 4 — research only')
    print('Rows:', len(rows), 'Signals:', sum(r['v4_signal'] for r in rows))
    for split in ('DEVELOPMENT_JUN_JUL', 'EVALUATION_AUG'):
        rr = [r for r in rows if r['split'] == split]
        signals = [r for r in rr if r['v4_signal']]
        with_outcome = [r for r in signals if r['forward_12_candle_short_pct_RESEARCH_ONLY'] != '']
        print(split, 'signals', len(signals), 'path_counts', dict(Counter(r['v4_path'] for r in signals)))
        print('  teacher exact:', sum(r['teacher_entry'] for r in signals), '/', sum(r['teacher_entry'] for r in rr))
        if with_outcome:
            returns = [r['forward_12_candle_short_pct_RESEARCH_ONLY'] for r in with_outcome]
            print('  12-candle same-day short return mean (gross):', round(sum(returns)/len(returns), 4),
                  'positive:', sum(x > 0 for x in returns), '/', len(returns))
    print('Teacher total:', len(teacher), 'matched candle rows:', sum(r['teacher_entry'] for r in rows))
    print('Outcomes are observational, not independent trades; no fees, stops or fill simulation.')


def main():
    if len(sys.argv) != 4:
        raise SystemExit('Usage: python aimn_exp4_two_path_short.py CANDLES.json TEACHING.json OUTPUT.csv')
    with open(sys.argv[1], encoding='utf-8') as f:
        candles = json.load(f)
    with open(sys.argv[2], encoding='utf-8') as f:
        lessons = json.load(f)['lessons']
    rows, teacher = run(candles, lessons)
    with open(sys.argv[3], 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary(rows, teacher)


if __name__ == '__main__':
    main()
