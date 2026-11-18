#!/usr/bin/env python3
"""How long after its last melee hit did each flying model leave the ground? [INGAME-1118 2026-11-18]

Reads the take-off recorder's file (``pin_probe.txt``, format in the header of ``pin_on_hit_probe.lua``; the
battle must have been recorded with ``entities 1`` in ``pin_probe.cfg``) and, for the last battle in it, lists every
take-off of every flight entity:

* a take-off = an E line in which the entity's airborne flag (+0x104) becomes 2;
* its last hit = the newest tick the hit table held for that entity at that moment (H lines);
* delay = take-off tick - last-hit tick, in battle ticks (100 ms).

The rule under test (D3, ``air_dive_rules.TAKEOFF_PIN_WINDOWS``): a model hit in melee stays down for the window of
its body size, and after the window the engine's own 3.0 s timer still has to run out. So a model that is ordered
away and no longer hit should leave ``window + 30`` ticks after its last hit, give or take the sampling period, and
never earlier than ``window`` ticks. A model that was ordered up later than that leaves later: the delay is a
lower bound on the rule, not an equality, which is why EARLY is the failure and the rest is printed.

Take-offs of entities that were never hit are counted, not judged. A record without E lines, with a FAIL line or
without the Z line of a flyer is not a measurement (exit 1).

usage: python -P tools/pipelines/pin_probe_report.py <pin_probe.txt> [--json]
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rolepath

import air_dive_rules

assert rolepath          # imported for its side effect: the role directories on sys.path

ENGINE_TIMER_TICKS = 30
SIZE_BY_CODE = {code: size for size, code in air_dive_rules.TAKEOFF_SIZE_CODES.items()}


def window_of(code):
    size = SIZE_BY_CODE.get(code)
    if size is None:
        return "unknown", air_dive_rules.TAKEOFF_PIN_WINDOW_UNKNOWN_SIZE
    return size, air_dive_rules.TAKEOFF_PIN_WINDOWS[size]


def parse(text):
    """The last battle of the record: header, units, sizes, hits per entity over time, take-offs."""
    battles, cur = [], None
    for raw in (text or "").splitlines():
        p = raw.split(" ")
        if p[0] == "BATTLE":
            cur = {"header": raw, "units": {}, "sizes": {}, "takeoffs": [], "fails": [], "e_lines": 0,
                   "last_hit": {}, "state": {}, "period": None, "entities": None}
            for cell in p[1:]:
                if cell.startswith("sample="):
                    cur["period"] = int(cell[7:])
                elif cell.startswith("entities="):
                    cur["entities"] = int(cell[9:])
            battles.append(cur)
        elif cur is None:
            continue
        elif p[0] == "UNIT":
            cur["units"][p[1]] = {"key": p[3], "flyer": p[-1] == "flyer=1"}
        elif p[0] == "FAIL":
            cur["fails"].append(raw)
        elif p[0] == "Z":
            for cell in p[3:]:
                ent, code = cell.split(":")
                cur["sizes"][ent] = (p[2], int(code))
        elif p[0] == "H":
            for cell in p[3:]:
                ent, tick, _hits = cell.split(":")
                cur["last_hit"][ent] = int(tick)
        elif p[0] == "E":
            cur["e_lines"] += 1
            tick, uid = int(p[2]), p[3]
            for cell in p[4:]:
                ent, fly, phase, _count = cell.split(":")
                was = cur["state"].get(ent)
                st = {"fly": int(fly), "asked": was["asked"] if was else None}
                if phase == "2" and (was is None or was["phase"] != "2"):
                    st["asked"] = tick
                st["phase"] = phase
                if st["fly"] == 2 and was is not None and was["fly"] != 2:
                    cur["takeoffs"].append({"uid": uid, "entity": ent, "tick": tick,
                                            "asked": st["asked"], "last_hit": cur["last_hit"].get(ent)})
                cur["state"][ent] = st
    return battles[-1] if battles else None


def judge(battle):
    """(per-unit rows, problems). A row: unit, size, window, the delays of its judged take-offs."""
    problems = []
    if battle is None:
        return [], ["no BATTLE line in the record"]
    problems += battle["fails"]
    if battle["entities"] != 1:
        problems.append("the battle was not recorded with 'entities 1' (no per-entity lines)")
    if battle["e_lines"] == 0:
        problems.append("no E line in the record")
    flyers = [uid for uid, u in battle["units"].items() if u["flyer"]]
    sized = {uid for uid, _code in battle["sizes"].values()}
    for uid in flyers:
        if uid not in sized:
            problems.append(f"flyer {uid} ({battle['units'][uid]['key']}) has no Z line: its body size was not read")
    rows = []
    for uid in flyers:
        codes = sorted({code for u, code in battle["sizes"].values() if u == uid})
        mine = [t for t in battle["takeoffs"] if t["uid"] == uid]
        hit = [t for t in mine if t["last_hit"] is not None]
        delays = [t["tick"] - t["last_hit"] for t in hit]
        size, window = window_of(codes[0]) if len(codes) == 1 else ("mixed", None)
        if len(codes) > 1:
            problems.append(f"flyer {uid}: its entities carry more than one size code {codes}")
        slack = max(1, -(-(battle["period"] or 200) // 100))      # one sampling period, in ticks
        early = [d for d in delays if window is not None and d < window - slack]
        if early:
            problems.append(f"flyer {uid} ({size}): {len(early)} take-off(s) earlier than its window "
                            f"{window} ticks after the last hit: {sorted(early)[:8]}")
        rows.append({"uid": uid, "key": battle["units"][uid]["key"], "size": size, "codes": codes,
                     "window": window, "expected": None if window is None else window + ENGINE_TIMER_TICKS,
                     "takeoffs": len(mine), "never_hit": len(mine) - len(hit), "delays": sorted(delays),
                     "early": len(early)})
    return rows, problems


def render(rows, problems):
    out = []
    for r in rows:
        d = r["delays"]
        if d:
            spread = (f"min {d[0]}, median {statistics.median(d):g}, max {d[-1]} ticks; "
                      f"within one second of window + 30: {sum(1 for x in d if abs(x - r['expected']) <= 10)}/{len(d)}"
                      if r["expected"] is not None else f"min {d[0]}, max {d[-1]} ticks")
        else:
            spread = "no take-off after a hit"
        out.append(f"{r['key']} (uid {r['uid']}, {r['size']}, window {r['window']}, expected about {r['expected']}): "
                   f"{r['takeoffs']} take-offs, {r['never_hit']} never hit, {len(d)} judged -- {spread}")
    out.append("PROBLEMS: " + ("none" if not problems else ""))
    out += ["  " + p for p in problems]
    return "\n".join(out)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        print(__doc__)
        return 2
    text = Path(paths[0]).read_text(encoding="utf-8", errors="replace")
    rows, problems = judge(parse(text))
    print(json.dumps({"rows": rows, "problems": problems}, indent=1) if as_json else render(rows, problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
