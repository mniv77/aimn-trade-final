"""EXP25: offline fixed-candidate entry ablation, no live changes."""
import csv,json
from pathlib import Path
from datetime import datetime,timedelta
from statistics import mean
ROOT=Path(__file__).resolve().parent
POLICIES=('baseline','mtl1','mtl2','mtl3','mtl4')
def main():
    bars=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda b:b['timestamp'])
    ts=[datetime.fromisoformat(b['timestamp']) for b in bars]
    idx={t.strftime('%Y-%m-%d %H:%M'):i for i,t in enumerate(ts)}
    if len(idx)!=len(bars): raise ValueError('Duplicate timestamps')
    def read(name):
        with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    source=read('aimn_exp24_trajectory_anatomy_audit.csv')
    prev= {r['episode']:r for r in read('aimn_exp23_failed_continuation_quality_audit.csv')}
    rows=[]; history={p:[] for p in POLICIES}
    for r in sorted(source,key=lambda r:r['signal_time']):
        s=idx[r['signal_time']]; e=idx[r['entry_time']]; x=idx[r['exit_time']]; p=prev[r['episode']]; net=float(r['net_pct'])
        if not s+1==e<=x or p['entry_signal_time']!=r['signal_time'] or p['quality_profit_exit_time']!=r['exit_time'] or abs(float(p['quality_profit_net_pct'])-net)>1e-8 or abs(float(bars[e]['open'])-float(r['entry_price']))>1e-8:raise ValueError('Baseline mismatch '+r['episode'])
        def v(i,k):return float(bars[i][k])
        start=s
        while start>0 and ts[start]-ts[start-1]==timedelta(minutes=5):start-=1
        if s-start<12:raise ValueError('Insufficient same-session context')
        # Two nonoverlapping trailing 30-minute blocks, ending at signal close.
        a=range(s-11,s-5); b=range(s-5,s+1)
        ah=max(v(i,'high') for i in a); al=min(v(i,'low') for i in a)
        bh=max(v(i,'high') for i in b); bl=min(v(i,'low') for i in b)
        move=100*(v(s,'close')/v(s-6,'close')-1)
        peak=max(range(s-12,s+1),key=lambda i:v(i,'high'))
        distance=100*(1-v(s,'close')/v(peak,'high'))
        # Exploratory fixed thresholds, not fitted in this script.
        context=move<=0 and (bh<=ah or bl<al)
        structure=peak<s and distance>=.30 and v(s,'close')<min(v(i,'low') for i in range(s-3,s))
        row=dict(r,context_30m_pct=move,prior_block_high=ah,prior_block_low=al,recent_block_high=bh,recent_block_low=bl,context_pass=int(context),structure_pass=int(structure))
        for policy in POLICIES:
            # Only actual accepted trades whose exit bar has fully elapsed are known.
            losses=[h for h in history[policy] if h[0]<s and ts[h[0]].date()==ts[s].date() and s-h[0]<=12 and h[1]<=0]
            memory=not losses
            accept={'baseline':True,'mtl1':context,'mtl2':structure,'mtl3':memory,'mtl4':context and structure and memory}[policy]
            row[policy+'_accept']=int(accept);row[policy+'_net_pct']=net if accept else 0.;row[policy+'_recent_losses']=len(losses)
            if accept:history[policy].append((x,net))
        rows.append(row)
    if len(rows)!=len(prev):raise ValueError('Episode count mismatch')
    out=ROOT/'aimn_exp25_major_local_trend_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for label,g in [('ALL',rows)]+[(k,[r for r in rows if r['split']==k]) for k in sorted({r['split'] for r in rows})]:
        print(label,len(g))
        for p in POLICIES:
            a=[r for r in g if r[p+'_accept']];print(p,len(a),sum(float(r['net_pct'])>0 for r in a),sum(float(r['net_pct'])<0 for r in a),round(mean(r[p+'_net_pct'] for r in g),4),round(sum(r[p+'_net_pct'] for r in g),4),round(mean(float(r['net_pct']) for r in a),4) if a else None)
    for r in rows:
        if r['signal_time'].startswith('2026-07-22'):print('JUL22',r['episode'],r['signal_time'],r['net_pct'],[r[p+'_accept'] for p in POLICIES])
    print('Saved',out)
if __name__=='__main__':main()
