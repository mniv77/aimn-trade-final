"""
AiMn KISS V3 Engine - ONE STRATEGY, ONE ENGINE, DIFFERENT MEMORIES
NO INDICATORS - Only V-Long / V-Short + 1.5% trailing
Impressive trades, no confusing indicators
"""
class KISSV3Engine:
    TRAIL_PCT = 0.015

    def __init__(self, mode="live"):
        self.mode = mode # live, backtest, tuner - each own notebook
        self.memory = {}
        self.state = "FLAT"
        self.peak = None
        self.entry_price = None

    def is_v_long(self, w):
        """V-Long = falling -> rising = ideal LONG"""
        return w[0] > w[1] < w[2] and w[2] > w[1]

    def is_v_short(self, w):
        """V-Short = rising -> falling = ideal SHORT"""
        return w[0] < w[1] > w[2] and w[2] < w[1]

    def detect_transition(self, candles):
        """START FROM NEW CANDLE GOING BACK"""
        for i in range(len(candles)-1, 1, -1):
            try:
                window = [candles[i-2].close, candles[i-1].close, candles[i].close]
                if self.is_v_long(window):
                    return "LONG", candles[i]
                if self.is_v_short(window):
                    return "SHORT", candles[i]
            except:
                window = [candles[i-2], candles[i-1], candles[i]]
                if self.is_v_long(window):
                    return "LONG", i
                if self.is_v_short(window):
                    return "SHORT", i
        return "FLAT", None

    def check_trail(self, price):
        """Trailing 1.5% protects profit - LONG->FLAT, SHORT->FLAT = wait"""
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
        """TRANSITIONS: ENTER SHORT<->LONG, FLAT->*, WAIT LONG->FLAT, SHORT->FLAT"""
        if new_signal == "FLAT":
            return self.check_trail(price)
        # ENTER transition
        if self.state!= new_signal:
            self.state = new_signal
            self.peak = price
            self.entry_price = price
        return self.state
