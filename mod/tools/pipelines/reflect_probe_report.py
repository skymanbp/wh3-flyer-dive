#!/usr/bin/env python3
"""TEST-ONLY: summary of reflect_probe.txt (pipelines/reflect_probe.lua). [update-1117 part C, D4]

Per unit of the battle (key, side, flyer or not):
  * impact reflections it took as the CHARGER (rf_refl): count, closing speed min / median / max;
  * damage it took (rf_dmg), by damage type and call site, and in particular the reflection's
    own damage call (call site returning to REFLECT_DAMAGE_RETURN, damage type 0): hits and the
    damage of each -- the game's reflection hit (D4's doubling factor is gone: D15 replaced it);
  * hit points: unary hp at its first melee sample, and its loss 1.5 s and 5 s later.
Verdict lines: CONTROL (some non-flyer took reflection damage: the logger can see a reflection),
FLYER (some flyer took reflection damage), and the counts behind both. A file with no BATTLE
... on line or no R / D line at all is INCOMPLETE, never a pass.
[d3-1118] Two lines more say how far the engine got when no reflection was seen:
ACTION UPDATES (rf_act1 / rf_act2: soldiers running an action that can call the reflection check,
by unit, with the soldier's +0x318 and the action's +0x38) and BRACE CHECK (rf_brace: calls of the
reflection check 0x14325bbec, by reflector unit, with the reflector's +0x318 -- the engine needs
0x69 there ("Back" otherwise) -- and, for the first enemy in its list, its +0x324 state (12 / 15 /
16 / 17 is "Interr") and its distance against the radius). A probe file older than these caves
has none of these lines; the report says "not logged" then, never "not reached".

[d10-1118, D4] Each damage call is printed with the CLASS of its call site (reflect_probe_asm.APPLIER_CALLS:
hit processor, splash, matched combat, charge collision, impact, ranged, the impact reflection, or unidentified).
And the charge-reflect multiplier of 9.0 (the damage calculator 0x142e5fcb0, rf_cgate / rf_cmul):
CHARGE REFLECT GATE n / MULTIPLIER n by caller, and for each multiplier the first damage call after it on the
same thread (by the shared clock): its class, victim unit and damage -- the hit the multiplier fed, if the
pairing holds. CANDIDATES says which logged interface field equals that victim (the field that names the
entity, read by one run). A file without C lines says "not logged", never "not applied".

[d15-1118, D15] DIVE COST: the log-only dive mark (dive_mark_asm.py) judged by rf_dmg on every impact (type 5)
and collision-attack (type 6) call. Per flyer unit: its mark events (armed / stamped / spent / expired), each
would-be cost (model, ticks since touchdown, the soldier's +0x318 and whether it is the braced 0x69, the model's
maximum and current health, the cost at DIVE_COST_SHARE of its body size), how many models would pay within
DIVE_COST_WINDOW_TICKS and what that is as a share of the unit's health. ATTACKER IDENTITY: on type-5 / 6 calls,
how often the applier's attacker is itself the flying entity, a rider of one, or no flyer at all. A file with no
MARK on line, lost D or M records, no M line or no type-5 / 6 call with a flying attacker is a FAIL (exit 1).

[d15-1118, maintainer] COST: the costs taken through unit:reduce_hitpoints_unary (stage 3-4: the recorder's
test-only step behind cost=1; since stage 5 the SHIPPED lib/dive_cost.lua, observed: its XPAY / XARC / XNOATTR
lines per entry of the cave dv_cost, cross-checked with the game data's charge_reflection units). Per flyer unit: calls, p requested, the measured health drop (the
reading before each call minus the lowest of the DIVE_COST_FOLLOW_TICKS readings after it), the ordinary damage
the D lines put on that unit in the same windows (as a share of the unit: initial men x the model's maximum
health), the drop attributable to the calls, models lost; with the switch off, the would-have calls. FAIL: no
COST line; an XERR line; a call after which no reading fell (the queued command was not executed -- the submit
is skipped when [[g]+0x468]+0x3b0 / +0x3b1 is set, 0x142f0f633); verdicts for a unit with no cost line at all.

[test standard, stage 6 2026-11-18] FLYER DAMAGE / CONTACT (flyer_damage_summary): per flyer unit the damage it
took, split by the calculator record before each hit, its first 5 s / 10 s, and the calls on the units it hit
around its first contact -- what the supervisor's scratch readers verify_d15 / read_d15_run / verify_contact
computed, now in this one report.

usage: python -P tools/pipelines/reflect_probe_report.py [reflect_probe.txt]
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path

import os
import statistics
import struct
import sys
from pathlib import Path

import air_dive_rules
import reflect_probe_asm

GAME_ROOT = Path(os.environ.get(
    "WH3_ROOT", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III"))
REFLECT_RET = f"{reflect_probe_asm.REFLECT_DAMAGE_RETURN:016X}"
TYPES = {0: "melee", 1: "ranged", 2: "ability", 3: "ability", 4: "explosion", 5: "impact", 6: "collision attack"}


def f32(hexbe):
    return struct.unpack(">f", bytes.fromhex(hexbe))[0]


def parse(text):
    """The last battle in the file: (on line, units {obj8: dict}, R rows, D rows, U rows, other)."""
    on, units, refl, dmg, hp, other = None, {}, [], [], [], []
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] in ("B", "A", "BS", "AS", "C", "CS"):
            other.append(line)          # read by brace_summary()
            continue
        if p[0] == "BATTLE":
            on, units, refl, dmg, hp, other = line, {}, [], [], [], []
        elif p[0] == "UNIT" and len(p) == 7:
            units[p[4].split("=")[1].upper()] = {"uid": p[1], "alliance": int(p[2]), "key": p[3],
                                         "men": int(p[5].split("=")[1]), "flyer": p[6] == "flyer=1"}
        elif p[0] == "R" and len(p) == 12:
            refl.append({"ms": int(p[1]), "tick": int(p[2]), "charger_unit": p[8].upper(), "reflector_unit": p[7].upper(),
                         "ret": p[5], "speed": f32(p[6]), "charger_flyer": p[9] == "1",
                         "brace": f32(p[10]), "immovable": int(p[11])})
        elif p[0] == "D" and len(p) in (10, 12, 24, 26):
            dmg.append({"ms": int(p[1]), "tick": int(p[2]), "ret": p[3].upper(), "unit": p[5].upper(), "damage": int(p[6]),
                        "type": int(p[7]), "flyer": p[8] == "1", "victim": p[4].upper(),
                        "thread": int(p[10]) if len(p) >= 12 else None, "clock": int(p[11]) if len(p) >= 12 else None})
            if len(p) == 24:                   # [d15-1118] the D15 fields, hex
                dmg[-1].update({"v318": int(p[12], 16), "verdict": int(p[13], 16), "attacker": p[14].upper(),
                                "att_fly": p[15].upper(), "v_max": int(p[16], 16), "v_hp": int(p[17], 16),
                                "a_max": int(p[18], 16), "a_hp": int(p[19], 16), "mark": int(p[20], 16),
                                "age": int(p[21], 16), "att_unit": p[22].upper(), "a_size": int(p[23], 16)})
            elif len(p) == 26:                 # [d15-1118 round 3] + the soldier's +0x68 and the unit's +0x3c18
                dmg[-1].update({"v68": int(p[12], 16), "verdict": int(p[13], 16), "u_brace": f32(p[14]),
                                "v318": int(p[15], 16), "attacker": p[16].upper(), "att_fly": p[17].upper(),
                                "v_max": int(p[18], 16), "v_hp": int(p[19], 16), "a_max": int(p[20], 16),
                                "a_hp": int(p[21], 16), "mark": int(p[22], 16), "age": int(p[23], 16),
                                "att_unit": p[24].upper(), "a_size": int(p[25], 16)})
        elif p[0] == "U":
            row = {"ms": int(p[1])}
            for cell in p[2:]:
                uid, h, men, melee = cell.split(":")
                row[uid] = (float(h), int(men), melee == "1")
            hp.append(row)
        else:
            other.append(line)
    return on, units, refl, dmg, hp, other


def hp_curve(hp, uid, after_s=(1.5, 5.0)):
    """(first melee ms, hp then, [loss after each of after_s]) or None."""
    first = next((r for r in hp if uid in r and r[uid][2]), None)
    if first is None:
        return None
    h0 = first[uid][0]
    losses = []
    for s in after_s:
        later = [r for r in hp if uid in r and r["ms"] >= first["ms"] + s * 1000]
        losses.append(round(h0 - later[0][uid][0], 5) if later else None)
    return first["ms"], h0, losses


INTERRUPTED = {12, 15, 16, 17}           # 0x14325bc8c..: charger +0x324 states that skip ("Interr")
BRACED_STATE = 0x69                      # 0x14325bdd6: reflector +0x318 the check needs ("Back" otherwise)


def brace_summary(other, units):
    """[d3-1118] Lines about the reflection check and the actions that call it, from the B / A / BS /
    AS lines of the last battle (``other``). [] when the file has none of them at all."""
    bs = [ln.split() for ln in other if ln.startswith("BS ")]
    as_ = [ln.split() for ln in other if ln.startswith("AS ")]
    b = [ln.split() for ln in other if ln.startswith("B ")]
    s_lines = [ln for ln in other if ln.startswith("S ")]
    if not (bs or as_ or b) and not any("brace=" in ln for ln in s_lines):
        return ["BRACE CHECK not logged (probe file older than rf_brace)"]
    name = lambda u8: units.get(u8.upper(), {}).get("key", u8)
    out = []
    acts = {}
    for p in as_:
        k = (p[2], name(p[3]), int(p[4], 16), int(p[5], 16))
        acts[k] = acts.get(k, 0) + int(p[6].split("=")[1])
    total_a = sum(acts.values())
    out.append(f"ACTION UPDATES {total_a}" + ("" if total_a else " (no soldier ran an action that can "
                                                                "call the reflection check)"))
    for (which, key, st, aid), n in sorted(acts.items(), key=lambda kv: -kv[1])[:12]:
        out.append(f"  update {which} {key}: soldier +0x318 {st:#x}, action +0x38 {aid:#x}: {n}")
    calls = {}
    for p in bs:
        k = (name(p[2]), int(p[3], 16), int(p[5]), int(p[6], 16) if int(p[5]) else None)
        calls[k] = calls.get(k, 0) + int(p[7].split("=")[1])
    total_b = sum(calls.values())
    braced = sum(n for (_k, st, _e, _s), n in calls.items() if st == BRACED_STATE)
    out.append(f"BRACE CHECK {'REACHED' if total_b else 'NOT REACHED'} {total_b} calls, reflector in "
               f"state {BRACED_STATE:#x} {braced}, with an enemy in reach list "
               f"{sum(n for (_k, _st, e, _s), n in calls.items() if e)}")
    for (key, st, enemies, est), n in sorted(calls.items(), key=lambda kv: -kv[1])[:12]:
        tag = "" if st == BRACED_STATE else ' (not 0x69: "Back")'
        etag = "" if est is None else f", first enemy +0x324 {est}" + (' ("Interr")' if est in INTERRUPTED else "")
        out.append(f"  {key}: reflector +0x318 {st:#x}{tag}, enemies {enemies}{etag}: {n}")
    near = []
    for p in b:
        if len(p) < 15 or p[11] in ("00000000",):
            continue
        rx, rz, radius, ex, ez = (f32(p[i]) for i in (8, 9, 10, 14, 15))
        near.append(((rx - ex) ** 2 + (rz - ez) ** 2, radius, int(p[5], 16), int(p[13], 16)))
    if near:
        d2 = sorted(x[0] for x in near)
        out.append(f"  first enemy distance in the logged calls: min {d2[0] ** 0.5:.1f} m, median "
                   f"{d2[len(d2) // 2] ** 0.5:.1f} m; radius value median "
                   f"{sorted(x[1] for x in near)[len(near) // 2]:.2f} ({len(near)} calls with an enemy)")
    return out


def call_class(ret_hex):
    """[d10-1118] The class of an applier call site from its return address (hex, 16 digits)."""
    return reflect_probe_asm.APPLIER_CALLS.get(int(ret_hex, 16), "unknown call site")


def charge_reflect_summary(other, dmg, units):
    """[d10-1118] The C / CS lines of the last battle: the damage calculator's charge-reflect test and
    multiplier, and the damage call each multiplier fed (same thread, next clock)."""
    c = [ln.split() for ln in other if ln.startswith("C ")]
    cs = [ln.split() for ln in other if ln.startswith("CS ")]
    if not c and not cs and not any(" cr=" in ln for ln in other if ln.startswith("S ")):
        return ["CHARGE REFLECT not logged (probe file older than rf_cgate / rf_cmul)"]
    name = lambda u8: units.get(u8.upper(), {}).get("key", u8)
    calls = {}
    for q in cs:
        k = (int(q[2]), int(q[3], 16), int(q[4], 16))
        calls[k] = calls.get(k, 0) + int(q[5].split("=")[1])
    gate = sum(n for (w, _r1, _r2), n in calls.items() if w == 1)
    mult = sum(n for (w, _r1, _r2), n in calls.items() if w == 2)
    out = [f"CHARGE REFLECT GATE {gate} calls (both of the calculator's tests passed), MULTIPLIER "
           f"{'APPLIED' if mult else 'NOT APPLIED'} {mult} calls"]
    for (w, r1, r2), n in sorted(calls.items(), key=lambda kv: -kv[1]):
        via = reflect_probe_asm.CALC_CALLERS.get(r1, f"{r1:#x}")
        up = f" <- {reflect_probe_asm.CALC_CALLERS_2.get(r2, f'{r2:#x}')}" if r2 else ""
        out.append(f"  {'gate' if w == 1 else 'multiplier'} via {via}{up}: {n}")
    by_thread = {}
    for d in dmg:
        if d["thread"] is not None:
            by_thread.setdefault(d["thread"], []).append(d)
    fed, cand_hits = {}, {i: 0 for i in range(4)}
    mults = [q for q in c if q[2] == "2"]
    for q in mults:
        thread, clock = int(q[11]), int(q[12])
        nxt = min((d for d in by_thread.get(thread, []) if d["clock"] > clock), key=lambda d: d["clock"], default=None)
        if nxt is None:
            fed[("no damage call after it on its thread", "", "")] = fed.get(("no damage call after it on its thread", "", ""), 0) + 1
            continue
        k = (call_class(nxt["ret"]), name(nxt["unit"]), TYPES.get(nxt["type"], str(nxt["type"])))
        fed[k] = fed.get(k, 0) + 1
        for i in range(4):
            if q[13 + i].upper() == nxt["victim"]:
                cand_hits[i] += 1
    for (cls, unit, typ), n in sorted(fed.items(), key=lambda kv: -kv[1])[:12]:
        out.append(f"  multiplier fed: {cls} on {unit} ({typ}): {n}")
    if mults:
        names = ("[target+8]", "[target+0x10]", "[source+8]", "[source+0x10]")
        out.append("CANDIDATES equal to the fed call's victim: " + ", ".join(
            f"{names[i]} {cand_hits[i]}/{len(mults)}" for i in range(4)))
        f = [(f32(q[7]), f32(q[8]), f32(q[9])) for q in mults]
        out.append(f"  multiplier values: charge factor median {statistics.median(x[0] for x in f):.2f} "
                   f"(threshold {f[0][1]:.2f}), multiplier {sorted({round(x[2], 3) for x in f})}")
    return out


CONTACT_BEFORE_MS, CONTACT_AFTER_MS = 2000, 3000      # verify_contact.py's window around the contact


def _frac_at(hp, uid, ms):
    """the unit's health fraction at the last U row at or before ms (None without one)"""
    best = None
    for r in hp:
        if r["ms"] <= ms and uid in r:
            best = r[uid][0]
    return best


