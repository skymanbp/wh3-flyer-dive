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

[d15-1118, maintainer] COST: the recorder's test-only step that applies the would-be costs through
unit:reduce_hitpoints_unary (switch cost=1). Per flyer unit: calls, p requested, the measured health drop (the
reading before each call minus the lowest of the DIVE_COST_FOLLOW_TICKS readings after it), the ordinary damage
the D lines put on that unit in the same windows (as a share of the unit: initial men x the model's maximum
health), the drop attributable to the calls, models lost; with the switch off, the would-have calls. FAIL: no
COST line; an XERR line; a call after which no reading fell (the queued command was not executed -- the submit
is skipped when [[g]+0x468]+0x3b0 / +0x3b1 is set, 0x142f0f633); verdicts for a unit with no cost line at all.

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
        elif p[0] == "D" and len(p) in (10, 12, 24):
            dmg.append({"ms": int(p[1]), "tick": int(p[2]), "ret": p[3].upper(), "unit": p[5].upper(), "damage": int(p[6]),
                        "type": int(p[7]), "flyer": p[8] == "1", "victim": p[4].upper(),
                        "thread": int(p[10]) if len(p) >= 12 else None, "clock": int(p[11]) if len(p) >= 12 else None})
            if len(p) == 24:                   # [d15-1118] the D15 fields, hex
                dmg[-1].update({"v318": int(p[12], 16), "verdict": int(p[13], 16), "attacker": p[14].upper(),
                                "att_fly": p[15].upper(), "v_max": int(p[16], 16), "v_hp": int(p[17], 16),
                                "a_max": int(p[18], 16), "a_hp": int(p[19], 16), "mark": int(p[20], 16),
                                "age": int(p[21], 16), "att_unit": p[22].upper(), "a_size": int(p[23], 16)})
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


NONE32 = 0xFFFFFFFF
MARK_KINDS = {1: "armed", 2: "stamped", 3: "spent", 4: "expired"}
VERDICTS = {0: "-", 1: "WOULD-BE COST", 2: "mark expired", 3: "not braced", 4: "armed only", 5: "already spent"}
SIZE_BY_CODE = {code: size for size, code in air_dive_rules.TAKEOFF_SIZE_CODES.items()}


def _s32(v):
    return v - 2**32 if v >= 2**31 else v


def dive_cost_summary(on, units, dmg, other):
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
            braced = "braced" if d["v318"] == reflect_probe_asm.BRACED else f"NOT braced ({d['v318']:#x})"
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
    return out, problems


DROP_EPS = 1e-4                       # a reading this much below the one before the call counts as a change


def cost_summary(units, dmg, other):
    """[d15-1118] (lines, problems) for the COST section; problems fail the report."""
    out, problems = [], []
    cost_line = next((ln for ln in other if ln.startswith("COST ")), None)
    if cost_line is None:
        return out, ["no COST line (recorder older than the cost step)"]
    out.append(cost_line)
    calls, xa = [], {}
    for ln in other:
        p = ln.split()
        if not p:
            continue
        if p[0] in ("X", "XOFF", "XREF") and len(p) == 11:
            calls.append({"kind": p[0], "ms": int(p[1]), "tick": int(p[2]), "uid": p[3], "key": p[4], "n": int(p[5]),
                          "want": float(p[6]), "p": float(p[7]), "before": float(p[8]), "men": int(p[9]),
                          "init": int(p[10])})
        elif p[0] == "XA" and len(p) == 6:
            xa.setdefault(p[2], []).append({"ms": int(p[1]), "k": int(p[3]), "hp": float(p[4]), "men": int(p[5])})
        elif p[0] == "XERR":
            problems.append(ln)
    for obj, u in sorted(units.items(), key=lambda kv: kv[1]["uid"]):
        if not u["flyer"]:
            continue
        mine = [c for c in calls if c["uid"] == u["uid"]]
        verdicts = [d for d in dmg if d.get("verdict") == 1 and d.get("att_unit") == obj]
        if verdicts and not mine and not any(u["uid"] in pr or obj in pr for pr in problems):
            problems.append(f"{u['key']} uid {u['uid']}: {len(verdicts)} would-be cost verdicts but no cost line")
        if not mine:
            continue
        maxes = [d["v_max"] for d in dmg if d["unit"] == obj and d.get("v_max", 0xFFFFFFFF) != 0xFFFFFFFF]
        maxes += [d["a_max"] for d in verdicts if d.get("a_max", 0xFFFFFFFF) != 0xFFFFFFFF]
        model_max = max(maxes) if maxes else None
        made = [c for c in mine if c["kind"] == "X"]
        drop = ordinary = 0.0
        lost = 0
        for i, c in enumerate(made):
            nxt = made[i + 1]["ms"] if i + 1 < len(made) else None
            after = [a for a in xa.get(u["uid"], []) if a["ms"] > c["ms"] and (nxt is None or a["ms"] <= nxt)]
            if not after:
                problems.append(f"{u['key']} uid {u['uid']}: call at {c['ms']} ms has no reading after it")
                continue
            low = min(a["hp"] for a in after)
            if low > c["before"] - DROP_EPS:
                problems.append(f"{u['key']} uid {u['uid']}: call at {c['ms']} ms (p {c['p']:.4f}) and no health "
                                f"change in {len(after)} readings (the queued command was not executed?)")
            drop += c["before"] - low
            lost += c["men"] - after[-1]["men"]
            hp_dmg = sum(d["damage"] for d in dmg if d["unit"] == obj and c["ms"] < d["ms"] <= after[-1]["ms"])
            if hp_dmg and model_max and c["init"] > 0:
                ordinary += hp_dmg / (c["init"] * model_max)
            elif hp_dmg:
                problems.append(f"{u['key']} uid {u['uid']}: ordinary damage {hp_dmg} with no model maximum health")
            c["hp_dmg"] = hp_dmg
        hp_total = sum(c.get("hp_dmg", 0) for c in made)
        out.append(f"COST {u['key']} uid {u['uid']}: calls {len(made)}, p requested "
                   f"{sum(c['p'] for c in made):.4f}, measured drop {drop:.4f}, ordinary damage in the windows "
                   f"{hp_total} ({ordinary:.4f} of the unit), attributable {drop - ordinary:.4f}, models lost {lost}; "
                   f"would-have calls {sum(1 for c in mine if c['kind'] == 'XOFF')}, refused "
                   f"{sum(1 for c in mine if c['kind'] == 'XREF')}")
        for c in mine:
            out.append(f"  {c['kind']} {c['ms']} ms tick {c['tick']}: {c['n']} paying models, p {c['want']:.4f} "
                       f"wanted / {c['p']:.4f} applied, health before {c['before']:.4f}, men {c['men']} of {c['init']}")
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
    print("CONTROL", "SEEN" if control else "NOT SEEN", f"({control} ground units took reflection damage)")
    print("FLYER", "SEEN" if flyer else "NOT SEEN", f"({flyer} flying units took reflection damage)")
    if not refl and not dmg:
        print("INCOMPLETE: no R or D line")
        return 1
    lines, problems = dive_cost_summary(on, units, dmg, other)
    cost_lines, cost_problems = cost_summary(units, dmg, other)
    lines += cost_lines
    problems += cost_problems
    for line in lines:
        print(line)
    for p in problems:
        print("FAIL D15:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
