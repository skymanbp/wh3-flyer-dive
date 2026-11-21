"""[D56 / D57] The SFO submod's pieces that do not need SFO's 2 GB pack (the build itself reads SFO and checks the
written pack against it, build_sfo_submod.check_pack, before it keeps the file):

* flyer_db.overlay answers for its tables, for any pack, and only inside the block; overlays do not nest;
* the main build's entity rule with keep = air_dive_rules.SFO_KEEP_ENTITY_COLUMNS leaves those columns as the base
  has them (the installed game), while every other cell it changes still changes; keep = () is the main pack;
* the submod's pack and fragment names sort before SFO's and the main pack's, plainly and case-blind (D57);
* the submod refuses a wrong output name.
"""
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path
import air_dive_rules  # noqa: E402 -- same reason (lib/)
import flyer_db  # noqa: E402 -- same reason (lib/)
import build_air_dive_minimod as main_build  # noqa: E402 -- same reason (pipelines/)
import build_sfo_submod as sub  # noqa: E402 -- same reason (pipelines/)

DB = main_build.GAME_DIR / "db.pack"
SFO_FRAGMENTS = ("#SFO_hero", "SFO_data", "SFO_units")     # read from sfo_grimhammer_3_main.pack, 2026-11-21


def need(path):
    if not Path(path).is_file():
        raise AssertionError(f"required input missing: {path}")
    return path


class Overlay(unittest.TestCase):
    def test_answers_inside_only(self):
        with flyer_db.overlay({"mounts_tables": b"X"}):
            self.assertEqual(flyer_db.installed_bytes("no_such.pack", "mounts_tables", "t"), b"X")
            with self.assertRaises(RuntimeError):
                with flyer_db.overlay({"land_units_tables": b"Y"}):
                    pass
        self.assertEqual(flyer_db._OVERLAY, {})
        with self.assertRaises(Exception):
            flyer_db.installed_bytes("no_such.pack", "mounts_tables", "t")


class KeepColumns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need(DB)
        cls.installed = {r["key"]: r for r in main_build._installed_entities(DB)[0]}

        def built(keep):
            (path, data), _loco = main_build.db_entries(DB, keep=keep)[0]
            return {r["key"]: r for r in flyer_db._decode_db_table_bytes(data, main_build.ENTITY_TABLE, path)}
        cls.main, cls.kept = built(()), built(air_dive_rules.SFO_KEEP_ENTITY_COLUMNS)

    def test_kept_columns_untouched(self):
        self.assertEqual(set(air_dive_rules.SFO_KEEP_ENTITY_COLUMNS), {"mass", "flying_charge_speed"})
        for k, row in self.kept.items():
            for col in air_dive_rules.SFO_KEEP_ENTITY_COLUMNS:
                self.assertEqual(row[col], self.installed[k][col], (k, col))

    def test_main_pack_still_cuts_and_sets(self):
        cut = [k for k, r in self.main.items() if r["mass"] != self.installed[k]["mass"]]
        speed = [k for k, r in self.main.items() if r["flying_charge_speed"] != self.installed[k]["flying_charge_speed"]]
        self.assertGreater(len(cut), 80)
        self.assertGreater(len(speed), 100)

    def test_other_cells_still_change(self):
        for k in self.kept:
            self.assertEqual(self.kept[k]["deceleration"], self.main[k]["deceleration"], k)
            self.assertEqual(self.kept[k]["jump_attack_chance"], self.main[k]["jump_attack_chance"], k)


class Names(unittest.TestCase):
    def test_sorts_first(self):
        packs = [sub.SUB_PACK_NAME, sub.SFO_PACK_NAME, main_build.MAIN_PACK_NAME]
        frags = [sub.FRAGMENT, *SFO_FRAGMENTS, main_build.FRAGMENT]
        for key in (str, str.lower):
            self.assertEqual(min(packs, key=key), sub.SUB_PACK_NAME)
            self.assertEqual(min(frags, key=key), sub.FRAGMENT)

    def test_wrong_output_name_refused(self):
        with self.assertRaises(SystemExit):
            sub.main(["--sfo", sub.SFO_PACK_NAME, "--main", main_build.MAIN_PACK_NAME, "--out", "flyer_sfo.pack"])


if __name__ == "__main__":
    unittest.main()
