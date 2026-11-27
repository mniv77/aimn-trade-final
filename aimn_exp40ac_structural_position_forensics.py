#!/usr/bin/env python3
"""EXP40-AC: causal structural descriptors, retrospective outcomes; no trading."""
import csv, json, hashlib
from pathlib import Path
from collections import Counter, defaultdict
from statistics import median
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'kiss/visual_research/independent_holdout_exp127/nvda_sep_oct_2026_5m_iex.json'
AB=ROOT/'kiss/results/exp40ab_historical_robustness'
OUT=ROOT/'kiss/results/exp40ac_structural_position_forensics'
DIGEST='3e944cd4cdeba1adb650804a0a3e81d5355c225d9ad05546176b1de8ef9e9718'

def read(p):
    with p.open(newline='') as f: return list(csv.DictReader(f))
def write(p,rr):
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0])); w.writeheader(); w.writerows(rr)
def pct(a,b): return 100*(b/a-1)
def short(a,b): return -pct(a,b)
def structure(day,i):
    # Strict two-sided pivots become available only after two subsequent closes.
    # Ambiguous outside bars and ties are not pivots.
    piv=[]
    for j in range(2,i-1):
        q=day[j]; neighbors=day[j-2:j]+day[j+1:j+3]
        hi=all(q['high']>x['high'] for x in neighbors)
        lo=all(q['low']<x['low'] for x in neighbors)
        if hi==lo: continue
        kind='H' if hi else 'L'; price=q['high' if hi else 'low']
        p=(kind,j,price)
        if piv and piv[-1][0]==kind:
            if (price>piv[-1][2] if hi else price<piv[-1][2]): piv[-1]=p
        else: piv.append(p)
    return piv

