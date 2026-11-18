"""Balance split (2026-11-17, user ruling): breath-while-engaged and the mass
cut ship in a second pack, ``flyer_dive_balance.pack``, built by the same run
as ``ld_air_dive.pack`` (``pipelines/build_air_dive_minimod.pack_entries``).

These checks read the very entry lists the build writes:

* the main pack ships no ``mass`` change and no breath usage-flag table: each
  of its flyer rows is the installed row plus ``tuned_cells``;
* each balance row is the main pack's full row plus the cut ``mass``
  (installed x 0.85 large / x 0.75 very_large, the celestial lions cut as
  large, the eleven war machines untouched), and the balance pack carries
  exactly the rows the cut changes;
* the balance pack's name and every DB fragment name it ships sort before the
  main pack's (RESIST-W2 measured "name that sorts first wins" with both sorted
  the same way, so both are pinned; the in-game swap test is still owed);
* the balance locomotion fragment is the main one byte for byte;
* the two packs' paths are disjoint;
* both packs carry the same build stamp, and the battle log's BALANCE line
  (script/flyer_dive/balance_check.lua, run in LuaJIT) tells a matched,
  mismatched and missing submod apart.
The installed game and LuaJIT are required inputs: without them the checks
refuse rather than pass.
/ 平衡子模组拆分：主包不改质量、不带喷吐表；子模组行＝主包整行＋减后质量；名字排序与建包戳。
"""
import hashlib
import os
import shutil
import subprocess
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

MOD_DIR = TOOLS_DIR.parent
DB_PACK = mini.GAME_DIR / "db.pack"
ENT = mini.ENTITY_TABLE
LOCO = mini.LOCOMOTION_TABLE
USAGE_DIR = f"db\\{air_dive_rules.USAGE_FLAGS_TABLE}\\"
# the ruled factors, written out here (not read from MASS_FACTOR) so a changed rule fails
RULED_FACTOR = {"large": 0.85, "very_large": 0.75}
LIONS = ("wh3_dlc24_cth_mon_celestial_lion", "wh3_dlc27_cth_mon_celestial_lion_boss")
# the eleven flying war machines and chariots that keep their mass (user ruling 2026-11-14),
# written out here (not read from MASS_CUT_MACHINES) so a dropped machine fails
RULED_MACHINES = frozenset({
    "wh3_dlc25_dwf_mnt_veh_thunderbarge", "wh3_dlc25_dwf_mnt_veh_thunderbarge_grungni",
    "ld_dwf_flying_thunderbarge", "wh3_main_cth_flying_sky_junk", "ld_cth_flying_sky_ark",
    "wh3_main_cth_flying_sky_lantern", "wh3_dlc27_hef_mnt_skycutter", "wh3_dlc27_hef_mnt_skycutter_bolt",
    "wh3_main_flying_tze_burning_chariot", "wh_main_dwf_flying_gyrocopter", "wh_main_dwf_flying_gyrobomber",
})


def _decode(entries, path):
    hits = [data for p, data in entries if p == path]
    if len(hits) != 1:
        raise AssertionError(f"{len(hits)} entries at {path}")
    rows, _raw = flyer_db._decode_db_table_bytes(hits[0], path.split("\\")[1], path,
                                                 capture_raw=True)
    return {r["key"]: r for r in rows}


def _db_fragments(entries):
    """[(table, fragment)] of every DB entry."""
    out = []
    for p, _d in entries:
        parts = p.replace("/", "\\").split("\\")
        if parts[0].lower() == "db":
            out.append((parts[1], parts[2]))
    return out


