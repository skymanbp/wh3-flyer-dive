"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 4): read ld_bob_probe_slice.txt (B / E / C lines).
  rises      per model: climbs >= RISE m out of a low within NEAR m of its lowest point (osc.py rule), from the
             first landed model of the unit to +12 s
  --fields   for every rise with dumps on both sides, the body / flight-controller dwords that changed between
             two ticks before the rise start and the rise start; counted over rises, and the same count over
             non-rising followers of the same unit at the same ticks (controls)
  --model    the B series of one model (uid:i)
usage: python -I bob_an.py <run label> [--fields] [--model uid:i]"""
import collections, sys
from pathlib import Path
H = Path(__file__).resolve().parent
RISE, NEAR, WINDOW = 1.0, 1.5, 12000
CUT = collections.Counter()      # dump lines cut short in the log, by kind (reported, not hidden)


def load(lab):
    B = collections.defaultdict(list)
    E, C = {}, {}
    for raw in (H / "runs" / lab / "ld_bob_probe_slice.txt").read_text("utf-8", errors="replace").splitlines():
        p = raw.split()
        if not p:
            continue
        if p[0] == "B" and len(p) >= 16:
            B[(p[2], int(p[3]))].append(dict(t=int(p[1]), body=p[4], lay=int(p[5]), fm=int(p[6]), st=int(p[7]),
                                            y=float(p[8]), vy=float(p[9]), x=float(p[10]), z=float(p[11]),
                                            gx=float(p[12]), gz=float(p[13]), cap=float(p[14]), vt=p[15]))
        elif p[0] in ("E", "C"):
            hexs = p[4] if p[0] == "E" else (p[5] if len(p) > 5 else "")
            if len(hexs) % 2 or not hexs:
                CUT[p[0]] += 1
                continue
            (E if p[0] == "E" else C)[(p[2], int(p[3]), int(p[1]))] = bytes.fromhex(hexs)
    return B, E, C


def first_landed(B):
    out = {}
    for (uid, _i), s in B.items():
        for r in s:
            if r["lay"] == 0:
                out[uid] = min(out.get(uid, 1 << 30), r["t"])
                break
    return out


def rises(s, t0):
    w = [r for r in s if t0 - 2000 <= r["t"] <= t0 + WINDOW]
    if len(w) < 3:
        return []
    low = min(r["y"] for r in w)
    out, mn, mn_i = [], w[0]["y"], 0
    for k, r in enumerate(w[1:], 1):
        if r["y"] < mn:
            mn, mn_i = r["y"], k
        elif r["y"] - mn >= RISE and mn - low <= NEAR:
            out.append((w[mn_i]["t"], r["t"]))      # (the low = rise start, the tick it crossed +1 m)
            mn, mn_i = r["y"], k
    return out


def main(argv):
    lab = argv[0]
    B, E, C = load(lab)
    t0s = first_landed(B)
    by_unit = collections.defaultdict(list)
    for (uid, i), s in sorted(B.items()):
        if uid in t0s:
            by_unit[uid].append((i, rises(s, t0s[uid])))
    print(f"dump lines cut short: {dict(CUT)}")
    for uid, ms in sorted(by_unit.items()):
        print(f"unit {uid}: lead landed t={t0s[uid]}, models {len(ms)}, rising {sum(1 for _, r in ms if r)}: "
              + " ".join(f"{i}:{[(a - t0s[uid], b - t0s[uid]) for a, b in r]}" for i, r in ms if r))
    if "--model" in argv:
        uid, i = argv[argv.index("--model") + 1].split(":")
        for r in B[(uid, int(i))]:
            if t0s[uid] - 2000 <= r["t"] <= t0s[uid] + WINDOW:
                print(f"  t{r['t'] - t0s[uid]:+6d} lay {r['lay']} fm {r['fm']} st {r['st']:3d} y {r['y']:.2f} "
                      f"vy {r['vy']:+.2f} goal ({r['gx']:.1f},{r['gz']:.1f}) pos ({r['x']:.1f},{r['z']:.1f}) "
                      f"cap {r['cap']:.2f} vt {r['vt']}")
    if "--fields" in argv:
        for name, D in (("body", E), ("fc", C)):
            hit, ctl, nr, nc = collections.Counter(), collections.Counter(), 0, 0
            for uid, ms in by_unit.items():
                ticks = sorted({t for (u, _i, t) in D if u == uid})
                for i, rs in ms:
                    for start, _cross in rs:
                        k = [t for t in ticks if t <= start]
                        if len(k) < 3 or (uid, i, k[-1]) not in D or (uid, i, k[-3]) not in D:
                            continue
                        a, b = D[(uid, i, k[-3])], D[(uid, i, k[-1])]
                        nr += 1
                        for o in range(0, min(len(a), len(b)) - 3, 4):
                            if a[o:o + 4] != b[o:o + 4]:
                                hit[o] += 1
                        for j, rj in ms:
                            if rj or j == i or (uid, j, k[-3]) not in D or (uid, j, k[-1]) not in D:
                                continue
                            ca, cb = D[(uid, j, k[-3])], D[(uid, j, k[-1])]
                            nc += 1
                            for o in range(0, min(len(ca), len(cb)) - 3, 4):
                                if ca[o:o + 4] != cb[o:o + 4]:
                                    ctl[o] += 1
            print(f"== {name}: rises with dumps {nr}, control pairs {nc}")
            rows = sorted(hit, key=lambda o: (-(hit[o] / max(nr, 1) - ctl[o] / max(nc, 1)), o))[:25]
            for o in rows:
                print(f"  +0x{o:03x}: rises {hit[o]}/{nr}  controls {ctl[o]}/{nc}")


if __name__ == "__main__":
    main(sys.argv[1:])
