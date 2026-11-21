"""[D11, gapfix-1118] The take-off gap's fix: the stamp cave raises a 0 countdown before lift-off.

Measured in game (series 4 run 1, traced caves): the flight update asks the take-off check only when the
countdown FC+0x44 is above 0 or the phase FC+0x90 is 1, and lifts a phase-2 model at countdown 0 before that
gate; every melee hit lands after its tick's update. So the stamp cave, when it records a melee hit on a model
in phase 1 or 2 whose countdown is 0, raises the countdown to 1 (lock cmpxchg 0 -> 1): the next update does not
lift, asks the rule, and a "held" answer re-arms it.

What is pinned here (no keystone needed):
* the value and the phases live in air_dive_rules and the cave builder takes them from there;
* the multiplayer marker changed with the rule (FLYPINS5, traced FLYPINT5; since D23 FLYPINS6 / FLYPINT6), in the
  tools and in both site tables;
* the shipped stamp cave's bytes carry exactly one ``lock cmpxchg dword [r8+0x44], edx`` fed by
  ``mov edx, TAKEOFF_GAP_RAISE_TO`` and no plain store to the countdown;
* the report counts hits at countdown 0 in those phases and how many were raised, and turns a hit that should
  have been raised and was not (or the reverse) into a problem line, exit 1.
The emulator proof (the raise cases, the concurrent re-arm, eight broken raise variants) runs in
pin_cave_asm.py / takeoff_trace_asm.py with keystone + unicorn before they write the site tables.
"""
import re
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
import pin_cave_asm  # noqa: E402 -- same reason (pipelines/)
import pin_probe_report as rep  # noqa: E402 -- same reason
import takeoff_trace_asm as tt  # noqa: E402 -- same reason

MOD_DIR = TOOLS_DIR.parent
SITE_FILE = MOD_DIR / air_dive_rules.TAKEOFF_SITE_LUA_PATH
CMPXCHG = "F0 41 0F B1 50 44"           # lock cmpxchg dword ptr [r8 + 0x44], edx


def cave_bytes(text, name):
    m = re.search(rf"name = '{name}',.*?bytes = '([^']*)'", text, re.S)
    assert m, name
    return m.group(1)


class Constants(unittest.TestCase):
    def test_the_rule_values(self):
        self.assertEqual(air_dive_rules.TAKEOFF_GAP_RAISE_TO, 1)
        self.assertEqual(tuple(air_dive_rules.TAKEOFF_GAP_RAISE_PHASES), (1, 2))

    def test_the_cave_takes_them_from_the_rules(self):
        self.assertEqual(pin_cave_asm.RAISE_TO, air_dive_rules.TAKEOFF_GAP_RAISE_TO)
        self.assertEqual(pin_cave_asm.RAISE_PHASES, tuple(air_dive_rules.TAKEOFF_GAP_RAISE_PHASES))
        src = pin_cave_asm.stamp_source()
        for phase in air_dive_rules.TAKEOFF_GAP_RAISE_PHASES:
            self.assertIn(f"cmp eax, {phase}\n        je raise_live", src)
        self.assertIn(f"mov edx, {air_dive_rules.TAKEOFF_GAP_RAISE_TO}\n", src)

    def test_another_value_changes_the_source(self):
        real = pin_cave_asm.RAISE_TO
        pin_cave_asm.RAISE_TO = 2
        try:
            self.assertIn("mov edx, 2\n", pin_cave_asm.stamp_source())
            self.assertNotEqual(pin_cave_asm.source_sha(), _sha_with(real))
        finally:
            pin_cave_asm.RAISE_TO = real


def _sha_with(value):
    real = pin_cave_asm.RAISE_TO
    pin_cave_asm.RAISE_TO = value
    try:
        return pin_cave_asm.source_sha()
    finally:
        pin_cave_asm.RAISE_TO = real


