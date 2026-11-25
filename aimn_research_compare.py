#!/usr/bin/env python3
"""AIMn EXP74/75: fetch a research ref and compare safely, NO DEPLOYMENT.

Fetches only the named research branch into a dedicated remote-tracking ref.
Never checks out, merges, resets, writes production files, or reloads the app.
Creates diff reports under backups/. No credentials or tokens are printed.
"""
from __future__ import annotations
import difflib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/MeirNiv/aimn-trade-final')
BRANCH = 'research/ai-vision-independent-v1'
REF = 'refs/remotes/origin/' + BRANCH
PROTECTED = ('templates/aimn_visual_lab.html', 'kiss_backtest_routes.py')
REQUIRED = ('kiss/exp74_kiss_hybrid_engine.py', 'kiss/exp75_kiss_profit_lock_engine.py', 'kiss/visual_research/aimn_nvda_candles.json')


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, check=False)


def main() -> int:
    print('AIMn EXP74/75 — RESEARCH COMPARISON ONLY')
    print('=' * 60)
    if not (ROOT / '.git').is_dir():
        print('STOP: project not found:', ROOT)
        return 2
    branch = git('branch', '--show-current')
    current = branch.stdout.strip()
    print('CURRENT BRANCH:', current)
    if branch.returncode or current != 'kiss-transition-detector-v5-6-6-final':
        print('STOP: unexpected production branch. Nothing changed.')
        return 2
    for path in PROTECTED:
        if not (ROOT / path).is_file():
            print('STOP: missing production file:', path)
            return 2
    print('Fetching research branch metadata and objects only; production files stay untouched.')
    result = git('fetch', '--no-tags', 'origin', '+' + 'refs/heads/' + BRANCH + ':' + REF)
    if result.returncode:
        print('STOP: fetch failed:', result.stderr.strip()[-1200:])
        return 3
    rev = git('rev-parse', '--verify', REF + '^{commit}')
    if rev.returncode:
        print('STOP: fetched research ref cannot be verified')
        return 3
    print('RESEARCH COMMIT:', rev.stdout.strip())
    reports = ROOT / 'backups' / ('exp74-exp75-compare-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-UTC'))
    reports.mkdir(parents=True, exist_ok=False)
    print('REPORT FOLDER:', reports)
    for path in PROTECTED:
        research = git('show', REF + ':' + path)
        if research.returncode:
            print('STOP: research file missing:', path)
            return 4
        local_lines = (ROOT / path).read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
        research_lines = research.stdout.splitlines(keepends=True)
        diff = list(difflib.unified_diff(local_lines, research_lines, fromfile='LIVE/' + path, tofile='RESEARCH/' + path, n=3))
        output = reports / (Path(path).name + '.diff')
        output.write_text(''.join(diff), encoding='utf-8')
        print('DIFF:', path, '|', len(diff), 'lines |', output)
        if diff:
            print('  Preview:', ''.join(diff[:12]).replace('\n', ' ')[:500])
    for path in REQUIRED:
        found = git('cat-file', '-e', REF + ':' + path)
        print('RESEARCH DEPENDENCY:', path, 'PRESENT' if found.returncode == 0 else 'MISSING')
    status = git('status', '--short', '--', *PROTECTED)
    print('PROTECTED WORKTREE STATUS:', status.stdout.strip() or 'clean')
    print('DONE: no production file modified; no deployment performed.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('STOP:', type(exc).__name__, str(exc))
        sys.exit(1)
