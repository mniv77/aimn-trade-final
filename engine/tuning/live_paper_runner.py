# engine/tuning/live_paper_runner.py
import time
import json
import os
import sys
import numpy as np
from datetime import datetime

# Add root directory to sys.path so 'db' can be imported correctly when run from engine/tuning/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from db import get_db_connection

def calculate_rsi(closes, period=14):
    """Calculates Relative Strength Index (RSI) using NumPy."""
    if len(closes) < period + 1:
        return 50.0
    delta = np.diff(closes)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    
    avg_gain = np.mean(gain[:period])
    avg_loss = np.mean(loss[:period])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

class LivePaperTrader:
    def __init__(self, symbol="BTCUSDT", timeframe="1hr", direction="LONG", rsi_len=50, rsi_entry=40.0, stop_loss=0.3, trail_start=1.5, trail_drop=0.3):
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = direction
        self.rsi_len = rsi_len
        self.rsi_entry = rsi_entry
        self.stop_loss = stop_loss
        self.trail_start = trail_start
        self.trail_drop = trail_drop
        
        self.position = None  # None, 'LONG' / 'SHORT'
        self.entry_price = 0.0
        self.highest_price = 0.0
        self.lowest_price = 0.0
        self.paper_balance = 10000.0  # Starting mock balance ($10,000)
        
        # Initialize rolling simulation state for live fallback feed
        np.random.seed(None)
        base_price = 90000.0 if "BTC" in self.symbol else 300.0
        self.sim_history = list(base_price + np.cumsum(np.random.randn(100) * (base_price * 0.001)))

    def fetch_latest_candles(self, limit=100):
        """Fetches latest candles from the database, or advances the live simulation feed forward."""
        try:
            db_res = get_db_connection()
            conn = None
            cur = None
            
            if isinstance(db_res, tuple):
                conn, cur = db_res
            else:
                conn = db_res
                if conn and hasattr(conn, 'cursor'):
                    cur = conn.cursor()

            if not cur and conn:
                cur = conn.cursor()

            rows = []
            if cur:
                cur.execute(
                    "SELECT open, high, low, close, timestamp FROM candles WHERE symbol=%s AND timeframe=%s ORDER BY timestamp DESC LIMIT %s",
                    (self.symbol, self.timeframe, limit)
                )
                rows = cur.fetchall()
                cur.close()
            if conn:
                conn.close()
            
            if rows:
                rows.reverse()
                closes, highs, lows = [], [], []
                for r in rows:
                    if isinstance(r, dict):
                        closes.append(float(r.get('close', 0)))
                        highs.append(float(r.get('high', 0)))
                        lows.append(float(r.get('low', 0)))
                    else:
                        closes.append(float(r[3]))
                        highs.append(float(r[1]))
                        lows.append(float(r[2]))
                return closes, highs, lows

            # Fallback: Advance live simulation price forward step-by-step
            last_price = self.sim_history[-1]
            step = np.random.randn() * (last_price * 0.0015)
            new_price = last_price + step
            self.sim_history.append(new_price)
            if len(self.sim_history) > 200:
                self.sim_history.pop(0)
                
            closes = self.sim_history[-limit:]
            highs = [c * 1.001 for c in closes]
            lows = [c * 0.999 for c in closes]
            return closes, highs, lows

        except Exception as e:
            last_price = self.sim_history[-1]
            new_price = last_price + (np.random.randn() * (last_price * 0.0015))
            self.sim_history.append(new_price)
            closes = self.sim_history[-limit:]
            highs = [c * 1.001 for c in closes]
            lows = [c * 0.999 for c in closes]
            return closes, highs, lows

    def evaluate_market(self):
        """Evaluates live candle feeds for entry and exit signals."""
        closes, highs, lows = self.fetch_latest_candles(limit=max(60, self.rsi_len + 10))
        if len(closes) < self.rsi_len + 2:
            print(f"[PAPER TRADER] Waiting for enough candle data... ({len(closes)} loaded, need {self.rsi_len + 2})")
            return

        current_price = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]
        
        rsi = calculate_rsi(np.array(closes), period=self.rsi_len)
        
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pos_str = self.position or 'NONE'
        print(f"[{now_str}] {self.symbol} ({self.timeframe}) | Price: {current_price:.2f} | RSI: {rsi:.2f} | Position: {pos_str} | Balance: ${self.paper_balance:.2f}")

        # Manage Open Position Exits
        if self.position == 'LONG':
            if current_high > self.highest_price:
                self.highest_price = current_high
            
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100.0
            max_gain_pct = ((self.highest_price - self.entry_price) / self.entry_price) * 100.0
            drop_from_peak = max_gain_pct - pnl_pct
            
            exit_triggered = False
            exit_reason = ""
            
            if pnl_pct <= -self.stop_loss:
                exit_triggered = True
                exit_reason = "STOP_LOSS"
            elif max_gain_pct >= self.trail_start and drop_from_peak >= self.trail_drop:
                exit_triggered = True
                exit_reason = "TRAILING_STOP"
                
            if exit_triggered:
                trade_pnl_dollar = (pnl_pct / 100.0) * self.paper_balance
                self.paper_balance += trade_pnl_dollar
                print(f"--> [EXIT LONG ({exit_reason})] Price: {current_price:.2f} | PnL: {pnl_pct:.2f}% | New Balance: ${self.paper_balance:.2f}")
                self.position = None
                self.entry_price = 0.0
                self.highest_price = 0.0

        elif self.position == 'SHORT':
            if current_low < self.lowest_price:
                self.lowest_price = current_low
            
            pnl_pct = ((self.entry_price - current_price) / self.entry_price) * 100.0
            max_gain_pct = ((self.entry_price - self.lowest_price) / self.entry_price) * 100.0
            drop_from_peak = max_gain_pct - pnl_pct
            
            exit_triggered = False
            exit_reason = ""
            
            if pnl_pct <= -self.stop_loss:
                exit_triggered = True
                exit_reason = "STOP_LOSS"
            elif max_gain_pct >= self.trail_start and drop_from_peak >= self.trail_drop:
                exit_triggered = True
                exit_reason = "TRAILING_STOP"
                
            if exit_triggered:
                trade_pnl_dollar = (pnl_pct / 100.0) * self.paper_balance
                self.paper_balance += trade_pnl_dollar
                print(f"--> [EXIT SHORT ({exit_reason})] Price: {current_price:.2f} | PnL: {pnl_pct:.2f}% | New Balance: ${self.paper_balance:.2f}")
                self.position = None
                self.entry_price = 0.0
                self.lowest_price = 0.0

        # Look for New Entry
        elif self.position is None:
            if self.direction == 'LONG' and rsi <= self.rsi_entry:
                self.position = 'LONG'
                self.entry_price = current_price
                self.highest_price = current_high
                print(f"--> [ENTER LONG] Price: {current_price:.2f} | RSI triggered at {rsi:.2f}")
            elif self.direction == 'SHORT' and rsi >= (100.0 - self.rsi_entry):
                self.position = 'SHORT'
                self.entry_price = current_price
                self.lowest_price = current_low
                print(f"--> [ENTER SHORT] Price: {current_price:.2f} | RSI triggered at {rsi:.2f}")

if __name__ == "__main__":
    print("=== STARTING LIVE PAPER TRADER ===")
    
    trader = LivePaperTrader(
        symbol="BTCUSDT",
        timeframe="1hr",
        direction="LONG",
        rsi_len=50,
        rsi_entry=40.0,
        stop_loss=0.3,
        trail_start=1.5,
        trail_drop=0.3
    )
    
    print(f"[PAPER TRADER] Starting live runner for {trader.symbol} ({trader.timeframe}) - Direction: {trader.direction}")
    print(f"[PAPER TRADER] Active Strategy Params -> RSI Len: {trader.rsi_len}, Entry: {trader.rsi_entry}, SL: {trader.stop_loss}%")
    
    try:
        while True:
            trader.evaluate_market()
            time.sleep(3)
    except KeyboardInterrupt:
        print("\n[PAPER TRADER] Stopped safely by user.")