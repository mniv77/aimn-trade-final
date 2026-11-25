#!/usr/bin/env python3
"""AIMn research deployment PRE-FLIGHT ONLY.

Creates timestamped backups of two production files and reports differences
against a locally available Git research ref. Does NOT deploy, fetch, checkout,
merge, modify tracked files, reload Flask, or place trades.

Run from anywhere on PythonAnywhere with:
    python3 aimn_research_deploy.py
(or provide the script's absolute path).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/MeirNiv/aimn-trade-final')
FILES = ('templates/aimn_visual_lab.html', 'kiss_backtest_routes.py')
RESEARCH_REFS = (
    'refs/remotes/origin/research/ai-vision-independent-v1',
    'refs/heads/research/ai-vision-independent-v1',
)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, check=False)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    print('AIMn EXP74/75 — SAFE DEPLOYMENT PRE-FLIGHT')
    print('=' * 66)
    if not (ROOT / '.git').exists():
        print('STOP: expected Git project not found:', ROOT)
        return 2
    missing = [name for name in FILES if not (ROOT / name).is_file()]
    if missing:
        print('STOP: missing production file(s):', ', '.join(missing))
        return 2

    now = datetime.now(timezone.utc)
    stamp = now.strftime('%Y%m%d-%H%M%S-UTC')
    backup_dir = ROOT / 'backups' / ('pre-exp74-exp75-' + stamp)
    # Never overwrite an existing backup folder.
    backup_dir.mkdir(parents=True, exist_ok=False)
    manifest = {'created_utc': now.isoformat(), 'purpose': 'EXP74/75 preflight, no deployment',
                'production_root': str(ROOT), 'files': {}}
    for name in FILES:
        source = ROOT / name
        target = backup_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        original_bytes = source.read_bytes()
        copied_bytes = target.read_bytes()
        if original_bytes != copied_bytes:
            print('STOP: backup verification failed for', name)
            return 3
        manifest['files'][name] = {'sha256': digest(original_bytes), 'bytes': len(original_bytes)}
        print('BACKED UP:', name, '(', len(original_bytes), 'bytes )')
    (backup_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('\nVERIFIED BACKUP:', backup_dir)

    branch = git('branch', '--show-current')
    print('LOCAL BRANCH:', branch.stdout.strip() if branch.returncode == 0 else 'unavailable')
    status = git('status', '--short', '--', *FILES)
    if status.returncode:
        print('WARNING: could not inspect working-tree status:', status.stderr.strip())
    elif status.stdout.strip():
        print('WARNING: local edits in protected files:')
        print(status.stdout.rstrip())
    else:
        print('Protected files: no uncommitted modifications reported by Git')

    research_ref = None
    for candidate in RESEARCH_REFS:
        check = git('rev-parse', '--verify', '--quiet', candidate + '^{commit}')
        if check.returncode == 0:
            research_ref = candidate
            break
    if research_ref is None:
        print('\nRESEARCH BRANCH: not available in local Git refs.')
        print('No network fetch attempted; no files modified.')
        print('NEXT: review the verified backup, then arrange a safe comparison with the remote research branch.')
        return 0

    print('\nRESEARCH REF:', research_ref)
    for name in FILES:
        result = git('show', research_ref + ':' + name)
        if result.returncode:
            print('\nWARNING: cannot read research version of', name)
            print(result.stderr.strip())
            continue
        local = (ROOT / name).read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
        remote = result.stdout.splitlines(keepends=True)
        diff = list(difflib.unified_diff(local, remote,
                    fromfile='PRODUCTION/' + name,
                    tofile='RESEARCH/' + name, n=3))
        print('\nFILE:', name)
        print('  Different lines in unified diff:', len(diff))
        if not diff:
            print('  Same content in working file and local research ref.')
        else:
            report_path = backup_dir / (Path(name).name + '.research.diff')
            report_path.write_text(''.join(diff), encoding='utf-8')
            print('  FULL DIFF SAVED:', report_path)
            print('  Preview (first 45 lines):')
            print(''.join(diff[:45]).rstrip())
            if len(diff) > 45:
                print('  ... additional lines in saved diff report')

    print('\nPRE-FLIGHT COMPLETE. NO DEPLOYMENT PERFORMED.')
    print('Please share the console output before we install anything.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('STOP: pre-flight failed:', type(exc).__name__, str(exc))
        sys.exit(1)
