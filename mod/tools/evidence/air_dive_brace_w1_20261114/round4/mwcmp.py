"""TEST-ONLY (2026-11-15, minimised-window probe): one battle run normal vs minimised (--window=background),
same pack and lanes. Per lane: touchdown time and speed, depth, travel, early stop; per run: wall duration,
probe sample rate (battle-time samples per second of the flyer), entity-reader ticks, battle length, and the
per-model rise count (osc.py) for multi-model lanes.
usage: python -I mwcmp.py <normal label> <minimised label>"""
import json, os, re, sys
from datetime import datetime
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import brace_an as b
import osc


def wall(lab):
    t = [re.match(r"\[air_dive_autotest\]\s+([\d.]+)s", ln) for ln in
         (H / "runs" / lab / "autotest.log").read_text("utf-8", errors="replace").splitlines()]
    t = [float(m.group(1)) for m in t if m]
    return max(t) if t else None


def run(lab):
    v = json.loads((H / "runs" / lab / "verdict.json").read_text("utf-8"))
    out = {"verdict": v["verdict"], "wall_s": wall(lab), "ticks": v.get("entity_read", {}).get("ticks")}
    rate, lanes = [], {}
    for rec in b.lanes(lab):
        s = rec["s"]
        if len(s) > 10:
            rate.append(round((len(s) - 1) / (s[-1]["t"] - s[0]["t"]), 2))
        ln = next(l for l in v["lanes"] if l["lane"] == rec["lane"])
        early = rec["stop"] is not None and rec["travel"] is not None and rec["travel"] < 15 and rec.get("maxd", 0) < 15
        lanes[rec["lane"]] = dict(t=ln.get("t"), v=ln.get("touchdown_speed_mps"), depth=ln.get("depth_into_target_m"),
                                  travel=ln.get("travel_after_touchdown_m"), early=early, men=rec["men"])
    out["probe_hz"] = sorted(set(rate))
    rises = {}
    for l, per in osc.lanes(lab):
        rises[l["lane"]] = sum(1 for c in per.values() if c[1])
    out["lanes"], out["rises"] = lanes, rises
    return out


a, c = run(sys.argv[1]), run(sys.argv[2])
print(f"verdict {a['verdict']} / {c['verdict']}; wall {a['wall_s']} / {c['wall_s']} s; entity ticks {a['ticks']} / {c['ticks']}; "
      f"probe sample rate (per flyer) {a['probe_hz']} / {c['probe_hz']}")
print("lane | touchdown t | touchdown speed | depth | travel | early | rising models")
for k in sorted(a["lanes"]):
    x, y = a["lanes"][k], c["lanes"].get(k, {})
    print(f"{k:4d} | {x['t']} / {y.get('t')} | {x['v']} / {y.get('v')} | {x['depth']} / {y.get('depth')} | "
          f"{x['travel']} / {y.get('travel')} | {x['early']} / {y.get('early')} | {a['rises'].get(k, '-')} / {c['rises'].get(k, '-')}")
