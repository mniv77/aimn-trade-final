#!/usr/bin/env python3
"""EXP40-R: causal trailing peak reference and retrospective entry timing audit."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'kiss/results/exp40q_combined_trajectory_forensics/warning_decisions.csv'
OUT = ROOT/'kiss/results/exp40r_entry_timing_forensics'
DATA = {
    'DISCOVERY': ('kiss/visual_research/aimn_nvda_candles.json','020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50',4680),
    'NOVEMBER': ('kiss/visual_research/independent_holdout_exp40l/nvda_2026-11-16_2026-11-25_5m_iex.json','eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d',624),
}

def read_data(path, digest, count):
    raw = (ROOT/path).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==digest, path
    rows = json.loads(raw)
    assert len(rows)==count
    assert all(a['timestamp']<b['timestamp'] for a,b in zip(rows,rows[1:]))
    for i in range(0,len(rows),78):
        t=datetime.fromisoformat(rows[i]['timestamp'])
        assert t.strftime('%H:%M')=='09:30'
        assert all(datetime.fromisoformat(rows[i+j]['timestamp'])==t+timedelta(minutes=5*j) for j in range(78))
    return rows

def num(r,k):
    v=r.get(k)
    return float(v) if v not in ('',None) else None

def write(path, rows):
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def audit_one(w, rows, i):
    s=rows[i]; t=datetime.fromisoformat(s['timestamp'])
    assert datetime.fromisoformat(w['decision_time'])==t+timedelta(minutes=5)
    assert abs(float(w['close'])-float(s['close']))<1e-8
    # Latest equal high wins; window includes signal bar, never future bars.
    start=max(i//78*78,i-11)
    p=max(range(start,i+1),key=lambda j:(float(rows[j]['high']),j))
    peak=float(rows[p]['high']); close=float(s['close'])
    entry=float(rows[i+1]['open']) if i%78!=77 else None
    old=num(w,'entry_open_hindsight')
    if old is not None:
        assert entry is not None and abs(old-entry)<1e-8
    return dict(**w,context=w['st_direction']+'/'+w['major_st'],peak_window_bars=i-start+1,
        peak_time=rows[p]['timestamp'],peak_high=peak,peak_age_bars=i-p,
        peak_to_decision_minutes=5*(i-p),peak_to_signal_close_pct=100*(peak-close)/peak,
        next_open_reference=entry,peak_to_next_open_pct=100*(peak-entry)/peak if entry is not None else None,
        peak_to_next_open_minutes=5*(i-p) if entry is not None else None)

def stats(rows,variant):
    selected=[r for r in rows if r[variant]=='PASS' and r['price_outcome_hindsight']!='CENSORED']
    def med(k):
        v=[num(r,k) for r in selected if num(r,k) is not None]
        return round(median(v),6) if v else None
    return dict(variant=variant,selected=len(selected),persistent=sum(r['price_outcome_hindsight']=='PERSISTENT_TARGET' for r in selected),
        median_peak_age_bars=med('peak_age_bars'),median_peak_to_entry_pct=med('peak_to_next_open_pct'),
        median_remaining_favorable_pct=med('favorable_pct_hindsight'),median_terminal_pct=med('terminal_move_pct_hindsight'),
        median_adverse_pct=med('adverse_pct_hindsight'),
        median_matched_st_lead_minutes=med('lead_minutes_hindsight'),
        matched_st_leads=sum(num(r,'lead_minutes_hindsight') is not None for r in selected),
        partial_peak_windows=sum(r['peak_window_bars']<12 for r in selected))

def main():
    raw=SOURCE.read_bytes()
    with SOURCE.open(newline='') as f: warnings=list(csv.DictReader(f))
    assert Counter(w['period'] for w in warnings)=={'DISCOVERY':546,'NOVEMBER':82}
    assert len({(w['period'],w['signal_time']) for w in warnings})==628
    audit=[]
    for period,args in DATA.items():
        rows=read_data(*args); index={r['timestamp']:i for i,r in enumerate(rows)}
        for w in warnings:
            if w['period']==period:
                audit.append(audit_one(w,rows,index[w['signal_time']]))
    assert len(audit)==628
    groups=defaultdict(list)
    for r in audit:
        groups[r['period'],r['context']].append(r)
        groups[r['period'],'ALL'].append(r)
    results=[dict(period=p,context=c,**stats(rr,v)) for (p,c),rr in sorted(groups.items()) for v in ('Q0','Q3','Q4')]
    focus=[r for r in results if r['context']=='LONG/SHORT']
    assert [(r['selected'],r['persistent']) for r in focus]==[(90,18),(33,10),(24,9),(18,8),(8,5),(7,5)]
    missed=[r for r in audit if r['context']=='LONG/SHORT' and r['price_outcome_hindsight']=='PERSISTENT_TARGET' and r['Q4']!='PASS']
    assert len(missed)==12
    report=dict(notes=[
        'Observational only; both periods discovery; no trading simulation or production edits.',
        'Peak proxy is highest high of latest 12 completed same-session bars including signal; latest equal high wins. Not an objective major turning point.',
        'Peak age is measured from peak bar completion to signal completion/next bar open, not from unknown intrabar peak time.',
        'Next open is a historical reference, not a guaranteed executable fill. Remaining favorable movement uses EXP40-P six-bar horizon.',
        'Q3/Q4 select at the same signal time; group timing differences reflect selection, not a measured execution delay. Overlapping warnings retained.',
        'Partial opening windows retained and counted; missing efficiency decisions remain missing. No new threshold selected.'
        ],source_sha256=hashlib.sha256(raw).hexdigest(),warnings=len(audit),focus=focus,
        missed_persistent_focus=dict(Counter(r['Q4'] for r in missed)),
        missed_examples=[{k:r[k] for k in ('period','signal_time','Q3','Q4','peak_age_bars','peak_to_next_open_pct','terminal_move_pct_hindsight','favorable_pct_hindsight')} for r in missed])
    OUT.mkdir(parents=True,exist_ok=False)
    write(OUT/'entry_timing_audit.csv',audit)
    write(OUT/'variant_timing_comparison.csv',results)
    write(OUT/'missed_persistent_warnings.csv',missed)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__': main()
