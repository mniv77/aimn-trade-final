#!/usr/bin/env python3
"""EXP40-AL: descriptive screening only; no trading replay or production edits."""
import csv
import json
import math
import hashlib
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'kiss/results/exp40ak_relative_v_leg_forensics/v_leg_audit.csv'
OUT = ROOT / 'kiss/results/exp40al_trajectory_discrimination'
PERIODS = ('JUN_AUG', 'SEP_OCT', 'NOV')
FIELDS = ('AUTH_W6_retracement', 'AUTH_W12_retracement', 'AUTH_W12_left_efficiency')
OUTCOMES = ('WIN', 'NO_FEE_CLOSE', 'GIVEBACK')

def num(r, key):
    try:
        x = float(r[key])
        return x if math.isfinite(x) else None
    except (ValueError, TypeError):
        return None

def quantile(a, q):
    a = sorted(a)
    if not a:
        return None
    p = q*(len(a)-1)
    i = int(p)
    return round(a[i]+(a[min(i+1,len(a)-1)]-a[i])*(p-i), 6)

def distribution(rows, key):
    a = [num(r,key) for r in rows]
    a = [x for x in a if x is not None]
    return dict(n=len(a), missing=len(rows)-len(a), **{f'q{int(q*100):02d}':quantile(a,q) for q in (0,.25,.5,.75,1)})

def auc(rows, key, reverse=False):
    # WIN versus NO_FEE_CLOSE, with half credit for ties.
    a = [num(r,key) for r in rows if r['trade_outcome']=='WIN']
    b = [num(r,key) for r in rows if r['trade_outcome']=='NO_FEE_CLOSE']
    a,b = [x for x in a if x is not None],[x for x in b if x is not None]
    if not a or not b: return None
    return round(sum(0.5 if x==y else float(x<y if reverse else x>y) for x in a for y in b)/(len(a)*len(b)),6)

def assess(rows, conditions):
    groups = {s: [] for s in ('PASS','FAIL','MISSING')}
    for r in rows:
        vals = [num(r,k) for k,_,_ in conditions]
        if any(x is None for x in vals): status='MISSING'
        elif all(x>=t if op=='>=' else x<=t for x,(_,op,t) in zip(vals,conditions)): status='PASS'
        else: status='FAIL'
        groups[status].append(r)
    result={}
    for status,rr in groups.items():
        c=Counter(r['trade_outcome'] for r in rr)
        result[status]=dict(n=len(rr), **{k:c[k] for k in OUTCOMES}, net_sum_pct=round(sum(float(r['trade_net_pct']) for r in rr),6))
    return result

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    with SRC.open(newline='') as f: rows=list(csv.DictReader(f))
    assert len(rows)==174
    auth=[r for r in rows if r['status']=='AUTHORIZED']
    trades=[r for r in rows if r['trade_outcome'] in OUTCOMES]
    assert len(auth)==65 and len(trades)==58
    assert Counter(r['trade_outcome'] for r in trades)=={'WIN':25,'NO_FEE_CLOSE':25,'GIVEBACK':8}
    assert all(r['status']=='AUTHORIZED' and r['candidate_status']=='SCHEDULED' for r in trades)
    assert abs(sum(float(r['trade_net_pct']) for r in trades)+7.178589)<.00001
    assert len({(r['period'],r['warning_time']) for r in rows})==174
    # Fixed coarse diagnostic grid; never choose an optimum or deploy it.
    a,b,c=FIELDS
    variants=[]
    for t in (.3,.4,.5,.6,.7):
        variants.extend([('AL1',[(a,'>=',t)]),('AL2',[(b,'>=',t)]),('AL3',[(c,'<=',t)])])
    for t in (.4,.5,.6):
        variants.extend([('AL4',[(a,'>=',t),(b,'>=',t)]),('AL5',[(b,'>=',t),(c,'<=',.6)])])
    report=dict(source_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),notes=['All historical periods are discovery.','Trade subsets are descriptive, not executable replay; blocked/overlapping opportunities may change when entries are filtered.','Missing features are separate, not silently rejected.','AUC is pairwise WIN vs NO_FEE_CLOSE ranking, not probability of a winning trade.','Fixed diagnostic grid is not a selected rule.'], distributions={}, auc={}, screens=[])
    flat=[]
    for period in ('ALL',*PERIODS):
        rr=[r for r in trades if period=='ALL' or r['period']==period]
        report['distributions'][period]={o:{k:distribution([r for r in rr if r['trade_outcome']==o],k) for k in FIELDS} for o in OUTCOMES}
        report['auc'][period]={k:auc(rr,k,k==c) for k in FIELDS}
        print(period,'AUC',json.dumps(report['auc'][period]))
        for name,cond in variants:
            label=' & '.join(f'{k} {op} {t}' for k,op,t in cond)
            res=assess(rr,cond)
            report['screens'].append(dict(period=period,variant=name,conditions=cond,results=res))
            for status,stats in res.items(): flat.append(dict(period=period,variant=name,conditions=label,status=status,**stats))
            if period=='ALL':
                p,f,m=(res[s] for s in ('PASS','FAIL','MISSING'))
                print(name,label,'PASS W/N/G',p['WIN'],p['NO_FEE_CLOSE'],p['GIVEBACK'],'net',p['net_sum_pct'],'FAIL W/N',f['WIN'],f['NO_FEE_CLOSE'],'MISSING',m['n'])
    OUT.mkdir(parents=True,exist_ok=False)
    with (OUT/'screen_audit.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Saved:',OUT)

if __name__=='__main__': main()
