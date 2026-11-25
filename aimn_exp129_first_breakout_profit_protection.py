#!/usr/bin/env python3
"""EXP129: independent in-memory SHORT first-high-break profit-protection replay.
Read-only: does not write files or alter any trading modules.
"""
import json
from collections import Counter

import aimn_exp83_v16_structural_exit as base
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp117_full_swing_replay as exp117

REPORT = 'kiss/results/exp128_confirmation_delay_audit.json'


def prepare(path):
    with open(path, encoding='utf-8') as f:
        rows = json.load(f)
    rows.sort(key=lambda r: str(r['timestamp']))
    times = [str(r['timestamp']) for r in rows]
    assert len(times) == len(set(times)), 'Duplicate candle timestamps'
    closes = [float(r['close']) for r in rows]
    starts = swing.get_session_starts(times)
    ph, pl, counts = swing.confirmed_pivots(rows, times, starts)
    states = [swing.structure(rows, times, starts, i, ph, pl, counts)
              for i in range(len(rows))]
    st = base.calculate_supertrend(rows, atr_period=10, multiplier=3.0)['st_trend'].tolist()
    rsi = base.rsi_wilder(closes)
    market = [base.get_market_state(closes, i) for i in range(len(rows))]
    return rows, times, states, st, rsi, market


def candidate_replay(rows, times, states, st, rsi, market):
    """Mirror EXP117, adding only one lowest-priority next-open warning exit."""
    opens = [float(r['open']) for r in rows]
    closes = [float(r['close']) for r in rows]
    highs = [float(r['high']) for r in rows]
    lows = [float(r['low']) for r in rows]
    n = len(rows)
    pos = None
    pending = None
    trades = []
    warnings = []
    for i in range(35, n):
        day = times[i][:10]
        if day != times[i-1][:10]:
            if pos is not None:
                trades.append(exp117.exp79.finish(pos, i-1, closes[i-1], 'SESSION_END', times))
                pos = None
            pending = None
        exited_at_open = False
        if pending is not None:
            action = pending
            pending = None
            if action == 'ENTER' and pos is None:
                pos = {'entry_time': times[i], 'entry_price': opens[i],
                       'entry_index': i, 'lowest_close': opens[i],
                       'fee_cover_seen': False, 'first_high_break_seen': False}
            elif action != 'ENTER' and pos is not None:
                trades.append(exp117.exp79.finish(pos, i, opens[i], action, times))
                pos = None
                exited_at_open = True
        if pos is not None:
            stop = pos['entry_price'] * (1 + exp117.exp79.STOP_PCT / 100)
            if highs[i] >= stop:
                trades.append(exp117.exp79.finish(pos, i, max(stop, opens[i]), 'STOP_LOSS', times))
                pos = None
                pending = None
            else:
                pos['lowest_close'] = min(pos['lowest_close'], closes[i])
                gross_close = (pos['entry_price'] / closes[i] - 1) * 100
                if gross_close > 2 * exp117.exp79.FEE:
                    pos['fee_cover_seen'] = True
                # Record the first high-break only once per position, regardless
                # of whether the trade is profitable at that moment.
                first_break = (not pos['first_high_break_seen'] and
                               states[i]['close_above_last_confirmed_high'] == 1)
                if first_break:
                    pos['first_high_break_seen'] = True
                    warnings.append({'entry_time': pos['entry_time'],
                                     'warning_time': times[i],
                                     'net_at_close': round(gross_close - 2 * exp117.exp79.FEE, 6),
                                     'eligible': gross_close > 2 * exp117.exp79.FEE})
                if i + 1 < n and times[i+1][:10] == day:
                    if st[i-1] == 'SHORT' and st[i] == 'LONG':
                        pending = 'ST_REVERSE'
                    elif rsi[i] is not None and rsi[i] >= exp117.exp79.RSI_LIMIT:
                        pending = 'RSI_RESCUE'
                    elif (pos['fee_cover_seen'] and
                          states[i]['low_sequence'] == 'HIGHER_LOW' and
                          states[i]['close_above_last_confirmed_high'] == 1):
                        pending = 'CONFIRMED_SWING_REVERSE'
                    elif first_break and gross_close > 2 * exp117.exp79.FEE:
                        pending = 'FIRST_HIGH_BREAK_PROFIT'
        candidate = base.is_major_long_to_short_reversal(highs, lows, closes, market, i) is not None
        if candidate:
            if pos is not None or exited_at_open or pending in (
                    'ST_REVERSE', 'RSI_RESCUE', 'CONFIRMED_SWING_REVERSE',
                    'FIRST_HIGH_BREAK_PROFIT'):
                pass
            elif pending == 'ENTER':
                pass
            elif st[i] != 'LONG':
                pass
            elif i + 1 >= n or times[i+1][:10] != day:
                pass
            else:
                pending = 'ENTER'
    if pos is not None:
        trades.append(exp117.exp79.finish(pos, n-1, closes[-1], 'DATA_END', times))
    return trades, warnings