def flyer_damage_summary(units, dmg, hp, other):
    """[test standard, stage 6 2026-11-18] What the supervisor's one-off readers (d15-1118_scratch/supervisor:
    verify_d15.py, read_d15_run.py, verify_contact.py) computed from the raw records, per flyer unit:
      FLYER DAMAGE: hits, total, first damage (ms, ticks after its first type-5 / 6 call as attacker), health
        left at the last U row, pool estimate total / (1 - left);
        each hit classed by the calculator record before it on the same victim entity (by clock): MULT (the
        charge-reflect multiplier, C which=2), GATE (C which=1), with the tail of the calculator's second
        return address, or none -- 'not logged' without C lines;
        the first 5 s and 10 s from its first damage: damage, health before -> after, split by that class;
      CONTACT: its first type-5 / 6 call as attacker, and the damage calls on the units it hit from
        CONTACT_BEFORE_MS before to CONTACT_AFTER_MS after, by type. (verify_contact.py took the contact
        from the driver's timeline; the record's own first call needs no second file.)"""
    c = [ln.split() for ln in other if ln.startswith("C ") and len(ln.split()) >= 14]
    last_c, cls = {}, {}
    events = sorted([(int(q[12]), 0, i) for i, q in enumerate(c)] +
                    [(d["clock"], 1, i) for i, d in enumerate(dmg) if d["clock"] is not None])
    for _clock, kind, i in events:
        if kind == 0:
            last_c[c[i][13].upper()] = c[i]
        else:
            q = last_c.get(dmg[i]["victim"])
            cls[i] = "none" if q is None else ("MULT " if q[2] == "2" else "GATE ") + q[6][-5:].upper()
    out = []
    for obj, u in sorted(units.items(), key=lambda kv: int(kv[1]["uid"])):
        if not u["flyer"]:
            continue
        mine = [(i, d) for i, d in enumerate(dmg) if d["unit"] == obj]
        as_att = [d for d in dmg if d.get("att_unit") == obj and d["type"] in (5, 6)]
        if not mine:
            out.append(f"FLYER DAMAGE {u['key']} uid {u['uid']}: no damage records")
        else:
            total = sum(d["damage"] for _i, d in mine)
            t0 = min(d["ms"] for _i, d in mine)
            tick0 = min(d["tick"] for _i, d in mine)
            left = hp[-1][u["uid"]][0] if hp and u["uid"] in hp[-1] else None
            pool = f"{total / (1 - left):.0f}" if left is not None and left < 1 else "-"
            since = (f", {tick0 - min(d['tick'] for d in as_att)} ticks after its first type-5/6 call as attacker"
                     if as_att else "")
            out.append(f"FLYER DAMAGE {u['key']} uid {u['uid']} ({u['men']} models): hits {len(mine)}, damage "
                       f"{total}, first at {t0} ms{since}; health left {left}, pool estimate {pool}")
            if c:
                by = {}
                for i, d in mine:
                    by.setdefault(cls.get(i, "none"), []).append(d["damage"])
                for k in sorted(by):
                    v = by[k]
                    out.append(f"  by calculator record before it {k}: n={len(v)} mean {sum(v) / len(v):.1f} "
                               f"min {min(v)} max {max(v)} sum {sum(v)}")
            else:
                out.append("  by calculator record before it: not logged (no C lines)")
            for win in (5000, 10000):
                w = [(i, d) for i, d in mine if t0 <= d["ms"] < t0 + win]
                split = {}
                for i, d in w:
                    split[cls.get(i, "none") if c else "not logged"] = \
                        split.get(cls.get(i, "none") if c else "not logged", 0) + d["damage"]
                out.append(f"  first {win // 1000} s from first damage: damage {sum(d['damage'] for _i, d in w)}, "
                           f"health {_frac_at(hp, u['uid'], t0 - 100)} -> {_frac_at(hp, u['uid'], t0 + win)}, "
                           f"by class {dict(sorted(split.items()))}")
        if as_att:
            first = min(as_att, key=lambda d: d["ms"])
            hit_units = {d["unit"] for d in as_att}
            near = [d for d in dmg if d["unit"] in hit_units
                    and first["ms"] - CONTACT_BEFORE_MS <= d["ms"] <= first["ms"] + CONTACT_AFTER_MS]
            byt = {}
            for d in near:
                byt[d["type"]] = byt.get(d["type"], 0) + 1
            out.append(f"CONTACT {u['key']} uid {u['uid']}: first type-5/6 call as attacker at {first['ms']} ms "
                       f"(tick {first['tick']}) on {', '.join(sorted(units.get(x, {}).get('key', x) for x in hit_units))}; "
                       f"damage calls on them in [-{CONTACT_BEFORE_MS // 1000} s, +{CONTACT_AFTER_MS // 1000} s] "
                       f"by type {dict(sorted(byt.items()))}, sum {sum(d['damage'] for d in near)}")
    return out


