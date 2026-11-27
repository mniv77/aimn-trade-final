#!/usr/bin/env python3
"""EXP40-AK: descriptive causal V-leg features; no strategy changes."""
import csv, json, hashlib
from pathlib import Path
from collections import Counter, defaultdict
from statistics import median
from datetime import datetime
ROOT=Path(__file__).resolve().parent
R=ROOT/'kiss/results'; D=ROOT/'kiss/visual_research'
AJ=R/'exp40aj_transition_monitoring_replay'; OUT=R/'exp40ak_relative_v_leg_forensics'
HASHES={'aimn_exp40ai_early_transition_replay.py':'a2af1e958a26bfd7696216180b4d8c7b4339de7f62126f27ffb6e3d3376aae65','aimn_exp40aj_transition_monitoring_replay.py':'b6dc48d9f33b59f4f2ea6f388357d1ddb34138ba80dfec3649f5043f74f9a05f'}
SETS=[('JUN_AUG','aimn_nvda_candles.json','020dd41d6a023f236d5bd62e38b98dc2e141a3761280c69aec7ec1c58f0d8f50',4680,104,38,34,-4.827365),('SEP_OCT','independent_holdout_exp127/nvda_sep_oct_2026_5m_iex.json','3e944cd4cdeba1adb650804a0a3e81d5355c225d9ad05546176b1de8ef9e9718',3354,57,20,17,-.243471),('NOV','independent_holdout_exp40l/nvda_2026-11-16_2026-11-25_5m_iex.json','eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d',624,13,7,7,-2.107753)]

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    with p.open(newline='') as f: return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def efficiency(prices,direction):
    steps=[b-a for a,b in zip(prices,prices[1:])]; den=sum(map(abs,steps))
    return direction*sum(steps)/den if den else None

def features(day,p,c,n):
    # Fixed full window preceding the peak; never cross a session boundary.
    keys=('origin_time','rise_pct','fall_pct','left_bars','right_bars','left_velocity','right_velocity','retracement','velocity_ratio','left_efficiency','right_efficiency')
    out=dict.fromkeys(keys)
    if p<n or c<=p: return out
    a=min(range(p-n,p),key=lambda i:(day[i]['low'],-i))
    low=day[a]['low']; peak=day[p]['high']; close=day[c]['close']
    rise=peak-low; fall=peak-close
    lv=100*rise/low/(p-a); rv=100*fall/peak/(c-p)
    out.update(origin_time=day[a]['timestamp'],rise_pct=100*rise/low,fall_pct=100*fall/peak,left_bars=p-a,right_bars=c-p,left_velocity=lv,right_velocity=rv,retracement=fall/rise if rise>0 else None,velocity_ratio=rv/lv if lv>0 else None,left_efficiency=efficiency([r['close'] for r in day[a:p+1]],1),right_efficiency=efficiency([r['close'] for r in day[p:c+1]],-1))
    return out

