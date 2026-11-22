"""[d15-1118, D15] The test-only probe for the braced-spear cost of a dive. Pinned here (no keystone needed):

* the marked dive caves (pipelines/dive_mark_asm.py): their buffer fits the rigs dive_cave_asm's own checks
  use, their magic differs from the shipped one, their layout keeps every shipped field, the mark is added
  where the design says (dv_through's air-charge branch arms, every hold that runs the slide window stamps)
  and nowhere else, and importing the module leaves the shipped sources alone;
* the probe pack builder: [stage 5] --reflect refuses a base whose dive site table does not carry the mark and
  dv_cost (D15 ships; the probe only records it), or that has no or two such tables;
* the report's DIVE COST section on synthetic records, and its FAILs on missing or lost records;
* the autotest driver's D15 control key short_m.
The emulator checks of the caves (the shipped cases on the marked caves, the mark's cases, the rf_dmg D15
cases and their mutants) need keystone + unicorn and run in dive_mark_asm.py / reflect_probe_asm.py before
build_probe_pack.py writes anything.
"""
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path
import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import build_probe_pack  # noqa: E402 -- same reason (pipelines/)
import dive_cave_asm  # noqa: E402 -- same reason (pipelines/)
import dive_mark_asm  # noqa: E402 -- same reason (pipelines/)
import reflect_probe_report as rrep  # noqa: E402 -- same reason (pipelines/)


class MarkedCaves(unittest.TestCase):
    def test_buffer_fits_the_shipped_rigs_and_is_not_adopted(self):
        self.assertLessEqual(dive_mark_asm.BYTES, dive_cave_asm.RIG_BUF)          # [D66] the rigs map RIG_BUF (16 KiB)
        self.assertEqual(dive_mark_asm.MARK_AT, dive_cave_asm.BUFFER_BYTES)
        self.assertNotEqual(dive_mark_asm.MAGIC, dive_cave_asm.MAGIC)
        self.assertEqual(len(dive_mark_asm.MAGIC), len(dive_cave_asm.MAGIC))

    def test_layout_keeps_every_shipped_field(self):
        shipped, marked = dive_cave_asm.layout(), dive_mark_asm.layout()
        for k, v in shipped.items():
            if k not in ("bytes", "magic"):
                self.assertEqual(marked[k], v, k)
        self.assertEqual(marked["bytes"], dive_mark_asm.BYTES)

    def test_mark_is_added_where_the_design_says(self):
        for name in dive_cave_asm.CAVES:
            shipped, marked = dive_cave_asm.cave_source(name), dive_mark_asm.cave_source(name)
            arms = "arm_out:" in marked
            stamps = "st_out:" in marked
            self.assertEqual(arms, name == "dv_through", name)
            self.assertEqual(stamps, "whold:" in shipped, name)
            if not arms and not stamps:
                self.assertEqual(marked, shipped, name)
        # the arm sits in the air-charge, not-in-melee branch: after wclr_go, never in the engaged branch
        thr = dive_mark_asm.cave_source("dv_through")
        self.assertLess(thr.index("wclr_go:"), thr.index("arm_out:"))
        self.assertLess(thr.index("arm_out:"), thr.index("wclr_out:"))
        # a hold never claims an entry: the stamp's table search has no compare-exchange
        keep = dive_mark_asm.cave_source("dv_keep")
        stamp = keep[keep.index("whold:"):keep.index("st_out:")]
        self.assertNotIn("cmpxchg qword", stamp)
        self.assertIn(f"cmp dword ptr [r9 + {dive_cave_asm.FLYMODE_OFF:#x}], 0", stamp)

    def test_shipped_sources_untouched(self):
        self.assertIs(dive_cave_asm.cave_source, dive_mark_asm._SHIPPED_SOURCE)
        self.assertEqual(dive_cave_asm.STEP_FACTOR, 1)
        self.assertTrue(dive_cave_asm.check_site_file())


class ProbePack(unittest.TestCase):
    def test_base_must_carry_d15(self):
        shipped = (TOOLS_DIR.parent / build_probe_pack.DIVE_SITE).read_bytes()
        eleven = b"\n".join(ln for ln in shipped.splitlines() if b"dv_reflect" not in ln and b"reflect_word_at" not in ln)
        for entries in ([("script/other.lua", b"")],
                        [(build_probe_pack.DIVE_SITE, shipped), (build_probe_pack.DIVE_SITE.replace("/", "\\"), shipped)],
                        [(build_probe_pack.DIVE_SITE, eleven)]):
            with self.assertRaises(SystemExit) as cm:
                build_probe_pack.require_d15_site(entries)
            self.assertIn("REFUSING", str(cm.exception))
        ok = [(build_probe_pack.DIVE_SITE.replace("/", "\\"), shipped)]
        self.assertIs(build_probe_pack.require_d15_site(ok), ok)


