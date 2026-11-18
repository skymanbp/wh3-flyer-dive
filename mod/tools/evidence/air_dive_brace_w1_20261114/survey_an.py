"""TEST-ONLY (AIR-DIVE-BRACE-W1): map flatness from a survey run's status.txt (S lines).
Per map: height range, steepest 50 m step (slope %), placement misses (the unit landed > 15 m from where it was
sent: map edge or an obstacle), and the widest band across the lanes whose height stays within +-0.5 m.
usage: python -I survey_an.py <run label>..."""
import collections, math, sys
from pathlib import Path
H = Path(__file__).resolve().parent


def load(lab):
    pts = {}
    for line in (H / "runs" / lab / "status.txt").read_text("utf-8", errors="replace").splitlines():
        p = line.split()
        if len(p) >= 9 and p[1] == "S":
            a, b = int(p[2]), int(p[3])
            wx, wz, x, z, y = map(float, p[4:9])
            pts[(a, b)] = (y, math.hypot(x - wx, z - wz))
    return pts


for lab in sys.argv[1:]:
    pts = load(lab)
    if not pts:
        print(lab, "no S lines")
        continue
    good = {k: v for k, v in pts.items() if v[1] <= 15}
    miss = sorted(k for k, v in pts.items() if v[1] > 15)
    ys = [v[0] for v in good.values()]
    steps = []
    for (a, b), (y, _d) in good.items():
        for da, db in ((50, 0), (0, 50)):
            n = good.get((a + da, b + db))
            if n:
                steps.append((abs(n[0] - y) / 50 * 100, (a, b), (a + da, b + db)))
    steps.sort(reverse=True)
    # per across column: height range along the attack axis
    col = collections.defaultdict(list)
    for (a, b), (y, _d) in good.items():
        col[a].append(y)
    ref = sorted(ys)[len(ys) // 2]
    flat = sorted(a for a, v in col.items() if max(v) - min(v) <= 1.0 and all(abs(y - ref) <= 0.5 for y in v))
    runs, cur = [], []
    for a in flat:
        if cur and a - cur[-1] != 50:
            runs.append(cur); cur = []
        cur.append(a)
    if cur:
        runs.append(cur)
    widest = max(runs, key=len) if runs else []
    print(f"== {lab}: points {len(pts)} placed {len(good)} missed {len(miss)} | height {min(ys):.2f}..{max(ys):.2f} "
          f"(median {ref:.2f}) | steepest 50 m step {steps[0][0]:.2f}% at {steps[0][1]}->{steps[0][2]} | "
          f"95th pct step {steps[len(steps) // 20][0]:.2f}%")
    print(f"   widest band within +-0.5 m of median and <= 1.0 m along the attack axis: across "
          f"{widest[0] if widest else None}..{widest[-1] if widest else None} m ({len(widest)} columns)")
    if miss:
        print("   missed points (across, along):", miss[:40])
    print("   column ranges:", " ".join(f"{a}:{min(v):.1f}/{max(v):.1f}" for a, v in sorted(col.items())))
