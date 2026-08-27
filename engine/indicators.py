import numpy as np
def calc_rsi_real(prices, period=14):
    if len(prices) < period+1:
        return [50.0]*len(prices)
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed>=0].sum()/period if len(seed[seed>=0])>0 else 0
    down = -seed[seed<0].sum()/period if len(seed[seed<0])>0 else 0.0001
    if down==0: down=0.0001
    rs=up/down
    rsi=[0.0]*len(prices)
    rsi[:period]=[100.-100./(1.+rs)]*period
    up_avg=up; down_avg=down
    for i in range(period, len(prices)-1):
        delta=deltas[i]
        upval=delta if delta>0 else 0
        downval=-delta if delta<0 else 0
        up_avg=(up_avg*(period-1)+upval)/period
        down_avg=(down_avg*(period-1)+downval)/period
        if down_avg==0: down_avg=0.0001
        rs=up_avg/down_avg
        rsi[i+1]=100.-100./(1.+rs)
    return rsi

def calc_macd_series(prices, fast=12, slow=26, signal=9):
    def ema(data, p):
        if len(data)<p: return [0.0]*len(data)
        k=2/(p+1)
        ema_vals=[sum(data[:p])/p]
        for price in data[p:]:
            ema_vals.append(price*k + ema_vals[-1]*(1-k))
        return [0.0]*(p-1)+ema_vals
    fast_ema=ema(prices, fast)
    slow_ema=ema(prices, slow)
    macd=[f - s for f,s in zip(fast_ema, slow_ema)]
    sig=ema(macd, signal)
    hist=[m - si for m,si in zip(macd, sig)]
    return macd, sig, hist
