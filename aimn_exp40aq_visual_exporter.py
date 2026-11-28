#!/usr/bin/env python3
"""EXP40-AQ: export frozen AM3 discovery events; no strategy execution."""
import csv
import hashlib
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent
AM = ROOT / 'kiss/results/exp40am_relative_trajectory_replay'
AJ = ROOT / 'kiss/results/exp40aj_transition_monitoring_replay'
SOURCE = ROOT / 'kiss/visual_research/aimn_nvda_candles.json'
OUT = ROOT / 'static/aimn_visual_lab/aimn_am3_transition_data.json'
HASHES = {
    AM / 'JUN_AUG_AM3_candidates.csv': '5e5b62a4deadfd534ce94ec88d85bbf69f92bdb55b9b3c919c82ab7825fca3aa',
    AM / 'JUN_AUG_AM3_gate.csv': '22c7dcd93c7465746a0e0d666a2840641c71ba22f97afa226a15de77a7d6f7ec',
    AM / 'JUN_AUG_AM3_trades.csv': '8f2e34e3aef01e7100be40a873bead392e153b562ee63980598781ab5f6858aa',
    AJ / 'JUN_AUG_AJ1_warnings.csv': 'e566d99f1b0d111a90686746a827aae017ea53eba64a265389a1105f2bcb6494',
    SOURCE: '020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def number(value):
    return None if value is None or value.strip() == '' else float(value)


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    for path, expected in HASHES.items():
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                f'Fingerprint mismatch: {path}')
    rows = json.loads(SOURCE.read_text())
    warnings = read(AJ / 'JUN_AUG_AJ1_warnings.csv')
    gates = read(AM / 'JUN_AUG_AM3_gate.csv')
    candidates = read(AM / 'JUN_AUG_AM3_candidates.csv')
    trades = read(AM / 'JUN_AUG_AM3_trades.csv')
    require((len(rows), len(warnings), len(gates), len(candidates), len(trades)) ==
            (4680,104,38,13,11), 'Unexpected reference counts')
    times = [r['timestamp'] for r in rows]
    require(times == sorted(set(times)), 'Invalid candle chronology')
    index = {t:i for i,t in enumerate(times)}
    events = []

    def emit(t, kind, **fields):
        require(t in index, f'Unknown event candle {t}')
        events.append(dict(candle_index=index[t], candle_time=t, kind=kind, **fields))

    authorized = {}
    for w in warnings:
        t, end = w['warning_time'], w['resolution_time']
        i = index[t]
        require(i == int(w['warning_index']) and i > 0, 'Warning index mismatch')
        require(abs(float(w['original_peak']) - float(rows[i-1]['high'])) < 1e-8,
                'Peak mismatch')
        require(index[end] >= i, 'Resolution predates warning')
        emit(t, 'AE3_WARNING', warning_time=t, original_peak=float(w['original_peak']))
        if w['status'] == 'AUTHORIZED':
            require(end not in authorized, 'Duplicate authorization')
            require(index[end] == i+1, 'AJ1 must resolve next candle')
            authorized[end] = t
            emit(end, 'AJ1_CONFIRMED', warning_time=t)
        else:
            emit(end, 'AJ1_REJECTED', warning_time=t, reason=w['status'])
    require(len(authorized)==38, 'Authorization count mismatch')
    passed = set()
    require(len({g['signal_time'] for g in gates})==38, 'Duplicate gate')
    for g in gates:
        t = g['signal_time']
        require(authorized[t]==g['warning_time'], 'Warning/gate mismatch')
        w12 = number(g['w12'])
        expected = 'MISSING' if w12 is None else 'PASS' if w12 >= .60 else 'BELOW_THRESHOLD'
        require(g['decision']==expected, 'Gate threshold mismatch')
        emit(t, 'AM3_GATE', warning_time=g['warning_time'], w12=w12,
             w6=number(g['w6']), decision=expected, threshold=.60)
        if expected=='PASS': passed.add(t)
    require(len(passed)==13, 'PASS count mismatch')
    require({c['signal_time'] for c in candidates}==passed, 'Candidate mismatch')
    scheduled=set()
    for c in candidates:
        t=c['signal_time']
        require(c['warning_time']==authorized[t], 'Candidate warning mismatch')
        emit(t,'EXECUTION_DECISION', status=c['status'], st5=c['st5'], st30=c['st30'],
             major_available=c['major_available'])
        if c['status']=='SCHEDULED': scheduled.add(t)
    require({t['signal_time'] for t in trades}==scheduled, 'Scheduled trade mismatch')
    for n,t in enumerate(trades,1):
        a,b,c=t['signal_time'],t['entry_time'],t['exit_time']
        require(index[b]==index[a]+1 and index[c]>=index[b], 'Trade chronology mismatch')
        require(a[:10]==b[:10]==c[:10], 'Unexpected overnight trade')
        emit(b,'ENTRY', trade_id=n, price=float(t['entry_price']), signal_time=a)
        emit(c,'EXIT', trade_id=n, price=float(t['exit_price']), reason=t['exit_reason'],
             phase=t['exit_phase'], net_pct=float(t['net_pnl_pct']))
    wins=sum(float(t['net_pnl_pct'])>0 for t in trades)
    net=round(sum(float(t['net_pnl_pct']) for t in trades),6)
    require(wins==6 and net==.18122, 'Frozen AM3 result mismatch')
    # Stable ordering within each completed candle. No future fields on warning/entry events.
    order={k:i for i,k in enumerate(('EXIT','ENTRY','AE3_WARNING','AJ1_CONFIRMED','AJ1_REJECTED','AM3_GATE','EXECUTION_DECISION'))}
    # Same-candle entry and exit must display entry first; no existing overlapping positions.
    order['ENTRY']=0; order['EXIT']=1
    events.sort(key=lambda e:(e['candle_index'],order[e['kind']]))
    payload=dict(schema='aimn-am3-visual-v1',symbol='NVDA',direction='SHORT',timeframe='5m',
                 period='JUN_AUG',threshold=.60, research_only=True,
                 timestamp_semantics='Source candle labels are New York local wall-clock; match by full OHLC and consistent timestamp mapping. Reveal events only at completed candle.',
                 source_hashes={str(p.relative_to(ROOT)):h for p,h in HASHES.items()},
                 candles=[[r['timestamp'],r['open'],r['high'],r['low'],r['close']] for r in rows],
                 events=events)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('x',encoding='utf-8') as f:
        json.dump(payload,f,separators=(',',':'),allow_nan=False)
        f.write('\n')
    print('SOURCE FINGERPRINTS PASSED')
    print('CANDLES',len(rows),'EVENTS',len(events))
    print('EVENT COUNTS',dict(Counter(e['kind'] for e in events)))
    print('FROZEN AM3 PARITY PASSED:',len(trades),'trades;',wins,'winners;',net,'net pct')
    print('Saved:',OUT)
    print('EXPORT ONLY — no orders or strategy changes. UI integration not installed.')


if __name__=='__main__':
    main()
