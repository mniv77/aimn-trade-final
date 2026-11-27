#!/usr/bin/env python3
"""EXP40-U: independent entry-detector comparison; no orders or production edits."""
import csv, json, hashlib
from pathlib import Path
from collections import Counter
from bisect import bisect_right
import aimn_exp40k_structural_reversal_replay as k
import aimn_exp40l_independent_validation as v
import aimn_exp40m_supertrend_forensics as m
import aimn_exp40o_transition_recognition_forensics as o
import aimn_exp40t_opening_selectivity as t
from aimn_exp40b_causal_replay import base, FEE, STOP, TRAIL
b=k.b
OUT=b.ROOT/'kiss/results/exp40u_combined_causal_replay'
VARIANTS=('U0','U1','U2','U3','U4')

def replay(rows, next_open, gate, cancel=False, flatten=False, cutoff=False, warning=None, entry_detector=None):
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
                # Existing exits retain priority; only fully held completed bars
                # can activate a warning. Execution remains at the next open.
                if warning is not None and (entry/pos['best_close']-1)*100 > FEE:
                    span=h[i]-l[i]
                    loc=(c[i]-l[i])/span if span else 0.5
                    body=(c[i]-o[i])/span if span else 0.0
                    hh=h[i]>h[i-1]; hl=l[i]>l[i-1]; hc=c[i]>c[i-1]
                    flags=dict(higher_high=hh, higher_high_low=hh and hl,
                        bullish_upper_close=hc and body>=0.5 and loc>=0.75,
                        higher_high_bullish_close=hh and hc and c[i]>o[i],
                        higher_close_break_prior_high=c[i]>h[i-1])
                    if flags[warning]:
                        events['structural_warning'] += 1
                        if reason is None:
                            reason='STRUCTURAL_'+warning.upper()
                if reason:
                    if next_open:
                        pending_exit=reason
                    else:
                        finish(i,c[i],reason,'CLOSE')
        signal = (base.is_early_v_short(h,o,c,states,i) is not None
                  if entry_detector is None else entry_detector(i))
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


def features(rows, start):
    # Each decision uses completed bars only. ST series uses causal recurrence.
    s5=m.snapshots(rows,5); s30=m.snapshots(m.aggregate(rows),30)
    avail=[s['available_time'] for s in s30]; last={}; result={}; total=0
    def efficiency(i,n):
        if not o.same_session(rows,i-n,i): return None
        c=[r['close'] for r in rows[i-n:i+1]]
        steps=[z-a for a,z in zip(c,c[1:])]; den=sum(abs(x) for x in steps)
        return -sum(steps)/den if den else 0.0
    for i,r in enumerate(rows):
        stamp=r['timestamp']
        if stamp<start or 'TWO_STEP' not in o.warning_rules(rows,i,'SHORT'): continue
        total+=1
        j=bisect_right(avail,s5[i]['available_time'])-1
        if s5[i]['trend']!='LONG' or j<0 or s30[j]['trend']!='SHORT': continue
        day=stamp[:10]; prev=last.get(day); reset=t.recovery(rows,prev,i)
        e6,e12=efficiency(i,6),efficiency(i,12)
        missing=e6 is None or e12 is None
        q4='MISSING' if missing else 'PASS' if e6>e12>0 else 'FAIL'
        result[i]=dict(st5='LONG',st30='SHORT',major_available=s30[j]['available_time'],
            e6=e6,e12=e12,Q4=q4,first=prev is None,recovery=reset,
            T1='PASS' if prev is None else 'FAIL',T2='PASS' if prev is None or reset else 'FAIL')
        last[day]=i
    return result,total

def check_features(rows,period,feat,total):
    qpath=b.ROOT/'kiss/results/exp40q_combined_trajectory_forensics/warning_decisions.csv'
    tpath=b.ROOT/'kiss/results/exp40t_opening_selectivity/opening_decisions.csv'
    q=m.read_csv(qpath); opening=m.read_csv(tpath)
    q=[r for r in q if r['period']==period]
    assert len(q)==total
    old={r['signal_time']:r for r in q if r['st_direction']=='LONG' and r['major_st']=='SHORT'}
    assert set(old)=={rows[i]['timestamp'] for i in feat}
    for i,x in feat.items():
        r=old[rows[i]['timestamp']]
        assert x['Q4']==r['Q4'] and x['major_available']==r['major_context_time']
        for key,col in [('e6','prior6_efficiency'),('e12','prior12_efficiency')]:
            val=None if r[col]=='' else float(r[col]); assert x[key]==val
    lookup={rows[i]['timestamp']:x for i,x in feat.items()}
    for r in opening:
        if r['period']!=period: continue
        x=lookup[r['signal_time']]
        assert x['Q4']=='MISSING' and x['T1']==r['T1'] and x['T2']==r['T2']
    return len(old)

