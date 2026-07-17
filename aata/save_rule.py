# save_rule.py

from aata.trading_rules import save_trading_rule


save_trading_rule(

    category="ENTRY",

    title="Never Enter Sideways Market",

    description="""
Avoid entering trades when the higher timeframe
(30-minute) market is sideways.
""",

    condition_text="""
IF Global Trend == SIDEWAYS
AND Breakout == FALSE
""",

    action_text="""
BLOCK TRADE
""",

    professor="Market Structure Professor",

    tags="sideways,entry,trend"
)