"""
AiMn KISS V3 Engine - ONE STRATEGY, ONE ENGINE, DIFFERENT MEMORIES
NO INDICATORS - Only V-Long / V-Short + 1.5% trailing
"""
class KISSV3Engine:
    TRAIL_PCT = 0.015

    def __init__(self, mode="live"):
        self.mode = mode
        self.memory = {}
        self.state = "FLAT"
        self.peak = None

    def is_v_long(self, w):
        return w[0] > w[1] < w[2] and w[2] > w[1]

    def is_v_short(self, w):
        return w[0] < w[1] > w[2] and w[2] < w[1]

    def detect_transition(self, candles):
        for i in range(len(candles)-1, 1, -1):
            window = [candles[i-2].close, candles[i-1].close, candles[i].close]
            if self.is_v_long(window):
                return "LONG", candles[i]
            if self.is_v_short(window):
                return "SHORT", candles[i]
        return "FLAT", None

    def check_trail(self, price):
        if self.state == "LONG":
            self.peak = max(self.peak, price) if self.peak else price
            if price < self.peak * (1 - self.TRAIL_PCT):
                return "FLAT"
        elif self.state == "SHORT":
            self.peak = min(self.peak, price) if self.peak else price
            if price > self.peak * (1 + self.TRAIL_PCT):
                return "FLAT"
        return self.state
