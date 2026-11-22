"""One pack again (owner ruling 2026-11-18, docs/DECISIONS.md D10, withdrawing D1's balance submod).

These checks read the very entry list the build writes (``build_air_dive_minimod.pack_entries``), and one real
build into a temporary folder:

* the flyer rows are the installed rows plus ``tuned_cells``; [D61] no flyer's mass changes (the mass cut is
  undone) and [D59] no flyer weapon gets a collision attack;
* the breath usage-flag table ships in this pack, once, at the vanilla path;
* the breath switch (MCT setting, D10) ships: its three scripts and the generated data module, whose ability
  list is exactly the abilities the table unlocks;
* the build writes one pack and nothing else, refuses ``--balance-out`` and any other pack name, and no
  shipped path or byte names the withdrawn submod or its pairing stamps.
The installed game is a required input: without it the checks refuse rather than pass.
/ 改回一个包：主包带吹息表、吹息开关随包（D61 起不改质量）；建包只写一个包，任何文件不提子模组。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path
import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import build_air_dive_minimod as mini  # noqa: E402 -- same reason (pipelines/)
import flyer_db  # noqa: E402 -- same reason
from packfile import PackFile  # noqa: E402 -- tools/ is on sys.path above

DB_PACK = mini.GAME_DIR / "db.pack"
ENT = mini.ENTITY_TABLE
USAGE_PATH = f"db\\{air_dive_rules.USAGE_FLAGS_TABLE}\\{air_dive_rules.USAGE_FLAGS_FRAGMENT}"
WITHDRAWN = (b"flyer_dive_balance", b"balance_check", b"balance_stamp", b"main_stamp")


def _decode(entries, path):
    hits = [data for p, data in entries if p == path]
    if len(hits) != 1:
        raise AssertionError(f"{len(hits)} entries at {path}")
    rows, _raw = flyer_db._decode_db_table_bytes(hits[0], path.split("\\")[1], path, capture_raw=True)
    return {r["key"]: r for r in rows}


class OnePack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB_PACK.is_file():
            raise RuntimeError(f"required installed db.pack missing: {DB_PACK}")
        cls.entries, cls.info = mini.pack_entries()
        rows, _h = flyer_db.decode_round_trip(DB_PACK, ENT, "test_one_pack")
        cls.installed = {r["key"]: r for r in rows}
        cls.ent = _decode(cls.entries, f"db\\{ENT}\\{mini.FRAGMENT}")

    def test_rows_are_installed_plus_tuned_cells(self):
        self.assertTrue(self.ent)
        for key, row in self.ent.items():
            with self.subTest(key=key):
                inst = self.installed[key]
                self.assertEqual(row, dict(inst, **air_dive_rules.tuned_cells(inst)))

    def test_no_mass_change(self):
        """[D61] the mass cut is undone: every shipped flyer row keeps the installed mass."""
        self.assertEqual(air_dive_rules.MASS_FACTOR, {})
        self.assertEqual(self.info["n_mass_cut"], 0)
        self.assertTrue(self.ent)
        for key, row in self.ent.items():
            with self.subTest(key=key):
                self.assertEqual(row["mass"], self.installed[key]["mass"])
        self.assertEqual(self.ent["wh2_main_hef_mon_star_dragon"]["mass"], 5900.0)

    def test_collision_attack_sized_on_uncut_mass(self):
        for key, row in self.ent.items():
            with self.subTest(key=key):
                self.assertEqual(air_dive_rules.uncut_mass(row), self.installed[key]["mass"])

    def test_no_flyer_collision_attack(self):
        """[D59] flyers carry no collision attack: no weapon row ships, every shipped land unit keeps CA's weapon."""
        self.assertEqual(air_dive_rules.IMPACT_STAGE, "A")
        weapon_paths = [p for p, _d in self.entries if p.startswith(f"db\\{air_dive_rules.COLLISION_ATTACK_TABLE}\\")]
        self.assertEqual(weapon_paths, [])
        land_path = f"db\\land_units_tables\\{mini.FRAGMENT}"
        shipped = _decode(self.entries, land_path)
        installed = {r["key"]: r for r in flyer_db.decode_round_trip(DB_PACK, "land_units_tables", "test_one_pack")[0]}
        self.assertTrue(shipped)
        for key, row in shipped.items():
            with self.subTest(key=key):
                self.assertEqual(row["primary_melee_weapon"], installed[key]["primary_melee_weapon"])

    def test_breath_table_ships_once(self):
        usage = [d for p, d in self.entries if p.startswith(USAGE_PATH.rsplit("\\", 1)[0] + "\\")]
        writer, removed, _breath = air_dive_rules.breath_usage_writer(DB_PACK, DB_PACK.parent / "local_en.pack")
        self.assertEqual(usage, [writer.build()])
        self.assertEqual(self.info["usage_rows_removed"], len(removed))
        self.assertGreater(len(removed), 0)

    def test_breath_switch_ships(self):
        paths = dict(self.entries)
        for rel in mini.BREATH_SWITCH_SCRIPTS:
            with self.subTest(rel=rel):
                self.assertEqual(paths[rel], (mini.MOD_DIR / rel).read_bytes().replace(b"\r\n", b"\n"))
        _w, removed, _b = air_dive_rules.breath_usage_writer(DB_PACK, DB_PACK.parent / "local_en.pack")
        data = paths[air_dive_rules.BREATH_SWITCH_LUA_PATH].decode("utf-8")
        self.assertEqual(data, air_dive_rules.breath_switch_lua(removed).decode("utf-8"))
        for key in {r["special_ability"] for r in removed}:
            self.assertIn(f'["{key}"]', data)
        self.assertEqual(data.count('"] = {'), len({r["special_ability"] for r in removed}))
        # the battle entry needs lib/cave_common, which the take-off scripts carry
        self.assertIn("script/campaign/flyer_dive/lib/cave_common.lua", paths)

    def test_paths_unique(self):
        paths = [p for p, _d in self.entries]
        self.assertEqual(len(paths), len(set(paths)))

    def test_nothing_names_the_withdrawn_submod(self):
        for path, data in self.entries:
            with self.subTest(path=path):
                for word in WITHDRAWN:
                    self.assertNotIn(word.decode(), path)
                    self.assertNotIn(word, data)
        self.assertFalse((mini.MOD_DIR / "script/flyer_dive/balance_check.lua").exists())
        entry = (mini.MOD_DIR / "script/battle/mod/flyer_dive.lua").read_text("utf-8")
        self.assertNotIn("balance", entry.lower())


class OneBuild(unittest.TestCase):
    def test_build_writes_one_pack(self):
        if not DB_PACK.is_file():
            raise RuntimeError(f"required installed db.pack missing: {DB_PACK}")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / mini.MAIN_PACK_NAME
            mini.main(["--out", str(out)])
            self.assertEqual(sorted(os.listdir(tmp)), [mini.MAIN_PACK_NAME])
            with PackFile.open(str(out)) as pack:
                built = {e.path: pack.read_file(e) for e in pack.entries}
        entries, _info = mini.pack_entries()
        self.assertEqual(built, dict(entries))

    def test_refuses_balance_out_and_other_names(self):
        with self.assertRaises(SystemExit):
            mini.main(["--out", "x/flyer_dive_takeoff.pack", "--balance-out", "x/flyer_dive_balance.pack"])
        with self.assertRaises(SystemExit):
            mini.main(["--out", "x/flyer_dive_balance.pack"])
        self.assertFalse(hasattr(mini, "balance_entries"))
        self.assertFalse(hasattr(air_dive_rules, "balance_cells"))


if __name__ == "__main__":
    unittest.main()
