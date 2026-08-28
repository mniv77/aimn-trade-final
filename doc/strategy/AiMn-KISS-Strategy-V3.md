# AiMn KISS V3 Strategy - ONE BRAIN

**Rule:** ONE STRATEGY. ONE SET OF RULES.

## Entry
Transition: SHORT->LONG, LONG->SHORT, FLAT->LONG, FLAT->SHORT = ENTER
LONG->FLAT, SHORT->FLAT = WAIT

## Memory Method
Remember WHAT=trend, WHEN=time. Start from new candle going BACK to find last transition.
Old method scanning 124..2016 forward = 20 trades 0.007% = commission killer.

## Standard Functions in engine/trend_engine.py
- TrendMemory
- get_market_state(closes, idx, window=20)
- confirm_transition(closes, from_idx, new_trend, 3)
- is_v_shape()
- find_last_transition() - NEW CANDLE BACKWARDS
- detect_transitions()
- emergency_rsi_exit()
- check_stop_loss()

See full doc: AiMn-KISS-Strategy-V3-full.md
