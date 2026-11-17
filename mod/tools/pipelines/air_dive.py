#!/usr/bin/env python3
"""Air dive charge -- the renamed flight tables, without the landing hold. [AIR-DIVE-W1 2026-11-09, W8 / W9 2026-11-10]

User 2026-11-09 (CONTENT_LEDGER §C8-45 item 3): flyers go straight up and
down, charge feebly and hover when chasing; make them descend WHILE they
charge forward and carry on into the enemy, as part of this mod and as a
standalone mini-mod.

WHAT SHIPS [AIR-DIVE-W8 2026-11-10, canary 13]. Two parts, both required:
1. every flight table whose slot 104 FLY_CHARGE_LAND plays a clip-driven
   descent ships RENAMED (see HOW THE TABLES SHIP) with slot 104 REMOVED;
2. ``air_dive_rules.tuned_cells`` sets ``jump_attack_chance`` 100 on every
   flyer entity, so the slot-489 JUMPING_ATTACK clip plays right after
   touchdown;
3. [AIR-DIVE-W9 2026-11-10, canary 15] slot 489 of every renamed table plays
   a from-scratch PLOUGH clip for its skeleton (``pipelines/air_dive_clips.py``:
   one clip per distinct skeleton and strike pose, 34 for the 53 tables;
   peak / travel per size class in ``air_dive_rules.PLOUGH_PROFILES``),
   484 too where vanilla plays the same clip in both, 489 added where vanilla
   has none (``dive_entries``). The clips and their fresh metas ship under
   ``animations/battle/ld_air_dive/plough/``.

WHY (in-game canaries and the battle movement recorder, user-confirmed
2026-11-10; star dragon unless stated):
* touchdown zeroes the entity's speed, and slot 104 holds it there: with the
  renamed tables live, slot 104 does play on landing (canary 8: a
  stand-death clip swapped in showed on touchdown), but the logical position
  moved 0.0 m after touchdown (travel 0.0, t_stop 0.1 s) while the dive
  clip's animroot ran on ~10 m. A slot-104 clip's root motion moves the mesh,
  never the entity, so the W1-W3 dive clips (forward descent, run-out after
  touchdown) could not create momentum;
* only attack slots move the entity after touchdown: 484 (moving attack) and
  489 (JUMPING_ATTACK), whose clip root motion the engine applies;
* canary 9/10 removed slot 104 but kept the vanilla jump chance (~20):
  about 0-5 m after touchdown;
* canary 12 set jump_attack_chance 100 but kept slot 104: 0.0 m;
* both together run on: canary 11b (star dragon only) ran ~24 m after
  touchdown twice, and canary 13 (all 53 tables, all flyers) 24.26 / 24.28 m,
  6.5-10 m into the enemy line (autotest; user-confirmed).
So the W1-W3 dive clips (slot 104), their shifted metas and the run-out
are gone: slot 104 no longer exists in the shipped tables, nothing plays
them. What moves the landed flyer is the slot-489 clip's animroot, so W9
authors that clip (point 3).

Which tables: those whose slot 104 plays at least one land clip whose
``animroot`` descends 1 m or more (MIN_CLIP_DROP) and whose bone 1 does not
cancel that descent -- the 53 tables canary 13 proved. A land clip with no
clip-driven descent (hawks, discs, fly-in-place daemons) or one that moves
the entity under a still mesh (crowmen, burning chariot, the bird04 clips,
the flight-sfsw daemon) leaves its table vanilla, listed under ``skipped``
with the reason; that scope is what was proven, not a claim that those
tables do not hold. Every other slot ships as CA authored it: the table
edit is ``dive_entries`` alone (slot 104 out, slot 489 / 484 to the plough
clip).

Slot 103 FLY_CHARGE_AIR_TO_GROUND is left as CA ships it; the manifest's
``slot_103_census`` records that no vanilla clip played there moves
``animroot`` down (largest |drop| 0.095 m).

HOW THE TABLES SHIP [AIR-DIVE-W8 2026-11-10]. W1-W7 shipped the changed flight
tables as same-named bins in ``@ld_air_dive.animpack``, expecting them to
override vanilla by name. They never did. Seven canary packs (user-confirmed
in game 2026-11-10) tried a same-named bin in our animpack, by-path copies of
``animation_tables.animpack`` and ``animation_tables__.animpack``, a loose
``animations/database/battle/bin/<name>.bin`` and the JSON fragment
``animations/database/battle/fragments/dr1_dragon.txt``: none took effect.
What works is the method of Workshop 3120190274 (storm_dargon_anim) and CBFM's
land_units "animchange" fragment -- ship each changed table under a NEW name
(``<name>_ld_dive``, only the bin header's ``name`` changes), register it,
copy the source table's culture rows, and repoint every land unit on the
source table. Canary 7 (every slot of ``dr1_dragon_ld_dive`` pointed at
``dr1_attack_01``) visibly changed the star dragon. The mechanism lives in
``lib/anim_table_rename.py``; this script emits the renamed bins (loose and in
``ld_air_dive_tables.animpack``) and records the rename map in the manifest's
``tables_renamed``; ``dbw_balance.generate_air_dive_overrides`` and the
mini-mod emit the three DB row sets from it, and every other land-unit emitter
repoints through ``anim_table_rename.repoint``. [AIR-DIVE-W9] A MOUNTED
unit's body plays ``mounts_tables.animation``, not ``man_animation``, so the
mount rows on a source table are repointed as well (``mount_rows``; build_pack
pass 1b2 for vendored mounts).

Outputs (deterministic; ``--check`` re-derives and compares sha256):
    mod/assets/air_dive/animations/database/battle/bin/*_ld_dive.bin  renamed tables (loose)
    mod/assets/air_dive/ld_air_dive_tables.animpack             the same bins, animpacked
    mod/assets/air_dive/animations/battle/ld_air_dive/plough/*  plough clips + metas (W9)
    mod/assets/air_dive/air_dive_manifest.json                 files + measurements
build_pack.collect_air_dive_files() ships the files the manifest names.

Usage:
    python -P tools/pipelines/air_dive.py            # derive and write
    python -P tools/pipelines/air_dive.py --check    # re-derive, compare
/ 空军俯冲：改名的飞行动画表去掉 104 号落地槽，飞兽跳击概率 100，落地后接跳击冲进敌阵。
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

import air_dive_clips
import air_dive_rules
import anim_codec
import anim_meta
import anim_table_bin
import anim_table_rename
from animpack_codec import animpack_build, animpack_iter
from packfile import PackFile

MOD_DIR = Path(rolepath.__file__).resolve().parent.parent
OUT_DIR = MOD_DIR / "assets" / "air_dive"
# [AIR-DIVE-W12] staged donor closures: their land units / mounts ride flight
# tables too (census_riders)
VENDORED_DIR = MOD_DIR / "assets" / "vendored_chars"
MANIFEST = OUT_DIR / "air_dive_manifest.json"
# [AIR-DIVE-W8] a non-vanilla animpack name holding non-vanilla table names:
# vanilla tables cannot be overridden by name (module docstring)
ANIMPACK_NAME = "ld_air_dive_tables.animpack"
TABLE_SUFFIX = "_ld_dive"
ANIMPACK_PACK_PATH = "animations\\database\\battle\\bin\\" + ANIMPACK_NAME
GAME_DATA = Path(os.environ.get(
    "LD_WH3_DATA",
    r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\data"))
ANIM_PACKS = ("anim.pack", "anim2.pack", "anim_3.pack")

SLOT_AIR_TO_GROUND = 103
SLOT_LAND = 104
MIN_CLIP_DROP = 1.0   # metres of animroot descent for a clip to BE the descent
# [AIR-DIVE-W9] the from-scratch plough clips (pipelines/air_dive_clips.py)
SLOT_JUMP = 489
# [AIR-DIVE-MP-DIVE-W1 2026-11-12, §C8-61] shipped design: the ground handoff
# (dive_entries); False only for the old plough comparison builds
GROUND_HANDOFF = True
SLOT_MOVING = 484
# [AIR-DIVE-RELEASE-W1 2026-11-13] a table with no 489 either (dr1b x3) gets
# its moving attack from this slot: CA's own ATTACK_1 clip of the same
# skeleton (CA's precedent: azazel's 484 plays a standing attack clip)
SLOT_ATTACK_1 = 454
CLIP_DIR = "animations/battle/ld_air_dive/plough/"


def _bin_inner(path):
    return path.startswith("animations/database/battle/bin/") and path.endswith(".bin")


def load_installed(data_dir=GAME_DATA):
    """``(bins, clip_reader)``: every battle bin (inner path -> bytes) and a
    function returning one clip's bytes by its lower-case VFS path."""
    bins, clips, packs = {}, {}, []
    for name in ANIM_PACKS:
        pf = PackFile.open(str(Path(data_dir) / name))
        packs.append(pf)
        for e in pf.entries:
            lp = e.path.replace("\\", "/").lower()
            if lp.endswith(".animpack") and "/database/battle/bin/" in lp:
                for ip, blob in animpack_iter(pf.read_file(e)):
                    if not _bin_inner(ip):
                        continue
                    if ip in bins and bins[ip] != blob:
                        raise SystemExit(
                            f"[air_dive] REFUSING: {ip} differs between "
                            "installed animpacks; which one wins is unknown")
                    bins.setdefault(ip, blob)
            elif lp.endswith(".anim") or lp.endswith(".meta"):
                # [AIR-DIVE-W9] .anm.meta too: the plough author reads the
                # source jump attack's events
                clips.setdefault(lp, (pf, e))

    def read_clip(path):
        """One clip's (or ``.anm.meta``'s) bytes by its VFS path."""
        hit = clips.get(path.lower())
        if hit is None:
            raise SystemExit(f"[air_dive] REFUSING: {path} not installed")
        return hit[0].read_file(hit[1])
    return bins, read_clip


