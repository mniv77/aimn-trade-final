"""EXP39: frozen MTF-5 plus selective recovery; standard library only."""
import ast,csv,statistics as st
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def read(name):
    with (ROOT/name).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))

def main():
    a=read('aimn_exp38_multidimensional_fingerprint_audit.csv')
    b=read('aimn_exp37_transition_fingerprint_audit.csv')
    rows=[r for r in a if r['strategy']=='MTF-5']; assert len(a)==780 and len(rows)==len(b)==130
    ref={r['signal_time']:r for r in b}; assert len(ref)==130 and len({r['signal_time'] for r in rows})==130
    desc=rows[0]['model']; assert all(r['model']==desc for r in rows)
    prefix,raw=desc.split(' votes: '); need=int(prefix.split('/')[0]); rules=ast.literal_eval(raw)
    def val(r,k):return float(r[k]) if r[k] not in ('','None') else None
    def vote(r,k,t,s):return val(r,k) is not None and s*(val(r,k)-t)>=0
    for r in rows:
        q=ref[r['signal_time']]; assert r['split']==q['split'] and r['label_RESEARCH_ONLY']==q['label_RESEARCH_ONLY'] and float(r['baseline_net_pct'])==float(q['baseline_net_pct'])
        for k in ('prior_peak_rise','peak_drawdown','peak_age_minutes','short_15m','short_30m','down_fraction','lower_high_proxy','rsi14','rsi_change_15m'):
            assert val(r,k)==val(q,k)
        r['votes']=sum(vote(r,*rule) for rule in rules); r['base_accept']=int(r['accept']); assert r['base_accept']==int(r['votes']>=need)
        r['pnl']=float(r['baseline_net_pct'])
    dev=[r for r in rows if r['split']=='DEVELOPMENT_JUN_JUL']; aug=[r for r in rows if r not in dev]; assert all(r['signal_time'][5:7]=='08' for r in aug)
    # Fixed hypotheses, not optimized against August or returns.
    def borderline(r):return r['votes']==need-1
    def structural(r):return val(r,'lower_high_proxy')==1 and val(r,'down_fraction') is not None and val(r,'down_fraction')>=2/3 and val(r,'short_15m') is not None and val(r,'short_15m')>0
    def proximity(r):return val(r,'peak_age_minutes') is not None and val(r,'peak_age_minutes')<=10 and val(r,'peak_drawdown') is not None and val(r,'peak_drawdown')<=.40
    models={'ROR-0':lambda r:True,'ROR-1':lambda r:bool(r['base_accept']),'ROR-2':lambda r:r['base_accept'] or borderline(r),'ROR-3':lambda r:r['base_accept'] or structural(r),'ROR-4':lambda r:r['base_accept'] or proximity(r),'ROR-5':lambda r:r['base_accept'] or (borderline(r) and (structural(r) or proximity(r)))}
    out=[]
    for name,fn in models.items():
        for period,g in [('DEV',dev),('AUG',aug),('ALL',rows)]:
            accepted=[r for r in g if fn(r)]; recovered=[r for r in accepted if not r['base_accept']]; w=sum(r['pnl']>0 for r in accepted)
            print(name,period,len(g),len(accepted),w,len(accepted)-w,round(sum(r['pnl'] for r in accepted)/len(g),6),round(st.mean(r['pnl'] for r in accepted),6) if accepted else None,'recovered',len(recovered),sum(r['pnl']>0 for r in recovered),sum(r['label_RESEARCH_ONLY']=='CONFIRMED' for r in recovered),sum(r['label_RESEARCH_ONLY']=='LOCAL_REVERSE_FIRST' for r in recovered),round(sum(r['pnl'] for r in recovered),6))
        for r in rows:
            accept=int(bool(fn(r))); out.append(dict(signal_time=r['signal_time'],split=r['split'],strategy=name,label_RESEARCH_ONLY=r['label_RESEARCH_ONLY'],baseline_net_pct=r['pnl'],mtf5_votes=r['votes'],mtf5_accept=r['base_accept'],borderline=int(borderline(r)),structural=int(structural(r)),proximity=int(proximity(r)),accept=accept,recovered=int(accept and not r['base_accept']),net_per_candidate=accept*r['pnl']))
    with (ROOT/'aimn_exp39_rejected_opportunity_recovery_audit.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
if __name__=='__main__':main()
