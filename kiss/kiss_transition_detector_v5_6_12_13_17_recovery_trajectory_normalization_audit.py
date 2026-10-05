CASES = [
    (1, "AMZN", "LONG", "PF", 0.4186323, 0.8478898),
    (2, "NVDA", "LONG", "PF", 0.1005940, 0.5388963),
    (3, "AMZN", "LONG", "NO_PF", 0.4449620, 0.2084967),
    (4, "GOOGL", "SHORT", "PF", 0.3182420, 0.6631340),
    (5, "AMZN", "SHORT", "NO_PF", 0.1244960, 0.2743140),
    (6, "QQQ", "SHORT", "NO_PF", 0.2728390, 0.4928710),
]

print("6 CASES LOADED")

print()
print("=" * 70)
print("GIVEBACK / MFE")
print("=" * 70)

for case in CASES:
    case_id, symbol, direction, outcome, mfe, giveback = case
    normalized = giveback / mfe

    print(
        f"CASE {case_id}: "
        f"{symbol} {direction} {outcome} "
        f"MFE={mfe:.6f}% "
        f"GIVEBACK={giveback:.6f}% "
        f"RATIO={normalized:.6f}"
    )

print()
print("=" * 70)
print("NORMALIZED PF vs NO_PF")
print("=" * 70)

pf_ratios = [
    c[5] / c[4]
    for c in CASES
    if c[3] == "PF"
]

no_pf_ratios = [
    c[5] / c[4]
    for c in CASES
    if c[3] == "NO_PF"
]

print(
    f"PF:    N={len(pf_ratios)} "
    f"range={min(pf_ratios):.6f} "
    f"to {max(pf_ratios):.6f}"
)

print(
    f"NO_PF: N={len(no_pf_ratios)} "
    f"range={min(no_pf_ratios):.6f} "
    f"to {max(no_pf_ratios):.6f}"
)

overlap = (
    max(min(pf_ratios), min(no_pf_ratios))
    <= min(max(pf_ratios), max(no_pf_ratios))
)

print(
    "STATUS:",
    "OVERLAP" if overlap else "NO_RANGE_OVERLAP"
)

print()
print("=" * 70)
print("DIRECTION-CONTROLLED NORMALIZED GIVEBACK")
print("=" * 70)

for direction in ("LONG", "SHORT"):

    pf = [
        c[5] / c[4]
        for c in CASES
        if c[2] == direction and c[3] == "PF"
    ]

    no_pf = [
        c[5] / c[4]
        for c in CASES
        if c[2] == direction and c[3] == "NO_PF"
    ]

    print()
    print(direction)

    if pf:
        print(
            f"  PF    N={len(pf)} "
            f"range={min(pf):.6f} "
            f"to {max(pf):.6f}"
        )
    else:
        print("  PF    N=0 range=N/A")

    if no_pf:
        print(
            f"  NO_PF N={len(no_pf)} "
            f"range={min(no_pf):.6f} "
            f"to {max(no_pf):.6f}"
        )
    else:
        print("  NO_PF N=0 range=N/A")

    if pf and no_pf:

        overlap = (
            max(min(pf), min(no_pf))
            <= min(max(pf), max(no_pf))
        )

        print(
            "  STATUS:",
            "OVERLAP" if overlap else "NO_RANGE_OVERLAP"
        )

    else:
        print("  STATUS: NOT_COMPARABLE")

print()
print("=" * 70)
print("DIRECTION-CONTROLLED NORMALIZED GIVEBACK")
print("=" * 70)

for direction in ("LONG", "SHORT"):

    pf = [
        c[5] / c[4]
        for c in CASES
        if c[2] == direction and c[3] == "PF"
    ]

    no_pf = [
        c[5] / c[4]
        for c in CASES
        if c[2] == direction and c[3] == "NO_PF"
    ]

    print()
    print(direction)

    if pf:
        print(
            f"  PF    N={len(pf)} "
            f"range={min(pf):.6f} "
            f"to {max(pf):.6f}"
        )
    else:
        print("  PF    N=0 range=N/A")

    if no_pf:
        print(
            f"  NO_PF N={len(no_pf)} "
            f"range={min(no_pf):.6f} "
            f"to {max(no_pf):.6f}"
        )
    else:
        print("  NO_PF N=0 range=N/A")

    if pf and no_pf:

        overlap = (
            max(min(pf), min(no_pf))
            <= min(max(pf), max(no_pf))
        )

        print(
            "  STATUS:",
            "OVERLAP" if overlap else "NO_RANGE_OVERLAP"
        )

    else:
        print("  STATUS: NOT_COMPARABLE")
