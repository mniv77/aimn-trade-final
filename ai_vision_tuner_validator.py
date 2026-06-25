"""
ai_vision_tuner_validator.py
AiMN V3.1 - AI Vision Tuning Validator

After tuner finds best params, this validates the entry signals
by generating chart images and asking Claude Vision to confirm.

Usage:
    from ai_vision_tuner_validator import validate_strategy
    score = validate_strategy(strategy_id, symbol, direction, 
                              highs, lows, closes, timestamps, params)
"""

import os
import json
import tempfile
from datetime import datetime
from db import get_db_connection

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def find_entry_points(highs, lows, closes, direction, params, max_entries=10):
    """
    Re-run mini backtest to find actual entry candle indices.
    Returns list of entry bar indices.
    """
    from engine.tuning.auto_tuner import calc_rsi_real, calc_macd_series

    rsi_len   = params['rsi_len']
    rsi_entry = params['rsi_entry']
    macd_fast = params.get('macd_fast', 12)
    macd_slow = params.get('macd_slow', 26)
    macd_sig  = params.get('macd_sig',  9)

    n = len(closes)
    macd_line, _ = calc_macd_series(closes, macd_fast, macd_slow, macd_sig)
    start_bar = max(rsi_len, macd_slow + macd_sig) + 1

    entries = []
    in_trade = False

    for i in range(start_bar, n - 1):
        if not in_trade:
            rsi = calc_rsi_real(highs, lows, closes, i, rsi_len)
            if rsi is None:
                continue
            macd_curr = macd_line[i]
            if direction == 'LONG':
                entry_cond = (rsi <= rsi_entry) and (macd_curr > 0)
            else:
                entry_cond = (rsi >= (100 - rsi_entry)) and (macd_curr < 0)
            if entry_cond:
                entries.append(i)
                in_trade = True
                if len(entries) >= max_entries:
                    break
        else:
            # Simple exit after 20 bars to find next entry
            if i - entries[-1] > 20:
                in_trade = False

    return entries


def generate_entry_chart(symbol, highs, lows, closes, timestamps,
                          entry_bar, n_candles=60, outpath=None):
    """
    Generate a chart image centered around the entry bar.
    Shows n_candles candles with the entry point at ~80% from left.
    """
    try:
        import pandas as pd
        import mplfinance as mpf

        # Window: entry bar at ~80% from left
        start = max(0, entry_bar - int(n_candles * 0.8))
        end   = min(len(closes), start + n_candles)
        start = max(0, end - n_candles)  # adjust if near end

        rows = []
        for i in range(start, end):
            rows.append({
                'timestamp': pd.to_datetime(timestamps[i], unit='ms') if isinstance(timestamps[i], (int, float)) else pd.to_datetime(timestamps[i]),
                'open' : closes[max(0, i-1)],  # approximate open
                'high' : highs[i],
                'low'  : lows[i],
                'close': closes[i],
                'volume': 1  # placeholder
            })

        df = pd.DataFrame(rows)
        df = df.set_index('timestamp')
        df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

        if outpath is None:
            outpath = f"/tmp/validator_{symbol.replace('/','_')}_{entry_bar}.png"

        if os.path.exists(outpath):
            os.remove(outpath)

        mpf.plot(df, type='candle', volume=True, style='charles',
                 title=f"{symbol} Entry Bar {entry_bar}",
                 figsize=(10, 6),
                 savefig=dict(fname=outpath, dpi=100, bbox_inches='tight'))
        return outpath

    except Exception as e:
        log(f"  ❌ Chart generation error: {e}")
        return None


def validate_strategy(strategy_id, symbol, direction,
                      highs, lows, closes, timestamps, params,
                      min_entries=3, max_entries=8, required_score=0.60):
    """
    Validate a tuned strategy using AI Vision.
    
    Returns:
        score (float): 0.0 - 1.0 (fraction of entries AI confirmed)
        validated (bool): True if score >= required_score
    """
    from ai_vision_check import check_reversal

    log(f"\n  🤖 AI VISION VALIDATOR: {symbol} {direction}")
    log(f"  Parameters: RSI_len={params['rsi_len']} RSI_entry={params['rsi_entry']}")

    # Find entry points
    entries = find_entry_points(highs, lows, closes, direction, params, max_entries)
    log(f"  Found {len(entries)} entry points to validate")

    if len(entries) < min_entries:
        log(f"  ⚠️  Too few entries ({len(entries)} < {min_entries}) — skipping AI validation")
        return None, None

    # Validate each entry with AI Vision
    confirmed = 0
    total     = 0
    results   = []

    for i, entry_bar in enumerate(entries):
        chart_path = generate_entry_chart(
            symbol, highs, lows, closes, timestamps,
            entry_bar, n_candles=60,
            outpath=f"/tmp/validator_{symbol.replace('/','_')}_{i}.png"
        )

        if not chart_path or not os.path.exists(chart_path):
            log(f"  ❌ Chart failed for entry {i}")
            continue

        try:
            result    = check_reversal(chart_path, symbol, direction)
            verdict   = result.get('verdict', 'ERROR')
            reason    = result.get('reason', '')[:80]
            total    += 1

            if verdict == 'CONFIRMED':
                confirmed += 1
                log(f"  ✅ Entry {i+1}/{len(entries)}: CONFIRMED — {reason}")
            else:
                log(f"  ❌ Entry {i+1}/{len(entries)}: {verdict} — {reason}")

            results.append({'entry_bar': entry_bar, 'verdict': verdict})

            # Clean up chart
            try:
                os.remove(chart_path)
            except:
                pass

        except Exception as e:
            log(f"  ❌ AI check error for entry {i}: {e}")
            continue

    if total == 0:
        log(f"  ⚠️  No entries validated")
        return None, None

    score     = confirmed / total
    validated = score >= required_score

    log(f"  📊 AI VALIDATION SCORE: {confirmed}/{total} = {score:.0%}")
    log(f"  {'✅ VALIDATED' if validated else '❌ REJECTED'} (threshold={required_score:.0%})")

    # Save to DB
    try:
        conn, cursor = get_db_connection()
        cursor.execute("""
            UPDATE strategy_params
            SET ai_validated = %s,
                ai_validation_score = %s
            WHERE id = %s
        """, (1 if validated else 0, round(score, 4), strategy_id))
        conn.close()
        log(f"  ✅ Saved ai_validated={1 if validated else 0} score={score:.2%} to strategy_params id={strategy_id}")
    except Exception as e:
        log(f"  ❌ DB save error: {e}")

    return score, validated


if __name__ == "__main__":
    print("AI Vision Tuner Validator — run via auto_tuner.py")
