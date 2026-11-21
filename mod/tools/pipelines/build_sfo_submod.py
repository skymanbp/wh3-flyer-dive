"""[D56 / D57] Build the SFO submod ``!flyer_dive_takeoff_sfo.pack``.

Why: the main pack re-ships whole vanilla rows (DB merge is whole-row replacement), so with SFO: Grimhammer III
(Workshop 2792731173) its flyer rows put SFO's health, stats and weapons back to vanilla
(docs/research/2026-11-21-sfo-compat.md). This pack carries the same rows built on SFO's instead.

How: the main build's own code (build_air_dive_minimod: entity rule, impact weapons, animation-table repoint) runs
with the four tables of air_dive_rules.SFO_TABLES read as vanilla with SFO's rows laid over them (flyer_db.overlay;
SFO's row replaces vanilla's by key, SFO's new keys follow), and the entity rule leaves
air_dive_rules.SFO_KEEP_ENTITY_COLUMNS as SFO has them. Inside SFO the fragment whose name sorts first wins a key
(the measured rule, HISTORY; SFO's three names sort the same plainly and case-blind).

Shipped, per table: every key SFO defines that the main pack ships or this build changes (the built row, or SFO's
own row when this build leaves it as SFO has it: the main pack's row must still be beaten), plus the ``_dive``
weapon clones whose source weapon SFO defines. Nothing else: animation tables, scripts and all other rows are the
main pack's, so the submod needs SFO and the main pack. Fragment and pack names start with ``!`` so they sort
before SFO's and the main pack's (D57).

usage: python -P tools/pipelines/build_sfo_submod.py --sfo <sfo_grimhammer_3_main.pack> --main <flyer_dive_takeoff.pack>
           --out <dir>/!flyer_dive_takeoff_sfo.pack
"""
import os as _boot_os, sys as _boot_sys
_boot_sys.path.insert(0, _boot_os.path.dirname(_boot_os.path.dirname(_boot_os.path.abspath(__file__))))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path

import argparse  # noqa: E402 -- after the path setup above
import json  # noqa: E402 -- same reason
from pathlib import Path  # noqa: E402 -- same reason

import air_dive_rules  # noqa: E402 -- same reason
import anim_table_bin  # noqa: E402 -- same reason
import anim_table_rename  # noqa: E402 -- same reason
import build_air_dive_minimod as main_build  # noqa: E402 -- same reason
import flyer_db  # noqa: E402 -- same reason
from packfile import PACK_TYPE_MOD, PackFile, write_pack_file  # noqa: E402 -- same reason

SUB_PACK_NAME = "!flyer_dive_takeoff_sfo.pack"
FRAGMENT = "!flyer_dive_takeoff_sfo"
SFO_PACK_NAME = "sfo_grimhammer_3_main.pack"
CLONE_SUFFIX = air_dive_rules.WEAPON_CLONE_SUFFIX
TAG = "sfo_submod"


def fragments(pack_path, table):
    """[(fragment name, bytes)] of ``db/<table>/*`` in a pack, in the order that decides which row wins: the name
    that sorts first, case-blind (the plain order is checked to agree, else refused)."""
    with PackFile.open(str(pack_path)) as pack:
        found = []
        for e in pack.entries:
            parts = e.path.replace("/", "\\").split("\\")
            if len(parts) == 3 and parts[0].lower() == "db" and parts[1].lower() == table:
                found.append((parts[2], pack.read_file(e)))
    blind = sorted(found, key=lambda f: f[0].lower())
    if [n for n, _ in blind] != [n for n, _ in sorted(found, key=lambda f: f[0])]:
        raise SystemExit(f"[{TAG}] REFUSING: {pack_path} {table}: plain and case-blind name orders differ "
                         f"({[n for n, _ in found]}); which fragment wins is not settled")
    return blind


def decoded(table, name, data):
    """[(row, cells to replay)] of one fragment, decoded with our schema."""
    rows, raw = flyer_db._decode_db_table_bytes(data, table, name, capture_raw=True)
    fields = flyer_db.SCHEMAS[table]["fields"]
    return [(r, flyer_db._lossy_cells(table, TAG, r, rr, fields)) for r, rr in zip(rows, raw)]


def sfo_rows(sfo_pack, table):
    """{key: (row, replay)} SFO gives that table (first-sorting fragment wins), and the keys in that order."""
    out, order = {}, []
    for name, data in fragments(sfo_pack, table):
        for row, replay in decoded(table, f"{Path(sfo_pack).name}:{name}", data):
            if row["key"] not in out:
                out[row["key"]] = (row, replay)
                order.append(row["key"])
    if not out:
        raise SystemExit(f"[{TAG}] REFUSING: {sfo_pack} carries no {table} rows")
    return out, order


