#!/usr/bin/env python3
"""EXP40-Z: fixed X4 trade reverse-transition audit; no orders or strategy edits."""
import csv
import json
import hashlib
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'kiss/results'
SOURCE = RESULTS / 'exp40x_causal_invalidation_replay'
OUT = RESULTS / 'exp40z_reverse_transition_forensics'
FEE = 0.2
SOURCES = {
    'DISCOVERY': ('kiss/visual_research/aimn_nvda_candles.json',
                  '020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50',
                  '48cd41e03afca3a82689cdb67bbecc975e7088d26d68f727da93f14c8bf8bc4d', 4680, 28, 11, -.947155),
    'NOVEMBER': ('kiss/visual_research/independent_holdout_exp40l/nvda_2026-11-16_2026-11-25_5m_iex.json',
                 'eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d',
                 '08f2dc41f2580374689e142c1e5178c78c548ca6343701f9f599ba4e6a2cc3bb', 624, 5, 2, .722305),
}
RULES = ('Z0','Z1','Z2','Z3','Z4')

def checked(path, digest):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f'Frozen source hash mismatch: {path}')
    return raw

def require(condition, message):
    if not condition:
        raise ValueError(message)

def pct(entry, price):
    return 100 * (entry / price - 1)

def write_csv(path, records):
    with path.open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

def main():
    bars, audits, inventory = [], [], []
    for period, (path, dh, th, nc, nt, nw, expected_net) in SOURCES.items():
        rows = json.loads(checked(ROOT / path, dh))
        tp = SOURCE / f'{period}_X4_trades.csv'
        checked(tp, th)
        with tp.open(newline='') as f:
            trades = list(csv.DictReader(f))
        require(len(rows)==nc and len(trades)==nt, f'{period} count mismatch')
        require(sum(float(t['net_pnl_pct'])>0 for t in trades)==nw, f'{period} winner mismatch')
        require(abs(sum(float(t['net_pnl_pct']) for t in trades)-expected_net)<.000002, f'{period} net mismatch')
        times = [datetime.fromisoformat(r['timestamp']) for r in rows]
        require(all(a<b for a,b in zip(times,times[1:])), 'Unsorted candle timestamps')
        ix = {r['timestamp']: i for i,r in enumerate(rows)}
        o,h,l,c = ([float(r[k]) for r in rows] for k in ('open','high','low','close'))
        for t in trades:
            a,z = ix[t['entry_time']],ix[t['exit_time']]
            entry,net = float(t['entry_price']),float(t['net_pnl_pct'])
            require(0<a<=z and abs(o[a]-entry)<1e-6 and times[a].date()==times[z].date(), 'Invalid trade alignment')
            require(abs(float(t['commission_pct'])-FEE)<1e-9, 'Fee mismatch')
            group = 'WIN' if net>0 else 'GIVEBACK' if float(t['best_close_pct'])>FEE else 'NO_FEE_CLOSE'
            key = dict(period=period, signal_time=t['signal_time'], entry_time=t['entry_time'], group=group)
            inventory.append(dict(**key,exit_time=t['exit_time'],exit_reason=t['exit_reason'],net_pct=net,best_close_pct=float(t['best_close_pct'])))
            best, previous_hhhl, first = 0.0, False, {}
            for i in range(a,z):
                require(times[i+1]-times[i]==timedelta(minutes=5), 'Missing held candle')
                gross = pct(entry,c[i]); best=max(best,gross)
                hh,hl,hc = h[i]>h[i-1],l[i]>l[i-1],c[i]>c[i-1]
                flags = dict(Z1=hh,Z2=hh and hl,Z3=hh and hl and hc,Z4=previous_hhhl and hh and hl)
                previous_hhhl = hh and hl
                # First held candle may compare with the completed signal candle.
                # Z4 requires two fully held candles, not a pre-entry comparison alone.
                next_net=pct(entry,o[i+1])-FEE
                bars.append(dict(**key,bar_time=rows[i]['timestamp'],decision_time=rows[i+1]['timestamp'],open=o[i],high=h[i],low=l[i],close=c[i],gross_close_pct=round(gross,6),best_close_pct=round(best,6),profit_seen=best>FEE,higher_high=hh,higher_low=hl,rising_close=hc,**flags,next_open_net_hindsight=round(next_net,6),actual_net_hindsight=net))
                if best>FEE:
                    for rule,flag in flags.items():
                        if flag and rule not in first:
                            first[rule]=(rows[i]['timestamp'],rows[i+1]['timestamp'],next_net)
            require(abs(best-float(t['best_close_pct']))<.000002, f'Best close mismatch: {t["signal_time"]}')
            for rule in RULES:
                hit=first.get(rule)
                hypothetical=round(hit[2],6) if hit else net
                audits.append(dict(**key,rule=rule,triggered=bool(hit),trigger_bar=hit[0] if hit else '',hypothetical_exit_time=hit[1] if hit else t['exit_time'],actual_net_pct=net,hypothetical_net_pct=hypothetical,delta_pp=round(hypothetical-net,6)))
    require(len(inventory)==33 and Counter(t['group'] for t in inventory)=={'WIN':13,'GIVEBACK':6,'NO_FEE_CLOSE':14}, 'Frozen trade groups mismatch')
    report=[]
    for period in ('DISCOVERY','NOVEMBER','COMBINED'):
        for rule in RULES:
            subset=[r for r in audits if r['rule']==rule and (period=='COMBINED' or r['period']==period)]
            for group in ('ALL','WIN','GIVEBACK','NO_FEE_CLOSE'):
                s=[r for r in subset if group=='ALL' or r['group']==group]
                report.append(dict(period=period,rule=rule,group=group,trades=len(s),triggered=sum(r['triggered'] for r in s),improved=sum(r['delta_pp']>0 for r in s),harmed=sum(r['delta_pp']<0 for r in s),winners_harmed=sum(r['group']=='WIN' and r['delta_pp']<0 for r in s),losers_converted=sum(r['actual_net_pct']<0 and r['hypothetical_net_pct']>0 for r in s),actual_net_pct=round(sum(r['actual_net_pct'] for r in s),6),hypothetical_net_pct=round(sum(r['hypothetical_net_pct'] for r in s),6),delta_sum_pp=round(sum(r['delta_pp'] for r in s),6)))
    summary=dict(notes=['Fixed-trade counterfactual, both periods discovery; no new entries or delayed exits simulated.', 'Only fully held candles before original exit bar; decisions at completed close and hypothetical execution at next open, including when that is the original intrabar exit candle.', 'Best completed gross closing profit strictly exceeds fee; Z4 requires consecutive higher-high/higher-low comparisons on two fully held candles.', 'No additional slippage; future outcomes used only for audit labels. No production changes.'],sources={p:dict(candles_sha256=v[1],trades_sha256=v[2]) for p,v in SOURCES.items()},trades=len(inventory),groups=dict(Counter(t['group'] for t in inventory)),completed_held_bars=len(bars),comparison=[r for r in report if r['group']=='ALL'],combined_groups=[r for r in report if r['period']=='COMBINED' and r['group']!='ALL'])
    OUT.mkdir(parents=True,exist_ok=False)
    write_csv(OUT/'trade_inventory.csv',inventory)
    write_csv(OUT/'held_candles.csv',bars)
    write_csv(OUT/'first_warning_audit.csv',audits)
    write_csv(OUT/'variant_comparison.csv',report)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