def _decode(read_clip, path):
    try:
        return anim_codec.decode(read_clip(path))
    except anim_codec.AnimFormatError as exc:
        return {"error": str(exc)}


def _counter_rooted(clip):
    """True when bone 1 (the visible body under animroot) cancels at least
    half of the animroot's vertical move: the clip moves the ENTITY while
    holding the mesh still (crowmen, burning chariot), so its animroot drop
    is not where the flyer is."""
    name, parent = clip["bones"][1]
    if parent != 0:
        return False
    a = anim_meta.root_track(clip)
    b = [fr[1][0] for fr in clip["frames"]]
    if a is None or any(t is None for t in b):
        return False
    da, db = a[-1][1] - a[0][1], b[-1][1] - b[0][1]
    return da * db < 0 and abs(db) >= 0.5 * abs(da)


def _displacement(clip):
    track = anim_meta.root_track(clip)
    return (track[-1][1] - track[0][1], track[-1][2] - track[0][2])


def _land_clip_verdict(clip):
    """``None`` when the land clip is a clip-driven descent (its table gets
    the dive), else the reason it is not."""
    if "error" in clip:
        return f"undecodable: {clip['error']}"
    if anim_meta.root_track(clip) is None:
        return "bone 0 is not an animated animroot"
    dy0, _dz0 = _displacement(clip)
    if -dy0 < MIN_CLIP_DROP:
        return (f"animroot drop {-dy0:.2f} m < {MIN_CLIP_DROP} m: "
                "the descent is not clip-driven")
    if _counter_rooted(clip):
        return ("bone 1 cancels the animroot descent: the clip moves the "
                "entity under a still mesh")
    return None


