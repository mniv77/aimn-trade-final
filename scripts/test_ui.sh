#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://meirniv.pythonanywhere.com}"
BROWSER="${BROWSER:-firefox}"
TIMEOUT_MS="${TIMEOUT_MS:-45000}"

export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
mkdir -p artifacts

echo "Running UI tests against: ${BASE_URL}  (browser=${BROWSER}, timeout=${TIMEOUT_MS}ms)"
python -m pytest tests/test_scanner_state_no_popup.py \
  --base "${BASE_URL}" --timeout "${TIMEOUT_MS}" --browser "${BROWSER}" -q -rs
python -m pytest tests/test_scanner_reset_ui_only.py \
  --base "${BASE_URL}" --timeout "${TIMEOUT_MS}" --browser "${BROWSER}" -q -rs
echo "✅ Done. Screenshots (if any) are in ./artifacts"
