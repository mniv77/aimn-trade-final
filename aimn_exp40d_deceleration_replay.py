"""EXP40-D: exploratory deceleration replay, NVDA SHORT, no production writes."""
import csv
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
import aimn_exp40b_causal_replay as b
from aimn_exp40b_causal_replay import base, FEE, STOP, TRAIL

OUT=b.ROOT/'kiss/results/exp40d_deceleration_replay'
B2_HASH='47ab2a8fe9cd84d50ccad567397830ae9ffbd46cd6628f513bbff64ade14f109'

def replay(rows, next_open, gate):
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
            allowed, feature = gate(i)
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


def features(rows):
    c=[float(x['close']) for x in rows]
    t=[datetime.fromisoformat(x['timestamp']) for x in rows]
    def get(i):
        # V17 peak is i-1. Two consecutive six-return windows, sharing only
        # their boundary close; exclude reversal candle and require continuity.
        end=i-1; start=end-12; mid=end-6
        f=dict(earlier_rise=None,recent_rise=None,earlier_eff=None,recent_eff=None,
               rise_delta=None,eff_delta=None,structure_break=None)
        f['structure_break']=float(rows[i]['close']) < min(float(rows[j]['low']) for j in range(max(0,i-3),i))
        if start<0 or t[start].date()!=t[i].date() or any(t[j]-t[j-1]!=timedelta(minutes=5) for j in range(start+1,i+1)):
            return f
        def measure(a,z):
            returns=[(c[j]/c[j-1]-1)*100 for j in range(a+1,z+1)]
            path=sum(abs(v) for v in returns)
            return (c[z]/c[a]-1)*100, sum(returns)/path if path else 0.0
        e,ee=measure(start,mid); r,re=measure(mid,end)
        f.update(earlier_rise=e,recent_rise=r,earlier_eff=ee,recent_eff=re,rise_delta=r-e,eff_delta=re-ee)
        return f
    return get


def main():
    raw=b.DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=b.DATA_HASH: raise ValueError('Candle hash mismatch')
    engine=Path(base.__file__).read_bytes()
    if hashlib.sha1(b'blob '+str(len(engine)).encode()+b'\0'+engine).hexdigest()!=b.ENGINE_BLOB: raise ValueError('Engine mismatch')
    saved=(b.OUTPUT/'B2_trades.csv').read_bytes()
    if hashlib.sha256(saved).hexdigest()!=B2_HASH: raise ValueError('B2 CSV mismatch')
    rows=json.loads(raw); get=features(rows)
    policies={
      'D0_BASELINE':lambda f:True,
      'D1_RISE_DECEL':lambda f:f['rise_delta']<0,
      'D2_EFF_DECEL':lambda f:f['eff_delta']<0,
      'D3_BOTH':lambda f:f['rise_delta']<0 and f['eff_delta']<0,
      'D4_STRUCTURE':lambda f:f['structure_break'],
    }
    results={}; report={'notes':['Exploratory discovery only; all months previously examined.', 'Missing 12-return history passes D1-D3; reported separately.', 'Structure means signal close below previous three lows, not confirmed major reversal.', 'B2 overnight and stop assumptions unchanged; no added slippage.', 'Splits assigned by signal date; continuous replay, not independent validation.'], 'variants':{}}
    baseline,be,bo=b.replay(rows,True)
    saved_rows=list(csv.DictReader(saved.decode().splitlines()))
    if len(baseline)!=len(saved_rows) or any({k:str(v) for k,v in x.items()}!=y for x,y in zip(baseline,saved_rows)): raise ValueError('Original B2 trade parity failed')
    for name,policy in policies.items():
        def gate(i):
            f=get(i)
            return (True if name in ('D1_RISE_DECEL','D2_EFF_DECEL','D3_BOTH') and f['rise_delta'] is None else bool(policy(f))), f
        t,e,o,a=replay(rows,True,gate)
        if name=='D0_BASELINE' and (t,e,o)!=(baseline,be,bo): raise ValueError('D0 replay parity failed')
        if len(a)!=135: raise ValueError('Candidate count mismatch')
        results[name]=(t,a)
        splits={label:b.summary([x for x in t if (x['signal_time'][5:7]=='08')==aug]) for label,aug in [('JUN_JUL',False),('AUG',True)]}
        report['variants'][name]={**b.summary(t),'events':e,'open_position':o,'missing_history':sum(x['rise_delta'] is None for x in a),'splits':splits}
    original={x['signal_time']:x for x in baseline}
    for name,(t,a) in results.items():
        current={x['signal_time']:x for x in t}
        removed=[x for k,x in original.items() if k not in current]
        added=[x for k,x in current.items() if k not in original]
        report['variants'][name].update(removed=b.summary(removed),added=b.summary(added))
    OUT.mkdir(parents=True,exist_ok=False)
    for name,(t,a) in results.items():
        for suffix,records in [('trades',t),('candidates',a)]:
            with (OUT/f'{name}_{suffix}.csv').open('x',newline='') as f:
                if records:
                    w=csv.DictWriter(f,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
