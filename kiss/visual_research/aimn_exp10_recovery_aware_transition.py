aimn_exp10_recovery_aware_transition.py#!/usr/bin/env python3
"""AIMn Experiment 10: recovery-aware SHORT detector (RESEARCH ONLY).

Usage:
 python aimn_exp10_recovery_aware_transition.py CANDLES.json V5_AUDIT.csv OUTPUT.csv

CANDLES.json: original NVDA OHLC candles, list of dictionaries with timestamp,
open, high, low, close. V5_AUDIT.csv: Experiment 5 audit output.

No broker calls. Uses only information through each candle close. Teacher labels,
V5 signals and forward outcomes are used ONLY for comparison, never decisions.
Thresholds are hypotheses; do not tune on August evaluation rows.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path


def pct(a, b):
    return 100.0 * (a / b - 1.0) if b else 0.0


def load_candles(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError('Expected a JSON list of candle dictionaries')
    candles = sorted(data, key=lambda c: c['timestamp'])
    if len({c['timestamp'][:16] for c in candles}) != len(candles):
        raise ValueError('Duplicate candle timestamps')
    for c in candles:
        for field in ('open', 'high', 'low', 'close'):
            c[field] = float(c[field])
        if c['low'] > c['high'] or not c['low'] <= c['close'] <= c['high']:
            raise ValueError('Invalid OHLC at ' + c['timestamp'])
    return candles


def load_v5(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    return {r['timestamp_ny'][:16]: r for r in rows}


def run(candles, v5):
    results = []
    state = 'SEEK'
    peak = None
    peak_i = -1
    weak_count = 0
    low_breaks = 0
    locked_peak = None
    locked_i = -1
    episode = 0
    day = None

    for i, c in enumerate(candles):
        t = c['timestamp'][:16]
        d = t[:10]
        if d != day:
            state, peak, peak_i = 'SEEK', None, -1
            weak_count = low_breaks = 0
            locked_peak, locked_i = None, -1
            day = d
        if i < 24:
            continue
        previous = candles[i-1]
        recent6 = candles[i-6:i]
        recent12 = candles[i-12:i]
        rise12 = pct(previous['close'], candles[i-12]['close'])
        rise6 = pct(previous['close'], candles[i-6]['close'])
        change1 = pct(c['close'], previous['close'])
        change3 = pct(c['close'], candles[i-3]['close'])
        prior_low = min(x['low'] for x in recent6)
        prior_high = max(x['high'] for x in recent12)
        approach = (rise12 >= 0.30 and rise6 >= 0.05
                    and pct(prior_high, c['close']) <= 0.70)
        before = state
        event = ''
        signal = 0
        reason = ''

        if state == 'SEEK':
            if approach:
                episode += 1
                state = 'TRACK'
                peak, peak_i = c['high'], i
                weak_count = low_breaks = 0
                event = 'TRACK_START'
        elif state == 'TRACK':
            if c['high'] > peak:
                peak, peak_i = c['high'], i
                weak_count = low_breaks = 0
                event = 'NEW_TRACKED_PEAK'
            drawdown = pct(peak, c['close'])
            age = i - peak_i
            if change1 < -0.06:
                weak_count += 1
            elif change1 > 0.12:
                weak_count = max(0, weak_count - 1)
            if c['close'] < prior_low:
                low_breaks += 1
            early = (2 <= age <= 12 and 0.18 <= drawdown <= 1.50
                     and weak_count >= 2 and change3 <= -0.10)
            confirmed = (age >= 1 and drawdown >= 0.30
                         and low_breaks >= 1 and change3 <= -0.18)
            if early or confirmed:
                signal = 1
                reason = 'EARLY_FAILED_RECOVERY' if early else 'STRUCTURAL_BREAK'
                state = 'LOCKED'
                locked_peak = peak
                locked_i = i
                event = 'SHORT_HYPOTHESIS'
            elif age > 24 or drawdown > 3.0:
                state = 'SEEK'
                event = 'TRACK_EXPIRED'
        else:
            # Recovery is observable only at this candle close. Require a fresh
            # high ABOVE the previously tracked peak and a positive close-to-close
            # recovery; do not use future highs or teacher entries.
            new_high = c['high'] > locked_peak
            recovered = change3 > 0.15 and c['close'] > previous['close']
            if new_high and recovered:
                episode += 1
                state = 'TRACK'
                peak, peak_i = c['high'], i
                weak_count = low_breaks = 0
                locked_peak, locked_i = None, -1
                event = 'RECOVERY_REARM_NEW_HIGH'
            elif i - locked_i >= 12 and approach and change3 > 0.15:
                episode += 1
                state = 'TRACK'
                peak, peak_i = c['high'], i
                weak_count = low_breaks = 0
                locked_peak, locked_i = None, -1
                event = 'V5_STYLE_REARM'

        baseline = v5.get(t)
        if baseline is None:
            raise ValueError('Missing V5 baseline row for candle ' + t)
        v5_signal = int(baseline['v5_signal'])
        teacher = int(baseline['teacher_entry'])
        future = baseline.get('forward_12_candle_short_pct_RESEARCH_ONLY', '')
        results.append({
            'timestamp_ny': t,
            'split': baseline['split'],
            'close': c['close'],
            'state_before': before,
            'state_after': state,
            'episode_id': episode,
            'event': event,
            'tracked_peak': round(peak, 5) if peak is not None else '',
            'locked_peak': round(locked_peak, 5) if locked_peak is not None else '',
            'exp10_signal': signal,
            'exp10_reason': reason,
            'v5_signal_BASELINE_ONLY': v5_signal,
            'v5_reason_BASELINE_ONLY': baseline['v5_reason'],
            'teacher_entry_AUDIT_ONLY': teacher,
            'teacher_confidence_AUDIT_ONLY': baseline['teacher_confidence'],
            'forward_12_candle_short_pct_AUDIT_ONLY': future,
        })
    return results


def summarize(rows):
    print('AIMn EXP10 — research only; no execution or P&L simulation')
    for split in ('DEVELOPMENT_JUN_JUL', 'EVALUATION_AUG'):
        subset = [r for r in rows if r['split'] == split]
        exp = [r for r in subset if r['exp10_signal']]
        base = [r for r in subset if r['v5_signal_BASELINE_ONLY']]
        forward = [float(r['forward_12_candle_short_pct_AUDIT_ONLY'])
                   for r in exp if r['forward_12_candle_short_pct_AUDIT_ONLY'] not in ('', None)]
        print(split, 'V5', len(base), 'EXP10', len(exp),
              'teacher exact V5', sum(r['teacher_entry_AUDIT_ONLY'] for r in base),
              'teacher exact EXP10', sum(r['teacher_entry_AUDIT_ONLY'] for r in exp),
              'recovery rearms', sum(r['event'] == 'RECOVERY_REARM_NEW_HIGH' for r in subset),
              '1h gross positive', sum(x > 0 for x in forward), '/', len(forward),
              '1h gross average', round(sum(forward)/len(forward), 4) if forward else 'N/A')
    print('Events:', dict(Counter(r['event'] for r in rows if r['event'])))
    print('Important: A signal is a research hypothesis, not an executed trade.')


def main():
    if len(sys.argv) == 1:
        folder = Path(__file__).resolve().parent
        sys.argv.extend(str(folder / name) for name in (
            'aimn_nvda_candles.json',
            'aimn_exp5_continuous_transition_audit.csv',
            'aimn_exp10_recovery_aware_transition_audit.csv',
        ))
    if len(sys.argv) != 4:
        raise SystemExit('Usage: python aimn_exp10_recovery_aware_transition.py CANDLES.json V5_AUDIT.csv OUTPUT.csv')
    candles = load_candles(sys.argv[1])
    v5 = load_v5(sys.argv[2])
    rows = run(candles, v5)
    if not rows:
        raise ValueError('No rows produced')
    output = Path(sys.argv[3])
    with output.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summarize(rows)
    print('Saved', output)


if __name__ == '__main__':
    main()
