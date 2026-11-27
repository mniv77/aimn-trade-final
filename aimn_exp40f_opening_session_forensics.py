"""EXP40-F: read-only opening-session discovery audit; no orders or production writes."""
import csv
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'kiss/visual_research/aimn_nvda_candles.json'
SOURCE = ROOT / 'kiss/results/exp40e_adaptive_trajectory'
OUT = ROOT / 'kiss/results/exp40f_opening_session_forensics'
HASH = '020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50'

def read_csv(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))

def pct(a,b):
    return 100*(a/b-1)

def contiguous(rows, times, a, z):
    return a >= 0 and times[a].date() == times[z].date() and all(times[j]-times[j-1]==timedelta(minutes=5) for j in range(a+1,z+1))

def main():
    raw=DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=HASH: raise ValueError('Candle hash mismatch')
    rows=json.loads(raw)
    times=[datetime.fromisoformat(r['timestamp']) for r in rows]
    if len(rows)!=4680 or any(a>=b for a,b in zip(times,times[1:])): raise ValueError('Unexpected candle sequence')
    idx={r['timestamp']:i for i,r in enumerate(rows)}
    candidates=read_csv(SOURCE/'E0_D3_candidates.csv')
    trades=read_csv(SOURCE/'E0_D3_trades.csv')
    if len(candidates)!=135 or len(trades)!=64 or len({r['signal_time'] for r in candidates})!=135: raise ValueError('E0 count mismatch')
    if sum(float(r['net_pnl_pct'])>0 for r in trades)!=23 or abs(sum(float(r['net_pnl_pct']) for r in trades)+11.658255)>1e-6: raise ValueError('E0 outcome mismatch')
    earliest=[r for r in candidates if r['history_type']=='EARLIEST']
    lookup={r['signal_time']:r for r in trades}
    if len(earliest)!=28 or any(r['signal_time'] not in lookup for r in earliest): raise ValueError('Earliest candidate parity failed')
    c,o,h,l=([float(r[k]) for r in rows] for k in ('close','open','high','low'))
    starts=[]; s=0
    for i,t in enumerate(times):
        if i and t.date()!=times[i-1].date(): s=i
        starts.append(s)
    records=[]
    for candidate in earliest:
        tr=lookup[candidate['signal_time']]; i=idx[tr['signal_time']]; s=starts[i]; p=s-1
        current_ok=contiguous(rows,times,s,i) and times[s].strftime('%H:%M')=='09:30'
        prev_ok=p>=0 and times[p].strftime('%H:%M')=='15:55'
        f=dict(session_bar=i-s,prev_30m_return_pct=None,prev_60m_return_pct=None,prev_30m_eff=None,prev_60m_eff=None,overnight_gap_pct=None,prior_high_distance_pct=None,prior_low_distance_pct=None,prior_close_location=None,opening_move_pct=None,opening_high_pullback_pct=None,opening_range_pct=None,opening_close_location=None,signal_body_pct=pct(o[i],c[i]),signal_range_pct=pct(h[i],l[i]),signal_close_location=(c[i]-l[i])/(h[i]-l[i]) if h[i]>l[i] else None,gap_retracement_fraction=None)
        if current_ok:
            hh=max(h[s:i+1]); ll=min(l[s:i+1]); f.update(opening_move_pct=pct(c[i],o[s]),opening_high_pullback_pct=100*(1-c[i]/hh),opening_range_pct=pct(hh,ll),opening_close_location=(c[i]-ll)/(hh-ll) if hh>ll else None)
        if prev_ok:
            for n in (6,12):
                a=p-n+1
                if contiguous(rows,times,a,p):
                    rr=[pct(c[a],o[a])]+[pct(c[j],c[j-1]) for j in range(a+1,p+1)]
                    path=sum(abs(v) for v in rr)
                    f[f'prev_{n*5}m_return_pct']=pct(c[p],o[a]); f[f'prev_{n*5}m_eff']=sum(rr)/path if path else 0.
            ps=starts[p]
            if contiguous(rows,times,ps,p) and times[ps].strftime('%H:%M')=='09:30':
                ph=max(h[ps:p+1]); pl=min(l[ps:p+1]); f.update(prior_high_distance_pct=pct(c[i],ph),prior_low_distance_pct=pct(c[i],pl),prior_close_location=(c[p]-pl)/(ph-pl) if ph>pl else None)
            if current_ok:
                f['overnight_gap_pct']=pct(o[s],c[p]); gap=o[s]-c[p]
                f['gap_retracement_fraction']=(o[s]-c[i])/gap if gap else None
        net=float(tr['net_pnl_pct']); best=float(tr['best_close_pct']); fee=float(tr['commission_pct'])
        records.append(dict(**tr,split='AUG' if times[i].month==8 else 'JUN_JUL',outcome='WINNER' if net>0 else 'LOSS_CLOSE_ABOVE_FEE' if best>fee else 'LOSS_CLOSE_NOT_ABOVE_FEE',**f))
    if sum(float(r['net_pnl_pct'])>0 for r in records)!=7 or abs(sum(float(r['net_pnl_pct']) for r in records)+4.215482)>1e-6: raise ValueError('Opening outcome parity failed')
    features=list(f)
    comparison=[]; groups=[]
    for split in ('ALL','JUN_JUL','AUG'):
        subset=[r for r in records if split=='ALL' or r['split']==split]
        for outcome in ('WINNER','LOSER','LOSS_CLOSE_ABOVE_FEE','LOSS_CLOSE_NOT_ABOVE_FEE'):
            g=[r for r in subset if (r['outcome']!='WINNER' if outcome=='LOSER' else r['outcome']==outcome)]
            groups.append(dict(split=split,outcome=outcome,trades=len(g),net_sum_pct=round(sum(float(r['net_pnl_pct']) for r in g),6)))
            for name in features:
                values=[r[name] for r in g if r[name] is not None]
                comparison.append(dict(split=split,outcome=outcome,feature=name,trades=len(g),available=len(values),mean=mean(values) if values else None,median=median(values) if values else None))
    report=dict(data_sha256=HASH,source_hashes={name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in ('E0_D3_candidates.csv','E0_D3_trades.csv')},opening_trades=28,winners=7,losers=21,groups=groups,notes=['Discovery only; no new gate or policy replay.','Features end at completed signal candle; prior-session data only from earlier dates.','Prior session must end at 15:55; missing history retained as null.','Gap retracement is signed relative to opening gap; not clipped.','Small samples and missing features limit inference.'])
    OUT.mkdir(parents=True,exist_ok=False)
    for name,data in [('opening_forensics.csv',records),('feature_comparison.csv',comparison)]:
        with (OUT/name).open('x',newline='') as fp:
            w=csv.DictWriter(fp,fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
