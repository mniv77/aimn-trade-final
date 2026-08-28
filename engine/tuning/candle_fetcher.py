
import sys
sys.path.insert(0, '/home/MeirNiv/aimn-trade-final')
from datetime import datetime

class Candle:
    def __init__(self, close, high=None, low=None, time=None):
        self.close = close
        self.high = high or close
        self.low = low or close
        self.time = time

def fetch_candles(symbol, timeframe='1hr', bars=8000):
    try:
        import yfinance as yf
        tf_map = {'1hr':'1h','1h':'1h','1m':'1m','5m':'5m','15m':'15m','1day':'1d','6hr':'1h'}
        yf_tf = tf_map.get(timeframe, '1h')
        period = "2y" if bars>5000 else "1y" if bars>2000 else "6mo"
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=yf_tf)
        if len(hist) < 10:
            raise Exception(f"yfinance empty len {len(hist)}")
        candles = []
        for idx, row in hist.tail(bars).iterrows():
            candles.append(Candle(close=float(row['Close']), high=float(row['High']), low=float(row['Low']), time=idx))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetched {len(candles)} candles for {symbol} via yfinance {yf_tf}")
        return candles
    except Exception as e:
        print(f"yfinance failed {symbol}: {e}")
        import traceback; traceback.print_exc()
        return None
