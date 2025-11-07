# =========================================
# File: tests/utils.py
# =========================================
from __future__ import annotations
from playwright.sync_api import Page

def goto_scanner(page: Page, base_url: str) -> None:
    # why: root "/" can be slower; go straight to /scanner
    page.goto(f"{base_url}/scanner", wait_until="domcontentloaded")
    page.wait_for_selector("#scan-results", state="attached")

def wait_for_dom_trade_state(page: Page, symbol: str, exchange: str, timeout_ms: int = 10000) -> bool:
    # Row shows active 'TRADING'
    try:
        row = page.locator("#scan-results .symbol-busy-active", has_text=symbol)
        row.wait_for(state="visible", timeout=timeout_ms)
        return True
    except Exception:
        pass
    # Broker panel shows "TRADING: <symbol>"
    try:
        broker = page.locator("#exchange-status > div", has_text=exchange)
        broker.locator(f"text=TRADING: {symbol}").wait_for(state="visible", timeout=timeout_ms)
        return True
    except Exception:
        return False

def wait_for_broker_available(page: Page, exchange: str, timeout_ms: int = 10000) -> bool:
    try:
        broker = page.locator("#exchange-status > div", has_text=exchange)
        broker.locator("text=AVAILABLE").wait_for(state="visible", timeout=timeout_ms)
        return True
    except Exception:
        return False