def _d(ms, tick, dtype, verdict, v318=0x69, att="A1000020", fly="A1000020", mark=2, age=21, att_unit="F0000001",
       size=4, a_max=9400, a_hp=9100, victim="5A000001", vunit="5B000001"):
    def h(v):
        return f"{v & 0xFFFFFFFF:08X}"
    return (f"D {ms} {tick} 0000000143061966 {victim} {vunit} 30 {dtype} 0 00000000 7 {ms} "
            f"{h(v318)} {h(verdict)} {att} {fly} {h(1200)} {h(950)} {h(a_max)} {h(a_hp)} {h(mark)} {h(age)} "
            f"{att_unit} {h(size)}")


GOOD = [
    "BATTLE x on: buffer 0000000150000000",
    "MARK on: dive buffer 00007FF4DFFA0010, window 30 ticks, braced state 0x69",
    "UNIT 1002 1 wh2_main_hef_mon_star_dragon obj=F0000001 men=1 flyer=1",
    "UNIT 1007 2 wh_main_emp_inf_spearmen_1 obj=5B000001 men=120 flyer=0",
    "M 30000 300 1 A1000020 F0000001 00000000",
    "M 33000 330 2 A1000020 F0000001 0000001E",
    _d(33100, 331, 5, 1, age=1),
    "M 33100 331 3 A1000020 F0000001 00000001",
    _d(33200, 332, 6, 5, mark=3, age=2),
    _d(40000, 400, 0, 0, mark=0xFFFFFFFF, age=0xFFFFFFFF),
    "S 40000 refl=0 dmg=4 brace=0 act=0 lost_refl=0 lost_dmg=0 lost_brace=0 lost_act=0 cr=0 lost_cr=0 mark=3 "
    "lost_mark=0",
]


def _report(lines):
    on, units, refl, dmg, hp, other = rrep.parse("\n".join(lines) + "\n")
    return rrep.dive_cost_summary(on, units, dmg, other)


class DiveCostReport(unittest.TestCase):
    def test_complete_record(self):
        out, problems = _report(GOOD)
        self.assertEqual(problems, [])
        text = "\n".join(out)
        self.assertIn("ATTACKER IDENTITY on type-5 / 6 calls: N=2; attacker is the flying entity 2/2", text)
        self.assertIn("DIVE COST wh2_main_hef_mon_star_dragon uid 1002: marks armed 1, stamped 1, spent 1, expired 0",
                      text)
        self.assertIn("touchdown model A1000020 tick 330 (30 ticks after its arm)", text)
        # the second contact in the same dive (verdict 5) and the type-0 hit are not costs
        self.assertEqual(text.count("would-be cost:"), 1, text)
        share = air_dive_rules.DIVE_COST_SHARE["very_large"]
        self.assertIn(f"would-be cost: model A1000020 tick 331 (1 ticks after touchdown), soldier 5A000001 of "
                      f"wh_main_emp_inf_spearmen_1 (+0x318 0x69, older record), model health 9100 / 9400 "
                      f"(size very_large), cost "
                      f"{share * 9400:.0f} ({share:.0%})", text)
        self.assertIn(f"models paying within {air_dive_rules.DIVE_COST_WINDOW_TICKS} ticks: 1 of 1 seen; cost "
                      f"{share * 9400:.0f} of 9400 = {share:.1%}", text)

    def test_rider_counts_as_rider(self):
        lines = [ln if not ln.startswith("D 33100") else _d(33100, 331, 5, 1, att="A1000010", age=1) for ln in GOOD]
        out, _problems = _report(lines)
        self.assertIn("attacker is the flying entity 1/2, a rider of one 1/2", "\n".join(out))

    def test_fails_loudly(self):
        cases = {
            "no MARK line": [ln for ln in GOOD if not ln.startswith("MARK")],
            "MARK off": [ln if not ln.startswith("MARK") else "MARK off: no dive caves installed" for ln in GOOD],
            "lost_mark=2": [ln.replace("lost_mark=0", "lost_mark=2") for ln in GOOD],
            "lost_dmg=5": [ln.replace("lost_dmg=0", "lost_dmg=5") for ln in GOOD],
            "no M line": [ln for ln in GOOD if not ln.startswith("M ")],
            "no type-5 / 6 call with a flying attacker": [ln for ln in GOOD if not ln.startswith("D ")]
            + [_d(1, 1, 0, 0)],
            "D lines without the D15 fields": [ln if not ln.startswith("D ") else " ".join(ln.split()[:12])
                                               for ln in GOOD],
            "no S line with mark counts": [ln for ln in GOOD if not ln.startswith("S ")],
        }
        for why, lines in cases.items():
            _out, problems = _report(lines)
            self.assertTrue(any(why in p for p in problems), (why, problems))
        self.assertEqual(_report(GOOD)[1], [])


class Driver(unittest.TestCase):
    def test_short_charge_key(self):
        text = (TOOLS_DIR / "pipelines" / "air_dive_autotest.lua").read_text("utf-8")
        self.assertIn("cfg.short_m, cfg.short_ms = 0, 20000", text)
        self.assertIn('status(fmt("short %d ordered ok=%s %s"', text)
        self.assertIn("flying=%s", text)


if __name__ == "__main__":
    unittest.main()
