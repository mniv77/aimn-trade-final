#!/usr/bin/env python3
"""EXP40-N: observational multi-timeframe ST trajectory audit, no orders."""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from bisect import bisect_right
from statistics import median, mean
import aimn_exp40m_supertrend_forensics as m

ROOT = m.ROOT
OUT = ROOT/'kiss/results/exp40n_supertrend_trajectory_forensics'
DISC = ROOT/'kiss/visual_research/aimn_nvda_candles.json'
B = ROOT/'kiss/results/exp40b_causal_replay'
K = ROOT/'kiss/results/exp40k_structural_reversal_replay'
ST_HASH = 'c1727a67c903fdc7dc0ca61562f233a07908aebb04347ce255f4e9fccede1749'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_sessions(rows):
    times = [datetime.fromisoformat(r['timestamp']) for r in rows]
    require(all(a < b for a,b in zip(times,times[1:])), 'Timestamp ordering')
    require(len(times)%78 == 0, 'Incomplete session count')
    for i in range(0,len(times),78):
        t=times[i]
        require(t.strftime('%H:%M:%S')=='09:30:00' and all(times[i+j]==t+timedelta(minutes=5*j) for j in range(78)), 'Incomplete session')
    return times


def enrich(series, minutes):
    result=[]
    for i,s in enumerate(series):
        rec=dict(s)
        rec['prior_trigger_band']=None
        rec['prior_trigger_direction']=None
        rec['close_minus_prior_trigger_atr']=None
        rec['next_trigger_band']=s['st']
        rec['next_trigger_distance_atr']=s['distance_atr']
        if i and series[i-1]['st'] is not None and s['atr'] is not None:
            p=series[i-1]
            rec.update(prior_trigger_band=p['st'],prior_trigger_direction=p['trend'],close_minus_prior_trigger_atr=(s['close']-p['st'])/s['atr'])
        for n in (3,6):
            key=f'absolute_distance_change_{n}bars_atr'
            rec[key]=None
            if i>=n:
                block=series[i-n:i+1]
                t=datetime.fromisoformat(block[0]['bar_time'])
                if all(x['trend']==s['trend'] and x['distance_atr'] is not None and datetime.fromisoformat(x['bar_time'])==t+timedelta(minutes=minutes*j) and x['bar_time'][:10]==s['bar_time'][:10] for j,x in enumerate(block)):
                    rec[key]=abs(s['distance_atr'])-abs(block[0]['distance_atr'])
        result.append(rec)
    return result


def trade_map(path, count, net):
    trades=m.read_csv(path)
    require(len(trades)==count and round(sum(float(t['net_pnl_pct']) for t in trades),6)==net, f'Trade parity: {path}')
    result={t['signal_time']:t for t in trades}
    require(len(result)==count, 'Duplicate trade signals')
    return result


def audit_period(rows, start, period, candidate_path, bpath, kpath, counts, nets):
    times=validate_sessions(rows)
    s5=enrich(m.snapshots(rows,5),5)
    s30=enrich(m.snapshots(m.aggregate(rows),30),30)
    avail=[s['available_time'] for s in s30]
    bytime={r['timestamp']:i for i,r in enumerate(rows)}
    cand=m.read_csv(candidate_path)
    require(len(cand)==counts[0] and len({c['signal_time'] for c in cand})==counts[0], 'Candidate count or duplicate')
    bm=trade_map(bpath,counts[1],nets[0]); km=trade_map(kpath,counts[2],nets[1])
    require(set(bm)|set(km) <= {c['signal_time'] for c in cand}, 'Trade not in candidates')
    empty30={k:None for k in s30[0]}
    audit=[]
    for c in cand:
        stamp=c['signal_time']; i=bytime[stamp]
        require(stamp>=start, 'Candidate before evaluation start')
        a=s5[i]; j=bisect_right(avail,a['available_time'])-1
        z=s30[j] if j>=0 else empty30
        if j>=0:
            require(z['available_time']<=a['available_time'], 'Future 30m candle')
        rec=dict(period=period,signal_time=stamp,candidate_status=c['status'],history_type=c.get('history_type'),allowed=c.get('allowed'))
        rec.update(m.prefixed(a,'st5_')); rec.update(m.prefixed(z,'st30_'))
        rec['st30_context_age_minutes']=(datetime.fromisoformat(a['available_time'])-datetime.fromisoformat(z['available_time'])).total_seconds()/60 if j>=0 else None
        rec['signal_open']=rows[i]['open']; rec['signal_high']=rows[i]['high']; rec['signal_low']=rows[i]['low']; rec['signal_close']=rows[i]['close']
        for n in (3,6):
            for field in ('high','low','close'):
                key=f'lower_{field}_count_{n}comparisons'
                rec[key]=None
                if i>=n and times[i-n].date()==times[i].date() and times[i]-times[i-n]==timedelta(minutes=5*n):
                    rec[key]=sum(float(rows[q][field])<float(rows[q-1][field]) for q in range(i-n+1,i+1))
        for name,mapping in [('b2',bm),('k3',km)]:
            t=mapping.get(stamp); net=float(t['net_pnl_pct']) if t else None
            rec[f'{name}_net_hindsight']=net
            rec[f'{name}_outcome_hindsight']='NOT_EXECUTED' if t is None else 'WIN' if net>0 else 'LOSS' if net<0 else 'BREAK_EVEN'
        for name,series in [('5m',s5),('30m',s30)]:
            future=next((s for s in series if s['available_time']>a['available_time'] and s['available_time'][:10]==stamp[:10] and s['transition']=='LONG->SHORT'),None)
            rec[f'next_{name}_short_flip_delay_minutes_hindsight']=(datetime.fromisoformat(future['available_time'])-datetime.fromisoformat(a['available_time'])).total_seconds()/60 if future else None
        audit.append(rec)
    return audit


