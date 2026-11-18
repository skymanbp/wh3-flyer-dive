"""Re-path calls (0x14307b4b0 entries) on a landed flyer still in flight movement and fast:
state 30/33, +0x104 0, +0x710 != 0, planar speed > 2 m/s. Per run, by caller."""
import sys, math, collections, struct
from pathlib import Path
runs = Path(__file__).resolve().parent / "runs"
for lab in sys.argv[1:]:
    f = runs / lab / "ld_repath_probe_slice.txt"
    c = collections.Counter(); tot = 0
    for l in f.read_text("utf-8", errors="replace").splitlines():
        p = l.split()
        if not p or p[0] != "R": continue
        tot += 1
        st, vx, vz, fm, lay = int(p[6]), float(p[7]), float(p[8]), int(p[9]), int(p[10])
        if st in (30, 33) and lay == 0 and fm != 0 and math.hypot(vx, vz) > 2:
            raw = bytes.fromhex(p[15]); q = struct.unpack("<%dQ" % (len(raw) // 8), raw)
            via = hex(q[32]) if p[5].endswith("307B700") and len(q) > 32 else ""
            c[p[5][-9:] + (" via " + via if via else "")] += 1
    print(f"{lab}: {tot} calls, in the dive window {sum(c.values())}: {dict(c)}")