def timeline_contact_summary(units, dmg, other, timeline_text):
    """[test standard, stage 6 2026-11-18] verify_contact.py's table, from the driver's timeline.txt next to the
    record: per lane, when the driver first tracked the flyer on the ground, the first charge-reflect gate and
    multiply records on it (C lines, by the entity its D lines name), the first damage on it, and the damage calls
    on its lane's target from CONTACT_BEFORE_MS before to CONTACT_AFTER_MS after that landing, by type.
    [] without a timeline; a lane line names what is missing."""
    import re
    if not timeline_text:
        return []
    lanes, landed = {}, {}
    for ln in timeline_text.splitlines():
        m = re.search(r"driver: \d+ lane (\d+) flyer=\S+ uid=(\d+) .* target=\S+ uid=(\d+)", ln)
        if m:
            lanes[int(m.group(1))] = (m.group(2), m.group(3))
        m = re.search(r"driver: (\d+) track (\d+) .* flying=false", ln)
        if m and int(m.group(2)) not in landed:
            landed[int(m.group(2))] = int(m.group(1))
    by_uid = {u["uid"]: obj for obj, u in units.items()}
    ent_unit = {d["victim"]: d["unit"] for d in dmg}
    c = [ln.split() for ln in other if ln.startswith("C ") and len(ln.split()) >= 14]
    out = []
    for n in sorted(lanes):
        fu, tu = (by_uid.get(x) for x in lanes[n])
        if fu is None or tu is None or n not in landed:
            out.append(f"LANE CONTACT {n}: no UNIT line or no landing in the timeline ({lanes[n]}, landed {landed.get(n)})")
            continue
        gates = [q for q in c if ent_unit.get(q[13].upper()) == fu and q[2] == "1"]
        mults = [q for q in c if ent_unit.get(q[13].upper()) == fu and q[2] == "2"]
        mine = [d for d in dmg if d["unit"] == fu]
        t = landed[n]
        near = [d for d in dmg if d["unit"] == tu and t - CONTACT_BEFORE_MS <= d["ms"] <= t + CONTACT_AFTER_MS]
        byt = {}
        for d in near:
            byt[d["type"]] = byt.get(d["type"], 0) + 1
        out.append(f"LANE CONTACT {n} {units[fu]['key']}: on the ground by {t} ms; first gate "
                   f"{min(int(q[1]) for q in gates) if gates else None} ({gates[0][6][-5:].upper() if gates else '-'}), "
                   f"first multiply {min(int(q[1]) for q in mults) if mults else None}, "
                   f"first damage on it {min(d['ms'] for d in mine) if mine else None}; damage calls on its target in "
                   f"[-{CONTACT_BEFORE_MS // 1000} s, +{CONTACT_AFTER_MS // 1000} s] by type {dict(sorted(byt.items()))}, "
                   f"sum {sum(d['damage'] for d in near)}")
    return out


