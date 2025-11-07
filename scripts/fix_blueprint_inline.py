# scripts/fix_blueprint_inline.py
from __future__ import annotations
import re
from pathlib import Path

APP = Path("app.py")

INLINE_START = re.compile(r"#\s*>>> trading_api START")
INLINE_END   = re.compile(r"#\s*>>> trading_api END")

def ensure_imports(src: str) -> str:
    need1 = "from blueprints.trading_api import trading_api"
    need2 = "from blueprints.credentials_api import credentials_api"
    if need1 not in src:
        # insert after first block of imports
        lines = src.splitlines()
        last_import = 0
        for i, ln in enumerate(lines[:200]):
            if re.match(r"^\s*(?:from\s+\S+\s+import|import\s+\S+)", ln):
                last_import = i
        lines.insert(last_import+1, need1)
        src = "\n".join(lines)
    if need2 not in src:
        lines = src.splitlines()
        last_import = 0
        for i, ln in enumerate(lines[:200]):
            if re.match(r"^\s*(?:from\s+\S+\s+import|import\s+\S+)", ln):
                last_import = i
        lines.insert(last_import+2, need2)
        src = "\n".join(lines)
    return src

def ensure_registration(src: str) -> str:
    # find app = Flask(...) line
    m = re.search(r"^(?P<i>\s*)app\s*=\s*Flask\([^)]*\)\s*$", src, re.MULTILINE)
    if not m:
        return src
    if "app.register_blueprint(trading_api)" in src and "app.register_blueprint(credentials_api)" in src:
        return src
    insert_at = m.end()
    before, after = src[:insert_at], src[insert_at:]
    inject = ""
    if "app.register_blueprint(trading_api)" not in src:
        inject += f"\n{m.group('i')}app.register_blueprint(trading_api)"
    if "app.register_blueprint(credentials_api)" not in src:
        inject += f"\n{m.group('i')}app.register_blueprint(credentials_api)"
    return before + inject + "\n" + after

def remove_inline_block(src: str) -> str:
    lines = src.splitlines()
    s_idx = e_idx = None
    for i, ln in enumerate(lines):
        if INLINE_START.search(ln):
            s_idx = i
        if INLINE_END.search(ln):
            e_idx = i
            break
    if s_idx is not None and e_idx is not None and e_idx >= s_idx:
        del lines[s_idx:e_idx+1]
        return "\n".join(lines) + "\n"
    return src

def main():
    if not APP.exists():
        raise SystemExit("app.py not found.")
    src = APP.read_text(encoding="utf-8")

    # 1) remove inline blueprint block (if present)
    new = remove_inline_block(src)

    # 2) ensure external imports present
    new = ensure_imports(new)

    # 3) ensure registration after app = Flask(...)
    new = ensure_registration(new)

    if new != src:
        APP.write_text(new, encoding="utf-8")
        print("✅ app.py updated (inline blueprint removed, imports/registration ensured).")
    else:
        print("ℹ️ No changes needed.")

if __name__ == "__main__":
    main()
