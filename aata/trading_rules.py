#  trading_rules.py

from db_connection import get_db


def save_trading_rule(
    category,
    title,
    description,
    condition_text,
    action_text,
    priority=5,
    confidence=100,
    professor="AATA",
    tags="",
    notes=""
):

    conn = get_db("MeirNiv$AATA")

    try:

        with conn.cursor() as cursor:

            sql = """
            INSERT INTO ai_trading_rules
            (
                category,
                title,
                description,
                condition_text,
                action_text,
                priority,
                confidence,
                professor,
                tags,
                notes
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """

            cursor.execute(
                sql,
                (
                    category,
                    title,
                    description,
                    condition_text,
                    action_text,
                    priority,
                    confidence,
                    professor,
                    tags,
                    notes,
                ),
            )

        conn.commit()

        print("Trading rule saved.")

    finally:
        conn.close()