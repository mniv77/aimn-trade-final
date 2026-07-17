# ==========================================================
# browser.py
#
# Purpose:
# AATA Knowledge Browser
#
# Version: 1.0
#
# Author: Meir Niv / OpenAI
# ==========================================================

from db_connection import get_db


def show_rules():
    """Display all trading rules."""

    conn = get_db("MeirNiv$AATA")

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, category, title, professor, confidence, status
                FROM ai_trading_rules
                ORDER BY id
            """)

            for row in cursor.fetchall():
                print(row)

    finally:
        conn.close()


def show_lessons():
    """Display AI lessons."""

    conn = get_db("MeirNiv$AATA")

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, category, title, priority, lesson_type, status
                FROM aata_ai_lessons
                ORDER BY id DESC
            """)

            for row in cursor.fetchall():
                print(row)

    finally:
        conn.close()


def main():
    """AATA browser menu."""

    while True:

        print("""
==================================================
          AATA KNOWLEDGE BROWSER
==================================================

1. View Trading Rules
2. View AI Lessons
3. Exit
""")

        choice = input("Choice: ").strip()

        if choice == "1":
            show_rules()

        elif choice == "2":
            show_lessons()

        elif choice == "3":
            break

        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
