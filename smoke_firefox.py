from playwright.sync_api import sync_playwright
URL = "https://meirniv.pythonanywhere.com/scanner"
with sync_playwright() as pw:
    b = pw.firefox.launch(headless=True)
    ctx = b.new_context()
    p = ctx.new_page()
    p.goto(URL, wait_until="domcontentloaded", timeout=30000)
    print("OK title:", p.title())
    b.close()
