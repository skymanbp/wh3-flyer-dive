"""TEST-ONLY (AIR-DIVE-BRACE-W1): how far each TARGET unit's centre moved between its lane's charge order and
the flyer's touchdown, in runs made with the old harness (no target setup): per-soldier reader U lines of the
target uid (centroid of its models' x,z). Median / max per target type.
usage: python -I retreat_old.py <prefix>..."""
import collections, json, math, os, re, statistics, sys
from pathlib import Path
H = Path(__file__).resolve().parent
SHORT = {"wh_main_emp_inf_spearmen_1": "spear", "wh_main_emp_inf_halberdiers": "halb",
         "wh_dlc04_emp_inf_free_company_militia_0": "militia"}
JOBT = {}
for f in H.glob("jobs_*.txt"):
    for line in f.read_text("utf-8").splitlines():
        q = line.split()
        if q and not q[0].startswith("#"):
            for a in q[4:]:
                if a.startswith("--targets="):
                    JOBT[q[0]] = a.split("=", 1)[1].split(",")

for pre in sys.argv[1:]:
    moved = collections.defaultdict(list)
    for lab in sorted(x for x in os.listdir(H / "runs") if x.startswith(pre) and (H / "runs" / x / "verdict.json").exists()):
        d = H / "runs" / lab
        v = json.loads((d / "verdict.json").read_text("utf-8"))
        order = {}
        for line in (d / "status.txt").read_text("utf-8", errors="replace").splitlines():
            m = re.match(r"(\d+) charge (\d+) ordered", line)
            if m:
                order[int(m.group(2))] = int(m.group(1))
        want = {}
        for l in v["lanes"]:
            if l.get("t") is None or l["lane"] not in order:
                continue
            want[str(l["target_uid"])] = (order[l["lane"]], int(l["t"] * 1000), SHORT.get((JOBT.get(lab) or ["?"] * 9)[l["lane"] - 1], "?"))
        cen = collections.defaultdict(list)
        t = 0
        er = d / "entity_read_slice.txt"
        if not er.exists():
            continue
        for line in er.read_text("utf-8", errors="replace").splitlines():
            p = line.split()
            if not p:
                continue
            if p[0] == "T":
                t = int(p[1])
            elif p[0] == "U" and p[1] in want:
                t0, t1, _k = want[p[1]]
                if t0 <= t <= t1:
                    xs = [m.split(",") for m in p[8:]]
                    xs = [(float(f[1]), float(f[2])) for f in xs if len(f) >= 3]
                    if xs:
                        cen[p[1]].append((sum(a for a, _ in xs) / len(xs), sum(b for _, b in xs) / len(xs)))
        for uid, pts in cen.items():
            if len(pts) >= 2:
                moved[want[uid][2]].append(math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]))
    print(pre, {k: (len(v), round(statistics.median(v), 1), round(max(v), 1)) for k, v in sorted(moved.items())})
