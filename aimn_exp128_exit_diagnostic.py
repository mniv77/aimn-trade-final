#!/usr/bin/env python3
"""EXP128: read-only, causal diagnostic of frozen EXP126 NVDA W12 exits.

Reads existing holdout OHLC and EXP126 trade/signal CSVs. Reconstructs
EXP125's indicator and W12 decision conditions without calling replay()
(or any report-writing function). Writes NEW files under EXP128 only.
This is an analysis of previously inspected holdout data, NOT validation.
"""
import csv
import json
from collections import Counter
from pathlib import Path

import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp121_joint_momentum_replay as exp121

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'kiss/visual_research/independent_holdout_exp127/nvda_sep_oct_2026_5m_iex.json'
TRADES = ROOT / 'kiss/results/exp126_independent_validation/nvda_w12_0p10_trades.csv'
SIGNALS = ROOT / 'kiss/results/exp126_independent_validation/nvda_w12_0p10_signals.csv'
OUT = ROOT / 'kiss/results/exp128_exit_diagnostic'
THRESHOLD = 0.10


def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def fmt(v):
    return '' if v is None else v


def main():
    for path in (SOURCE, TRADES, SIGNALS):
        if not path.is_file():
            raise FileNotFoundError(f'Required input missing: {path}')
    rows = json.loads(SOURCE.read_text(encoding='utf-8'))
    rows.sort(key=lambda r: str(r['timestamp']))
    times = [str(r['timestamp']) for r in rows]
    if len(set(times)) != len(times):
        raise ValueError('Duplicate OHLC timestamps')
    index = {t: i for i, t in enumerate(times)}
    closes = [float(r['close']) for r in rows]
    starts = swing.get_session_starts(times)
    ph, pl, counts = swing.confirmed_pivots(rows, times, starts)
    states = [swing.structure(rows, times, starts, i, ph, pl, counts)
              for i in range(len(rows))]
    st = base.calculate_supertrend(rows, atr_period=10, multiplier=3.0)['st_trend'].tolist()
    rsi = base.rsi_wilder(closes)
    trades = read_csv(TRADES)
    signals = read_csv(SIGNALS)
    signal_keys = {(s['entry_time'], s['signal_time']) for s in signals}
    if len(trades) != 6:
        raise AssertionError(f'Expected six frozen NVDA trades, got {len(trades)}')

    report = []
    per_trade = []
    for trade in trades:
        entry_time, exit_time = trade['entry_time'], trade['exit_time']
        if entry_time not in index or exit_time not in index:
            raise ValueError(f'Trade timestamp missing: {entry_time} / {exit_time}')
        first, last = index[entry_time], index[exit_time]
        if last < first:
            raise ValueError(f'Exit precedes entry: {entry_time}')
        entry = float(trade['entry_price'])
        fee_seen = False
        lowest_close = entry
        max_gross_close = 0.0
        reasons = Counter()
        actual_signal_count = 0
        for i in range(first, last + 1):
            # EXP125 executes a pending exit at this candle's OPEN, before
            # examining its high/low/close. Exclude that candle on exit day.
            is_exit_open = (i == last and trade['exit_reason'] != 'SESSION_END'
                            and trade['exit_reason'] != 'DATA_END'
                            and trade['exit_reason'] != 'STOP_LOSS')
            # Session-end exits occur at the final candle CLOSE, and their
            # closing state is still observable. STOP_LOSS may occur intrabar:
            # its close is not causally available at the time of exit.
            is_stop_exit = (i == last and trade['exit_reason'] == 'STOP_LOSS')
            if is_exit_open or is_stop_exit:
                continue
            if times[i][:10] != entry_time[:10]:
                raise AssertionError('Unexpected cross-session trade')
            c = closes[i]
            lowest_close = min(lowest_close, c)
            gross_close = 100 * (entry / c - 1)
            max_gross_close = max(max_gross_close, gross_close)
            if gross_close > 2 * exp79.FEE:
                fee_seen = True
            state = states[i]
            higher_low = state['low_sequence'] == 'HIGHER_LOW'
            high_break = state['close_above_last_confirmed_high'] == 1
            m = exp121.momentum(rows, closes, starts, i)
            st_flip = i > 0 and st[i - 1] == 'SHORT' and st[i] == 'LONG'
            rsi_rescue = rsi[i] is not None and rsi[i] >= exp79.RSI_LIMIT
            next_same_day = i + 1 < len(rows) and times[i + 1][:10] == times[i][:10]
            stop_price = entry * (1 + exp79.STOP_PCT / 100)
            stop_hit = float(rows[i]['high']) >= stop_price
            if stop_hit:
                decision = 'STOP_LOSS_INTRABAR'
            elif not next_same_day:
                decision = 'NO_NEXT_SAME_SESSION_CANDLE'
            elif st_flip:
                decision = 'ST_REVERSE_PRIORITY'
            elif rsi_rescue:
                decision = 'RSI_RESCUE_PRIORITY'
            elif not fee_seen:
                decision = 'FEE_COVER_NOT_SEEN'
            elif not higher_low:
                decision = 'NO_CONFIRMED_HIGHER_LOW'
            elif not high_break:
                decision = 'NO_CLOSE_ABOVE_CONFIRMED_HIGH'
            elif m is None:
                decision = 'W12_UNAVAILABLE_SAME_SESSION'
            elif m <= THRESHOLD:
                decision = 'W12_NOT_ABOVE_THRESHOLD'
            else:
                decision = 'W12_SIGNAL'
            actual_signal = (entry_time, times[i]) in signal_keys
            if actual_signal:
                actual_signal_count += 1
                if decision != 'W12_SIGNAL':
                    raise AssertionError(f'Saved W12 signal does not reproduce at {times[i]}: {decision}')
            if decision == 'W12_SIGNAL' and not actual_signal:
                raise AssertionError(f'Unrecorded reconstructed W12 signal at {times[i]}')
            reasons[decision] += 1
            report.append({
                'entry_time': entry_time,
                'exit_time': exit_time,
                'exit_reason': trade['exit_reason'],
                'candle_time': times[i],
                'open': rows[i]['open'], 'high': rows[i]['high'],
                'low': rows[i]['low'], 'close': rows[i]['close'],
                'entry_price': entry,
                'gross_profit_at_close_pct': round(gross_close, 6),
                'max_gross_profit_at_close_so_far_pct': round(max_gross_close, 6),
                'giveback_from_best_close_pp': round(max_gross_close - gross_close, 6),
                'fee_cover_seen': int(fee_seen),
                'low_sequence': state['low_sequence'],
                'higher_low': int(higher_low),
                'latest_low_pivot_time': fmt(state['latest_low_pivot_time']),
                'latest_low_confirmed_time': fmt(state['latest_low_confirmed_time']),
                'latest_low_price': fmt(state['latest_low_price']),
                'latest_high_pivot_time': fmt(state['latest_high_pivot_time']),
                'latest_high_confirmed_time': fmt(state['latest_high_confirmed_time']),
                'latest_high_price': fmt(state['latest_high_price']),
                'close_above_last_confirmed_high': fmt(state['close_above_last_confirmed_high']),
                'w12_pct': '' if m is None else round(m, 6),
                'w12_above_threshold': '' if m is None else int(m > THRESHOLD),
                'supertrend': st[i],
                'supertrend_flip_short_to_long': int(st_flip),
                'rsi': '' if rsi[i] is None else round(float(rsi[i]), 6),
                'rsi_rescue': int(rsi_rescue),
                'stop_hit_in_candle': int(stop_hit),
                'next_candle_same_session': int(next_same_day),
                'decision': decision,
                'saved_w12_signal': int(actual_signal),
            })
        expected_signals = sum(s['entry_time'] == entry_time for s in signals)
        if actual_signal_count != expected_signals:
            raise AssertionError(f'Signal count mismatch for {entry_time}')
        per_trade.append({
            'entry_time': entry_time,
            'exit_time': exit_time,
            'exit_reason': trade['exit_reason'],
            'saved_net_pnl_pct': trade['net_pnl_pct'],
            'saved_best_close_short_pct': trade['best_close_short_pct'],
            'saved_w12_signals': expected_signals,
            'diagnostic_candles': sum(r['entry_time'] == entry_time for r in report),
            'decision_counts': dict(reasons),
        })
    if sum(x['saved_w12_signals'] for x in per_trade) != len(signals):
        raise AssertionError('Signal CSV includes unexpected trade')
    OUT.mkdir(parents=True, exist_ok=True)
    detail = OUT / 'nvda_candle_decisions.csv'
    with detail.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(report[0]))
        writer.writeheader()
        writer.writerows(report)
    summary = {
        'experiment': 'EXP128',
        'research_only': True,
        'purpose': 'Diagnostic of already inspected holdout; not independent validation',
        'source_ohlc': str(SOURCE),
        'source_trades': str(TRADES),
        'source_signals': str(SIGNALS),
        'threshold_pct': THRESHOLD,
        'trades': per_trade,
        'limitations': [
            'No new entries or exits are simulated.',
            'Intrabar stop-loss exit candle is excluded from close-based diagnostics.',
            'Next-open exit candle is excluded because its close was unavailable at exit.',
            'The final session candle can be observed but cannot schedule a next-session exit.',
            'Saved best-close metric is not necessarily a realizable fill.',
        ],
    }
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('EXP128 — READ-ONLY NVDA EXIT DIAGNOSTIC')
    print('Candles audited:', len(report), 'Trades:', len(per_trade))
    for t in per_trade:
        print(t['entry_time'], '=>', t['exit_time'], t['exit_reason'],
              'signals:', t['saved_w12_signals'], 'decisions:', t['decision_counts'])
    print('New diagnostic files:', detail, OUT / 'summary.json')
    print('EXP125/126/127 and production files unchanged.')


if __name__ == '__main__':
    main()
