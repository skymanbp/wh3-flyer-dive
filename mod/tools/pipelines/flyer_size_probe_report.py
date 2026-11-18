#!/usr/bin/env python3
"""TEST-ONLY: does engine entity +0x74 hold the battle_entities size class?
[update-1117 B, user ruling D3 2026-11-17]

Reads flyer_size_probe.txt (pipelines/flyer_size_probe.lua) and joins every
unit key with the installed tables (land unit -> its flying body entity,
air_dive_rules.body_entity -> battle_entities.size). Prints one line per
flying model (unit key, installed size, int32 at +0x74, and the same read
again) and a verdict:

  HOLDS        every size present reads one value, the value never changes
               between the two reads, different sizes read different values
               and the values rise with size (small < medium < large <
               very_large) -- the mapping {size: value} is printed;
  REFUTED      some size reads two values, or two sizes read one value, or
               a value changed between the reads, or the order is not by size;
  INCOMPLETE   fewer than all four sizes or fewer than two reads were seen
               (never a pass).
Also printed per model: the D3 take-off window its size gets
(air_dive_rules.takeoff_pin_window) and the float at +0xb4 (the physics mass the static read
names, design.md section 3) -- informative only.

usage: python -P tools/pipelines/flyer_size_probe_report.py [flyer_size_probe.txt]
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path

import os
import struct
import sys
from pathlib import Path

import air_dive_rules

GAME_ROOT = Path(os.environ.get(
    "LD_WH3_ROOT", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III"))
FIRST = 0x60
SIZE_AT, MASS_AT = 0x74, 0xB4


def parse(text):
    """(units {uid: key}, reads {(uid, index): [(ms, entity id, bytes)]}, status)"""
    units, reads, status = {}, {}, []
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "BATTLE":
            units, reads, status = {}, {}, ["BATTLE"]     # the last battle in the file
        elif p[0] == "UNIT" and len(p) >= 4:
            units[p[1]] = p[3]
        elif p[0] == "E" and len(p) == 6:
            reads.setdefault((p[2], int(p[3])), []).append((int(p[1]), p[4], bytes.fromhex(p[5])))
        elif p[0] in ("END", "FAIL"):
            status.append(line)
    return units, reads, status


def int_at(raw, off):
    return struct.unpack_from("<i", raw, off - FIRST)[0]


def float_at(raw, off):
    return struct.unpack_from("<f", raw, off - FIRST)[0]


def installed_sizes(keys):
    """{land unit key: (body entity key, size)} from the installed game; missing keys absent."""
    import flyer_db
    db = GAME_ROOT / "data" / "db.pack"
    land = {r["key"]: r for r in flyer_db.decode_round_trip(db, "land_units_tables", "size_probe")[0]}
    mounts = {r["key"]: r for r in flyer_db.decode_round_trip(db, "mounts_tables", "size_probe")[0]}
    ents = {r["key"]: r for r in flyer_db.decode_round_trip(db, "battle_entities_tables", "size_probe")[0]}
    out = {}
    for k in keys:
        if k in land:
            e = air_dive_rules.body_entity(land[k], mounts, ents)
            if e is not None:
                out[k] = (e["key"], e["size"])
    return out


def verdict(rows):
    """rows: [(size, [values over reads])] -> (word, why, mapping)."""
    by_size, why = {}, []
    for size, values in rows:
        if len(set(values)) != 1:
            why.append(f"a {size} model's value changed between reads: {values}")
        by_size.setdefault(size, set()).update(values)
    for size, vals in by_size.items():
        if len(vals) != 1:
            why.append(f"{size} reads {sorted(vals)}")
    mapping = {s: next(iter(v)) for s, v in by_size.items() if len(v) == 1}
    if len(set(mapping.values())) != len(mapping):
        why.append(f"two sizes read one value: {mapping}")
    order = [s for s in air_dive_rules.BODY_SIZES if s in mapping]
    if [mapping[s] for s in order] != sorted(mapping[s] for s in order):
        why.append(f"values do not rise with size: {mapping}")
    if why:
        return "REFUTED", why, mapping
    reads = min((len(v) for _s, v in rows), default=0)
    missing = [s for s in air_dive_rules.BODY_SIZES if s not in mapping]
    if missing or reads < 2:
        return "INCOMPLETE", [f"sizes not seen: {missing}" if missing else "",
                              f"reads per model: {reads}"], mapping
    return "HOLDS", [], mapping


def main(argv):
    path = Path(argv[0]) if argv else GAME_ROOT / "flyer_size_probe.txt"
    units, reads, status = parse(path.read_text("utf-8", errors="replace"))
    if "BATTLE" not in status:
        print("INCOMPLETE: no BATTLE line in", path)
        return 1
    sizes = installed_sizes(set(units.values()))
    rows = []
    for (uid, index), seen in sorted(reads.items()):
        key = units.get(uid, "?")
        body, size = sizes.get(key, ("?", "?"))
        values = [int_at(raw, SIZE_AT) for _ms, _id, raw in seen]
        masses = [round(float_at(raw, MASS_AT), 1) for _ms, _id, raw in seen]
        window = air_dive_rules.takeoff_pin_window(size) if size != "?" else "?"
        print(f"{key:55s} body {body:45s} size {size:10s} D3 window {window} ticks entity {seen[0][1]} "
              f"+0x74 {values} +0xb4 {masses}")
        if size != "?":
            rows.append((size, values))
    word, why, mapping = verdict(rows)
    for s in status[1:]:
        print(s)
    print(f"{word}: mapping {mapping}" + ("".join(f"\n  {w}" for w in why if w)))
    return 0 if word == "HOLDS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
