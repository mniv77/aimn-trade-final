#!/usr/bin/env python3
"""EXP40-O: whole-chart transition benchmarks, observational only."""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from statistics import median
import aimn_exp40m_supertrend_forensics as m

OUT = m.ROOT / 'kiss/results/exp40o_transition_recognition_forensics'
ST_HASH = 'c1727a67c903fdc7dc0ca61562f233a07908aebb04347ce255f4e9fccede1749'
HORIZON = 6
PIVOT = 3
RULES = ('PEAK_BREAK', 'TWO_STEP')


def same_session(rows, a, b):
    return (0 <= a <= b < len(rows) and
            rows[a]['timestamp'][:10] == rows[b]['timestamp'][:10])


def elapsed(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()/60


def direction_move(ref, price, target):
    return 100 * (price-ref)/ref * (1 if target == 'LONG' else -1)


def warning_rules(rows, i, target):
    """Symmetric, causal rules; no ST requirement, no future values."""
    if not same_session(rows, i-2, i):
        return []
    a, b, c = rows[i-2:i+1]
    down = target == 'SHORT'
    result = []
    if same_session(rows, i-4, i):
        prior = rows[i-4:i-1]
        if down:
            peak = b['high'] >= max(r['high'] for r in prior)
            broke = c['close'] < b['low'] and c['close'] < c['open']
        else:
            peak = b['low'] <= min(r['low'] for r in prior)
            broke = c['close'] > b['high'] and c['close'] > c['open']
        if peak and broke:
            result.append('PEAK_BREAK')
    keys = ('high', 'low', 'close')
    if all((a[k] > b[k] > c[k]) if down else (a[k] < b[k] < c[k]) for k in keys):
        result.append('TWO_STEP')
    return result


def analyze(period, rows, minutes, start):
    s = m.snapshots(rows, minutes)
    flips, warnings, pivots = [], [], []
    def eligible(i):
        return rows[i]['timestamp'] >= start
    def future_flip(i, target, include_current=False):
        for j in range(i if include_current else i+1, min(i+HORIZON+1,len(rows))):
            if not same_session(rows,i,j):
                break
            if s[j]['transition'] == ('LONG->SHORT' if target=='SHORT' else 'SHORT->LONG'):
                return j
        return None
    # Warnings are evaluated on all eligible completed bars, not just V17 entries.
    for i, r in enumerate(rows):
        if not eligible(i):
            continue
        for target in ('SHORT','LONG'):
            for rule in warning_rules(rows,i,target):
                j = future_flip(i,target)
                complete = same_session(rows,i,i+HORIZON)
                end = i+HORIZON if complete else None
                future = rows[i+1:end+1] if complete else []
                favorable = (max(direction_move(r['close'],q['low'] if target=='SHORT' else q['high'],target) for q in future) if future else None)
                adverse = (min(direction_move(r['close'],q['high'] if target=='SHORT' else q['low'],target) for q in future) if future else None)
                # A warning in the opposite ST state can anticipate a flip. Other warnings
                # are retained, but are not counted as failed flip predictions.
                opposite = s[i]['trend'] == ('LONG' if target=='SHORT' else 'SHORT')
                label = ('MATCHED' if j is not None else 'NO_FLIP_WITHIN_HORIZON' if complete else 'CENSORED') if opposite else 'NOT_OPPOSITE_ST'
                warnings.append(dict(period=period,timeframe=minutes,rule=rule,target=target,
                    signal_time=r['timestamp'],decision_time=s[i]['available_time'],st_direction=s[i]['trend'],
                    close=r['close'],st_distance_atr=s[i]['distance_atr'],flip_label_hindsight=label,
                    matched_flip_time_hindsight=s[j]['available_time'] if j is not None and opposite else None,
                    lead_minutes_hindsight=elapsed(s[i]['available_time'],s[j]['available_time']) if j is not None and opposite else None,
                    forward_close_move_pct_hindsight=direction_move(r['close'],rows[end]['close'],target) if complete else None,
                    forward_favorable_pct_hindsight=favorable,forward_adverse_pct_hindsight=adverse))
        # Independent retrospective price benchmark: strict centered 3-bar pivot,
        # followed by >= 1 ATR directional close displacement within 3 bars.
        # This is a proxy, not a claim of objective major reversal ground truth.
        if same_session(rows,i-PIVOT,i+PIVOT) and s[i]['atr'] is not None:
            neighbors=rows[i-PIVOT:i]+rows[i+1:i+PIVOT+1]
            for target in ('SHORT','LONG'):
                down=target=='SHORT'
                strict=(r['high']>max(q['high'] for q in neighbors)) if down else (r['low']<min(q['low'] for q in neighbors))
                move=max((r['close']-q['close']) if down else (q['close']-r['close']) for q in rows[i+1:i+PIVOT+1])
                if not strict or move<s[i]['atr']:
                    continue
                j=future_flip(i,target,True)
                complete=same_session(rows,i,i+HORIZON)
                pivots.append(dict(period=period,timeframe=minutes,target=target,pivot_time=r['timestamp'],
                    pivot_available_time=s[i]['available_time'],label_known_time=s[i+PIVOT]['available_time'],
                    pivot_close=r['close'],excursion_atr_hindsight=move/s[i]['atr'],st_direction_at_pivot=s[i]['trend'],
                    flip_time_hindsight=s[j]['available_time'] if j is not None else None,
                    flip_label_hindsight='MATCHED' if j is not None else 'NO_FLIP_WITHIN_HORIZON' if complete else 'CENSORED'))
    for i, snap in enumerate(s):
        if not eligible(i) or not snap['transition']:
            continue
        old,target=snap['transition'].split('->')
        # Restrict the extreme to the previous ST run and current session, excluding flip bar.
        prior=[]; j=i-1
        while j>=0 and same_session(rows,j,i) and s[j]['trend']==old:
            prior.append(j); j-=1
        peak=None
        if prior:
            peak=max(prior,key=lambda k:(rows[k]['high'],k)) if target=='SHORT' else min(prior,key=lambda k:(rows[k]['low'],-k))
        matching=[w for w in warnings if w['target']==target and w['matched_flip_time_hindsight']==snap['available_time']]
        rec=dict(period=period,timeframe=minutes,transition=snap['transition'],flip_bar_time=snap['bar_time'],
                 flip_available_time=snap['available_time'],flip_close=snap['close'],prior_run_same_session_bars=len(prior),
                 extreme_bar_time_hindsight=rows[peak]['timestamp'] if peak is not None else None,
                 extreme_price_hindsight=(rows[peak]['high'] if target=='SHORT' else rows[peak]['low']) if peak is not None else None,
                 extreme_close_hindsight=rows[peak]['close'] if peak is not None else None,
                 delay_minutes_from_extreme_bar_close_hindsight=elapsed(s[peak]['available_time'],snap['available_time']) if peak is not None else None,
                 close_move_pct_hindsight=direction_move(rows[peak]['close'],snap['close'],target) if peak is not None else None)
        for rule in RULES:
            hits=[w for w in matching if w['rule']==rule]
            rec[rule.lower()+'_warning_count']=len(hits)
            rec[rule.lower()+'_earliest_lead_minutes']=max((w['lead_minutes_hindsight'] for w in hits),default=None)
        flips.append(rec)
    return flips,warnings,pivots


def summarize(period,minutes,flips,warnings,pivots):
    out=[]
    for target in ('SHORT','LONG'):
        f=[r for r in flips if r['transition'].endswith('->'+target)]
        p=[r for r in pivots if r['target']==target]
        delays=[r['delay_minutes_from_extreme_bar_close_hindsight'] for r in f if r['delay_minutes_from_extreme_bar_close_hindsight'] is not None]
        moves=[r['close_move_pct_hindsight'] for r in f if r['close_move_pct_hindsight'] is not None]
        rec=dict(period=period,timeframe=minutes,target=target,flips=len(f),extreme_available=len(delays),
                 median_delay_minutes=median(delays) if delays else None,median_close_move_pct=median(moves) if moves else None,
                 price_pivot_proxies=len(p),price_pivot_flip_labels=dict(Counter(r['flip_label_hindsight'] for r in p)),rules={})
        for rule in RULES:
            w=[r for r in warnings if r['target']==target and r['rule']==rule]
            leads=[r['lead_minutes_hindsight'] for r in w if r['lead_minutes_hindsight'] is not None]
            rec['rules'][rule]=dict(warnings=len(w),labels=dict(Counter(r['flip_label_hindsight'] for r in w)),
                distinct_flips_anticipated=sum(r[rule.lower()+'_warning_count']>0 for r in f),median_warning_lead_minutes=median(leads) if leads else None)
        out.append(rec)
    return out


def main():
    source=m.ROOT/'kiss/kiss_exp53_supertrend.py'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==ST_HASH
    disc=m.load(m.ROOT/'kiss/visual_research/aimn_nvda_candles.json','020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50')
    warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec')
    test=m.load(m.TEST,'eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d')
    assert (len(disc),len(warm),len(test))==(4680,780,624)
    all_f=[]; all_w=[]; all_p=[]; summary=[]
    expected={('DISCOVERY',5):(61,61),('DISCOVERY',30):(12,11),('NOVEMBER',5):(7,7),('NOVEMBER',30):(1,1)}
    for period,data,start in [('DISCOVERY',disc,disc[0]['timestamp']),('NOVEMBER',warm+test,m.START)]:
        times=[r['timestamp'] for r in data]
        assert all(a<b for a,b in zip(times,times[1:]))
        for i in range(0,len(data),78):
            t=datetime.fromisoformat(times[i]); assert t.strftime('%H:%M')=='09:30'
            assert all(datetime.fromisoformat(times[i+j])==t+timedelta(minutes=5*j) for j in range(78))
        for minutes,rows in [(5,data),(30,m.aggregate(data))]:
            f,w,p=analyze(period,rows,minutes,start)
            counts=Counter(r['transition'] for r in f)
            assert (counts['LONG->SHORT'],counts['SHORT->LONG'])==expected[period,minutes]
            all_f+=f; all_w+=w; all_p+=p; summary+=summarize(period,minutes,f,w,p)
    report=dict(notes=['Observational only; no trades, optimization, or production edits. Both periods are discovery.',
        'ST ATR10 multiplier3. Warm-up as EXP40-M. All warning features use completed bars only.',
        'Flip matching: next 1-6 same-session bars (30m or 180m horizon). Session-end incomplete unmatched cases censored.',
        'Warnings already aligned with ST are retained but excluded from flip anticipation labels. Multiple warnings can match one flip.',
        'Extreme reference is retrospective, prior ST run within same session, excludes flip bar; delay starts at extreme bar close. Not executable.',
        'Price pivot proxy: strict centered 3-bar high/low and subsequent 3-bar close excursion >=1 ATR; known only after 3 future bars. Not objective major-trend truth.',
        'No flip within horizon does not prove a false price reversal. Future price outcomes are descriptive only.'],
        evaluated_5m_bars=5304,flip_count=len(all_f),warning_count=len(all_w),price_pivot_count=len(all_p),groups=summary)
    OUT.mkdir(parents=True,exist_ok=False)
    m.write_csv(OUT/'supertrend_flip_audit.csv',all_f)
    m.write_csv(OUT/'causal_warning_audit.csv',all_w)
    m.write_csv(OUT/'price_pivot_proxy_audit.csv',all_p)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