print()
print("=" * 70)
print("LEAVE-ONE-CASE-OUT NORMALIZED GIVEBACK SENSITIVITY")
print("=" * 70)

for removed in CASES:

    remaining = [c for c in CASES if c[0] != removed[0]]

    pf = [
        c[5] / c[4]
        for c in remaining
        if c[3] == "PF"
    ]

    no_pf = [
        c[5] / c[4]
        for c in remaining
        if c[3] == "NO_PF"
    ]

    overlap = (
        max(min(pf), min(no_pf))
        <= min(max(pf), max(no_pf))
    )

    print()
    print(
        f"REMOVE CASE {removed[0]}: "
        f"{removed[1]} {removed[2]} {removed[3]}"
    )

    print(
        f"  POOLED PF    N={len(pf)} "
        f"range={min(pf):.6f} to {max(pf):.6f}"
    )

    print(
        f"  POOLED NO_PF N={len(no_pf)} "
        f"range={min(no_pf):.6f} to {max(no_pf):.6f}"
    )

    print(
        "  POOLED STATUS:",
        "OVERLAP" if overlap else "NO_RANGE_OVERLAP"
    )
print()
print("=" * 70)
print("POST-RECOVERY-FAILURE TRAJECTORY")
print("=" * 70)

POST = [
    (1, "AMZN", "LONG", 10, 20, -0.1551277, -0.4292575, "PF"),
    (2, "NVDA", "LONG", 15, 25, -0.2251390, -0.4383024, "PF"),
    (3, "AMZN", "LONG", 25, 30, 0.2364657, 0.2364657, "NO_PF"),
    (4, "GOOGL", "SHORT", 20, 25, 0.0156770, -0.3448918, "PF"),
    (5, "AMZN", "SHORT", 25, 30, -0.1498170, -0.1498170, "NO_PF"),
    (6, "QQQ", "SHORT", 15, 20, 0.1789590, -0.2200320, "NO_PF"),
]

print()
print("CASE-LEVEL POST-FAILURE CHANGE")

for c in POST:

    case_id, symbol, direction, recovery_time, deterioration_time, first_ret, ret30, outcome = c

    change = ret30 - first_ret

    if change < -0.05:
        behavior = "CONTINUED_DETERIORATION"
    elif change > 0.05:
        behavior = "RECOVERY"
    else:
        behavior = "FLAT"

    print(
        f"CASE {case_id}: {symbol} {direction} {outcome} "
        f"FAIL=+{deterioration_time}m "
        f"RETURN={first_ret:+.6f}% "
        f"TO_30={ret30:+.6f}% "
        f"CHANGE={change:+.6f}% "
        f"{behavior}"
    )

print()
print("OUTCOME SUMMARY")

for outcome in ("PF", "NO_PF"):

    rows = [c for c in POST if c[7] == outcome]

    changes = [c[6] - c[5] for c in rows]

    continued = sum(x < -0.05 for x in changes)
    recovered = sum(x > 0.05 for x in changes)
    flat = len(changes) - continued - recovered

    print(
        f"{outcome}: N={len(rows)} "
        f"CONTINUED={continued} "
        f"RECOVERY={recovered} "
        f"FLAT={flat} "
        f"AVG_CHANGE={sum(changes)/len(changes):+.6f}%"
    )
print()
print("=" * 70)
print("TRAJECTORY PERSISTENCE AUDIT")
print("=" * 70)

PERSISTENCE = [
    (1, "AMZN", "LONG", "PF", ["D", "D", "D"]),
    (2, "NVDA", "LONG", "PF", ["D", "D"]),
    (3, "AMZN", "LONG", "NO_PF", ["D"]),
    (4, "GOOGL", "SHORT", "PF", ["D", "D"]),
    (5, "AMZN", "SHORT", "NO_PF", ["D"]),
    (6, "QQQ", "SHORT", "NO_PF", ["D", "D", "D"]),
]

