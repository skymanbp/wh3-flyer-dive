#!/usr/bin/env python3
"""Air dive probe -- per-charge report from flyer_dive_probe.txt. [AIR-DIVE-W4 2026-11-09]

Reads what ``air_dive_probe.lua`` (shipped by ``build_air_dive_minimod.py
--probe`` / ``--probe-only``) records in a battle and answers, per charge,
the question W2 and W3 could not: after the contact moment, does the body
keep moving into the enemy formation or stop at its front?

Per unit, the samples are split into episodes (a gap of more than GAP_S
between samples = the unit left the 80 m gate). In each episode an ANCHOR is:
* flyer: a touchdown, ``is_currently_flying`` 1 -> 0 (if the engine call
  failed, "na": the first sample after a >= 2 m descent where the height
  stops falling);
* any unit: the first ``is_in_melee`` 0 -> 1 after a sample at >= RUN_MPS
  (a charge, not a shuffle into contact).
From each anchor it reports: speed at the anchor (max over the previous
0.3 s), the path travelled after it until the unit stops (speed < STOP_MPS
for STOP_S) or ANCHOR_WINDOW_S runs out, the time to stop, and the advance
into the target -- the enemy unit nearest at the anchor -- measured as the
change of the unit's depth along its approach direction relative to the
target's centroid (positive = went deeper into the formation; the target's
own movement is taken out when the log has its position).

usage: python -P air_dive_probe_report.py <flyer_dive_probe.txt>
                 [--battle N] [--json out.json]
       (default: the last battle in the file; N counts from 1, -1 = last)
/ 读探针日志，逐次冲锋报告：接触后身体是否继续冲进敌阵。
"""
import argparse
import json
import math
import sys
from pathlib import Path

GAP_S = 1.0
RUN_MPS = 3.0
STOP_MPS = 0.5
STOP_S = 0.3
ANCHOR_WINDOW_S = 5.0
PRE_S = 0.3
DESCENT_M = 2.0
# [AIR-DIVE-GRIFFON] window after a touchdown in which the plough's speed peak
# shows (its clip root reaches 20 m/s inside the first second). Single-model
# units only: a multi-model unit's position() alternates between models.
JUMP_WINDOW_S = 1.0


def _bool(v):
    return None if v == "na" else v == "1"


def parse(path):
    """List of battles: {header, units: uid -> info, samples: uid -> [row]}."""
    return parse_text(Path(path).read_text("utf-8", errors="replace"))


# An S line: S <ms> <unit> then these fields at these positions (18 tokens).
# Table-driven (TEST-REPAIR-1113): the dict literal it replaces was a
# Py_Dup_Census clone of an unrelated stats literal.
_S_FIELDS = (("x", 3, float), ("y", 4, float), ("z", 5, float),
             ("spd", 6, float), ("bearing", 7, float),
             ("flying", 8, _bool), ("moving", 9, _bool),
             ("fast", 10, _bool), ("melee", 11, _bool),
             ("alive", 12, int), ("near", 13, str),
             ("near_d", 14, float), ("near_x", 15, float), ("near_z", 16, float))


def parse_text(text):
    """parse() on the log's text (air_dive_autotest judges a byte slice)."""
    battles, cur = [], None
    for raw in text.splitlines():
        parts = raw.split()
        if not parts:
            continue
        tag = parts[0]
        if tag == "BATTLE":
            cur = {"header": raw, "units": {}, "samples": {}, "notes": []}
            battles.append(cur)
        elif cur is None:
            continue
        elif tag == "UNIT":
            kv = dict(p.split("=", 1) for p in parts[4:] if "=" in p)
            cur["units"][parts[1]] = {
                "alliance": int(parts[2]), "key": parts[3],
                "fly": _bool(kv.get("fly", "na")), "men": int(kv.get("men", 0)),
                "class": kv.get("class")}
        elif tag == "S" and len(parts) == 18:
            row = {"t": int(parts[1]) / 1000.0}
            row.update((name, conv(parts[i])) for name, i, conv in _S_FIELDS)
            cur["samples"].setdefault(parts[2], []).append(row)
        else:
            cur["notes"].append(raw)
    return battles


def episodes(rows):
    out, ep = [], []
    for r in rows:
        if ep and r["t"] - ep[-1]["t"] > GAP_S:
            out.append(ep)
            ep = []
        ep.append(r)
    if ep:
        out.append(ep)
    return out


def anchors(ep, is_flyer):
    """[(index, kind)] in time order."""
    found = []
    if is_flyer:
        have_flag = any(r["flying"] is not None for r in ep)
        if have_flag:
            for i in range(1, len(ep)):
                if ep[i - 1]["flying"] and ep[i]["flying"] is False:
                    found.append((i, "touchdown"))
        else:
            top = 0
            for i in range(1, len(ep)):
                if ep[i]["y"] > ep[top]["y"]:
                    top = i
                was_falling = ep[i]["y"] < ep[i - 1]["y"] - 0.05
                fell = ep[top]["y"] - ep[i]["y"] >= DESCENT_M
                nxt = ep[i + 1] if i + 1 < len(ep) else None
                if (fell and was_falling and nxt is not None
                        and nxt["y"] >= ep[i]["y"] - 0.05):
                    found.append((i, "touchdown(height)"))
                    top = i
    ran = False
    for i in range(1, len(ep)):
        if ep[i - 1]["spd"] >= RUN_MPS:
            ran = True
        if ran and ep[i - 1]["melee"] is False and ep[i]["melee"]:
            found.append((i, "melee"))
            ran = False
    return sorted(found)


