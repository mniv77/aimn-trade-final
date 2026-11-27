"""EXP40-AH: observational AE3 warning comparison; no trading or tuning."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'kiss/results/exp40ag_early_warning_discrimination/warning_feature_audit.csv'
OUT = ROOT / 'kiss/results/exp40ah_quantitative_discrimination'
PERIODS = {'JUN_AUG': (104, 92, 16), 'SEP_OCT': (57, 47, 8), 'NOV': (13, 12, 6), 'ALL': (174, 151, 30)}
VARIANTS = ('AH0','AH1','AH2','AH3','AH4','AH5')

def number(r, k):
    v = r[k]
    if v in ('', None):
        return None
    x = float(v)
    if not math.isfinite(x):
        raise ValueError((k,v))
    return x

def decisions(r):
    a,b,c = (number(r,k) for k in ('rsi_delta3','st5_delta3','signal_break_prior_low'))
    assert c in (None,0,1)
    def combine(*flags):
        return 'MISSING' if None in flags else 'PASS' if all(flags) else 'FAIL'
    x = None if a is None else a < 0
    y = None if b is None else b < 0
    z = None if c is None else c == 1
    return dict(AH0='PASS',AH1=combine(x),AH2=combine(y),AH3=combine(z),AH4=combine(x,y),AH5=combine(x,y,z))

def rate(n,d):
    return round(100*n/d,3) if d else None

def med(rows,k):
    vals = [number(r,k) for r in rows]
    vals = [v for v in vals if v is not None]
    return round(median(vals),6) if vals else None

def stats(rows):
    outcomes = Counter(r['price_outcome_hindsight'] for r in rows)
    matches = Counter(r['two_step_match'] for r in rows)
    complete = [r for r in rows if r['price_outcome_hindsight'] != 'CENSORED']
    known = matches['EARLIER'] + matches['NO_LATER_TWO_STEP']
    return dict(warnings=len(rows),complete=len(complete),persistent=outcomes['PERSISTENT_TARGET'],
                persistent_pct=rate(outcomes['PERSISTENT_TARGET'],len(complete)),
                no_fee_excursion=outcomes['NO_FEE_SCALE_EXCURSION'],faded=outcomes['TARGET_FADED'],
                censored=outcomes['CENSORED'],earlier=matches['EARLIER'],unmatched=matches['NO_LATER_TWO_STEP'],
                matching_censored=matches['CENSORED'],confirmation_pct=rate(matches['EARLIER'],known),
                median_favorable=med(complete,'favorable_hindsight'),median_adverse=med(complete,'adverse_hindsight'),
                median_terminal=med(complete,'terminal_hindsight'),median_peak_to_entry=med(rows,'peak_to_next_open_pct'))

def write(path, rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    raw=SRC.read_bytes()
    with SRC.open(newline='') as f: rows=list(csv.DictReader(f))
    assert hashlib.sha256(SRC.read_bytes()).digest()==hashlib.sha256(raw).digest()
    assert len(rows)==174 and all(r['detector']=='AE3' and r['context']=='LONG/SHORT' for r in rows)
    assert len({(r['period'],r['signal_time']) for r in rows})==174
    assert Counter(r['two_step_match'] for r in rows)=={'EARLIER':85,'NO_LATER_TWO_STEP':72,'CENSORED':17}
    assert Counter(r['price_outcome_hindsight'] for r in rows)=={'PERSISTENT_TARGET':30,'NO_FEE_SCALE_EXCURSION':64,'TARGET_FADED':57,'CENSORED':23}
    audit=[dict(r,**decisions(r)) for r in rows]
    results=[]
    for period,expected in PERIODS.items():
        group=[r for r in audit if period=='ALL' or r['period']==period]
        baseline=stats(group)
        assert (baseline['warnings'],baseline['complete'],baseline['persistent'])==expected
        for name in VARIANTS:
            selected=[r for r in group if r[name]=='PASS']
            rejected=[r for r in group if r[name]=='FAIL']
            missing=[r for r in group if r[name]=='MISSING']
            s,rej,mis=map(stats,(selected,rejected,missing))
            rec=dict(period=period,variant=name,**s,rejected=len(rejected),missing=len(missing),
                     persistent_retained_pct=rate(s['persistent'],baseline['persistent']),
                     persistent_rejected=rej['persistent'],persistent_missing=mis['persistent'],
                     no_fee_rejected=rej['no_fee_excursion'],no_fee_missing=mis['no_fee_excursion'],
                     no_fee_rejected_pct=rate(rej['no_fee_excursion'],baseline['no_fee_excursion']))
            results.append(rec)
    report=dict(notes=['All periods are discovery. No orders, replay or production changes.',
                       'Conditions use only signal-time features. Missing inputs excluded and reported separately.',
                       'Six-bar price proxies and later TWO_STEP confirmation are retrospective, not trade P&L.',
                       'Overlapping warnings are dependent. No threshold search or statistical significance claim.',
                       'AH2 measures change in ATR-normalized boundary distance, not absolute price distance.'],
                source_sha256=hashlib.sha256(raw).hexdigest(),results=results)
    OUT.mkdir(parents=True,exist_ok=False)
    write(OUT/'warning_decisions.csv',audit); write(OUT/'variant_comparison.csv',results)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('PERIOD   RULE WARN FULL PERSIST RATE% LOST MISS NOFEE_REJ CONF% MED_TERM')
    for r in results:
        print(r['period'],r['variant'],r['warnings'],r['complete'],r['persistent'],r['persistent_pct'],r['persistent_rejected'],r['persistent_missing'],r['no_fee_rejected'],r['confirmation_pct'],r['median_terminal'])
    print('Saved:',OUT)

if __name__=='__main__': main()
