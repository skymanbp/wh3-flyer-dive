"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 4, mass-cut early stops): how fast the crowd slows a landed single-model
flyer, per flyer type, for two batch prefixes on the same lanes (spear + halberd lanes only).
Per lane, from touchdown (probe T samples, 0.1 s):
  d2  = metres from touchdown where planar speed first falls below SKIP_SPEED (2 m/s; below it dv_contact
        lets the engine's melee engage happen) -- None if it never does within 8 s
  v05 / v10 = speed 0.5 s / 1.0 s after touchdown
  ppl = enemy models within 6 m at 0.5 s (N lines)
  mass = the flyer's +0x23c-adjacent probe field 'mass' as sampled
usage: python -I decel_an.py <prefixA> <prefixB> [--detail]"""
import collections, math, os, statistics, sys
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import brace_an as b

SKIP = 2.0
SHORT = {}
for line in (H / "jobs_e.txt").read_text("utf-8").splitlines():
    q = line.split()
    if q and not q[0].startswith("#"):
        SHORT[q[3].split(",")[0]] = q[0].split("_", 1)[1]


def lanes(pre):
    out = collections.defaultdict(list)
    for lab in sorted(d for d in os.listdir(H / "runs") if d.startswith(pre) and (H / "runs" / d / "verdict.json").exists()):
        for rec in b.lanes(lab):
            if rec["men"] != 1 or rec["touchdown"] is None or rec["target"] == "militia":
                continue
            s, td = rec["s"], rec["touchdown"]
            t0 = s[td]["t"]
            d2 = None
            for r in s[td:]:
                if r["t"] > t0 + 8:
                    break
                if math.hypot(r["vx"], r["vz"]) < SKIP:
                    d2 = math.hypot(r["x"] - s[td]["x"], r["z"] - s[td]["z"])
                    break

            def at(dt):
                r = min(s[td:], key=lambda q: abs(q["t"] - (t0 + dt)))
                return math.hypot(r["vx"], r["vz"])
            n05 = rec["N"].get(min(rec["N"], key=lambda ms: abs(ms / 1000 - (t0 + 0.5))), {}) if rec["N"] else {}
            early = rec["stop"] is not None and rec["travel"] is not None and rec["travel"] < 15 and rec.get("maxd", 0) < 15
            out[SHORT.get(rec["flyer"], rec["flyer"])].append(dict(lab=lab, lane=rec["lane"], d2=d2, v05=at(0.5),
                                                                   v10=at(1.0), ppl=n05.get("n6"), mass=s[td]["mass"],
                                                                   early=early, target=rec["target"]))
    return out


def med(x):
    x = [v for v in x if v is not None]
    return round(statistics.median(x), 2) if x else None


A, B = lanes(sys.argv[1]), lanes(sys.argv[2])
print(f"type      | mass A/B | early A B | d<2m/s med A -> B (lanes slowed below 2 m/s within 15 m) | v0.5 A -> B | "
      f"v1.0 A -> B | enemies within 6 m at 0.5 s A -> B")
for t in sorted(set(A) | set(B)):
    a, c = A.get(t, []), B.get(t, [])
    print(f"{t:9s} | {med([r['mass'] for r in a])}/{med([r['mass'] for r in c])} | "
          f"{sum(r['early'] for r in a)}/{len(a)} {sum(r['early'] for r in c)}/{len(c)} | "
          f"{med([r['d2'] for r in a])} -> {med([r['d2'] for r in c])} "
          f"({sum(1 for r in a if r['d2'] is not None and r['d2'] < 15)} -> {sum(1 for r in c if r['d2'] is not None and r['d2'] < 15)}) | "
          f"{med([r['v05'] for r in a])} -> {med([r['v05'] for r in c])} | {med([r['v10'] for r in a])} -> "
          f"{med([r['v10'] for r in c])} | {med([r['ppl'] for r in a])} -> {med([r['ppl'] for r in c])}")
allA = [r for v in A.values() for r in v]
allB = [r for v in B.values() for r in v]
print(f"ALL       | early {sum(r['early'] for r in allA)}/{len(allA)} -> {sum(r['early'] for r in allB)}/{len(allB)} | "
      f"slowed below 2 m/s within 15 m {sum(1 for r in allA if r['d2'] is not None and r['d2'] < 15)} -> "
      f"{sum(1 for r in allB if r['d2'] is not None and r['d2'] < 15)} | v1.0 {med([r['v10'] for r in allA])} -> "
      f"{med([r['v10'] for r in allB])}")
if "--detail" in sys.argv:
    for name, D in (("A", A), ("B", B)):
        for t, rs in sorted(D.items()):
            for r in rs:
                if r["early"]:
                    print(f"  {name} {t} {r['lab']} lane {r['lane']} {r['target']}: d2 {r['d2']}, v0.5 {r['v05']:.1f}, "
                          f"v1.0 {r['v10']:.1f}, mass {r['mass']}")