NONE32 = 0xFFFFFFFF
MARK_KINDS = {1: "armed", 2: "stamped", 3: "spent", 4: "expired"}
VERDICTS = {0: "-", 1: "WOULD-BE COST", 2: "mark expired", 3: "not braced", 4: "armed only", 5: "already spent"}
SIZE_BY_CODE = {code: size for size, code in air_dive_rules.TAKEOFF_SIZE_CODES.items()}


def _s32(v):
    return v - 2**32 if v >= 2**31 else v


VERDICT_REASONS = {0: "no verdict", 1: "would-be cost", 2: "mark expired", 3: "soldier not braced",
                   4: "armed only", 5: "already spent"}


def _braced(d):
    """the soldier's braced flag (+0x68 bit 3) on a round-3 record; None on an older one."""
    if "v68" not in d:
        return None
    return bool(d["v68"] & reflect_probe_asm.BRACED_BIT) and d["v68"] <= 0xFF


def _float_hist(values, edges=(0.0, 0.25, 0.5, 0.75, 1.0)):
    out = {}
    for v in values:
        k = next((f"<={e}" for e in edges if v <= e), f">{edges[-1]}")
        out[k] = out.get(k, 0) + 1
    return out


def dive_cost_summary(on, units, dmg, other, threshold=None):
    """[d15-1118] (lines, problems): the DIVE COST section and the attacker identity statistics. Problems are
    missing or lost records; the caller fails on any."""
    out, problems = [], []
    mark_line = next((ln for ln in other if ln.startswith("MARK ")), None)
    if mark_line is None:
        problems.append("no MARK line (recorder older than d15-1118?)")
    elif not mark_line.startswith("MARK on:"):
        problems.append(mark_line)
    else:
        out.append(mark_line)
    s_lines = [ln for ln in other if ln.startswith("S ")]
    if not s_lines or "lost_mark=" not in s_lines[-1]:
        problems.append("no S line with mark counts")
    else:
        last = dict(kv.split("=") for kv in s_lines[-1].split()[2:])
        for k in ("lost_dmg", "lost_mark"):
            if int(last.get(k, "0")):
                problems.append(f"{k}={last[k]}: records were overwritten before they were read")
    ev = []
    for ln in other:
        p = ln.split()
        if p and p[0] == "M" and len(p) == 7:
            ev.append({"ms": int(p[1]), "tick": int(p[2]), "kind": int(p[3]), "ent": p[4].upper(),
                       "unit": p[5].upper(), "extra": _s32(int(p[6], 16))})
    if not ev:
        problems.append("no M line: no dive was marked")
    d15 = [d for d in dmg if "verdict" in d]
    if dmg and not d15:
        problems.append("D lines without the D15 fields (recorder older than d15-1118)")
    contact = [d for d in d15 if d["type"] in (5, 6)]
    flying = [d for d in contact if d["att_fly"] != "00000000"]
    if not flying:
        problems.append("no type-5 / 6 call with a flying attacker")
    # attacker identity on type 5 / 6
    n = len(contact)
    own = sum(1 for d in contact if d["att_fly"] != "00000000" and d["att_fly"] == d["attacker"])
    rider = sum(1 for d in contact if d["att_fly"] != "00000000" and d["att_fly"] != d["attacker"])
    none_att = sum(1 for d in contact if d["attacker"] == "00000000")
    flyer_units = {o for o, u in units.items() if u["flyer"]}
    of_flyer_unit = sum(1 for d in contact if d["att_unit"] in flyer_units)
    out.append(f"ATTACKER IDENTITY on type-5 / 6 calls: N={n}; attacker is the flying entity {own}/{n}, a rider "
               f"of one {rider}/{n}, no attacker {none_att}/{n}, no flyer {n - own - rider - none_att}/{n}; "
               f"attacker's unit is a flyer unit {of_flyer_unit}/{n}")
    window = air_dive_rules.DIVE_COST_WINDOW_TICKS
    for obj, u in sorted(units.items(), key=lambda kv: kv[1]["uid"]):
        if not u["flyer"]:
            continue
        mine_ev = [e for e in ev if e["unit"] == obj]
        mine = [d for d in contact if d["att_unit"] == obj]
        models = {d["att_fly"]: d["a_max"] for d in mine if d["att_fly"] != "00000000" and d["a_max"] != NONE32}
        models.update({d["victim"]: d["v_max"] for d in d15 if d["unit"] == obj and d["flyer"]
                       and d["victim"] not in models and d["v_max"] != NONE32})
        counts = {k: sum(1 for e in mine_ev if e["kind"] == k) for k in MARK_KINDS}
        out.append(f"DIVE COST {u['key']} uid {u['uid']}: marks " + ", ".join(
            f"{MARK_KINDS[k]} {counts[k]}" for k in MARK_KINDS) + f"; type-5/6 calls as attacker {len(mine)}")
        for e in mine_ev:
            if e["kind"] == 2:
                out.append(f"  touchdown model {e['ent']} tick {e['tick']} ({e['extra']} ticks after its arm)")
        payers, cost = {}, 0.0
        for d in mine:
            if d["verdict"] != 1:
                continue
            size = SIZE_BY_CODE.get(d["a_size"])
            share = air_dive_rules.DIVE_COST_SHARE.get(size)
            c = share * d["a_max"] if share is not None else None
            payers.setdefault(d["att_fly"], c)
            b = _braced(d)
            braced = (f"braced (+0x68 {d['v68']:#04x})" if b else f"NOT braced (+0x68 {d['v68']:#x})") \
                if b is not None else f"(+0x318 {d['v318']:#x}, older record)"
            victim_key = units.get(d["unit"], {}).get("key", d["unit"])
            out.append(f"  would-be cost: model {d['att_fly']} tick {d['tick']} ({_s32(d['age'])} ticks after "
                       f"touchdown), soldier {d['victim']} of {victim_key} {braced}, model health {d['a_hp']} / "
                       f"{d['a_max']} (size {size or d['a_size']}), cost "
                       + (f"{c:.0f} ({share:.0%})" if c is not None else "UNKNOWN: unreadable size code"))
            if c is None:
                problems.append(f"{u['key']}: model {d['att_fly']} has size code {d['a_size']}")
        cost = sum(c for c in payers.values() if c is not None)
        total = sum(models.values())
        if payers:
            out.append(f"  models paying within {window} ticks: {len(payers)} of {len(models)} seen; cost {cost:.0f} of "
                       f"{total} = {cost / total:.1%} of the unit's health (models seen; UNIT men {u['men']})")
        else:
            out.append(f"  models paying within {window} ticks: 0 of {len(models)} seen")
        # [round 3] the bracing values at contacts with a stamped mark, and the verdicts by reason
        stamped = [d for d in mine if d["mark"] == 2 or d["verdict"] in (1, 2, 3)]
        if stamped and "v68" in stamped[0]:
            bits = {"bit 3 set": sum(1 for d in stamped if _braced(d)),
                    "bit 3 clear": sum(1 for d in stamped if not _braced(d))}
            flags = {}
            for d in stamped:
                flags[f"{d['v68']:#04x}"] = flags.get(f"{d['v68']:#04x}", 0) + 1
            fractions = [d["u_brace"] for d in stamped if d["u_brace"] == d["u_brace"]]
            above = (f", unit fraction above the threshold {threshold}: "
                     f"{sum(1 for v in fractions if v > threshold)}/{len(fractions)}") if threshold is not None else ""
            out.append(f"  BRACING at {len(stamped)} contacts with a stamped mark: soldier +0x68 {bits} "
                       f"(values {dict(sorted(flags.items()))}); unit +0x3c18 {_float_hist(fractions)}{above}")
        reasons = {}
        for d in mine:
            r = VERDICT_REASONS.get(d["verdict"], f"verdict {d['verdict']}")
            reasons[r] = reasons.get(r, 0) + 1
        out.append(f"  VERDICTS {dict(sorted(reasons.items()))}")
        # [round 3] a ground re-charge never pays: arms in the battle, and the charge-factor multiplies on the
        # unit's models more than the window after its last stamp (with no new arm, they were not dives)
        ents = set(models) | {d["att_fly"] for d in mine}
        stamps = [e["ms"] for e in mine_ev if e["kind"] == 2]
        late = 0
        if stamps:
            cutoff = max(stamps) + window * 100
            for ln in other:
                p = ln.split()
                if p and p[0] == "C" and len(p) >= 14 and p[2] == "2" and p[13].upper() in ents \
                        and int(p[1]) > cutoff and f32(p[7]) >= 0.7:
                    late += 1
        out.append(f"  RECHARGE arms {counts[1]}, multiplies (charge factor >= 0.7) on its models more than {window} "
                   f"ticks after its last stamp {late}" + ("" if stamps else " (no stamp)"))
    return out, problems


