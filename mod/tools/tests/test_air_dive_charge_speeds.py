"""AIR-DIVE-W10 (2026-11-11): every shipping flyer has a charge-speed row.

User ruling 2026-11-11: "不要全部一样，根据定位和背景逐个调整" -- the flying
charge speed is set per flyer by role and lore, not by one formula. The table
is ``air_dive_rules.FLYER_CHARGE_SPEEDS``; ``tuned_cells`` refuses a flyer
without a row, so every emitter already fails closed. These checks pin the
table itself against what ships:

* every installed flyer the rule applies to (fly_speed > 0, not fauna) has a
  row -- the vanilla rows the monster lane and the ld_air_dive fragment ship;
* every flying row of a staged donor closure (assets/vendored_chars/*/tsv)
  has a row -- build_pack pass 1d applies the rule to them;
* our own flying bodies (character entities, balance overrides) have rows;
* no row is stale: each key is one of the three sets above;
* every speed is in (0, 20] (the engine cap) with a role from FLYER_ROLES and
  a non-empty reason; the rewrite of a donor TSV changes only rule cells.
The installed game is a required input (§A14.4): without it the vanilla
flyer set is unknown and the check refuses rather than passing.
"""
import glob
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

MOD_DIR = TOOLS_DIR.parent
DB_PACK = Path(os.environ.get(
    "LD_VANILLA_DB_PACK",
    r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\data\db.pack"))
VENDORED_GLOB = str(MOD_DIR / "assets" / "vendored_chars" / "*" / "tsv" / "db"
                    / "battle_entities_tables" / "*.tsv")
# Our own flying bodies, emitted by generators (measured on ld_mod.pack
# 2026-11-11): dbw_characters (Galrauch, Ka'Bandha), dbw_balance (the Doom
# Knight disc body).
OUR_FLYING_BODIES = {"ld_chr_galrauch", "ld_chr_kabandha", "ld_moncav_tze_disc"}


def installed_flyers():
    if not DB_PACK.is_file():
        raise RuntimeError(f"required installed db.pack missing: {DB_PACK}")
    rows, _h = installed_db_table.decode_round_trip(
        DB_PACK, "battle_entities_tables", "air_dive_charge_speeds")
    return {r["key"] for r in rows if air_dive_rules.is_flyer(r)}


def vendored_flyers():
    keys = {}
    for path in sorted(glob.glob(VENDORED_GLOB)):
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        header = lines[0].split("\t")
        for line in lines[2:]:
            if not line.strip():
                continue
            row = dict(zip(header, line.split("\t")))
            if float(row["fly_speed"]) > 0 and row["type"] not in air_dive_rules.EXCLUDED_TYPES:
                keys[row["key"]] = path
    if not keys:
        raise RuntimeError(f"no donor flyer found under {VENDORED_GLOB}")
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

    def test_our_flying_bodies_have_rows(self):
        self.assertEqual(sorted(OUR_FLYING_BODIES - set(self.table)), [])

    def test_no_stale_row(self):
        known = self.installed | set(self.vendored) | OUR_FLYING_BODIES
        self.assertEqual(sorted(set(self.table) - known), [])

    def test_rows_are_well_formed(self):
        for key, (speed, role, reason) in self.table.items():
            with self.subTest(key=key):
                self.assertGreater(speed, 0)
                self.assertLessEqual(speed, air_dive_rules.CHARGE_CAP)
                self.assertIn(role, air_dive_rules.FLYER_ROLES)
                self.assertTrue(reason.strip())

    def test_unlisted_flyer_is_refused(self):
        row = {"key": "ld_no_such_flyer", "fly_speed": 9.0, "type": "giant",
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
        for path in sorted(set(self.vendored.values())):
            text = Path(path).read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
