#!/usr/bin/env python3
"""EXP40-P: price-based warning outcomes, not a trading replay."""
import json, hashlib
from collections import Counter, defaultdict
from bisect import bisect_right
from statistics import median
import aimn_exp40m_supertrend_forensics as m
import aimn_exp40o_transition_recognition_forensics as o

OUT=m.ROOT/'kiss/results/exp40p_transition_noise_forensics'
FEE=0.20
STOP=0.50
H=6

def analyze(period, rows, warnings):
    s5=m.snapshots(rows,5); s30=m.snapshots(m.aggregate(rows),30)
    available=[s['available_time'] for s in s30]
    index={r['timestamp']:i for i,r in enumerate(rows)}
    result=[]
    for w in warnings:
        if w['period']!=period or int(w['timeframe'])!=5: continue
        i=index[w['signal_time']]; r=rows[i]; s=s5[i]; target=w['target']
        assert w['decision_time']==s['available_time'] and w['st_direction']==s['trend']
        assert w['rule'] in o.warning_rules(rows,i,target)
        j=bisect_right(available,s['available_time'])-1
        ctx=s30[j] if j>=0 else {}
        atr=s['atr']; sign=1 if target=='LONG' else -1
        def move(a,b): return sign*100*(b/a-1)
        def prior(n):
            if not o.same_session(rows,i-n,i): return None,None
            c=[q['close'] for q in rows[i-n:i+1]]
            steps=[b-a for a,b in zip(c,c[1:])]; total=sum(abs(x) for x in steps)
            return move(c[0],c[-1]), sign*sum(steps)/total if total else 0.0
        p3,e3=prior(3); p6,e6=prior(6); p12,e12=prior(12)
        rec={**w,'major_st':ctx.get('trend','UNKNOWN'),'major_context_time':ctx.get('available_time'),
             'st_age':s['trend_age_bars'],'atr_pct':100*atr/r['close'] if atr else None,
             'signal_range_pct':100*(r['high']-r['low'])/r['close'],
             'signal_body_target_pct':move(r['open'],r['close']),
             'prior3_target_move_pct':p3,'prior3_efficiency':e3,'prior6_target_move_pct':p6,'prior6_efficiency':e6,
             'prior12_target_move_pct':p12,'prior12_efficiency':e12,
             'entry_open_hindsight':None,'terminal_move_pct_hindsight':None,'favorable_pct_hindsight':None,
             'adverse_pct_hindsight':None,'stop_touched_hindsight':None,'entry_bar_stop_touched_hindsight':None,
             'positive_closes_hindsight':None,'price_outcome_hindsight':'CENSORED'}
        if o.same_session(rows,i,i+H):
            future=rows[i+1:i+H+1]; entry=future[0]['open']
            fav=max([0]+[move(entry,q['high'] if target=='LONG' else q['low']) for q in future])
            adv=min([0]+[move(entry,q['low'] if target=='LONG' else q['high']) for q in future])
            terminal=move(entry,future[-1]['close']); positive=sum(move(entry,q['close'])>FEE for q in future)
            stop=adv<=-STOP
            # Descriptive labels, not true reversal labels or simulated trades.
            label='PERSISTENT_TARGET' if terminal>FEE and positive>=4 else 'TARGET_FADED' if fav>FEE else 'NO_FEE_SCALE_EXCURSION'
            rec.update(entry_open_hindsight=entry,terminal_move_pct_hindsight=terminal,favorable_pct_hindsight=fav,
                       adverse_pct_hindsight=adv,stop_touched_hindsight=stop,
                       entry_bar_stop_touched_hindsight=move(entry,future[0]['low'] if target=='LONG' else future[0]['high'])<=-STOP,
                       positive_closes_hindsight=positive,price_outcome_hindsight=label)
        result.append(rec)
    return result

def summarize(records):
    groups=defaultdict(list)
    for r in records:
        groups[r['period'],r['target'],r['rule'],'ALL'].append(r)
        groups[r['period'],r['target'],r['rule'],r['st_direction']+'/'+r['major_st']].append(r)
    out=[]; features=[]
    for (period,target,rule,context),rr in sorted(groups.items()):
        valid=[r for r in rr if r['price_outcome_hindsight']!='CENSORED']
        counts=Counter(r['price_outcome_hindsight'] for r in rr)
        out.append(dict(period=period,target=target,rule=rule,context=context,warnings=len(rr),complete=len(valid),
            persistent=counts['PERSISTENT_TARGET'],faded=counts['TARGET_FADED'],no_excursion=counts['NO_FEE_SCALE_EXCURSION'],censored=counts['CENSORED'],
            stop_touched=sum(r['stop_touched_hindsight'] for r in valid),entry_bar_stop=sum(r['entry_bar_stop_touched_hindsight'] for r in valid),
            persistent_stop_touched=sum(r['stop_touched_hindsight'] and r['price_outcome_hindsight']=='PERSISTENT_TARGET' for r in valid),
            median_terminal=median(r['terminal_move_pct_hindsight'] for r in valid) if valid else None))
        for label in ('PERSISTENT_TARGET','TARGET_FADED','NO_FEE_SCALE_EXCURSION'):
            subset=[r for r in valid if r['price_outcome_hindsight']==label]
            for key in ('st_distance_atr','st_age','atr_pct','signal_range_pct','signal_body_target_pct','prior3_target_move_pct','prior3_efficiency','prior6_target_move_pct','prior6_efficiency','prior12_target_move_pct','prior12_efficiency'):
                vals=[float(r[key]) for r in subset if r[key] not in (None,'')]
                features.append(dict(period=period,target=target,rule=rule,context=context,outcome=label,feature=key,count=len(subset),available=len(vals),median=median(vals) if vals else None))
    return out,features

def main():
    assert hashlib.sha256((m.ROOT/'kiss/kiss_exp53_supertrend.py').read_bytes()).hexdigest()==o.ST_HASH
    disc=m.load(m.ROOT/'kiss/visual_research/aimn_nvda_candles.json','020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50')
    warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec')
    test=m.load(m.TEST,'eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d')
    path=o.OUT/'causal_warning_audit.csv'; warnings=m.read_csv(path)
    assert len(warnings)==2081
    rows=analyze('DISCOVERY',disc,warnings)+analyze('NOVEMBER',warm+test,warnings)
    assert len(rows)==sum(int(w['timeframe'])==5 for w in warnings)==1837
    groups,features=summarize(rows)
    report=dict(notes=['Observational only; both periods discovery; no orders or strategy changes.', 'Only 5m warnings; completed 30m context. Duplicate warnings across rules and overlapping horizons retained.', 'Next open reference; six same-session bars including entry bar; incomplete horizons censored.', 'Directional simple price returns, not engine P&L. Persistent proxy: terminal >0.20% and at least four closes >0.20%. Faded: otherwise favorable excursion >0.20%. Other cases no fee-scale excursion.', '0.50% adverse touch is static diagnostic, not actual trailing-stop replay. Intrabar ordering unknown. Price outcome labels do not establish major reversal truth.', 'Thresholds chosen for descriptive analysis, not optimized.'],warning_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),warnings=len(rows),groups=[g for g in groups if g['context']=='ALL'])
    OUT.mkdir(parents=True,exist_ok=False)
    m.write_csv(OUT/'warning_price_audit.csv',rows); m.write_csv(OUT/'outcome_groups.csv',groups); m.write_csv(OUT/'feature_comparison.csv',features)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__': main()