DROP_EPS = 1e-4                       # a reading this much below the one before the call counts as a change
SAMPLE_MS = 100                       # reflect_probe.lua SAMPLE_MS: one recorder tick, one XA reading
# [d15-1118 stage 5] what the cost's own application looks like in the D lines (both runs of 2026-11-18): an
# applier call of type 2 with no attacker on a model of the paying unit, two recorder ticks after the call, from
# the applier's caller 0x1430be044 (APPLIER_CALLS "unidentified 0x1430be044": unit:reduce_hitpoints_unary's way in)
OWN_TYPE = 2


def _own_application(d):
    """a D line that can be a reduce_hitpoints_unary application: type 2, the D15 fields, no attacker"""
    return d["type"] == OWN_TYPE and d.get("attacker") == "00000000"


def _call_groups(made, follow_ms):
    """calls of one unit whose follow windows overlap, in order: [[call, ...], ...]"""
    groups = []
    for c in made:
        if groups and c["ms"] <= groups[-1][-1]["ms"] + follow_ms:
            groups[-1].append(c)
        else:
            groups.append([c])
    return groups


def cost_summary(units, dmg, other, reflect_keys=None):
    """[d15-1118] (lines, problems) for the COST section; problems fail the report.

    [stage 5] The cost is the shipped one (lib/dive_cost.lua); its observer lines name every entry of the cave
    dv_cost: XPAY (paid), XARC (braced, behind the front arc), XNOATTR (braced, no charge reflection). With
    ``reflect_keys`` (the land units with charge_reflection in the installed data) the cave's own attribute test
    is cross-checked: a paid soldier's unit must be in it, a skipped one must not. The paying entries of a unit
    must add up to the models its X / XREF lines name.

    [stage 5] Calls of one unit whose follow windows (DIVE_COST_FOLLOW_TICKS recorder ticks) overlap are judged
    together, on every distinct reading up to the end of the last call's window: "no health change" only when the
    lowest of them is not below the health before the group's first call. The cost's own applications (type-2
    calls with no attacker on the paying unit inside the group's window) are listed per model and are not
    ordinary damage."""
    out, problems = [], []
    cost_line = next((ln for ln in other if ln.startswith("COST ")), None)
    if cost_line is None:
        return out, ["no COST line (recorder older than the cost step)"]
    out.append(cost_line)
    follow_ms = air_dive_rules.DIVE_COST_FOLLOW_TICKS * SAMPLE_MS
    calls, xa, noattr, windows, entries = [], {}, {}, [], {}
    for ln in other:
        p = ln.split()
        if not p:
            continue
        if p[0] in ("X", "XOFF", "XREF") and len(p) == 11:
            calls.append({"kind": p[0], "ms": int(p[1]), "tick": int(p[2]), "uid": p[3], "key": p[4], "n": int(p[5]),
                          "want": float(p[6]), "p": float(p[7]), "before": float(p[8]), "men": int(p[9]),
                          "init": int(p[10])})
        elif p[0] == "XA" and len(p) == 6:
            # one reading per recorder tick and unit; overlapping calls print the same reading twice
            xa.setdefault(p[2], {})[int(p[1])] = {"ms": int(p[1]), "hp": float(p[4]), "men": int(p[5])}
        elif p[0] == "XERR":
            problems.append(ln)
        elif p[0] == "XNOATTR" and len(p) == 7:
            noattr.setdefault(p[5].upper(), []).append(ln)
            entries.setdefault(p[5].upper(), []).append(("XNOATTR", p[4], None))
        elif p[0] in ("XPAY", "XARC") and len(p) == 9:
            entries.setdefault(p[5].upper(), []).append((p[0], p[4], float(p[7])))
    for obj, u in sorted(units.items(), key=lambda kv: kv[1]["uid"]):
        if not u["flyer"]:
            continue
        mine = [c for c in calls if c["uid"] == u["uid"]]
        verdicts = [d for d in dmg if d.get("verdict") == 1 and d.get("att_unit") == obj]
        skipped = noattr.get(obj, [])
        if skipped:
            keys = sorted({ln.split()[4] for ln in skipped})
            out.append(f"COST {u['key']} uid {u['uid']}: {len(skipped)} braced contacts skipped, the soldier's unit "
                       f"lacks charge_reflection ({', '.join(keys)})")
        ent = entries.get(obj, [])
        arcs = [cos for kind, _k, cos in ent if kind == "XARC"]
        pays = [(key, cos) for kind, key, cos in ent if kind == "XPAY"]
        if ent:
            out.append(f"COST {u['key']} uid {u['uid']}: dv_cost entries: paid {len(pays)} (cos "
                       f"{sorted(round(c, 2) for _k, c in pays)}), behind the arc {len(arcs)} (cos "
                       f"{sorted(round(c, 2) for c in arcs)}), no charge reflection {len(skipped)}")
        if reflect_keys is not None:
            for kind, key, _cos in ent:
                if key == "?":
                    continue
                if (kind == "XNOATTR") == (key in reflect_keys):
                    problems.append(f"{u['key']} uid {u['uid']}: {kind} on {key}, which the game data says "
                                    f"{'has' if key in reflect_keys else 'lacks'} charge_reflection (attribute 0x27?)")
        called = sum(c["n"] for c in mine if c["kind"] in ("X", "XREF"))
        if pays and called != len(pays) and not any(u["uid"] in pr or obj in pr for pr in problems):
            problems.append(f"{u['key']} uid {u['uid']}: {len(pays)} paying entries but calls for {called} models")
        skipped = skipped + [None] * len(arcs)
        if len(verdicts) > len(skipped) and not mine and not any(u["uid"] in pr or obj in pr for pr in problems):
            problems.append(f"{u['key']} uid {u['uid']}: {len(verdicts) - len(skipped)} would-be cost verdicts "
                            "but no cost line")
        if not mine:
            continue
        maxes = [d["v_max"] for d in dmg if d["unit"] == obj and d.get("v_max", 0xFFFFFFFF) != 0xFFFFFFFF]
        maxes += [d["a_max"] for d in verdicts if d.get("a_max", 0xFFFFFFFF) != 0xFFFFFFFF]
        model_max = max(maxes) if maxes else None
        made = [c for c in mine if c["kind"] == "X"]
        readings = sorted(xa.get(u["uid"], {}).values(), key=lambda a: a["ms"])
        drop = ordinary = 0.0
        lost = own_total = hp_total = 0
        detail = []
        for group in _call_groups(made, follow_ms):
            first, end = group[0], group[-1]["ms"] + follow_ms
            after = [a for a in readings if first["ms"] < a["ms"] <= end]
            p_sum = sum(c["p"] for c in group)
            when = ", ".join(f"{c['ms']}" for c in group)
            if not after:
                problems.append(f"{u['key']} uid {u['uid']}: call at {when} ms has no reading after it")
                continue
            low = min(a["hp"] for a in after)
            if low > first["before"] - DROP_EPS:
                problems.append(f"{u['key']} uid {u['uid']}: call at {when} ms (p {p_sum:.4f}) and no health "
                                f"change in {len(after)} readings (the queued command was not executed?)")
            drop += first["before"] - low
            lost += first["men"] - after[-1]["men"]
            inside = [d for d in dmg if d["unit"] == obj and first["ms"] < d["ms"] <= end]
            own = [d for d in inside if _own_application(d)]
            hp_dmg = sum(d["damage"] for d in inside if not _own_application(d))
            if hp_dmg and model_max and first["init"] > 0:
                ordinary += hp_dmg / (first["init"] * model_max)
            elif hp_dmg:
                problems.append(f"{u['key']} uid {u['uid']}: ordinary damage {hp_dmg} with no model maximum health")
            hp_total += hp_dmg
            own_total += sum(d["damage"] for d in own)
            want = p_sum * first["init"] * model_max if model_max else None
            split = ", ".join(f"{d['victim']} (max {d['v_max']}) {d['damage']} at {d['ms']} ms" for d in own)
            detail.append(f"  OWN calls at {when} ms: p {p_sum:.4f} of {first['init']} x {model_max} = "
                          f"{want:.1f} wanted; applied {sum(d['damage'] for d in own)} on {len({d['victim'] for d in own})} model(s): "
                          f"{split or 'none seen'}" if want is not None else
                          f"  OWN calls at {when} ms: applied {sum(d['damage'] for d in own)} on {len({d['victim'] for d in own})} model(s): "
                          f"{split or 'none seen'}")
        out.append(f"COST {u['key']} uid {u['uid']}: calls {len(made)}, p requested "
                   f"{sum(c['p'] for c in made):.4f}, measured drop {drop:.4f}, the cost's own applications "
                   f"{own_total}, ordinary damage in the windows {hp_total} ({ordinary:.4f} of the unit), "
                   f"attributable {drop - ordinary:.4f}, models lost {lost}; would-have calls "
                   f"{sum(1 for c in mine if c['kind'] == 'XOFF')}, refused {sum(1 for c in mine if c['kind'] == 'XREF')}")
        for c in mine:
            out.append(f"  {c['kind']} {c['ms']} ms tick {c['tick']}: {c['n']} paying models, p {c['want']:.4f} "
                       f"wanted / {c['p']:.4f} applied, health before {c['before']:.4f}, men {c['men']} of {c['init']}")
        out.extend(detail)
        windows.extend((g[0]['ms'], g[-1]['ms'] + follow_ms) for g in _call_groups(made, follow_ms))
    # [stage 5] the same kind of hit on a flyer unit outside every call's window: none expected (control)
    flyer_objs = {o for o, u in units.items() if u['flyer']}
    stray = [d for d in dmg if d['unit'] in flyer_objs and _own_application(d)
             and not any(a < d['ms'] <= b for a, b in windows)]
    out.append(f"COST type-{OWN_TYPE} hits with no attacker on flyer units outside every call's window: {len(stray)}"
               + (f" ({', '.join(units[d['unit']]['key'] + ' ' + str(d['damage']) + ' at ' + str(d['ms']) for d in stray[:5])})"
                  if stray else ""))
    return out, problems


