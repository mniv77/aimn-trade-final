#!/usr/bin/env python3
"""AIMn Experiment 9: early SHORT failures and second peaks (research only).

Usage:
 python aimn_exp9_second_peak_diagnostic.py CANDLES.json EXP8_AUDIT.csv OUTPUT.csv

Features ending at V5 signal use candles no later than that signal.
Later path features are explicitly hindsight diagnostics, not signal inputs.
No broker calls or trading orders. Does not change V5.
"""
import csv
import json
import sys
from pathlib import Path


def pct(a, b):
    return round(100.0 * (a / b - 1), 4) if b else None


def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def audit(candles, cases):
    candles = sorted(candles, key=lambda c: c['timestamp'])
    by_time = {c['timestamp'][:16]: i for i, c in enumerate(candles)}
    if len(by_time) != len(candles):
        raise ValueError('Duplicate candle timestamps')
    out = []
    for case in cases:
        start = case.get('prior_v5_timestamp_ny', '')
        teacher = case['teacher_timestamp_ny']
        if not start:
            continue
        if start not in by_time or teacher not in by_time:
            raise ValueError(f'Missing candle for {start} / {teacher}')
        a, b = by_time[start], by_time[teacher]
        if b <= a:
            raise ValueError(f'Invalid ordering for {teacher}')
        entry = candles[a]
        entry_close = float(entry['close'])
        if abs(entry_close - float(case['prior_v5_close'])) > 0.0001:
            raise ValueError(f'Entry price mismatch: {start}')
        # Causal features at signal close. No candles later than a are consulted.
        prior = candles[max(0, a - 12):a]
        prior6 = candles[max(0, a - 6):a]
        same_day = [c for c in prior if c['timestamp'][:10] == start[:10]]
        prev_close = float(candles[a-1]['close']) if a else entry_close
        signal_close_change = pct(entry_close, prev_close)
        peak_prior12 = max((float(c['high']) for c in prior), default=entry_close)
        prior6_low = min((float(c['low']) for c in prior6), default=entry_close)
        signal_peak_distance = pct(peak_prior12, entry_close)
        signal_break_prior6_low = int(entry_close < prior6_low)
        signal_candle_red = int(entry_close < float(entry['open']))
        signal_upper_wick_pct = pct(float(entry['high']), max(float(entry['open']), entry_close))
        signal_prior6_return = pct(prev_close, float(candles[a-6]['close'])) if a >= 6 else None
        # Hindsight-only path: excludes signal candle, includes teacher candle.
        path = candles[a+1:b+1]
        max_high = max(float(c['high']) for c in path)
        min_low = min(float(c['low']) for c in path)
        high_i = max(range(a+1, b+1), key=lambda j: float(candles[j]['high']))
        first_higher_high = next((candles[j]['timestamp'][:16] for j in range(a+1, b+1)
                                  if float(candles[j]['high']) > float(entry['high'])), '')
        new_high_count = sum(float(c['high']) > float(entry['high']) for c in path)
        second_peak_high = float(candles[high_i]['high'])
        second_peak_timestamp = candles[high_i]['timestamp'][:16]
        # Candidate second peak is descriptive only; do not confuse with a causal entry signal.
        after_peak = candles[high_i+1:b+1]
        decline_after_peak_pct = pct(float(candles[b]['close']), second_peak_high)
        high_before_teacher = high_i < b
        out.append({
            'teacher_timestamp_ny': teacher,
            'teacher_confidence': case.get('confidence', ''),
            'v5_signal_timestamp_ny': start,
            'v5_reason': case.get('prior_v5_reason', ''),
            'minutes_earlier': case.get('minutes_earlier', ''),
            'signal_close': entry_close,
            'signal_change1_pct_CAUSAL': signal_close_change,
            'signal_prior6_return_pct_CAUSAL': signal_prior6_return,
            'signal_distance_from_prior12_high_pct_CAUSAL': signal_peak_distance,
            'signal_broke_prior6_low_CAUSAL': signal_break_prior6_low,
            'signal_red_candle_CAUSAL': signal_candle_red,
            'signal_upper_wick_pct_CAUSAL': signal_upper_wick_pct,
            'same_day_prior_candles_available_CAUSAL': len(same_day),
            'path_candles_HINDSIGHT': len(path),
            'max_adverse_rise_pct_HINDSIGHT': pct(max_high, entry_close),
            'max_favorable_drop_pct_HINDSIGHT': round(-pct(min_low, entry_close), 4),
            'first_higher_high_time_HINDSIGHT': first_higher_high,
            'new_higher_high_candles_HINDSIGHT': new_high_count,
            'highest_peak_time_HINDSIGHT': second_peak_timestamp,
            'highest_peak_price_HINDSIGHT': second_peak_high,
            'highest_peak_before_teacher_HINDSIGHT': int(high_before_teacher),
            'teacher_close_vs_highest_peak_pct_HINDSIGHT': decline_after_peak_pct,
            'stop_0_5_touched_HINDSIGHT': int(max_high >= entry_close * 1.005),