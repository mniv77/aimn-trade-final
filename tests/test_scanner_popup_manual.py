# File: tests/test_scanner_popup_manual.py
from __future__ import annotations
from pathlib import Path
from tests.utils import (
    goto_scanner, enable_preopen, click_manual_stock,
    wait_for_trade_popup, setup_console_capture, wait_for_dom_trade_state
)

def test_manual_popup_opens(pw_context, page, base_url: str, artifacts_dir: Path):
    logs = setup_console_capture(page)
    goto_scanner(page, base_url)
    page.screenshot(path=str(artifacts_dir / "manual_scanner_loaded.png"))

    pre = enable_preopen(pw_context, page)
    page.screenshot(path=str(artifacts_dir / "manual_preopen.png"))

    assert click_manual_stock(page), "Manual Test - Stock button not found or not clickable"

    popup = wait_for_trade_popup(pw_context, page, pre_popup=pre)
    if popup is not None:
        popup.wait_for_load_state("domcontentloaded")
        popup.screenshot(path=str(artifacts_dir / "manual_popup_ok.png"))
        return

    # Fallback: UI proves trade state
    ok = wait_for_dom_trade_state(page, symbol="AAPL", exchange="ALPACA", timeout=8000)
    page.screenshot(path=str(artifacts_dir / "manual_no_popup.png"))
    with open(artifacts_dir / "manual_console.log", "w", encoding="utf-8") as f:
        f.write("\n".join(logs))
    assert ok, "No popup and UI did not reflect active trade for AAPL/ALPACA."