def gate_for(feat,name):
    def gate(i):
        x=feat[i]; q=x['Q4']; allow=(name=='U1' or q=='PASS' or
            (q=='MISSING' and name in ('U3','U4') and x['T1' if name=='U3' else 'T2']=='PASS'))
        return allow,dict(x)
    return gate

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    for name,digest in v.HASHES.items(): v.checked(b.ROOT/name,digest)
    v.checked(b.ROOT/'kiss/kiss_exp53_supertrend.py',o.ST_HASH)
    engine=Path(base.__file__).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(engine)).encode()+b'\0'+engine).hexdigest()==b.ENGINE_BLOB
    disc=json.loads(v.checked(b.DATA,b.DATA_HASH))
    warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec')
    test=m.load(m.TEST,'eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d')
    v.validate_rows(disc,4680,'2026-06-04 09:30:00','2026-08-28 15:55:00')
    v.validate_rows(warm,780,'2026-11-02 09:30:00','2026-11-13 15:55:00')
    v.validate_rows(test,624,m.START,'2026-11-25 15:55:00')
    report=dict(notes=['Discovery replay only, no orders or production changes.',
        'Independent TWO_STEP detector; decision features recomputed from candles, no outcome labels used.',
        'Q4 and T1/T2 parity verified against prior audits; censored research warnings are not excluded from replay.',
        'U0 exact frozen trade/candidate parity; K3 stops, exits, fees, session cutoff and flatten retained.',
        'Replay begins at original engine warm-up index; no warm-up entries. No same-bar reentry.',
        'Trade sums are not portfolio returns; no additional slippage. Additional costs are sensitivity only.'],periods={})
    results={}
    for period,rows,start,expected,source in [
        ('DISCOVERY',disc,disc[0]['timestamp'],(32,-.199296),k.OUT/'K3_BULLISH_UPPER_CLOSE'),
        ('NOVEMBER',warm+test,m.START,(3,-1.673977),v.OUT/'K3')]:
        feat,total=features(rows,start); n=check_features(rows,period,feat,total)
        assert (total,n)==((546,93) if period=='DISCOVERY' else (82,19))
        group={}; report['periods'][period]=dict(warnings=total,focus=n,variants=group)
        for name in VARIANTS:
            if name=='U0':
                gate=v.gate_for(rows,None if period=='DISCOVERY' else start)
                args=(rows,True,gate,True,True,True)
                trades,events,op,audit=replay(*args,warning='bullish_upper_close')
                assert (trades,events,op,audit)==k.replay(*args,warning='bullish_upper_close')
                audit=[r for r in audit if r['signal_time']>=start]
                k.e.verify_csv(trades,Path(str(source)+'_trades.csv'))
                k.e.verify_csv(audit,Path(str(source)+'_candidates.csv'))
                assert (len(trades),b.summary(trades)['net_sum_pct'])==expected
            else:
                trades,events,op,audit=replay(rows,True,gate_for(feat,name),True,True,True,
                    warning='bullish_upper_close',entry_detector=lambda i:i in feat)
            assert op is None and all(not r['overnight'] and r['signal_time']>=start and r['entry_time'][:10]==r['signal_time'][:10] for r in trades)
            assert all(r['signal_time'][11:16]<'15:30' and r['exit_time'][11:16]<='15:55' for r in trades)
            group[name]=dict(**b.summary(trades),candidates=len(audit),events=events,
                extra_cost_net_pct={str(cost):round(sum(r['net_pnl_pct']-cost for r in trades),6) for cost in (.02,.05,.10)},
                splits={label:b.summary([r for r in trades if r['signal_time'][5:7] in months]) for label,months in ([('JUN_JUL',('06','07')),('AUG',('08',))] if period=='DISCOVERY' else [('NOVEMBER',('11',))])})
            results[period,name]=(trades,audit)
    OUT.mkdir(parents=True,exist_ok=False)
    for (period,name),(trades,audit) in results.items():
        v.write_csv(OUT/f'{period}_{name}_trades.csv',trades)
        v.write_csv(OUT/f'{period}_{name}_candidates.csv',audit)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__': main()
