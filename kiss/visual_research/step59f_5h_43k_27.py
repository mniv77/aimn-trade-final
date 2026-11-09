
#!/usr/bin/env python3
"""AIMn Step 59F-5H-43K-27: Trend maturity / remaining opportunity audit.
Read-only; completed pre-entry 5m candles only; no filter changes.
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

LAB = Path('kiss/visual_research')
sys.path.insert(0, str(LAB.resolve()))
import step59f_5h43c_flat_long_replay as engine

PARAMS = dict(entry_cutoff='15:45', commission_pct=0.01,
              entry_slippage_pct=0.02, exit_slippage_pct=0.02,
              trailing_minus_pct=1.5, rsi_rescue_short=80.0,
              atr_exhaustion_filter=True, flat_long_filter=True)
DATASETS = {
    'RESEARCH': (LAB / 'aimn_nvda_candles.json', 22, 6.764673),
    'VALIDATION': (LAB / 'nvda_sep_oct_2026_validation.json', 14, 2.219621),
}
PRIORITY = {'2026-07-06', '2026-07-24', '2026-08-03', '2026-08-21'}


def dt(value):
    return datetime.fromisoformat(str(value))


def pct(new, old):
    return 100.0 * (new / old - 1.0) if old else None


def fmt(value):
    return 'NA' if value is None else f'{value:+.4f}%'


def load(path):
    obj = json.loads(path.read_text(encoding='utf-8'))
    rows = obj['candles'] if isinstance(obj, dict) else obj
    rows = sorted(rows, key=lambda r: dt(r['timestamp']))
    times = [dt(r['timestamp']) for r in rows]
    assert len(times) == len(set(times)), 'Duplicate timestamps'
    return rows


def audit_entry(rows, entry):
    # Same-day only: excludes the entry candle and every future candle.
    prior = [r for r in rows if dt(r['timestamp']).date() == entry.date()
             and dt(r['timestamp']) + timedelta(minutes=5) <= entry]
    if not prior:
        return dict(bars=0, maturity='UNKNOWN', recovery='UNKNOWN',
                    opening=None, high_to_last=None, low_to_last=None,
                    recent_down=None, recovery_size=None,
                    recovery_age=None, down_streak=0)

    first_open = float(prior[0]['open'])
    closes = [float(r['close']) for r in prior]
    highs = [float(r['high']) for r in prior]
    lows = [float(r['low']) for r in prior]
    last = closes[-1]
    high = max(highs)
    low = min(lows)
    high_idx = max(i for i, x in enumerate(highs) if x == high)
    low_idx = max(i for i, x in enumerate(lows) if x == low)

    # Pre-entry range position is a description, not future potential.
    position = (last - low) / (high - low) if high > low else None
    if position is None:
        maturity = 'UNKNOWN'
    elif position <= 0.25:
        maturity = 'NEAR_OBSERVED_LOW'
    elif position >= 0.75:
        maturity = 'NEAR_OBSERVED_HIGH'
    else:
        maturity = 'MIDDLE_OF_RANGE'

    # Count consecutive falling closes at the end of completed history.
    streak = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] < closes[i - 1]:
            streak += 1
        else:
            break

    # Locate the latest completed local recovery using closes only.
    # A peak at index j is confirmed by a lower close at j+1.
    # It is available at entry only if j+1 is completed.
    peaks = [j for j in range(1, len(closes) - 1)
             if closes[j] > closes[j-1] and closes[j] > closes[j+1]]
    recent_peak = peaks[-1] if peaks else None
    if recent_peak is None:
        recovery = 'NO_CONFIRMED_LOCAL_PEAK'
        recovery_size = None
        recovery_age = None
        recent_down = None
    else:
        recovery_age = len(closes) - 1 - recent_peak
        # Advance into peak over at most six prior closes.
        start = max(0, recent_peak - 6)
        trough = min(closes[start:recent_peak + 1])
        recovery_size = pct(closes[recent_peak], trough)
        recent_down = pct(last, closes[recent_peak])
        if recovery_size is None or recovery_size <= 0:
            recovery = 'NO_MEASURABLE_RECOVERY'
        elif recovery_age <= 2:
            recovery = 'RECENT_LOCAL_PEAK'
        else:
            recovery = 'OLDER_LOCAL_PEAK'

    return dict(bars=len(prior), maturity=maturity, recovery=recovery,
                opening=pct(last, first_open),
                high_to_last=pct(last, high),
                low_to_last=pct(last, low),
                recent_down=recent_down, recovery_size=recovery_size,
                recovery_age=recovery_age, down_streak=streak,
                high_idx=high_idx, low_idx=low_idx,
                high_before_low=high_idx < low_idx)


def summary(label, records, key):
    print('\n' + label)
    groups = defaultdict(list)
    for r in records:
        groups[r[key]].append(r)
    for name, items in sorted(groups.items()):
        w = sum(r['net'] > 0 for r in items)
        l = sum(r['net'] < 0 for r in items)
        print(f'{name:31s} N={len(items):2d} W={w:2d} L={l:2d} '
              f'NET={sum(r["net"] for r in items):+.6f}%')


def report(name, records, detail=True):
    print('\n' + '=' * 106 + '\n' + name + '\n' + '=' * 106)
    summary('PRE-ENTRY PRICE LOCATION', records, 'maturity')
    summary('LAST CONFIRMED LOCAL PEAK', records, 'recovery')
    summary('LOCATION / RECOVERY', records, 'joint')
    if detail:
        print('\nTRADE AUDIT')
        for r in records:
            print(f'{r["time"]} NET={r["net"]:+.6f}% '
                  f'LOC={r["maturity"]} PEAK={r["recovery"]} '
                  f'BARS={r["bars"]} STREAK={r["down_streak"]} '
                  f'OPEN_TO_LAST={fmt(r["opening"])} '
                  f'HIGH_TO_LAST={fmt(r["high_to_last"])} '
                  f'LOW_TO_LAST={fmt(r["low_to_last"])} '
                  f'RECOVERY={fmt(r["recovery_size"])} '
                  f'SINCE_PEAK={fmt(r["recent_down"])} '
                  f'PEAK_AGE={r["recovery_age"]}')


def main():
    print('AIMn — STEP 59F-5H-43K-27')
    print('TREND MATURITY AND REMAINING OPPORTUNITY')
    print('READ-ONLY OBSERVATIONAL AUDIT')
    combined = []
    for name, (path, count, expected_net) in DATASETS.items():
        rows = load(path)
        result = engine.run(rows=rows, **PARAMS)
        assert result['trade_count'] == count, f'{name}: trade count changed'
        assert abs(result['net_pnl_pct'] - expected_net) < 0.000002, f'{name}: net changed'
        times = {dt(row['timestamp']): i for i, row in enumerate(rows)}
        records = []
        for trade in result['trades']:
            entry = dt(trade['entry_time'])
            i = times[entry]
            # Explicitly pass only rows BEFORE entry.
            measures = audit_entry(rows[:i], entry)
            r = dict(dataset=name, time=str(entry), net=float(trade['net_pnl_pct']),
                     **measures)
            r['joint'] = r['maturity'] + ' / ' + r['recovery']
            records.append(r)
        assert len(records) == count
        report(name, records)
        combined.extend(records)
    assert len(combined) == 36
    assert abs(sum(r['net'] for r in combined) - 8.984294) < 0.000002
    report('COMBINED — DESCRIPTIVE ONLY', combined, detail=False)
    print('\nPRIORITY CASES')
    for r in combined:
        if r['time'][:10] in PRIORITY:
            print(f'{r["dataset"]:10s} {r["time"]} NET={r["net"]:+.6f}% '
                  f'LOC={r["maturity"]} PEAK={r["recovery"]} '
                  f'STREAK={r["down_streak"]} RECOVERY={fmt(r["recovery_size"])} '
                  f'SINCE_PEAK={fmt(r["recent_down"])} AGE={r["recovery_age"]}')
    print('\nLIMITATIONS:')
    print('Observed price range is not a prediction of remaining profit.')
    print('Local peak is a close-based shape, not a confirmed major reversal.')
    print('A peak is only counted after its following candle has completed.')
    print('Same-day pre-entry candles only; no entry/future candles used.')
    print('No new filters, no tuning, no file writes. V18 unchanged.')
    print('STEP 59F-5H-43K-27: PASS')


if __name__ == '__main__':
    main()
