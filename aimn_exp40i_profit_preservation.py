"""EXP40-I: prospective profit preservation, independent discovery replay."""
import csv, json, hashlib
from pathlib import Path
from collections import Counter
import aimn_exp40g_prior_session_replay as g
from aimn_exp40b_causal_replay import base, FEE, STOP, TRAIL
b,d,e = g.b,g.d,g.e
OUT=b.ROOT/'kiss/results/exp40i_profit_preservation'
HOUT=b.ROOT/'kiss/results/exp40h_session_protection'

def replay(rows, next_open, gate, cancel=False, flatten=False, cutoff=False, protection=0):
    c, o, h, l = ([float(r[k]) for r in rows] for k in ('close','open','high','low'))
    ts = [r['timestamp'] for r in rows]
    states = [base.get_market_state(c, i) for i in range(len(rows))]
    rsi = base.rsi_wilder(c)
    trades, events, audit = [], Counter(), []
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
        clock = ts[i][11:16]
        if pending_entry is not None and cancel and ts[pending_entry][:10] != ts[i][:10]:
            pending_entry = None
            events['stale_entry_cancelled'] += 1
        if flatten and clock == '15:55' and pos is not None and pending_exit is None:
            pending_exit = 'SESSION_FLATTEN'

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
            # Only completed, survived candles can arm profit protection.
            best_gross = (entry / pos['best_close'] - 1) * 100
            if protection and best_gross > FEE:
                if protection == 1:
                    target = entry / (1 + FEE / 100)
                    label = 'FEE_BREAK_EVEN'
                elif protection == 2:
                    target = entry / (1 + (FEE + 0.5 * (best_gross - FEE)) / 100)
                    label = 'LOCK_HALF_NET'
                elif protection == 3:
                    target = pos['trough'] * (1 + TRAIL / 2)
                    label = 'ADAPTIVE_TRAIL'
                else:
                    raise ValueError('Unknown protection policy')
                # A stop already crossed at the prior close cannot be placed
                # retrospectively. Schedule exit at this open instead.
                if target < level:
                    level, reason = target, label
                    events['protection_active_bars'] += 1
                    if c[i-1] >= level:
                        observe_price(o[i])
                        finish(i,o[i],reason,'OPEN')
            if pos is not None:
                observe_price(o[i])
            if pos is not None and h[i]>=level:
                fill=max(o[i],level)
                observe_price(fill)
                finish(i,fill,reason,'INTRABAR')
            elif pos is not None:
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
            allowed, feature = gate(i)
            if allowed and ((flatten and clock >= '15:50') or (cutoff and clock >= '15:30')):
                allowed = False
                events['time_gate'] += 1
            record = dict(signal_time=ts[i], **feature, allowed=allowed)
            audit.append(record)
            # Preserve baseline policy: no re-entry on a bar already occupied.
            if occupied_at_start or pos is not None:
                events['blocked_in_position']+=1
                record['status']='BLOCKED_POSITION'
            elif not allowed:
                events['rejected']+=1
                record['status']='REJECTED'
            elif next_open:
                record['status']='SCHEDULED' if i+1<len(rows) else 'UNFILLED_FINAL'
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
    return trades,dict(events),open_position,audit


