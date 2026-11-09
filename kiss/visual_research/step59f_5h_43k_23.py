
"""AIMn 59F-5H-43K-23: read-only 5m/30m structure audit.
Run from the repository root. No output files are written.
"""
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

LAB = Path('kiss/visual_research')
sys.path.insert(0, str(LAB.resolve()))
import step59f_5h43c_flat_long_replay as engine

PARAMS = dict(entry_cutoff='15:45', commission_pct=0.01,
              entry_slippage_pct=0.02, exit_slippage_pct=0.02,
              trailing_minus_pct=1.5, rsi_rescue_short=80.0,
              atr_exhaustion_filter=True, flat_long_filter=True)
DATASETS = {'RESEARCH': (LAB/'aimn_nvda_candles.json', 22, 6.764673),
            'VALIDATION': (LAB/'nvda_sep_oct_2026_validation.json', 14, 2.219621)}

def timestamp(value):
    return datetime.fromisoformat(str(value))

def read_rows(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = data['candles'] if isinstance(data, dict) else data
    rows = sorted(rows, key=lambda r: timestamp(r['timestamp']))
    times = [timestamp(r['timestamp']) for r in rows]
    assert len(times) == len(set(times)), 'Duplicate candle timestamps'
    return rows

def prior_5m(rows, index, limit=30):
    entry_time = timestamp(rows[index]['timestamp'])
    subset = rows[max(0, index-limit):index]
    if not subset or entry_time-timestamp(subset[-1]['timestamp']) != timedelta(minutes=5):
        return []
    start = len(subset)-1
    while start and timestamp(subset[start]['timestamp'])-timestamp(subset[start-1]['timestamp']) == timedelta(minutes=5):
        start -= 1
    return subset[start:]

def completed_30m(rows, entry_time):
    """Build 30m bars from 5m start timestamps; require all six 5m bars.
    A 30m bar is usable only when its end <= entry_time.
    """
    groups = {}
    for r in rows:
        t = timestamp(r['timestamp'])
        if t >= entry_time or t.date() != entry_time.date():
            continue
        start = t.replace(minute=(t.minute//30)*30, second=0, microsecond=0)
        if start.hour < 9 or (start.hour == 9 and start.minute < 30):
            continue
        if start + timedelta(minutes=30) > entry_time:
            continue
        groups.setdefault(start, []).append(r)
    result = []
    for start in sorted(groups):
        group = sorted(groups[start], key=lambda r: timestamp(r['timestamp']))
        expected = [start+timedelta(minutes=5*i) for i in range(6)]
        if [timestamp(r['timestamp']) for r in group] != expected:
            continue
        result.append({'start': start, 'open': float(group[0]['open']),
                       'close': float(group[-1]['close']),
                       'high': max(float(r['high']) for r in group),
                       'low': min(float(r['low']) for r in group)})
    return result

def classify_30m(bars):
    if len(bars) < 3:
        return '30M_INSUFFICIENT', None
    last = bars[-3:]
    closes = [b['close'] for b in last]
    changes = [(closes[i]/closes[i-1]-1)*100 for i in (1,2)]
    if changes[0] > 0 and changes[1] < 0:
        state = '30M_UP_TO_DOWN'
    elif changes[0] < 0 and changes[1] < 0:
        state = '30M_DOWN_CONTINUATION'
    elif changes[0] > 0 and changes[1] > 0:
        state = '30M_UP_CONTINUATION'
    elif changes[0] < 0 and changes[1] > 0:
        state = '30M_DOWN_TO_UP'
    else:
        state = '30M_FLAT_OR_MIXED'
    return state, changes

def classify_5m(prior):
    if len(prior) < 3:
        return '5M_INSUFFICIENT', None
    closes = [float(r['close']) for r in prior]
    steps = [(closes[i]/closes[i-1]-1)*100 for i in range(1,len(closes))]
    streak = 0
    for step in reversed(steps):
        if step < 0:
            streak += 1
        else:
            break
    if streak == 1 and len(steps) >= 2 and steps[-2] > 0:
        state = '5M_FIRST_DOWN_TURN'
    elif streak == 2 and len(steps) >= 3 and steps[-3] > 0:
        state = '5M_SECOND_DOWN'
    elif streak >= 3:
        state = '5M_DOWN_CONTINUATION'
    elif streak == 0:
        state = '5M_NOT_FALLING'
    else:
        state = '5M_UNCONFIRMED_SEQUENCE'
    return state, streak

def describe(name, records):
    print('\n'+'='*95+'\n'+name+'\n'+'='*95)
    for field in ('state30', 'state5', 'joint'):
        print('\n'+field.upper())
        for state in sorted(set(r[field] for r in records)):
            group = [r for r in records if r[field] == state]
            w = sum(r['net'] > 0 for r in group)
            l = sum(r['net'] < 0 for r in group)
            net = sum(r['net'] for r in group)
            print(f'{state:55s} N={len(group):2d} W={w:2d} L={l:2d} NET={net:+.6f}%')
    print('\nTRADE AUDIT')
    for r in records:
        print(f"{r['entry']} NET={r['net']:+.6f}%  {r['state30']} / {r['state5']} "
              f"30M_BARS={r['bars30']} 30M_STEPS={r['steps30']} 5M_STREAK={r['streak5']} "
              f"EXEC_BELOW_ENTRY_OPEN={r['slippage']:.5f}%")

def main():
    print('AIMn — STEP 59F-5H-43K-23')
    print('MAJOR TREND TRANSITION VS LOCAL RECOVERY — OBSERVATIONAL ONLY')
    combined = []
    total_net = 0.0
    for name,(path,expected_count,expected_net) in DATASETS.items():
        rows = read_rows(path)
        result = engine.run(rows=rows, **PARAMS)
        assert result['trade_count'] == expected_count, f'{name}: count changed'
        assert abs(result['net_pnl_pct']-expected_net) < 0.000002, f'{name}: net changed'
        indexes = {timestamp(r['timestamp']): i for i,r in enumerate(rows)}
        records = []
        for trade in result['trades']:
            t = timestamp(trade['entry_time'])
            assert t in indexes, f'Entry missing {t}'
            i = indexes[t]
            open_price = float(rows[i]['open'])
            execution = float(trade['entry_price'])
            assert open_price > 0 and execution > 0
            slippage = (1-execution/open_price)*100
            assert abs(slippage-PARAMS['entry_slippage_pct']) < 0.0001
            prior = prior_5m(rows,i)
            bars30 = completed_30m(rows,t)
            state30,steps30 = classify_30m(bars30)
            state5,streak5 = classify_5m(prior)
            record = dict(entry=str(t), net=float(trade['net_pnl_pct']),
                          state30=state30,state5=state5,
                          joint=state30+' / '+state5,
                          bars30=len(bars30),steps30=steps30,
                          streak5=streak5,slippage=slippage)
            records.append(record)
        assert len(records) == expected_count
        describe(name, records)
        combined.extend(records)
        total_net += result['net_pnl_pct']
    assert len(combined) == 36
    assert abs(total_net-8.984294) < 0.000002
    describe('COMBINED (DESCRIPTIVE ONLY)',combined)
    print('\nCAUTION: 30m classifications are short-horizon close patterns, NOT proven major trends.')
    print('Only complete 30m bars ending by entry time; no partial 30m candles.')
    print('No lookahead. V18 unchanged. No files created or modified.')
    print('STEP 59F-5H-43K-23: PASS')

if __name__ == '__main__':
    main()