def measure(ep, i, target_rows):
    a = ep[i]
    pre = [r for r in ep[:i + 1] if a["t"] - r["t"] <= PRE_S and r["spd"] >= 0]
    v_in = max((r["spd"] for r in pre), default=-1.0)
    # approach direction: displacement over the PRE_S before the anchor
    j = max(0, i - max(1, len(pre) - 1))
    dx, dz = a["x"] - ep[j]["x"], a["z"] - ep[j]["z"]
    norm = math.hypot(dx, dz)
    if norm < 1e-3:
        dx, dz = a["near_x"] - a["x"], a["near_z"] - a["z"]
        norm = math.hypot(dx, dz) or 1.0
    ux, uz = dx / norm, dz / norm
    target = a["near"]

    def tpos(t):
        rows = target_rows.get(target) or []
        best = None
        for r in rows:
            if best is None or abs(r["t"] - t) < abs(best["t"] - t):
                best = r
        if best is not None and abs(best["t"] - t) <= 0.6:
            return best["x"], best["z"], True
        return a["near_x"], a["near_z"], False

    def target_y(t):
        rows = target_rows.get(target) or []
        best = min(rows, key=lambda r: abs(r["t"] - t), default=None)
        return best["y"] if best is not None and abs(best["t"] - t) <= 0.6 else None

    def depth(r):
        tx, tz, live = tpos(r["t"])
        return (r["x"] - tx) * ux + (r["z"] - tz) * uz, live

    d0, live0 = depth(a)
    path, stop_t, still_since, last = 0.0, None, None, a
    after = [r for r in ep[i + 1:] if r["t"] - a["t"] <= ANCHOR_WINDOW_S]
    for r in after:
        path += math.hypot(r["x"] - last["x"], r["z"] - last["z"])
        last = r
        if r["spd"] < STOP_MPS:
            still_since = still_since if still_since is not None else r["t"]
            if r["t"] - still_since >= STOP_S - 1e-6:
                stop_t = still_since
                break
        else:
            still_since = None
    end = last
    d1, live1 = depth(end)
    ty = target_y(a["t"])
    # [AIR-DIVE-GRIFFON] the jump attack shows as a speed peak right after
    # the anchor (the plough clip runs at ~20 m/s); a stop shows as ~0.
    peak = max((r["spd"] for r in after if 0.05 < r["t"] - a["t"] <= JUMP_WINDOW_S),
               default=-1.0)
    path_to_stop = path
    if stop_t is not None:
        path_to_stop, prev = 0.0, a
        for r in after:
            if r["t"] > stop_t:
                break
            path_to_stop += math.hypot(r["x"] - prev["x"], r["z"] - prev["z"])
            prev = r
    return {
        "t": round(a["t"], 2), "pos": [round(a["x"], 1), round(a["z"], 1)],
        "y": round(a["y"], 2), "speed_in": round(v_in, 2),
        "target": target, "dist_to_target_centroid": round(a["near_d"], 2),
        "travel_after_m": round(path_to_stop, 2),
        "time_to_stop_s": None if stop_t is None else round(stop_t - a["t"], 2),
        "stopped": stop_t is not None,
        "depth_at_anchor": round(d0, 2), "depth_at_end": round(d1, 2),
        "advance_into_target_m": round(d1 - d0, 2),
        "target_tracked": live0 and live1,
        "in_melee_at_end": end["melee"],
        "target_ground_rise_m": None if ty is None else round(ty - a["y"], 2),
        "peak_mps_after": round(peak, 2),
    }


def report(battle):
    units, samples = battle["units"], battle["samples"]
    out = []
    for uid, rows in samples.items():
        info = units.get(uid, {"key": "?", "fly": None, "alliance": 0, "men": 0})
        is_flyer = bool(info.get("fly"))
        for ep in episodes(rows):
            for i, kind in anchors(ep, is_flyer):
                rec = measure(ep, i, samples)
                rec.update({"uid": uid, "key": info["key"], "flyer": is_flyer,
                            "alliance": info["alliance"], "anchor": kind,
                            "target_key": units.get(rec["target"], {}).get("key")})
                out.append(rec)
    out.sort(key=lambda r: (not r["flyer"], r["key"], r["t"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("log")
    ap.add_argument("--battle", type=int, default=-1)
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    battles = parse(args.log)
    if not battles:
        raise SystemExit(f"[air_dive_probe_report] no BATTLE line in {args.log}: "
                         "the recorder did not run (check lua_mod_log.txt)")
    idx = args.battle - 1 if args.battle > 0 else args.battle
    battle = battles[idx]
    rows = report(battle)
    print(battle["header"])
    for n in battle["notes"]:
        print("  note:", n)
    print(f"  {len(battle['units'])} units seen, "
          f"{sum(len(v) for v in battle['samples'].values())} samples")
    if not rows:
        print("  NO charges found: no touchdown and no run-into-melee in range")
    hdr = ("kind", "key", "anchor", "t", "v_in", "travel", "t_stop",
           "depth0", "depth1", "advance", "melee_end", "target")
    print("  " + " | ".join(hdr))
    for r in rows:
        print("  " + " | ".join(str(x) for x in (
            "FLY" if r["flyer"] else "GND", r["key"], r["anchor"], r["t"],
            r["speed_in"], r["travel_after_m"], r["time_to_stop_s"],
            r["depth_at_anchor"], r["depth_at_end"],
            r["advance_into_target_m"], r["in_melee_at_end"],
            r["target_key"])))
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"header": battle["header"], "charges": rows}, indent=1) + "\n",
            encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