print()
print("CASE-LEVEL DETERIORATION PERSISTENCE")

for case_id, symbol, direction, outcome, sequence in PERSISTENCE:

    run_length = len(sequence)
    uninterrupted = all(state == "D" for state in sequence)

    print(
        f"CASE {case_id}: {symbol} {direction} {outcome} "
        f"SEQUENCE={' -> '.join(sequence)} "
        f"RUN={run_length} "
        f"UNINTERRUPTED={uninterrupted}"
    )

print()
print("PERSISTENCE BY OUTCOME")

for outcome in ("PF", "NO_PF"):

    rows = [
        c for c in PERSISTENCE
        if c[3] == outcome
    ]

    runs = [len(c[4]) for c in rows]

    run2 = sum(r >= 2 for r in runs)
    run3 = sum(r >= 3 for r in runs)

    print(
        f"{outcome}: "
        f"N={len(rows)} "
        f"AVG_RUN={sum(runs)/len(runs):.3f} "
        f"MAX_RUN={max(runs)} "
        f"RUN>=2={run2} "
        f"RUN>=3={run3}"
    )

print()
print("KEY COMPARISON")

pf_runs = [
    len(c[4])
    for c in PERSISTENCE
    if c[3] == "PF"
]

no_pf_runs = [
    len(c[4])
    for c in PERSISTENCE
    if c[3] == "NO_PF"
]

print(
    "PF RUNS:",
    pf_runs
)

print(
    "NO_PF RUNS:",
    no_pf_runs
)

print()
print(
    "INTERPRETATION: "
    "PERSISTENT DETERIORATION IS DESCRIPTIVE ONLY. "
    "NO THRESHOLD OR TRADING RULE IS DERIVED."
)
print()
print("=" * 70)
print("TRAJECTORY ANATOMY AFTER RECOVERY FAILURE")
print("=" * 70)

ANATOMY = [
    (1, "AMZN", "LONG", "PF", "NEUTRAL", 20, -0.1551277, -0.4292575, 3),
    (2, "NVDA", "LONG", "PF", "NEUTRAL", 25, -0.2251390, -0.4383024, 2),
    (3, "AMZN", "LONG", "NO_PF", "RECOVERING", 30, 0.2364657, 0.2364657, 1),
    (4, "GOOGL", "SHORT", "PF", "RECOVERING", 25, 0.0156770, -0.3448918, 2),
    (5, "AMZN", "SHORT", "NO_PF", "RECOVERING", 30, -0.1498170, -0.1498170, 1),
    (6, "QQQ", "SHORT", "NO_PF", "RECOVERING", 20, 0.1789590, -0.2200320, 3),
]

print()
print("CASE-LEVEL ANATOMY")

for c in ANATOMY:

    (
        case_id,
        symbol,
        direction,
        outcome,
        prior_state,
        deterioration_time,
        first_return,
        return_30,
        d_run,
    ) = c

    change = return_30 - first_return

    first_return_context = (
        "ADVERSE"
        if first_return < 0
        else "FAVORABLE"
        if first_return > 0
        else "FLAT"
    )

    print()
    print(
        f"CASE {case_id}: {symbol} {direction} {outcome}"
    )
    print(
        f"  PRIOR_STATE={prior_state}"
    )
    print(
        f"  FIRST_DETERIORATING=+{deterioration_time}m"
    )
    print(
        f"  RETURN_AT_FIRST_D={first_return:+.6f}% "
        f"{first_return_context}"
    )
    print(
        f"  RETURN_AT_30M={return_30:+.6f}%"
    )
    print(
        f"  CHANGE_TO_30M={change:+.6f}%"
    )
    print(
        f"  DETERIORATING_RUN={d_run}"
    )

print()
print("GROUP SUMMARY")

