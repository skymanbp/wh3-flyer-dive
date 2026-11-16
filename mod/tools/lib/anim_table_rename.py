"""Ship a changed vanilla battle animation table under a NEW name. [AIR-DIVE-W8 2026-11-10]

WHY THIS EXISTS. Total War: Warhammer III does not let a mod replace a vanilla
battle animation table by shipping something under the table's own name.
Measured in game over seven canary packs (user-confirmed 2026-11-10), each of
these was ignored and the vanilla table kept playing:

* a same-named bin inside a mod animpack (``@ld_air_dive.animpack``, the W1-W7
  delivery of the air dive);
* by-path copies of the whole ``animation_tables.animpack`` and
  ``animation_tables__.animpack``;
* a loose ``animations/database/battle/bin/<name>.bin``;
* the JSON fragment ``animations/database/battle/fragments/<name>.txt``.

What does take effect is the method Workshop 3120190274 (storm_dargon_anim)
and the Community Bug Fix Mod's land_units "animchange" fragment use, and
canary 7 proved it (every slot of ``dr1_dragon_ld_dive`` pointed at
``dr1_attack_01``; the star dragon visibly changed):

1. ship a copy of the table whose header ``name`` is new (nothing else in
   the bin changes), inside an animpack and also as a loose bin at
   ``animations/database/battle/bin/<new>.bin``;
2. register it: one ``battle_animations_table_tables`` row (key, skeleton);
3. copy the source table's rows of ``culture_to_battle_animation_tables_tables``
   (table, culture_pack) onto the new name;
4. repoint ``land_units_tables.man_animation`` of every unit on the source
   table to the new name;
5. [AIR-DIVE-W9 2026-11-10] repoint ``mounts_tables.animation`` of every
   mount on the source table. A MOUNTED unit's body (griffon, pegasus,
   ridden dragon, skycutter) plays its mount row's ``animation``;
   ``man_animation`` is only the rider's table. The rider table's header
   ``s1`` names a mount table too, but it already disagrees with the mount
   row in 50 of the 1,122 vanilla mounted units (253 leave it empty;
   measured 2026-11-10), so repointing the mount row alone is safe. 67
   vanilla mount rows name one of the air dive's 53 renamed tables and 222
   vanilla land units ride them; W8 repointed only step 4, so griffon
   knights, skycutters and every ridden flyer kept the vanilla table
   (lane air-dive-clips canary 15 found it).

[AIR-DIVE-W12 2026-11-11] One source table may ship as SEVERAL copies, each
serving named battle entities (the air dive gives each charge speed its own
plough clip, so riders of one table at different speeds need different
copies). A record then carries ``entities``; the source maps to
``{entity: copy}`` and every repoint names the row's entity -- a rider the
records do not name is a refusal, so a new rider cannot silently take some
other speed's copy.

This module is that mechanism and nothing air-dive specific: the rename of a
bin, the four DB row sets read from the installed db.pack, and the repoint
of one ``man_animation`` / ``animation`` value. Every emitter that ships a
land unit or a mount (vanilla override, our clones, our characters, the
vendored closures, the mini-mod) repoints through this module, so a unit on
a renamed table cannot be forgotten by one lane and remembered by another. Fail-closed throughout: a
header name that does not match its path, a registry skeleton that disagrees
with the bin's, a culture table that does not walk to EOF, a new name that
collides with a vanilla table -- each is a refusal, never a guess.
/ 原版动画表不能按同名覆盖；改名发新表、登记、复制文化行、改指 land_units。
"""
from __future__ import annotations

import json
from pathlib import Path

import anim_table_bin

BIN_DIR = "animations/database/battle/bin/"
REGISTRY_TABLE = "battle_animations_table_tables"
CULTURE_TABLE = "culture_to_battle_animation_tables_tables"
LAND_TABLE = "land_units_tables"
MOUNTS_TABLE = "mounts_tables"


class Refused(RuntimeError):
    """The rename cannot be done safely; the message says why."""


def bin_path(name):
    """VFS inner path of the battle bin for table ``name``."""
    return f"{BIN_DIR}{name}.bin"


