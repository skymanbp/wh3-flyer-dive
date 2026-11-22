"""Reference battle report for every lane (flyers and ground monsters alike): start and target from the driver's
'lane N flyer=... uid=U at=x,z target=... at=x,z' lines in stdout.txt (the probe's S lines only cover flyers).
Per lane, from the first tick a model is within 8 m of the target centre (along the approach line): every 0.4 s
for 6 s the median depth past the centre, median speed (+0x1c8) and move states (+0x26c); then the deepest point
over the whole record and the depth 10 s after contact. Usage: python ref_report.py <pos3.txt> <run dir>"""
import math
import re
import statistics as st
import sys
from collections import Counter
from pathlib import Path

pos_file, run = Path(sys.argv[1]), Path(sys.argv[2])
lane = {}
for m in re.finditer(r"lane (\d+) flyer=(\S+) uid=(\d+) at=([-\d.]+),([-\d.]+) target=(\S+) uid=\d+ at=([-\d.]+),([-\d.]+)",
                     (run / "stdout.txt").read_text("utf-8")):
    n, fk, uid, sx, sz, tk, tx, tz = m.groups()
    lane[uid] = (int(n), fk, tk, float(sx), float(sz), float(tx), float(tz))
ticks = {}
for line in pos_file.read_text("utf-8").splitlines():
    p = line.split()
    if p and p[0] == "FAIL":
        sys.exit("REFUSING: " + line)
    if p and p[0] == "P" and p[2] in lane:
        cells = [[float(v) if i < 3 else int(v) for i, v in enumerate(c.split(":"))] for c in p[3:]]
        ticks.setdefault(p[2], []).append((int(p[1]), cells))
if len(lane) != 16 or len(ticks) != 16:
    sys.exit(f"REFUSING: lanes={len(lane)} with ticks={len(ticks)}")
for uid, (n, fk, tk, sx, sz, tx, tz) in sorted(lane.items(), key=lambda kv: kv[1][0]):
    d = math.hypot(tx - sx, tz - sz)
    ax, az = (tx - sx) / d, (tz - sz) / d
    rows = [(ms, [((c[0] - tx) * ax + (c[1] - tz) * az, c[2], c[3]) for c in cells]) for ms, cells in ticks[uid]]
    t0 = next((ms for ms, cs in rows if cs and max(c[0] for c in cs) > -8.0), None)
    print(f"== lane {n}: {fk} -> {tk}")
    if t0 is None:
        print("   never within 8 m")
        continue
    for ms, cs in rows:
        if t0 <= ms <= t0 + 6000 and (ms - t0) % 400 == 0 and cs:
            print(f"   +{(ms - t0) / 1000:3.1f}s depth {st.median(c[0] for c in cs):6.1f} speed "
                  f"{st.median(c[1] for c in cs):5.1f} move {dict(Counter(c[2] for c in cs))}")
    deep = max(max(c[0] for c in cs) for ms, cs in rows if cs)
    at10 = [st.median(c[0] for c in cs) for ms, cs in rows if cs and ms >= t0 + 10000][:1]
    print(f"   deepest {deep:.1f}  median depth at +10s {at10[0] if at10 else float('nan'):.1f}")
