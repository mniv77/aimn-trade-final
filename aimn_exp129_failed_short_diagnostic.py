#!/usr/bin/env python3
"""EXP129: read-only diagnostic of adverse SHORT structure on frozen NVDA holdout.

Inputs: EXP128 candle decisions, EXP126 frozen W12 trades, EXP127 IEX candles.
No production imports, strategy modifications, or parameter optimization.
Outputs are new CSV/JSON reports in kiss/results/exp129_failed_short_diagnostic.
"""
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AUDIT = ROOT / 'kiss/results/exp128_exit_diagnostic/nvda_candle_decisions.csv'
TRADES = ROOT / 'kiss/results/exp126_independent_validation/nvda_w12_0p10_trades.csv'
CANDLES = ROOT / 'kiss/visual_research/independent_holdout_exp127/nvda_sep_oct_2026_5m_iex.json'
OUT = ROOT / 'kiss/results/exp129_failed_short_diagnostic'
FEE_PER_SIDE_PCT = 0.10  # Frozen experiment convention
W12_REFERENCE_PCT = 0.10  # Frozen EXP125 threshold; not tuned here


def load_csv(path):
    if not path.is_file():
        raise FileNotFoundError(f'Required input missing: {path}')
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def stamp(s):
    s = str(s).strip().replace('Z', '+00:00')
    return datetime.fromisoformat(s).replace(tzinfo=None).isoformat(sep=' ', timespec='seconds')


def number(x):
    return float(x) if x not in (None, '') else None


