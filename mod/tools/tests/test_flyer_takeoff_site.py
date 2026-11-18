"""AIR-DIVE-TAKEOFF-W1 (2026-11-12, CONTENT_LEDGER §C8-58): the flyer take-off
rule's site table.

The rule -- a flying unit is held in melee only while more than half of its
living models were struck within the last 15 battle ticks -- is two code
caves (FLYER-TAKEOFF-HITS 2026-11-16: one stamp at the damage applier
replaced the two inside the hit processor). Their source, emulator check, sites and field anchors live in
``pipelines/pin_cave_asm.py``; what ships is the generated data module
``data/takeoff_site.lua``. These checks pin the join between the two:

* the committed table was generated from the current cave source (a cave edit
  without ``--write-site`` would ship bytes the emulator never saw);
* the table names every cave and every field anchor, the hold cave, its
  resume offset and the ruled window, and no entry the tool does not know;
* every pattern is one memreader Plus accepts (its own length limit, read
  from the vendored loader; no wildcard first);
* the installed game holds every cave site and every anchor exactly once.
The installed exe is a required input (§A14.4): without it the last check
refuses rather than passing. The emulator check itself (506 cases, 19 broken
caves each caught) needs keystone + unicorn and runs inside pin_cave_asm.py
before it writes the table; it is not repeated here.
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
import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import pin_cave_asm  # noqa: E402 -- same reason (pipelines/)
from cave_site_cases import loader_pattern_limit, read_site_text  # noqa: E402 -- because it follows the sys.path bootstrap above (TEST-REPAIR-1113: one home)

MOD_DIR = TOOLS_DIR.parent
SITE_FILE = MOD_DIR / air_dive_rules.TAKEOFF_SITE_LUA_PATH
GAME_EXE = Path(os.environ.get(
    "WH3_GAME_EXE",
    r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\Warhammer3.exe"))


def site_text():
    return read_site_text(SITE_FILE)


class SiteTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = site_text()

    def test_generated_from_the_current_cave_source(self):
        self.assertTrue(pin_cave_asm.check_site_file(MOD_DIR))

    def test_names_every_cave_and_anchor_and_nothing_else(self):
        named = re.findall(r"name = '([a-z_]+)', feature = '([a-z_]+)', kind = '([a-z]+)'", self.text)
        want = ([(n, pin_cave_asm.FEATURE, "cave") for n in pin_cave_asm.CAVES]
                + [(n, pin_cave_asm.FEATURE, "anchor") for n in pin_cave_asm.ANCHORS])
        self.assertEqual(named, want)
        self.assertEqual((len(pin_cave_asm.CAVES), len(pin_cave_asm.ANCHORS)), (2, 7))

    def test_owner_feature_hold_and_window(self):
        # whole lines of the table's top level (an entry repeats the feature inline)
        lines = self.text.splitlines()
        for line in (f"    owner = '{air_dive_rules.TAKEOFF_OWNER}',",
                     f"    feature = '{air_dive_rules.TAKEOFF_FEATURE}',",
                     f"    hold = '{pin_cave_asm.HOLD_NAME}', resume_at = {pin_cave_asm.HOLD_RESUME_AT},",
                     f"    build = '{air_dive_rules.TAKEOFF_BUILD}',"):
            with self.subTest(line=line):
                self.assertEqual(lines.count(line), 1)
        self.assertEqual(self.text.count(f" window = {air_dive_rules.TAKEOFF_PIN_WINDOW_TICKS},"), 1)
        # the ruled window: 1.5 s at the engine's 10 battle ticks a second
        self.assertEqual(air_dive_rules.TAKEOFF_PIN_WINDOW_TICKS, 15)
        # [§C8-78] one living model: 3.0 s
        self.assertEqual(self.text.count(
            f" window_single = {air_dive_rules.TAKEOFF_PIN_WINDOW_SINGLE_TICKS},"), 1)
        self.assertEqual(air_dive_rules.TAKEOFF_PIN_WINDOW_SINGLE_TICKS, 30)
        self.assertIn(pin_cave_asm.HOLD_NAME, pin_cave_asm.CAVES)

    def test_every_cave_takes_the_buffer_and_only_the_hold_cave_resumes(self):
        for name in pin_cave_asm.CAVES:
            m = re.search(rf"name = '{name}',.*?bytes = '([^']*)'", self.text, re.S)
            self.assertIsNotNone(m, name)
            holders = re.findall(r"\{([a-z]+):8\}", m.group(1))
            with self.subTest(cave=name):
                self.assertEqual(holders, ["buf", "resume"] if name == pin_cave_asm.HOLD_NAME
                                 else ["buf"])

    def test_patterns_are_ones_the_loader_accepts(self):
        limit = loader_pattern_limit()
        patterns = {n: v[0] for n, v in pin_cave_asm.CAVES.items()}
        patterns.update({n: v[0] for n, v in pin_cave_asm.ANCHORS.items()})
        for name, pattern in patterns.items():
            tokens = pattern.split()
            with self.subTest(site=name):
                self.assertLessEqual(len(tokens), limit)
                self.assertNotEqual(tokens[0], "??")
                self.assertTrue(all(re.fullmatch(r"[0-9A-F]{2}|\?\?", t) for t in tokens))
                self.assertEqual(self.text.count(f"pattern = '{pattern}'"), 1)


class InstalledGame(unittest.TestCase):
    def test_every_site_and_anchor_exactly_once(self):
        if not GAME_EXE.is_file():
            raise RuntimeError(f"required installed game exe missing: {GAME_EXE}")
        found = pin_cave_asm.check_exe(GAME_EXE)
        self.assertEqual(sorted(found), sorted([*pin_cave_asm.CAVES, *pin_cave_asm.ANCHORS]))
        self.assertEqual(len(set(found.values())), len(found))


if __name__ == "__main__":
    unittest.main()
