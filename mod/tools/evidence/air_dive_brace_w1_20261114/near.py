"""Per entity-read tick (0.2 s): flyer position (repath T sample nearest), nearest target model distance,
models within 3/5/7 m, target models' mean displacement since previous tick, and front of target along charge axis.
usage: python -I near.py <run_dir> <flyer_uid> <target_uid> <t0> <t1>"""
import sys, math
from pathlib import Path
run, fu, tu, a, b = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
d = Path(run)
T = []
for l in (d / "ld_repath_probe_slice.txt").read_text("utf-8", errors="replace").splitlines():
    p = l.split()
    if p and p[0] == "T" and p[2] == fu:
        T.append((int(p[1]) / 1000, float(p[11]), float(p[12]), math.hypot(float(p[7]), float(p[8])), int(p[4]), int(p[5]) & 0xffff))
U = {}; t = None
for l in open(d / "entity_read_slice.txt", encoding="utf-8", errors="replace"):
    p = l.split()
    if not p: continue
    if p[0] == "T" and len(p) == 2: t = int(p[1]) / 1000
    elif p[0] == "U" and p[1] == tu and t is not None and a - 0.5 <= t <= b:
        pts = []
        for part in p[7:]:
            q = part.split(",")
            if len(q) >= 14:
                pts.append((q[0], float(q[1]), float(q[2]), int(q[6])))
        U[t] = pts
prev = None
for tt in sorted(U):
    if tt < a: prev = U[tt]; continue
    f = min(T, key=lambda s: abs(s[0] - tt))
    ds = sorted(math.hypot(x - f[1], z - f[2]) for _, x, z, _ in U[tt])
    mv = ""
    if prev:
        pm = {k: (x, z) for k, x, z, _ in prev}
        dd = [math.hypot(x - pm[k][0], z - pm[k][1]) for k, x, z, _ in U[tt] if k in pm]
        mv = f"mean_move {sum(dd)/len(dd):.2f} max_move {max(dd):.2f}"
    zs = sorted(z for _, x, z, _ in U[tt] if abs(x - f[1]) < 8)
    print(f"t{tt:6.1f} fly z{f[2]:7.2f} v{f[3]:5.1f} st{f[4]} sl{f[5]} | nearest {ds[0]:4.1f} n<3 {sum(x<3 for x in ds):2d} n<5 {sum(x<5 for x in ds):2d} n<7 {sum(x<7 for x in ds):2d} | front-z(|dx|<8) {zs[-1] if zs else float('nan'):.1f}/{zs[0] if zs else float('nan'):.1f} | {mv}")
    prev = U[tt]
