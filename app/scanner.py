# /app/scanner.py
import pandas as pd
from .indicators import rsi, macd

def score_row(close: pd.Series, params) -> float:
    r = rsi(close, params.rsi_period).iloc[-1]
    m_line, s_line, _ = macd(close, params.macd_fast, params.macd_slow, params.macd_signal)
    macd_cross = 1.0 if m_line.iloc[-1] > s_line.iloc[-1] else 0.0
    vol_score = 1.0  # placeholder
    # Weighted score in [0,1+] roughly
    score = (params.weight_rsi * (1 - r/100)) + (params.weight_macd * macd_cross) + (params.weight_vol * vol_score)
    return float(score)

def should_enter(score: float, threshold: float) -> bool:
    return score >= threshold