#!/usr/bin/env python3
"""EXP40-J: read-only H4 trajectory audit; not a trading replay."""
import csv
import json
import hashlib
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta

DATA = Path('kiss/visual_research/aimn_nvda_candles.json')
TRADES = Path('kiss/results/exp40h_session_protection/H4_CUTOFF_trades.csv')
OUT = Path('kiss/results/exp40j_reverse_transition_forensics')
FEE = 0.2

def pct(entry, price):
    return 100 * (entry / price - 1)

def write_csv(path, rows):
    with path.open('x', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def main():
    raw = DATA.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50', 'Candle hash mismatch'
    rows = json.loads(raw)
    with TRADES.open(newline='') as f:
        trades = list(csv.DictReader(f))
    assert len(rows) == 4680 and len(trades) == 32
    assert sum(float(t['net_pnl_pct']) > 0 for t in trades) == 17
    assert abs(sum(float(t['net_pnl_pct']) for t in trades) + .672133) < .000002
    times = [datetime.fromisoformat(r['timestamp']) for r in rows]
    assert all(a < b for a,b in zip(times,times[1:]))
    ix = {r['timestamp']:i for i,r in enumerate(rows)}
    o,h,l,c = ([float(r[k]) for r in rows] for k in ('open','high','low','close'))
    bars, audits = [], []
    rules = ['higher_high','higher_high_low','bullish_upper_close','higher_high_bullish_close','higher_close_break_prior_high']
    for t in trades:
        a,z = ix[t['entry_time']],ix[t['exit_time']]
        entry,net = float(t['entry_price']),float(t['net_pnl_pct'])
        assert a <= z and abs(o[a]-entry)<1e-6 and times[a].date()==times[z].date()
        group = 'WINNER' if net>0 else 'PROFIT_GIVEN_BACK' if float(t['best_close_pct'])>FEE else 'NO_CLOSE_ABOVE_FEES'
        best = 0.0
        first = {}
        for i in range(a,z):
            # Exclude exit candle: its full OHLC was not observed while held.
            assert i>0 and times[i+1]-times[i]==timedelta(minutes=5)
            current = pct(entry,c[i]); best=max(best,current)
            span=h[i]-l[i]
            loc=(c[i]-l[i])/span if span else 0.5
            body=(c[i]-o[i])/span if span else 0.0
            hh=h[i]>h[i-1]; hl=l[i]>l[i-1]; hc=c[i]>c[i-1]
            flags=dict(higher_high=hh,higher_high_low=hh and hl,
                       bullish_upper_close=hc and body>=0.5 and loc>=0.75,
                       higher_high_bullish_close=hh and hc and c[i]>o[i],
                       higher_close_break_prior_high=c[i]>h[i-1])
            start=max(a,i-2)
            # Count only comparisons with preceding completed bars, including signal bar.
            lower_highs=sum(h[j]<h[j-1] for j in range(start,i+1))
            lower_lows=sum(l[j]<l[j-1] for j in range(start,i+1))
            next_net=pct(entry,o[i+1])-FEE
            rec=dict(signal_time=t['signal_time'],entry_time=t['entry_time'],bar_time=rows[i]['timestamp'],decision_time=times[i+1].isoformat(sep=' '),group=group,open=o[i],high=h[i],low=l[i],close=c[i],gross_close_pct=round(current,6),best_close_so_far_pct=round(best,6),profit_seen=best>FEE,higher_low=hl,higher_close=hc,close_location=round(loc,6),signed_body_fraction=round(body,6),lower_high_count_last_up_to_3=lower_highs,lower_low_count_last_up_to_3=lower_lows,comparison_count=i-start+1,**flags,next_open_net_hindsight_pct=round(next_net,6),actual_net_hindsight_pct=net)
            bars.append(rec)
            if best>FEE:
                for rule in rules:
                    if flags[rule] and rule not in first:
                        first[rule]=(rows[i]['timestamp'],rows[i+1]['timestamp'],next_net)
        assert abs(best-float(t['best_close_pct']))<.000002, ('best close mismatch',t['signal_time'],best,t['best_close_pct'])
        for rule in rules:
            hit=first.get(rule)
            audits.append(dict(signal_time=t['signal_time'],group=group,rule=rule,trigger_bar=hit[0] if hit else '',hypothetical_exit_time=hit[1] if hit else '',actual_net_pct=net,hypothetical_net_pct=round(hit[2],6) if hit else net,delta_pp=round(hit[2]-net,6) if hit else 0,triggered=bool(hit)))
    report={}
    for rule in rules:
        subset=[r for r in audits if r['rule']==rule]
        report[rule]={}
        for group in ['ALL','WINNER','PROFIT_GIVEN_BACK','NO_CLOSE_ABOVE_FEES']:
            s=[r for r in subset if group=='ALL' or r['group']==group]
            report[rule][group]=dict(trades=len(s),triggered=sum(r['triggered'] for r in s),improved=sum(r['delta_pp']>0 for r in s),harmed=sum(r['delta_pp']<0 for r in s),delta_sum_pp=round(sum(r['delta_pp'] for r in s),6))
    summary=dict(notes=['Discovery-only fixed-trade forensic comparison, not a full replay; ignores newly available entries after hypothetical exits.','Only fully held candles are used for decisions. Next-open outcomes and original trade groups are retrospective audit labels.','Warning rules evaluated after best completed closing gross profit exceeds modeled fee. No extra slippage.','Bar timestamps are start labels.'],baseline_trades=len(trades),baseline_net_sum_pct=round(sum(float(t['net_pnl_pct']) for t in trades),6),groups=dict(Counter(r['group'] for r in audits if r['rule']==rules[0])),completed_held_bars=len(bars),source_sha256=dict(candles=hashlib.sha256(raw).hexdigest(),trades=hashlib.sha256(TRADES.read_bytes()).hexdigest()),rules=report)
    OUT.mkdir(parents=True,exist_ok=False)
    write_csv(OUT/'held_candles.csv',bars)
    write_csv(OUT/'first_warning_audit.csv',audits)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
