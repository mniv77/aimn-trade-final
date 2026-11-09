
"""AIMn Step 59F-5H-43K-22: read-only V18 recovery-peak audit."""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

LAB = Path('kiss/visual_research')
sys.path.insert(0, str(LAB.resolve()))
import step59f_5h43c_flat_long_replay as engine

PARAMS = dict(
    entry_cutoff='15:45',
    commission_pct=0.01,
    entry_slippage_pct=0.02,
    exit_slippage_pct=0.02,
    trailing_minus_pct=1.5,
    rsi_rescue_short=80.0,
    atr_exhaustion_filter=True,
    flat_long_filter=True
)

DATASETS = {
    'RESEARCH': (
        LAB / 'aimn_nvda_candles.json', 22, 6.764673
    ),
    'VALIDATION': (
        LAB / 'nvda_sep_oct_2026_validation.json',
        14, 2.219621
    ),
}

WATCH = {
    '2026-07-06 13:45:00',
    '2026-07-24 09:55:00',
    '2026-08-11 11:50:00',
    '2026-08-13 11:35:00',
    '2026-08-21 13:25:00',
    '2026-08-21 15:30:00',
    '2026-09-02 13:10:00',
    '2026-09-28 14:25:00',
    '2026-10-08 12:45:00',
}

def dt(value):
    return datetime.fromisoformat(str(value))

def avg(values):
    nums = [v for v in values if v is not None]
    return sum(nums) / len(nums) if nums else None

def fmt(value):
    return 'N/A' if value is None else f'{value:+.4f}%'