def main():
    raw=b.DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=b.DATA_HASH: raise ValueError('Data hash mismatch')
    engine=Path(base.__file__).read_bytes()
    if hashlib.sha1(b'blob '+str(len(engine)).encode()+b'\0'+engine).hexdigest()!=b.ENGINE_BLOB: raise ValueError('Engine mismatch')
    rows=json.loads(raw)
    # Fixed regular session schedule only; refuse incomplete or shortened sessions.
    from datetime import datetime,timedelta
    sessions={}
    for row in rows:
        t=datetime.fromisoformat(row['timestamp']); sessions.setdefault(t.date(),[]).append(t)
    for day,times in sessions.items():
        if len(times)!=78 or times[0].strftime('%H:%M')!='09:30' or times[-1].strftime('%H:%M')!='15:55' or any(z-a!=timedelta(minutes=5) for a,z in zip(times,times[1:])):
            raise ValueError(f'Unsupported session: {day}')
    full,short,prior=d.features(rows),e.short_features(rows),g.prior_features(rows)
    def gate(i):
        x={**full(i),**short(i)}
        allowed,policy=e.decision('E1_FULL_ONLY',x)
        kind='FULL' if x['rise_delta'] is not None else 'SHORT_ONLY' if x['short_rise_delta'] is not None else 'EARLIEST'
        x.update(history_type=kind,policy_used=policy)
        pv=prior(i)
        if kind=='EARLIEST':
            allowed=g.opening_decision('G1_PRIOR_30M',pv); x['policy_used']='G1_PRIOR_30M'
        x.update(**pv,opening_policy='G1_PRIOR_30M' if kind=='EARLIEST' else 'NOT_APPLICABLE')
        return allowed,x
    policies={'I0_H4':0,'I1_BREAK_EVEN':1,'I2_HALF_NET':2,'I3_ADAPTIVE_TRAIL':3}
    results={}
    report={'notes':['Discovery only; no production changes or independent validation.', 'H4 entry and session policy unchanged.', 'Protection activates after a completed held candle shows gross profit strictly greater than 0.2%.', 'I1 locks modeled fees; I2 locks half the best closing net profit; I3 halves trailing distance after activation.', 'Stops apply prospectively; gaps fill at open, so profit is not guaranteed.', 'If a newly tightened stop is already crossed at prior close, exit at next open.', 'Existing pending exits and session flatten retain precedence.', 'No additional slippage; net sums are not compounded portfolio returns.'], 'variants':{}}
    for name,mode in policies.items():
        t,ev,op,a=replay(rows,True,gate,True,True,True,mode)
        if mode==0:
            e.verify_csv(t,HOUT/'H4_CUTOFF_trades.csv')
            e.verify_csv(a,HOUT/'H4_CUTOFF_candidates.csv')
            if len(t)!=32 or len(a)!=135 or round(sum(x['net_pnl_pct'] for x in t),6)!=-0.672133:
                raise ValueError('H4 parity failure')
            report['baseline_parity']={'trades':len(t),'candidates':len(a)}
        if op is not None or any(x['overnight'] or x['signal_time'][:10]!=x['entry_time'][:10] for x in t):
            raise ValueError('Session protection failure')
        results[name]=(t,a)
        report['variants'][name]={**b.summary(t),'events':ev,'open_position':op,'splits':{label:b.summary([x for x in t if (x['signal_time'][5:7]=='08')==aug]) for label,aug in [('JUN_JUL',False),('AUG',True)]}}
    original={x['signal_time']:x for x in results['I0_H4'][0]}
    for name,(t,a) in results.items():
        current={x['signal_time']:x for x in t}
        shared=[dict(signal_time=k,old_net=original[k]['net_pnl_pct'],new_net=x['net_pnl_pct'],delta=round(x['net_pnl_pct']-original[k]['net_pnl_pct'],6),old_exit=original[k]['exit_time'],new_exit=x['exit_time'],new_reason=x['exit_reason']) for k,x in current.items() if k in original and x!=original[k]]
        report['variants'][name].update(removed=b.summary([x for k,x in original.items() if k not in current]),added=b.summary([x for k,x in current.items() if k not in original]),changed_shared=shared,original_winners_harmed=sum(original[k]['net_pnl_pct']>0 and x['net_pnl_pct']<original[k]['net_pnl_pct'] for k,x in current.items() if k in original),original_losers_rescued=sum(original[k]['net_pnl_pct']<=0 and x['net_pnl_pct']>0 for k,x in current.items() if k in original))
    OUT.mkdir(parents=True,exist_ok=False)
    for name,(t,a) in results.items():
        for suffix,records in [('trades',t),('candidates',a)]:
            with (OUT/f'{name}_{suffix}.csv').open('x',newline='') as fp:
                if records:
                    w=csv.DictWriter(fp,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
