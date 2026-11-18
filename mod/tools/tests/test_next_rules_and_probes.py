"""update-1117 (user rulings 2026-11-17, docs/DECISIONS.md D3 / D4): the two ruled numbers that do
not ship yet, and the test-only probes that decide how they will.

* D3: one take-off window per body size (very_large 30, large 35, medium 40, small 45 ticks),
  every battle_entities size covered, an unknown size refused;
* D4: the flyer's reflection hit is twice the game's own;
* the size probe's verdict: HOLDS only for one value per size, distinct, rising with size and
  stable between reads; REFUTED / INCOMPLETE otherwise (never a pass on missing data);
* the impact probe's caves sit exactly once in the installed exe, at the addresses of the static
  read (the emulator check needs keystone + unicorn and runs in reflect_probe_asm.py / the probe
  pack build, not here).
The installed exe is a required input: without it the last check refuses rather than passing.
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
import flyer_size_probe_report as size_report  # noqa: E402 -- same reason (pipelines/)
import reflect_probe_asm  # noqa: E402 -- same reason

GAME_EXE = Path(os.environ.get(
    "LD_GAME_EXE", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\Warhammer3.exe"))


class RuledNumbers(unittest.TestCase):
    def test_take_off_windows_by_size(self):
        # D3: "越小等越久" -- smaller waits longer; 10 battle ticks a second
        self.assertEqual(air_dive_rules.TAKEOFF_PIN_WINDOWS,
                         {"very_large": 30, "large": 35, "medium": 40, "small": 45})
        self.assertEqual(set(air_dive_rules.TAKEOFF_PIN_WINDOWS), set(air_dive_rules.BODY_SIZES))
        windows = [air_dive_rules.takeoff_pin_window(s) for s in air_dive_rules.BODY_SIZES]
        self.assertEqual(windows, sorted(windows, reverse=True))

    def test_unknown_size_refused(self):
        for size in ("huge", None, "Large"):
            with self.subTest(size=size), self.assertRaises(RuntimeError):
                air_dive_rules.takeoff_pin_window(size)

    def test_reflection_factor(self):
        self.assertEqual(air_dive_rules.REFLECTION_FLYER_DAMAGE_FACTOR, 2.0)


class SizeProbeVerdict(unittest.TestCase):
    FULL = [("small", [0, 0]), ("small", [0, 0]), ("medium", [1, 1]), ("large", [2, 2]),
            ("very_large", [3, 3])]

    def test_holds(self):
        word, why, mapping = size_report.verdict(self.FULL)
        self.assertEqual((word, mapping), ("HOLDS", {"small": 0, "medium": 1, "large": 2, "very_large": 3}))

    def test_refuted(self):
        cases = {
            "two values in one size": self.FULL + [("small", [1, 1])],
            "two sizes one value": [r if r[0] != "medium" else ("medium", [2, 2]) for r in self.FULL],
            "changed between reads": [r if r[0] != "large" else ("large", [2, 5]) for r in self.FULL],
            "not rising with size": [("small", [3, 3]), ("medium", [2, 2]), ("large", [1, 1]),
                                     ("very_large", [0, 0])],
        }
        for name, rows in cases.items():
            with self.subTest(case=name):
                self.assertEqual(size_report.verdict(rows)[0], "REFUTED")

    def test_incomplete_is_not_a_pass(self):
        self.assertEqual(size_report.verdict([r for r in self.FULL if r[0] != "medium"])[0], "INCOMPLETE")
        self.assertEqual(size_report.verdict([(s, v[:1]) for s, v in self.FULL])[0], "INCOMPLETE")
        self.assertEqual(size_report.verdict([])[0], "INCOMPLETE")


class ImpactProbeSites(unittest.TestCase):
    def test_sites_once_at_the_static_addresses(self):
        if not GAME_EXE.is_file():
            raise RuntimeError(f"required installed game exe missing: {GAME_EXE}")
        self.assertEqual(reflect_probe_asm.check_exe(GAME_EXE), reflect_probe_asm.EXE_SITES)

    def test_damage_site_pattern_starts_after_the_take_off_stamp(self):
        # the shipped take-off cave owns the applier's first 10 bytes; the probe's pattern must not
        import pin_cave_asm
        stamp = pin_cave_asm.CAVES["pin_stamp"][0].split()
        stolen = len(pin_cave_asm.CAVES["pin_stamp"][2].split())
        self.assertEqual(stamp[stolen:stolen + 20], reflect_probe_asm.DMG_PATTERN.split()[:20])


if __name__ == "__main__":
    unittest.main()
