"""TEST-ONLY: does a run at battle speed N measure the same as at 1x? Per run of jobs_speed.txt:
verdict, SPEED line, per lane touchdown speed / travel after touchdown / stopped (verdict.json),
early stops (brace_an), and sample density in BATTLE time: probe T samples per flyer per model
second, entity-reader ticks per model second (entity_read_slice 'T <ms>' lines), plus wall-clock
run length from autotest.log. usage: speedcmp.py"""
import importlib.util
import json
import re
from pathlib import Path

H = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ba", H / "brace_an.py")
ba = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ba)

for d in sorted(p for p in (H / "runs").iterdir() if p.name.startswith("S") and (p / "verdict.json").exists()):
    v = json.loads((d / "verdict.json").read_text("utf-8"))
    probe = (d / "ld_brace_probe_slice.txt").read_text("utf-8", errors="replace").splitlines()
    speed = next((l for l in probe if l.startswith("SPEED")), "SPEED 1 (no file)")
    tms = [int(l.split()[1]) for l in probe if l.startswith("T ")]
    flyers = {l.split()[2] for l in probe if l.startswith("T ")}
    span = (max(tms) - min(tms)) / 1000 if tms else 0
    t_rate = len(tms) / max(len(flyers), 1) / span if span else 0
    er = [int(l.split()[1]) for l in open(d / "entity_read_slice.txt", encoding="utf-8", errors="replace")
          if l.startswith("T ") and len(l.split()) == 2]
    er_rate = (len(er) - 1) / ((er[-1] - er[0]) / 1000) if len(er) > 1 else 0
    wall = re.findall(r"^\[air_dive_autotest\]\s+([\d.]+)s", (d / "autotest.log").read_text("utf-8", errors="replace"), re.M)
    early = sum(1 for rec in ba.lanes(d.name) if rec["stop"] is not None and rec["travel"] < 15)
    lanes = " | ".join(f"v_td {l.get('touchdown_speed_mps')} travel {l.get('travel_after_touchdown_m')} "
                       f"stopped {l.get('stopped')}" for l in v["lanes"])
    print(f"{d.name:12s} {v['verdict']:4s} {speed:12s} wall {wall[-1] if wall else '?'}s  probe {t_rate:.1f}/model-s "
          f"(span {span:.0f}s)  entity_read {er_rate:.2f} ticks/model-s ({len(er)})  early stops {early}  "
          f"entity_read problems {len((v.get('entity_read') or {}).get('problems', ['missing']))}\n    {lanes}")