def merged_table(db_pack, sfo, order, table):
    """Bytes of vanilla's ``table`` with SFO's rows laid over it, under vanilla's GUID."""
    rows, header, replay = flyer_db.decode_round_trip_with_replay(db_pack, table, TAG)
    schema = dict(flyer_db.SCHEMAS[table])
    schema["guid"] = header["guid"]
    w = flyer_db.DBTableWriter(table, schema=schema)
    seen = set()
    for row, rp in zip(rows, replay):
        k = row["key"]
        if k in sfo:
            w.add_row(*sfo[k])
            seen.add(k)
        else:
            w.add_row(row, raw_fields=rp)
    for k in order:
        if k not in seen:
            w.add_row(*sfo[k])
    return w.build(), header["guid"]


def unserved(sfo):
    """{key}: SFO land units / mounts on a renamed flight table whose body no renamed copy serves (a body SFO
    added: the copies are per body), and riders SFO moved off the rider table their copy was made from. They keep
    SFO's own table: no dive animation, the memory-level rules still apply."""
    _records, renames = air_dive_rules.table_renames()
    out = set()
    for table, column, entity in (("land_units_tables", "man_animation", "man_entity"),
                                  ("mounts_tables", "animation", "entity")):
        for k, (row, _r) in sfo[table].items():
            if row.get(column) in renames:
                try:
                    anim_table_rename.repoint(row[column], renames, row[entity])
                except anim_table_rename.Refused:
                    out.add(k)
    # riders: the rider copy was made from one rider table; a unit SFO moved to another keeps SFO's
    _r_records, rider_units, _r_renames = air_dive_rules.rider_renames()
    for k, (src, _copy) in rider_units.items():
        row = sfo["land_units_tables"].get(k)
        if row is not None and row[0]["man_animation"] != src:
            out.add(k)
    return out


def _blanked_bin(pack, rec, names):
    """A copy's parsed table with every copy name blanked, for comparison."""
    entry = next(e for e in pack.entries if e.path.replace("\\", "/").lower() == rec["bin"].lower())
    text = json.dumps(anim_table_bin.parse(pack.read_file(entry)),
                      default=lambda o: o.hex() if isinstance(o, bytes) else str(o))
    for n in sorted(names, key=len, reverse=True):
        text = text.replace(n, "<NAME>")
    return text


def serve_unserved(sfo, skip, built, db_pack, main_pack):
    """Give the units / mounts unserved() left out the copy the main pack gives the same key's vanilla body
    (riders: the rider copy of SFO's table whose mount copy s1 is their own's). Allowed only because the per-body
    copies of one table are the same table under another name (0 plough clips ship): proved here from the main
    pack's bins, a difference is a refusal. Returns ({table: {key: (row, replay)}}, keys still unserved)."""
    records, renames = air_dive_rules.table_renames()
    r_records, r_units, _r_renames = air_dive_rules.rider_renames()
    by_name = {r["renamed"]: r for r in records + r_records}
    out = {"land_units_tables": {}, "mounts_tables": {}}
    left = []
    with PackFile.open(str(main_pack)) as pack:
        for table, column, entity in (("land_units_tables", "man_animation", "man_entity"),
                                      ("mounts_tables", "animation", "entity")):
            vanilla = {r["key"]: r for r in flyer_db.decode_round_trip_with_replay(db_pack, table, TAG)[0]}
            for k in sorted(skip):
                if k not in sfo[table]:
                    continue
                row, replay = built.get(table, {}).get(k) or sfo[table][k]
                src, new, same = row[column], None, []
                if table == "land_units_tables" and k in r_units:
                    own_s1 = by_name[r_units[k][1]]["s1"]
                    same = sorted(r["renamed"] for r in r_records if r["source"] == src and r["s1"] == own_s1)
                    new = same[0] if same else None
                elif isinstance(renames.get(src), dict):
                    v = vanilla.get(k)
                    if v is not None and v[column] == src:
                        new = renames[src].get(v[entity])
                    same = sorted(set(renames[src].values()) - {src})
                if new is None:
                    left.append(k)
                    continue
                if len(same) > 1:
                    blanks = {_blanked_bin(pack, by_name[c], same) for c in same}
                    if len(blanks) != 1:
                        raise SystemExit(f"[{TAG}] REFUSING: {k}: the copies of {src} differ ({same}); a body "
                                         "no copy serves cannot borrow one")
                row, replay = dict(row), dict(replay or {})
                row[column] = new
                replay.pop(column, None)
                out[table][k] = (row, replay or None)
    return out, left


