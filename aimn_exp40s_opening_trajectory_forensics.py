#!/usr/bin/env python3
"""EXP40-S: opening-session warning forensics, no trading or strategy changes."""
import csv
import json
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'kiss/results/exp40q_combined_trajectory_forensics/warning_decisions.csv'
OUT = ROOT/'kiss/results/exp40s_opening_trajectory_forensics'
DATA = {
    'DISCOVERY': ('kiss/visual_research/aimn_nvda_candles.json','020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50',4680),
    'NOVEMBER': ('kiss/visual_research/independent_holdout_exp40l/nvda_2026-11-16_2026-11-25_5m_iex.json','eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d',624),
}
WARM = ('kiss/visual_research/independent_holdout_exp144/nvda_nov_2026_5m_iex.json','d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec',780)

def read_data(spec):
    path,digest,n=spec
    raw=(ROOT/path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest: raise ValueError('Hash mismatch: '+path)
    rows=json.loads(raw)
    assert len(rows)==n and n%78==0
    assert all(a['timestamp']<b['timestamp'] for a,b in zip(rows,rows[1:]))
    for i in range(0,n,78):
        t=datetime.fromisoformat(rows[i]['timestamp'])
        assert t.strftime('%H:%M')=='09:30'
        assert all(datetime.fromisoformat(rows[i+j]['timestamp'])==t+timedelta(minutes=5*j) for j in range(78))
    return rows

def pct(a,b): return 100*(b/a-1)
def streak(values):
    n=0
    for a,b in reversed(list(zip(values,values[1:]))):
        if b>=a: break
        n+=1
    return n

def features(rows,i,prior_warnings,prior_focus):
    start=i//78*78
    session=rows[start:i+1]
    o=float(session[0]['open']); c=[float(x['close']) for x in session]
    h=[float(x['high']) for x in session]; l=[float(x['low']) for x in session]
    p=max(range(len(h)),key=lambda j:(h[j],j))
    low=min(l); prev=float(rows[start-1]['close']) if start else None
    # Use first open, then completed closes. Signed efficiency favors SHORT.
    path=[o]+c; changes=[b-a for a,b in zip(path,path[1:])]
    travel=sum(abs(x) for x in changes)
    prev30=None
    if start>=6:
        prev30=pct(float(rows[start-6]['open']),prev)
    return dict(session_bars=len(session),opening_gap_pct=pct(prev,o) if prev is not None else None,
        opening_candle_return_pct=pct(o,c[0]),session_return_pct=pct(o,c[-1]),
        session_peak_age_bars=len(h)-1-p,session_peak_high=h[p],
        session_peak_to_close_pct=-pct(h[p],c[-1]),session_low_to_close_pct=pct(low,c[-1]),
        session_range_pct=100*(max(h)-low)/o,
        session_short_efficiency=-sum(changes)/travel if travel else 0.0,
        lower_high_streak=streak(h),lower_low_streak=streak(l),lower_close_streak=streak(c),
        prior_session_last30_return_pct=prev30,
        session_warning_number=prior_warnings+1,focus_warning_number=prior_focus+1)

def write(path,rows):
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    raw=SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='05d885fa55df7237001662cdc67e078aad43669c494c4bcdf195bd19c877cf2d'
    with SOURCE.open(newline='') as f: warnings=list(csv.DictReader(f))
    assert Counter(w['period'] for w in warnings)=={'DISCOVERY':546,'NOVEMBER':82}
    audit=[]
    for period,spec in DATA.items():
        rows=read_data(spec)
        if period=='NOVEMBER': rows=read_data(WARM)+rows
        index={r['timestamp']:i for i,r in enumerate(rows)}
        counts=Counter(); focus=Counter()
        for w in sorted((x for x in warnings if x['period']==period),key=lambda x:x['signal_time']):
            t=w['signal_time']; day=t[:10]; i=index[t]
            assert abs(float(w['close'])-float(rows[i]['close']))<1e-8
            assert datetime.fromisoformat(w['decision_time'])==datetime.fromisoformat(t)+timedelta(minutes=5)
            is_focus=w['st_direction']=='LONG' and w['major_st']=='SHORT'
            if is_focus and w['Q4']=='MISSING':
                audit.append(dict(**w,**features(rows,i,counts[day],focus[day])))
            counts[day]+=1
            if is_focus: focus[day]+=1
    assert len(audit)==24
    assert Counter((r['period'],r['price_outcome_hindsight']) for r in audit)=={
        ('DISCOVERY','PERSISTENT_TARGET'):6,('DISCOVERY','TARGET_FADED'):9,('DISCOVERY','NO_FEE_SCALE_EXCURSION'):5,
        ('NOVEMBER','PERSISTENT_TARGET'):2,('NOVEMBER','TARGET_FADED'):2}
    keys=['opening_gap_pct','opening_candle_return_pct','session_return_pct','session_peak_age_bars','session_peak_to_close_pct','session_low_to_close_pct','session_range_pct','session_short_efficiency','lower_high_streak','lower_low_streak','lower_close_streak','prior_session_last30_return_pct','session_warning_number','focus_warning_number','atr_pct','prior3_efficiency','prior6_efficiency']
    groups=defaultdict(list)
    for r in audit:
        groups[r['period'],r['price_outcome_hindsight']].append(r)
    comparison=[]; group_summary=[]
    for (period,outcome),rr in sorted(groups.items()):
        rec=dict(period=period,outcome=outcome,count=len(rr),first_focus_warnings=sum(r['focus_warning_number']==1 for r in rr))
        for key in keys:
            vals=[float(r[key]) for r in rr if r[key] not in ('',None)]
            med=round(median(vals),6) if vals else None
            comparison.append(dict(period=period,outcome=outcome,feature=key,count=len(rr),available=len(vals),median=med))
            if key in ('opening_gap_pct','session_return_pct','session_peak_age_bars','session_peak_to_close_pct','session_short_efficiency','lower_high_streak','lower_low_streak','focus_warning_number'): rec[key]=med
        group_summary.append(rec)
    report=dict(notes=[
        'Observational only; both periods discovery; no thresholds selected or strategy changes.',
        'All features use completed candles through signal; outcome columns inherited from EXP40-P are retrospective.',
        'Session efficiency includes first open and completed closes; positive favors SHORT. Opening gap and previous session context use prior available regular-session close.',
        'Prior last30 return uses previous session final six-bar open to close. November includes verified EXP144 warm-up.',
        'Warning numbers count all earlier same-session TWO_STEP SHORT warnings, or earlier LONG/SHORT-context warnings respectively, regardless of Q4 decision or outcome.',
        'Repeated warnings overlap; 24 observations are not independent trades. No profitability inference.'
    ],source_sha256=hashlib.sha256(raw).hexdigest(),observations=len(audit),groups=group_summary,
        first_vs_repeated=[dict(period=p,warning_group=g,observations=len(rr),outcomes=dict(Counter(r['price_outcome_hindsight'] for r in rr))) for p in DATA for g in ('FIRST','REPEATED') for rr in [[r for r in audit if r['period']==p and (r['focus_warning_number']==1)==(g=='FIRST')]]])
    OUT.mkdir(parents=True,exist_ok=False)
    write(OUT/'opening_warning_audit.csv',audit)
    write(OUT/'opening_feature_comparison.csv',comparison)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__': main()
