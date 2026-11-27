#!/usr/bin/env python3
"""EXP40-L: read-only NVDA validation data acquisition; no orders."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import aimn_exp127_alpaca_holdout_downloader as source

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'kiss/visual_research/independent_holdout_exp40l'
DEFAULT_START = '2026-11-16'
DEFAULT_LAST = '2026-11-25'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default=DEFAULT_START)
    parser.add_argument('--last', default=DEFAULT_LAST)
    args = parser.parse_args()
    start = dt.date.fromisoformat(args.start)
    last = dt.date.fromisoformat(args.last)
    if start <= dt.date(2026, 11, 13) or last < start:
        raise ValueError('Require a valid date range after November 13, 2026')
    # Custom ranges are supported only for complete weekday sessions.
    # Holidays and early closes require explicit calendar handling.
    expected = []
    day = start
    while day <= last:
        if day.weekday() < 5:
            expected.extend(dt.datetime.combine(day, dt.time(9, 30)) + dt.timedelta(minutes=5*i) for i in range(78))
        day += dt.timedelta(days=1)
    if not expected:
        raise ValueError('No expected sessions')
    end = last + dt.timedelta(days=1)
    source.START = start.isoformat() + 'T00:00:00Z'
    source.END = end.isoformat() + 'T00:00:00Z'
    stem = f'nvda_{start.isoformat()}_{last.isoformat()}_5m_iex'
    path = OUT / (stem + '.json')
    manifest = OUT / (stem + '_manifest.json')
    if path.exists() or manifest.exists():
        raise FileExistsError('Refusing to overwrite existing validation artifacts')
    key, secret = source.credentials()
    raw = source.fetch('NVDA', 'iex', key, secret)
    rows, outside = source.convert(raw)
    actual = [dt.datetime.fromisoformat(r['timestamp']) for r in rows]
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        raise ValueError(f'Session completeness failed: expected {len(expected)}, got {len(actual)}; missing examples {missing[:5]}; unexpected examples {unexpected[:5]}')
    for row in rows:
        if not all(math.isfinite(row[k]) for k in ('open','high','low','close','volume')) or row['volume'] < 0:
            raise ValueError('Invalid numeric candle values')
    payload = (json.dumps(rows, indent=2, allow_nan=False) + '\n').encode('utf-8')
    info = dict(experiment='EXP40-L', symbol='NVDA', feed='iex', adjustment='raw', timeframe='5m', timezone='America/New_York', start_utc=source.START, requested_end_utc=source.END, candles=len(rows), sessions=len(rows)//78, first=rows[0]['timestamp'], last=rows[-1]['timestamp'], outside_regular_session_removed=outside, sha256=hashlib.sha256(payload).hexdigest(), path=str(path), collected_utc=dt.datetime.now(dt.timezone.utc).isoformat(), note='Complete weekday sessions only. Date disjointness is not proof of untouched research usage. IEX may differ from discovery feed. No strategy evaluation performed.')
    OUT.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(payload)
    with manifest.open('x', encoding='utf-8') as f:
        json.dump(info, f, indent=2)
        f.write('\n')
    print(json.dumps(info, indent=2))
    print('DATA ONLY — no orders, no production changes.')


if __name__ == '__main__':
    main()
