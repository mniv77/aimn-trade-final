CASES = [
    (1, "AMZN", "LONG",  "PF",    0.8478898),
    (2, "NVDA", "LONG",  "PF",    0.5388963),
    (3, "AMZN", "LONG",  "NO_PF", 0.2084967),
    (4, "GOOGL","SHORT", "PF",    0.6631340),
    (5, "AMZN", "SHORT", "NO_PF", 0.2743140),
    (6, "QQQ",  "SHORT", "NO_PF", 0.4928710),
]

def vals(cases, outcome, direction=None):
    return [
        c[4] for c in cases
        if c[3] == outcome
        and (direction is None or c[2] == direction)
    ]

def status(pf, no_pf):
    if not pf or not no_pf:
        return "NOT_COMPARABLE"
    return (
        "OVERLAP"
        if max(min(pf), min(no_pf)) <= min(max(pf), max(no_pf))
        else "NO_RANGE_OVERLAP"
    )

def report(title, cases, direction=None):
    pf = vals(cases, "PF", direction)
    no_pf = vals(cases, "NO_PF", direction)

    print(title)
    print(
        f"  PF    N={len(pf)} "
        f"range={min(pf) if pf else 'N/A'}"
        f" to {max(pf) if pf else 'N/A'}"
    )
    print(
        f"  NO_PF N={len(no_pf)} "
        f"range={min(no_pf) if no_pf else 'N/A'}"
        f" to {max(no_pf) if no_pf else 'N/A'}"
    )
    print(f"  STATUS: {status(pf, no_pf)}")

print("=" * 70)
print("AIMn KISS V13.17")
print("FAILED-RECOVERY GIVEBACK CASE-LEVEL SENSITIVITY")
print("=" * 70)

print("\nBASELINE")
report("POOLED", CASES)
report("LONG", CASES, "LONG")
report("SHORT", CASES, "SHORT")

print()
print("=" * 70)
print("LEAVE-ONE-CASE-OUT SENSITIVITY")
print("=" * 70)

for removed in CASES:

    remaining = [
        c for c in CASES
        if c[0] != removed[0]
    ]

    print()
    print(
        f"REMOVED CASE {removed[0]}: "
        f"{removed[1]} {removed[2]} {removed[3]} "
        f"giveback={removed[4]:.6f}%"
    )

    report("  POOLED", remaining)
    report("  LONG", remaining, "LONG")
    report("  SHORT", remaining, "SHORT")

print()
print("=" * 70)
print("SENSITIVITY AUDIT COMPLETE")
print("=" * 70)
