#!/usr/bin/env python3
"""EXP40-T: observational opening warning policies; no orders or engine edits."""
import csv
import json
import hashlib
from collections import Counter
from statistics import median
import aimn_exp40s_opening_trajectory_forensics as s

ROOT=s.ROOT
SOURCE=s.OUT/'opening_warning_audit.csv'
OUT=ROOT/'kiss/results/exp40t_opening_selectivity'
RULES=('T0','T1','T2')

def read(path):
    with path.open(newline='') as f: return list(csv.DictReader(f))

def recovery(rows, previous, current):
    # Require a completed bullish close-to-close move above the previous
    # warning candle high, strictly between the two warnings.
    if previous is None: return None
    high=float(rows[previous]['high'])
    return next((rows[j]['timestamp'] for j in range(previous+1,current)
                 if float(rows[j]['close'])>high and
                 float(rows[j]['close'])>float(rows[j-1]['close'])),None)

def stats(rows,rule):
    selected=[r for r in rows if r[rule]=='PASS']
    c=Counter(r['price_outcome_hindsight'] for r in selected)
    p=c['PERSISTENT_TARGET']; total=sum(r['price_outcome_hindsight']=='PERSISTENT_TARGET' for r in rows)
    return dict(variant=rule,observations=len(rows),selected=len(selected),persistent=p,
                faded=c['TARGET_FADED'],no_excursion=c['NO_FEE_SCALE_EXCURSION'],
                persistence_pct=round(100*p/len(selected),4) if selected else None,
                retained_pct=round(100*p/total,4) if total else None,
                stop_touched=sum(r['stop_touched_hindsight']=='True' for r in selected),
                entry_bar_stop=sum(r['entry_bar_stop_touched_hindsight']=='True' for r in selected),
                median_terminal_pct=round(median(float(r['terminal_move_pct_hindsight']) for r in selected),6) if selected else None)

def main():
    raw=SOURCE.read_bytes(); audit=read(SOURCE); warnings=read(s.SOURCE)
    assert hashlib.sha256(s.SOURCE.read_bytes()).hexdigest()=='05d885fa55df7237001662cdc67e078aad43669c494c4bcdf195bd19c877cf2d'
    assert len(audit)==24 and len(warnings)==628
    lookup={(r['period'],r['signal_time']):r for r in audit}
    assert len(lookup)==24
    result=[]
    for period,spec in s.DATA.items():
        rows=s.read_data(spec)
        if period=='NOVEMBER': rows=s.read_data(s.WARM)+rows
        idx={r['timestamp']:i for i,r in enumerate(rows)}
        last={}; counts=Counter()
        for w in sorted((r for r in warnings if r['period']==period and r['st_direction']=='LONG' and r['major_st']=='SHORT'),key=lambda r:r['signal_time']):
            t=w['signal_time']; day=t[:10]; i=idx[t]; prev=last.get(day)
            counts[day]+=1
            if (period,t) in lookup:
                r=lookup[period,t]
                assert w['Q4']=='MISSING' and int(r['focus_warning_number'])==counts[day]
                assert r['price_outcome_hindsight']==w['price_outcome_hindsight']!='CENSORED'
                reset=recovery(rows,prev,i); first=prev is None
                result.append(dict(**r,previous_focus_warning=rows[prev]['timestamp'] if prev is not None else None,
                    recovery_confirmation_time=reset,T0='PASS',T1='PASS' if first else 'FAIL',
                    T2='PASS' if first or reset is not None else 'FAIL'))
            last[day]=i
    assert len(result)==24
    groups=[dict(period=p,**stats(rr,v)) for p in ('DISCOVERY','NOVEMBER','COMBINED')
            for rr in [[r for r in result if p=='COMBINED' or r['period']==p]] for v in RULES]
    assert [(g['selected'],g['persistent']) for g in groups if g['period']=='COMBINED' and g['variant'] in ('T0','T1')]==[(24,8),(14,6)]
    report=dict(notes=['Observational only; both periods discovery; no trades or orders.',
        'T0 all missing-history focus warnings; T1 first focus warning of session; T2 first or recovery since immediately preceding focus warning.',
        'Recovery proxy: an intervening completed close above previous warning high and above its own preceding close. No future bars or outcome inputs. No threshold optimization.',
        'Previous warnings include all focus warnings regardless of Q4 status. Recovery is a provisional proxy, not proof of new major transition.',
        'Overlapping horizons; static adverse touch is not a stop replay. Q4 unchanged.'],
        source_sha256=hashlib.sha256(raw).hexdigest(),groups=groups,
        recovered=[{k:r[k] for k in ('period','signal_time','previous_focus_warning','recovery_confirmation_time','price_outcome_hindsight')} for r in result if r['T2']=='PASS' and r['T1']=='FAIL'])
    OUT.mkdir(parents=True,exist_ok=False)
    s.write(OUT/'opening_decisions.csv',result); s.write(OUT/'variant_comparison.csv',groups)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__': main()
