"""TEST-ONLY (AIR-DIVE-BRACE-W1): did each target hold before contact? From status.txt: the target_setup
line per lane, TT lines (target position every 0.5 s) between that lane's charge order and its flyer's
touchdown (verdict t; end of record if none). Prints per lane: setup results, target type, distance the
target's centre moved and the share of samples it reported is_moving.
usage: python -I hold.py <label>..."""
import json, math, re, sys
from pathlib import Path
H = Path(__file__).resolve().parent
SHORT = {"wh_main_emp_inf_spearmen_1": "spear", "wh_main_emp_inf_halberdiers": "halb",
         "wh_dlc04_emp_inf_free_company_militia_0": "militia"}

for lab in sys.argv[1:]:
    d = H / "runs" / lab
    st = (d / "status.txt").read_text("utf-8", errors="replace").splitlines()
    v = json.loads((d / "verdict.json").read_text("utf-8")) if (d / "verdict.json").exists() else {"lanes": []}
    tds = {l["lane"]: l.get("t") for l in v["lanes"]}
    setup, order, tt, tkey = {}, {}, {}, {}
    for line in st:
        p = line.split()
        if len(p) < 2:
            continue
        m = re.match(r"\S+ lane (\d+) target_setup (.*)", line)
        if m:
            setup[int(m.group(1))] = m.group(2).strip()
        m = re.match(r"(\d+) charge (\d+) ordered", line)
        if m:
            order[int(m.group(2))] = int(m.group(1))
        m = re.match(r"\S+ lane (\d+) flyer=.* target=(\S+) ", line)
        if m:
            tkey[int(m.group(1))] = m.group(2)
        if p[1] == "TT" and len(p) >= 8:
            tt.setdefault(int(p[3]), []).append((int(p[2]), float(p[4]), float(p[5]), p[7] == "true"))
    print(f"== {lab}")
    for i in sorted(set(order) | set(setup)):
        t0 = order.get(i)
        t1 = int(tds[i] * 1000) if tds.get(i) else None
        pts = [x for x in tt.get(i, []) if t0 is not None and x[0] >= t0 and (t1 is None or x[0] <= t1)]
        if pts:
            moved = math.hypot(pts[-1][1] - pts[0][1], pts[-1][2] - pts[0][2])
            mv = sum(x[3] for x in pts) / len(pts)
            print(f"  lane {i} {SHORT.get(tkey.get(i), tkey.get(i))}: setup [{setup.get(i)}] moved {moved:.1f} m over "
                  f"{(pts[-1][0] - pts[0][0]) / 1000:.1f} s before touchdown, is_moving {mv:.0%}")
        else:
            print(f"  lane {i}: setup [{setup.get(i)}] no TT samples in the window (order {t0}, touchdown {t1})")
