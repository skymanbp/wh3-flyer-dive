#!/usr/bin/env python3
"""Air dive charge -- the STANDALONE mini-mod pack. [AIR-DIVE-W1 2026-11-09]

User 2026-11-09 (CONTENT_LEDGER §C8-45 item 3): the dive charge ships inside
ld_mod.pack and "can also be its own small mod". This writes that small mod:
one PFH5 mod pack holding exactly the air-dive content and nothing of ours
besides it, built from the installed game every time (so a game patch is a
re-run, not a hand edit):

* the RENAMED flight tables (``<name>_ld_dive``, slot 104 removed, slot
  489 playing the plough clip; loose bins plus
  ``ld_air_dive_tables.animpack``) and [AIR-DIVE-W9] the 34 plough clips and
  their metas, taken from ``mod/assets/air_dive`` after re-checking every
  sha256 against ``air_dive_manifest.json`` (``pipelines/air_dive.py``
  derives them);
* [AIR-DIVE-W8 2026-11-10] the three DB row sets that make the renamed tables
  play (vanilla tables cannot be overridden by name; ``lib/anim_table_rename``):
  ``battle_animations_table_tables`` (one row per renamed table),
  ``culture_to_battle_animation_tables_tables`` (the source tables' culture
  rows, copied) and ``land_units_tables`` (every installed land unit on a
  source table, whole, ``man_animation`` repointed), and [AIR-DIVE-W9]
  ``mounts_tables`` (every installed mount on a source table, whole,
  ``animation`` repointed -- a mounted unit's body plays the mount's table),
  each under the installed fragment's GUID;
* ``db\\battle_entities_tables\\ld_air_dive``: EVERY installed flyer the rule
  changes (``air_dive_rules``, ``jump_attack_chance`` 100 included),
  installed row + the rule's cells, unchanged
  cells replayed byte-for-byte. Unlike ld_mod.pack there is no monster lane
  here, so all of them ship in this one fragment;
* ``db\\battle_entity_locomotion_constants_tables\\ld_air_dive``: the two
  ld_flyer_* rows;
* [AIR-DIVE-W15 2026-11-11] ``db\\special_ability_to_invalid_usage_flags_tables\\data__``:
  the whole installed table under its vanilla path minus the rows that stop a
  breath ability in melee or while grounded (``air_dive_rules.breath_usage_writer``;
  a junction row cannot be deleted by key). A mod that ships the same
  data__ wins or loses by load order.

* [AIR-DIVE-W16 2026-11-12] the impact (``air_dive_rules`` IMPACT_STAGE,
  ``--impact-stage`` for the comparison builds): ``melee_weapons_tables``
  (every flyer weapon with a collision attack, a weapon a ground unit also
  carries cloned and the flyer's land unit repointed -- merged into the
  land-unit fragment), the dealt-collision knock thresholds in the
  battle_entities fragment (tuned_cells), and the hidden charge passive
  (seven ability tables, one junction row per installed flyer land unit).

Both fragments are written under the installed fragment's GUID after the
installed table round-trips through our writer schema (installed_db_table),
like the N2 firing-line mini-pack. Conflicts: a mod that ships the same
flyer rows whole (e.g. Workshop 3575054982 overrides 136) wins or loses by
load order; that is stated, not solved.

* [AIR-DIVE-TAKEOFF-W1 2026-11-12] the take-off-from-melee rule scripts
  (``takeoff_entries``: a flyer is held only while more than half of its
  living models are being struck; memreader Plus is a declared prerequisite).
* [AIR-DIVE-MP-DIVE-W1 2026-11-12] the physics dive scripts
  (``dive_rule_entries``: the ground handoff -- slot 104 and, where the table
  has a 484, slot 489 removed, jump_attack_chance 0, no plough clip -- plus
  eight code caves (AIR-DIVE-RELEASE-W1: five of them re-path call sites) so
  a landing flyer keeps its speed and only the bodies it
  hits slow it). Both rules carry their campaign entry, so they run in single
  player and in multiplayer CAMPAIGN battles when every player's game agrees
  (memreader Plus agreement); [FLYER-MP-BATTLE-W1 2026-11-15] multiplayer
  custom / quick / ranked battles run them too, as single player does
  (no agreement exists outside a campaign; lib/ld_cave_common start_battle).

[AIR-DIVE-W4 2026-11-09] ``--probe`` adds the battle movement recorder
``pipelines/air_dive_probe.lua`` as ``script/battle/mod/ld_air_dive_probe.lua``
(writes ld_air_dive_probe.txt next to the game exe, read by
``pipelines/air_dive_probe_report.py``); ``--probe-only`` writes a pack with
the recorder and nothing else, so a vanilla control battle can be recorded
with the dive pack disabled. Both packs carry the script at the same path,
so enabling both loads it once. Never part of ld_mod.pack.

Usage:  python -P tools/pipelines/build_air_dive_minimod.py --out <path.pack>
        [--probe | --probe-only [--takeoff]]
        (deliberately no default: this pack is not part of the mod build)
/ 独立小模组：只含改名动画表（去 104 号槽）与飞兽数据，每次都从安装游戏重新生成。
"""
import os as _ld_os, sys as _ld_sys
_ld_sys.path.insert(0, _ld_os.path.dirname(
    _ld_os.path.dirname(_ld_os.path.abspath(__file__))))
