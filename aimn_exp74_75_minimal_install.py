#!/usr/bin/env python3
"""AIMn EXP74/75 isolated deployment. Dry run by default; --apply to install.
Never switches Git branches, changes live trading engines, or reloads web apps.
"""
from __future__ import annotations
import argparse
import datetime as dt
import difflib
import hashlib
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
BRANCH = 'refs/remotes/origin/research/ai-vision-independent-v1'
TARGETS = ('templates/aimn_visual_lab.html', 'kiss_backtest_routes.py')
ENGINES = ('kiss/exp74_kiss_hybrid_engine.py', 'kiss/exp75_kiss_profit_lock_engine.py')
DATA = 'kiss/visual_research/aimn_nvda_candles.json'
ENDPOINT = '@app.route("/api/aimn_visual_lab/exp74_75", methods=["GET"])'
PANEL = '<section id="exp74_75ResearchPanel" style="padding:12px;border:1px solid #34506e;margin:10px 0"><strong>EXP74 vs EXP75 — NVDA SHORT historical research (V15; separate from V17 saved trades)</strong> <select id="expCompareMode" onchange="updateVisionMarkers()"><option value="both">Both</option><option value="EXP74">EXP74</option><option value="EXP75">EXP75</option><option value="off">Hide</option></select><span id="expCompareSummary">Load NVDA SHORT chart to compare.</span><div id="expCompareTrades" style="max-height:180px;overflow:auto"></div></section>\n'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, stderr=subprocess.STDOUT)

def research(path):
    return git('show', f'{BRANCH}:{path}').decode('utf-8')

def exactly_once(s, needle, name):
    n=s.count(needle)
    if n != 1: raise RuntimeError(f'{name}: expected exactly one anchor, found {n}: {needle[:80]}')

def build():
    current={p:(ROOT/p).read_text(encoding='utf-8') for p in TARGETS}
    research_html=research(TARGETS[0]); research_routes=research(TARGETS[1]);
    html=current[TARGETS[0]]; routes=current[TARGETS[1]]
    if 'id="expCompareMode"' in html or ENDPOINT in routes:
        raise RuntimeError('Research comparison already partly installed. Stop; do not apply twice.')
    exactly_once(html,'<select id="trade">','trade dropdown')
    html=html.replace('<select id="trade">', PANEL+'<select id="trade">',1)
    begin='let expCompareMarkers=[];'; end='function updateVisionMarkers(){'
    exactly_once(research_html,begin,'research comparison start')
    exactly_once(research_html,end,'research comparison end')
    js=research_html.split(begin,1)[1].split(end,1)[0]
    exactly_once(html,end,'local markers function')
    html=html.replace(end,begin+js+end,1)
    exactly_once(html,'  installVisionSelection();','chart setup')
    html=html.replace('  installVisionSelection();','  installVisionSelection();\n  await loadExpCompare(symbol);',1)
    old='series.setMarkers([...kiss,...ai,...review].sort((a,b)=>a.time-b.time));'
    exactly_once(html,old,'original chart marker render')
    html=html.replace(old,"const mode=el('expCompareMode').value;\n  const comparison=view==='ai'||mode==='off'?[]:expCompareMarkers.filter(m=>valid.has(m.time)&&(mode==='both'||m.experiment===mode));\n  series.setMarkers([...kiss,...ai,...review,...comparison].sort((a,b)=>a.time-b.time));",1)
    exactly_once(research_routes,ENDPOINT,'research endpoint')
    # Research endpoint is appended at the end of the route registration function.
    endpoint='    '+research_routes.split('    '+ENDPOINT,1)[1]
    endpoint='    '+ENDPOINT+endpoint
    if not routes.endswith('\n'):routes+='\n'
    routes+='\n'+endpoint
    # Validate engine/data are accessible from research ref; never overwrite existing files blindly.
    outputs={TARGETS[0]:html.encode(),TARGETS[1]:routes.encode()}
    for p in ENGINES+(DATA,):
        b=git('show',f'{BRANCH}:{p}')
        dest=ROOT/p
        if dest.exists():
            if dest.read_bytes()!=b: raise RuntimeError(f'Existing {p} differs from research branch; stop for manual review.')
        else: outputs[p]=b
    return current,outputs

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    print('AIMn EXP74/75 MINIMAL RESEARCH INSTALL — '+('APPLY' if args.apply else 'DRY RUN'))
    print('Project:',ROOT)
    branch=git('branch','--show-current').decode().strip();print('Current branch:',branch)
    if branch!='kiss-transition-detector-v5-6-6-final':raise RuntimeError('Unexpected production branch; refusing')
    git('rev-parse','--verify',BRANCH)
    current,outputs=build()
    for p,b in outputs.items():
        print(('UPDATE' if (ROOT/p).exists() else 'ADD')+': '+p+' | SHA256 '+hashlib.sha256(b).hexdigest()[:16])
    if not args.apply:
        print('DRY RUN SUCCESS: No files modified. Review output, then run with --apply.');return
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S-UTC')
    backup=ROOT/'backups'/('pre-minimal-exp74-exp75-'+stamp)
    backup.mkdir(parents=True,exist_ok=False)
    for p in TARGETS:
        dest=backup/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/p,dest)
        assert dest.read_bytes()==(ROOT/p).read_bytes()
    print('Verified backup:',backup)
    # Write atomically, but do not reload server.
    for p,b in outputs.items():
        dest=ROOT/p;dest.parent.mkdir(parents=True,exist_ok=True)
        temp=dest.with_name(dest.name+'.exp74_75_new')
        temp.write_bytes(b)
        if p.endswith('.py'):
            import ast
            ast.parse(b.decode('utf-8'),filename=p)
        temp.replace(dest)
        assert dest.read_bytes()==b
    print('INSTALL SUCCESS. NO WEB RELOAD. NO BRANCH SWITCH. NO LIVE TRADING ENGINE CHANGES.')
    print('Next: share this output for review before reloading PythonAnywhere.')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('STOPPED SAFELY:',e,file=sys.stderr);sys.exit(1)
