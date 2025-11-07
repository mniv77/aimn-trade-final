import numpy as np
import pandas as pd

def rsi_tv(close, window):
    recent_high = close.rolling(window).max()
    recent_low = close.rolling(window).min()
    rsi_real = (close - recent_low) / (recent_high - recent_low) * 100
    rsi_real = rsi_real.fillna(50)  # TV sets to 50 if undefined
    return rsi_real

def macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist_line = macd_line - signal_line
    return macd_line, signal_line, hist_line

def atr(df, length=14):
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr_val = tr.rolling(window=length, min_periods=length).mean()
    return atr_val

def sma(series, length):
    return series.rolling(window=length).mean()

def obv(close, volume):
    obv = [0]
    for i in range(1, len(close)):
        if close[i] > close[i-1]:
            obv.append(obv[-1] + volume.iloc[i])
        elif close[i] < close[i-1]:
            obv.append(obv[-1] - volume.iloc[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=close.index)

# Volume direction helpers
def volume_direction(close, volume, vol_ma_length, vol_threshold):
    vol_ma = sma(volume, vol_ma_length)
    vol_ratio = volume / vol_ma
    price_change = (close - close.shift(1)) / close.shift(1) * 100
    direction = np.zeros(len(close))
    for i in range(1, len(close)):
        if volume.iloc[i] > vol_ma.iloc[i] * vol_threshold:
            if price_change.iloc[i] > 0.1:
                direction[i] = 1
            elif price_change.iloc[i] < -0.1:
                direction[i] = -1
    return direction
