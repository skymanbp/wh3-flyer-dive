"""Battle animation table ``.bin`` (version 4) codec. [AIR-DIVE-W1 2026-11-09]

A battle bin maps animation slots (``schemas/anim_ids_warhammer_3.csv``:
103 = FLY_CHARGE_AIR_TO_GROUND, 104 = FLY_CHARGE_LAND, ...) to the clips an
animation table plays. ``animpack_codec`` already reads the container and two
facts out of a bin (its table name, the clip paths it names); this module is
the first that reads and writes the whole slot list, because AIR-DIVE-W1 has
to change which clip one slot plays.

Layout, measured on the installed game (every battle bin in anim.pack /
anim2.pack / anim_3.pack: 1,426 decode and re-encode byte-identical, zero
trailing bytes; the one non-battle ``matched_combat/attila_generated.bin`` is
version 1 and refused)::

    u32 4 | u32 3 | str name | str s1 | str s2 | str skeleton | str locomotion_graph
    u16 flags | u32 entry_count
    entry: u32 slot | f32 blend_in | f32 weight | u32 weapon_bools | u8 unk
           u32 ref_count | ref_count * (str anim, str meta, str sound_meta)
    (str = u16 length + ascii)

[AIR-DIVE-W8 2026-11-10] A vanilla table can NOT be overridden by shipping a
bin with the same inner path (or name) in a mod: seven in-game canaries
(user-confirmed) showed the vanilla table keep playing every time, although
311 bins across 10 Workshop packs ship same-named bins (measured 2026-11-09).
A changed table ships under a new name and land units are repointed to it:
``lib/anim_table_rename.py``.
/ 战斗动画表 bin 的完整读写；1,426 个原版 bin 逐字节往返。
"""
from __future__ import annotations

import struct

# the string form is anim_codec's (TEST-REPAIR-1113: one home)
from anim_codec import read_ascii16 as _rs, write_ascii16 as _ws


class BinFormatError(ValueError):
    """Not a version-4 battle animation table."""


def parse(blob):
    """Decode a battle bin into a plain dict; refuse anything but version 4."""
    o = 0
    ver, sub = struct.unpack_from("<II", blob, o)
    o += 8
    if ver != 4:
        raise BinFormatError(f"bin version {ver} (only 4 is a battle table)")
    out = {"version": ver, "sub": sub}
    for key in ("name", "s1", "s2", "skeleton", "locomotion_graph"):
        out[key], o = _rs(blob, o)
    out["flags"] = struct.unpack_from("<H", blob, o)[0]
    o += 2
    count = struct.unpack_from("<I", blob, o)[0]
    o += 4
    entries = []
    for _ in range(count):
        slot, blend, weight, wb = struct.unpack_from("<IffI", blob, o)
        o += 16
        unk = blob[o]
        o += 1
        rc = struct.unpack_from("<I", blob, o)[0]
        o += 4
        refs = []
        for _r in range(rc):
            anim, o = _rs(blob, o)
            meta, o = _rs(blob, o)
            sound, o = _rs(blob, o)
            refs.append([anim, meta, sound])
        entries.append({"slot": slot, "blend_in": blend, "weight": weight,
                        "weapon_bools": wb, "unk": unk, "refs": refs})
    if o != len(blob):
        raise BinFormatError(f"consumed {o} of {len(blob)} bytes")
    out["entries"] = entries
    return out


def write(table):
    """Encode a dict from :func:`parse` back to bytes."""
    out = bytearray(struct.pack("<II", table["version"], table["sub"]))
    for key in ("name", "s1", "s2", "skeleton", "locomotion_graph"):
        out += _ws(table[key])
    out += struct.pack("<H", table["flags"])
    out += struct.pack("<I", len(table["entries"]))
    for e in table["entries"]:
        out += struct.pack("<IffI", e["slot"], e["blend_in"], e["weight"],
                           e["weapon_bools"])
        out += bytes([e["unk"]]) + struct.pack("<I", len(e["refs"]))
        for anim, meta, sound in e["refs"]:
            out += _ws(anim) + _ws(meta) + _ws(sound)
    return bytes(out)
