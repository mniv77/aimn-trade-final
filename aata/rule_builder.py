# rule_builder.py

from aata.trading_rules import save_trading_rule


def ask(prompt, default=""):
    value = input(f"{prompt} [{default}]: ").strip()
    return value if value else default


def main():

    print("=" * 60)
    print("          AATA TRADING RULE BUILDER")
    print("=" * 60)

    category = ask("Category", "ENTRY")
    title = ask("Title")

    print("\nDescription (press ENTER when finished):")
    description = input("> ")

    print("\nCondition:")
    condition = input("> ")

    print("\nAction:")
    action = input("> ")

    priority = int(ask("Priority", "5"))
    confidence = float(ask("Confidence", "100"))

    professor = ask(
        "Professor",
        "Market Structure Professor"
    )

    tags = ask("Tags")
    notes = ask("Notes")

    save_trading_rule(
        category=category,
        title=title,
        description=description,
        condition_text=condition,
        action_text=action,
        priority=priority,
        confidence=confidence,
        professor=professor,
        tags=tags,
        notes=notes,
    )

    print("\n✅ Trading Rule Saved Successfully.")


if __name__ == "__main__":
    main()