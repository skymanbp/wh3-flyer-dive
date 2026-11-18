"""AIR-DIVE-W10 (2026-11-11): every shipping flyer has a charge-speed row.

User ruling 2026-11-11: "不要全部一样，根据定位和背景逐个调整" -- the flying
charge speed is set per flyer by role and lore, not by one formula. The table
is ``air_dive_rules.FLYER_CHARGE_SPEEDS``; ``tuned_cells`` refuses a flyer
without a row, so every emitter already fails closed. These checks pin the
table itself against what ships:

* every installed flyer the rule applies to (fly_speed > 0, not fauna) has a
  row -- the vanilla rows the flyer_dive_takeoff.pack entity fragment ships;
* every donor flyer of the main mod (the recorded snapshot
  data/main_mod_flyers.json, read through lib/main_mod_flyers.py) has a row --
  adapter input: the air-dive census counts them, the flyer pack does not
  ship them;
* the main mod's own generated flying bodies (MAIN_MOD_FLYING_BODIES) have
  rows -- adapter input as well;
* no row is stale: each key is one of the three sets above;
* every speed is in (0, 20] (the engine cap) with a role from FLYER_ROLES and
  a non-empty reason; the rewrite of a donor flyer row (the snapshot's rows in
  their source TSV format) changes only rule cells.
The installed game is a required input (§A14.4): without it the vanilla
flyer set is unknown and the check refuses rather than passing. So is the
snapshot: a missing or malformed one is a refusal in main_mod_flyers.load.
"""
import os
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path
import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import flyer_db as installed_db_table  # noqa: E402 -- same reason (FLYER-FIX-1117: self-contained repository)
import main_mod_flyers  # noqa: E402 -- because rolepath above puts lib/ on sys.path

DB_PACK = Path(os.environ.get(
    "WH3_DB_PACK",
    r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\data\db.pack"))
# Adapter input: the main mod's own flying bodies, emitted by its generators and not shipped by the flyer
# pack (measured on the main mod's built pack 2026-11-11): Galrauch and Ka'Bandha (its character emitter),
# the Doom Knight disc body (its balance emitter). They stay so the charge-speed table keeps covering every
# body the future main-mod adapter pack will carry.
MAIN_MOD_FLYING_BODIES = {"ld_chr_galrauch", "ld_chr_kabandha", "ld_moncav_tze_disc"}


def installed_flyers():
    if not DB_PACK.is_file():
        raise RuntimeError(f"required installed db.pack missing: {DB_PACK}")
    rows, _h = installed_db_table.decode_round_trip(
        DB_PACK, "battle_entities_tables", "air_dive_charge_speeds")
    return {r["key"] for r in rows if air_dive_rules.is_flyer(r)}


def vendored_flyers():
    """``{donor flyer entity: source TSV path}`` from the snapshot."""
    keys = {}
    for source, row in main_mod_flyers.entity_rows():
        if float(row["fly_speed"]) > 0 and row["type"] not in air_dive_rules.EXCLUDED_TYPES:
            keys[row["key"]] = source
    if not keys:
        raise RuntimeError(f"no donor flyer in {main_mod_flyers.SNAPSHOT}")
    return keys


class ChargeSpeedCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = air_dive_rules.FLYER_CHARGE_SPEEDS
        cls.installed = installed_flyers()
        cls.vendored = vendored_flyers()

    def test_every_installed_flyer_has_a_row(self):
        self.assertEqual(sorted(self.installed - set(self.table)), [])

    def test_every_donor_flyer_has_a_row(self):
        self.assertEqual(sorted(set(self.vendored) - set(self.table)), [])

    def test_main_mod_flying_bodies_have_rows(self):
        self.assertEqual(sorted(MAIN_MOD_FLYING_BODIES - set(self.table)), [])

    def test_no_stale_row(self):
        known = self.installed | set(self.vendored) | MAIN_MOD_FLYING_BODIES
        self.assertEqual(sorted(set(self.table) - known), [])

    def test_rows_are_well_formed(self):
        for key, (speed, role, reason) in self.table.items():
            with self.subTest(key=key):
                self.assertGreater(speed, 0)
                self.assertLessEqual(speed, air_dive_rules.CHARGE_CAP)
                self.assertIn(role, air_dive_rules.FLYER_ROLES)
                self.assertTrue(reason.strip())

    def test_unlisted_flyer_is_refused(self):
        row = {"key": "no_such_flyer", "fly_speed": 9.0, "type": "giant",
               "flying_charge_speed": 12.0}
        with self.assertRaises(RuntimeError):
            air_dive_rules.tuned_cells(row)

    def test_donor_rewrite_touches_only_rule_cells(self):
        # [AIR-DIVE-TAKEOFF-W1 2026-11-12, §C8-58] acceleration is no longer a
        # rule cell (vanilla again): a rewrite that touches it fails here
        allowed = {"flying_charge_speed", "deceleration",
                   "locomotion_constants", "jump_attack_chance",
                   *air_dive_rules.CHARGE_DISTANCE_FLOORS,
                   *air_dive_rules.TURN_ANIM_CELLS}
        texts = main_mod_flyers.entities_tsv_texts()
        for path in sorted(set(self.vendored.values())):
            text = texts[path]
            new, _count = air_dive_rules.rewrite_vendored_entities_tsv(text)
            old_lines, new_lines = text.split("\n"), new.split("\n")
            self.assertEqual(len(old_lines), len(new_lines))
            header = old_lines[0].rstrip("\r").split("\t")
            for a, b in zip(old_lines[2:], new_lines[2:]):
                for col, x, y in zip(header, a.split("\t"), b.split("\t")):
                    if x != y:
                        with self.subTest(path=path, col=col):
                            # [balance split 2026-11-17] mass is no longer a main rule
                            # cell (tuned_cells): the cut and its assertions moved to
                            # balance_cells / tests/test_flyer_dive_balance.py
                            self.assertIn(col, allowed)


class SnapshotShape(unittest.TestCase):
    """The snapshot holds what its header says, and a broken one is refused, not read as empty."""

    def test_recorded_entity_rows_all_fly(self):
        rows = main_mod_flyers.entity_rows()
        self.assertTrue(rows)
        self.assertEqual([r["key"] for _s, r in rows if not air_dive_rules.is_flyer(r)], [])

    def test_missing_snapshot_is_refused(self):
        with self.assertRaises(main_mod_flyers.SnapshotError):
            main_mod_flyers.load(TESTS_DIR / "no_such_snapshot.json")

    def test_malformed_row_is_refused(self):
        import json
        import tempfile
        data = json.loads(main_mod_flyers.SNAPSHOT.read_text(encoding="utf-8"))
        name = sorted(data["closures"])[0]
        table = sorted(data["closures"][name])[0]
        data["closures"][name][table]["rows"][0].pop()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(main_mod_flyers.SnapshotError):
                main_mod_flyers.load(path)


if __name__ == "__main__":
    unittest.main()
