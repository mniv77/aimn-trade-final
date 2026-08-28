from engine.safety_filter import is_safe_to_enter
class KISSV3Engine:
    TRAIL_PCT = 0.015
    MIN_V_PCT = 0.002
    SMA_PERIOD = 200

    def __init__(self, mode="live"):
        self.mode = mode
        self.state = "FLAT"
        self.peak = None
        self.entry_price = None
        self.last_idx = 2

    def sma(self, closes, period, idx):
        if idx < period: return None
        return sum(closes[idx-period:idx]) / period

    def is_v_long(self, w):
        if not (w[0] > w[1] < w[2]):
            return False
        depth = min(w[0], w[2]) - w[1]
        return depth / w[1] >= self.MIN_V_PCT

    def is_v_short(self, w):
        if not (w[0] < w[1] > w[2]):
            return False
        depth = w[1] - min(w[0], w[2])
        return depth / w[1] >= self.MIN_V_PCT

    def detect_transition(self, closes, from_idx=None):
        start = from_idx if from_idx is not None else self.last_idx
        start = max(2, start)
        for i in range(start, len(closes)):
            sma200 = self.sma(closes, self.SMA_PERIOD, i)
            w = [closes[i-2], closes[i-1], closes[i]]
            is_long = self.is_v_long(w)
            is_short = self.is_v_short(w)
            if sma200 is not None:
                if is_long and closes[i] < sma200: is_long=False
                if is_short and closes[i] > sma200: is_short=False
            if is_long:
                self.last_idx = i+1
                return "LONG", i
            if is_short:
                self.last_idx = i+1
                return "SHORT", i
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
        if self.state!= "FLAT":
            if self.check_trail(price)=="FLAT":
                self.state="FLAT"
                self.peak=None
                return "FLAT"
        if new_signal=="FLAT":
            return self.state
        if self.state!=new_signal:
            self.state=new_signal
            self.peak=price
            self.entry_price=price
        return self.state
