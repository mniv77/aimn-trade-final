# File: tests/test_scanner_popup_auto.py
from __future__ import annotations
from pathlib import Path
from tests.utils import (
    goto_scanner, enable_preopen, wait_for_trade_popup,
    setup_console_capture, wait_for_dom_trade_state
)

AUTO_FORCE_JS = """
() => {
  try { activeTradeExchange = null; activeTradeSymbol = null; } catch {}
  try { lastPopupTime = 0; } catch {}
  try { openedPopups = new Set(); } catch {}
  const idx = (typeof testingRowIndex !== 'undefined') ? testingRowIndex : 3;
  const row = { symbol:'AAPL', exchange:'ALPACA', signal:'BUY', quantity:10,
                price:'175.50', change:'+2.5', rsi:'65.3', volume:'1000000' };
  try { scanData[idx] = row; } catch(e) { window.scanData = []; window.testingRowIndex = 3; window.scanData[3] = row; }
  if (typeof checkAndOpenPopups === 'function') checkAndOpenPopups();
  else if (typeof openTradePopupForSignal === 'function') openTradePopupForSignal(row);
}
"""

def test_auto_popup_triggers(pw_context, page, base_url: str, artifacts_dir: Path):
    logs = setup_console_capture(page)
    goto_scanner(page, base_url)
    page.screenshot(path=str(artifacts_dir / "auto_scanner_loaded.png"))

    pre = enable_preopen(pw_context, page)
    page.screenshot(path=str(artifacts_dir / "auto_preopen.png"))

    page.evaluate(AUTO_FORCE_JS)

    popup = wait_for_trade_popup(pw_context, page, pre_popup=pre)
    if popup is not None:
        popup.wait_for_load_state("domcontentloaded")
        popup.screenshot(path=str(artifacts_dir / "auto_popup_ok.png"))
        return

    # Fallback: UI proves trade state
    ok = wait_for_dom_trade_state(page, symbol="AAPL", exchange="ALPACA", timeout=8000)
    page.screenshot(path=str(artifacts_dir / "auto_no_popup.png"))
    with open(artifacts_dir / "auto_console.log", "w", encoding="utf-8") as f:
        f.write("\n".join(logs))
    assert ok, "No popup and UI did not reflect active trade for AAPL/ALPACA."