def main():
    with open(REPORT, encoding='utf-8') as f:
        report = json.load(f)
    totals = {'baseline': 0.0, 'candidate': 0.0}
    for symbol, info in report['symbols'].items():
        rows, times, states, st, rsi, market = prepare(info['source'])
        baseline, _, _, _ = exp117.simulate(rows, st, rsi, market, states, 'JOINT_SWING')
        frozen = {t['entry_time']: t for t in info['trades_detail']}
        assert len(baseline) == len(frozen), f'{symbol}: baseline count mismatch'
        for trade in baseline:
            ref = frozen[trade['entry_time']]
            assert trade['exit_time'] == ref['structural_exit_time'], f'{symbol}: exit mismatch'
            assert trade['exit_reason'] == ref['structural_exit_reason'], f'{symbol}: reason mismatch'
            assert abs(trade['net_pnl_pct'] - ref['structural_net_pct']) < 0.000001, f'{symbol}: P&L mismatch'
        candidate, warnings = candidate_replay(rows, times, states, st, rsi, market)
        bnet = round(sum(t['net_pnl_pct'] for t in baseline), 6)
        cnet = round(sum(t['net_pnl_pct'] for t in candidate), 6)
        totals['baseline'] += bnet
        totals['candidate'] += cnet
        bmap = {t['entry_time']: t for t in baseline}
        cmap = {t['entry_time']: t for t in candidate}
        print(f'\n{symbol} — BASELINE PARITY PASS')
        print(f'Baseline: {len(baseline)} trades, net {bnet:+.6f}%')
        print(f'Candidate: {len(candidate)} trades, net {cnet:+.6f}%')
        print(f'Delta: {cnet-bnet:+.6f} percentage points')
        print('Candidate exit reasons:', dict(Counter(t['exit_reason'] for t in candidate)))
        print('Warnings:', len(warnings), 'eligible:', sum(w['eligible'] for w in warnings))
        print('New entries:', sorted(set(cmap) - set(bmap)))
        print('Missing entries:', sorted(set(bmap) - set(cmap)))
        for entry in sorted(set(bmap) | set(cmap)):
            a, b = bmap.get(entry), cmap.get(entry)
            if a is None:
                print('NEW', entry, b['exit_time'], b['exit_reason'], b['net_pnl_pct'])
            elif b is None:
                print('MISSING', entry, a['exit_time'], a['exit_reason'], a['net_pnl_pct'])
            elif (a['exit_time'], a['exit_reason'], a['net_pnl_pct']) != (b['exit_time'], b['exit_reason'], b['net_pnl_pct']):
                print('CHANGED', entry, 'baseline:', a['exit_time'], a['exit_reason'], a['net_pnl_pct'],
                      'candidate:', b['exit_time'], b['exit_reason'], b['net_pnl_pct'])
        for w in warnings:
            print('WARNING', w['entry_time'], w['warning_time'],
                  'net_close:', w['net_at_close'], 'eligible:', w['eligible'])
    assert abs(totals['baseline'] - (-1.613417)) < 0.000001, 'Frozen combined baseline mismatch'
    print('\nCOMBINED BASELINE:', f"{totals['baseline']:+.6f}%")
    print('COMBINED CANDIDATE:', f"{totals['candidate']:+.6f}%")
    print('COMBINED DELTA:', f"{totals['candidate']-totals['baseline']:+.6f} percentage points")
    print('RESEARCH ONLY — no files written')


if __name__ == '__main__':
    main()
