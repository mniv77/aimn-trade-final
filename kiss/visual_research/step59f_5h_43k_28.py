
#!/usr/bin/env python3
"""AIMn 59F-5H-43K-28: read-only peak-to-entry displacement audit."""
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
    return 100 * (new / old - 1) if old else None


def fmt(value):
    return 'NA' if value is None else f'{value:+.4f}%'


def load(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = data['candles'] if isinstance(data, dict) else data
    rows = sorted(rows, key=lambda x: dt(x['timestamp']))
    times = [dt(r['timestamp']) for r in rows]
    assert len(times) == len(set(times)), 'Duplicate candle timestamps'
    return rows


def classify_displacement(value):
    if value is None:
        return 'NO_CONFIRMED_PEAK'
    if value < 0.20:
        return 'UNDER_0_20'
    if value < 0.50:
        return 'FROM_0_20_TO_0_50'
    if value < 1.00:
        return 'FROM_0_50_TO_1_00'
    return 'AT_LEAST_1_00'


def classify_ratio(value):
    if value is None:
        return 'RATIO_UNAVAILABLE'
    if value < 1:
        return 'DECLINE_SMALLER_THAN_RECOVERY'
    if value < 3:
        return 'DECLINE_1_TO_3_TIMES_RECOVERY'
    return 'DECLINE_AT_LEAST_3_TIMES_RECOVERY'


def measure(prior, entry):
    # Only fully completed same-day candles before entry.
    rows = [r for r in prior if dt(r['timestamp']).date() == entry.date()
            and dt(r['timestamp']) + timedelta(minutes=5) <= entry]
    closes = [float(r['close']) for r in rows]

    if not closes:
        return dict(bars=0, age=None, recovery=None, decline=None,
                    ratio=None, streak=0,
                    distance_class='NO_CONFIRMED_PEAK',
                    ratio_class='RATIO_UNAVAILABLE')

    streak = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] < closes[i - 1]:
            streak += 1
        else:
            break

    # A local close peak is confirmed only after a lower close.
    peaks = [j for j in range(1, len(closes) - 1)
             if closes[j] > closes[j - 1]
             and closes[j] > closes[j + 1]]

    if not peaks:
        return dict(bars=len(closes), age=None,
                    recovery=None, decline=None, ratio=None,
                    streak=streak,
                    distance_class='NO_CONFIRMED_PEAK',
                    ratio_class='RATIO_UNAVAILABLE')

    j = peaks[-1]

    # Look back at most six completed closes before the peak.
    trough = min(closes[max(0, j - 6):j + 1])

    recovery = pct(closes[j], trough)

    # Positive value means price has declined since the peak.
    decline = pct(closes[j], closes[-1])

    ratio = (
        decline / recovery
        if recovery is not None and recovery > 0
        else None
    )

    return dict(
        bars=len(closes),
        age=len(closes) - 1 - j,
        recovery=recovery,
        decline=decline,
        ratio=ratio,
        streak=streak,
        distance_class=classify_displacement(decline),
        ratio_class=classify_ratio(ratio),
    )


def summarize(label, records, key):
    print('\n' + label)

    groups = defaultdict(list)
    for r in records:
        groups[r[key]].append(r)

    for name, group in sorted(groups.items()):
        w = sum(r['net'] > 0 for r in group)
        l = sum(r['net'] < 0 for r in group)
        net = sum(r['net'] for r in group)

        print(
            f'{name:40s} '
            f'N={len(group):2d} '
            f'W={w:2d} '
            f'L={l:2d} '
            f'NET={net:+.6f}%'
        )


def report(label, records, detailed=True):
    print('\n' + '=' * 105)
    print(label)
    print('=' * 105)

    summarize(
        'DECLINE FROM LAST CONFIRMED CLOSE PEAK',
        records,
        'distance_class'
    )
    summarize(
        'DECLINE / PRECEDING RECOVERY RATIO',
        records,
        'ratio_class'
    )
    summarize('PEAK AGE', records, 'age_class')

    if detailed:
        print('\nTRADE AUDIT')

        for r in records:
            ratio_text = (
                'NA' if r['ratio'] is None
                else f'{r["ratio"]:.2f}x'
            )

            print(
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'AGE={r["age"]} '
                f'BARS={r["bars"]} '
                f'STREAK={r["streak"]} '
                f'RECOVERY={fmt(r["recovery"])} '
                f'DECLINE={fmt(r["decline"])} '
                f'RATIO={ratio_text} '
                f'CLASS={r["distance_class"]}'
            )


def main():
    print('AIMn — STEP 59F-5H-43K-28')
    print('PEAK-TO-ENTRY DISPLACEMENT AND ENTRY TIMING')
    print('READ-ONLY OBSERVATIONAL AUDIT')

    all_records = []

    for name, (path, expected_count, expected_net) in DATASETS.items():
        rows = load(path)
        result = engine.run(rows=rows, **PARAMS)

        assert result['trade_count'] == expected_count, (
            f'{name} trade count changed'
        )
        assert abs(result['net_pnl_pct'] - expected_net) < 0.000002, (
            f'{name} net changed'
        )

        index = {
            dt(row['timestamp']): i
            for i, row in enumerate(rows)
        }

        records = []

        for trade in result['trades']:
            entry = dt(trade['entry_time'])
            i = index[entry]

            # No entry candle or future candle is passed.
            metrics = measure(rows[:i], entry)

            age = metrics['age']
            age_class = (
                'NO_PEAK' if age is None
                else 'RECENT_1_TO_2' if age <= 2
                else 'OLDER_3_PLUS'
            )

            records.append(
                dict(
                    dataset=name,
                    time=str(entry),
                    net=float(trade['net_pnl_pct']),
                    age_class=age_class,
                    **metrics
                )
            )

        assert len(records) == expected_count
        report(name, records)
        all_records.extend(records)

    assert len(all_records) == 36
    assert abs(
        sum(r['net'] for r in all_records) - 8.984294
    ) < 0.000002

    report(
        'COMBINED — DESCRIPTIVE ONLY',
        all_records,
        detailed=False
    )

    print('\nPRIORITY CASES')

    for r in all_records:
        if r['time'][:10] in PRIORITY:
            ratio_text = (
                'NA' if r['ratio'] is None
                else f'{r["ratio"]:.2f}x'
            )

            print(
                f'{r["dataset"]:10s} '
                f'{r["time"]} '
                f'NET={r["net"]:+.6f}% '
                f'AGE={r["age"]} '
                f'STREAK={r["streak"]} '
                f'RECOVERY={fmt(r["recovery"])} '
                f'DECLINE={fmt(r["decline"])} '
                f'RATIO={ratio_text}'
            )

    print('\nLIMITATIONS:')
    print('Only completed same-day candles before entry were used.')
    print('Local close peak is not a confirmed major trend reversal.')
    print('Recovery uses a six-close lookback and is descriptive.')
    print('Decline from peak is not a forecast of remaining opportunity.')
    print('Ratio can be unstable for tiny recoveries.')
    print('No entry filters, no changes to V18, no files written.')

    print('STEP 59F-5H-43K-28: PASS')


if __name__ == '__main__':
    main()