def write_csv(path, rows, columns):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def main():
    decisions = load_csv(AUDIT)
    trades = load_csv(TRADES)
    if not CANDLES.is_file():
        raise FileNotFoundError(f'Required input missing: {CANDLES}')
    candles = json.loads(CANDLES.read_text(encoding='utf-8'))
    if not isinstance(candles, list):
        raise ValueError('Expected JSON array of OHLC candles')
    by_time = {}
    for c in candles:
        t = stamp(c['timestamp'])
        if t in by_time:
            raise ValueError(f'Duplicate candle timestamp: {t}')
        by_time[t] = c
    ordered = sorted(by_time)
    next_time = {t: ordered[i + 1] if i + 1 < len(ordered) else None for i, t in enumerate(ordered)}
    trades_by_entry = {}
    for t in trades:
        entry = stamp(t['entry_time'])
        if entry in trades_by_entry:
            raise ValueError(f'Duplicate trade entry: {entry}')
        trades_by_entry[entry] = t
    if len(trades) != 6:
        raise ValueError(f'Frozen EXP126 trade count changed: expected 6, got {len(trades)}')

    observations = []
    counts = Counter()
    for d in decisions:
        entry = stamp(d['entry_time'])
        if entry not in trades_by_entry:
            raise ValueError(f'EXP128 entry absent from EXP126: {entry}')
        t = stamp(d['candle_time'])
        if t not in by_time:
            raise ValueError(f'EXP128 candle absent from EXP127: {t}')
        tr = trades_by_entry[entry]
        exit_t = stamp(tr['exit_time'])
        # Only completed candles strictly before the recorded execution time.
        # A SESSION_END exit at that candle close is not an actionable next-open exit.
        if t >= exit_t:
            continue
        if d['close_above_last_confirmed_high'] != '1':
            continue
        w12 = number(d.get('w12_pct'))
        if w12 is None or w12 <= W12_REFERENCE_PCT:
            continue
        nxt = next_time[t]
        if nxt is None or nxt[:10] != t[:10] or nxt > exit_t:
            counts['warning_without_eligible_next_open'] += 1
            continue
        # A pending frozen exit at the same next open takes priority; it is
        # informative but not an independent alternative execution.
        actual_exit_same_open = nxt == exit_t and tr['exit_reason'] not in ('SESSION_END', 'DATA_END')
        entry_price = number(tr['entry_price'])
        next_open = number(by_time[nxt]['open'])
        if entry_price is None or next_open is None or next_open <= 0:
            raise ValueError('Invalid entry or next-open price')
        hypothetical_gross = (entry_price / next_open - 1) * 100
        hypothetical_net = hypothetical_gross - 2 * FEE_PER_SIDE_PCT
        actual_net = number(tr['net_pnl_pct'])
        current_gross = number(d['gross_profit_at_close_pct'])
        category = 'LOSING_AT_WARNING' if current_gross < 0 else ('PROFITABLE_AT_WARNING' if current_gross > 0 else 'BREAKEVEN_AT_WARNING')
        row = {
            'entry_time': entry, 'warning_time': t, 'next_open_time': nxt,
            'original_exit_time': exit_t, 'original_exit_reason': tr['exit_reason'],
            'warning_category': category, 'decision': d['decision'],
            'higher_low': d['higher_low'], 'fee_cover_seen': d['fee_cover_seen'],
            'w12_pct': round(w12, 6), 'gross_at_warning_close_pct': round(current_gross, 6),
            'entry_price': round(entry_price, 6), 'next_open_price': round(next_open, 6),
            'hypothetical_net_pct': round(hypothetical_net, 6),
            'frozen_actual_net_pct': round(actual_net, 6),
            'hypothetical_minus_actual_pp': round(hypothetical_net - actual_net, 6),
            'same_open_as_frozen_exit': int(actual_exit_same_open),
        }
        observations.append(row)
        counts[category] += 1
    observations.sort(key=lambda x: (x['entry_time'], x['warning_time']))

    # Only the earliest warning for each trade is shown as an illustrative
    # single-exit counterfactual; later warnings cannot all be traded.
    first = {}
    for row in observations:
        first.setdefault(row['entry_time'], row)
    first_rows = list(first.values())
    by_entry = {stamp(t['entry_time']): t for t in trades}
    audit = []
    for entry in sorted(by_entry):
        tr = by_entry[entry]
        f = first.get(entry)
        audit.append({
            'entry_time': entry, 'original_exit_time': stamp(tr['exit_time']),
            'original_exit_reason': tr['exit_reason'],
            'frozen_actual_net_pct': tr['net_pnl_pct'],
            'first_warning_time': f['warning_time'] if f else '',
            'first_warning_category': f['warning_category'] if f else '',
            'hypothetical_next_open_time': f['next_open_time'] if f else '',
            'hypothetical_net_pct': f['hypothetical_net_pct'] if f else '',
            'hypothetical_minus_actual_pp': f['hypothetical_minus_actual_pp'] if f else '',
            'warning_count': sum(x['entry_time'] == entry for x in observations),
        })
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / 'all_adverse_breakout_observations.csv', observations,
              list(observations[0]) if observations else [
                  'entry_time','warning_time','next_open_time','warning_category'])
    write_csv(OUT / 'first_warning_per_trade.csv', first_rows,
              list(observations[0]) if observations else [
                  'entry_time','warning_time','next_open_time','warning_category'])
    write_csv(OUT / 'all_six_trades_audit.csv', audit, list(audit[0]))
    report = {
        'experiment': 'EXP129', 'status': 'DIAGNOSTIC_ONLY_NOT_VALIDATED',
        'symbol': 'NVDA', 'direction': 'SHORT',
        'frozen_trades': len(trades), 'audited_candle_rows': len(decisions),
        'qualifying_actionable_warning_observations': len(observations),
        'trades_with_warning': len(first),
        'warning_categories': dict(counts),
        'frozen_actual_net_sum_pct_points': round(sum(number(t['net_pnl_pct']) for t in trades), 6),
        'first_warning_hypothetical_net_sum_for_warned_trades_pct_points': round(sum(x['hypothetical_net_pct'] for x in first_rows), 6),
        'first_warning_frozen_net_sum_for_warned_trades_pct_points': round(sum(x['frozen_actual_net_pct'] for x in first_rows), 6),
        'cautions': [
            'The warning filter is exploratory, selected after viewing the holdout; not independently validated.',
            'Only breakout plus W12 > 0.10 is observed; no new strategy or tuned threshold is proposed.',
            'Every hypothetical exit uses the next same-session candle OPEN, not the warning close.',
            'First-warning comparison is a diagnostic counterfactual, not a complete strategy replay.',
            'A warning that shares a next-open time with an existing frozen exit is not an independent alternative.',
            'The original six trades remain fixed; new entries after hypothetical exits are not simulated.',
            'Commission 0.10% each side; no slippage or market-impact model.',
            'The October 5 same-bar entry/session-close case remains a separate simulation audit item.',
        ],
    }
    (OUT / 'summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('EXP129 — READ-ONLY FAILED-SHORT ENTRY DIAGNOSTIC')
    print('Frozen trades:', len(trades), 'Audited candle rows:', len(decisions))
    print('Qualifying actionable warnings:', len(observations), 'Trades with warnings:', len(first))
    print('Warning categories:', dict(counts))
    for a in audit:
        print(a['entry_time'], 'frozen_net=', a['frozen_actual_net_pct'],
              'first_warning=', a['first_warning_time'] or 'NONE',
              'hypothetical_net=', a['hypothetical_net_pct'] if a['first_warning_time'] else 'N/A')
    print('New reports:', OUT)
    print('No existing experiment or production file modified.')


if __name__ == '__main__':
    main()