def load_rows(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = data['candles'] if isinstance(data, dict) else data
    return sorted(
        rows, key=lambda row: dt(row['timestamp'])
    )

def preceding(rows, index, limit=25):
    entry = dt(rows[index]['timestamp'])
    prior = rows[max(0, index-limit):index]

    if not prior:
        return []

    if entry - dt(prior[-1]['timestamp']) != timedelta(minutes=5):
        return []

    start = len(prior) - 1

    while start > 0:
        a = dt(prior[start]['timestamp'])
        b = dt(prior[start-1]['timestamp'])
        if a - b != timedelta(minutes=5):
            break
        start -= 1

    return prior[start:]

def analyze(segment, entry_time, execution):
    out = dict(
        status='NO_RECOVERY',
        peak_time=None,
        peak_age=None,
        recovery_pct=None,
        first_down_pct=None,
        first_down_age=None,
        below_peak_pct=None,
        below_low_pct=None,
        low_broken=None,
        higher_peak=None,
        prior_peak_gap_pct=None,
        down_streak=None
    )

    if len(segment) < 5:
        out['status'] = 'INSUFFICIENT'
        return out

    highs = [float(r['high']) for r in segment]
    lows = [float(r['low']) for r in segment]
    closes = [float(r['close']) for r in segment]

    if min(highs + lows + closes) <= 0:
        out['status'] = 'INVALID_PRICE'
        return out

    low_pivots = [
        i for i in range(1, len(segment)-1)
        if lows[i] < lows[i-1]
        and lows[i] < lows[i+1]
    ]

    high_pivots = [
        i for i in range(1, len(segment)-1)
        if highs[i] > highs[i-1]
        and highs[i] > highs[i+1]
    ]

    candidates = [
        (hi, lo)
        for lo in low_pivots
        for hi in high_pivots
        if lo < hi and highs[hi] > lows[lo]
    ]

    if not candidates:
        return out

    hi = max(h for h, _ in candidates)
    lo = max(l for h, l in candidates if h == hi)

    peak = highs[hi]
    swing_low = lows[lo]
    peak_time = dt(segment[hi]['timestamp'])

    earlier = [
        i for i in high_pivots if i < hi
    ]

    previous_peak = (
        highs[earlier[-1]] if earlier else None
    )

    first_down_index = next(
        (
            i for i in range(hi+1, len(segment))
            if closes[i] < closes[i-1]
        ),
        None
    )

    first_down_pct = None
    first_down_age = None

    if first_down_index is not None:
        i = first_down_index
        first_down_pct = (
            closes[i] / closes[i-1] - 1
        ) * 100

        first_down_age = int(
            (
                entry_time -
                dt(segment[i]['timestamp'])
            ).total_seconds() / 300
        )

    streak = 0

    for i in range(len(closes)-1, 0, -1):
        if closes[i] >= closes[i-1]:
            break
        streak += 1

    out.update(
        status='OK',
        peak_time=str(peak_time),
        peak_age=int(
            (entry_time - peak_time).total_seconds()/300
        ),
        recovery_pct=(peak/swing_low - 1)*100,
        first_down_pct=first_down_pct,
        first_down_age=first_down_age,
        below_peak_pct=(peak/execution - 1)*100,
        below_low_pct=(swing_low/execution - 1)*100,
        low_broken=execution < swing_low,
        higher_peak=(
            peak > previous_peak
            if previous_peak is not None else None
        ),
        prior_peak_gap_pct=(
            (peak/previous_peak - 1)*100
            if previous_peak is not None else None
        ),
        down_streak=streak
    )

    return out

def summary(name, records):
    print('\n' + '='*95)
    print(name)
    print('='*95)

    groups = [
        (
            'WINNERS',
            [r for r in records if r['net'] > 0]
        ),
        (
            'LOSERS',
            [r for r in records if r['net'] < 0]
        ),
    ]

    for label, subset in groups:
        usable = [
            r['shape'] for r in subset
            if r['shape']['status'] == 'OK'
        ]

        first_down = [
            s for s in usable
            if s['first_down_pct'] is not None
        ]

        higher_known = [
            s for s in usable
            if s['higher_peak'] is not None
        ]

        print('\n' + label)
        print('TRADES:', len(subset))
        print('RECOVERY USABLE:', len(usable))
        print('FIRST DOWN USABLE:', len(first_down))
        print('HIGHER PEAK KNOWN:', len(higher_known))

        print('HIGHER PEAK TRUE:', sum(
            s['higher_peak'] is True
            for s in higher_known
        ))

        print('AVG RECOVERY:', fmt(avg([
            s['recovery_pct'] for s in usable
        ])))

        print('AVG PEAK AGE:', avg([
            s['peak_age'] for s in usable
        ]))

        print('AVG FIRST DOWN:', fmt(avg([
            s['first_down_pct'] for s in first_down
        ])))

        print('AVG FIRST DOWN AGE:', avg([
            s['first_down_age'] for s in first_down
        ]))

        print('AVG BELOW PEAK:', fmt(avg([
            s['below_peak_pct'] for s in usable
        ])))

        print('AVG BELOW LOW:', fmt(avg([
            s['below_low_pct'] for s in usable
        ])))

        print('LOW BROKEN:', sum(
            s['low_broken'] is True
            for s in usable
        ))

    print('\nRECOVERY STATUS:', dict(Counter(
        r['shape']['status'] for r in records
    )))

def main():
    print('AIMn — STEP 59F-5H-43K-22')
    print('RECOVERY PEAK QUALITY / FIRST DOWNWARD TURN')

    all_records = []
    combined_net = 0.0

    for name, (path, expected_count, expected_net) in DATASETS.items():
        rows = load_rows(path)
        result = engine.run(rows=rows, **PARAMS)

        assert result['trade_count'] == expected_count, (
            name + ': trade count changed'
        )

        assert abs(
            result['net_pnl_pct'] - expected_net
        ) < 0.000002, name + ': net changed'

        index = {
            dt(row['timestamp']): i
            for i, row in enumerate(rows)
        }

        records = []

        for trade in result['trades']:
            entry_time = dt(trade['entry_time'])

            assert entry_time in index, (
                f'Missing entry {entry_time}'
            )

            i = index[entry_time]
            execution = float(trade['entry_price'])
            entry_open = float(rows[i]['open'])

            assert execution > 0 and entry_open > 0

            assert abs(
                execution/entry_open -
                (1 - PARAMS['entry_slippage_pct']/100)
            ) < 0.000001

            shape = analyze(
                preceding(rows, i),
                entry_time,
                execution
            )

            records.append(dict(
                dataset=name,
                entry=str(entry_time),
                net=float(trade['net_pnl_pct']),
                shape=shape
            ))

        summary(name, records)

        print('\nTRADE AUDIT')

        for r in records:
            s = r['shape']

            print(
                r['entry'],
                f"NET={r['net']:+.6f}%",
                'STATUS='+s['status'],
                'PEAK_AGE='+str(s['peak_age']),
                'RECOVERY='+fmt(s['recovery_pct']),
                'FIRST_DOWN='+fmt(s['first_down_pct']),
                'FIRST_DOWN_AGE='+str(s['first_down_age']),
                'HIGHER_PEAK='+str(s['higher_peak']),
                'BELOW_PEAK='+fmt(s['below_peak_pct']),
                'BELOW_LOW='+fmt(s['below_low_pct']),
                'LOW_BROKEN='+str(s['low_broken']),
                'STREAK='+str(s['down_streak'])
            )

        all_records.extend(records)
        combined_net += result['net_pnl_pct']

    print('\n' + '='*95)
    print('IMPORTANT WATCH CASES')
    print('='*95)

    for r in all_records:
        if r['entry'] in WATCH:
            print('\nENTRY:', r['entry'])
            print('NET:', f"{r['net']:+.6f}%")
            print('SHAPE:', r['shape'])

    assert len(all_records) == 36

    assert abs(
        combined_net - 8.984294
    ) < 0.000002

    print('\nOnly completed pre-entry candles used.')
    print('Actual V18 entry execution prices used.')
    print('Research and validation reported separately.')
    print('No new thresholds or entry filters.')
    print('Original V18 engine unchanged.')
    print('No files created or modified by the audit.')
    print('No production changes.')
    print('STEP 59F-5H-43K-22: PASS')

if __name__ == '__main__':
    main()