def main_pack_keys(main_pack, table):
    keys = set()
    for name, data in fragments(main_pack, table):
        keys |= {r["key"] for r, _ in decoded(table, f"{Path(main_pack).name}:{name}", data)}
    return keys


def built_rows(entries, table):
    """{key: (row, replay)} of every built fragment of ``table``; a key built twice is refused."""
    out = {}
    for path, data in entries:
        parts = path.replace("/", "\\").split("\\")
        if len(parts) == 3 and parts[1] == table:
            for row, replay in decoded(table, path, data):
                if row["key"] in out:
                    raise SystemExit(f"[{TAG}] REFUSING: {table} {row['key']} built twice")
                out[row["key"]] = (row, replay)
    return out


def submod_entries(sfo_pack, main_pack, db_pack=None):
    """``(entries, report)``: the submod's fragments and per-table counts."""
    db_pack = main_build.GAME_DIR / "db.pack" if db_pack is None else Path(db_pack)
    sfo, overlay, guids = {}, {}, {}
    for table in air_dive_rules.SFO_TABLES:
        rows, order = sfo_rows(sfo_pack, table)
        sfo[table] = rows
        overlay[table], guids[table] = merged_table(db_pack, rows, order, table)
    skip = unserved(sfo)
    with flyer_db.overlay(overlay):
        dbs, _n_ent, _n_loco = main_build.db_entries(db_pack, keep=air_dive_rules.SFO_KEEP_ENTITY_COLUMNS)
        impact, repoint, _report = main_build.impact_entries(db_pack)
        renamed, _counts = main_build.rename_entries(db_pack, repoint, skip)
    built_entries = dbs + impact + renamed
    built_all = {t: built_rows(built_entries, t) for t in air_dive_rules.SFO_TABLES}
    served, left = serve_unserved(sfo, skip, built_all, db_pack, main_pack)
    for t, rows in served.items():
        built_all[t].update(rows)
    entries, report = [], {}
    for table in air_dive_rules.SFO_TABLES:
        built = built_all[table]
        ship_keys = (main_pack_keys(main_pack, table) | set(built)) & set(sfo[table])
        clones = {k for k in built if k.endswith(CLONE_SUFFIX) and k[:-len(CLONE_SUFFIX)] in sfo[table]
                  and k not in sfo[table]}
        schema = dict(flyer_db.SCHEMAS[table])
        schema["guid"] = guids[table]
        w = flyer_db.DBTableWriter(table, schema=schema)
        changed = 0
        for k in sorted(ship_keys | clones):
            row, replay = built.get(k) or sfo[table][k]
            if k in built and (k in clones or built[k][0] != sfo[table][k][0]):
                changed += 1
            w.add_row(row, raw_fields=replay)
        if w.rows:
            entries.append((f"db\\{table}\\{FRAGMENT}", w.build()))
        report[table] = {"shipped": len(w.rows), "changed_from_sfo": changed, "clones": len(clones),
                         "sfo_keys": len(sfo[table])}
    report["borrowed_copy"] = sorted(k for rows in served.values() for k in rows)
    report["no_dive_animation"] = sorted(set(left))
    return entries, report


# columns each table's shipped rows must hold exactly as SFO has them (D56: SFO's numbers stay)
SFO_HELD = {"land_units_tables": ("bonus_hit_points", "melee_attack", "melee_defence", "charge_bonus", "armour",
                                  "morale", "attribute_group", "rank_depth"),
            "battle_entities_tables": ("hit_points", "fly_speed", "run_speed", "charge_speed")
            + tuple(air_dive_rules.SFO_KEEP_ENTITY_COLUMNS),
            "mounts_tables": ("entity",),
            "melee_weapons_tables": ("damage", "ap_damage", "bonus_v_large", "splash_attack_max_attacks")}


