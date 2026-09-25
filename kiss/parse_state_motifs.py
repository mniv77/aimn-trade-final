from collections import defaultdict
import re

aggregated = defaultdict(lambda: {"total_n": 0, "delta_sum": 0.0, "occurrences": 0})
curr_state = "UNKNOWN"
curr_motif = None

with open("v1316_run.txt") as f:
    for line in f:
        line = line.strip()
        st_match = re.search(r"CURRENT STATE\s*=\s*(\w+)", line)
        if st_match:
            curr_state = st_match.group(1)
            
        if "CURRENT STATE = DETERIORATING" in line: curr_state = "DETERIORATING"
        elif "CURRENT STATE = PERSISTENT_FAILURE" in line: curr_state = "PERSISTENT_FAILURE"
        elif "CURRENT STATE = RECOVERING" in line: curr_state = "RECOVERING"
        elif "CURRENT STATE = NEUTRAL" in line: curr_state = "NEUTRAL"
            
        motif_match = re.search(r"MOTIF:\s*([A-Za-z0-9_ ->]+)", line)
        if motif_match:
            curr_motif = motif_match.group(1).strip()
            
        if "DELTA=" in line and curr_motif:
            m = re.search(r"\+(15|30|45|60)m\s+MOTIF_N=(\d+).*?DELTA=([+-]?\d+\.\d+)%", line)
            if m:
                hz, n, delta = m.group(1), int(m.group(2)), float(m.group(3))
                key = (curr_state, curr_motif, f"+{hz}m")
                aggregated[key]["total_n"] += n
                aggregated[key]["delta_sum"] += delta
                aggregated[key]["occurrences"] += 1

print(f"{'CURRENT STATE':<20} | {'MOTIF':<42} | {'HZ':<6} | {'SUM_N':<6} | {'MEAN DELTA'}")
print("-" * 90)
for (st, motif, hz), d in sorted(aggregated.items()):
    mean_delta = d["delta_sum"] / d["occurrences"] if d["occurrences"] > 0 else 0
    print(f"{st:<20} | {motif:<42} | {hz:<6} | {d['total_n']:<6} | {mean_delta:+.3f}%")
