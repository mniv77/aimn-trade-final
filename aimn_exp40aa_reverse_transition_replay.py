#!/usr/bin/env python3
"""EXP40-AA: supplemental reverse-transition replay; discovery only."""
import json, hashlib
from pathlib import Path
from collections import Counter
import aimn_exp40u_combined_causal_replay as u
import aimn_exp40x_causal_invalidation_replay as x
from aimn_exp40u_combined_causal_replay import b, k, m, v, base, FEE, STOP, TRAIL
OUT=b.ROOT/'kiss/results/exp40aa_reverse_transition_replay'
POLICIES={'AA0':('U2','W3',None,'X2'),'AA1':('U2','W3','higher_high','X2'),'AA2':('U2','W3','higher_high_low','X2'),'AA3':('U4','W1',None,'X4'),'AA4':('U4','W1','higher_high','X4'),'AA5':('U4','W1','higher_high_low','X4')}

def replay(rows, next_open, gate, cancel=False, flatten=False, cutoff=False, warning=None, entry_detector=None, invalidation=None, supplemental=None):
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
                    if reason is None and supplemental is not None and flags[supplemental]:
                        reason='SUPPLEMENTAL_'+supplemental.upper()
                        events['supplemental_warning'] += 1
                # Only the first fully held candle; existing exits retain priority.
                if reason is None and invalidation is not None and i == pos['entry_i']:
                    if invalidation(i, pos['signal_i']):
                        reason = 'FIRST_CANDLE_INVALIDATION'
                        events['first_candle_invalidation'] += 1
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


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    for name,digest in v.HASHES.items(): v.checked(b.ROOT/name,digest)
    v.checked(b.ROOT/'kiss/kiss_exp53_supertrend.py',u.o.ST_HASH)
    engine=Path(base.__file__).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(engine)).encode()+b'\0'+engine).hexdigest()==b.ENGINE_BLOB
    disc=m.load(b.DATA,b.DATA_HASH)
    warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec')
    test=m.load(m.TEST,'eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d')
    v.validate_rows(disc,4680,'2026-06-04 09:30:00','2026-08-28 15:55:00')
    v.validate_rows(warm,780,'2026-11-02 09:30:00','2026-11-13 15:55:00')
    v.validate_rows(test,624,m.START,'2026-11-25 15:55:00')
    report=dict(notes=['Both periods discovery; no orders or production changes.', 'K3 and all existing exits retained; supplemental warning only after best completed gross close exceeds fee.', 'Exact X2/X4 trade and candidate parity required. Earlier exits may free subsequent entries.', 'Trade sums are not portfolio returns. Extra costs are sensitivity only.'],periods={},combined={},baseline_hashes={})
    results={}
    expected={('DISCOVERY','X2'):(16,-1.093947),('NOVEMBER','X2'):(2,.854282),('DISCOVERY','X4'):(28,-.947155),('NOVEMBER','X4'):(5,.722305)}
    hashes={'DISCOVERY':'48cd41e03afca3a82689cdb67bbecc975e7088d26d68f727da93f14c8bf8bc4d','NOVEMBER':'08f2dc41f2580374689e142c1e5178c78c548ca6343701f9f599ba4e6a2cc3bb'}
    for period,rows,start in [('DISCOVERY',disc,disc[0]['timestamp']),('NOVEMBER',warm+test,m.START)]:
        feat,total=u.features(rows,start); n=u.check_features(rows,period,feat,total)
        assert (total,n)==((546,93) if period=='DISCOVERY' else (82,19))
        s5=m.snapshots(rows,5)
        group=report['periods'][period]={}
        for name,(entry,policy,extra,refname) in POLICIES.items():
            args=(rows,True,u.gate_for(feat,entry),True,True,True)
            kw=dict(warning='bullish_upper_close',entry_detector=lambda i:i in feat,invalidation=x.invalidator(rows,s5,policy))
            t,ev,op,a=replay(*args,**kw,supplemental=extra)
            assert op is None and all(not r['overnight'] and r['signal_time']>=start and r['entry_time'][:10]==r['signal_time'][:10] and r['signal_time'][11:16]<'15:30' and r['exit_time'][11:16]<='15:55' for r in t)
            if extra is None:
                assert (t,ev,op,a)==x.replay(*args,**kw)
                for suffix,data in [('trades',t),('candidates',a)]:
                    path=x.OUT/f'{period}_{refname}_{suffix}.csv'
                    digest=hashlib.sha256(path.read_bytes()).hexdigest()
                    if refname=='X4' and suffix=='trades': assert digest==hashes[period]
                    k.e.verify_csv(data,path)
                    report['baseline_hashes'][path.name]=digest
                assert (len(t),b.summary(t)['net_sum_pct'])==expected[period,refname]
            results[period,name]=(t,a)
            ref=results[period,'AA0' if refname=='X2' else 'AA3'][0]
            original={r['signal_time']:r for r in ref}; current={r['signal_time']:r for r in t}
            group[name]=dict(**b.summary(t),events=ev,net_delta_vs_baseline=round(sum(r['net_pnl_pct'] for r in t)-sum(r['net_pnl_pct'] for r in ref),6),winners_harmed=sum(r['net_pnl_pct']>0 and (key not in current or current[key]['net_pnl_pct']<r['net_pnl_pct']) for key,r in original.items()),losers_converted=sum(r['net_pnl_pct']<0 and key in current and current[key]['net_pnl_pct']>0 for key,r in original.items()),added=len(current.keys()-original.keys()),removed=len(original.keys()-current.keys()),splits={label:b.summary([r for r in t if r['signal_time'][5:7] in months]) for label,months in ([('JUN_JUL',('06','07')),('AUG',('08',))] if period=='DISCOVERY' else [('NOVEMBER',('11',))])})
    for name in POLICIES:
        t=[r for period in ('DISCOVERY','NOVEMBER') for r in results[period,name][0]]
        report['combined'][name]=dict(**b.summary(t),extra_cost_net_pct={str(cost):round(sum(r['net_pnl_pct']-cost for r in t),6) for cost in (.02,.05,.10)})
    OUT.mkdir(parents=True,exist_ok=False)
    for (period,name),(t,a) in results.items():
        v.write_csv(OUT/f'{period}_{name}_trades.csv',t)
        v.write_csv(OUT/f'{period}_{name}_candidates.csv',a)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(periods={p:{n:{k:g[k] for k in ('trades','winners','losers','net_sum_pct','net_delta_vs_baseline','winners_harmed','losers_converted','added','removed','exits')} for n,g in group.items()} for p,group in report['periods'].items()},combined=report['combined']),indent=2,allow_nan=False))

if __name__=='__main__': main()
