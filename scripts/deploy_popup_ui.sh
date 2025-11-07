#!/usr/bin/env bash
set -euo pipefail
SRC="${1:-/home/MeirNiv/aimn-trade-final}"
DEST="${2:-/home/MeirNiv/popup-trader-ui}"
mkdir -p "$DEST"/templates "$DEST"/static/snaps
copy() { local from="$SRC/$1" to="$DEST/$2"; if [[ -f "$from" ]]; then install -m 0644 -D "$from" "$to"; echo "copied: $from -> $to"; else echo "WARN: missing $from"; fi; }
copy requirements.txt requirements.txt
copy wsgi.py        wsgi.py
copy app.py         app.py
copy static/app.js  static/app.js
copy templates/base.html    templates/base.html
copy templates/index.html   templates/index.html
copy templates/orders.html  templates/orders.html
copy templates/demo_trigger.html templates/demo_trigger.html
chmod 775 "$DEST/static/snaps" || true
echo "Done. Next: set WSGI to $DEST/wsgi.py, map /static to $DEST/static, Reload."
