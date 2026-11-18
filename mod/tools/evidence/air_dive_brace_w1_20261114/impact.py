"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 3, mass cut): impact per flyer type for two batch prefixes run on the
same lanes -- target men knocked down within 1.5 s of touchdown (entity reader), target hp loss in 1.5 s,
depth into the target (single-model lanes), touchdown speed. Every lane with a touchdown, single- and
multi-model alike (multi-model: the entity block only).
usage: python -I impact.py <prefixA> <prefixB>"""
import collections, json, os, statistics, sys
from pathlib import Path
H = Path(__file__).resolve().parent
SHORT = {}
for f in ("jobs_e.txt",):
    for line in (H / f).read_text("utf-8").splitlines():
        q = line.split()
        if q and not q[0].startswith("#"):
            SHORT[q[3].split(",")[0]] = q[0].split("_", 1)[1]


def collect(pre):
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    for lab in sorted(d for d in os.listdir(H / "runs") if d.startswith(pre)):
        p = H / "runs" / lab / "verdict.json"
        if not p.exists():
            continue
        v = json.loads(p.read_text("utf-8"))
        for l in v["lanes"]:
            if l.get("t") is None:
                continue
            t = SHORT.get(l["flyer"], l["flyer"])
            e = l.get("entity") or {}
            if e.get("men_knocked") is not None:
                out[t]["knock"].append(e["men_knocked"])
            if l.get("target_hp_loss_1_5s") is not None:
                out[t]["hp15"].append(l["target_hp_loss_1_5s"])
            if l.get("target_men_lost_1_5s") is not None:
                out[t]["lost15"].append(l["target_men_lost_1_5s"])
            if l.get("depth_into_target_m") is not None:
                out[t]["depth"].append(l["depth_into_target_m"])
    return out


def med(x):
    return round(statistics.median(x), 3) if x else None


a, b = collect(sys.argv[1]), collect(sys.argv[2])
print(f"type       | knocked 1.5s {sys.argv[1]} -> {sys.argv[2]} | hp loss 1.5s | men lost 1.5s | depth m | lanes")
tot = collections.defaultdict(lambda: [[], []])
for t in sorted(set(a) | set(b)):
    row = []
    for k in ("knock", "hp15", "lost15", "depth"):
        row.append(f"{med(a[t][k])} -> {med(b[t][k])}")
        tot[k][0] += a[t][k]
        tot[k][1] += b[t][k]
    print(f"{t:10s} | " + " | ".join(row) + f" | {len(a[t]['hp15'])}/{len(b[t]['hp15'])}")
print("ALL        | " + " | ".join(f"{med(tot[k][0])} -> {med(tot[k][1])}" for k in ("knock", "hp15", "lost15", "depth")))
