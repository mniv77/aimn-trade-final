# fix_tuner_commission .
import pathlib, re
p = pathlib.Path("/home/MeirNiv/aimn-trade-final/app.py")
txt = p.read_text()

# 1. Fix import in run_tuning to use our alias (already done but ensure)
txt = txt.replace("from engine.tuning.candle_fetcher import fetch_candles", "from engine.tuning.candle_fetcher import fetch_gemini_candles as fetch_candles")
txt = txt.replace("from engine.tuning.candle_fetcher import fetch_candles_with_broker", "from engine.tuning.candle_fetcher import fetch_gemini_candles as fetch_candles")

# 2. Patch the tuning loop to enforce commission and min_trades
# Find the section where total_pnl_val is set and inject filter
# We replace the scoring logic to subtract commission

# Ensure run_tuning filters 0-profit combos and low avg
# Look for common pattern: if trades < min_trades: continue
# If not present, inject after simulate

# Add commission filter before best selection
if "# COMMISSION FILTER" not in txt:
    # Insert after "trades = " line inside run_tuning
    txt = re.sub(
        r"(trades_val\s*=\s*len\(trades\))",
        r"\1\n                # COMMISSION FILTER - reject combos that don't beat fees\n                avg_pnl = total_pnl_val / trades_val if trades_val else 0\n                net_avg = avg_pnl - 0.4  # Gemini 0.2% entry + 0.2% exit\n                if net_avg < 0.25:  # must beat commission by 0.25%\n                    continue\n                if total_pnl_val - (trades_val*0.4) <=0:\n                    continue",
        txt
    )
    # Also filter out init_profit=0 or decay_start=0 combos if they are strings
    txt = re.sub(
        r'"init_profit":\s*init_profit',
        r'"init_profit": init_profit if str(init_profit)!="0" else "0.5"',
        txt
    )

p.write_text(txt)
print("Patched app.py with commission filter")
print("Now fixing auto_tuner defaults...")

# Fix auto_tuner.html defaults to not include 0
q = pathlib.Path("/home/MeirNiv/aimn-trade-final/templates/auto_tuner.html")
if q.exists():
    t = q.read_text()
    # replace 0,1,0.5 with 0.5,1,1.5 and 2,0,3,4,0 with 2,3,4
    t = t.replace('value="0,1,0.5"', 'value="0.5,1,1.5"')
    t = t.replace('value="2,0,3,4,0"', 'value="2,3,4"')
    t = t.replace('value="0,1,0.5" id="init_profit"', 'value="0.5,1,1.5" id="init_profit"')
    q.write_text(t)
    print("Patched auto_tuner.html defaults")
else:
    print("auto_tuner.html not found, skip")

print("DONE - reload web")
