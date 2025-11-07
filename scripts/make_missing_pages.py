# scripts/make_missing_pages.py
from __future__ import annotations
import os
from pathlib import Path

TEMPLATES = {
    "orders.html": "📦 Orders",
    "trade-tester.html": "🧪 Trade Tester",
    "symbols.html": "🔣 Symbols",
    "simple-explanation.html": "📘 Simple Explanation",
    "architectural-analysis.html": "🏗️ Architectural Analysis",
    "scanner-analysis.html": "🛰️ Scanner Analysis",
    "scanner-simulator.html": "🎛️ Scanner Simulator",
    "beginner-guide.html": "🌱 Beginner Guide",
    "scanner/diagnostics.html": "🩺 Scanner Diagnostics",
    "aiml.html": "🤖 AI / ML",
    "tuning.html": "🎚️ Tuning",
}

BASE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100">
  <div class="max-w-5xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">{title}</h1>
      <a href="/" class="text-sm px-3 py-1 rounded bg-slate-700 hover:bg-slate-600">← Back</a>
    </div>
    <div class="rounded-xl border border-slate-700 p-6 bg-slate-800/60">
      <p class="opacity-80">This is a placeholder page. Replace with real content.</p>
    </div>
  </div>
</body></html>
"""

def ensure(path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(BASE.format(title=title), encoding="utf-8")
        print(f"Created: {path}")
    else:
        print(f"Exists:  {path}")

def main() -> None:
    templates_dir = Path("templates")
    for fname, title in TEMPLATES.items():
        ensure(templates_dir / fname, title)
    # minimal index.html if missing
    idx = templates_dir / "index.html"
    if not idx.exists():
        idx.write_text("""<!doctype html><meta charset='utf-8'>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/water.css@2/out/water.css">
<h1>AIMn Dashboard</h1>
<ul>
<li><a href="/scanner">Scanner</a></li>
<li><a href="/go/tuning">Tuning</a></li>
<li><a href="/go/orders">Orders</a></li>
<li><a href="/go/trade-tester">Trade Tester</a></li>
<li><a href="/go/symbols">Symbols</a></li>
<li><a href="/go/simple-explanation">Simple Explanation</a></li>
<li><a href="/go/architectural-analysis">Architectural Analysis</a></li>
<li><a href="/go/scanner-analysis">Scanner Analysis</a></li>
<li><a href="/go/scanner/diagnostics">Scanner Diagnostics</a></li>
<li><a href="/go/beginner-guide">Beginner Guide</a></li>
<li><a href="/go/aiml">AI/ML</a></li>
</ul>
""", encoding="utf-8")
        print("Created: templates/index.html")
    else:
        print("Exists:  templates/index.html")

if __name__ == "__main__":
    main()
