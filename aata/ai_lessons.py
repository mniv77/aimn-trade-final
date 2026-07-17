# ai_lessons.py

from db_connection import get_db


def save_ai_lesson(
    category,
    title,
    description,
    priority=3,
    lesson_type="IDEA",
    market="",
    timeframe="",
    tags="",
    notes=""
):

    conn = get_db("MeirNiv$AATA")

    try:

        with conn.cursor() as cursor:

            sql = """
            INSERT INTO aata_ai_lessons
            (
                category,
                title,
                description,
                priority,
                lesson_type,
                market,
                timeframe,
                tags,
                notes
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """

            cursor.execute(
                sql,
                (
                    category,
                    title,
                    description,
                    priority,
                    lesson_type,
                    market,
                    timeframe,
                    tags,
                    notes,
                ),
            )

        conn.commit()

    finally:
        conn.close()