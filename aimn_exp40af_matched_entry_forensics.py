#!/usr/bin/env python3
"""EXP40-AF: retrospective AE3 versus AE0 warning pairs; no trading."""
import csv, json, hashlib
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
from statistics import median
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'kiss/results/exp40ae_early_transition_forensics/warning_audit.csv'
OUT=ROOT/'kiss/results/exp40af_matched_entry_forensics'

def num(r,k):
    return float(r[k]) if r[k] not in ('',None) else None

def med(v):
    v=[x for x in v if x is not None]
    return round(median(v),6) if v else None

def write(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def summarize(rr):
    complete=[r for r in rr if r['both_complete']]
    return dict(pairs=len(rr),unique_late_signals=len({(r['period'],r['late_signal']) for r in rr}),both_complete=len(complete),contexts=dict(Counter(r['late_context'] for r in rr)),median_lead_minutes=med([r['lead_minutes'] for r in rr]),median_entry_advantage_pct=med([r['entry_advantage_pct'] for r in rr]),better_entry=sum(r['entry_advantage_pct']>0 for r in rr if r['entry_advantage_pct'] is not None),priced_pairs=sum(r['entry_advantage_pct'] is not None for r in rr),early_persistent=sum(r['early_outcome']=='PERSISTENT_TARGET' for r in complete),late_persistent=sum(r['late_outcome']=='PERSISTENT_TARGET' for r in complete),median_favorable_delta=med([r['favorable_delta'] for r in complete]),median_adverse_delta=med([r['adverse_delta'] for r in complete]),median_terminal_delta=med([r['terminal_delta'] for r in complete]))

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    with SRC.open(newline='') as f: rows=list(csv.DictReader(f))
    late={(r['period'],r['signal_time']):r for r in rows if r['detector']=='AE0'}
    assert len(late)==sum(r['detector']=='AE0' for r in rows)
    early=[r for r in rows if r['detector']=='AE3' and r['context']=='LONG/SHORT']
    assert Counter(r['two_step_match'] for r in early)=={'EARLIER':85,'NO_LATER_TWO_STEP':72,'CENSORED':17}
    pairs=[]
    for a in early:
        if a['two_step_match']!='EARLIER': continue
        lead=int(float(a['two_step_lead_bars'])); assert 1<=lead<=6
        stamp=(datetime.fromisoformat(a['signal_time'])+timedelta(minutes=5*lead)).isoformat(sep=' ')
        b=late[a['period'],stamp]; assert stamp[:10]==a['signal_time'][:10]
        ea,eb=num(a,'next_open_hindsight'),num(b,'next_open_hindsight')
        complete=all(r['price_outcome_hindsight']!='CENSORED' for r in (a,b))
        p=dict(period=a['period'],early_signal=a['signal_time'],late_signal=stamp,lead_minutes=5*lead,late_context=b['context'],early_entry=ea,late_entry=eb,entry_advantage_pct=100*(ea/eb-1) if ea is not None and eb is not None else None,both_complete=complete,early_outcome=a['price_outcome_hindsight'],late_outcome=b['price_outcome_hindsight'])
        for k in ('favorable','adverse','terminal'):
            x,y=num(a,k+'_hindsight'),num(b,k+'_hindsight'); p['early_'+k]=x; p['late_'+k]=y; p[k+'_delta']=x-y if complete else None
        pairs.append(p)
    # Earliest warning per later timestamp, no selection using future price outcomes.
    unique={}
    for p in sorted(pairs,key=lambda x:x['early_signal']): unique.setdefault((p['period'],p['late_signal']),p)
    unique=list(unique.values())
    unmatched=[r for r in early if r['two_step_match']=='NO_LATER_TWO_STEP']
    report=dict(notes=['All periods discovery. Retrospective pairing is not causal entry logic or proof of same transition.','Six-bar outcome windows start at different times; deltas are not same-endpoint trade returns. Positive adverse delta means less adverse excursion.','Earliest AE3 per matched AE0 chosen for deduplication; overlapping episodes remain dependent.','Unmatched means no AE0 within six bars, not proof of a missed trade. No replay or orders.'],source_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),groups={})
    for period in ('ALL','JUN_AUG','SEP_OCT','NOV'):
        filt=lambda rr:[r for r in rr if period=='ALL' or r['period']==period]
        g=report['groups'][period]={}
        for label,rr in [('all_pairs',pairs),('unique_pairs',unique),('unique_same_context',[p for p in unique if p['late_context']=='LONG/SHORT']),('unique_changed_context',[p for p in unique if p['late_context']!='LONG/SHORT'])]: g[label]=summarize(filt(rr))
        u=filt(unmatched); g['unmatched']=dict(count=len(u),outcomes=dict(Counter(r['price_outcome_hindsight'] for r in u)),median_terminal=med([num(r,'terminal_hindsight') for r in u]))
    OUT.mkdir(parents=True,exist_ok=False); write(OUT/'matched_all.csv',pairs); write(OUT/'matched_unique.csv',unique); write(OUT/'unmatched_ae3.csv',unmatched)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report['groups']['ALL'],indent=2,allow_nan=False))
    for p in ('JUN_AUG','SEP_OCT','NOV'): print(p,json.dumps({k:report['groups'][p][k] for k in ('unique_pairs','unmatched')},allow_nan=False))

if __name__=='__main__': main()