def analyze(day,i,c,trade):
    q=day[i]; price=q['close']; piv=structure(day,i)
    highs=[p for p in piv if p[0]=='H']; lows=[p for p in piv if p[0]=='L']
    h=highs[-1] if highs else None; l=lows[-1] if lows else None
    hh=pct(highs[-2][2],h[2]) if len(highs)>=2 else None
    ll=pct(lows[-2][2],l[2]) if len(lows)>=2 else None
    pattern='UNKNOWN' if hh is None or ll is None else 'LOWER_HIGH_LOWER_LOW' if hh<0 and ll<0 else 'HIGHER_HIGH_HIGHER_LOW' if hh>0 and ll>0 else 'MIXED'
    a=max(0,i-11); peak=max(range(a,i+1),key=lambda j:(day[j]['high'],j)); trough=min(range(a,i+1),key=lambda j:(day[j]['low'],-j))
    top=day[peak]['high']; bottom=day[trough]['low']
    r=dict(c,trade_outcome='UNTRADED',trade_net_pct=None,trade_best_close_pct=None,trade_exit_reason=None,
        pivot_pattern=pattern,pivot_sequence=''.join(p[0] for p in piv[-4:]),confirmed_pivots=len(piv),
        latest_high_time=day[h[1]]['timestamp'] if h else None,latest_high_confirmed_bar=day[h[1]+2]['timestamp'] if h else None,
        latest_low_time=day[l[1]]['timestamp'] if l else None,latest_low_confirmed_bar=day[l[1]+2]['timestamp'] if l else None,
        latest_high_price=h[2] if h else None,latest_low_price=l[2] if l else None,
        high_change_pct=hh,low_change_pct=ll,confirmed_high_age=i-h[1] if h else None,
        confirmed_high_decline_pct=short(h[2],price) if h else None,
        below_confirmed_low_pct=short(l[2],price) if l else None,
        recent12_peak_age=i-peak,recent12_peak_decline_pct=short(top,price),
        recent12_range_position=(price-bottom)/(top-bottom) if top>bottom else None,
        recent12_trough_age=i-trough,prior3_decline_pct=short(day[i-3]['close'],price) if i>=3 else None,
        prior6_decline_pct=short(day[i-6]['close'],price) if i>=6 else None,
        next_open_hindsight=None,first_close_move_hindsight=None,favorable_hindsight=None,adverse_hindsight=None,terminal_hindsight=None,price_outcome_hindsight='CENSORED')
    if trade:
        net=float(trade['net_pnl_pct']); best=float(trade['best_close_pct'])
        r.update(trade_outcome='WIN' if net>0 else 'GIVEBACK' if best>.2 else 'NO_FEE_CLOSE',trade_net_pct=net,trade_best_close_pct=best,trade_exit_reason=trade['exit_reason'])
    if i+6<len(day):
        f=day[i+1:i+7]; e=f[0]['open']; fav=max([0]+[short(e,z['low']) for z in f]); adv=min([0]+[short(e,z['high']) for z in f]); terminal=short(e,f[-1]['close']); n=sum(short(e,z['close'])>.2 for z in f)
        r.update(next_open_hindsight=e,first_close_move_hindsight=short(e,f[0]['close']),favorable_hindsight=fav,adverse_hindsight=adv,terminal_hindsight=terminal,price_outcome_hindsight='PERSISTENT_TARGET' if terminal>.2 and n>=4 else 'TARGET_FADED' if fav>.2 else 'NO_FEE_SCALE_EXCURSION')
    return r

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    raw=SRC.read_bytes(); assert hashlib.sha256(raw).hexdigest()==DIGEST
    rows=json.loads(raw); days=defaultdict(list)
    for r in rows: days[r['timestamp'][:10]].append(r)
    assert len(rows)==3354 and len(days)==43 and all(len(d)==78 for d in days.values())
    index={r['timestamp']:(day,i) for day in days.values() for i,r in enumerate(day)}
    c=read(AB/'AB1_candidates.csv'); trades=read(AB/'AB1_trades.csv'); lookup={r['signal_time']:r for r in trades}
    assert len(c)==54 and len({r['signal_time'] for r in c})==54 and len(lookup)==13
    assert set(lookup)=={r['signal_time'] for r in c if r['status']=='SCHEDULED'}
    assert round(sum(float(r['net_pnl_pct']) for r in trades),6)==-2.369424
    audit=[analyze(*index[r['signal_time']],r,lookup.get(r['signal_time'])) for r in c]
    groups=defaultdict(list)
    for r in audit:
        groups['TRADE',r['trade_outcome']].append(r); groups['PRICE_PROXY',r['price_outcome_hindsight']].append(r); groups['STRUCTURE',r['pivot_pattern']].append(r)
    summaries=[]
    keys=('e6','e12','high_change_pct','low_change_pct','confirmed_high_age','confirmed_high_decline_pct','below_confirmed_low_pct','recent12_peak_age','recent12_peak_decline_pct','recent12_range_position','recent12_trough_age','prior3_decline_pct','prior6_decline_pct')
    for (kind,label),rr in sorted(groups.items()):
        rec=dict(group=kind,label=label,count=len(rr),trade_outcomes=dict(Counter(r['trade_outcome'] for r in rr)),price_outcomes=dict(Counter(r['price_outcome_hindsight'] for r in rr)),features={})
        for k in keys:
            vals=[float(r[k]) for r in rr if r[k] not in ('',None)]; rec['features'][k]=dict(available=len(vals),median=round(median(vals),6) if vals else None)
        summaries.append(rec)
    assert Counter(r['trade_outcome'] for r in audit)=={'WIN':4,'NO_FEE_CLOSE':8,'GIVEBACK':1,'UNTRADED':41}
    report=dict(notes=['September–October now discovery for this analysis. No new entry rule, replay or orders.', 'All 54 focus candidates including blocked and rejected. Six-bar price proxies are not trade outcomes; overlapping windows are dependent.', 'Pivots strict two bars either side, confirmed only after second right bar closes; ties and outside bars excluded; consecutive same-kind pivots compressed to more extreme. Session reset. No optimization.', 'Recent12 uses up to 12 completed candles including signal. Returns in proxy use simple price change, not engine trade formula.'],source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [SRC,AB/'AB1_candidates.csv',AB/'AB1_trades.csv']},groups=summaries)
    OUT.mkdir(parents=True,exist_ok=False); write(OUT/'candidate_structural_audit.csv',audit); (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(candidates=len(audit),trade_outcomes=dict(Counter(r['trade_outcome'] for r in audit)),price_outcomes=dict(Counter(r['price_outcome_hindsight'] for r in audit)),structure_groups=[{k:v for k,v in g.items() if k!='features'} for g in summaries if g['group']=='STRUCTURE'],trade_feature_medians={g['label']:g['features'] for g in summaries if g['group']=='TRADE' and g['label']!='UNTRADED'}),indent=2,allow_nan=False))
if __name__=='__main__': main()