class BalanceSplit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB_PACK.is_file():
            raise RuntimeError(f"required installed db.pack missing: {DB_PACK}")
        cls.main, cls.bal, cls.info = mini.pack_entries()
        rows, _h = flyer_db.decode_round_trip(DB_PACK, ENT, "test_flyer_dive_balance")
        cls.installed = {r["key"]: r for r in rows}
        cls.main_ent = _decode(cls.main, f"db\\{ENT}\\{mini.FRAGMENT}")
        cls.bal_ent = _decode(cls.bal, f"db\\{ENT}\\{mini.BALANCE_FRAGMENT}")

    # --- main pack -----------------------------------------------------------
    def test_main_rows_are_installed_plus_tuned_cells_without_mass(self):
        self.assertTrue(self.main_ent)
        for key, row in self.main_ent.items():
            with self.subTest(key=key):
                inst = self.installed[key]
                self.assertEqual(row["mass"], inst["mass"])
                want = dict(inst, **air_dive_rules.tuned_cells(inst))
                self.assertEqual(row, want)

    def test_tuned_cells_never_touch_mass(self):
        for key, inst in self.installed.items():
            with self.subTest(key=key):
                if air_dive_rules.is_flyer(inst):
                    self.assertNotIn("mass", air_dive_rules.tuned_cells(inst))

    def test_main_ships_no_breath_table(self):
        self.assertEqual([p for p, _d in self.main if p.startswith(USAGE_DIR)], [])

    # --- balance pack ---------------------------------------------------------
    def test_balance_rows_are_main_rows_plus_cut_mass(self):
        want_keys = {k for k, r in self.installed.items()
                     if air_dive_rules.is_flyer(r) and k not in RULED_MACHINES
                     and ("large" if k in LIONS else r["size"]) in RULED_FACTOR}
        self.assertEqual(set(self.bal_ent), want_keys)
        self.assertEqual(len(self.bal_ent), self.info["balance"]["mass_rows"])
        for key, row in self.bal_ent.items():
            with self.subTest(key=key):
                inst = self.installed[key]
                base = self.main_ent.get(key, inst)
                size = "large" if key in LIONS else inst["size"]
                self.assertEqual(row["mass"], round(inst["mass"] * RULED_FACTOR[size], 3))
                self.assertEqual(dict(row, mass=base["mass"]), base)

    def test_mass_rule_exceptions(self):
        for key in LIONS:                     # very_large bodies, cut as large (user ruling 2026-11-15)
            with self.subTest(key=key):
                self.assertEqual(self.installed[key]["size"], "very_large")
                self.assertEqual(self.bal_ent[key]["mass"],
                                 round(self.installed[key]["mass"] * 0.85, 3))
        self.assertEqual(air_dive_rules.MASS_CUT_MACHINES, RULED_MACHINES)
        machines = RULED_MACHINES & set(self.installed)
        self.assertTrue(machines)
        self.assertEqual(sorted(machines & set(self.bal_ent)), [])
        star = "wh2_main_hef_mon_star_dragon"
        self.assertEqual(self.bal_ent[star]["mass"], round(self.installed[star]["mass"] * 0.75, 3))

    def test_balance_ships_the_breath_table(self):
        usage = [p for p, _d in self.bal if p.startswith(USAGE_DIR)]
        self.assertEqual(usage, [USAGE_DIR + air_dive_rules.USAGE_FLAGS_FRAGMENT])
        self.assertGreater(self.info["balance"]["usage_rows_removed"], 0)

    def test_locomotion_rows_are_main_bytes(self):
        main = [d for p, d in self.main if p == f"db\\{LOCO}\\{mini.FRAGMENT}"]
        bal = [d for p, d in self.bal if p == f"db\\{LOCO}\\{mini.BALANCE_FRAGMENT}"]
        self.assertEqual(len(main), 1)
        self.assertEqual(bal, main)

    # --- the pair ---------------------------------------------------------------
    def test_names_sort_before_the_main_pack(self):
        self.assertLess(mini.BALANCE_PACK_NAME, mini.MAIN_PACK_NAME)
        self.assertLess(mini.BALANCE_PACK_NAME.lower(), mini.MAIN_PACK_NAME.lower())
        main_frags = _db_fragments(self.main)
        bal_frags = _db_fragments(self.bal)
        self.assertTrue(bal_frags)
        first_main = min(f for _t, f in main_frags)
        for table, frag in bal_frags:
            with self.subTest(table=table, fragment=frag):
                self.assertLess(frag, first_main)
                self.assertLess(frag.lower(), first_main.lower())
                for t2, f2 in main_frags:
                    if t2 == table:
                        self.assertLess(frag, f2)

    def test_build_refuses_other_pack_names(self):
        with self.assertRaises(SystemExit):
            mini.main(["--out", "x/ld_air_dive.pack", "--balance-out", "x/zz_balance.pack"])
        with self.assertRaises(SystemExit):
            mini.main(["--out", "x/ld_air_dive.pack"])

    def test_paths_disjoint(self):
        self.assertEqual({p for p, _d in self.main} & {p for p, _d in self.bal}, set())

    def test_both_packs_carry_the_same_stamp(self):
        ent = [d for p, d in self.main if p == f"db\\{ENT}\\{mini.FRAGMENT}"][0]
        stamp = hashlib.sha256(ent).hexdigest()[:16]
        self.assertEqual(self.info["balance"]["stamp"], stamp)
        main_stamp = dict(self.main)[mini.STAMP_MAIN_PATH].decode("utf-8")
        bal_stamp = dict(self.bal)[mini.STAMP_BALANCE_PATH].decode("utf-8")
        self.assertIn(f'return {{ main = "{stamp}" }}', main_stamp)
        self.assertIn(f'return {{ built_for_main = "{stamp}" }}', bal_stamp)
        self.assertIn(mini.BALANCE_CHECK_PATH, dict(self.main))


LUA_CASE = r"""
package.path = arg[1] .. "/?.lua;" .. package.path
local check = dofile(arg[1] .. "/script/flyer_dive/balance_check.lua")
local function fake(mods)
    return function(name)
        local m = mods[name]
        if m == nil then error("module '" .. name .. "' not found") end
        return m
    end
end
local main = { main = "aaaa" }
print(check.line(fake({ [check.MAIN] = main, [check.BALANCE] = { built_for_main = "aaaa" } })))
print(check.line(fake({ [check.MAIN] = main, [check.BALANCE] = { built_for_main = "bbbb" } })))
print(check.line(fake({ [check.MAIN] = main })))
print(check.line(fake({})))
"""


class BalanceCheckLua(unittest.TestCase):
    def test_line(self):
        luajit = os.environ.get("LUAJIT") or shutil.which("luajit")
        if not luajit:
            raise RuntimeError("required input missing: luajit (set LUAJIT)")
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / "case.lua"
            case.write_text(LUA_CASE, encoding="utf-8")
            out = subprocess.run([luajit, str(case), str(MOD_DIR)], capture_output=True,
                                 text=True, check=True).stdout.splitlines()
        self.assertEqual(out[0], "BALANCE submod loaded, built for this main version aaaa")
        self.assertTrue(out[1].startswith("BALANCE MISMATCH: balance submod built for a different "
                                          "main version (submod built for bbbb, main is aaaa)"), out[1])
        self.assertEqual(out[2], "BALANCE submod not loaded (main aaaa)")
        self.assertTrue(out[3].startswith("BALANCE check failed"), out[3])

    def test_battle_entry_writes_the_line(self):
        text = (MOD_DIR / "script/battle/mod/ld_flyer_dive.lua").read_text(encoding="utf-8")
        self.assertIn('pcall(require, "script/flyer_dive/balance_check")', text)
        self.assertIn("pcall(balance_check.line, require)", text)


if __name__ == "__main__":
    unittest.main()
