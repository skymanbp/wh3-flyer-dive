"""TEST-ONLY (AIR-DIVE-BRACE-W1, dive bobbing): per-model altitude of every multi-model flyer lane from the
per-soldier reader (entity_read_slice.txt, U lines, y every 0.2 s).
Window: from the lane's charge order to the lead touchdown + 8 s (verdict t). Per model:
  flips  = sign changes of the vertical speed among steps with |dy| >= STEP m (one 0.2 s tick)
  rises  = climbs of >= RISE m out of a local low that is within NEAR m of that model's lowest point in the
           window (a model that had come down and goes back up: the visible bob)
Per lane: models, median / max flips and rises, models with >= 1 rise.
usage: python -I osc.py <prefix>... [--detail]"""
import collections, json, os, re, statistics, sys
from pathlib import Path
H = Path(__file__).resolve().parent
STEP, RISE, NEAR, AFTER = 0.3, 1.0, 1.5, 8000
TYPE_OF = {}
for line in (H / "jobs_e.txt").read_text("utf-8").splitlines():
    q = line.split()
    if q and not q[0].startswith("#"):
        TYPE_OF[q[3].split(",")[0]] = q[0].split("_", 1)[1]


def series(lab, uid):
    out, t = collections.defaultdict(list), 0
    for line in (H / "runs" / lab / "entity_read_slice.txt").read_text("utf-8", errors="replace").splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "T":
            t = int(p[1])
        elif p[0] == "U" and p[1] == uid:
            for m in p[8:]:
                f = m.split(",")
                if len(f) >= 13:
                    out[f[0]].append((t, float(f[12])))
    return out


def model_counts(pts):
    ys = [y for _t, y in pts]
    if len(ys) < 3:
        return None
    low = min(ys)
    dys = [b - a for a, b in zip(ys, ys[1:])]
    sig = [d for d in dys if abs(d) >= STEP]
    flips = sum(1 for a, b in zip(sig, sig[1:]) if (a > 0) != (b > 0))
    rises, i = 0, 1
    minimum = ys[0]
    for y in ys[1:]:
        if y < minimum:
            minimum = y
        elif y - minimum >= RISE and minimum - low <= NEAR:
            rises += 1
            minimum = y          # count the next one only after another low
        if y < minimum:
            minimum = y
    return flips, rises


def lanes(lab):
    d = H / "runs" / lab
    v = json.loads((d / "verdict.json").read_text("utf-8"))
    orders = {}
    for line in (d / "status.txt").read_text("utf-8", errors="replace").splitlines():
        m = re.match(r"(\d+) charge (\d+) ordered uid=(\d+)", line)
        if m:
            orders[m.group(3)] = int(m.group(1))
    for l in v["lanes"]:
        if (l.get("flyer_men") or 0) <= 1 or l.get("t") is None:
            continue
        uid = str(l["flyer_uid"])
        t0, t1 = orders.get(uid), int(l["t"] * 1000) + AFTER
        if t0 is None:
            continue
        per = {k: model_counts([(t, y) for t, y in pts if t0 <= t <= t1]) for k, pts in series(lab, uid).items()}
        per = {k: c for k, c in per.items() if c}
        yield l, per


def main(argv):
    detail = "--detail" in argv
    pres = [a for a in argv if not a.startswith("--")]
    for pre in pres:
        by = collections.defaultdict(list)
        for lab in sorted(x for x in os.listdir(H / "runs") if x.startswith(pre) and (H / "runs" / x / "verdict.json").exists()):
            try:
                for l, per in lanes(lab):
                    if not per:
                        continue
                    f = [c[0] for c in per.values()]
                    r = [c[1] for c in per.values()]
                    by[TYPE_OF.get(l["flyer"], l["flyer"])].append((lab, l["lane"], len(per), f, r))
                    if detail:
                        print(f"  {lab} lane {l['lane']}: models {len(per)} flips {f} rises {r}")
            except FileNotFoundError:
                continue
        print(f"== {pre}: type lanes | models | flips/model med max | rises/model med max | models with a rise")
        for t, L in sorted(by.items()):
            f = [x for e in L for x in e[3]]
            r = [x for e in L for x in e[4]]
            print(f"{t:10s} {len(L):2d} | {len(f):3d} | {statistics.median(f):4.1f} {max(f):3d} | "
                  f"{statistics.median(r):4.1f} {max(r):3d} | {sum(1 for x in r if x)}/{len(r)}")


if __name__ == "__main__":
    main(sys.argv[1:])
