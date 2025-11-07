# scripts/clean_blueprint_conflict.py
from __future__ import annotations
import re
from pathlib import Path

APP = Path("app.py")

INLINE_START = re.compile(r"#\s*>>> trading_api START")
INLINE_END   = re.compile(r"#\s*>>> trading_api END")

def remove_marked_block(text: str) -> str:
    lines = text.splitlines()
    s = e = None
    for i, ln in enumerate(lines):
        if INLINE_START.search(ln): s = i
        if INLINE_END.search(ln): e = i
    if s is not None and e is not None and e >= s:
        del lines[s:e+1]
        return "\n".join(lines) + "\n"
    return text

# Remove any @trading_api.route(...) def ... blocks that slipped into app.py
ROUTE_BLOCK = re.compile(
    r"""@trading_api\.route\([^\)]*\)\s*      # decorator
        def\s+\w+\(.*?\):\s*                  # function header
        (?:[^@]|\n(?!@))*?                    # body until next decorator-like line
        (?=\n@\w|\n\s*app\.register_blueprint|\Z)""",
    re.DOTALL | re.VERBOSE,
)

def remove_inline_routes(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = ROUTE_BLOCK.sub("", text)
    return text

def ensure_single_registration(text: str) -> str:
    # Keep first occurrence after app = Flask(...), drop duplicates
    regs = [m for m in re.finditer(r"^\s*app\.register_blueprint\(\s*trading_api\s*\)\s*$", text, re.MULTILINE)]
    if len(regs) > 1:
        # remove all but the first
        keep = regs[0].span()
        pieces = []
        last = 0
        for i, m in enumerate(regs):
            if i == 0:
                continue
            pieces.append(text[last:m.start()])
            last = m.end()
        pieces.append(text[last:])
        # reconstruct by inserting the kept line at its original place
        text = text  # we’ll do a simpler pass:
        count = 0
        def repl(_):
            nonlocal count
            count += 1
            return "" if count > 1 else _.group(0)
        text = re.sub(r"^\s*app\.register_blueprint\(\s*trading_api\s*\)\s*$", repl, text, flags=re.MULTILINE)
    return text

def ensure_imports(text: str) -> str:
    need = [
        "from blueprints.trading_api import trading_api",
        "from blueprints.credentials_api import credentials_api",
    ]
    if all(n in text for n in need):
        return text
    lines = text.splitlines()
    last_import = 0
    for i, ln in enumerate(lines[:200]):
        if re.match(r"^\s*(?:from\s+\S+\s+import|import\s+\S+)", ln):
            last_import = i
    for off, n in enumerate(need):
        if n not in text:
            lines.insert(last_import + 1 + off, n)
    return "\n".join(lines) + ("\n" if not text.endswith("\n") else "")

def main():
    if not APP.exists():
        raise SystemExit("app.py not found")
    src = APP.read_text(encoding="utf-8")
    orig = src

    src = remove_marked_block(src)
    src = remove_inline_routes(src)
    src = ensure_imports(src)
    src = ensure_single_registration(src)

    if src != orig:
        APP.write_text(src, encoding="utf-8")
        print("✅ Cleaned app.py (removed inline trading_api routes / deduped registration).")
    else:
        print("ℹ️ No changes needed.")

if __name__ == "__main__":
    main()
