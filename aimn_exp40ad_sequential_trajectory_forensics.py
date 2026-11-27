#!/usr/bin/env python3
"""EXP40-AD: descriptive sequential trajectory research; no replay or orders."""
import json, hashlib
from collections import Counter, defaultdict
from statistics import median
from datetime import datetime
from pathlib import Path
import aimn_exp40ac_structural_position_forensics as ac
ROOT=Path(__file__).resolve().parent
R=ROOT/'kiss/results'; D=ROOT/'kiss/visual_research'
OUT=R/'exp40ad_sequential_trajectory_forensics'
AA=R/'exp40aa_reverse_transition_replay'; AB=ac.AB
SETS=[('JUN_AUG',D/'aimn_nvda_candles.json','020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50',4680,AA/'DISCOVERY_AA1_candidates.csv',AA/'DISCOVERY_AA1_trades.csv',93,16,-.152856),('SEP_OCT',ac.SRC,ac.DIGEST,3354,AB/'AB1_candidates.csv',AB/'AB1_trades.csv',54,13,-2.369424),('NOV',D/'independent_holdout_exp40l/nvda_2026-11-16_2026-11-25_5m_iex.json','eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d',624,AA/'NOVEMBER_AA1_candidates.csv',AA/'NOVEMBER_AA1_trades.csv',19,2,1.216933)]

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def phases(day,i):
    out={}; blocks=[]
    for label,offset in [('A',9),('B',6),('C',3)]:
        start=i-offset; end=start+3
        vals=dict(velocity=None,efficiency=None,range_pct=None,high=None,low=None)
        if start>=0:
            bars=day[start:end+1]
            assert all((datetime.fromisoformat(b['timestamp'])-datetime.fromisoformat(a['timestamp'])).total_seconds()==300 for a,b in zip(bars,bars[1:]))
            c=[r['close'] for r in bars]; steps=[b-a for a,b in zip(c,c[1:])]; den=sum(map(abs,steps))
            # Movement uses four closes; high/low range uses the three destination bars only.
            hi=max(r['high'] for r in bars[1:]); lo=min(r['low'] for r in bars[1:])
            vals=dict(velocity=ac.short(c[0],c[-1])/3,efficiency=-sum(steps)/den if den else 0.,range_pct=100*(hi-lo)/c[0],high=hi,low=lo)
        blocks.append(vals); out.update({f'{label}_{k}':v for k,v in vals.items()})
    for label,a,b in [('BA',blocks[0],blocks[1]),('CB',blocks[1],blocks[2])]:
        for k in a:
            out[f'{label}_delta_{k}']=None if a[k] is None or b[k] is None else (ac.pct(a[k],b[k]) if k in ('high','low') else b[k]-a[k])
    v=[x['velocity'] for x in blocks]; out['phase_pattern']='MISSING' if None in v else '/'.join('SHORT' if x>0 else 'LONG' if x<0 else 'FLAT' for x in v)
    out['latest_phase_change']='MISSING' if None in v[1:] else 'LONG_TO_SHORT' if v[1]<=0<v[2] else 'SHORT_TO_NONSHORT' if v[2]<=0<v[1] else 'SHORT_STRENGTHENING' if v[2]>v[1]>0 else 'SHORT_NOT_STRENGTHENING' if v[1]>0 and v[2]>0 else 'NONSHORT'
    return out

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    audit=[]; hashes={}
    for period,src,sha,n,cp,tp,nc,nt,net in SETS:
        assert digest(src)==sha
        for p in (src,cp,tp): hashes[str(p.relative_to(ROOT))]=digest(p)
        rows=json.loads(src.read_bytes()); assert len(rows)==n
        stamps=[r['timestamp'] for r in rows]; assert stamps==sorted(set(stamps))
        days=defaultdict(list)
        for r in rows: days[r['timestamp'][:10]].append(r)
        assert all(len(d)==78 and d[0]['timestamp'][11:16]=='09:30' and d[-1]['timestamp'][11:16]=='15:55' for d in days.values())
        idx={r['timestamp']:(d,i) for d in days.values() for i,r in enumerate(d)}
        candidates=ac.read(cp); trades=ac.read(tp); lookup={r['signal_time']:r for r in trades}
        assert len(candidates)==nc and len({r['signal_time'] for r in candidates})==nc
        assert len(lookup)==len(trades)==nt and round(sum(float(r['net_pnl_pct']) for r in trades),6)==net
        assert set(lookup)<=set(r['signal_time'] for r in candidates)
        for c in candidates:
            day,i=idx[c['signal_time']]; row=ac.analyze(day,i,c,lookup.get(c['signal_time']))
            audit.append(dict(period=period,**row,**phases(day,i)))
    assert len(audit)==166
    # Candidate files share a schema, but preserve any additional fields safely.
    fields=list(dict.fromkeys(k for r in audit for k in r)); audit=[{k:r.get(k) for k in fields} for r in audit]
    keys=[k for k in phases([],0) if k not in ('phase_pattern','latest_phase_change')]
    groups=defaultdict(list)
    for r in audit:
        for p in (r['period'],'ALL'):
            for kind,key in [('TRADE','trade_outcome'),('PRICE','price_outcome_hindsight'),('PHASE','latest_phase_change'),('PATTERN','phase_pattern')]: groups[p,kind,r[key]].append(r)
    report=[]
    for (p,kind,label),rr in sorted(groups.items()):
        rec=dict(period=p,group=kind,label=label,count=len(rr),trade_outcomes=dict(Counter(r['trade_outcome'] for r in rr)),price_outcomes=dict(Counter(r['price_outcome_hindsight'] for r in rr)),features={})
        for k in keys:
            vals=[r[k] for r in rr if r[k] is not None]; rec['features'][k]=dict(available=len(vals),median=round(median(vals),6) if vals else None)
        report.append(rec)
    summary=dict(notes=['All periods discovery; no filters or replay. Positive velocity denotes SHORT; percentage points per five-minute interval. Each phase uses three consecutive close changes; adjacent phases share endpoint only. High/low ranges use disjoint destination bars. Missing history stays missing.','Six-bar price proxy is retrospective, not executable P&L. Overlapping candidate outcomes are dependent. Trade labels use frozen AA1/AB1 only.'],source_hashes=hashes,groups=report)
    OUT.mkdir(parents=True,exist_ok=False); ac.write(OUT/'candidate_phase_audit.csv',audit); (OUT/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    compact=[{k:v for k,v in r.items() if k!='features'} for r in report if r['group']=='PHASE']
    med=[dict(period=r['period'],label=r['label'],count=r['count'],features={k:r['features'][k] for k in ('A_velocity','B_velocity','C_velocity','BA_delta_velocity','CB_delta_velocity','A_efficiency','B_efficiency','C_efficiency')}) for r in report if r['period']=='ALL' and r['group']=='TRADE' and r['label']!='UNTRADED']
    print(json.dumps(dict(candidates=len(audit),trade_outcomes=dict(Counter(r['trade_outcome'] for r in audit)),phase_groups=compact,trade_medians=med),indent=2,allow_nan=False))
if __name__=='__main__': main()
