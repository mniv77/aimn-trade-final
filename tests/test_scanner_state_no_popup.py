# =========================================
# File: tests/test_scanner_state_no_popup.py
# =========================================
from __future__ import annotations
from pathlib import Path
from tests.utils import goto_scanner, wait_for_dom_trade_state

def test_trade_state_without_popup(pw_context, page, base_url: str, artifacts_dir: Path):
    goto_scanner(page, base_url)
    page.screenshot(path=str(artifacts_dir / "state_scanner_loaded.png"))
    # Trigger manual stock test; popup may be blocked, but UI should flip to TRADING
    page.evaluate("() => { if (typeof openTradePopupTestStock === 'function') openTradePopupTestStock(); }")
    ok = wait_for_dom_trade_state(page, symbol="AAPL", exchange="ALPACA", timeout_ms=15000)
    page.screenshot(path=str(artifacts_dir / "state_after_trigger.png"))
    assert ok, "UI did not reflect active trade for AAPL/ALPACA."