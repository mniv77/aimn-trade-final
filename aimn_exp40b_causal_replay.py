"""EXP40-B: isolated NVDA SHORT V17 execution audit. No orders or production writes."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from engine import kiss_backtest as base

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'kiss/visual_research/aimn_nvda_candles.json'
SAVED = ROOT / 'instance/kiss_saved_results'
OUTPUT = ROOT / 'kiss/results/exp40b_causal_replay'
DATA_HASH = '020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50'
ENGINE_BLOB = 'c2dd7b7ff262b467ca0c3012bfb6e10c812ef70f'
FEE = 0.2
TRAIL = 0.005
STOP = 0.015
FIELDS = ('entry_time','exit_time','entry_price','exit_price','exit_reason',
          'net_pnl_pct','max_favorable_pct','max_adverse_pct')


def replay(rows, next_open):
    c, o, h, l = ([float(r[k]) for r in rows] for k in ('close','open','high','low'))
    ts = [r['timestamp'] for r in rows]
    states = [base.get_market_state(c, i) for i in range(len(rows))]
    rsi = base.rsi_wilder(c)
    trades, events = [], Counter()
    pos = pending_entry = pending_exit = None

    def enter(i, signal, price):
        return dict(entry_i=i, signal_i=signal, entry=price, trough=price,
                    best_close=price, pending_flat=False, fav=0., adv=0.)

    def finish(i, price, reason, phase):
        nonlocal pos, pending_exit
        entry = pos['entry']
        gross = (entry / price - 1) * 100
        # On an intrabar exit candle, the full range is not observable while held.
        # Only opening and fill prices are credited on that candle.
        trades.append(dict(signal_time=ts[pos['signal_i']], entry_time=ts[pos['entry_i']],
            exit_time=ts[i], entry_price=round(entry,8), exit_price=round(price,8),
            exit_reason=reason, exit_phase=phase, pnl_pct=round(gross,6),
            commission_pct=FEE, net_pnl_pct=round(round(gross,6)-FEE,6),
            max_favorable_pct=round(pos['fav'],6), max_adverse_pct=round(pos['adv'],6),
            best_close_pct=round((entry/pos['best_close']-1)*100,6),
            overnight=ts[pos['entry_i']][:10]!=ts[i][:10]))
        pos = pending_exit = None

    def observe_price(price):
        v = (pos['entry']/price-1)*100
        pos['fav'] = max(pos['fav'],v)
        pos['adv'] = min(pos['adv'],v)

    for i in range(base.TREND_WINDOW+1,len(rows)):
        # Preserve original overnight policy; no additional session filter here.
        occupied_at_start = pos is not None
        if next_open and pending_exit is not None:
            observe_price(o[i])
            finish(i,o[i],pending_exit,'OPEN')
        if next_open and pending_entry is not None:
            assert pos is None
            pos = enter(i,pending_entry,o[i])
            pending_entry = None
            occupied_at_start = True
        if pos is not None:
            entry = pos['entry']
            fixed = entry*(1+STOP)
            trail = pos['trough']*(1+TRAIL)
            # Both orders are assumed resting before the bar. First reachable
            # level wins; opening gaps use the open. No current-bar low ratchet.
            level, reason = (fixed,'STOP_LOSS') if fixed<=trail else (trail,'TRAILING_REVERSE')
            observe_price(o[i])
            if h[i]>=level:
                fill=max(o[i],level)
                observe_price(fill)
                finish(i,fill,reason,'INTRABAR')
            else:
                observe_price(l[i]); observe_price(h[i])
                pos['trough']=min(pos['trough'],l[i])
                pos['best_close']=min(pos['best_close'],c[i])
                if states[i-1]=='SHORT' and states[i]=='FLAT':
                    pos['pending_flat']=True
                turn = ((states[i-1]=='SHORT' and states[i]=='LONG') or
                        (pos['pending_flat'] and states[i-1]=='FLAT' and states[i]=='LONG'))
                reason = ('V_PROFIT' if base.is_v_long(c,i) and (entry/c[i]-1)*100>FEE
                          else 'TREND_CHANGE' if turn
                          else 'RSI_EMERGENCY' if rsi[i] is not None and rsi[i]>80 else None)
                if reason:
                    if next_open:
                        pending_exit=reason
                    else:
                        finish(i,c[i],reason,'CLOSE')
        signal = base.is_early_v_short(h,o,c,states,i) is not None
        if signal:
            events['signals']+=1
            # Preserve baseline policy: no re-entry on a bar already occupied.
            if occupied_at_start or pos is not None:
                events['blocked_in_position']+=1
            elif next_open:
                if i+1<len(rows): pending_entry=i
                else: events['unfilled_final_signal']+=1
            else:
                pos=enter(i,i,c[i])
    # B1 matches original forced end-of-data mark; B2 reports it separately
    # rather than claiming a next-open fill that is not available.
    open_position=None
    if pos is not None:
        if not next_open:
            finish(len(rows)-1,c[-1],'END_OF_DATA','CLOSE_MARK')
        else:
            open_position=dict(entry_time=ts[pos['entry_i']],entry_price=pos['entry'],
                last_time=ts[-1],last_close=c[-1],pending_exit=pending_exit,
                marked_net_pct=(pos['entry']/c[-1]-1)*100-FEE)
    return trades,dict(events),open_position


def summary(t):
    return dict(trades=len(t),winners=sum(x['net_pnl_pct']>0 for x in t),
        losers=sum(x['net_pnl_pct']<=0 for x in t),
        net_sum_pct=round(sum(x['net_pnl_pct'] for x in t),6),
        gross_sum_pct=round(sum(x['pnl_pct'] for x in t),6),
        exits=dict(Counter(x['exit_reason'] for x in t)))


def main():
    raw=DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DATA_HASH: raise ValueError('Frozen candle hash mismatch')
    engine_bytes=Path(base.__file__).read_bytes()
    blob=hashlib.sha1(b'blob '+str(len(engine_bytes)).encode()+b'\0'+engine_bytes).hexdigest()
    if blob!=ENGINE_BLOB: raise ValueError('Frozen engine blob mismatch; investigate before replay')
    rows=json.loads(raw)
    assert len(rows)==4680
    assert all(a['timestamp']<b['timestamp'] for a,b in zip(rows,rows[1:]))
    for r in rows:
        o,h,l,c=(float(r[k]) for k in ('open','high','low','close'))
        assert all(math.isfinite(v) and v>0 for v in (o,h,l,c)) and l<=min(o,c)<=max(o,c)<=h
    saved=[]
    expected=dict(entry_mode='V17',rsi_rescue_long=20.,rsi_rescue_short=80.,trailing_minus_pct=.5,commission_pct_one_side=.1)
    for f in SAVED.glob('*.json'):
        d=json.loads(f.read_text())
        if (d.get('symbol'),d.get('direction'),str(d.get('broker_id')),d.get('timeframe'),d.get('parameters'))==('NVDA','SHORT','2','5m',expected): saved.append(d['trades'])
    assert len(saved)==1,'Expected exactly one matching saved baseline'
    b0=base.run_kiss_backtest(rows,'NVDA','SHORT','5m',20,80,.5,.1,'V17')['trades']
    assert len(b0)==len(saved[0])==124 and all(all(a[k]==b[k] for k in FIELDS) for a,b in zip(b0,saved[0])),'Baseline parity failed'
    results={'B0':b0}; report={'data_sha256':DATA_HASH,'engine_git_blob':blob,'baseline_parity':124,'variants':{'B0':summary(b0)}}
    for name,next_open in [('B1',False),('B2',True)]:
        t,events,open_pos=replay(rows,next_open); results[name]=t
        report['variants'][name]={**summary(t),'events':events,'open_position':open_pos}
    # Never overwrite prior research output.
    OUTPUT.mkdir(parents=True,exist_ok=False)
    for name,t in results.items():
        fields=list(dict.fromkeys(k for row in t for k in row))
        with (OUTPUT/(name+'_trades.csv')).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(t)
    (OUTPUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
