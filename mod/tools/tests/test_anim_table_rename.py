"""AIR-DIVE-W8 (2026-11-10): no shipped battle bin may reuse a vanilla table name.

WHAT WOULD GO WRONG WITHOUT THIS. W1-W7 shipped the air dive's changed flight
tables as same-named bins in the W1-W7 builds' own animpack, believing a mod bin
overrides the vanilla table of the same name. It does not: seven in-game
canaries (user-confirmed 2026-11-10) showed the vanilla table keep playing for
a same-named bin in our animpack, by-path copies of the vanilla table
animpacks, a loose bin and the JSON fragment. Every probe, measurement and
user report of those seven lanes was therefore about CA's clips, not ours, and
nothing in the build could tell. The working method (lib/anim_table_rename.py)
ships the changed table under a NEW name, registers it, copies its culture
rows and repoints the land units.

These checks pin that:
* no battle bin under mod/assets (loose or inside an animpack) carries a vanilla table's name, by path stem or header ``name``;
* the air-dive manifest's renamed tables are new names of vanilla tables,
  each bin's header names it, and the bin ships loose and animpacked;
* the pack's emitter ships every installed land unit and mount on a renamed
  table, repointed to the copy serving its entity (PackRepointsRiders);
* the culture_to_battle_animation_tables schema round-trips the installed
  fragment byte for byte (the pack writes it);
* the TSV repoint touches only man_animation and keeps line endings;
* [canary 13] no renamed table carries slot 104 FLY_CHARGE_LAND (it pins the
  landed flyer) and the flyer rule sets jump_attack_chance (100 at W8, 0 since
  AIR-DIVE-MP-DIVE-W1, §C8-61) unless an
  author declared the column -- the two parts are only effective together;
* [AIR-DIVE-W9, canary 15] every renamed table's slot 489 played a plough
  clip; [AIR-DIVE-MP-DIVE-W1, §C8-61] the shipped design is the ground
  handoff instead: no clip is staged, slot 489 is gone where the table has a
  slot-484 moving attack and is CA's own otherwise;
* [AIR-DIVE-W9] mounted units: their body plays mounts_tables.animation, so
  every emitter of mount rows repoints through the helper too, and the
  mounts_tables writer schema round-trips the installed fragment.
* [AIR-DIVE-W12] one copy per charge speed: a source whose riders charge at
  different speeds ships one copy per speed, each serving named entities;
  the repoint picks the copy by the row's entity and refuses one no copy
  serves; every copy's slot-489 clip peaks at that copy's speed, which is
  each served entity's FLYER_CHARGE_SPEEDS row.
The installed game is a required input: without it the vanilla name set is
unknown and the check refuses rather than passing (§A14.4).
"""
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import rolepath  # noqa: E402 -- tools dir must be on sys.path first (§A12.2)
import air_dive_rules  # noqa: E402 -- same reason
import anim_table_bin  # noqa: E402 -- same reason
import anim_table_rename  # noqa: E402 -- same reason
import flyer_db as db_writer  # noqa: E402 -- same reason (FLYER-FIX-1117: self-contained repository)
import flyer_db as installed_db_table  # noqa: E402 -- same reason (FLYER-FIX-1117: self-contained repository)
from animpack_codec import animpack_iter  # noqa: E402 -- same reason
from packfile import PackFile  # noqa: E402 -- same reason

