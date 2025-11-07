# scripts/fix_future_imports.py
# Usage: python scripts/fix_future_imports.py
from __future__ import annotations
import io, re
from pathlib import Path

APP = Path("app.py")

FUTURE_RE = re.compile(r'^\s*from\s+__future__\s+import\s+([a-zA-Z0-9_,\s]+)\s*$')

def main() -> None:
    if not APP.exists():
        raise SystemExit("app.py not found in current directory.")
    src = APP.read_text(encoding="utf-8").splitlines(keepends=False)

    # 1) Collect leading header (shebang, encoding, comments, docstring)
    i = 0
    out = []

    # Shebang/encoding/comments block
    while i < len(src) and (
        src[i].startswith("#!") or
        src[i].startswith("#") or
        src[i].strip() == ""    # blank lines allowed in header
    ):
        out.append(src[i])
        i += 1

    # Optional module docstring
    def starts_triple_quote(line: str) -> bool:
        s = line.strip()
        return (s.startswith('"""') or s.startswith("'''"))
    if i < len(src) and starts_triple_quote(src[i]):
        quote = '"""' if src[i].strip().startswith('"""') else "'''"
        out.append(src[i]); i += 1
        while i < len(src):
            out.append(src[i])
            if src[i].strip().endswith(quote):
                i += 1
                break
            i += 1

    # 2) Scan entire file for future import lines, remove them in-place
    futures: list[str] = []
    body = []
    for line in src[i:]:
        m = FUTURE_RE.match(line)
        if m:
            futures.append(m.group(1))
        else:
            body.append(line)

    # 3) De-duplicate merged futures
    merged = []
    seen = set()
    for part in ",".join(futures).split(","):
        name = part.strip()
        if name and name not in seen:
            seen.add(name)
            merged.append(name)

    # 4) Rebuild file: header + future import (if any) + newline + body
    buf = io.StringIO()
    for line in out:
        buf.write(line + "\n")
    if merged:
        buf.write(f"from __future__ import {', '.join(merged)}\n")
    # ensure one blank line after future import
    if merged and (not body or body[0].strip() != ""):
        buf.write("\n")
    for line in body:
        buf.write(line + "\n")

    APP.write_text(buf.getvalue(), encoding="utf-8")
    print("✅ Fixed future imports in app.py")

if __name__ == "__main__":
    main()