FEATURES=['st5_distance_atr','st30_distance_atr','st5_close_minus_prior_trigger_atr','st30_close_minus_prior_trigger_atr','st5_absolute_distance_change_3bars_atr','st5_absolute_distance_change_6bars_atr','st30_absolute_distance_change_3bars_atr','st30_absolute_distance_change_6bars_atr','st5_trend_age_bars','st30_trend_age_bars','st30_context_age_minutes','lower_high_count_3comparisons','lower_high_count_6comparisons','lower_low_count_3comparisons','lower_low_count_6comparisons','lower_close_count_3comparisons','lower_close_count_6comparisons']


def compare(audit):
    result=[]; groups=[]
    for period in ('DISCOVERY','NOVEMBER'):
        subset=[a for a in audit if a['period']==period]
        for context in ['ALL']+sorted({f"{a['st5_trend']}/{a['st30_trend']}" for a in subset}):
            matched=[a for a in subset if context=='ALL' or f"{a['st5_trend']}/{a['st30_trend']}"==context]
            for outcome in ('WIN','LOSS','BREAK_EVEN','NOT_EXECUTED'):
                group=[a for a in matched if a['b2_outcome_hindsight']==outcome]
                if not group: continue
                groups.append(dict(period=period,context=context,b2_outcome=outcome,candidates=len(group),net_sum_pct=round(sum(a['b2_net_hindsight'] for a in group if a['b2_net_hindsight'] is not None),6) if outcome!='NOT_EXECUTED' else None))
                for f in FEATURES:
                    v=[a[f] for a in group if a[f] is not None]
                    result.append(dict(period=period,context=context,b2_outcome=outcome,feature=f,candidates=len(group),available=len(v),mean=round(mean(v),6) if v else None,median=round(median(v),6) if v else None))
    return result,groups


def main():
    require(not OUT.exists(), 'Refusing to overwrite EXP40-N')
    require(digest(ROOT/'kiss/kiss_exp53_supertrend.py')==ST_HASH,'SuperTrend source hash mismatch')
    disc=m.load(DISC,'020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50')
    warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec')
    test=m.load(m.TEST,'eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d')
    require((len(disc),len(warm),len(test))==(4680,780,624),'Candle count')
    require(disc[-1]['timestamp']<warm[0]['timestamp']<test[0]['timestamp'],'Dataset ordering')
    dpaths=(K/'K3_BULLISH_UPPER_CLOSE_candidates.csv', B/'B2_trades.csv',K/'K3_BULLISH_UPPER_CLOSE_trades.csv')
    npaths=(m.SOURCE/'K3_candidates.csv',m.SOURCE/'B2_trades.csv',m.SOURCE/'K3_trades.csv')
    a=audit_period(disc,disc[0]['timestamp'],'DISCOVERY',*dpaths,(135,122,32),(-30.391587,-.199296))
    a+=audit_period(warm+test,m.START,'NOVEMBER',*npaths,(13,12,3),(-3.268879,-1.673977))
    # Check November ST snapshots against the already recorded EXP40-M audit.
    old={r['signal_time']:r for r in m.read_csv(m.OUT/'candidate_supertrend_audit.csv')}
    require(len(old)==13,'EXP40-M candidate count')
    for r in a:
        if r['period']!='NOVEMBER': continue
        p=old[r['signal_time']]
        for f in ('st5_trend','st30_trend','st5_available_time','st30_available_time'):
            require(r[f]==p[f],f'EXP40-M parity: {f}')
        for f in ('st5_distance_atr','st30_distance_atr'):
            require(abs(r[f]-float(p[f]))<1e-10,f'EXP40-M parity: {f}')
    comp,groups=compare(a)
    report=dict(notes=['Observational only; both periods are discovery data. No thresholds selected or strategy replay performed.','B2 outcome labels exist only for executed trades; blocked candidates are not assumed losers. K3 labels reflect selected executions.','5m and 30m ST ATR10 multiplier3; 30m context completed only. Discovery begins without prehistory; missing values retained. November has 780 warm-up bars.','Prior trigger band is previous active ST; current active ST is next-bar trigger boundary. Prior distance uses current ATR; approach uses change in absolute current-band ATR distance (negative means closer).','Approach windows require uninterrupted same-session bars and unchanged ST direction. 30m windows count 30m bars, not 5m bars.','30m distance describes the last completed 30m close, not the current 5m price. Future flip labels are retrospective.','Trade sums are not portfolio returns; feed comparability not established.'],source_st_sha256=ST_HASH,input_hashes={str(p.relative_to(ROOT)):digest(p) for p in (DISC,m.WARM,m.TEST,*dpaths,*npaths,m.OUT/'candidate_supertrend_audit.csv')},candidates=len(a),november_m_parity=13,groups=groups,context_counts={p:dict(Counter(f"{r['st5_trend']}/{r['st30_trend']}" for r in a if r['period']==p)) for p in ('DISCOVERY','NOVEMBER')},all_context_feature_summary=[r for r in comp if r['context']=='ALL' and r['b2_outcome'] in ('WIN','LOSS')])
    OUT.mkdir(parents=True,exist_ok=False)
    m.write_csv(OUT/'candidate_trajectory_audit.csv',a)
    m.write_csv(OUT/'feature_comparison.csv',comp)
    m.write_csv(OUT/'outcome_groups.csv',groups)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
