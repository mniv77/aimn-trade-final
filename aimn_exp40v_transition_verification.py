#!/usr/bin/env python3
"""EXP40-V: fixed U4 trade verification, observational only."""
import json, hashlib
from bisect import bisect_right
from statistics import median
from collections import Counter
import aimn_exp40u_combined_causal_replay as u
from aimn_exp40u_combined_causal_replay import m,b,v,k
OUT=b.ROOT/'kiss/results/exp40v_transition_verification'

def audit(rows,trades,period):
    s5=m.snapshots(rows,5); s30=m.snapshots(m.aggregate(rows),30)
    avail=[x['available_time'] for x in s30]
    idx={r['timestamp']:i for i,r in enumerate(rows)}
    out=[]; inventory=[]
    for tr in trades:
        a,z=idx[tr['entry_time']],idx[tr['exit_time']]
        sig=idx[tr['signal_time']]; entry=float(tr['entry_price']); net=float(tr['net_pnl_pct'])
        assert a==sig+1 and entry==float(rows[a]['open']) and a<=z
        group='WIN' if net>0 else 'GIVEBACK' if float(tr['best_close_pct'])>0.2 else 'NO_FEE_CLOSE'
        inventory.append(dict(period=period,signal_time=tr['signal_time'],entry_time=tr['entry_time'],exit_time=tr['exit_time'],group=group,net_pct=net,completed_bars=z-a,entry_bar_stop=z==a and tr['exit_phase']=='INTRABAR'))
        for n in (1,2,3):
            i=a+n-1
            if i>=z: continue  # exit bar is never credited, including intrabar stops
            r,p=rows[i],rows[i-1]; s,prev=s5[i],s5[i-1]
            j=bisect_right(avail,s['available_time'])-1
            held=rows[a:i+1]; close=float(r['close']); nxt=float(rows[i+1]['open'])
            same=s['trend']==prev['trend']=='LONG' and s['distance_atr'] is not None and prev['distance_atr'] is not None
            retreat=same and s['distance_atr']>prev['distance_atr']
            rising=close>float(p['close']); higher_low=float(r['low'])>float(p['low'])
            best=max(0.,max((entry/float(x['close'])-1)*100 for x in held))
            never_short=all(x['trend']=='LONG' for x in s5[sig:i+1])
            flags=dict(V1=never_short and retreat and rising,V2=never_short and retreat and rising and higher_low,V3=never_short and retreat and rising and best<=0.2)
            alt=(entry/nxt-1)*100-0.2
            out.append(dict(period=period,group=group,signal_time=tr['signal_time'],entry_time=tr['entry_time'],bar_number=n,bar_time=r['timestamp'],decision_time=s['available_time'],st5=s['trend'],st30=s30[j]['trend'] if j>=0 else 'UNKNOWN',st_distance_atr=s['distance_atr'],st_distance_change_atr=s['distance_atr']-prev['distance_atr'] if same else None,never_short=never_short,retreat=bool(retreat),rising_close=rising,higher_low=higher_low,lower_high=float(r['high'])<float(p['high']),lower_low=float(r['low'])<float(p['low']),gross_close_pct=(entry/close-1)*100,best_close_pct=best,**flags,original_net_pct=net,next_open_net_hindsight=alt,delta_hindsight=alt-net))
    return out,inventory

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    disc=m.load(b.DATA,b.DATA_HASH)
    warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec')
    test=m.load(m.TEST,'eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d')
    v.checked(b.ROOT/'kiss/kiss_exp53_supertrend.py',u.o.ST_HASH)
    records=[]; inventory=[]; hashes={}
    for period,rows,expected in [('DISCOVERY',disc,(27,12,-1.688768)),('NOVEMBER',warm+test,(5,2,.722305))]:
        path=u.OUT/f'{period}_U4_trades.csv'; hashes[period]=hashlib.sha256(path.read_bytes()).hexdigest()
        trades=m.read_csv(path)
        assert (len(trades),sum(float(x['net_pnl_pct'])>0 for x in trades),round(sum(float(x['net_pnl_pct']) for x in trades),6))==expected
        start=rows[0]['timestamp'] if period=='DISCOVERY' else m.START
        feat,total=u.features(rows,start); u.check_features(rows,period,feat,total)
        replay,_,op,_=u.replay(rows,True,u.gate_for(feat,'U4'),True,True,True,warning='bullish_upper_close',entry_detector=lambda i:i in feat)
        assert op is None; k.e.verify_csv(replay,path)
        a,z=audit(rows,trades,period); records.extend(a); inventory.extend(z)
    groups=[]; rules=[]
    for period in ('DISCOVERY','NOVEMBER','COMBINED'):
        rr=[x for x in records if period=='COMBINED' or x['period']==period]
        for n in (1,2,3):
            for group in ('WIN','NO_FEE_CLOSE','GIVEBACK'):
                g=[x for x in rr if x['bar_number']==n and x['group']==group]
                groups.append(dict(period=period,bar=n,group=group,count=len(g),median_gross_close_pct=round(median(x['gross_close_pct'] for x in g),6) if g else None,never_short=sum(x['never_short'] for x in g),retreat=sum(x['retreat'] for x in g),rising_close=sum(x['rising_close'] for x in g),lower_low=sum(x['lower_low'] for x in g)))
        for rule in ('V1','V2','V3'):
            first={}
            for x in rr:
                if x[rule]: first.setdefault(x['signal_time'],x)
            g=list(first.values())
            rules.append(dict(period=period,rule=rule,triggered=len(g),groups=dict(Counter(x['group'] for x in g)),improved=sum(x['delta_hindsight']>0 for x in g),harmed=sum(x['delta_hindsight']<0 for x in g),winners_harmed=sum(x['group']=='WIN' and x['delta_hindsight']<0 for x in g),delta_sum_pct=round(sum(x['delta_hindsight'] for x in g),6)))
    report=dict(notes=['Fixed-trade observational counterfactual only; both periods discovery. No new entries simulated.','First three fully held candles only; excludes original exit candle. Decision at close, hypothetical fill next open.','V1: ST remains LONG since signal, distance increases versus prior bar, rising close. V2 adds higher low. V3 adds best completed gross close <= fee. No fitted thresholds.','Existing stops and exits are not changed. Counterfactual deltas do not establish strategy profitability.'],source_hashes=hashes,trade_groups=dict(Counter(x['group'] for x in inventory)),entry_bar_stops=sum(x['entry_bar_stop'] for x in inventory),observations=len(records),groups=groups,rules=rules)
    OUT.mkdir(parents=True,exist_ok=False)
    for name,data in [('trade_inventory',inventory),('verification_audit',records),('feature_comparison',groups),('rule_comparison',rules)]: m.write_csv(OUT/f'{name}.csv',data)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n'); print(json.dumps(report,indent=2,allow_nan=False))
if __name__=='__main__': main()
