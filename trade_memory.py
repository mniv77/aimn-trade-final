#trade_memory.py
"""
AIV Trade Memory Layer
Logs trades for learning future scoring adjustments
"""

import json
from datetime import datetime
from typing import Dict
from trade_memory import TradeMemory

import pandas as pd
from collections import defaultdict


class TradeMemory:
    """
    Learns which V patterns perform best over time.
    """

    def __init__(self):
        self.trades = []

        # learning stats
        self.stats = {
            "LONG_V": {"wins": 0, "losses": 0},
            "SHORT_V": {"wins": 0, "losses": 0},
            "CHOP": {"wins": 0, "losses": 0},
        }

    def log_trade(self, trade: dict):
        self.trades.append(trade)

        v_type = trade.get("v_type", "UNKNOWN")
        result = trade.get("result", "LOSS")  # WIN / LOSS

        if v_type not in self.stats:
            self.stats[v_type] = {"wins": 0, "losses": 0}

        if result == "WIN":
            self.stats[v_type]["wins"] += 1
        else:
            self.stats[v_type]["losses"] += 1

    def success_rate(self, v_type: str) -> float:
        s = self.stats.get(v_type, {"wins": 0, "losses": 0})
        total = s["wins"] + s["losses"]
        if total == 0:
            return 0.5
        return s["wins"] / total

    def bias(self, v_type: str) -> float:
        """
        Returns confidence multiplier for scoring system.
        """
        return 0.5 + self.success_rate(v_type)

"""
AIV Trade Memory Layer
Logs trades for learning future scoring adjustments
"""

import json
from datetime import datetime
from typing import Dict


class TradeMemory:

    def __init__(self, file_path="trade_memory.json"):
        self.file_path = file_path

    def log_trade(self, trade: Dict):
        trade["timestamp"] = datetime.utcnow().isoformat()

        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
        except:
            data = []

        data.append(trade)

        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_trades(self):
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except:
            return []