def dive_entries(table, plough=None):
    """The renamed table's entries, edited in place.

    [AIR-DIVE-MP-DIVE-W1 2026-11-12, user ruling §C8-61] The shipped design is
    the ground handoff (prototype H of AIR-DIVE-CONTINUOUS-W1, the data the
    physics-dive caves were measured on): slot 104 FLY_CHARGE_LAND removed
    (no landing action), slot 489 JUMPING_ATTACK removed too wherever the
    table has a slot 484 moving attack (the attack picker would otherwise
    start CA's pounce at touchdown), no plough clip -- a landed flyer is left
    to the charge locomotion and the collisions (the code caves in
    lib/ld_flyer_dive.lua keep it moving). ``plough`` is None. Returns
    ``{"slot_104_removed", "slot_489_removed", "slot_484_added",
    "plough_slots": [], "slot_489_added": False}``.

    [AIR-DIVE-RELEASE-W1 2026-11-13] Every renamed table gets a slot 484
    MOVING_ATTACK: 35 of the 50 source tables have none, so a landed flyer
    on them could only pounce (489) once stopped. Where the vanilla table has
    none, 484 is added from CA's own clips of the same skeleton, by CA's own
    convention: the table's 489 jump attack (CA ships exactly that in 484 on
    ``dr1_dragon`` x4 and ``bc2_griffon`` x2 -- same refs, same fields), else
    (no 489: the three ``dr1b`` tables) its ATTACK_1 clip (CA's 484 on
    ``hu6g_wh3_dlc20_azazel_sword`` is a standing attack clip). The source
    entry's fields are copied whole. No vanilla or Workshop table holds a
    moving attack for any of these 35 skeletons (census in §C11
    AIR-DIVE-RELEASE-W1). The added 484 then takes the 489-removal rule above
    like any vanilla 484.

    The plough design below (``plough`` given) is kept for the comparison
    builds; it is no longer shipped. Every slot as CA authored it except

    * slot 104 FLY_CHARGE_LAND, removed (module docstring: it pins the landed
      flyer; the slot-489 jump attack carries it on);
    * [AIR-DIVE-W9] slot 489 JUMPING_ATTACK, its refs replaced by the
      plough clip ``plough`` = {"clip", "meta", "third", "source_slot"}
      (``pipelines/air_dive_clips.py``), and slot 484 too where vanilla plays
      the very same clips in 484 and 489 (the table then has no separate
      moving attack to keep);
    * slot 489 ADDED where the vanilla table has none (dr1b x3, the hu14
      blue scribes), its blend/weight/weapon/unk fields copied from the slot
      the strike pose came from.

    Returns ``{"slot_104_removed", "plough_slots", "slot_489_added"}``.
    """
    removed = [list(r) for e in table["entries"] if e["slot"] == SLOT_LAND
               for r in e["refs"]]
    if not removed:
        raise SystemExit(f"[air_dive] REFUSING: {table['name']} has no slot "
                         f"{SLOT_LAND} to remove")
    if plough is None:
        added_484 = None
        if not any(e["slot"] == SLOT_MOVING for e in table["entries"]):
            src = (next((e for e in table["entries"] if e["slot"] == SLOT_JUMP), None)
                   or next((e for e in table["entries"] if e["slot"] == SLOT_ATTACK_1), None))
            if src is None:
                raise SystemExit(f"[air_dive] REFUSING: {table['name']} has neither slot "
                                 f"{SLOT_JUMP} nor {SLOT_ATTACK_1} to give it a moving attack")
            table["entries"].append(dict(src, slot=SLOT_MOVING, refs=[list(r) for r in src["refs"]]))
            added_484 = {"from_slot": src["slot"], "refs": [list(r) for r in src["refs"]]}
        drop = {SLOT_LAND}
        if any(e["slot"] == SLOT_MOVING for e in table["entries"]):
            drop.add(SLOT_JUMP)
        jump_gone = [list(r) for e in table["entries"] if e["slot"] == SLOT_JUMP and SLOT_JUMP in drop
                     for r in e["refs"]]
        table["entries"] = [e for e in table["entries"] if e["slot"] not in drop]
        return {"slot_104_removed": removed, "slot_489_removed": jump_gone,
                "slot_484_added": added_484, "plough_slots": [], "slot_489_added": False}
    jump = [r[0] for e in table["entries"] if e["slot"] == SLOT_JUMP
            for r in e["refs"]]
    moving = [r[0] for e in table["entries"] if e["slot"] == SLOT_MOVING
              for r in e["refs"]]
    swap = {SLOT_JUMP} | ({SLOT_MOVING} if moving and moving == jump else set())
    ref = [plough["clip"], plough["meta"], plough["third"]]
    table["entries"] = [e for e in table["entries"] if e["slot"] != SLOT_LAND]
    for e in table["entries"]:
        if e["slot"] in swap:
            e["refs"] = [list(ref)]
    added = not jump
    if added:
        src = next((e for e in table["entries"]
                    if e["slot"] == plough["source_slot"]), None)
        if src is None:
            raise SystemExit(f"[air_dive] REFUSING: {table['name']} has no "
                             f"slot {plough['source_slot']} to copy slot "
                             f"{SLOT_JUMP}'s fields from")
        table["entries"].append({
            "slot": SLOT_JUMP, "blend_in": src["blend_in"],
            "weight": src["weight"], "weapon_bools": src["weapon_bools"],
            "unk": src["unk"], "refs": [list(ref)]})
    return {"slot_104_removed": removed, "plough_slots": sorted(swap),
            "slot_489_added": added}


