"""TEST-ONLY: goal distance at every batch-E early stop (single-model) -> goal collapse vs not."""
import sys, math, re
sys.path.insert(0, ".")
import brace_an as b
rows = [l for l in open(sys.argv[1], encoding="utf-8") if "EARLY" in l and " men 1 " in l]
for l in rows:
    lab, lane = l.split()[0], int(l.split()[2])
    for rec in b.lanes(lab):
        if rec["lane"] != lane or rec["stop"] is None: continue
        s, i, td = rec["s"], rec["stop"], rec["touchdown"]
        win = s[td:i+1]
        gd = [math.hypot(r["gx"]-r["x"], r["gz"]-r["z"]) for r in win]
        collapse = any(a > 5 and c < 1.0 for a, c in zip(gd, gd[1:]))
        print(f"{lab:10s} l{lane} {rec['target']:7s} goal {gd[0]:5.1f}->{gd[-1]:5.1f} collapse={collapse} v_td {s[td]['s1c8']:.1f} | {l.split('cause ')[1].strip()}")