import rolepath

import argparse
import hashlib
import json
import os
from pathlib import Path

import air_dive_rules
import anim_table_rename
import flyer_db as db_writer   # [FLYER-FIX-1117] self-contained: the recorded schemas, not the main mod's writer
from flyer_db import decode_round_trip_with_replay, decode_round_trip
from packfile import PACK_TYPE_MOD, write_pack_file

MOD_DIR = Path(rolepath.__file__).resolve().parent.parent
ASSET_DIR = MOD_DIR / "assets" / "air_dive"
GAME_DIR = Path(os.environ.get(
    "LD_WH3_DATA",
    r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\data"))
FRAGMENT = "ld_air_dive"
PROBE_SOURCE = Path(__file__).resolve().parent / "air_dive_probe.lua"
PROBE_PACK_PATH = "script/battle/mod/ld_air_dive_probe.lua"   # Lua: forward slashes


def probe_entry(variant):
    """The recorder script with its variant tag filled in (fail-closed)."""
    text = PROBE_SOURCE.read_text("utf-8")
    if text.count('"@VARIANT@"') != 1:
        raise SystemExit("[air_dive_minimod] REFUSING: air_dive_probe.lua must "
                         "carry exactly one \"@VARIANT@\" tag")
    return (PROBE_PACK_PATH, text.replace("@VARIANT@", variant).encode("utf-8"))


def anim_entries(asset_dir=ASSET_DIR):
    manifest = json.loads((asset_dir / "air_dive_manifest.json").read_text("utf-8"))
    out = []
    for rec in manifest["files"]:
        data = (asset_dir / rec["staged"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != rec["sha256"]:
            raise SystemExit(f"[air_dive_minimod] REFUSING: {rec['staged']} "
                             "sha256 drift -- re-run pipelines/air_dive.py")
        out.append((rec["pack_path"], data))
    return out, manifest


def db_entries(db_pack):
    rows, header, replay = decode_round_trip_with_replay(
        db_pack, "battle_entities_tables", "air_dive_minimod",
        remedy="before overriding it")
    schema = dict(db_writer.SCHEMAS["battle_entities_tables"])
    schema["guid"] = header["guid"]
    ent = db_writer.DBTableWriter("battle_entities_tables", schema=schema)
    for row, raw in zip(rows, replay):
        cells = air_dive_rules.tuned_cells(row)
        if not cells:
            continue
        new_row, raw = dict(row), dict(raw or {})
        for field, value in cells.items():
            new_row[field] = value
            raw.pop(field, None)
        ent.add_row(new_row, raw_fields=raw)

    loco_rows, loco_header = decode_round_trip(
        db_pack, "battle_entity_locomotion_constants_tables",
        "air_dive_minimod", remedy="before extending it")
    schema = dict(db_writer.SCHEMAS["battle_entity_locomotion_constants_tables"])
    schema["guid"] = loco_header["guid"]
    loco = db_writer.DBTableWriter(
        "battle_entity_locomotion_constants_tables", schema=schema)
    for row in air_dive_rules.flyer_locomotion_rows(loco_rows):
        loco.add_row(row)
    return [
        (f"db\\battle_entities_tables\\{FRAGMENT}", ent.build()),
        (f"db\\battle_entity_locomotion_constants_tables\\{FRAGMENT}",
         loco.build()),
    ], len(ent.rows), len(loco.rows)


def _guid_writer(db_pack, table):
    """A writer for ``table`` under the installed fragment's GUID, after the
    installed fragment round-trips through our schema."""
    import flyer_db as installed_db_table
    _rows, header = installed_db_table.decode_round_trip(
        db_pack, table, "air_dive_minimod", remedy="before extending it")
    schema = dict(db_writer.SCHEMAS[table])
    schema["guid"] = header["guid"]
    return db_writer.DBTableWriter(table, schema=schema)


def rename_entries(db_pack, repoint=None):
    """[AIR-DIVE-W8] The renamed tables' registry, culture, land-unit and
    [AIR-DIVE-W9] mount fragments, and their row counts. [AIR-DIVE-W16]
    ``repoint`` {land unit: cloned weapon} is merged into the land units."""
    records, renames = air_dive_rules.table_renames()
    tag = "air_dive_minimod"
    reg_rows, _unregistered = anim_table_rename.registry_rows(records, db_pack, tag)
    land = anim_table_rename.land_unit_rows(renames, db_pack, tag)
    if repoint:
        land = air_dive_rules.weapon_repointed_land_rows(land, repoint, db_pack, tag)
    out, counts = [], {}
    for table, rows in (
            (anim_table_rename.REGISTRY_TABLE, [(r, None) for r in reg_rows]),
            (anim_table_rename.CULTURE_TABLE,
             [(r, None) for r in anim_table_rename.culture_rows(renames, db_pack, tag)]),
            (anim_table_rename.LAND_TABLE, land),
            (anim_table_rename.MOUNTS_TABLE,
             anim_table_rename.mount_rows(renames, db_pack, tag))):
        if not rows:
            raise SystemExit(f"[air_dive_minimod] REFUSING: no {table} rows "
                             "for the renamed tables")
        w = _guid_writer(db_pack, table)
        for row, raw in rows:
            w.add_row(row, raw_fields=raw)
        out.append((f"db\\{table}\\{FRAGMENT}", w.build()))
        counts[table] = len(rows)
    return out, counts


def impact_entries(db_pack):
    """[AIR-DIVE-W16] The impact fragments for IMPACT_STAGE, the land-unit
    weapon repoint map and the report."""
    tables, repoint, report = air_dive_rules.installed_impact(db_pack, tag="air_dive_minimod")
    out = []
    for table, rows in tables.items():
        w = _guid_writer(db_pack, table)
        for row, raw in rows:
            w.add_row(row, raw_fields=raw or None)
        out.append((f"db\\{table}\\{FRAGMENT}", w.build()))
    return out, repoint, report


# [AIR-DIVE-TAKEOFF-W1 2026-11-12] take-off from melee (user rulings
# 2026-11-12, CONTENT_LEDGER §C8-57 / §C8-58): the battle entry, the pure rule
# module and the generated site table, at the same paths ld_mod.pack ships them
# (both enabled load them once). [AIR-DIVE-MP-DIVE-W1 2026-11-12] and the
# campaign entry, which carries the multiplayer agreement: without it this pack
# alone never got "allowed" in a multiplayer campaign battle (AIR-DIVE-MP-TEST-W1
# found it), so the rule was single-player only. It depends on memreader Plus
# and the rule module only.
# memreader Plus is a declared prerequisite of this pack, not vendored into it:
# ld_mod.pack carries its own pinned copy, and a player of the stand-alone pack
# subscribes to memreader Plus. Without it the battle entry logs "not installed".
# / 近战起飞：四份脚本与主包同路径（含带联机协商的战役入口）；memreader Plus 为
#   本小模组的声明前置。
TAKEOFF_SCRIPTS = (
    "script/battle/mod/ld_flyer_takeoff.lua",
    "script/campaign/mod/ld_flyer_takeoff.lua",
    "script/campaign/lore_disasters/lib/ld_flyer_takeoff.lua",
    "script/campaign/lore_disasters/lib/ld_cave_common.lua",   # shared with the other cave lanes (TEST-REPAIR-1113)
    air_dive_rules.TAKEOFF_SITE_LUA_PATH,
)
# [AIR-DIVE-MP-DIVE-W1 2026-11-12, §C8-61] the physics dive (a landing flyer
# keeps its speed, only the bodies it hits slow it): campaign entry (the
# multiplayer agreement), battle entry, the pure module and the generated
# site table (pipelines/dive_cave_asm.py). Same prerequisite and the same
# multiplayer rules as the take-off.
DIVE_SCRIPTS = (
    "script/battle/mod/ld_flyer_dive.lua",
    "script/campaign/mod/ld_flyer_dive.lua",
    "script/campaign/lore_disasters/lib/ld_flyer_dive.lua",
    # lib/ld_cave_common.lua, which the dive module requires too, ships once in
    # TAKEOFF_SCRIPTS: dive_rule_entries() never ships without takeoff_entries().
    "script/campaign/lore_disasters/data/ld_flyer_dive_site.lua",
)


def takeoff_entries(mod_dir=MOD_DIR, game_dir=GAME_DIR):
    """The take-off scripts (with the shared lib/ld_cave_common); refuses a site table that was not generated
    from the current cave sources, and an installed game that does not hold
    every cave site and field anchor exactly once."""
    import pin_cave_asm
    pin_cave_asm.check_site_file(mod_dir)
    pin_cave_asm.check_exe(Path(game_dir).parent / "Warhammer3.exe")
    out = []
    for rel in TAKEOFF_SCRIPTS:
        disk = mod_dir / rel
        if not disk.is_file():
            raise SystemExit(f"[air_dive_minimod] REFUSING: {disk} missing")
        out.append((rel, disk.read_bytes().replace(b"\r\n", b"\n")))
    return out


def dive_rule_entries(mod_dir=MOD_DIR, game_dir=GAME_DIR):
    """The physics-dive scripts (lib/ld_cave_common ships with the take-off
    scripts); refuses a site table that was not
    generated from the current cave sources, and an installed game whose exe
    does not hold every cave site exactly once with the expected bytes."""
    import dive_cave_asm
    dive_cave_asm.check_site_file(mod_dir)
    dive_cave_asm.check_exe(Path(game_dir).parent / "Warhammer3.exe")
    out = []
    for rel in DIVE_SCRIPTS:
        disk = mod_dir / rel
        if not disk.is_file():
            raise SystemExit(f"[air_dive_minimod] REFUSING: {disk} missing")
        out.append((rel, disk.read_bytes().replace(b"\r\n", b"\n")))
    return out


def usage_entries(game_dir=GAME_DIR):
    """[AIR-DIVE-W15] The breath usage-flag table and the rows it drops."""
    writer, removed, breath = air_dive_rules.breath_usage_writer(
        game_dir / "db.pack", game_dir / "local_en.pack")
    path = (f"db\\{air_dive_rules.USAGE_FLAGS_TABLE}\\"
            f"{air_dive_rules.USAGE_FLAGS_FRAGMENT}")
    return [(path, writer.build())], removed, breath


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--probe", action="store_true",
                      help="also ship the battle movement recorder")
    mode.add_argument("--probe-only", action="store_true",
                      help="ship ONLY the recorder (vanilla control run)")
    ap.add_argument("--takeoff", action="store_true",
                    help="with --probe-only: also ship the take-off rule scripts "
                         "(the A/B arm); the full build always ships them")
    ap.add_argument("--impact-stage", choices=air_dive_rules.IMPACT_STAGES,
                    default=air_dive_rules.IMPACT_STAGE,
                    help="AIR-DIVE-W16 comparison builds (default: the shipped stage)")
    args = ap.parse_args(argv)
    air_dive_rules.IMPACT_STAGE = args.impact_stage
    if args.probe_only:
        extra = takeoff_entries() if args.takeoff else []
        size = write_pack_file(args.out, [probe_entry("probe_only")] + extra,
                               PACK_TYPE_MOD)
        print(f"wrote {args.out} ({size} bytes): movement recorder only"
              + (" + take-off rule scripts" if extra else ""))
        return
    anims, manifest = anim_entries()
    dbs, n_ent, n_loco = db_entries(GAME_DIR / "db.pack")
    impact, repoint, impact_report = impact_entries(GAME_DIR / "db.pack")
    renamed, counts = rename_entries(GAME_DIR / "db.pack", repoint)
    usage, removed, breath = usage_entries()
    extra = [probe_entry("with_dive")] if args.probe else []
    takeoff = takeoff_entries()
    dive = dive_rule_entries()
    size = write_pack_file(args.out, anims + dbs + impact + renamed + usage + takeoff + dive + extra,
                           PACK_TYPE_MOD)
    print(f"wrote {args.out} ({size} bytes): "
          f"{len(manifest['tables_renamed'])} renamed flight tables without slot 104 "
          f"({counts[anim_table_rename.REGISTRY_TABLE]} registry rows, "
          f"{counts[anim_table_rename.CULTURE_TABLE]} culture rows, "
          f"{counts[anim_table_rename.LAND_TABLE]} land units and "
          f"{counts[anim_table_rename.MOUNTS_TABLE]} mounts repointed), "
          f"{len(manifest['plough_clips'])} plough clips (ground handoff ships none), "
          f"{n_ent} flyer entity rows, {n_loco} locomotion rows, "
          f"{len(removed)} melee/grounded rows off "
          f"{len({r['special_ability'] for r in removed})} of {len(breath)} "
          "breath abilities"
          + f", impact stage {args.impact_stage} {impact_report}"
          + f", take-off rule scripts {len(takeoff)}, physics dive scripts {len(dive)}"
          + (", movement recorder" if args.probe else ""))


if __name__ == "__main__":
    main()
