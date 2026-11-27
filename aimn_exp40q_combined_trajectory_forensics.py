#!/usr/bin/env python3
"""EXP40-Q: fixed sign-based trajectory screen, observational only."""
import csv
import json
import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'kiss/results/exp40p_transition_noise_forensics/warning_price_audit.csv'
OUT = ROOT / 'kiss/results/exp40q_combined_trajectory_forensics'
RULES = ('Q0','Q1','Q2','Q3','Q4')
PERSIST = 'PERSISTENT_TARGET'

def number(r, key):
    return float(r[key]) if r[key] not in ('', None) else None

def decisions(r):
    e6, e12 = (number(r,k) for k in ('prior6_efficiency','prior12_efficiency'))
    return dict(Q0=True, Q1=None if e6 is None else e6>0,
                Q2=None if e12 is None else e12>0,
                Q3=None if e6 is None or e12 is None else e6>0 and e12>0,
                Q4=None if e6 is None or e12 is None else e6>e12>0)

def stats(rows, variant):
    complete = [r for r in rows if r['price_outcome_hindsight']!='CENSORED']
    eligible = [r for r in complete if decisions(r)[variant] is not None]
    selected = [r for r in eligible if decisions(r)[variant]]
    c = Counter(r['price_outcome_hindsight'] for r in selected)
    p = c[PERSIST]
    total_p = sum(r['price_outcome_hindsight']==PERSIST for r in complete)
    eligible_p = sum(r['price_outcome_hindsight']==PERSIST for r in eligible)
    def rate(a,b): return round(100*a/b,4) if b else None
    def med(rr,k):
        v=[number(r,k) for r in rr if number(r,k) is not None]
        return round(median(v),6) if v else None
    return dict(variant=variant,warnings=len(rows),complete=len(complete),missing=len(complete)-len(eligible),
                selected=len(selected),rejected=len(eligible)-len(selected),persistent=p,faded=c['TARGET_FADED'],
                no_excursion=c['NO_FEE_SCALE_EXCURSION'],persistent_pct=rate(p,len(selected)),
                comparable_baseline_pct=rate(eligible_p,len(eligible)),persistent_retained_pct=rate(p,total_p),
                stop_touched=sum(r['stop_touched_hindsight']=='True' for r in selected),
                entry_bar_stop=sum(r['entry_bar_stop_touched_hindsight']=='True' for r in selected),
                median_terminal=med(selected,'terminal_move_pct_hindsight'),
                median_prior6_move=med(selected,'prior6_target_move_pct'),
                selected_censored=sum(r['price_outcome_hindsight']=='CENSORED' and decisions(r)[variant] is True for r in rows))

def write(path,rows):
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    raw=SOURCE.read_bytes()
    with SOURCE.open(newline='') as f: all_rows=list(csv.DictReader(f))
    assert len(all_rows)==1837
    rows=[r for r in all_rows if r['target']=='SHORT' and r['rule']=='TWO_STEP']
    assert Counter(r['period'] for r in rows)=={'DISCOVERY':546,'NOVEMBER':82}
    assert len({(r['period'],r['signal_time']) for r in rows})==len(rows)
    groups=defaultdict(list)
    for r in rows:
        context=r['st_direction']+'/'+r['major_st']
        groups[r['period'],context].append(r)
        groups[r['period'],'ALL'].append(r)
    expected={'DISCOVERY':(90,18),'NOVEMBER':(18,8)}
    for period,(n,p) in expected.items():
        s=stats(groups[period,'LONG/SHORT'],'Q0'); assert (s['complete'],s['persistent'])==(n,p)
    results=[dict(period=period,context=context,**stats(rr,v)) for (period,context),rr in sorted(groups.items()) for v in RULES]
    audit=[dict(**r,**{v:('MISSING' if x is None else 'PASS' if x else 'FAIL') for v,x in decisions(r).items()}) for r in rows]
    report=dict(notes=['Observational only; both periods discovery; no trades, orders or strategy edits.',
        'Q0 all TWO_STEP SHORT warnings; Q1 E6>0; Q2 E12>0; Q3 both positive; Q4 E6>E12>0. Nested windows, not independent acceleration estimates.',
        'Missing features excluded explicitly; comparable baseline uses same available subset. Censored outcomes excluded from rates.',
        'Overlapping warning windows retained; no independent-trade or profitability inference. Static adverse touch is not a trailing-stop replay.',
        'Rules selected after inspecting discovery summaries; fresh validation required. No threshold sweep.'],
        source_sha256=hashlib.sha256(raw).hexdigest(),warnings=len(rows),focus=[r for r in results if r['context']=='LONG/SHORT'])
    OUT.mkdir(parents=True,exist_ok=False)
    write(OUT/'warning_decisions.csv',audit); write(OUT/'variant_comparison.csv',results)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__': main()
