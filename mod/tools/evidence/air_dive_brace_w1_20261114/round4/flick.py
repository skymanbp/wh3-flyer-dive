"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 4): small up/down flicker -- models whose height alternates up and down
by >= 0.3 m on consecutive 0.2 s samples (osc flips) without a >= 1 m rise; per prefix: models, models with
>= 6 flips, and the amplitude band.
usage: python -I flick.py <prefix>..."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osc
for pre in sys.argv[1:]:
    tot = flick = 0
    amps, where = [], []
    for lab in sorted(x for x in os.listdir(osc.H / "runs") if x.startswith(pre) and (osc.H / "runs" / x / "verdict.json").exists()):
        for l, per in osc.lanes(lab):
            s = osc.series(lab, str(l["flyer_uid"]))
            for k, c in per.items():
                tot += 1
                if c[0] >= 6 and c[1] == 0:
                    flick += 1
                    ys = [y for t, y in s[k] if l["t"] * 1000 <= t <= l["t"] * 1000 + 8000]
                    amps.append(round(max(ys) - min(ys), 2))
                    where.append(f"{lab}:{l['lane']}:{osc.TYPE_OF.get(l['flyer'], l['flyer'])}")
    print(f"{pre}: models {tot}, flicker (>= 6 flips, no rise) {flick}, amplitude {amps}, {where}")