def rename_bin(inner_path, blob, suffix, entities=None):
    """``(record, new_blob)`` for one vanilla battle bin renamed by ``suffix``.

    ``record`` = {"source", "renamed", "skeleton", "bin"}: the source table's
    name, the new name, the skeleton from the bin header (the registry row
    copies it) and the new bin's inner path. Only the header ``name`` field
    changes; the path must already be ``BIN_DIR/<name>.bin`` (CA's own layout
    for every one of the 1,426 installed battle bins). [AIR-DIVE-W12]
    ``entities`` (a list) is copied into the record: the battle entities this
    copy serves (module docstring).
    """
    table = anim_table_bin.parse(blob)
    old = table["name"]
    if inner_path != bin_path(old):
        raise Refused(f"{inner_path}: header name {old!r} does not match its "
                      "path, so which table it is cannot be told")
    if not suffix or old.endswith(suffix):
        raise Refused(f"{old}: suffix {suffix!r} is empty or already present")
    table["name"] = old + suffix
    rec = {"source": old, "renamed": table["name"],
           "skeleton": table["skeleton"], "bin": bin_path(table["name"])}
    if entities is not None:
        if not entities:
            raise Refused(f"{old}{suffix}: serves no entity")
        rec["entities"] = sorted(entities)
    return rec, anim_table_bin.write(table)


def load_renames(manifest_path, key="tables_renamed", keep_key="grounded_riders"):
    """``(records, renames)`` from a manifest's ``key`` list (records as
    :func:`rename_bin` returns them); fail-closed. ``renames`` maps a source
    table to its one copy (a record without ``entities``) or to
    ``{entity: copy}`` (records with ``entities``; a source mixing the two
    forms, or one entity served twice, is a refusal). [AIR-DIVE-W12] The
    manifest's ``keep_key`` (``{source: [entity]}``, optional) names riders
    of a per-entity source that keep the SOURCE table (the air dive's
    non-flying riders): they map to the source itself."""
    path = Path(manifest_path)
    if not path.is_file():
        raise Refused(f"{path} missing -- the renamed animation tables and "
                      "their repoint come from it")
    records = json.loads(path.read_text(encoding="utf-8")).get(key)
    if not records:
        raise Refused(f"{path}: no {key!r} records")
    out, seen = {}, set()
    for rec in records:
        src, new = rec["source"], rec["renamed"]
        if new in seen:
            raise Refused(f"{path}: {new} renamed twice")
        seen.add(new)
        if rec["bin"] != bin_path(new) or not rec.get("skeleton"):
            raise Refused(f"{path}: {src} record has no skeleton or a bin "
                          f"path {rec['bin']!r} that does not name {new}")
        ents = rec.get("entities")
        if ents is None:
            if src in out:
                raise Refused(f"{path}: {src} -> {new} renamed twice")
            out[src] = new
            continue
        by_ent = out.setdefault(src, {})
        if not isinstance(by_ent, dict) or not ents:
            raise Refused(f"{path}: {src} mixes whole-table and per-entity "
                          "copies, or a copy serves no entity")
        for ent in ents:
            if ent in by_ent:
                raise Refused(f"{path}: {src}: entity {ent} served by "
                              f"{by_ent[ent]} and {new}")
            by_ent[ent] = new
    keep = json.loads(path.read_text(encoding="utf-8")).get(keep_key) or {}
    for src, ents in sorted(keep.items()):
        by_ent = out.get(src)
        if not isinstance(by_ent, dict):
            raise Refused(f"{path}: {keep_key} names {src}, which has no "
                          "per-entity copies")
        for ent in ents:
            if ent in by_ent:
                raise Refused(f"{path}: {src}: entity {ent} both kept and "
                              f"served by {by_ent[ent]}")
            by_ent[ent] = src
    return records, out


def repoint(man_animation, renames, entity=None):
    """The table a row must name: the renamed copy when its table was
    renamed, else unchanged. [AIR-DIVE-W12] Where the source ships per-entity
    copies, ``entity`` picks the copy; an entity no copy serves is a refusal."""
    target = renames.get(man_animation)
    if target is None:
        return man_animation
    if isinstance(target, str):
        return target
    if entity not in target:
        raise Refused(f"{man_animation}: no renamed copy serves entity "
                      f"{entity!r} (served: {sorted(target)})")
    return target[entity]


def targets(renames, source):
    """Every renamed copy of ``source`` (empty when it is not renamed)."""
    target = renames.get(source)
    if target is None:
        return []
    if isinstance(target, str):
        return [target]
    return sorted(set(target.values()) - {source})


def _installed_rows(db_pack, table, tag):
    import installed_db_table
    rows, header = installed_db_table.decode_round_trip(db_pack, table, tag)
    return rows, header


