"""TEST-ONLY (AIR-DIVE-BRACE-W1, bounded slide): per flyer type, from verdict.json lanes (single-model only):
travel after touchdown (m), time to stop (s), share stopped within the record, depth into target (m),
target hp loss 1.5 s / 5 s, touchdown speed. usage: python -I slide.py <prefix>..."""
import json, os, sys, statistics, collections
from pathlib import Path
H = Path(__file__).resolve().parent
TYPE_OF = {}
for line in (H / "jobs_e.txt").read_text("utf-8").splitlines():
    q = line.split()
    if q and not q[0].startswith("#"):
        TYPE_OF[q[3].split(",")[0]] = q[0].split("_", 1)[1]
F = ("travel_after_touchdown_m", "time_to_stop_s", "depth_into_target_m", "target_hp_loss_1_5s", "target_hp_loss_5s",
     "touchdown_speed_mps")


def med(v):
    v = [x for x in v if isinstance(x, (int, float))]
    return round(statistics.median(v), 2) if v else None


for pre in sys.argv[1:]:
    by = collections.defaultdict(list)
    for d in sorted(os.listdir(H / "runs")):
        if not d.startswith(pre) or not (H / "runs" / d / "verdict.json").exists():
            continue
        for l in json.loads((H / "runs" / d / "verdict.json").read_text("utf-8"))["lanes"]:
            if l.get("flyer_men") == 1 and l.get("status") == "OK":
                by[TYPE_OF.get(l["flyer"], l["flyer"])].append(l)
    print(f"== {pre}: type n | travel_m med/max | stop_s med | stopped | depth_m med | hp1.5 med | hp5 med | v_td med")
    allv = collections.defaultdict(list)
    for t in sorted(by):
        L = by[t]
        tr = [l.get("travel_after_touchdown_m") for l in L]
        for f in F:
            allv[f] += [l.get(f) for l in L]
        allv["stopped"] += [bool(l.get("stopped")) for l in L]
        print(f"{t:10s} {len(L):2d} | {med(tr)} / {max(x for x in tr if x is not None):.1f} | {med([l.get('time_to_stop_s') for l in L])} | "
              f"{sum(bool(l.get('stopped')) for l in L)}/{len(L)} | {med([l.get('depth_into_target_m') for l in L])} | "
              f"{med([l.get('target_hp_loss_1_5s') for l in L])} | {med([l.get('target_hp_loss_5s') for l in L])} | "
              f"{med([l.get('touchdown_speed_mps') for l in L])}")
    print(f"ALL        {len(allv['stopped'])} | {med(allv['travel_after_touchdown_m'])} | {med(allv['time_to_stop_s'])} | "
          f"{sum(allv['stopped'])}/{len(allv['stopped'])} | {med(allv['depth_into_target_m'])} | "
          f"{med(allv['target_hp_loss_1_5s'])} | {med(allv['target_hp_loss_5s'])} | {med(allv['touchdown_speed_mps'])}")
