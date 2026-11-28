#!/usr/bin/env python3
"""Fail closed on competing browser research sessions; preserve migration metadata."""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
P = ROOT / 'static/aimn_trend_noise_panel.js'
BACKUP = ROOT / 'instance/aimn_before_utc_conflict_guard.js'
GUARD = '''    const target=keyFor(id), existing=storage.getItem(target);
    const parts=JSON.parse(id), legacy=parts.slice();
    legacy[5]=candles[0].legacyTime;
    legacy[10]=candles[candles.length-1].legacyTime;
    const oldId=JSON.stringify(legacy), oldKey=keyFor(oldId);
    const matches=[];
    for(let j=0;j<storage.length;j++){
      const key=storage.key(j);
      if(!key||key===target||!key.startsWith(PREFIX))continue;
      let p;
      try{p=JSON.parse(decodeURIComponent(key.slice(PREFIX.length)));}catch{continue;}
      if(Array.isArray(p)&&p.length===parts.length&&p.every((v,i)=>i===5||i===10||v===parts[i]))matches.push(key);
    }
    if(existing!==null){
      if(!matches.length)return existing;
      const current=JSON.parse(existing), m=current.utc_migration;
      if(matches.length!==1||!m||m.version!==1||keyFor(m.original_dataset_id)!==matches[0])throw Error('Conflicting UTC and legacy sessions; recovery blocked');
      const prior=JSON.parse(storage.getItem(matches[0]));
      if(prior.schema!==VERSION||prior.dataset_id!==m.original_dataset_id||!Array.isArray(prior.records)||!Array.isArray(current.records)||current.records.length<prior.records.length||current.visible_candles<prior.visible_candles||!Number.isFinite(Date.parse(prior.updated_at_utc))||!(Date.parse(prior.updated_at_utc)<=Date.parse(m.migrated_at_utc)))throw Error('Legacy session changed or incomplete migration; recovery blocked');
      return existing;
    }
    if(!matches.length)return null;
    if(matches.length!==1||matches[0]!==oldKey||oldId===id)throw Error('Ambiguous legacy session; migration blocked');
    const raw=storage.getItem(oldKey);
'''
OLD = '''      storage.setItem(sessionKey, JSON.stringify({
        schema: VERSION,'''
NEW = '''      const previous=JSON.parse(storage.getItem(sessionKey)||'null');
      storage.setItem(sessionKey, JSON.stringify({
        ...(previous?.dataset_id===datasetId && previous.utc_migration
          ? {utc_migration:previous.utc_migration} : {}),
        schema: VERSION,'''

def build(s):
    start = s.index('    const target=keyFor(id);', s.index('function migrateUTC(id)'))
    end = s.index('    const saved=JSON.parse(raw);', start)
    if 'if(existing!==null)return existing;' not in s[start:end] or s.count(OLD)!=1:
        raise ValueError('Source anchors differ; no changes made')
    return (s[:start]+GUARD+s[end:]).replace(OLD,NEW)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    original=P.read_bytes()
    result=build(original.decode('utf-8'))
    print('Exact source anchors PASSED')
    node=shutil.which('node')
    with tempfile.TemporaryDirectory() as td:
        f=Path(td)/'check.js'; f.write_text(result,encoding='utf-8')
        if node:
            subprocess.run([node,'--check',str(f)],check=True)
            print('JavaScript syntax PASSED')
        else:
            print('Node unavailable; browser verification required')
    if not args.apply:
        print('DRY RUN ONLY — no files changed'); return
    BACKUP.parent.mkdir(exist_ok=True)
    with BACKUP.open('xb') as f: f.write(original)
    if P.read_bytes()!=original: raise RuntimeError('Source changed during installation')
    with tempfile.NamedTemporaryFile(dir=P.parent,suffix='.js',delete=False) as f:
        tmp=Path(f.name); f.write(result.encode('utf-8'))
    try:
        shutil.copymode(P,tmp); tmp.replace(P)
    finally:
        tmp.unlink(missing_ok=True)
    print('UTC CONFLICT SAFEGUARD INSTALLED')
    print('Migration metadata preservation INSTALLED')
    print('Original JavaScript backed up:',BACKUP)
    print('No browser research data modified')

if __name__=='__main__': main()