def _tsv_rows(path):
    """Rows of a staged DB TSV (header line, ``#`` metadata line, rows)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"))) for line in lines[2:] if line.strip()]


def body_sizes(db_pack, vendored_dir=VENDORED_DIR):
    """[AIR-DIVE-W13] ``{battle entity: size}`` from the installed
    ``battle_entities`` table, the staged donor closures' same table and
    ``air_dive_rules.GENERATED_ENTITY_SIZES`` (the entities only our
    generator emits). A donor row overriding an installed key wins (the donor
    ships it); fail-closed on a missing required input."""
    import flyer_db as installed_db_table
    rows, _h = installed_db_table.decode_round_trip(db_pack, "battle_entities_tables",
                                                    "air_dive_sizes")
    sizes = {r["key"]: r["size"] for r in rows}
    found = sorted(Path(vendored_dir).glob("*/tsv/db/battle_entities_tables/*.tsv"))
    if not found:
        raise SystemExit(f"[air_dive] REFUSING: no staged donor battle_entities "
                         f"under {vendored_dir}")
    for path in found:
        sizes.update((r["key"], r["size"]) for r in _tsv_rows(path))
    sizes.update(air_dive_rules.GENERATED_ENTITY_SIZES)
    return sizes


def census_riders(sources, data_dir=GAME_DATA, vendored_dir=VENDORED_DIR):
    """[AIR-DIVE-W12] ``({source table: {flyer entity: plough speed}},
    {source table: [non-flyer entity]}, {flyer entity: size})`` over every row that plays one of
    ``sources``: installed land units (``man_animation`` / ``man_entity``) and
    mounts (``animation`` / ``entity``), the staged donor closures' same two
    tables, and ``air_dive_rules.GENERATED_RIDERS``. A flyer is an entity with
    a ``FLYER_CHARGE_SPEEDS`` row (the table is the coverage list of every
    shipping flyer); the rest ride a flight table without ever flying
    (measured 2026-11-11: the two varghulf units on ``hu8b_varghulf``) and are
    reported, not repointed. [AIR-DIVE-W13] The plough speed is
    ``air_dive_rules.plough_speed(charge speed, body size)``; a flyer whose
    size no source carries is a refusal. Fail-closed on a missing required
    input."""
    import flyer_db as installed_db_table
    db_pack = Path(data_dir) / "db.pack"
    if not db_pack.is_file():
        raise SystemExit(f"[air_dive] REFUSING: {db_pack} missing")
    pairs = []
    for table, col, ecol in (("land_units_tables", "man_animation", "man_entity"),
                             ("mounts_tables", "animation", "entity")):
        rows, _h = installed_db_table.decode_round_trip(db_pack, table, "air_dive_census")
        pairs += [(r[col], r[ecol]) for r in rows]
        found = sorted(Path(vendored_dir).glob(f"*/tsv/db/{table}/*.tsv"))
        if not found:
            raise SystemExit(f"[air_dive] REFUSING: no staged donor {table} "
                             f"under {vendored_dir}")
        for path in found:
            pairs += [(r[col], r[ecol]) for r in _tsv_rows(path)]
    pairs += list(air_dive_rules.GENERATED_RIDERS)
    sizes = body_sizes(db_pack, vendored_dir)
    flyers, grounded, flyer_sizes = {}, {}, {}
    for src, ent in pairs:
        if src not in sources:
            continue
        if ent in air_dive_rules.FLYER_CHARGE_SPEEDS:
            if ent not in sizes:
                raise SystemExit(f"[air_dive] REFUSING: flyer {ent} on {src} has "
                                 "no battle_entities size in any source")
            flyer_sizes[ent] = sizes[ent]
            flyers.setdefault(src, {})[ent] = air_dive_rules.plough_speed(
                air_dive_rules.charge_speed(ent)[0], sizes[ent])
        elif ent not in grounded.setdefault(src, []):
            grounded[src].append(ent)
    # a non-flyer matters only on a table that gets copies (it keeps the
    # source table there); on a table no flyer rides nothing is renamed
    return (flyers, {k: sorted(v) for k, v in grounded.items() if v and k in flyers},
            flyer_sizes)


def variants(riders):
    """[AIR-DIVE-W12] ``[(suffix, speed, [entities])]`` for one source table:
    one renamed copy per plough speed (AIR-DIVE-W13) among its riders, ``_ld_dive`` when
    they all share one speed, else ``_ld_dive_v<tenths>`` each."""
    by_speed = {}
    for ent, speed in riders.items():
        by_speed.setdefault(speed, []).append(ent)
    if len(by_speed) == 1:
        (speed, ents), = by_speed.items()
        return [(TABLE_SUFFIX, speed, sorted(ents))]
    return [(f"{TABLE_SUFFIX}_{air_dive_rules.speed_tag(s)}", s, sorted(e))
            for s, e in sorted(by_speed.items())]


def author_ploughs(jobs, flight, read_clip, files):
    """One plough clip per distinct (skeleton, strike ref, speed) over the
    renamed copies, written into ``files``; returns
    ``({renamed name: plough}, [clip report])``. ``jobs`` is
    ``[(source bin, renamed name, speed)]``.

    [AIR-DIVE-W9] Walked in RENAMED-name order so a clip name clash (two
    strike refs with one file stem) always suffixes the same table.
    ``flight[ip]`` must still be the vanilla table: the author reads its
    slot-104 land pose. [AIR-DIVE-W12] The clip peaks at the copy's charge
    speed; its name carries the speed tag."""
    authored, reports, ploughs = {}, {}, {}
    for ip, renamed, speed in sorted(jobs, key=lambda j: j[1]):
        van = flight[ip]
        sref, sslot, _tried = air_dive_clips.pick_strike(read_clip, van)
        key = (van["skeleton"], tuple(sref), speed)
        if key not in authored:
            clip, meta, rep = air_dive_clips.author(read_clip, van, sref, speed)
            base = sref[0].split("/")[-1][:-len(".anim")]
            tag = air_dive_rules.speed_tag(speed)
            stem = f"{base}_{tag}"
            if stem in reports:
                stem = f"{base}_{van['name']}_{tag}"
            if stem in reports:
                raise SystemExit(f"[air_dive] REFUSING: plough clip name "
                                 f"clash {stem}")
            cpath = f"{CLIP_DIR}{stem}_ld_plough.anim"
            mpath = f"{CLIP_DIR}{stem}_ld_plough.anm.meta"
            files[cpath], files[mpath] = clip, meta
            authored[key] = (cpath, mpath)
            reports[stem] = {
                "clip": cpath, "meta": mpath, "skeleton": rep["skeleton"],
                "class": rep["class"], "speed": speed, "strike": list(sref),
                "strike_slot": sslot, "duration_s": rep["duration_s"],
                "travel_m": rep["travel_m"], "peak_mps": rep["peak_mps"],
                "impact_t": rep["impact_t"], "poses": rep["poses"],
                "missing_poses": rep["missing_poses"],
                "meta_events": rep["meta"]["events"],
                "splash_donor": rep["meta"]["splash_donor"], "tables": []}
        cpath, mpath = authored[key]
        stem = cpath[len(CLIP_DIR):-len("_ld_plough.anim")]
        reports[stem]["tables"].append(renamed)
        ploughs[renamed] = {"clip": cpath, "meta": mpath, "third": sref[2],
                            "source_slot": sslot}
    return ploughs, [dict(r, stem=k) for k, r in sorted(reports.items())]


def derive(data_dir=GAME_DATA):
    """Everything this lane ships, in memory: ``(files, manifest)``.

    ``files`` maps a staged relative path to bytes.
    """
    bins, read_clip = load_installed(data_dir)
    vanilla_names, flight = set(), {}
    for ip in sorted(bins):
        try:
            table = anim_table_bin.parse(bins[ip])
        except anim_table_bin.BinFormatError:
            continue
        vanilla_names.add(table["name"])
        slots = {e["slot"] for e in table["entries"]}
        if SLOT_LAND in slots:
            flight[ip] = table
    land_users = {}
    for ip, table in flight.items():
        for e in table["entries"]:
            if e["slot"] == SLOT_LAND:
                for r in e["refs"]:
                    land_users.setdefault(r[0].lower(), set()).add(ip)

    # slot 103: measure, never change (see the module docstring)
    s103 = {r[0].lower() for t in flight.values() for e in t["entries"]
            if e["slot"] == SLOT_AIR_TO_GROUND for r in e["refs"]}
    worst_103, undecoded_103 = 0.0, []
    for key in sorted(s103):
        clip = _decode(read_clip, key)
        if "error" in clip or anim_meta.root_track(clip) is None:
            undecoded_103.append(key)
            continue
        worst_103 = max(worst_103, abs(_displacement(clip)[0]))

    land_clips, skipped, dive_tables = [], [], set()
    for key in sorted(land_users):
        clip = _decode(read_clip, key)
        users = sorted(land_users[key])
        reason = _land_clip_verdict(clip)
        if reason is not None:
            skipped.append({"clip": key, "tables": users, "reason": reason})
            continue
        land_clips.append({"clip": key, "skeleton": clip["skeleton"],
                           "tables": users,
                           "animroot_drop_m": round(-_displacement(clip)[0], 3)})
        dive_tables.update(users)

    # [AIR-DIVE-W12] who rides each table: one renamed copy per charge
    # speed among its flying riders; a table no flyer rides is not renamed
    by_name = {flight[ip]["name"]: ip for ip in dive_tables}
    riders, grounded, sizes = census_riders(set(by_name), data_dir)
    unridden = sorted(set(by_name) - set(riders))
    jobs = []
    for name in sorted(riders):
        for suffix, speed, ents in variants(riders[name]):
            jobs.append((by_name[name], name + suffix, speed, ents, suffix))

    # [AIR-DIVE-W8] each changed table ships under a NEW name (loose bin +
    # animpack); vanilla tables cannot be overridden by name (docstring)
    files, entries, bins_out = {}, [], []
    # [AIR-DIVE-W9] the plough clips, authored before any table is edited --
    # [AIR-DIVE-MP-DIVE-W1] only in the plough design; the shipped ground
    # handoff authors none (dive_entries)
    if GROUND_HANDOFF:
        ploughs, clip_reports = {renamed: None for _ip, renamed, _sp, _e, _s in jobs}, []
    else:
        ploughs, clip_reports = author_ploughs(
            [(ip, renamed, speed) for ip, renamed, speed, _e, _s in jobs],
            flight, read_clip, files)
    for ip, renamed, speed, ents, suffix in jobs:
        table = anim_table_bin.parse(anim_table_bin.write(flight[ip]))
        edit = dive_entries(table, ploughs[renamed])
        rec, blob = anim_table_rename.rename_bin(
            ip, anim_table_bin.write(table), suffix, ents)
        if rec["renamed"] in vanilla_names:
            raise SystemExit(f"[air_dive] REFUSING: {rec['renamed']} is "
                             "already a vanilla table name")
        entries.append((rec["bin"], blob))
        files[rec["bin"]] = blob
        bins_out.append(dict(rec, source_bin=ip, speed=speed,
                             body_sizes={e: sizes[e] for e in ents}, **edit))
    files[ANIMPACK_NAME] = animpack_build(entries)

    manifest = {
        "generator": "tools/pipelines/air_dive.py",
        "rule": {"min_clip_drop_m": MIN_CLIP_DROP,
                 "slot_104": "removed from every renamed table",
                 "slot_484": ("CA's own where the vanilla table has one; otherwise added from "
                              "the table's 489 jump attack, else its 454 ATTACK_1 (CA's own "
                              "clips, AIR-DIVE-RELEASE-W1)") if GROUND_HANDOFF else "as CA authored",
                 "slot_489": (("removed where the table has a 484 moving attack (every table "
                               "since AIR-DIVE-RELEASE-W1); no plough clip (AIR-DIVE-MP-DIVE-W1 "
                               "ground handoff)") if GROUND_HANDOFF else
                              ("the skeleton's plough clip (air_dive_clips); "
                               "484 too where vanilla plays the same clips; "
                               "added where vanilla has no 489")),
                 "jump_attack_chance": (f"{air_dive_rules.JUMP_ATTACK_CHANCE} on every flyer "
                                        "(air_dive_rules)"),
                 "copies": ("one renamed copy per plough speed among a table's "
                            "flying riders; the plough clip peaks at that speed "
                            "(AIR-DIVE-W12); plough speed = charge speed x "
                            "body-size multiplier, cap 20 (AIR-DIVE-W13)"),
                 "slot_103": "unchanged (no vanilla clip carries descent there)"},
        "flight_tables": len(flight),
        "slot_103_census": {"clips": len(s103),
                            "max_abs_animroot_drop_m": round(worst_103, 3),
                            "not_measured": undecoded_103},
        "tables_renamed": bins_out,
        "unridden_tables": unridden,
        "grounded_riders": grounded,
        "plough_clips": clip_reports,
        "land_clips": land_clips,
        "skipped": skipped,
        "files": [
            {"staged": rel, "pack_path": _pack_path(rel),
             "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for rel, data in sorted(files.items())],
    }
    return files, manifest


def _pack_path(rel):
    if rel == ANIMPACK_NAME:
        return ANIMPACK_PACK_PATH
    return rel.replace("/", "\\")


def write(files, manifest, out_dir=OUT_DIR):
    """Write the staged files and manifest; [AIR-DIVE-W12] a file under
    ``out_dir`` the derivation no longer produces (a renamed copy or plough
    clip of an earlier naming) is removed -- the directory is this
    pipeline's alone."""
    out_dir = Path(out_dir)
    keep = {(out_dir / rel).resolve() for rel in files} | {(out_dir / MANIFEST.name).resolve()}
    if out_dir.is_dir():
        for path in sorted(out_dir.rglob("*")):
            if path.is_file() and path.resolve() not in keep:
                path.unlink()
    for rel, data in files.items():
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
    text = json.dumps(manifest, indent=1, ensure_ascii=False) + "\n"
    (out_dir / MANIFEST.name).write_text(text, encoding="utf-8", newline="\n")


def check(out_dir=OUT_DIR):
    """Re-derive and compare with the committed manifest and files."""
    files, manifest = derive()
    committed = json.loads((Path(out_dir) / MANIFEST.name).read_text("utf-8"))
    if committed != manifest:
        raise SystemExit("[air_dive] STALE: manifest differs from a fresh "
                         "derivation -- re-run tools/pipelines/air_dive.py")
    for rec in manifest["files"]:
        data = (Path(out_dir) / rec["staged"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != rec["sha256"]:
            raise SystemExit(f"[air_dive] STALE: {rec['staged']} sha256 drift")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        m = check()
        print(f"[air_dive] OK: {len(m['tables_renamed'])} renamed tables "
              f"without slot 104, {len(m['plough_clips'])} plough clips, "
              "matches a fresh derivation")
        return
    files, manifest = derive()
    write(files, manifest)
    print(f"[air_dive] {manifest['flight_tables']} flying tables, "
          f"{len(manifest['land_clips'])} clip-driven land clips, "
          f"{len(manifest['tables_renamed'])} tables renamed without slot 104, "
          f"{len(manifest['plough_clips'])} plough clips in slot 489, "
          f"{len(manifest['skipped'])} land clips skipped")


if __name__ == "__main__":
    main()
