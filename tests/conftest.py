# =========================================
# File: tests/conftest.py
# =========================================
from __future__ import annotations
import os
from pathlib import Path
import pytest

pytest.importorskip(
    "playwright",
    reason="Playwright not installed. Run: pip install -r Requirements.txt && python -m playwright install",
)

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--base", action="store",
                     default=os.getenv("AIMN_BASE_URL", "http://127.0.0.1:5000"),
                     help="Base URL of the app")
    parser.addoption("--headed", action="store_true",
                     default=bool(int(os.getenv("AIMN_HEADED", "0"))),
                     help="Run browser headed")
    parser.addoption("--timeout", action="store", type=int,
                     default=int(os.getenv("AIMN_TIMEOUT_MS", "45000")),
                     help="Default Playwright timeout (ms)")
    parser.addoption("--slowmo", action="store", type=int,
                     default=int(os.getenv("AIMN_SLOWMO_MS", "0")),
                     help="Slow motion (ms)")
    parser.addoption("--artifacts", action="store",
                     default=os.getenv("AIMN_ARTIFACTS_DIR", "artifacts"),
                     help="Screenshots/output directory")
    parser.addoption("--browser", action="store",
                     default=os.getenv("AIMN_BROWSER", "auto"),
                     choices=["auto","firefox","webkit","chromium"],
                     help="Browser engine preference")

@pytest.fixture(scope="session")
def base_url(pytestconfig) -> str:
    return str(pytestconfig.getoption("--base")).rstrip("/")

@pytest.fixture(scope="session")
def artifacts_dir(pytestconfig) -> Path:
    p = Path(str(pytestconfig.getoption("--artifacts"))); p.mkdir(parents=True, exist_ok=True)
    return p

def _launch_with_fallback(pw, pref: str, headed: bool, slowmo: int):
    order = {"auto": ["firefox","webkit","chromium"],
             "firefox": ["firefox"], "webkit": ["webkit"], "chromium": ["chromium"]}[pref]
    errs = []
    for which in order:
        try:
            if which == "chromium":
                return pw.chromium.launch(
                    headless=not headed, slow_mo=slowmo or None,
                    # why: hosted envs
                    args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu","--no-zygote","--single-process"],
                ), which
            if which == "firefox":
                return pw.firefox.launch(headless=not headed, slow_mo=slowmo or None), which
            return pw.webkit.launch(headless=not headed, slow_mo=slowmo or None), which
        except Exception as e:
            errs.append(f"{which}: {e}")
    raise RuntimeError("No Playwright browser could launch.\n" + "\n".join(errs))

@pytest.fixture(scope="session")
def pw_context(pytestconfig):
    from playwright.sync_api import sync_playwright
    headed  = bool(pytestconfig.getoption("--headed"))
    timeout = int(pytestconfig.getoption("--timeout"))
    slowmo  = int(pytestconfig.getoption("--slowmo"))
    pref    = str(pytestconfig.getoption("--browser"))
    with sync_playwright() as pw:
        try:
            browser, _ = _launch_with_fallback(pw, pref, headed, slowmo)
        except Exception as e:
            pytest.skip(f"Playwright could not launch on this host:\n{e}")
        ctx = browser.new_context()
        ctx.set_default_timeout(timeout)
        ctx.set_default_navigation_timeout(timeout)
        yield ctx
        try:
            browser.close()
        except Exception:
            pass

@pytest.fixture()
def page(pw_context):
    p = pw_context.new_page()
    yield p
    try:
        p.close()
    except Exception:
        pass