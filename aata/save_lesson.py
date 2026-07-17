#save_lesson.py


from aata.ai_lessons import save_ai_lesson

save_ai_lesson(
    category="Trend",
    title="Avoid Sideways Markets",
    description="""
Never enter when the 30m trend is sideways.
Wait for breakout.
""",
    priority=5,
    market="CRYPTO",
    timeframe="30m",
    tags="trend,sideways"
)

print("Lesson saved.")