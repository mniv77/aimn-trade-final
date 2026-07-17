#  save_rule_002.py

from aata.trading_rules import save_trading_rule


save_trading_rule(

    category="MARKET_STRUCTURE",

    title="30m Trend Gives Trading Permission",

    description="""
The higher timeframe determines if trading is allowed.
The 5m chart is only for timing.
""",

    condition_text="""
IF 30m trend is SIDEWAYS
THEN trading permission is denied.
""",

    action_text="""
ALLOW entries only when 30m has a clear directional trend.
""",

    priority=10,

    confidence=95,

    professor="Market Structure Professor",

    tags="30m,trend,timeframe,permission"
)