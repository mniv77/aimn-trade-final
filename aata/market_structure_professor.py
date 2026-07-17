# market_structure_professor.py

from db_connection import get_db


class MarketStructureProfessor:

    def __init__(self):
        self.rules = []

    def load_rules(self):

        conn = get_db("MeirNiv$AATA")

        try:
            with conn.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        id,
                        title,
                        description,
                        condition_text,
                        action_text,
                        confidence
                    FROM ai_trading_rules
                    WHERE status='ACTIVE'
                    ORDER BY priority DESC, id
                """)

                self.rules = cursor.fetchall()

        finally:
            conn.close()

    def evaluate(self, market_state):

        print("\n==============================")
        print(" MARKET STRUCTURE PROFESSOR")
        print("==============================")

        print(f"Market State : {market_state}\n")

        score = 100

        for rule in self.rules:

            print(f"Rule {rule['id']} : {rule['title']}")

            if (
                market_state.upper() == "SIDEWAYS"
                and "SIDEWAYS" in rule["title"].upper()
            ):

                print("  ❌ Rule triggered")

                score = 0

                return {
                    "approved": False,
                    "score": score,
                    "reason": rule["title"]
                }

        return {
            "approved": True,
            "score": score,
            "reason": "No blocking rule"
        }


if __name__ == "__main__":

    professor = MarketStructureProfessor()

    professor.load_rules()

    result = professor.evaluate("SIDEWAYS")

    print("\nDecision")
    print(result)