#!/usr/bin/env python3
"""Install UTC display and copy-on-migrate browser research. No strategy changes."""
from pathlib import Path
import argparse, shutil, subprocess, tempfile
ROOT=Path(__file__).resolve().parent
HTML=ROOT/'templates/aimn_ai_vision_replay.html'
TREND=ROOT/'static/aimn_trend_noise_panel.js'
AM3=ROOT/'static/aimn_am3_transition_panel.js'
HELPER=r'''// AIMn UTC v1: known archive/API wall-clock labels are New York market time.
const aimnNYFormat = new Intl.DateTimeFormat('en-GB', {timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
function aimnNYSeconds(t) {
  const m=/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$/.exec(t);
  if(!m) throw Error('Expected New York wall-clock timestamp: '+t);
  const [y,mo,d,h,mi,s]=m.slice(1).map(Number);
  const wall=Date.UTC(y,mo-1,d,h,mi,s);
  function wallAt(ms){const p=Object.fromEntries(aimnNYFormat.formatToParts(new Date(ms)).map(x=>[x.type,x.value]));return Date.UTC(+p.year,+p.month-1,+p.day,+p.hour,+p.minute,+p.second);}
  // Check all possible New York UTC offsets. Reject ambiguous/nonexistent times.
  const matches=[wall+4*3600000,wall+5*3600000].filter(ms=>wallAt(ms)===wall);
  if(matches.length!==1 || new Date(wall).toISOString().slice(0,19)!==t.replace(' ','T')) throw Error('Invalid or ambiguous New York timestamp: '+t);
  return matches[0]/1000;
}
function aimnParseSeconds(t, knownNY){
  if(typeof t!=='string') throw Error('Invalid timestamp');
  if(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(t)){const ms=Date.parse(t);if(!Number.isFinite(ms))throw Error('Invalid explicit timestamp');return Math.floor(ms/1000);}
  if(!knownNY) throw Error('Local JSON timestamps need explicit UTC or timezone offsets');
  return aimnNYSeconds(t);
}
'''
MIGRATION=r'''  // Copy only: never delete or overwrite the original legacy storage key.
  function migrateUTC(id) {
    const target=keyFor(id);
    const existing=storage.getItem(target);
    if(existing!==null)return existing;
    const parts=JSON.parse(id), legacy=parts.slice();
    legacy[5]=candles[0].legacyTime; legacy[10]=candles[candles.length-1].legacyTime;
    const oldId=JSON.stringify(legacy), oldKey=keyFor(oldId);
    if(oldId===id)return null;
    const raw=storage.getItem(oldKey);
    if(raw===null){
      // If a similar session exists under another timezone, fail closed.
      for(let j=0;j<storage.length;j++){
        const key=storage.key(j);if(!key||!key.startsWith(PREFIX))continue;
        let p;try{p=JSON.parse(decodeURIComponent(key.slice(PREFIX.length)));}catch{continue;}
        if(Array.isArray(p)&&p.length===parts.length&&p.every((v,i)=>i===5||i===10||v===parts[i]))throw Error('Possible legacy session in a different browser timezone; migration blocked');
      }
      return null;
    }
    const saved=JSON.parse(raw);
    if(saved.schema!==VERSION||saved.dataset_id!==oldId||!Array.isArray(saved.records)||!Number.isInteger(saved.visible_candles)||saved.visible_candles<20||saved.visible_candles>candles.length)throw Error('Invalid legacy session');
    function correct(obj,unix,utc,count,price){
      if(!Number.isInteger(count)||count<1||count>saved.visible_candles)throw Error('Invalid legacy candle index');
      const c=candles[count-1];
      if(obj[unix]!==c.legacyTime||obj[utc]!==new Date(c.legacyTime*1000).toISOString()||Number(price)!==c.close)throw Error('Legacy candle/time/price mismatch at '+count);
      obj[unix]=c.time;obj[utc]=new Date(c.time*1000).toISOString();
    }
    for(const r of saved.records){
      if(r.ai_assessment!=null)throw Error('Legacy AI assessment requires separate audit');
      correct(r,'cutoff_unix','cutoff_utc',r.visible_candles,r.cutoff_close);
      if(r.trade_result){const t=r.trade_result;correct(t,'entry_cutoff_unix','entry_cutoff_utc',t.entry_visible_candles,t.entry_close);correct(t,'exit_cutoff_unix','exit_cutoff_utc',r.visible_candles,t.exit_close);}
      if(r.outcome){const o=r.outcome;if(!Number.isInteger(o.revealed_candles)||o.revealed_candles<1)throw Error('Invalid reveal count');correct(o,'revealed_to_unix','revealed_to_utc',r.visible_candles+o.revealed_candles,o.end_close);}
    }
    saved.dataset_id=id;
    saved.utc_migration={version:1,original_dataset_id:oldId,migrated_at_utc:new Date().toISOString()};
    const migrated=JSON.stringify(saved);
    if(storage.getItem(target)!==null||storage.getItem(oldKey)!==raw)throw Error('Storage changed during migration');
    storage.setItem(target,migrated);
    if(storage.getItem(target)!==migrated||storage.getItem(oldKey)!==raw)throw Error('Storage verification failed');
    return migrated;
  }
'''
def replace(s,a,b):
    if s.count(a)!=1: raise ValueError('Expected exactly one occurrence: '+a[:100])
    return s.replace(a,b)
