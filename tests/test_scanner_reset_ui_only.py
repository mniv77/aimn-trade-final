# =========================================
# File: tests/test_scanner_reset_ui_only.py
# =========================================
from __future__ import annotations
from pathlib import Path
from tests.utils import goto_scanner, wait_for_dom_trade_state, wait_for_broker_available

def test_trade_resets_to_available_without_backend(pw_context, page, base_url: str, artifacts_dir: Path):
    goto_scanner(page, base_url)
    page.screenshot(path=str(artifacts_dir / "reset_loaded.png"))
    # Enter TRADING state
    page.evaluate("() => { if (typeof openTradePopupTestStock === 'function') openTradePopupTestStock(); }")
    assert wait_for_dom_trade_state(page, symbol="AAPL", exchange="ALPACA", timeout_ms=15000)
    page.screenshot(path=str(artifacts_dir / "reset_trading.png"))
    # Simulate popup closing -> scanner listens for postMessage and should reset
    page.evaluate("""() => {
        window.postMessage({ type:'TRADE_CLOSED', symbol:'AAPL', exchange:'ALPACA', pnl:'0', reason:'ui-only' }, '*');
    }""")
    assert wait_for_broker_available(page, exchange="ALPACA", timeout_ms=15000)
    page.screenshot(path=str(artifacts_dir / "reset_available.png"))