def registry_rows(records, db_pack, tag):
    """``battle_animations_table_tables`` rows for the renamed tables.

    The skeleton is the bin header's; where vanilla registers the source table
    the two must agree (refusal otherwise). A source table vanilla never
    registered (``dr04_dragon_jade``, measured 2026-11-10) still gets its row:
    the new name must be registered for any unit to use it.
    Returns ``(rows, unregistered_sources)``.
    """
    rows, _h = _installed_rows(db_pack, REGISTRY_TABLE, tag)
    by_key = {r["key"]: r for r in rows}
    out, unregistered = [], []
    for rec in sorted(records, key=lambda r: r["renamed"]):
        if rec["renamed"] in by_key:
            raise Refused(f"{rec['renamed']}: already a vanilla table name")
        src = by_key.get(rec["source"])
        if src is None:
            unregistered.append(rec["source"])
        elif src["skeleton"] != rec["skeleton"]:
            raise Refused(f"{rec['source']}: registry skeleton "
                          f"{src['skeleton']!r} != bin header {rec['skeleton']!r}")
        out.append({"key": rec["renamed"], "skeleton": rec["skeleton"]})
    return out, unregistered


def culture_rows(renames, db_pack, tag):
    """``culture_to_battle_animation_tables_tables`` rows: every installed row
    of a source table, copied onto its new name."""
    rows, _h = _installed_rows(db_pack, CULTURE_TABLE, tag)
    return [{"battle_animations_table": new, "culture_pack": r["culture_pack"]}
            for r in rows
            for new in targets(renames, r["battle_animations_table"])]


def _repointed_rows(table, column, entity_column, renames, db_pack, tag, skip):
    """``[(row, raw)]``: every installed ``table`` row whose ``column`` names
    a source table, whole, that cell repointed (by the row's
    ``entity_column`` where the source has per-entity copies) and every other
    cell replayed byte-for-byte (DB merge is whole-row replacement)."""
    import installed_db_table
    rows, _header, replay = installed_db_table.decode_round_trip_with_replay(
        db_pack, table, tag)
    out = []
    for row, raw in zip(rows, replay):
        if row.get(column) not in renames or row["key"] in skip:
            continue
        new = repoint(row[column], renames, row[entity_column])
        if new == row[column]:
            continue  # [AIR-DIVE-W12] a rider that keeps the source table
        new_row, raw = dict(row), dict(raw or {})
        new_row[column] = new
        raw.pop(column, None)
        out.append((new_row, raw or None))
    return out


def land_unit_rows(renames, db_pack, tag, skip=()):
    """Every installed land unit on a source table, ``man_animation``
    repointed (:func:`_repointed_rows`). Keys in ``skip`` are shipped whole by
    another emitter, which repoints them itself (one row, one owner)."""
    return _repointed_rows(LAND_TABLE, "man_animation", "man_entity",
                           renames, db_pack, tag, skip)


def mount_rows(renames, db_pack, tag, skip=()):
    """[AIR-DIVE-W9] Every installed mount on a source table, ``animation``
    repointed (module docstring step 5); ``skip`` as for land units."""
    return _repointed_rows(MOUNTS_TABLE, "animation", "entity", renames,
                           db_pack, tag, skip)


def repoint_land_units_tsv(text, renames):
    """``(text, count)``: a staged ``land_units_tables`` TSV with each row's
    ``man_animation`` repointed (:func:`repoint_tsv`)."""
    return repoint_tsv(text, renames, "man_animation", "man_entity")


def repoint_mounts_tsv(text, renames):
    """[AIR-DIVE-W9] ``(text, count)``: a staged ``mounts_tables`` TSV with
    each row's ``animation`` repointed (:func:`repoint_tsv`)."""
    return repoint_tsv(text, renames, "animation", "entity")


def repoint_tsv(text, renames, column, entity_column):
    """``(text, count)``: a staged DB TSV (header line, ``#`` metadata line,
    rows) with each row's ``column`` repointed (by its ``entity_column``
    where the source has per-entity copies). The text is returned unchanged
    (same object) when nothing moves; line endings are kept."""
    lines = text.split("\n")
    header = lines[0].rstrip("\r").split("\t")
    for c in (column, entity_column):
        if c not in header:
            raise Refused(f"TSV has no {c} column")
    col, ecol = header.index(column), header.index(entity_column)
    count = 0
    for i in range(2, len(lines)):
        line = lines[i]
        cr = line.endswith("\r")
        cells = (line[:-1] if cr else line).split("\t")
        if len(cells) <= col or cells[col] not in renames:
            continue
        new = repoint(cells[col], renames,
                      cells[ecol] if len(cells) > ecol else None)
        if new == cells[col]:
            continue  # [AIR-DIVE-W12] a rider that keeps the source table
        cells[col] = new
        lines[i] = "\t".join(cells) + ("\r" if cr else "")
        count += 1
    return ("\n".join(lines), count) if count else (text, 0)
