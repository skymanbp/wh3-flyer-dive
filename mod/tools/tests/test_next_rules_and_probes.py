"""update-1117 (user rulings 2026-11-17, docs/DECISIONS.md D3 / D4): the ruled numbers and the
test-only probes that decided (D3) or will decide (D4) how they ship.

* D3: one take-off window per body size (D37: very_large 40, large 45, medium 50, small 55 ticks),
  every battle_entities size covered, an unknown size refused; the engine's size codes as
  measured in game 2026-11-18 (1..4, small .. very large) and the window table the cave reads,
  whose unknown-code slot is the longest window (a model with an unreadable size is never
  let out earlier than any size is);
* D4: the flyer's reflection hit is twice the game's own;
* the size probe's verdict: HOLDS only for one value per size, distinct, rising with size and
  stable between reads; REFUTED / INCOMPLETE otherwise (never a pass on missing data);
* the impact probe's caves sit exactly once in the installed exe, at the addresses of the static
  read (the emulator check needs keystone + unicorn and runs in reflect_probe_asm.py / the probe
  pack build, not here);
* [d3-1118] the impact report tells "the reflection check was never reached" from "the probe file
  is older than that logger" and from "reached, but the reflector was not in state 0x69".
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
    "WH3_GAME_EXE", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\Warhammer3.exe"))


class RuledNumbers(unittest.TestCase):
    def test_take_off_windows_by_size(self):
        # D3: "越小等越久" -- smaller waits longer; 10 battle ticks a second. D37 (owner 2026-11-20): one
        # second more for every size (was 30 / 35 / 40 / 45). The one place the ruled numbers are pinned.
        self.assertEqual(air_dive_rules.TAKEOFF_PIN_WINDOWS,
                         {"very_large": 40, "large": 45, "medium": 50, "small": 55})
        self.assertEqual(set(air_dive_rules.TAKEOFF_PIN_WINDOWS), set(air_dive_rules.BODY_SIZES))
        windows = [air_dive_rules.takeoff_pin_window(s) for s in air_dive_rules.BODY_SIZES]
        self.assertEqual(windows, sorted(windows, reverse=True))

    def test_unknown_size_refused(self):
        for size in ("huge", None, "Large"):
            with self.subTest(size=size), self.assertRaises(RuntimeError):
                air_dive_rules.takeoff_pin_window(size)

    def test_size_codes_as_measured(self):
        # ingame_1118 item2_1 (and item6_1 / item6_2): harpies 1, pegasus 2, manticore 3, star dragon 4
        self.assertEqual(air_dive_rules.TAKEOFF_SIZE_CODES,
                         {"small": 1, "medium": 2, "large": 3, "very_large": 4})

    def test_window_table_the_cave_reads(self):
        by_code = sorted(air_dive_rules.TAKEOFF_SIZE_CODES, key=air_dive_rules.TAKEOFF_SIZE_CODES.get)
        self.assertEqual(air_dive_rules.takeoff_window_table(),
                         [air_dive_rules.TAKEOFF_PIN_WINDOWS[s] for s in by_code]
                         + [max(air_dive_rules.TAKEOFF_PIN_WINDOWS.values())])
        self.assertEqual(air_dive_rules.TAKEOFF_PIN_WINDOW_UNKNOWN_SIZE,
                         max(air_dive_rules.TAKEOFF_PIN_WINDOWS.values()))

    def test_window_table_refuses_bad_codes(self):
        """Negative controls: the table is refused, not built wrong, when the codes are not
        exactly 1..4 over the four sizes."""
        good = dict(air_dive_rules.TAKEOFF_SIZE_CODES)
        bad = {
            "a code missing": {k: v for k, v in good.items() if k != "large"},
            "two sizes one code": {**good, "large": 2},
            "codes from 0": {k: v - 1 for k, v in good.items()},
            "an unknown size": {**good, "huge": 5},
        }
        for name, codes in bad.items():
            with self.subTest(case=name):
                air_dive_rules.TAKEOFF_SIZE_CODES = codes
                try:
                    with self.assertRaises(RuntimeError):
                        air_dive_rules.takeoff_window_table()
                finally:
                    air_dive_rules.TAKEOFF_SIZE_CODES = good

    def test_the_cave_layout_follows_the_rules(self):
        import pin_cave_asm
        self.assertEqual(list(pin_cave_asm.WINDOWS), air_dive_rules.takeoff_window_table())
        lay = pin_cave_asm.layout()
        self.assertEqual(lay["windows"], air_dive_rules.takeoff_window_table())
        self.assertEqual(lay["size_at"], 0x74)
        # the five windows end where the regroup block begins [D23], which ends before the table; no header
        # field overlaps another
        self.assertEqual(lay["windows_at"] + 4 * len(lay["windows"]), lay["regroup_off_at"])
        rg = [lay[k] for k in ("regroup_off_at", "regroup_calls_at", "regroup_skipped_at", "regroup_would_at",
                               "regroup_queued_at", "regroup_unheld_at")]
        self.assertEqual(rg, list(range(rg[0], rg[0] + 4 * len(rg), 4)))
        self.assertLessEqual(rg[-1] + 4, lay["table_at"])
        fields = sorted([lay[k] for k in ("mode_at", "stamps_at", "allowed_at", "dropped_at",
                                          "unmatched_at", "held_at", "free_at", "unsized_at")]
                        + [lay["magic_at"], lay["magic_at"] + 4])
        self.assertEqual(len(fields), len(set(fields)))
        self.assertTrue(all(f < lay["windows_at"] for f in fields))

    def test_dive_cost_numbers(self):
        # [D15] the probe's window and the per-size share; the superseded D4 factor is gone
        self.assertFalse(hasattr(air_dive_rules, "REFLECTION_FLYER_DAMAGE_FACTOR"))
        self.assertEqual(set(air_dive_rules.DIVE_COST_SHARE), set(air_dive_rules.BODY_SIZES))
        self.assertTrue(all(0 < v < 0.5 for v in air_dive_rules.DIVE_COST_SHARE.values()))
        self.assertGreater(air_dive_rules.DIVE_COST_WINDOW_TICKS, 0)


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


class BraceSummary(unittest.TestCase):
    UNITS = {"B19F5B30": {"key": "wh_main_emp_inf_spearmen_1"}}

    def summary(self, lines):
        import reflect_probe_report
        return reflect_probe_report.brace_summary(lines, self.UNITS)

    def test_old_file_is_not_logged_not_unreached(self):
        out = self.summary(["S 1400 refl=0 dmg=0 lost_refl=0 lost_dmg=0"])
        self.assertEqual(out, ["BRACE CHECK not logged (probe file older than rf_brace)"])

    def test_never_reached(self):
        out = self.summary(["S 1400 refl=0 dmg=3 brace=0 act=0 lost_refl=0 lost_dmg=0 lost_brace=0 lost_act=0"])
        self.assertIn("ACTION UPDATES 0 (no soldier ran an action that can call the reflection check)", out)
        self.assertTrue(any(line.startswith("BRACE CHECK NOT REACHED 0 calls") for line in out), out)

    def test_reached_but_not_braced(self):
        out = self.summary(["BS 3400 B19F5B30 00000031 0 2 0000001E n=40",
                            "BS 3400 B19F5B30 00000069 0 1 0000000F n=2",
                            "S 3400 refl=0 dmg=3 brace=42 act=0 lost_refl=0 lost_dmg=0 lost_brace=0 lost_act=0"])
        self.assertTrue(any(line.startswith("BRACE CHECK REACHED 42 calls, reflector in state 0x69 2") for line in out),
                        out)
        self.assertTrue(any('wh_main_emp_inf_spearmen_1: reflector +0x318 0x31 (not 0x69: "Back")' in line
                            for line in out), out)
        self.assertTrue(any('first enemy +0x324 15 ("Interr")' in line for line in out), out)


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
