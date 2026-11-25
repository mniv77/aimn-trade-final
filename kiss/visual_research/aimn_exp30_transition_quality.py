"""EXP30: fixed DTR-3 candidate quality audit; no live trading changes."""
import csv,json,statistics as st
from pathlib import Path
from datetime import datetime,timedelta
ROOT=Path(__file__).resolve().parent

def main():
    bars=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda b:b['timestamp'])
    def read(name):
        with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    ref=read('aimn_exp19_trend_position_audit.csv'); prior=read('aimn_exp29_dual_trajectory_audit.csv')
    t=[datetime.fromisoformat(b['timestamp']) for b in bars]; c=[float(b['close']) for b in bars]; o=[float(b['open']) for b in bars]
    keys=[x.strftime('%Y-%m-%d %H:%M') for x in t]; idx={k:i for i,k in enumerate(keys)}
    assert len(idx)==len(bars)==len(ref)==4680
    assert all(k==r['timestamp_ny'] and abs(p-float(r['close']))<1e-8 for k,p,r in zip(keys,c,ref))
    def contiguous(a,b):return a>=0 and b<len(t) and t[a].date()==t[b].date() and all(t[j]-t[j-1]==timedelta(minutes=5) for j in range(a+1,b+1))
    rows=[]
    for r in prior:
        if r['strategy']!='DTR-3':continue
        i=idx[r['signal_time']]; p=idx[r['pivot_time']]; s=1 if r['direction']=='LONG' else -1
        assert p<=i and contiguous(p,i) and abs(c[i]-float(r['signal_close']))<1e-8
        # Original direction is opposite to the candidate direction.
        strength=eff=weak=None
        if contiguous(p-12,p):
            strength=-s*(c[p]/c[p-12]-1)*100
            path=sum(abs(c[j]-c[j-1]) for j in range(p-11,p+1))
            eff=abs(c[p]-c[p-12])/path if path else 0
            early=-s*(c[p-6]/c[p-12]-1)*100; late=-s*(c[p]/c[p-6]-1)*100
            weak=early>0 and 0<=late<early
        # Recovery toward original direction, followed by renewed opposite movement.
        failed=any(s*(c[j]-c[j-1])<0 for j in range(p+1,i)) and s*(c[i]-c[i-1])>0 and s*(c[i]-c[p])>0 if i>p else False
        opposite=contiguous(i-3,i) and sum(s*(c[j]-c[j-1])>0 for j in range(i-2,i+1))>=2 and s*(c[i]/c[i-3]-1)*100>=.20
        strong=strength is not None and strength>=.50 and eff>=.25
        flags=[True,strong,weak is True,failed,opposite,strong and sum([weak is True,failed,opposite])>=2]
        gross=net=None
        if contiguous(i,i+6):
            gross=s*(c[i+6]-o[i+1])/o[i+1]*100
            net=gross-.10*(1+c[i+6]/o[i+1])
        row=dict(r);row.update(preceding_60m_strength_pct=strength,preceding_efficiency=eff,weakening=weak,failed_recovery=int(failed),opposite_development=int(opposite),next_open_30m_gross_RESEARCH_ONLY=gross,next_open_30m_net_RESEARCH_ONLY=net)
        row.update({f'TQ-{j}_accept':int(v) for j,v in enumerate(flags)});rows.append(row)
    assert len(rows)==260
    out=ROOT/'aimn_exp30_transition_quality_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for j in range(6):
        for d in ('SHORT','LONG'):
            for split in ('ALL','DEVELOPMENT_JUN_JUL','EVALUATION_AUG'):
                base=[r for r in rows if r['direction']==d and (split=='ALL' or r['split']==split)]; g=[r for r in base if r[f'TQ-{j}_accept']]; v=[r['next_open_30m_net_RESEARCH_ONLY'] for r in g if r['next_open_30m_net_RESEARCH_ONLY'] is not None]; q=[int(r['confirmed_before_local_reverse_RESEARCH_ONLY']) for r in g if r['confirmed_before_local_reverse_RESEARCH_ONLY']!='']; print(j,d,split,len(g),len(v),round(st.mean(v),4) if v else None,sum(x>0 for x in v),sum(q),len(q))
    print('Saved',out)
if __name__=='__main__':main()
