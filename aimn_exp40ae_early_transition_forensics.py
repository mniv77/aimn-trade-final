#!/usr/bin/env python3
"""EXP40-AE: all-bar observational warning comparison, no trades or orders."""
import json
from bisect import bisect_right
from collections import Counter, defaultdict
from statistics import median
import aimn_exp40ad_sequential_trajectory_forensics as ad
import aimn_exp40ac_structural_position_forensics as ac
import aimn_exp40m_supertrend_forensics as m
import aimn_exp40o_transition_recognition_forensics as o
OUT=ad.R/'exp40ae_early_transition_forensics'


def detectors(day,i):
    old=o.warning_rules(day,i,'SHORT')
    rules=[name for name,key in [('AE0','TWO_STEP'),('AE1','PEAK_BREAK')] if key in old]
    if i<1: return rules
    b,c=day[i-1:i+1]
    bearish=c['close']<b['close'] and c['close']<c['open']
    # Two preceding nonoverlapping 3-change LONG phases, second weaker.
    decel=False
    if i>=7:
        a,z,y=[day[j]['close'] for j in (i-7,i-4,i-1)]
        v1=ac.short(a,z); v2=ac.short(z,y)
        decel=v1<v2<0 and bearish
    # Previous bar is a trailing four-bar peak; first lower high/close.
    peak=i>=4 and b['high']>=max(r['high'] for r in day[i-4:i-1])
    structural=peak and bearish and c['high']<b['high']
    if decel: rules.append('AE2')
    if structural: rules.append('AE3')
    if decel and structural: rules.append('AE4')
    return rules


def main():
    if OUT.exists(): raise FileExistsError(OUT)
    audit=[]; hashes={}; counts={}; focus={}
    prior=[]
    for period,src,sha,n,cp,tp,nc,nt,net in ad.SETS:
        assert ad.digest(src)==sha
        data=json.loads(src.read_bytes()); assert len(data)==n
        hashes[str(src.relative_to(ad.ROOT))]=sha
        if period=='NOV':
            warm=m.load(m.WARM,'d038f8c34226810c0ef397fee3a393c2757535f12e5243da7f35674ac548d3ec')
        else: warm=prior
        rows=warm+data
        stamps=[r['timestamp'] for r in rows]; assert stamps==sorted(set(stamps))
        s5=m.snapshots(rows,5); s30=m.snapshots(m.aggregate(rows),30)
        avail=[r['available_time'] for r in s30]; index={r['timestamp']:i for i,r in enumerate(rows)}
        days=defaultdict(list)
        for r in data: days[r['timestamp'][:10]].append(r)
        assert all(len(d)==78 for d in days.values())
        counts[period]=len(data); focus[period]=0
        for day in days.values():
            rules=[detectors(day,i) for i in range(len(day))]
            for i,r in enumerate(day):
                if not rules[i]: continue
                s=s5[index[r['timestamp']]]; j=bisect_right(avail,s['available_time'])-1
                major=s30[j]['trend'] if j>=0 and s30[j]['st'] is not None else 'UNKNOWN'
                local=s['trend'] if s['st'] is not None else 'UNKNOWN'
                context=local+'/'+major
                if 'AE0' in rules[i] and context=='LONG/SHORT': focus[period]+=1
                base=ac.analyze(day,i,{'signal_time':r['timestamp']},None)
                # Future matching is an observational proxy, not proof of same transition.
                future=next((k-i for k in range(i+1,min(i+7,len(day))) if 'AE0' in rules[k]),None)
                match='SAME_BAR' if 'AE0' in rules[i] else 'EARLIER' if future is not None else 'NO_LATER_TWO_STEP' if i+6<len(day) else 'CENSORED'
                peak=max(z['high'] for z in day[max(0,i-11):i+1])
                for name in rules[i]:
                    audit.append(dict(period=period,detector=name,context=context,**base,two_step_match=match,two_step_lead_bars=0 if match=='SAME_BAR' else future,peak_to_next_open_pct=ac.short(peak,day[i+1]['open']) if i+1<len(day) else None))
        prior=rows
        assert focus[period]==nc,(period,focus[period],nc)
        print(period,'candles',n,'focus TWO_STEP',focus[period],flush=True)
    groups=[]
    for period in [*counts,'ALL']:
        for context in ['ALL','LONG/SHORT']:
            for name in ['AE0','AE1','AE2','AE3','AE4']:
                rr=[r for r in audit if (period=='ALL' or r['period']==period) and (context=='ALL' or r['context']==context) and r['detector']==name]
                complete=[r for r in rr if r['price_outcome_hindsight']!='CENSORED']
                outcomes=Counter(r['price_outcome_hindsight'] for r in rr)
                def med(key,records=rr):
                    v=[r[key] for r in records if r[key] is not None]; return round(median(v),6) if v else None
                groups.append(dict(period=period,context=context,detector=name,warnings=len(rr),complete=len(complete),persistent=outcomes['PERSISTENT_TARGET'],persistent_pct=round(100*outcomes['PERSISTENT_TARGET']/len(complete),3) if complete else None,outcomes=dict(outcomes),two_step_matches=dict(Counter(r['two_step_match'] for r in rr)),median_lead_bars=med('two_step_lead_bars',[r for r in rr if r['two_step_match']=='EARLIER']),median_peak_age=med('recent12_peak_age'),median_peak_to_entry_pct=med('peak_to_next_open_pct'),median_favorable_pct=med('favorable_hindsight'),median_adverse_pct=med('adverse_hindsight'),median_terminal_pct=med('terminal_hindsight')))
    report=dict(notes=['All periods discovery. Observational warnings only; no replay or orders.','AE2 requires two preceding three-change rising phases, second weaker, followed by bearish close. AE3 requires preceding trailing four-bar peak and lower high/bearish close. AE4 intersection.','Future six-bar outcomes and later TWO_STEP matches are hindsight only. Overlapping warnings dependent; matching does not establish same transition.','No-later-TWO_STEP is not proof of a missed opportunity. No threshold optimization.'],source_hashes=hashes,candles=counts,focus_parity=focus,groups=groups)
    OUT.mkdir(parents=True,exist_ok=False)
    ac.write(OUT/'warning_audit.csv',audit)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps([g for g in groups if g['context']=='LONG/SHORT'],indent=2,allow_nan=False))

if __name__=='__main__': main()