def proxy(day,i):
    if i+6>=len(day): return 'CENSORED'
    future=day[i+1:i+7]; e=future[0]['open']; short=lambda z:100*(1-z/e)
    if short(future[-1]['close'])>.2 and sum(short(z['close'])>.2 for z in future)>=4: return 'PERSISTENT_TARGET'
    return 'TARGET_FADED' if max(short(z['low']) for z in future)>.2 else 'NO_FEE_SCALE_EXCURSION'

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    for name,h in HASHES.items(): assert digest(ROOT/name)==h,name
    audit=[]; hashes={}
    for period,rel,h,n,nw,na,nt,net in SETS:
        src=D/rel; assert digest(src)==h
        rows=json.loads(src.read_bytes()); assert len(rows)==n
        assert [r['timestamp'] for r in rows]==sorted({r['timestamp'] for r in rows})
        days=defaultdict(list)
        for r in rows: days[r['timestamp'][:10]].append(r)
        assert all(len(d)==78 and all((datetime.fromisoformat(b['timestamp'])-datetime.fromisoformat(a['timestamp'])).total_seconds()==300 for a,b in zip(d,d[1:])) for d in days.values())
        index={r['timestamp']:(d,i) for d in days.values() for i,r in enumerate(d)}
        paths={s:AJ/f'{period}_AJ1_{s}.csv' for s in ('warnings','candidates','trades')}
        w,c,t=(read(paths[s]) for s in ('warnings','candidates','trades'))
        hashes.update({str(p.relative_to(ROOT)):digest(p) for p in [src,*paths.values()]})
        cm={z['warning_time']:z for z in c}; tm={z['signal_time']:z for z in t}
        assert len(w)==nw and len({z['warning_time'] for z in w})==nw and len(c)==len(cm)==na and len(t)==len(tm)==nt
        assert set(cm)=={z['warning_time'] for z in w if z['status']=='AUTHORIZED'}
        assert set(tm)=={z['signal_time'] for z in c if z['status']=='SCHEDULED'}
        assert round(sum(float(z['net_pnl_pct']) for z in t),6)==net
        for z in w:
            stamp=z['warning_time']; day,i=index[stamp]; p=i-1; assert p>=0 and day[p]['high']==float(z['original_peak'])
            cand=cm.get(stamp); tr=tm.get(cand['signal_time']) if cand else None
            rec=dict(period=period,**z,candidate_status=cand['status'] if cand else '',trade_outcome='UNTRADED',trade_net_pct=None,trade_best_close_pct=None,warning_price_proxy=proxy(day,i),authorization_price_proxy=None)
            if tr:
                val=float(tr['net_pnl_pct']); best=float(tr['best_close_pct']); rec.update(trade_outcome='WIN' if val>0 else 'GIVEBACK' if best>.2 else 'NO_FEE_CLOSE',trade_net_pct=val,trade_best_close_pct=best)
            j=None
            if cand:
                assert cand['signal_time']==z['resolution_time']; dd,j=index[cand['signal_time']]; assert dd is day and j==i+1
                rec['authorization_price_proxy']=proxy(day,j)
            for label,pos in [('WARNING',i),('AUTH',j)]:
                for win in (6,12,24):
                    f=features(day,p,pos,win) if pos is not None else dict.fromkeys(features(day,p,i,win))
                    rec.update({f'{label}_W{win}_{key}':val for key,val in f.items()})
            audit.append(rec)
    assert len(audit)==174 and Counter(r['trade_outcome'] for r in audit)=={'WIN':25,'GIVEBACK':8,'NO_FEE_CLOSE':25,'UNTRADED':116}
    assert Counter(r['status'] for r in audit)=={'AUTHORIZED':65,'EXPIRED':61,'PEAK_INVALIDATED':22,'SESSION_OR_CUTOFF':25,'MAJOR_CONTEXT_LOST':1}
    groups=[]
    for period in ('ALL','JUN_AUG','SEP_OCT','NOV'):
        pool=[r for r in audit if period=='ALL' or r['period']==period]
        for field in ('trade_outcome','status','warning_price_proxy','authorization_price_proxy'):
            for label in sorted({r[field] for r in pool if r[field] is not None}):
                rr=[r for r in pool if r[field]==label]; rec=dict(period=period,group=field,label=label,count=len(rr),features={})
                for key in audit[0]:
                    if not key.startswith(('WARNING_W','AUTH_W')) or key.endswith('origin_time'): continue
                    vals=[r[key] for r in rr if r[key] is not None]; rec['features'][key]=dict(available=len(vals),median=round(median(vals),6) if vals else None)
                groups.append(rec)
    OUT.mkdir(parents=True,exist_ok=False); write(OUT/'v_leg_audit.csv',audit)
    report=dict(notes=['All periods discovery. No thresholds or replay.', 'Peak is original AE3 preceding high. Origin is lowest low among exactly N earlier same-session candles, latest tie. Full windows only.', 'Magnitude uses wick extrema and decision close; efficiency uses closes, not assumed intrabar paths. Ratios are proxies, not proof of genuine reversal.', 'Authorization features only for authorized warnings; retrospective price proxies use next open and six subsequent bars; not executable outcomes.'],source_hashes={**HASHES,**hashes},groups=groups)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Warnings',len(audit),'authorized',sum(r['status']=='AUTHORIZED' for r in audit),'trades',sum(r['trade_outcome']!='UNTRADED' for r in audit))
    for g in groups:
        if g['group']=='trade_outcome' and g['label']!='UNTRADED':
            print(g['period'],g['label'],g['count'],json.dumps({k:v for k,v in g['features'].items() if k.startswith('AUTH_') and k.endswith(('rise_pct','retracement','velocity_ratio','left_efficiency'))}))
    print('Saved:',OUT)
if __name__=='__main__': main()
