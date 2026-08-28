"""
AiMn KISS V3 Engine - ONE STRATEGY, ONE ENGINE, DIFFERENT MEMORIES
NO INDICATORS - Only V-Long / V-Short + 1.5% trailing
Impressive trades, no confusing indicators
"""
class KISSV3Engine:
    TRAIL_PCT = 0.015

    def __init__(self, mode="live"):
        self.mode = mode
        self.memory = {}
        self.state = "FLAT"
        self.peak = None
        self.entry_price = None

    def is_v_long(self, w):
        return w[0] > w[1] < w[2] and w[2] > w[1]

    def is_v_short(self, w):
        return w[0] < w[1] > w[2] and w[2] < w[1]

    def detect_transition(self, candles):
        for i in range(len(candles)-1, 1, -1):
            try:
                c2 = candles[i-2].close if hasattr(candles[i-2], 'close') else candles[i-2]
                c1 = candles[i-1].close if hasattr(candles[i-1], 'close') else candles[i-1]
                c0 = candles[i].close if hasattr(candles[i], 'close') else candles[i]
                window = [c2, c1, c0]
                if self.is_v_long(window):
                    return "LONG", i
                if self.is_v_short(window):
                    return "SHORT", i
            except Exception as e:
                continue
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

    def next_state(self, new_signal, price):
        if new_signal == "FLAT":
            return self.check_trail(price)
        if self.state!= new_signal:
            self.state = new_signal
            self.peak = price
            self.entry_price = price
        return self.state