MOD_DIR = TOOLS_DIR.parent
GAME = Path(r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\data")
ANIM_PACKS = ("anim.pack", "anim2.pack", "anim_3.pack")
# the pack ships staged files from mod/assets alone.
SHIP_ROOTS = (MOD_DIR / "assets",)
BIN_DIR = "animations/database/battle/bin/"


def _require_game():
    missing = [n for n in ANIM_PACKS + ("db.pack",) if not (GAME / n).is_file()]
    if missing:
        raise AssertionError(f"installed game data missing {missing} under {GAME}: "
                             "the vanilla table names cannot be known")


def _name(blob):
    """Header table name, or None for a bin that is not a v4 battle table
    (the one such vanilla file is matched_combat, version 1)."""
    try:
        return anim_table_bin.parse(blob)["name"]
    except anim_table_bin.BinFormatError:
        return None


def vanilla_table_names():
    """Every vanilla battle table name: bin path stems and header names."""
    _require_game()
    names = set()
    for pack in ANIM_PACKS:
        pf = PackFile.open(str(GAME / pack))
        try:
            for e in pf.entries:
                lp = e.path.replace("\\", "/").lower()
                blobs = []
                if lp.endswith(".animpack") and "/database/battle/bin/" in lp:
                    blobs = list(animpack_iter(pf.read_file(e)))
                elif lp.startswith(BIN_DIR) and lp.endswith(".bin"):
                    blobs = [(lp, pf.read_file(e))]
                for ip, blob in blobs:
                    if not (ip.startswith(BIN_DIR) and ip.endswith(".bin")):
                        continue
                    names.add(ip.rsplit("/", 1)[1][:-4].lower())
                    name = _name(blob)
                    if name:
                        names.add(name.lower())
        finally:
            pf.close()
    if len(names) < 1000:
        raise AssertionError(f"only {len(names)} vanilla table names read")
    return names


def shipped_battle_bins(roots=SHIP_ROOTS):
    """``[(file, inner path or None, header name or None)]`` for every battle
    bin we stage, loose or inside an animpack."""
    out = []
    for root in roots:
        for path in sorted(Path(root).rglob("*")):
            rel = path.as_posix().lower()
            if path.suffix == ".animpack":
                for ip, blob in animpack_iter(path.read_bytes()):
                    if ip.startswith(BIN_DIR) and ip.endswith(".bin"):
                        out.append((path, ip, _name(blob)))
            elif path.suffix == ".bin" and "/" + BIN_DIR in rel:
                out.append((path, None, _name(path.read_bytes())))
    return out


def vanilla_named(bins, vanilla):
    hits = []
    for path, ip, name in bins:
        stem = (ip or path.as_posix()).rsplit("/", 1)[1][:-4].lower()
        if stem in vanilla or (name and name.lower() in vanilla):
            hits.append((str(path), ip, name))
    return hits


class NoVanillaNamedBins(unittest.TestCase):
    def test_no_staged_bin_reuses_a_vanilla_table_name(self):
        hits = vanilla_named(shipped_battle_bins(), vanilla_table_names())
        self.assertEqual(hits, [], "a shipped battle bin reuses a vanilla "
                         "table name; the game ignores it -- ship it renamed "
                         "(lib/anim_table_rename.py)")

    def test_the_check_sees_a_vanilla_name(self):
        """Anti-vacuity: the W1-W7 shape (a dr1_dragon bin) must be caught,
        by path stem and by header name."""
        vanilla = vanilla_table_names()
        fake = [(Path("x/" + BIN_DIR + "dr1_dragon.bin"), None, "dr1_dragon"),
                (Path("y.animpack"), BIN_DIR + "renamed.bin", "dr1_dragon")]
        self.assertEqual(len(vanilla_named(fake, vanilla)), 2)


class AirDiveRenames(unittest.TestCase):
    def test_manifest_renames_are_new_names_of_vanilla_tables(self):
        vanilla = vanilla_table_names()
        records, _renames = air_dive_rules.table_renames()
        self.assertTrue(records)
        base = MOD_DIR / "assets" / "air_dive"
        staged = {p.relative_to(base).as_posix(): p for p in base.rglob("*.bin")}
        animpacks = list(base.glob("*.animpack"))
        self.assertEqual(len(animpacks), 1)
        packed = dict(animpack_iter(animpacks[0].read_bytes()))
        for rec in records:
            with self.subTest(table=rec["source"]):
                self.assertIn(rec["source"].lower(), vanilla)
                self.assertNotIn(rec["renamed"].lower(), vanilla)
                self.assertEqual(rec["bin"], anim_table_rename.bin_path(rec["renamed"]))
                loose = staged[rec["bin"]].read_bytes()
                self.assertEqual(anim_table_bin.parse(loose)["name"], rec["renamed"])
                self.assertEqual(packed[rec["bin"]], loose)
        # [FLYER-SEAT-1117] the rider table copies whose header s1 names a renamed mount copy ride in the
        # same animpack (pipelines/air_dive.py rider_copies)
        riders, _units, _rr = air_dive_rules.rider_renames()
        self.assertTrue(riders)
        for rec in riders:
            with self.subTest(rider=rec["source"], mount=rec["s1"]):
                self.assertIn(rec["source"].lower(), vanilla)
                self.assertNotIn(rec["renamed"].lower(), vanilla)
                self.assertEqual(rec["bin"], anim_table_rename.bin_path(rec["renamed"]))
                loose = staged[rec["bin"]].read_bytes()
                table = anim_table_bin.parse(loose)
                self.assertEqual((table["name"], table["s1"]), (rec["renamed"], rec["s1"]))
                self.assertEqual(packed[rec["bin"]], loose)
        self.assertEqual(len(packed), len(records) + len(riders))

    def test_renamed_tables_have_no_landing_slot(self):
        """Slot 104 pins the landed flyer (canary 8: 0.0 m); canary 13 ran on
        24 m only with it gone from every renamed table."""
        base = MOD_DIR / "assets" / "air_dive"
        bins = sorted(p for p in base.rglob("*_dive*.bin") if "_dive_rider" not in p.name)
        self.assertTrue(bins)
        for path in bins:
            with self.subTest(table=path.name):
                slots = {e["slot"] for e in
                         anim_table_bin.parse(path.read_bytes())["entries"]}
                self.assertNotIn(104, slots)

    def test_slot_489_is_cas_own_or_removed(self):
        """[AIR-DIVE-MP-DIVE-W1 2026-11-12, §C8-61] The shipped design is the
        ground handoff (pipelines/air_dive.py dive_entries): a landed flyer is
        carried by the charge locomotion and the code caves, not by a clip.
        So no clip is staged (a plough or W1-W3 dive clip would be dead
        weight), slot 489 is gone wherever the table has a slot-484 moving
        attack (the attack picker would start CA's pounce at touchdown), and
        where it stays it plays CA's own clips -- nothing of ours.
        [FLYER-SEAT-1117 2026-11-17] The one exception: slot 103 of a table on
        a skeleton with a declared rider seat plays the levelled copy of its
        own dive clip (manifest ``level_clips``), the only staged clips."""
        import json
        base = MOD_DIR / "assets" / "air_dive"
        manifest = json.loads((base / "air_dive_manifest.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(manifest["plough_clips"], [])
        staged = {p.relative_to(base).as_posix() for p in base.rglob("*")
                  if p.name.endswith((".anim", ".anm.meta"))}
        level = {rec["clip"] for rec in manifest["level_clips"]}
        self.assertTrue(level)
        self.assertEqual(staged, level)
        recs = {rec["bin"]: rec for rec in manifest["tables_renamed"]}
        bins = sorted(p for p in base.rglob("*_dive*.bin") if "_dive_rider" not in p.name)
        self.assertTrue(bins)
        self.assertEqual({p.relative_to(base).as_posix() for p in bins},
                         set(recs))
        for path in bins:
            rec = recs[path.relative_to(base).as_posix()]
            with self.subTest(table=path.name):
                entries = anim_table_bin.parse(path.read_bytes())["entries"]
                slots = {e["slot"] for e in entries}
                if 484 in slots:
                    self.assertNotIn(489, slots)
                else:
                    self.assertEqual(rec["slot_489_removed"], [])
                if rec["slot_489_removed"]:
                    self.assertIn(484, slots)
                self.assertEqual(rec["plough_slots"], [])
                self.assertFalse(rec["slot_489_added"])
                ours = {c["to"] for c in (rec["slot_103_level"] or {}).get("clips", [])}
                for e in entries:
                    for r in e["refs"]:
                        if e["slot"] == 103 and r[0] in ours:
                            continue
                        self.assertNotIn("flyer_dive", r[0], f"slot {e['slot']}")


class PloughSpeedPerFlyer(unittest.TestCase):
    """[AIR-DIVE-W12] User 2026-11-11: momentum = speed x mass -- the plough
    clip runs at the flyer's own charge speed, not a size-class peak.
    [AIR-DIVE-W13] times the body-size multiplier, capped at 20.
    [AIR-DIVE-CONTINUOUS-W1, §C8-59 item 1] now its arrival speed, 0.9 x the
    charge speed (air_dive_rules.plough_speed); the W13 body-size multiplier
    is dropped. The speed still names a table's per-speed copies."""

    @classmethod
    def setUpClass(cls):
        import json
        base = MOD_DIR / "assets" / "air_dive"
        cls.manifest = json.loads((base / "air_dive_manifest.json")
                                  .read_text(encoding="utf-8"))
        cls.base = base

    def test_every_copy_serves_entities_at_its_speed(self):
        recs = self.manifest["tables_renamed"]
        self.assertTrue(recs)
        for rec in recs:
            with self.subTest(table=rec["renamed"]):
                self.assertTrue(rec["entities"])
                self.assertEqual(set(rec["body_sizes"]), set(rec["entities"]))
                for ent in rec["entities"]:
                    self.assertEqual(air_dive_rules.plough_speed(
                        air_dive_rules.charge_speed(ent)[0], rec["body_sizes"][ent]),
                        rec["speed"])

    def test_plough_speed_is_the_arrival_speed(self):
        """[AIR-DIVE-CONTINUOUS-W1, §C8-59 item 1] The arrival speed (0.9 x
        charge speed) whatever the body size (the W13 size bonus is dropped),
        capped at CHARGE_CAP; an unknown size is still refused."""
        ps = air_dive_rules.plough_speed
        self.assertEqual(ps(15.0, "very_large"), 13.5)
        self.assertEqual(ps(17.5, "large"), 15.8)
        self.assertEqual(ps(18.0, "medium"), 16.2)
        self.assertEqual(ps(17.0, "small"), 15.3)
        self.assertEqual(ps(25.0, "medium"), air_dive_rules.CHARGE_CAP)
        with self.assertRaises(RuntimeError):
            ps(15.0, "huge")

    def test_copies_carry_no_plough_clip(self):
        """[AIR-DIVE-MP-DIVE-W1, §C8-61] The plough design (W9-W13: each copy's
        slot 489 played a clip peaking at the copy's speed) is no longer
        shipped; every per-speed copy is the ground handoff and names no
        clip of ours in any slot."""
        recs = self.manifest["tables_renamed"]
        self.assertTrue(recs)
        for rec in recs:
            with self.subTest(table=rec["renamed"]):
                self.assertEqual(rec["plough_slots"], [])
                self.assertFalse(rec["slot_489_added"])
                table = anim_table_bin.parse((self.base / rec["bin"]).read_bytes())
                refs = [r[0] for e in table["entries"] for r in e["refs"]]
                self.assertTrue(refs)
                self.assertFalse([r for r in refs if "_dive_plough" in r])

    def test_plough_profile_scales_travel_with_speed(self):
        v_l, d_l = air_dive_rules.PLOUGH_PROFILES["L"]
        self.assertEqual(air_dive_rules.plough_profile("dragon01", v_l), ("L", v_l, d_l))
        _c, v, d = air_dive_rules.plough_profile("dragon01", 15.0)
        self.assertEqual(v, 15.0)
        self.assertAlmostEqual(d / v, d_l / v_l)
        for bad in (("no_such_skeleton", 15.0), ("dragon01", 25.0), ("dragon01", 0.0)):
            with self.subTest(args=bad), self.assertRaises(RuntimeError):
                air_dive_rules.plough_profile(*bad)

    def test_speed_tag(self):
        self.assertEqual(air_dive_rules.speed_tag(16.5), "v165")
        self.assertEqual(air_dive_rules.speed_tag(15.0), "v150")
        with self.assertRaises(RuntimeError):
            air_dive_rules.speed_tag(16.55)

    def test_repoint_by_entity(self):
        renames = {"hr1_pegasus": {"a": "hr1_pegasus_dive_v170",
                                   "b": "hr1_pegasus_dive_v180",
                                   "ground": "hr1_pegasus"},
                   "dr1_dragon": "dr1_dragon_dive"}
        rp = anim_table_rename.repoint
        self.assertEqual(rp("hr1_pegasus", renames, "a"), "hr1_pegasus_dive_v170")
        self.assertEqual(rp("hr1_pegasus", renames, "b"), "hr1_pegasus_dive_v180")
        self.assertEqual(rp("hr1_pegasus", renames, "ground"), "hr1_pegasus")
        self.assertEqual(rp("dr1_dragon", renames, "anything"), "dr1_dragon_dive")
        self.assertEqual(rp("hu1_x", renames, "a"), "hu1_x")
        with self.assertRaises(anim_table_rename.Refused):
            rp("hr1_pegasus", renames, "unknown")
        self.assertEqual(anim_table_rename.targets(renames, "hr1_pegasus"),
                         ["hr1_pegasus_dive_v170", "hr1_pegasus_dive_v180"])
        text = ("key\tanimation\tentity\n#meta\n"
                "m1\thr1_pegasus\ta\nm2\thr1_pegasus\tground\nm3\thr1_pegasus\tb\n")
        moved, count = anim_table_rename.repoint_mounts_tsv(text, renames)
        self.assertEqual(count, 2)
        self.assertIn("m1\thr1_pegasus_dive_v170\ta", moved)
        self.assertIn("m2\thr1_pegasus\tground", moved)
        self.assertIn("m3\thr1_pegasus_dive_v180\tb", moved)

    def test_generated_riders_are_served(self):
        """Adapter input: the Lore Disasters generators' riders
        (GENERATED_RIDERS) resolve to a copy at their own speed; a new one must
        be added to GENERATED_RIDERS and the pipeline rerun, else dive_table
        refuses."""
        records, renames = air_dive_rules.table_renames()
        speed_of = {r["renamed"]: r["speed"] for r in records}
        size_of = {e: s for r in records for e, s in r["body_sizes"].items()}
        for src, ent in air_dive_rules.GENERATED_RIDERS:
            with self.subTest(rider=(src, ent)):
                new = air_dive_rules.dive_table(src, ent)
                self.assertEqual(speed_of[new], air_dive_rules.plough_speed(
                    air_dive_rules.charge_speed(ent)[0], size_of[ent]))


class FlyerJumpAttack(unittest.TestCase):
    # [AIR-DIVE-W10] a real flyer key: the charge speed is looked up per
    # flyer, and this row's 20.0 is that flyer's row (boss terrorgheist)
    ROW = {"key": "wh_dlc08_vmp_mon_terrorgheist_boss",
           "fly_speed": 9.5, "type": "monster", "flying_charge_speed": 20.0,
           "acceleration": 8.0, "deceleration": 30.0,   # AIR-DIVE-CONTINUOUS-W1
           "charge_distance_commence_run": 60.0,
           "charge_distance_adopt_charge_pose": 45.0,
           "charge_distance_pick_target": 60.0,
           "locomotion_constants": "flyer_dive_large_entity",
           "allow_turn_to_move_anim": False, "allow_static_turn_anim": False,
           "jump_attack_chance": 20}

    def test_flyer_gets_0_unless_declared(self):
        """[AIR-DIVE-MP-DIVE-W1, §C8-61] 0 (was 100 at W8): the ground handoff
        plays no jump attack at touchdown."""
        self.assertEqual(air_dive_rules.JUMP_ATTACK_CHANCE, 0)
        self.assertEqual(air_dive_rules.tuned_cells(self.ROW),
                         {"jump_attack_chance": 0})
        self.assertEqual(air_dive_rules.tuned_cells(
            self.ROW, declared=["jump_attack_chance"]), {})
        self.assertEqual(air_dive_rules.tuned_cells(
            dict(self.ROW, fly_speed=0.0)), {})



class PackRepointsRiders(unittest.TestCase):
    """The pack's emitter (``pipelines/build_air_dive_minimod.rename_entries``) ships every installed
    land unit and mount that rides a renamed source table, repointed to the copy serving its entity: a
    row left out keeps naming the vanilla table, which still plays, and that flyer never dives. The
    expected rows come from the installed tables and the manifest's records, not from the emitter's
    helpers; every other cell is the installed row's (DB merge is whole-row replacement).
    [FLYER-DECOUPLE 2026-11-17] These checks used to read the source text of the main mod's emitters
    (``generators/dbw_*.py``, ``build_pack.py``), which this repository does not have; its one emitter
    is checked here by what it emits."""

    @classmethod
    def setUpClass(cls):
        import json
        import build_air_dive_minimod as mini
        _require_game()
        manifest = json.loads((MOD_DIR / "assets" / "air_dive" / "air_dive_manifest.json")
                              .read_text(encoding="utf-8"))
        cls.records = manifest["tables_renamed"]
        cls.riders = manifest["riders_renamed"]
        entries, _counts = mini.rename_entries(GAME / "db.pack")
        cls.emitted = {}
        for path, data in entries:
            table = path.split("\\")[1]
            if table in (anim_table_rename.LAND_TABLE, anim_table_rename.MOUNTS_TABLE):
                rows = db_writer._decode_db_table_bytes(data, table, path)
                cls.emitted[table] = {r["key"]: r for r in rows}

    def _expected(self, table, column, entity_column):
        rows, _h = installed_db_table.decode_round_trip(GAME / "db.pack", table, "test_anim_table_rename")
        copy_of = {}
        for rec in self.records:
            for ent in rec["entities"]:
                copy_of[(rec["source"], ent)] = rec["renamed"]
        want = {}
        for row in rows:
            new = copy_of.get((row[column], row[entity_column]))
            if new is not None:
                want[row["key"]] = dict(row, **{column: new})
        return want, {r["key"]: r for r in rows}

    def _assert_ships(self, table, want):
        self.assertTrue(want)
        got = self.emitted[table]
        self.assertEqual(sorted(set(want) - set(got)), [], "rows on a renamed table not shipped")
        self.assertEqual(sorted(set(got) - set(want)), [], "rows shipped that ride no renamed table")
        for key, row in sorted(want.items()):
            with self.subTest(key=key):
                self.assertEqual(got[key], row)

    def test_every_land_unit_on_a_renamed_table_ships_repointed(self):
        want, installed = self._expected(anim_table_rename.LAND_TABLE, "man_animation", "man_entity")
        for rec in self.riders:      # [FLYER-SEAT-1117] a rider unit names its rider table copy instead
            for unit in rec["land_units"]:
                want[unit] = dict(installed[unit], man_animation=rec["renamed"])
        self._assert_ships(anim_table_rename.LAND_TABLE, want)

    def test_every_mount_on_a_renamed_table_ships_repointed(self):
        """[AIR-DIVE-W9] A mounted unit's body plays its mount row's table
        (griffon knights -> bc2_griffon)."""
        want, _installed = self._expected(anim_table_rename.MOUNTS_TABLE, "animation", "entity")
        self._assert_ships(anim_table_rename.MOUNTS_TABLE, want)


class CultureSchema(unittest.TestCase):
    def test_installed_fragment_round_trips(self):
        _require_game()
        table = anim_table_rename.CULTURE_TABLE
        schema = db_writer.SCHEMAS[table]
        self.assertFalse(schema["version_marker"])
        self.assertEqual(list(schema["fields"]),
                         ["battle_animations_table", "culture_pack"])
        rows, _header = installed_db_table.decode_round_trip(
            GAME / "db.pack", table, "test_anim_table_rename")
        self.assertGreater(len(rows), 1000)


class MountsSchema(unittest.TestCase):
    def test_installed_fragment_round_trips(self):
        """[AIR-DIVE-W9] The pack writes the repointed mount rows with this
        schema."""
        _require_game()
        table = anim_table_rename.MOUNTS_TABLE
        schema = db_writer.SCHEMAS[table]
        self.assertTrue(schema["version_marker"])
        self.assertEqual(list(schema["fields"])[:2], ["key", "animation"])
        rows, _header = installed_db_table.decode_round_trip(
            GAME / "db.pack", table, "test_anim_table_rename")
        self.assertGreater(len(rows), 300)


class TsvRepoint(unittest.TestCase):
    def test_only_man_animation_moves_and_line_endings_hold(self):
        text = ("key\tman_animation\tman_entity\r\n#meta\r\n"
                "u1\tdr1_dragon\tdr1_dragon\r\nu2\thu1_x\thu1_x\r\n")
        moved, count = anim_table_rename.repoint_land_units_tsv(
            text, {"dr1_dragon": "dr1_dragon_dive"})
        self.assertEqual(count, 1)
        self.assertEqual(moved, text.replace("u1\tdr1_dragon\t",
                                             "u1\tdr1_dragon_dive\t"))
        same, zero = anim_table_rename.repoint_land_units_tsv(text, {"x": "y"})
        self.assertIs(same, text)
        self.assertEqual(zero, 0)

    def test_mounts_tsv_moves_only_animation(self):
        text = ("key\tanimation\tentity\n#meta\n"
                "m1\tbc2_griffon\tbc2_griffon\nm2\thr1_horse\thr1_horse\n")
        moved, count = anim_table_rename.repoint_mounts_tsv(
            text, {"bc2_griffon": "bc2_griffon_dive"})
        self.assertEqual(count, 1)
        self.assertEqual(moved, text.replace("m1\tbc2_griffon\t",
                                             "m1\tbc2_griffon_dive\t"))


if __name__ == "__main__":
    unittest.main()
