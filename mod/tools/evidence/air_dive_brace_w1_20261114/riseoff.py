"""TEST-ONLY: target_ground_rise_m per lane offset, by batch prefix (single-model lanes only)."""
import json, os, sys, statistics, collections
from pathlib import Path
H = Path(__file__).resolve().parent
for pre in sys.argv[1:]:
    by = collections.defaultdict(list)
    for d in sorted(os.listdir(H / "runs")):
        if not d.startswith(pre) or not (H / "runs" / d / "verdict.json").exists():
            continue
        v = json.loads((H / "runs" / d / "verdict.json").read_text("utf-8"))
        for l in v["lanes"]:
            r = l.get("target_ground_rise_m")
            if r is not None and l.get("flyer_men") == 1:
                by[v["lane_offsets_m"][l["lane"] - 1]].append(r)
    print(pre, {k: (len(x), round(min(x), 2), round(statistics.median(x), 2), round(max(x), 2)) for k, x in sorted(by.items())})
