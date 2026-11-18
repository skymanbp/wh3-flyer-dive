"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 2): for every goal-collapse early stop, the G (stop-at-point
0x1431341b0) and K (vfunc 0x143098b04) events on that flyer entity around the collapse tick, with the
return address and the first stack qwords that look like code (0x14xxxxxxx) = the call chain.
usage: python -I collapse_who.py <prefix>..."""
import math, os, sys
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import brace_an as b


def code_frames(hexstack, n=8):
    out = []
    for i in range(0, len(hexstack) - 15, 16):
        q = int.from_bytes(bytes.fromhex(hexstack[i:i + 16]), "little")
        if 0x140001000 <= q < 0x1433ae000:
            out.append(f"{q:x}")
            if len(out) >= n:
                break
    return out


for pre in sys.argv[1:]:
    for lab in sorted(d for d in os.listdir(H / "runs") if d.startswith(pre) and (H / "runs" / d / "verdict.json").exists()):
        for rec in b.lanes(lab):
            s, td, i = rec["s"], rec["touchdown"], rec["stop"]
            if i is None or rec["travel"] is None or rec["travel"] >= 15 or rec["men"] != 1:
                continue
            gd = [math.hypot(r["gx"] - r["x"], r["gz"] - r["z"]) for r in s[td:i + 1]]
            k = next((j for j in range(1, len(gd)) if gd[j - 1] > 5 and gd[j] < 1.0), None)
            if k is None:
                print(f"{lab} lane {rec['lane']} early stop without goal collapse: {b.cause(rec)}")
                continue
            t1 = s[td + k]["t"]; t0 = s[td + k - 1]["t"]
            ent = s[td + k]["ent"]
            print(f"== {lab} lane {rec['lane']} {rec['target']} collapse between {t0:.1f} and {t1:.1f} s "
                  f"(goal {gd[k-1]:.1f} -> {gd[k]:.1f} m) ent {ent}")
            for t, kind, p in rec["EV"]:
                if t0 - 0.15 <= t <= t1 + 0.05 and len(p) > 5 and p[4] == ent:
                    print(f"   {kind} {t:.1f} ret {p[5][-9:]} st {p[6]} {' '.join(p[9:15])} chain {code_frames(p[-1])}")
