"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 3b): the slide-window table (probe W lines) against each single-model
lane's touchdown. Per flyer: where its first window opened relative to touchdown (metres along its track,
negative = before touchdown), whether it was on the ground then, when it was released and how far it had
come from touchdown by then.
usage: python -I window_an.py <prefix>..."""
import math, os, statistics, sys
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import brace_an as b


def wlines(lab):
    out = []
    for raw in (H / "runs" / lab / "ld_brace_probe_slice.txt").read_text("utf-8", errors="replace").splitlines():
        p = raw.split()
        if len(p) == 8 and p[0] == "W":
            out.append(dict(t=int(p[1]) / 1000, slot=int(p[2]), uid=p[3], ent=p[4], state=p[5],
                            x=float(p[6]), z=float(p[7])))
    return out


opened_vs_td, rel_travel, never = [], [], 0
for pre in sys.argv[1:]:
    for lab in sorted(d for d in os.listdir(H / "runs") if d.startswith(pre)):
        if not (H / "runs" / lab / "verdict.json").exists():
            continue
        W = wlines(lab)
        for rec in b.lanes(lab):
            if rec["men"] != 1 or rec["touchdown"] is None:
                continue
            s, td = rec["s"], rec["touchdown"]
            ents = {q["ent"] for q in s}
            mine = [w for w in W if w["ent"] in ents]
            first = next((w for w in mine if w["state"] == "new"), None)
            rel = next((w for w in mine if w["state"] == "released"), None)
            if first is None:
                never += 1
                print(f"{lab} lane {rec['lane']} {rec['flyer']}: no window opened")
                continue
            # signed distance of the window point from touchdown along the flight track
            near = min(s, key=lambda q: abs(q["t"] - first["t"]))
            dist = math.hypot(first["x"] - s[td]["x"], first["z"] - s[td]["z"])
            sign = -1 if first["t"] < s[td]["t"] else 1
            opened_vs_td.append(sign * dist)
            line = (f"{lab} lane {rec['lane']} {rec['flyer'][:30]:30s} vs {rec['target']:7s}: window opened "
                    f"{sign * dist:+6.1f} m from touchdown at t={first['t']:.1f} (layer then {near['lay']}, "
                    f"td t={s[td]['t']:.1f})")
            if rel:
                at = min(s, key=lambda q: abs(q["t"] - rel["t"]))
                tr = math.hypot(at["x"] - s[td]["x"], at["z"] - s[td]["z"])
                rel_travel.append(tr)
                line += f"; released t={rel['t']:.1f}, {tr:.1f} m from touchdown"
            else:
                line += "; not released"
            print(line)
print(f"windows opened: {len(opened_vs_td)}, before touchdown {sum(1 for d in opened_vs_td if d < -0.5)}, "
      f"none opened {never}; median opening {statistics.median(opened_vs_td) if opened_vs_td else None:+.1f} m")
if rel_travel:
    print(f"released {len(rel_travel)}: travel from touchdown at release median {statistics.median(rel_travel):.1f} m, "
          f"min {min(rel_travel):.1f}, max {max(rel_travel):.1f}; released under 15 m: "
          f"{sum(1 for t in rel_travel if t < 15)}")