for outcome in ("PF", "NO_PF"):

    rows = [
        c for c in ANATOMY
        if c[3] == outcome
    ]

    prior_states = {}
    adverse = 0
    favorable = 0
    flat = 0
    runs = []
    changes = []

    for c in rows:

        prior = c[4]
        first_return = c[6]
        return_30 = c[7]

        prior_states[prior] = prior_states.get(prior, 0) + 1

        if first_return < 0:
            adverse += 1
        elif first_return > 0:
            favorable += 1
        else:
            flat += 1

        runs.append(c[8])
        changes.append(return_30 - first_return)

    print()
    print(f"{outcome}: N={len(rows)}")
    print(f"  PRIOR_STATES={prior_states}")
    print(
        f"  FIRST_D_RETURN: "
        f"ADVERSE={adverse} "
        f"FAVORABLE={favorable} "
        f"FLAT={flat}"
    )
    print(
        f"  AVG_D_TO_30_CHANGE="
        f"{sum(changes) / len(changes):+.6f}%"
    )
    print(
        f"  D_RUNS={runs}"
    )

print()
print("QQQ EXCEPTION CHECK")

qqq = next(
    c for c in ANATOMY
    if c[1] == "QQQ"
)

print(
    "QQQ:",
    f"prior={qqq[4]}",
    f"first_D_return={qqq[6]:+.6f}%",
    f"return_30={qqq[7]:+.6f}%",
    f"D_run={qqq[8]}",
)

print()
print(
    "INTERPRETATION: "
    "DESCRIPTIVE TRAJECTORY ANATOMY ONLY. "
    "NO THRESHOLD OR TRADING RULE IS DERIVED."
)
print()
print("=" * 70)
print("SUCCESSIVE-DETERIORATION GEOMETRY")
print("=" * 70)

GEOMETRY = [
    (1, "AMZN", "LONG", "PF", [-0.1551277, -0.4292575]),
    (2, "NVDA", "LONG", "PF", [-0.2251390, -0.4383024]),
    (3, "AMZN", "LONG", "NO_PF", [0.2364657]),
    (4, "GOOGL", "SHORT", "PF", [0.0156770, -0.3448918]),
    (5, "AMZN", "SHORT", "NO_PF", [-0.1498170]),
    (6, "QQQ", "SHORT", "NO_PF", [0.1789590, -0.2200320]),
]

print()
print("CASE-LEVEL GEOMETRY")

for case_id, symbol, direction, outcome, returns in GEOMETRY:

    print()
    print(
        f"CASE {case_id}: "
        f"{symbol} {direction} {outcome}"
    )

    print(
        "  RETURNS:",
        " -> ".join(f"{x:+.6f}%" for x in returns)
    )

    if len(returns) >= 2:

        changes = [
            returns[i] - returns[i - 1]
            for i in range(1, len(returns))
        ]

        print(
            "  SUCCESSIVE_CHANGES:",
            " -> ".join(f"{x:+.6f}%" for x in changes)
        )

        worsening = sum(x < 0 for x in changes)
        improving = sum(x > 0 for x in changes)
        flat = sum(x == 0 for x in changes)

        print(
            f"  WORSENING={worsening} "
            f"IMPROVING={improving} "
            f"FLAT={flat}"
        )

        print(
            f"  TOTAL_CHANGE="
            f"{returns[-1] - returns[0]:+.6f}%"
        )

        print(
            f"  NEW_ADVERSE_EXTREME="
            f"{returns[-1] < min(returns[:-1])}"
        )

    else:
        print("  SUCCESSIVE_CHANGES: N/A")
        print("  TOTAL_CHANGE: N/A")

print()
print("PF vs NO_PF — OBSERVABLE GEOMETRY")

for outcome in ("PF", "NO_PF"):

    rows = [
        c for c in GEOMETRY
        if c[3] == outcome
        and len(c[4]) >= 2
    ]

    print()
    print(
        f"{outcome}: "
        f"CASES_WITH_2PLUS_D_POINTS={len(rows)}"
    )

    for c in rows:

        changes = [
            c[4][i] - c[4][i - 1]
            for i in range(1, len(c[4]))
        ]

        print(
            f"  {c[1]}: "
            f"changes="
            f"{[round(x, 6) for x in changes]}"
        )

print()
print("IMPORTANT LIMITATION")
print(
    "QQQ has three DETERIORATING observations, "
    "but only the first and +30m signed returns are currently "
    "available in this compact audit. The intermediate D return "
    "is not reconstructed or invented here."
)

print()
print(
    "INTERPRETATION: "
    "DESCRIPTIVE GEOMETRY ONLY. "
    "NO THRESHOLD OR TRADING RULE IS DERIVED."
)
