"""
AIV Scanner v4 - CLEAN STABLE VERSION
- Entry + Exit + Scaling + Trailing + Re-entry
- Anti-chop protection
- Position-aware logic
"""

import pandas as pd
from typing import Dict, Optional

from v_classifier import VClassifier
from trade_memory import TradeMemory
from position_manager import PositionManager
from indicators import AIMnIndicators


class AIMnScanner:

    def __init__(self, symbol_params: Dict[str, Dict]):
        self.symbol_params = symbol_params
        self.v_engine = VClassifier()
        self.memory = TradeMemory()
        self.position_manager = PositionManager()

    # ---------------------------
    # GLOBAL TREND
    # ---------------------------
    def get_global_trend(self, df: pd.DataFrame) -> str:
        if df is None or len(df) < 50:
            return "UNKNOWN"

        fast = df["close"].rolling(20).mean().iloc[-1]
        slow = df["close"].rolling(50).mean().iloc[-1]

        if fast > slow:
            return "UP"
        elif fast < slow:
            return "DOWN"
        return "SIDEWAYS"

    # ---------------------------
    # CHOP FILTER
    # ---------------------------
    def is_chop_market(self, df: pd.DataFrame) -> bool:
        if df is None or len(df) < 50:
            return True

        ema_fast = df["close"].ewm(span=20).mean().iloc[-1]
        ema_slow = df["close"].ewm(span=50).mean().iloc[-1]

        trend_strength = abs(ema_fast - ema_slow) / ema_slow

        recent = df.tail(30)
        price_range = (recent["high"].max() - recent["low"].min()) / recent["close"].iloc[-1]

        volatility = df["close"].pct_change().rolling(10).std().iloc[-1]

        if trend_strength < 0.002 and price_range < 0.01:
            return True

        if volatility < 0.002:
            return True

        return False

    # ---------------------------
    # RE-ENTRY LOGIC
    # ---------------------------
    def detect_reentry(self, df: pd.DataFrame, trend: str) -> bool:
        if df is None or len(df) < 30:
            return False

        recent = df.tail(10)
        pullback = (recent["close"].iloc[-1] - recent["close"].iloc[0]) / recent["close"].iloc[0]

        if trend == "UP":
            return pullback < -0.002
        if trend == "DOWN":
            return pullback > 0.002

        return False

    # ---------------------------
    # EXIT ENGINE
    # ---------------------------
    def get_exit_signal(self, df: pd.DataFrame, symbol: str):

        pos = self.position_manager.get_position(symbol)
        if not pos:
            return None

        if df is None or len(df) < 50:
            return None
            
        # ---------------------------
        # EXHAUSTION EXIT (NEW)
        # ---------------------------
        if self.check_exhaustion_exit(df, pos):
            self.position_manager.close_position(symbol)
            return "EXHAUSTION_EXIT"            

        trend = self.get_global_trend(df)
        price = df["close"].iloc[-1]

        entry = pos["entry_price"]
        direction = pos["direction"]

        move = (price - entry) / entry

        # trend flip exit
        if direction == "LONG" and trend == "DOWN":
            self.position_manager.close_position(symbol)
            return "TREND_EXIT"

        if direction == "SHORT" and trend == "UP":
            self.position_manager.close_position(symbol)
            return "TREND_EXIT"

        # profit take
        if direction == "LONG" and move > 0.03:
            self.position_manager.close_position(symbol)
            return "TAKE_PROFIT"

        if direction == "SHORT" and move < -0.03:
            self.position_manager.close_position(symbol)
            return "TAKE_PROFIT"

        # stop loss
        if direction == "LONG" and move < -0.015:
            self.position_manager.close_position(symbol)
            return "STOP_LOSS"

        if direction == "SHORT" and move > 0.015:
            self.position_manager.close_position(symbol)
            return "STOP_LOSS"

        return None

    # ---------------------------
    # TRAILING STOP
    # ---------------------------
    def check_trailing_stop(self, symbol: str, df: pd.DataFrame):

        pos = self.position_manager.get_position(symbol)
        if not pos:
            return False

        price = df["close"].iloc[-1]
        self.position_manager.update_price(symbol, price)

        peak = pos["peak"]
        trough = pos["trough"]
        direction = pos["direction"]

        if direction == "LONG":
            if (peak - price) / peak > 0.012:
                self.position_manager.close_position(symbol)
                return True

        if direction == "SHORT":
            if (price - trough) / trough > 0.012:
                self.position_manager.close_position(symbol)
                return True

        return False

    # ---------------------------
    # PROFIT SCALING
    # ---------------------------
    def check_profit_scaling(self, symbol: str, df: pd.DataFrame):

        pos = self.position_manager.get_position(symbol)
        if not pos:
            return None

        price = df["close"].iloc[-1]
        entry = pos["entry_price"]
        direction = pos["direction"]

        move = (price - entry) / entry

        if pos["partials"] == 0:
            if direction == "LONG" and move > 0.015:
                pos["partials"] += 1
                return "PARTIAL_1"

            if direction == "SHORT" and move < -0.015:
                pos["partials"] += 1
                return "PARTIAL_1"

        if pos["partials"] == 1:
            if direction == "LONG" and move > 0.03:
                pos["partials"] += 1
                return "PARTIAL_2"

            if direction == "SHORT" and move < -0.03:
                pos["partials"] += 1
                return "PARTIAL_2"

        return None

    # ---------------------------
    # MAIN SCAN
    # ---------------------------
    def scan_symbol(self, symbol: str, df: pd.DataFrame):

        if df is None or len(df) < 60:
            return None

        if self.position_manager.has_position(symbol):
            return None

        df_ind = AIMnIndicators.calculate_all_indicators(df, self.symbol_params.get(symbol, {}))

        if self.is_chop_market(df_ind):
            return None
            
        # SPIKE FILTER (NEW)
        if self.is_liquidity_spike(df_ind):
            return None     

        trend = self.get_global_trend(df_ind)
        v_signal = VClassifier().classify_v(df_ind)

        normal = v_signal.get("trade_allowed", False)
        reentry = self.detect_reentry(df_ind, trend)

        if not entry_quality:
            return None

        price = df_ind["close"].iloc[-1]

        if reentry:
            direction = "LONG" if trend == "UP" else "SHORT"
            entry_type = "REENTRY"
        else:
            direction = v_signal.get("direction")
            entry_type = "NORMAL"

        if direction is None:
            return None

        self.position_manager.open_position(symbol, direction, price, entry_type)

        return {
            "symbol": symbol,
            "direction": direction,
            "entry_price": price,
            "entry_type": entry_type,
            "trend": trend,
            "v_type": v_signal.get("v_type", "UNKNOWN")
        }
        
        
        
        
        
        
        
        
        
        
        
        
    def check_exhaustion_exit(self, df: pd.DataFrame, position: dict) -> bool:
        """
        Exhaustion Exit v1:
        detects late entries and momentum fade
        """

        if df is None or len(df) < 50:
            return False

        rsi = df["rsi_real"].iloc[-1] if "rsi_real" in df else None
        if rsi is None:
            return False

        recent = df.tail(10)
        price = df["close"].iloc[-1]

        direction = position.get("direction")
        entry = position.get("entry_price")

        if entry is None:
            return False

        # ---------------------------
        # LONG EXHAUSTION
        # ---------------------------
        if direction == "LONG":

            # condition 1: overheated market
            if rsi > 78:

                # condition 2: momentum fading
                rsi_prev = df["rsi_real"].iloc[-5] if "rsi_real" in df else rsi

                if rsi < rsi_prev:
                    return True

               # condition 3: no new highs
               if recent["high"].max() <= df["high"].iloc[-10]:
                    return True

       # ---------------------------
       # SHORT EXHAUSTION
       # ---------------------------
       if direction == "SHORT":

           if rsi < 22:

              rsi_prev = df["rsi_real"].iloc[-5] if "rsi_real" in df else rsi

              if rsi > rsi_prev:
                    return True
    
              if recent["low"].min() >= df["low"].iloc[-10]:
                    return True

       return False
        
        
        
        
        
        
        
    def is_liquidity_spike(self, df: pd.DataFrame) -> bool:
        """
        Spike Filter v1:
        detects stop hunts + fake breakouts
        """

        if df is None or len(df) < 50:
            return False

        recent = df.tail(5)

        # candle size
        last_candle = recent.iloc[-1]
        body = abs(last_candle["close"] - last_candle["open"])
        range_ = last_candle["high"] - last_candle["low"]

        avg_range = (df["high"] - df["low"]).rolling(20).mean().iloc[-1]

        # spike condition 1: abnormal candle size
        if range_ > avg_range * 2.2:
           return True

        # spike condition 2: strong body move
        if body > avg_range * 1.5:
           return True

        # spike condition 3: instant reversal after spike
        prev = df["close"].iloc[-3]
        curr = df["close"].iloc[-1]

        spike_move = abs(curr - prev) / prev
 
        if spike_move > 0.008:  # 0.8% fast move (1m/5m sensitive)
          return True

        return False