class Marker(unittest.TestCase):
    def test_marker_changed_with_the_rule(self):
        self.assertEqual(pin_cave_asm.MAGIC, b"FLYPINS6")
        self.assertEqual(tt.MAGIC, b"FLYPINT6")
        self.assertIn("magic = 'FLYPINS6'", SITE_FILE.read_text(encoding="utf-8"))
        self.assertIn("magic = 'FLYPINT6'", tt.check_site_file())

    def test_no_old_marker_left_in_the_mod(self):
        for path in list((MOD_DIR / "script").rglob("*.lua")) + list((TOOLS_DIR / "pipelines").glob("*.*")):
            if path.suffix not in (".lua", ".py"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            with self.subTest(path=path.name):
                for old in ("FLYPINS4", "FLYPINT4", "FLYPINS5", "FLYPINT5"):
                    self.assertNotIn(old, text)


class ShippedBytes(unittest.TestCase):
    def test_one_compare_exchange_fed_by_the_raise_value(self):
        text = SITE_FILE.read_text(encoding="utf-8")
        stamp = cave_bytes(text, "pin_stamp")
        self.assertEqual(stamp.count(CMPXCHG), 1, stamp)
        before = stamp[:stamp.index(CMPXCHG)].split()
        want = ["31", "C0", "BA"] + [f"{b:02X}" for b in air_dive_rules.TAKEOFF_GAP_RAISE_TO.to_bytes(4, "little")]
        self.assertEqual(before[-len(want):], want)             # xor eax, eax; mov edx, imm32
        # no plain store to [r8 + 0x44] (mov dword ptr [r8 + 0x44], imm32 = 41 C7 40 44)
        self.assertNotIn("41 C7 40 44", stamp)
        # the hold cave does not touch the countdown
        self.assertNotIn(CMPXCHG, cave_bytes(text, "pin_hold"))

    def test_the_traced_stamp_carries_the_same_raise(self):
        stamp = cave_bytes(tt.check_site_file(), "pin_stamp")
        self.assertEqual(stamp.count(CMPXCHG), 1)


# ---- the report -------------------------------------------------------------------------------------------
LARGE = air_dive_rules.TAKEOFF_SIZE_CODES["large"]


def record(t_lines, mode=1):
    lines = [f"BATTLE 2026-11-18 05:00:00 window=0 mode={mode} table=8192 sample=100 entities=1 trace=1",
             "UNIT 7 1 wh2_dlc10_def_mon_feral_manticore_0 obj=AAAA0000 flyer=1", f"Z 100 7 E1:{LARGE}",
             "E 100 190 7 E1:0:1:100"] + t_lines + ["E 20600 206 7 E1:0:1:30"]
    return "\n".join(lines) + "\n"


class ReportRaise(unittest.TestCase):
    def census(self, text):
        return rep.raise_census(rep.parse(text))

    def test_raised_hits_counted_no_problem(self):
        counts, problems = self.census(record(["T 204 7 E1:u1.0,f1.0,x1.0r", "T 205 7 E1:u2.1,h2.1",
                                               "T 300 7 E1:u2.0,x2.0r", "T 301 7 E1:u2.30,x2.30"]))
        self.assertEqual(counts, {"gap hits": 2, "raised": 2})
        self.assertEqual(problems, [])

    def test_not_raised_in_mode_1_is_a_problem(self):
        counts, problems = self.census(record(["T 204 7 E1:u1.0,f1.0,x1.0", "T 205 7 E1:u2.0,x2.0r"]))
        self.assertEqual(counts, {"gap hits": 2, "raised": 1})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("not raised (x1.0)", problems[0])

    def test_raised_in_mode_2_is_a_problem(self):
        _counts, problems = self.census(record(["T 204 7 E1:u2.0,x2.0r"], mode=2))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("mode 2", problems[0])
        self.assertEqual(self.census(record(["T 204 7 E1:u2.0,x2.0"], mode=2))[1], [])

    def test_raised_outside_the_gap_is_a_problem(self):
        for tok in ("x2.5r", "x3.0r", "x0.0r"):
            with self.subTest(tok=tok):
                counts, problems = self.census(record([f"T 204 7 E1:u2.5,{tok}"]))
                self.assertEqual(counts, {"gap hits": 0, "raised": 0})
                self.assertEqual(len(problems), 1, problems)

    def test_untouched_hits_are_not_counted(self):
        counts, problems = self.census(record(["T 204 7 E1:u2.5,x2.5", "T 205 7 E1:u3.0,x3.0",
                                               "T 206 7 E1:u0.0,x0.0", "T 207 ? ?AB12CD34:x2.0"]))
        self.assertEqual(counts, {"gap hits": 0, "raised": 0})
        self.assertEqual(problems, [])

    def test_render_and_exit_code(self):
        good = record(["T 204 7 E1:u1.0,f1.0,x1.0r"])
        bad = record(["T 204 7 E1:u1.0,f1.0,x1.0"])
        battle = rep.parse(good)
        self.assertIn("RAISE hits at countdown 0 in phase 1/2: 1, raised 1",
                      rep.render(*rep.judge(battle), rep.trace_census(battle), rep.raise_census(battle)[0]))
        with tempfile.TemporaryDirectory() as td:
            g, b = Path(td) / "good.txt", Path(td) / "bad.txt"
            g.write_text(good, encoding="utf-8")
            b.write_text(bad, encoding="utf-8")
            self.assertEqual(rep.main([str(g), "--json"]), 0)
            self.assertEqual(rep.main([str(b), "--json"]), 1)
            self.assertTrue(any("not raised" in p for p in rep.judge(rep.parse(bad))[1]))


if __name__ == "__main__":
    unittest.main()
