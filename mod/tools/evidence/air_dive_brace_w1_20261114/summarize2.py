"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 2): early stops per flyer TYPE x target for any batch prefix,
keyed by the lane's own flyer key (works for packed battles with several types per run).
Also counts goal-collapse stops (movement goal +0x1e0 jumps from > 5 m to < 1 m between touchdown and stop)
and, for packed runs, lanes whose flyer stopped nearer another lane's centre line than its own.
usage: python -I summarize2.py <prefix> [<prefix>...]"""
import collections, json, math, os, re, sys
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import brace_an as b

TYPE_OF = {}
for f in H.glob("jobs_e.txt"):
    for line in f.read_text("utf-8").splitlines():
        q = line.split()
        if q and not q[0].startswith("#"):
            TYPE_OF[q[3].split(",")[0]] = q[0].split("_", 1)[1]


def lane_cross(v, x, z):
    fr = v.get("lane_frame") or {}
    ax, az = fr.get("axis_x", 0.024), fr.get("axis_z", -1.0)
    # signed distance along the across-lanes direction (perpendicular to the charge axis)
    return -((x - fr.get("centre_x", 0)) * (-az) + (z - fr.get("centre_z", 0)) * ax)   # sign checked on batch E touchdowns


def main(prefixes):
    lanes, early, collapse, causes, wrong = (collections.Counter(), collections.Counter(), collections.Counter(),
                                             collections.defaultdict(collections.Counter), [])
    runs = 0
    for pre in prefixes:
        labs = sorted(d for d in os.listdir(H / "runs") if d.startswith(pre) and (H / "runs" / d / "verdict.json").exists())
        runs += len(labs)
        for lab in labs:
            v = json.loads((H / "runs" / lab / "verdict.json").read_text("utf-8"))
            offs = v.get("lane_offsets_m") or []
            for rec in b.lanes(lab):
                if rec["men"] != 1:
                    continue
                k = (TYPE_OF.get(rec["flyer"], rec["flyer"]), rec["target"])
                lanes[k] += 1
                s, td, i = rec["s"], rec["touchdown"], rec["stop"]
                if i is None or rec["travel"] is None or rec["travel"] >= 15 or rec.get("maxd", 0) >= 15:
                    continue
                early[k] += 1
                causes[k[0]][b.cause(rec).split("(")[0]] += 1
                gd = [math.hypot(r["gx"] - r["x"], r["gz"] - r["z"]) for r in s[td:i + 1]]
                if any(a > 5 and c < 1.0 for a, c in zip(gd, gd[1:])):
                    collapse[k] += 1
                if offs:
                    c = lane_cross(v, s[i]["x"], s[i]["z"])
                    near = min(range(len(offs)), key=lambda j: abs(offs[j] - c))
                    if near != rec["lane"] - 1:
                        wrong.append((lab, rec["lane"], offs[rec["lane"] - 1], round(c, 1)))
    print(f"prefixes {prefixes}: {runs} runs (single-model lanes only)")
    print("type       spear   halb    militia | collapse | causes")
    for t in sorted({k[0] for k in lanes}):
        print(f"{t:10s}", " ".join(f"{early[(t, g)]}/{lanes[(t, g)]:<5d}" for g in ("spear", "halb", "militia")),
              "|", sum(collapse[(t, g)] for g in ("spear", "halb", "militia")), "|", dict(causes[t]))
    print("spear+halb:", sum(v for (t, g), v in early.items() if g != "militia"), "/",
          sum(v for (t, g), v in lanes.items() if g != "militia"),
          " militia:", sum(v for (t, g), v in early.items() if g == "militia"), "/",
          sum(v for (t, g), v in lanes.items() if g == "militia"),
          " goal-collapse:", sum(collapse.values()))
    if wrong:
        print("stopped nearer another lane:", wrong)


if __name__ == "__main__":
    main(sys.argv[1:])