def build():
    h,t,a=[p.read_text() for p in (HTML,TREND,AM3)]
    h=replace(h,'const $=id=>document.getElementById(id);',HELPER+'\nconst $=id=>document.getElementById(id);')
    h=replace(h,'function normalize(root){','function normalize(root,knownNY=true){')
    h=replace(h,'let parsed=Date.parse(t);if(!Number.isFinite(parsed))throw Error(\'Invalid timestamp at candle \'+i);n=Math.floor(parsed/1000)','n=aimnParseSeconds(t,knownNY)')
    h=replace(h,'return {time:n,open:o,high:h,low:l,close:c}',"return {time:n,legacyTime:typeof t==='string'&&!/^\\d+$/.test(t)?Math.floor(Date.parse(t)/1000):n,open:o,high:h,low:l,close:c}")
    h=replace(h,'candles=normalize(raw);sourceName=f.name','candles=normalize(raw,false);sourceName=f.name')
    t=replace(t,'  function restoreForDataset() {',MIGRATION+'\n  function restoreForDataset() {')
    t=replace(t,'const raw = storage.getItem(sessionKey);','const raw = migrateUTC(id);')
    start=a.index('    let offset = null;'); end=a.index('      for (const [key,j]',start)
    a=a[:start]+'''    for (let i=0;i<candles.length;i++) {
      const c = candles[i], r = data.candles[i];
      if (c.time !== aimnNYSeconds(r[0])) { failure='UTC mismatch at candle '+(i+1); return false; }
'''+a[end:]
    a=replace(a,"e.candle_time+' ET | '+label(e)","new Date(candles[e.candle_index].time*1000).toISOString().replace('T',' ').replace('.000Z',' UTC')+' | '+label(e)")
    return [h,t,a]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');args=p.parse_args()
    paths=(HTML,TREND,AM3); contents=build()
    node=shutil.which('node')
    if node:
        import re
        with tempfile.TemporaryDirectory() as d:
            for i,s in enumerate(contents):
                if i==0:s='\n'.join(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',s,re.S))
                f=Path(d)/f'{i}.js';f.write_text(s);subprocess.run([node,'--check',str(f)],check=True)
        print('JavaScript syntax checks PASSED')
    else: print('Node unavailable; browser syntax verification still required')
    print('Exact source anchors PASSED')
    if not args.apply: print('DRY RUN ONLY — no files changed');return
    backup=ROOT/'instance'/'aimn_utc_preinstall_v1';backup.mkdir(parents=True,exist_ok=False)
    for path in paths:shutil.copy2(path,backup/path.name)
    try:
        for path,s in zip(paths,contents):path.write_text(s)
    except Exception:
        for path in paths:shutil.copy2(backup/path.name,path)
        raise
    print('UTC INSTALL PASSED; original files saved in',backup)
    print('Browser migration runs on reload; original storage key retained.')
if __name__=='__main__':main()
