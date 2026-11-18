#!/usr/bin/env python3
"""TEST-ONLY: summary of reflect_probe.txt (pipelines/reflect_probe.lua). [update-1117 part C, D4]

Per unit of the battle (key, side, flyer or not):
  * impact reflections it took as the CHARGER (rf_refl): count, closing speed min / median / max;
  * damage it took (rf_dmg), by damage type and call site, and in particular the reflection's
    own damage call (call site returning to REFLECT_DAMAGE_RETURN, damage type 0): hits and the
    damage of each -- the game's reflection hit. With the user's ruling D4 a diving flyer is to
    take REFLECTION_FLYER_DAMAGE_FACTOR times that hit; this report prints the factor and, when a
    flyer took reflection hits, each hit next to its expected doubled value is a later run's job
    (a run with the mechanism in place against a run without);
  * hit points: unary hp at its first melee sample, and its loss 1.5 s and 5 s later.
Verdict lines: CONTROL (some non-flyer took reflection damage: the logger can see a reflection),
FLYER (some flyer took reflection damage), and the counts behind both. A file with no BATTLE
... on line or no R / D line at all is INCOMPLETE, never a pass.

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
    "LD_WH3_ROOT", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III"))
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
        if p[0] == "BATTLE":
            on, units, refl, dmg, hp, other = line, {}, [], [], [], []
        elif p[0] == "UNIT" and len(p) == 7:
            units[p[4].split("=")[1].upper()] = {"uid": p[1], "alliance": int(p[2]), "key": p[3],
                                         "men": int(p[5].split("=")[1]), "flyer": p[6] == "flyer=1"}
        elif p[0] == "R" and len(p) == 12:
            refl.append({"ms": int(p[1]), "tick": int(p[2]), "charger_unit": p[8].upper(), "reflector_unit": p[7].upper(),
                         "ret": p[5], "speed": f32(p[6]), "charger_flyer": p[9] == "1",
                         "brace": f32(p[10]), "immovable": int(p[11])})
        elif p[0] == "D" and len(p) == 10:
            dmg.append({"ms": int(p[1]), "tick": int(p[2]), "ret": p[3].upper(), "unit": p[5].upper(), "damage": int(p[6]),
                        "type": int(p[7]), "flyer": p[8] == "1"})
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
    factor = air_dive_rules.REFLECTION_FLYER_DAMAGE_FACTOR
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
            print(f"  damage {t:16s} site {ret}: {len(vals)} calls, {sum(vals)} total{tag}")
        if reflect_hits:
            print(f"  reflection hits: {reflect_hits} (the game's own; the ruled flyer hit is x{factor}: "
                  f"{[h * factor for h in reflect_hits]})")
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
    print("CONTROL", "SEEN" if control else "NOT SEEN", f"({control} ground units took reflection damage)")
    print("FLYER", "SEEN" if flyer else "NOT SEEN", f"({flyer} flying units took reflection damage)")
    if not refl and not dmg:
        print("INCOMPLETE: no R or D line")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
