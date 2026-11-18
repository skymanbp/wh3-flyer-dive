"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 3): every early stop (< 15 m travel and < 15 m from touchdown at its
farthest, single-model lanes) of a batch prefix, with cause, travel, max distance, speed at touchdown,
touchdown-to-stop time and the slide-window counter in the cave log at that moment.
usage: python -I early_list.py <prefix>..."""
import json, os, re, sys
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import brace_an as b


def released_series(lab):
    out = []
    p = H / "runs" / lab / "ld_flyer_dive_slice.txt"
    if not p.exists():
        return out
    for line in p.read_text("utf-8", errors="replace").splitlines():
        m = re.search(r"(\d\d):(\d\d):(\d\d) NOW .*?slides ended (\d+)", line)
        if m:
            out.append((int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)), int(m.group(4))))
    return out


for pre in sys.argv[1:]:
    labs = sorted(d for d in os.listdir(H / "runs") if d.startswith(pre) and (H / "runs" / d / "verdict.json").exists())
    for lab in labs:
        rel = released_series(lab)
        for rec in b.lanes(lab):
            if rec["men"] != 1:
                continue
            i = rec["stop"]
            if i is None or rec["travel"] is None or rec["travel"] >= 15 or rec.get("maxd", 0) >= 15:
                continue
            s, td = rec["s"], rec["touchdown"]
            print(f"{lab} lane {rec['lane']} {rec['flyer']} vs {rec['target']}: travel {rec['travel']:.1f} m, "
                  f"maxd {rec.get('maxd', 0):.1f}, td t={s[td]['t']} stop t={s[i]['t']}, cause {b.cause(rec)}; "
                  f"slides ended over the battle {rel[-1][1] if rel else 'n/a'}")
