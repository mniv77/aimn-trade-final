"""
AIMn V3.1 - Structure Scoring Engine
Converts global + local V signals into a trade score (0-100)
"""

import pandas as pd
import numpy as np
from v_classifier import VClassifier


class AIVScoringEngine:

    class AIVScoringEngine:

    def __init__(self, memory):
        self.v = VClassifier()
        self.memory = memory   # 👈 CONNECT MEMORY HERE

    # ---------------------------
    # GLOBAL TREND SCORE
    # ---------------------------
    def score_global(self, df, direction):
        trend = self.v.get_global_trend(df)

        if trend == "SIDEWAYS":
            return 10

        if (trend == "UP" and direction == "BUY") or (trend == "DOWN" and direction == "SELL"):
            return 30

        return 0

    # ---------------------------
    # LOCAL V SCORE
    # ---------------------------
    def score_local_v(self, v_type):
        if v_type in ["V_UP", "V_DOWN"]:
            return 20
        return 5

    # ---------------------------
    # CONTINUATION SCORE
    # ---------------------------
    def score_continuation(self, v_result):
        if v_result["v_type"] == "CONTINUATION":
            return 20
        if v_result["v_type"] == "REVERSAL_RISK":
            return 0
        return 10

    # ---------------------------
    # VOLUME SCORE
    # ---------------------------
    def score_volume(self, df):
        vol = df["volume"].rolling(20).mean().iloc[-1]
        vol_now = df["volume"].iloc[-1]

        ratio = vol_now / vol if vol else 1

        if 0.8 <= ratio <= 1.5:
            return 15
        elif ratio < 0.8:
            return 10
        else:
            return 5

    # ---------------------------
    # RISK PENALTY
    # ---------------------------
    def risk_penalty(self, df):
        atr = df["close"].pct_change().abs().rolling(10).mean().iloc[-1]

        if atr > 0.02:
            return 10
        elif atr > 0.01:
            return 5
        return 0

    # ---------------------------
    # MAIN SCORE
    # ---------------------------
    def evaluate(self, df):
        v_result = self.v.classify_v(df)

        direction = v_result.get("direction")
        if not direction:
            return {
                "score": 0,
                "trade_allowed": False,
                "reason": "No direction"
            }

        g = self.score_global(df, direction)
        l = self.score_local_v(v_result["local_v"])
        c = self.score_continuation(v_result)
        v = self.score_volume(df)
        r = self.risk_penalty(df)

        # 🧠 MEMORY BOOST (NEW)
        memory_boost = self.memory.bias(v_result["v_type"])

        # normalize boost into score impact
        memory_score = memory_boost * 10

        total = g + l + c + v - r + memory_score

        return {
            "score": round(total, 2),
            "global_trend": v_result["global_trend"],
            "local_v": v_result["local_v"],
            "v_type": v_result["v_type"],
            "direction": direction,
            "trade_allowed": total >= 75
        }