"""TEST-ONLY: scan AIR-DIVE-RELEASE-W1 runs (T samples, 0.1 s) for single-model flyers that stop within 8 s
of their first touchdown: per stop, speed sequence of the brake, travel since touchdown, slot/state
before/after, first non-1 slot after stop and its delay. usage: oldstops.py <runs dir> [labels...]"""
import sys, math, json
from pathlib import Path
from collections import defaultdict
runs = Path(sys.argv[1]); labs = sys.argv[2:] or sorted(p.name for p in runs.iterdir() if (p / "ld_repath_probe_slice.txt").exists())
for lab in labs:
    d = runs / lab
    v = json.loads((d / "verdict.json").read_text("utf-8")) if (d / "verdict.json").exists() else {"lanes": []}
    tgt = {l["flyer_uid"]: l.get("target_uid") for l in v["lanes"]}
    T = defaultdict(list)
    for l in (d / "ld_repath_probe_slice.txt").read_text("utf-8", errors="replace").splitlines():
        p = l.split()
        if p and p[0] == "T" and len(p) >= 13:
            T[p[2]].append((int(p[1]) / 1000, int(p[4]), int(p[5]) & 0xffff, math.hypot(float(p[7]), float(p[8])), int(p[10]), float(p[11]), float(p[12])))
    for uid, s in sorted(T.items()):
        td = next((i for i in range(1, len(s)) if s[i - 1][4] == 2 and s[i][4] == 0), None)
        if td is None: continue
        for i in range(td + 1, len(s) - 3):
            if s[i][0] > s[td][0] + 8: break
            if s[i - 1][3] > 5 and s[i][3] < s[i - 1][3] - 2.5 and s[i + 2][3] < 1.0:
                seq = [round(x[3], 2) for x in s[i - 2:i + 4]]
                trav = math.hypot(s[i + 3][5] - s[td][5], s[i + 3][6] - s[td][6])
                after = next(((round(x[0] - s[i][0], 1), x[2], x[1]) for x in s[i:i + 30] if x[2] != 1 and x[2] != s[i - 1][2]), None)
                print(f"{lab:12s} uid {uid} tgt {tgt.get(uid)} td {s[td][0]:.1f} brake {s[i][0]:.1f} (+{s[i][0]-s[td][0]:.1f}s) travel {trav:.1f} m "
                      f"speeds {seq} st/slot before {s[i-1][1]}/{s[i-1][2]} -> next slot {after}")
                break
