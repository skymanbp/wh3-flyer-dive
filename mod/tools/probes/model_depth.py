"""Per lane: median over the flyer's models of each model's deepest point past the target centre in the first 8 s
after contact, and how many models got 5 m past it. Start / target from the driver's lane lines (as ref_report.py).
Usage: python model_depth.py <pos file> <run dir>"""
import math, re, statistics as st, sys
from pathlib import Path
pos, run = Path(sys.argv[1]), Path(sys.argv[2])
lane = {}
for m in re.finditer(r"lane (\d+) flyer=(\S+) uid=(\d+) at=([-\d.]+),([-\d.]+) target=(\S+) uid=\d+ at=([-\d.]+),([-\d.]+)",
                     (run / "stdout.txt").read_text("utf-8")):
    n, fk, uid, sx, sz, tk, tx, tz = m.groups()
    lane[uid] = (int(n), fk, tk, float(sx), float(sz), float(tx), float(tz))
ticks = {}
for line in pos.read_text("utf-8").splitlines():
    p = line.split()
    if p and p[0] == "FAIL":
        sys.exit("REFUSING: " + line)
    if p and p[0] == "P" and p[2] in lane:
        ticks.setdefault(p[2], []).append((int(p[1]), [tuple(float(v) for v in c.split(":")[:2]) for c in p[3:]]))
if not lane or not ticks:
    sys.exit(f"REFUSING: lanes {len(lane)} ticks {len(ticks)}")
for uid, (n, fk, tk, sx, sz, tx, tz) in sorted(lane.items(), key=lambda kv: kv[1][0]):
    d = math.hypot(tx - sx, tz - sz); ax, az = (tx - sx) / d, (tz - sz) / d
    rows = [(ms, [(x - tx) * ax + (z - tz) * az for x, z in cs]) for ms, cs in ticks.get(uid, [])]
    t0 = next((ms for ms, ds in rows if ds and max(ds) > -8.0), None)
    if t0 is None:
        print(f"lane {n:2d} {fk[:30]:30s} -> {tk[-12:]:12s} never within 8 m"); continue
    deep = {}
    for ms, ds in rows:
        if t0 <= ms <= t0 + 8000:
            for i, v in enumerate(ds):
                deep[i] = max(deep.get(i, -99), v)
    vals = list(deep.values())
    print(f"lane {n:2d} {fk[:30]:30s} -> {tk[-12:]:12s} models {len(vals):2d} median deepest {st.median(vals):5.1f} m, "
          f"{sum(v >= 5 for v in vals)}/{len(vals)} past 5 m")
