"""TEST-ONLY: dwords that change at the goal-collapse tick (vs previous tick) for batch-E collapse lanes;
prints the ones common to every collapse and absent from the tick before."""
import sys, struct
sys.path.insert(0, ".")
import brace_an as b
CASES = [("E2_terror", 3, 71700), ("E1_wyvern", 1, 27700), ("E1_wyvern", 3, 69400), ("E2_wyvern", 2, 47100)]
def diff(a, c):
    return {o: (struct.unpack_from("<I", a, o)[0], struct.unpack_from("<I", c, o)[0]) for o in range(0, min(len(a), len(c)) - 3, 4) if a[o:o+4] != c[o:o+4]}
sets, prev = [], []
for lab, ln, ms in CASES:
    r = next(x for x in b.lanes(lab) if x["lane"] == ln)
    D = r["D"]
    d1 = diff(D[ms - 100], D[ms]); d0 = diff(D[ms - 200], D[ms - 100])
    sets.append(d1); prev.append(d0)
    print(lab, ln, ms, "changed", len(d1), "prev tick changed", len(d0))
common = set.intersection(*(set(s) for s in sets))
print("common at collapse:", len(common))
for o in sorted(common):
    nprev = sum(o in p for p in prev)
    vals = " ".join(f"{s[o][0]:08x}->{s[o][1]:08x}" for s in sets)
    print(f"  +0x{o:x} prev-tick-changes {nprev}/4  {vals}")
