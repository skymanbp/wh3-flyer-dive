"""AIR-DIVE-MP-DIVE-W1 (2026-11-12, CONTENT_LEDGER §C8-61): the flyer physics
dive's site table.

The rule -- a flyer that lands from a charge keeps its speed and only the
bodies it hits slow it -- is eleven code caves (three since AIR-DIVE-MP-DIVE-W1,
five call-site caves since AIR-DIVE-RELEASE-W1, the
contact-engage cave dv_contact, the blocked-stop call-site cave dv_settle
and the landing-commit call-site cave dv_commit since AIR-DIVE-BRACE-W1). Their source, emulator check
and sites live in ``pipelines/dive_cave_asm.py``; what ships is the generated
data module ``data/dive_site.lua``. These checks pin the join:

* the committed table was generated from the current cave source;
* it names every cave, every resume offset and call-site read, and no entry
  the tool does not know;
* every pattern is one memreader Plus accepts (its own length limit, read
  from the vendored loader);
* the installed game holds every cave site exactly once with the stolen bytes.
The installed exe is a required input (§A14.4): without it the last check
refuses rather than passing. The emulator check (keystone + unicorn) runs in
dive_cave_asm.py before it writes the table; it is not repeated here.
"""
import os
import re
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path
import dive_cave_asm  # noqa: E402 -- because rolepath above puts pipelines/ on sys.path
import dive_cost_asm  # noqa: E402 -- same reason ([D15 stage 5] it writes the shipped table)
from cave_site_cases import loader_pattern_limit, read_site_text  # noqa: E402 -- because it follows the sys.path bootstrap above (TEST-REPAIR-1113: one home)

MOD_DIR = TOOLS_DIR.parent
SITE_FILE = MOD_DIR / dive_cave_asm.SITE_LUA
GAME_EXE = Path(os.environ.get("WH3_GAME_EXE", str(dive_cave_asm.EXE)))


def site_text():
    return read_site_text(SITE_FILE)


class DiveSiteTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = site_text()

    def test_generated_from_the_current_cave_source(self):
        self.assertTrue(dive_cave_asm.check_site_file(MOD_DIR))

    def test_names_every_cave_and_nothing_else(self):
        named = re.findall(r"name = '([a-z_]+)', feature = '([a-z_]+)', kind = '([a-z]+)'", self.text)
        # [D15, d15-1118 stage 5] + the facing anchor and dv_cost (dive_cost_asm.py)
        self.assertEqual(named, [(n, dive_cave_asm.FEATURE, "cave") for n in dive_cave_asm.CAVES]
                         + [("dv_facing", dive_cave_asm.FEATURE, "anchor"), ("dv_cost", dive_cave_asm.FEATURE, "cave")])
        self.assertIn(f"    owner = '{dive_cave_asm.OWNER}',", self.text.splitlines())
        self.assertIn("    resume_at = { dv_through = 29, dv_engage = 11, dv_reorder = 8, dv_reorder_move = 10, "
                      "dv_attack_move = 17, dv_tick_move = 11, dv_settle = 14, dv_commit = 12, dv_cost = 26 },",
                      self.text.splitlines())
        self.assertIn("            reads = { facing = { from = 'dv_facing' } },", self.text.splitlines())
        self.assertIn("            reads = { facing = { at = 12, after = 16 } },", self.text.splitlines())
        # [AIR-DIVE-RELEASE-W1] each call-site cave names the call it replaces
        for name, site in dive_cave_asm.CALL_SITES.items():
            with self.subTest(cave=name):
                self.assertIn(f"            reads = {{ orig = {{ type = 'call', at = {site['call_at']} }} }},",
                              self.text.splitlines())

    def test_patterns_fit_the_loader(self):
        limit = loader_pattern_limit()
        patterns = {name: spec[0] for name, spec in dive_cave_asm.CAVES.items()}
        patterns.update({"dv_cost": dive_cost_asm.COST_SITE, "dv_facing": dive_cost_asm.FACING_ANCHOR})
        for name, pattern in patterns.items():
            with self.subTest(cave=name):
                tokens = pattern.split()
                self.assertLessEqual(len(tokens), limit)
                self.assertNotEqual(tokens[0], "??")

    def test_installed_exe_holds_each_site_once(self):
        if not GAME_EXE.is_file():
            raise RuntimeError(f"required input missing: installed game exe {GAME_EXE}")
        found = dive_cost_asm.check_exe(GAME_EXE)
        self.assertEqual(sorted(found), sorted(list(dive_cave_asm.CAVES) + ["dv_cost", "dv_facing"]))
        self.assertEqual({k: found[k] for k in ("dv_cost", "dv_facing")}, dive_cost_asm.EXE_SITES)


if __name__ == "__main__":
    unittest.main()