def main(argv):
    path = Path(argv[0]) if argv else GAME_ROOT / "reflect_probe.txt"
    on, units, refl, dmg, hp, other = parse(path.read_text("utf-8", errors="replace"))
    if not on or " on:" not in on:
        print("INCOMPLETE:", on or "no BATTLE line")
        return 1
    print(on)
    for line in other:
        if line.startswith(("STOP", "FAIL", "S ")):
            print(line)
    control = flyer = 0
    for obj, u in sorted(units.items(), key=lambda kv: (kv[1]["alliance"], kv[1]["uid"])):
        mine_r = [r for r in refl if r["charger_unit"] == obj]
        mine_d = [d for d in dmg if d["unit"] == obj]
        reflect_hits = [d["damage"] for d in mine_d if d["ret"] == REFLECT_RET]
        print(f"\n{u['key']} uid {u['uid']} side {u['alliance']} {'FLYER' if u['flyer'] else 'ground'} men {u['men']}")
        if mine_r:
            sp = sorted(r["speed"] for r in mine_r)
            print(f"  reflections as charger: {len(mine_r)}, closing speed {sp[0]:.1f} / "
                  f"{statistics.median(sp):.1f} / {sp[-1]:.1f} m/s, reflector bracing x"
                  f"{statistics.median(r['brace'] for r in mine_r):.2f}")
        by = {}
        for d in mine_d:
            k = (TYPES.get(d["type"], str(d["type"])), d["ret"])
            by.setdefault(k, []).append(d["damage"])
        for (t, ret), vals in sorted(by.items(), key=lambda kv: -sum(kv[1])):
            tag = "  <- the reflection's damage call" if ret == REFLECT_RET else ""
            print(f"  damage {t:16s} site {ret} [{call_class(ret)}]: {len(vals)} calls, {sum(vals)} total{tag}")
        if reflect_hits:
            print(f"  reflection hits: {reflect_hits} (the game's own)")
            if u["flyer"]:
                flyer += 1
            else:
                control += 1
        curve = hp_curve(hp, u["uid"])
        if curve:
            print(f"  first melee {curve[0] / 1000:.1f} s at hp {curve[1]:.4f}; loss after 1.5 s {curve[2][0]}, "
                  f"after 5 s {curve[2][1]}")
    print(f"\nreflections logged {len(refl)} (flyer chargers {sum(r['charger_flyer'] for r in refl)}), "
          f"damage calls {len(dmg)}, reflection damage calls "
          f"{sum(1 for d in dmg if d['ret'] == REFLECT_RET)}")
    for line in brace_summary(other, units):
        print(line)
    for line in charge_reflect_summary(other, dmg, units):
        print(line)
    for line in flyer_damage_summary(units, dmg, hp, other):
        print(line)
    timeline = path.parent / "timeline.txt"        # the driver's, next to the record in a flyer_run folder
    for line in timeline_contact_summary(units, dmg, other,
                                         timeline.read_text("utf-8", errors="replace") if timeline.is_file() else ""):
        print(line)
    print("CONTROL", "SEEN" if control else "NOT SEEN", f"({control} ground units took reflection damage)")
    print("FLYER", "SEEN" if flyer else "NOT SEEN", f"({flyer} flying units took reflection damage)")
    if not refl and not dmg:
        print("INCOMPLETE: no R or D line")
        return 1
    import unit_attributes
    threshold = unit_attributes.kv_rules(GAME_ROOT / "data" / "db.pack")["unit_braced_status_threshold"]
    lines, problems = dive_cost_summary(on, units, dmg, other, threshold)
    reflect_keys = set(unit_attributes.units_with_attribute(GAME_ROOT / "data" / "db.pack", "charge_reflection"))
    cost_lines, cost_problems = cost_summary(units, dmg, other, reflect_keys)
    lines += cost_lines
    problems += cost_problems
    for line in lines:
        print(line)
    for p in problems:
        print("FAIL D15:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
