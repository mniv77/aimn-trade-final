#!/usr/bin/env python3
"""AIMn Experiment 8 — early SHORT entry path-risk audit (research only).

Usage:
    python aimn_exp8_early_entry_risk.py CANDLES.json EXP7_AUDIT.csv OUTPUT.csv

Reads the Experiment 7 paired comparisons and actual 5-minute candle highs/lows.
No broker orders, strategy modifications, model fitting, or future-informed signals.

The input candles MUST have matching New York timestamps and prices. If the
file is from a different price series, this script refuses to produce results.
Stop touches are hypothetical; they are not fills or execution simulations.
"""
import csv
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

THRESHOLDS = (0.5, 1.0, 1.5)
NEW_COLUMNS = [
    'path_candles', 'max_high_between', 'min_low_between',
    'short_mae_pct', 'short_mfe_pct', 'new_high_after_signal',
    'worst_high_timestamp', 'best_low_timestamp',
    'stop_0_5_touched', 'stop_1_0_touched', 'stop_1_5_touched',
    'first_stop_0_5_timestamp', 'first_stop_1_0_timestamp',
    'first_stop_1_5_timestamp', 'analysis_status',
]


def ny_time(raw):
    """Convert a candle timestamp to NY wall time, retaining local timestamps."""
    if isinstance(raw, (int, float)):
        dt = datetime.fromtimestamp(raw, timezone.utc).astimezone(ZoneInfo('America/New_York'))
    else:
        value = str(raw).strip().replace('Z', '+00:00')
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is not None:
            dt = dt.astimezone(ZoneInfo('America/New_York'))
    return dt.strftime('%Y-%m-%d %H:%M')


def audit(candles, exp7_rows):
    by_time = {}
    for candle in candles:
        stamp = ny_time(candle['timestamp'])
        if stamp in by_time:
            raise ValueError('Duplicate candle timestamp: ' + stamp)
        by_time[stamp] = candle

    results = []
    for source in exp7_rows:
        row = dict(source)
        row.update({name: '' for name in NEW_COLUMNS})
        earlier = row.get('prior_v5_timestamp_ny', '').strip()
        teacher = row.get('teacher_timestamp_ny', '').strip()
        if not earlier:
            row['analysis_status'] = 'NO_PRIOR_SIGNAL'
            results.append(row)
            continue
        if earlier not in by_time or teacher not in by_time:
            raise ValueError(f'Missing candle for interval {earlier} -> {teacher}')
        entry_close = float(row['prior_v5_close'])
        teacher_close = float(row['teacher_close'])
        if abs(float(by_time[earlier]['close']) - entry_close) > 0.011:
            raise ValueError(f'Price mismatch at {earlier}: candle vs V5 entry {entry_close}')
        if abs(float(by_time[teacher]['close']) - teacher_close) > 0.011:
            raise ValueError(f'Price mismatch at {teacher}: candle vs teacher {teacher_close}')
        if earlier[:10] != teacher[:10] or earlier >= teacher:
            raise ValueError(f'Invalid same-day interval: {earlier} -> {teacher}')

        # The entry is assumed at the earlier signal candle CLOSE.
        # Exclude that candle's high/low (which may have occurred before entry).
        # Include the teacher candle as the endpoint of the comparison.
        path = [(stamp, by_time[stamp]) for stamp in sorted(by_time)
                if earlier < stamp <= teacher and stamp[:10] == earlier[:10]]
        if not path:
            raise ValueError(f'No post-entry candles: {earlier} -> {teacher}')
        high_stamp, high_candle = max(path, key=lambda x: float(x[1]['high']))
        low_stamp, low_candle = min(path, key=lambda x: float(x[1]['low']))
        max_high = float(high_candle['high'])
        min_low = float(low_candle['low'])
        row['path_candles'] = len(path)
        row['max_high_between'] = max_high
        row['min_low_between'] = min_low
        row['short_mae_pct'] = round(100 * max(0, max_high / entry_close - 1), 4)
        row['short_mfe_pct'] = round(100 * max(0, 1 - min_low / entry_close), 4)
        row['new_high_after_signal'] = int(max_high > float(by_time[earlier]['high']))
        row['worst_high_timestamp'] = high_stamp
        row['best_low_timestamp'] = low_stamp
        for threshold in THRESHOLDS:
            key = str(threshold).replace('.', '_')
            touched = [stamp for stamp, candle in path
                       if float(candle['high']) >= entry_close * (1 + threshold / 100)]
            row[f'stop_{key}_touched'] = int(bool(touched))
            row[f'first_stop_{key}_timestamp'] = touched[0] if touched else ''
        row['analysis_status'] = 'OBSERVED_PATH_NOT_EXECUTION'
        results.append(row)
    return results


def main():
    if len(sys.argv) != 4:
        raise SystemExit('Usage: python aimn_exp8_early_entry_risk.py CANDLES.json EXP7_AUDIT.csv OUTPUT.csv')
    with open(sys.argv[1], encoding='utf-8') as f:
        candles = json.load(f)
    with open(sys.argv[2], newline='', encoding='utf-8-sig') as f:
        exp7_rows = list(csv.DictReader(f))
    rows = audit(candles, exp7_rows)
    with open(sys.argv[3], 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    pairs = [r for r in rows if r['analysis_status'] == 'OBSERVED_PATH_NOT_EXECUTION']
    print('Experiment 8 — research only; paired intervals:', len(pairs))
    for threshold in THRESHOLDS:
        key = str(threshold).replace('.', '_')
        print(f'{threshold}% hypothetical stop touches:', sum(int(r[f'stop_{key}_touched']) for r in pairs))
    print('Audit written:', sys.argv[3])


if __name__ == '__main__':
    main()