def check_pack(out, sfo_pack, main_pack):
    """Problems of a built submod (empty = good), read back from its bytes: names sort before SFO's and the main
    pack's (plainly and case-blind); every row is SFO's key (or a clone of SFO's weapon); SFO_HELD cells equal
    SFO's; every land unit / mount the main pack also ships names the same animation table the main pack does
    unless SFO moved it; a land unit that does not take the main pack's weapon clone keeps an SFO weapon that already
    has a collision attack."""
    problems, weapons = [], None
    names = [Path(out).name, Path(sfo_pack).name, Path(main_pack).name]
    for key in (str, str.lower):
        if min(names, key=key) != names[0]:
            problems.append(f"pack name {names[0]} does not sort first ({key.__name__})")
    for table in air_dive_rules.SFO_TABLES:
        frag = fragments(out, table)
        if not frag:
            problems.append(f"{table}: no fragment")
            continue
        other = [n for n, _ in fragments(sfo_pack, table) + fragments(main_pack, table)]
        for key in (str, str.lower):
            if any(key(frag[0][0]) >= key(n) for n in other):
                problems.append(f"{table}: fragment {frag[0][0]} does not sort before {other}")
        sfo, _order = sfo_rows(sfo_pack, table)
        main = {}
        for name, data in fragments(main_pack, table):
            main.update({r["key"]: r for r, _ in decoded(table, name, data)})
        for name, data in frag:
            for row, _ in decoded(table, name, data):
                k = row["key"]
                base = sfo.get(k) or sfo.get(k[:-len(CLONE_SUFFIX)] if k.endswith(CLONE_SUFFIX) else None)
                if base is None:
                    problems.append(f"{table} {k}: not an SFO key or a clone of one")
                    continue
                for col in SFO_HELD[table]:
                    if row[col] != base[0][col]:
                        problems.append(f"{table} {k}.{col}: {row[col]!r}, SFO has {base[0][col]!r}")
                m = main.get(k)
                if table in ("land_units_tables", "mounts_tables") and m is not None:
                    col, ent = ("man_animation", "man_entity") if table == "land_units_tables" else ("animation",
                                                                                                     "entity")
                    if base[0][col] == _vanilla_cell(table, k, col) and row[col] != m[col]:
                        problems.append(f"{table} {k}.{col}: {row[col]!r}, the main pack has {m[col]!r}")
                if table == "land_units_tables" and m is not None and m["primary_melee_weapon"].endswith(
                        CLONE_SUFFIX) and row["primary_melee_weapon"] != m["primary_melee_weapon"]:
                    # the main pack clones a weapon only to give it a collision attack; on SFO's data the unit
                    # may keep its own weapon only if SFO's already has one (SFO's numbers stay, D56)
                    if weapons is None:   # the submod's own weapon rows first (its clones), then SFO's
                        weapons = {k: r for k, (r, _x) in sfo_rows(sfo_pack, "melee_weapons_tables")[0].items()}
                        for wname, wdata in fragments(out, "melee_weapons_tables"):
                            weapons.update({r["key"]: r for r, _ in decoded("melee_weapons_tables", wname, wdata)})
                    w = weapons.get(row["primary_melee_weapon"])
                    if w is None or int(w["collision_attack_max_targets"]) <= 0:
                        problems.append(f"{table} {k}: weapon {row['primary_melee_weapon']!r} has no collision "
                                        f"attack (submod or SFO), the main pack gives {m['primary_melee_weapon']!r}")
    return problems


_VANILLA = {}


def _vanilla_cell(table, key, col):
    if table not in _VANILLA:
        rows = flyer_db.decode_round_trip_with_replay(main_build.GAME_DIR / "db.pack", table, TAG)[0]
        _VANILLA[table] = {r["key"]: r for r in rows}
    row = _VANILLA[table].get(key)
    return None if row is None else row[col]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sfo", required=True, help=f"SFO's {SFO_PACK_NAME}")
    ap.add_argument("--main", required=True, help=f"the built {main_build.MAIN_PACK_NAME} it pairs with")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if Path(args.out).name != SUB_PACK_NAME:
        raise SystemExit(f"[{TAG}] REFUSING: {args.out} must be named {SUB_PACK_NAME} (D57: it must sort first)")
    if Path(args.sfo).name != SFO_PACK_NAME or Path(args.main).name != main_build.MAIN_PACK_NAME:
        raise SystemExit(f"[{TAG}] REFUSING: --sfo must be {SFO_PACK_NAME}, --main {main_build.MAIN_PACK_NAME}")
    entries, report = submod_entries(args.sfo, args.main)
    size = write_pack_file(args.out, entries, PACK_TYPE_MOD)
    problems = check_pack(args.out, args.sfo, args.main)
    if problems:
        Path(args.out).unlink()
        raise SystemExit(f"[{TAG}] REFUSING (pack removed): {len(problems)} problems: {problems[:20]}")
    print(f"wrote {args.out} ({size} bytes), read back and checked: {report}")


if __name__ == "__main__":
    main()
