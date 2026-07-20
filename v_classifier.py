import pandas as pd
import numpy as np


class VClassifier:
    """
    Detects V structures (reversal zones) and filters noise.
    Outputs: LONG_V, SHORT_V, CHOP, NONE
    """

    def __init__(self):
        self.lookback = 20

    def classify_v(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) < self.lookback:
            return {
                "trade_allowed": False,
                "direction": None,
                "v_type": "INSUFFICIENT_DATA"
            }

        recent = df.iloc[-self.lookback:]
        price = recent["close"]

        high = price.max()
        low = price.min()
        current = price.iloc[-1]

        # position inside range (0 = bottom, 1 = top)
        pos = (current - low) / (high - low + 1e-9)

        # volatility
        vol = recent["close"].pct_change().std()

        # wick proxy (if available)
        wick_score = 0
        if "high" in recent and "low" in recent:
            wick_score = ((recent["high"] - recent["low"]) / recent["close"]).mean()

        # --------------------------
        # V DETECTION LOGIC
        # --------------------------

        # LONG V (bottom reversal zone)
        if pos < 0.25 and vol > 0.01:
            return {
                "trade_allowed": True,
                "direction": "BUY",
                "v_type": "LONG_V"
            }

        # SHORT V (top rejection zone)
        if pos > 0.75 and vol > 0.01:
            return {
                "trade_allowed": True,
                "direction": "SELL",
                "v_type": "SHORT_V"
            }

        # CHOP zone (middle = NO TRADE)
        if 0.40 <= pos <= 0.60:
            return {
                "trade_allowed": False,
                "direction": None,
                "v_type": "CHOP_MIDDLE_ZONE"
            }

        # default = weak/no signal
        return {
            "trade_allowed": False,
            "direction": None,
            "v_type": "NO_V"
        }