"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 4): time series of chosen body / flight-controller dwords of one model
(as hex, float and int) from the bob probe dumps.
usage: python -I bob_fields.py <run label> <uid:i> <body|fc> <off,off,...> [t_from t_to (ms after lead landing)]"""
import struct, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
import bob_an

lab, model, kind, offs = sys.argv[1:5]
t_from, t_to = (int(sys.argv[5]), int(sys.argv[6])) if len(sys.argv) > 6 else (-500, 4000)
uid, i = model.split(":")
i = int(i)
B, E, C = bob_an.load(lab)
t0 = bob_an.first_landed(B)[uid]
D = E if kind == "body" else C
ys = {r["t"]: r for r in B[(uid, i)]}
offs = [int(o, 16) for o in offs.split(",")]
for (u, j, t), raw in sorted(D.items(), key=lambda kv: kv[0][2]):
    if u != uid or j != i or not (t_from <= t - t0 <= t_to):
        continue
    r = ys.get(t, {})
    cells = []
    for o in offs:
        v = raw[o:o + 4]
        cells.append(f"+{o:03x}={v[::-1].hex()}/{struct.unpack('<f', v)[0]:.3g}")
    print(f"t{t - t0:+6d} y {r.get('y', 0):.2f} lay {r.get('lay')} fm {r.get('fm')} st {r.get('st')} | " + " ".join(cells))
