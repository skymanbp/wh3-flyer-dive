"""Read-only views of the installed game's DB that the D15 probe needs (d15-1118): the kv rules and the land
units that carry a unit attribute.

* ``kv_rules(db_pack)``: {key: float} from every ``_kv_rules_tables`` fragment (the same decoding
  tests/test_reflect_charge.py pins against the game's values).
* ``units_with_attribute(db_pack, attribute)``: the land_units keys whose ``attribute_group`` carries
  ``attribute`` in ``unit_attributes_to_groups_junctions_tables`` (attribute, group); 129 for
  ``charge_reflection`` in 9.0.5 (docs/HISTORY.md PROBES-1118).
A table that does not decode to its end, or a missing table, is an error (no partial answer).
"""
import struct
from pathlib import Path

import flyer_db
import packfile


def _fragments(db_pack, prefix):
    out = []
    with packfile.PackFile.open(str(db_pack)) as p:
        for e in p.entries:
            if e.path.replace("\\", "/").lower().startswith(prefix):
                out.append((e.path, p.read_file(e)))
    if not out:
        raise RuntimeError(f"[unit_attributes] REFUSING: no {prefix} in {db_pack}")
    return out


def _body(d):
    """(row count, offset of the first row) after the optional GUID and version markers."""
    at = 0
    if d[:4] == b"\xfd\xfe\xfc\xff":
        at = 6 + 2 * struct.unpack_from("<H", d, 4)[0]
    if d[at:at + 4] == b"\xfc\xfd\xfe\xff":
        at += 8
    return struct.unpack_from("<I", d, at + 1)[0], at + 5


def _string(d, at):
    ln = struct.unpack_from("<H", d, at)[0]
    return d[at + 2:at + 2 + ln].decode("utf-8"), at + 2 + ln


def kv_rules(db_pack):
    out = {}
    for path, d in _fragments(db_pack, "db/_kv_rules_tables/"):
        n, at = _body(d)
        for _ in range(n):
            key, at = _string(d, at)
            out[key] = struct.unpack_from("<f", d, at)[0]
            at += 4
        if at != len(d):
            raise RuntimeError(f"[unit_attributes] REFUSING: {path} decoded to {at} of {len(d)}")
    return out


def _attribute_groups(db_pack, attribute):
    groups = set()
    for path, d in _fragments(db_pack, "db/unit_attributes_to_groups_junctions_tables/"):
        n, at = _body(d)
        for _ in range(n):
            attr, at = _string(d, at)
            group = ""
            if d[at]:                       # optional string: a flag byte, then the string
                group, at = _string(d, at + 1)
            else:
                at += 1
            if attr == attribute and group:
                groups.add(group)
        if at != len(d):
            raise RuntimeError(f"[unit_attributes] REFUSING: {path} decoded to {at} of {len(d)}")
    return groups


def units_with_attribute(db_pack, attribute):
    groups = _attribute_groups(db_pack, attribute)
    if not groups:
        raise RuntimeError(f"[unit_attributes] REFUSING: no attribute group carries {attribute!r}")
    rows = flyer_db.decode_round_trip(Path(db_pack), "land_units_tables", "attrs")[0]
    return sorted(r["key"] for r in rows if r.get("attribute_group") in groups)
