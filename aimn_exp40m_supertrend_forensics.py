#!/usr/bin/env python3
"""EXP40-M: observational SuperTrend audit; no strategy changes or orders."""
import csv
import json
import hashlib
import math
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from bisect import bisect_right
from kiss.kiss_exp53_supertrend import calculate_supertrend

ROOT=Path(__file__).resolve().parent
WARM=ROOT/'kiss/visual_research/independent_holdout_exp144/nvda_nov_2026_5m_iex.json'
TEST=ROOT/'kiss/visual_research/independent_holdout_exp40l/nvda_2026-11-16_2026-11-25_5m_iex.json'
SOURCE=ROOT/'kiss/results/exp40l_independent_validation'
OUT=ROOT/'kiss/results/exp40m_supertrend_forensics'
START='2026-11-16 09:30:00'

def load(path,digest):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest: raise ValueError(f'Hash mismatch: {path}')
    return json.loads(raw)

def read_csv(path):
    with path.open(newline='') as f: return list(csv.DictReader(f))

def write_csv(path,rows):
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def aggregate(rows):
    result=[]
    for i in range(0,len(rows),6):
        block=rows[i:i+6]
        t=datetime.fromisoformat(block[0]['timestamp'])
        if len(block)!=6 or t.minute not in (0,30) or any(datetime.fromisoformat(r['timestamp'])!=t+timedelta(minutes=5*j) for j,r in enumerate(block)):
            raise ValueError('Incomplete 30m block')
        result.append(dict(timestamp=block[0]['timestamp'],open=block[0]['open'],high=max(r['high'] for r in block),low=min(r['low'] for r in block),close=block[-1]['close'],volume=sum(r.get('volume',0) for r in block)))
    return result

def snapshots(rows,minutes):
    df=calculate_supertrend(rows,atr_period=10,multiplier=3.0)
    if list(df['timestamp'])!=[r['timestamp'] for r in rows]: raise ValueError('ST timestamp mismatch')
    out=[]; last=None; age=0
    for r in df.to_dict('records'):
        direction=r['st_trend']; age=age+1 if direction==last else 1; last=direction
        line=float(r['supertrend']); atr=float(r['atr']); close=float(r['close'])
        valid=math.isfinite(line) and math.isfinite(atr) and atr>0
        out.append(dict(bar_time=r['timestamp'],available_time=(datetime.fromisoformat(r['timestamp'])+timedelta(minutes=minutes)).isoformat(sep=' '),trend=direction,transition=r['st_transition'],trend_age_bars=age if valid else None,st=line if valid else None,atr=atr if valid else None,close=close,distance_pct=100*(close-line)/close if valid else None,distance_atr=(close-line)/atr if valid else None,st_change=None))
        if len(out)>1 and valid and out[-2]['st'] is not None and direction==out[-2]['trend']:
            out[-1]['st_change']=line-out[-2]['st']
    return out

def prefixed(s,p): return {p+k:v for k,v in s.items()}

def main():
    warm=load(WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec')
    test=load(TEST,'eabb5477fc612d1d7ad21973282bc2a527c94da26fefdb9931172c89950b572d')
    rows=warm+test
    assert len(warm)==780 and len(test)==624
    times=[r['timestamp'] for r in rows]; assert all(a<b for a,b in zip(times,times[1:]))
    for i in range(0,len(rows),78):
        t=datetime.fromisoformat(times[i]); assert t.strftime('%H:%M')=='09:30'
        assert all(datetime.fromisoformat(times[i+j])==t+timedelta(minutes=5*j) for j in range(78))
    s5=snapshots(rows,5); s30=snapshots(aggregate(rows),30)
    avail=[s['available_time'] for s in s30]
    bytime={r['timestamp']:i for i,r in enumerate(rows)}
    cand=read_csv(SOURCE/'K3_candidates.csv'); b2=read_csv(SOURCE/'B2_trades.csv'); k3=read_csv(SOURCE/'K3_trades.csv')
    assert len(cand)==13 and len(b2)==12 and len(k3)==3
    assert round(sum(float(t['net_pnl_pct']) for t in b2),6)==-3.268879
    assert round(sum(float(t['net_pnl_pct']) for t in k3),6)==-1.673977
    bmap={t['signal_time']:t for t in b2}; kmap={t['signal_time']:t for t in k3}
    timeline=[]; audit=[]
    def context(i):
        a=s5[i]; j=bisect_right(avail,a['available_time'])-1
        assert j>=0 and s30[j]['available_time']<=a['available_time']
        return {**prefixed(a,'st5_'),**prefixed(s30[j],'st30_')}
    for i,r in enumerate(rows):
        if r['timestamp']>=START: timeline.append({**r,**context(i)})
    for c in cand:
        t=c['signal_time']; i=bytime[t]; bt=bmap.get(t); kt=kmap.get(t); ctx=context(i)
        rec={**c,**ctx,'signal_open':rows[i]['open'],'signal_high':rows[i]['high'],'signal_low':rows[i]['low'],'signal_close':rows[i]['close'],'b2_net_hindsight':bt['net_pnl_pct'] if bt else None,'k3_net_hindsight':kt['net_pnl_pct'] if kt else None}
        # Future ST confirmations are descriptive labels, never entry features.
        for name,series in [('5m',s5),('30m',s30)]:
            future=next((s for s in series if s['available_time']>ctx['st5_available_time'] and s['available_time'][:10]==t[:10] and s['transition']=='LONG->SHORT'),None)
            rec[f'next_{name}_short_flip_hindsight']=future['available_time'] if future else None
            rec[f'next_{name}_short_flip_delay_minutes_hindsight']=(datetime.fromisoformat(future['available_time'])-datetime.fromisoformat(ctx['st5_available_time'])).total_seconds()/60 if future else None
        audit.append(rec)
    report={'notes':['Observational only; November data now used for discovery. No orders or strategy edits.','ST ATR 10 multiplier 3; both timeframes include regular-session warm-up and carry state overnight.','30m context uses only completed bars, including the prior session when necessary.','Signed distance is close minus ST, normalized by close or ATR. Future flip delays are measured from candidate decision time, not from an objectively labeled reversal.','Trade outcomes and future flips are hindsight labels, not entry inputs.'],'source_st_sha256':hashlib.sha256((ROOT/'kiss/kiss_exp53_supertrend.py').read_bytes()).hexdigest(),'candidates':len(audit),'timeline_bars':len(timeline),'candidate_context_counts':dict(Counter(f"{a['st5_trend']}/{a['st30_trend']}" for a in audit)),'candidate_summary':[{key:a[key] for key in ('signal_time','status','st5_trend','st30_trend','st5_distance_atr','st30_distance_atr','b2_net_hindsight','k3_net_hindsight','next_5m_short_flip_delay_minutes_hindsight','next_30m_short_flip_delay_minutes_hindsight')} for a in audit]}
    OUT.mkdir(parents=True,exist_ok=False)
    write_csv(OUT/'candidate_supertrend_audit.csv',audit)
    write_csv(OUT/'validation_supertrend_timeline.csv',timeline)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__': main()
