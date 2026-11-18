"""TEST-ONLY (AIR-DIVE-BRACE-W1, dive bobbing): what each model's body was doing when it re-rose.
Reads MF lines (per-model body +0x710 flight mode, +0x104 layer, +0x26c state, +0xe4, height) of the patched
per-soldier reader. For every climb of >= RISE m out of a low within NEAR m of the model's lowest point
(window: charge order .. touchdown + 8 s), records (layer, flight mode, state) at the low and at the top, and
the time from the lead's touchdown. Prints a tally per prefix.
usage: python -I mf_an.py <prefix>..."""
import collections, json, os, re, sys
from pathlib import Path
H = Path(__file__).resolve().parent
RISE, NEAR, AFTER = 1.0, 1.5, 8000


def run_lanes(lab):
    d = H / "runs" / lab
    v = json.loads((d / "verdict.json").read_text("utf-8"))
    orders = {}
    for line in (d / "status.txt").read_text("utf-8", errors="replace").splitlines():
        m = re.match(r"(\d+) charge (\d+) ordered uid=(\d+)", line)
        if m:
            orders[m.group(3)] = int(m.group(1))
    want = {str(l["flyer_uid"]): (orders.get(str(l["flyer_uid"])), int(l["t"] * 1000)) for l in v["lanes"]
            if (l.get("flyer_men") or 0) > 1 and l.get("t") is not None}
    ser = collections.defaultdict(lambda: collections.defaultdict(list))
    t = 0
    for line in (d / "entity_read_slice.txt").read_text("utf-8", errors="replace").splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "T":
            t = int(p[1])
        elif p[0] == "MF" and p[1] in want:
            for m in p[2:]:
                f = m.split(",")
                if len(f) == 6:
                    ser[p[1]][f[0]].append((t, int(f[1]), int(f[2]), int(f[3]), float(f[4]), float(f[5])))
    return want, ser


def main(prefixes):
    for pre in prefixes:
        low_tally, top_tally, times, n_models, n_rise = collections.Counter(), collections.Counter(), [], 0, 0
        for lab in sorted(x for x in os.listdir(H / "runs") if x.startswith(pre) and (H / "runs" / x / "verdict.json").exists()):
            try:
                want, ser = run_lanes(lab)
            except FileNotFoundError:
                continue
            for uid, models in ser.items():
                t0, td = want[uid]
                if t0 is None:
                    continue
                for mid, pts in models.items():
                    w = [p for p in pts if t0 <= p[0] <= td + AFTER]
                    if len(w) < 3:
                        continue
                    n_models += 1
                    lowest = min(p[5] for p in w)
                    lo = w[0]
                    rose = False
                    for p in w[1:]:
                        if p[5] < lo[5]:
                            lo = p
                        elif p[5] - lo[5] >= RISE and lo[5] - lowest <= NEAR:
                            low_tally[(lo[2], lo[1], lo[3])] += 1
                            top_tally[(p[2], p[1], p[3])] += 1
                            times.append(round((lo[0] - td) / 1000, 1))
                            lo, rose = p, True
                    n_rise += rose
        print(f"== {pre}: models {n_models}, models with a rise {n_rise}")
        print("   at the low  (layer, flight, state):", low_tally.most_common(6))
        print("   at the top  (layer, flight, state):", top_tally.most_common(6))
        if times:
            c = collections.Counter(int(x) for x in times)
            print("   rise start, s after lead touchdown (floor):", sorted(c.items()))


if __name__ == "__main__":
    main(sys.argv[1:])
