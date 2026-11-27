#!/usr/bin/env python3
"""EXP40-AG: causal descriptors of AE3 warnings; retrospective labels only."""
import json
from bisect import bisect_right
from collections import Counter, defaultdict
from statistics import median
from engine import kiss_backtest as base
import aimn_exp40ae_early_transition_forensics as ae
import aimn_exp40ad_sequential_trajectory_forensics as ad
import aimn_exp40ac_structural_position_forensics as ac
import aimn_exp40m_supertrend_forensics as m
OUT=ad.R/'exp40ag_early_warning_discrimination'
SRC=ae.OUT/'warning_audit.csv'

def features(day,i,idx,rsi,s5,major):
    b,c=day[i-1:i+1]; peak=max(range(max(0,i-11),i+1),key=lambda j:(day[j]['high'],j))
    span=c['high']-c['low']; prior_span=b['high']-b['low']
    def delta(series,n):
        return series[idx]-series[idx-n] if i>=n and series[idx] is not None and series[idx-n] is not None else None
    dist=[s['distance_atr'] for s in s5]
    p=idx-i+peak
    return dict(rsi=rsi[idx],rsi_peak=rsi[p],rsi_delta3=delta(rsi,3),rsi_delta6=delta(rsi,6),rsi_delta_peak=rsi[idx]-rsi[p] if rsi[idx] is not None and rsi[p] is not None else None,
        st5_distance_atr=dist[idx],st5_delta3=delta(dist,3),st5_delta6=delta(dist,6),st5_age=s5[idx]['trend_age_bars'],st30_distance_atr=major['distance_atr'],st30_age=major['trend_age_bars'],
        signal_body_fraction=(c['open']-c['close'])/span if span else None,signal_close_location=(c['close']-c['low'])/span if span else None,signal_range_ratio=span/prior_span if prior_span else None,
        signal_lower_low=int(c['low']<b['low']),signal_break_prior_low=int(c['close']<b['low']),signal_high_change=ac.pct(b['high'],c['high']),signal_low_change=ac.pct(b['low'],c['low']),
        **ad.phases(day,i))

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    old=[r for r in ac.read(SRC) if r['detector']=='AE3' and r['context']=='LONG/SHORT']
    lookup={(r['period'],r['signal_time']):r for r in old}; assert len(old)==len(lookup)==174
    assert Counter(r['two_step_match'] for r in old)=={'EARLIER':85,'NO_LATER_TWO_STEP':72,'CENSORED':17}
    audit=[]; prior=[]; hashes={str(SRC):ad.digest(SRC)}
    for period,src,sha,n,*_ in ad.SETS:
        assert ad.digest(src)==sha
        data=json.loads(src.read_bytes()); assert len(data)==n
        warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec') if period=='NOV' else prior
        rows=warm+data; stamps=[r['timestamp'] for r in rows]; assert stamps==sorted(set(stamps))
        idxs={t:i for i,t in enumerate(stamps)}; s5=m.snapshots(rows,5); s30=m.snapshots(m.aggregate(rows),30); avail=[s['available_time'] for s in s30]
        rsi=base.rsi_wilder([float(r['close']) for r in rows],14)
        days=defaultdict(list)
        for r in data: days[r['timestamp'][:10]].append(r)
        assert all(len(d)==78 for d in days.values())
        for day in days.values():
            for i,c in enumerate(day):
                if 'AE3' not in ae.detectors(day,i): continue
                idx=idxs[c['timestamp']]; j=bisect_right(avail,s5[idx]['available_time'])-1
                if j<0 or s5[idx]['st'] is None or s30[j]['st'] is None or (s5[idx]['trend'],s30[j]['trend'])!=('LONG','SHORT'): continue
                r=lookup[period,c['timestamp']]
                audit.append(dict(r,**features(day,i,idx,rsi,s5,s30[j])))
        prior=rows; hashes[str(src)]=sha
    assert len(audit)==174 and {(r['period'],r['signal_time']) for r in audit}==set(lookup)
    keys=['rsi','rsi_peak','rsi_delta3','rsi_delta6','rsi_delta_peak','st5_distance_atr','st5_delta3','st5_delta6','st5_age','st30_distance_atr','st30_age','signal_body_fraction','signal_close_location','signal_range_ratio','signal_lower_low','signal_break_prior_low','signal_high_change','signal_low_change','high_change_pct','low_change_pct','recent12_peak_age','recent12_peak_decline_pct','recent12_range_position','prior3_decline_pct','prior6_decline_pct','A_velocity','B_velocity','C_velocity','BA_delta_velocity','CB_delta_velocity','A_efficiency','B_efficiency','C_efficiency']
    groups=[]
    for period in ['JUN_AUG','SEP_OCT','NOV','ALL']:
        rr=[r for r in audit if period=='ALL' or r['period']==period]
        for axis in ['two_step_match','price_outcome_hindsight']:
            for label in sorted({r[axis] for r in rr}):
                subset=[r for r in rr if r[axis]==label]; stats={}
                for k in keys:
                    v=[float(r[k]) for r in subset if r[k] not in ('',None)]
                    stats[k]=dict(available=len(v),median=round(median(v),6) if v else None)
                groups.append(dict(period=period,axis=axis,label=label,count=len(subset),features=stats))
    OUT.mkdir(parents=True,exist_ok=False); ac.write(OUT/'warning_feature_audit.csv',audit)
    (OUT/'summary.json').write_text(json.dumps(dict(notes=['All discovery data. No entry filters, optimization, replay or orders. Later TWO_STEP is not proof of genuine trend. Overlapping observations dependent. RSI uses same warm-up as AE.'],source_hashes=hashes,groups=groups),indent=2,allow_nan=False)+'\n')
    compact=['rsi','rsi_delta3','rsi_delta_peak','st5_distance_atr','st5_delta3','signal_body_fraction','signal_close_location','signal_lower_low','signal_break_prior_low','B_velocity','C_velocity','CB_delta_velocity','recent12_range_position']
    for g in groups:
        if g['label'] in ('EARLIER','NO_LATER_TWO_STEP','PERSISTENT_TARGET','NO_FEE_SCALE_EXCURSION'):
            print(g['period'],g['label'],g['count'],json.dumps({k:g['features'][k]['median'] for k in compact}))
if __name__=='__main__': main()
