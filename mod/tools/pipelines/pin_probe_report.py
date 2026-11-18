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

[d10-1118, D11] With the traced caves and ``trace 1`` the record has T lines (what the take-off caves saw of each
entity in each tick, in order; format in the recorder's header). Then every EARLY take-off is explained: its
tokens from three ticks before its last hit to one tick after it left, and which of the two explanations of the
gap the data supports --
  (1) the take-off check is not asked when the countdown is 0: after the hit, the flight update ran with the
      countdown at 0 outside phase 1 and no check followed it, while every tick had its update;
  (2) the check is asked less often than once per tick: a tick after the hit with no update at all, or an
      update in which the gate should have asked (countdown above 0, or phase 1, FC +0x64 clear) and did not;
-- or "neither", with the reason (e.g. the check WAS asked after the hit and the rule answered free). A TRACE line
counts, over every traced entity, the ticks with 0 / 1 / more updates and how often the gate asked when its
static reading says it should (the gate at 0x143053ce3: takeoff_trace_asm.py). A battle recorded with
``trace=1`` but without a T line is a problem: the trace was asked for and is missing.

[D11, gapfix-1118] The stamp cave raises the countdown 0 -> 1 of a model in phase 1 or 2 when it records a melee
hit on it (``air_dive_rules.TAKEOFF_GAP_RAISE_PHASES``), in mode 1 only; the trace marks such a hit token with
``r``. A RAISE line counts the hit tokens (of entities in a flyer's living list) at countdown 0 in those phases and
how many were raised. In mode 1 every one of them must be raised, in any other mode none, and no other token may
carry ``r``; anything else is a problem line.

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
                   "last_hit": {}, "state": {}, "period": None, "entities": None,
                   "trace_on": "trace=1" in p[1:], "trace": {}, "t_lines": 0, "mode": None}
            for cell in p[1:]:
                if cell.startswith("mode="):
                    cur["mode"] = int(cell[5:])
                elif cell.startswith("sample="):
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
        elif p[0] == "T":
            cur["t_lines"] += 1
            tick = int(p[1])
            for cell in p[3:]:
                ent, toks = cell.split(":", 1)
                cur["trace"].setdefault(ent, {}).setdefault(tick, []).extend(toks.split(","))
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


def token(tok):
    """(letter, phase, count, flags) of a T-line token, e.g. "u2.0s" -> ("u", 2, 0, "s")."""
    letter, rest = tok[0], tok[1:]
    phase, _dot, tail = rest.partition(".")
    digits = "".join(ch for ch in tail if ch.isdigit() or ch == "-")
    return letter, int(phase), int(digits), tail[len(digits):]


def _asks_after(stream, i):
    """True when the token after the update at ``stream[i]`` (before the next update) is a check."""
    for _tick, tok in stream[i + 1:]:
        if tok[0] == "u":
            return False
        if tok[0] in "fhp":
            return True
    return False


def _gate_should_ask(letter, phase, count, flags):
    return letter == "u" and (count > 0 or phase == 1) and "g" not in flags


def explain(battle, takeoff):
    """[d10-1118] Which explanation of an early take-off the T lines support: (verdict, reason, sequence)."""
    ent, up = takeoff["entity"], takeoff["tick"]
    ticks = battle["trace"].get(ent)
    if not ticks:
        return "unexplained", "no T line for this entity (record with the traced caves and 'trace 1')", []
    hits = [t for t, toks in ticks.items() if t <= up and any(x[0] == "x" for x in toks)]
    hit = max(hits) if hits else takeoff["last_hit"]
    if hit is None:
        return "unexplained", "no hit before the take-off", []
    sequence = [f"{t}: {','.join(ticks[t])}" for t in range(hit - 3, up + 2) if t in ticks]
    stream = []
    for t in range(hit, up + 1):
        toks = ticks.get(t, [])
        if t == hit and any(x[0] == "x" for x in toks):
            last_x = max(i for i, x in enumerate(toks) if x[0] == "x")
            toks = toks[last_x + 1:]
        stream += [(t, x) for x in toks]
    asks = [(t, x) for t, x in stream if x[0] in "fhp"]
    for t, x in asks:
        letter, _ph, _c, flags = token(x)
        if letter == "h":
            return "neither", f"the check was asked after the hit and the rule held it (tick {t}: {x})", sequence
        if letter == "p":
            return "neither", f"the check was asked after the hit and passed to the game's own (tick {t}: {x})", sequence
        if flags:
            return "neither", (f"the check was asked after the hit but the rule could not judge the model "
                               f"(tick {t}: {x}; !u = no living entity carries its FC, !n = no model)"), sequence
        return "neither", (f"the check was asked after the hit and the rule answered free (tick {t}: {x}): "
                           "a fault in the rule itself (window or hit table)"), sequence
    gap = [(t, x) for i, (t, x) in enumerate(stream)
           if x[0] == "u" and token(x)[1] != 1 and token(x)[2] == 0 and not _asks_after(stream, i)]
    missing = [t for t in range(hit + 1, up + 1) if not any(x[0] == "u" for x in ticks.get(t, []))]
    skipped = [(t, x) for i, (t, x) in enumerate(stream)
               if _gate_should_ask(*token(x)) and not _asks_after(stream, i)]
    one = bool(gap) and not missing
    two = bool(missing or skipped)
    why1 = f"updates at countdown 0 outside phase 1, no check after them: {[f'{t} {x}' for t, x in gap]}"
    why2 = (f"ticks without an update: {missing}" if missing else "") + (
        ("; " if missing else "") + f"updates the gate should have asked on, not asked: "
        f"{[f'{t} {x}' for t, x in skipped]}" if skipped else "")
    if one and two:
        return "both", why1 + "; " + why2, sequence
    if one:
        return "(1) not asked when the countdown is 0", why1 + "; every tick had its update", sequence
    if two:
        return "(2) asked less often than once per tick", why2, sequence
    if not stream:
        return "neither", "no trace entry between the hit and the take-off", sequence
    return "neither", "every update after the hit was in phase 1 or had a countdown, and none was skipped", sequence


def trace_census(battle):
    """[d10-1118] Over every traced entity: ticks with 0 / 1 / 2+ updates between its first and last traced
    tick, and the gate's asks against its static reading."""
    per_tick = {0: 0, 1: 0, 2: 0}
    gate = {"should, asked": 0, "should, not asked": 0, "should not, asked": 0, "should not, not asked": 0}
    for ent, ticks in battle["trace"].items():
        if ent.startswith("?"):
            continue
        for t in range(min(ticks), max(ticks) + 1):
            n = sum(1 for x in ticks.get(t, []) if x[0] == "u")
            per_tick[min(n, 2)] += 1
        stream = [(t, x) for t in sorted(ticks) for x in ticks[t]]
        for i, (_t, x) in enumerate(stream):
            if x[0] != "u":
                continue
            key = ("should" if _gate_should_ask(*token(x)) else "should not") + (
                ", asked" if _asks_after(stream, i) else ", not asked")
            gate[key] += 1
    return per_tick, gate


def raise_census(battle):
    """[D11] ({"gap hits": n, "raised": n}, [problem]) over the hit tokens of the traced entities."""
    phases = set(air_dive_rules.TAKEOFF_GAP_RAISE_PHASES)
    counts, problems = {"gap hits": 0, "raised": 0}, []
    for ent, ticks in battle["trace"].items():
        if ent.startswith("?"):                       # not in a living list: the cave does not raise it
            continue
        for tick in sorted(ticks):
            for tok in ticks[tick]:
                if tok[0] != "x":
                    continue
                _letter, phase, count, flags = token(tok)
                raised = "r" in flags
                if count == 0 and phase in phases:
                    counts["gap hits"] += 1
                    counts["raised"] += raised
                    if battle["mode"] == 1 and not raised:
                        problems.append(f"entity {ent} tick {tick}: hit at countdown 0 in phase {phase} "
                                        f"not raised ({tok})")
                    elif battle["mode"] != 1 and raised:
                        problems.append(f"entity {ent} tick {tick}: hit raised in mode {battle['mode']} ({tok})")
                elif raised:
                    problems.append(f"entity {ent} tick {tick}: hit raised at countdown {count} phase {phase} "
                                    f"({tok})")
    return counts, problems


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
        gaps = []
        for t in hit:
            if window is not None and t["tick"] - t["last_hit"] < window - slack:
                verdict, reason, sequence = explain(battle, t)
                gaps.append({"entity": t["entity"], "tick": t["tick"], "last_hit": t["last_hit"],
                             "verdict": verdict, "reason": reason, "sequence": sequence})
        rows.append({"uid": uid, "key": battle["units"][uid]["key"], "size": size, "codes": codes,
                     "window": window, "expected": None if window is None else window + ENGINE_TIMER_TICKS,
                     "takeoffs": len(mine), "never_hit": len(mine) - len(hit), "delays": sorted(delays),
                     "early": len(early), "gaps": gaps})
    if battle["trace_on"] and battle["t_lines"] == 0:
        problems.append("the battle was recorded with trace=1 but has no T line (the traced caves wrote nothing)")
    if battle["trace"]:
        problems += raise_census(battle)[1]
    return rows, problems


def render(rows, problems, census=None, raises=None):
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
    for r in rows:
        for g in r.get("gaps", []):
            out.append(f"TAKE-OFF GAP flyer {r['uid']} entity {g['entity']}: hit at tick {g['last_hit']}, airborne "
                       f"at {g['tick']} (window {r['window']}) -- {g['verdict']}: {g['reason']}")
            out += ["    " + line for line in g["sequence"]]
    if census is not None:
        per_tick, gate = census
        out.append(f"TRACE updates per entity-tick: none {per_tick[0]}, one {per_tick[1]}, more {per_tick[2]}; "
                   "gate asked when it should " + f"{gate['should, asked']}/"
                   f"{gate['should, asked'] + gate['should, not asked']}, asked when it should not "
                   f"{gate['should not, asked']}/{gate['should not, asked'] + gate['should not, not asked']}")
    if raises is not None:
        out.append(f"RAISE hits at countdown 0 in phase "
                   f"{'/'.join(str(p) for p in air_dive_rules.TAKEOFF_GAP_RAISE_PHASES)}: {raises['gap hits']}, "
                   f"raised {raises['raised']}")
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
    battle = parse(text)
    rows, problems = judge(battle)
    census = trace_census(battle) if battle is not None and battle["trace"] else None
    raises = raise_census(battle)[0] if census is not None else None
    print(json.dumps({"rows": rows, "problems": problems, "trace": census, "raise": raises}, indent=1) if as_json
          else render(rows, problems, census, raises))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
