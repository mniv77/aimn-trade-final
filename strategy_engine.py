"""
============================================================
AIMn Trading Strategy Engine (Master v2.0)
============================================================
Shared core module for Live Trading, Scanners, and Backtesting.
"""

import pandas as pd
import numpy as np

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculates the current Average True Range (ATR) from OHLC data."""
    df = df.copy()
    df.columns = [col.title() for col in df.columns]
    df['prev_close'] = df['Close'].shift(1)
    df['tr1'] = df['High'] - df['Low']
    df['tr2'] = (df['High'] - df['prev_close']).abs()
    df['tr3'] = (df['Low'] - df['prev_close']).abs()
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=period).mean()
    return float(df['atr'].iloc[-1])

def calc_rsi_real(series, period=14) -> float:
    """
    Custom RSI Real Rule:
    Looks back over history (period=14) where max price = 100 units and min price = 0 units.
    Normalized real price scaling.
    """
    s = pd.Series(series)
    if len(s) < period:
        return 50.0  # Default baseline
    
    roll_min = s.rolling(window=period).min()
    roll_max = s.rolling(window=period).max()
    
    last_val = float(s.iloc[-1])
    last_min = float(roll_min.iloc[-1])
    last_max = float(roll_max.iloc[-1])
    
    if last_max == last_min:
        return 50.0
        
    scaled = ((last_val - last_min) / (last_max - last_min)) * 100.0
    return float(scaled)

def calculate_dynamic_targets(entry_price: float, atr: float, direction: str,
                               sl_multiplier: float = 1.5,
                               tp1_multiplier: float = 2.0,
                               tp2_multiplier: float = 3.5) -> dict:
    """Computes dynamic Stop Loss and Take Profit levels based on ATR multiples."""
    direction = str(direction).upper()

    if direction in ['LONG', 'BUY']:
        stop_loss = entry_price - (atr * sl_multiplier)
        take_profit_1 = entry_price + (atr * tp1_multiplier)
        take_profit_2 = entry_price + (atr * tp2_multiplier)
    elif direction in ['SHORT', 'SELL']:
        stop_loss = entry_price + (atr * sl_multiplier)
        take_profit_1 = entry_price - (atr * tp1_multiplier)
        take_profit_2 = entry_price - (atr * tp2_multiplier)
    else:
        raise ValueError("Direction must be 'LONG' or 'SHORT'")

    risk = abs(entry_price - stop_loss)
    reward_tp1 = abs(take_profit_1 - entry_price)
    rr_ratio_tp1 = round(reward_tp1 / risk, 2) if risk > 0 else 0
    
    return {
        "entry_price": round(entry_price, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit_1": round(take_profit_1, 2),
        "take_profit_2": round(take_profit_2, 2),
        "risk_amount_pts": round(risk, 2),
        "rr_ratio_tp1": rr_ratio_tp1
    }

def check_asymmetrical_shock_shield(df: pd.DataFrame, direction: str, rsi_real_val: float) -> dict:
    """
    Asymmetrical Emergency Shock Shield & RSI Real Rule:
    - If LONG: Triggers panic exit on severe drop or RSI Real <= 10.
    - If SHORT: Triggers panic exit on violent jump or RSI Real >= 90.
    """
    direction = str(direction).upper()
    df = df.copy()
    df.columns = [col.title() for col in df.columns]
    
    if len(df) < 2:
        return {"panic_exit": False, "reason": "Insufficient data"}
        
    last_close = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[-2])
    pct_change = ((last_close - prev_close) / prev_close) * 100
    
    shock_threshold = 1.5
    
    if direction == 'LONG':
        if pct_change <= -shock_threshold or rsi_real_val <= 10:
            return {
                "panic_exit": True,
                "reason": f"CRASH BOMB DETECTED: Price dropped {pct_change:.2f}% against LONG position."
            }
    elif direction == 'SHORT':
        if pct_change >= shock_threshold or rsi_real_val >= 90:
            return {
                "panic_exit": True,
                "reason": f"SPIKE BOMB DETECTED: Price jumped +{pct_change:.2f}% against SHORT position."
            }
            
    return {"panic_exit": False, "reason": "Normal market conditions - riding trend."}

def evaluate_state_transition(previous_state: str, current_trend: str, is_reversal: bool) -> str:
    """Core State Machine Transition Engine (FLAT, LONG, SHORT)."""
    prev = str(previous_state).upper()
    trend = str(current_trend).upper()
    
    if prev == 'FLAT':
        if trend in ['LONG', 'BUY']:
            return 'LONG'
        elif trend in ['SHORT', 'SELL']:
            return 'SHORT'
    elif prev in ['LONG', 'SHORT']:
        if is_reversal:
            return 'FLAT'
            
    return prev
