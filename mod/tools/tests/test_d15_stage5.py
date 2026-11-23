"""[d15-1118 stage 5] The D15 report after the first two in-game cost runs (series4 d15_brace_spear / _sword).

Two defects the spear run showed, pinned on small synthetic records:
* two calls on one unit 100 ms apart, the health drop arriving 200 ms after each call: the first call was judged
  on the one reading before the second call and failed "no health change";
* the cost's own application (an applier call of type 2 with no attacker on a model of the paying unit) was
  counted as ordinary damage, so every COST line said "attributable 0.0000".

And, read from the installed exe: the bracing update sets +0x68 bit 3 without looking at any enemy. [D51] D15's
cost (dv_cost, lib/dive_cost.lua) is removed; in its place what dv_reflect rests on: the engine's reflection
multiply, the gates before it, the jump past it, and the getter the cave calls on the struck charger; and the
battle entry's wiring of the factor word.
"""
import os
import struct
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path
import reflect_probe_report as rrep  # noqa: E402 -- because rolepath above puts pipelines/ on sys.path
import dive_reflect_asm  # noqa: E402 -- same reason

GAME = Path(os.environ.get("WH3_ROOT", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III"))
EXE = GAME / "Warhammer3.exe"

UNIT = "B2E690B0"


def h(v):
    return f"{v & 0xFFFFFFFF:08X}"


def d_line(ms, victim, damage, dtype, attacker, v_max=261, v_hp=261, verdict=0, unit=UNIT, att_unit="00000000"):
    """a 26-token D line (round 3 layout)"""
    return (f"D {ms} {ms // 100} 00000001430BE1D0 {victim} {unit} {damage} {dtype} 1 {victim} 5864 1 "
            f"00000011 {h(verdict)} 00000000 00000000 {attacker} {attacker} {h(v_max)} {h(v_hp)} "
            f"FFFFFFFF FFFFFFFF FFFFFFFF FFFFFFFF {att_unit} FFFFFFFF")


BASE = [
    "BATTLE x on: buffer 0",
    "COST on (cost=1)",
    f"UNIT 1005 1 wh_main_brt_cav_pegasus_knights obj={UNIT} men=24 flyer=1",
    "UNIT 1010 2 wh_main_emp_inf_spearmen_1 obj=B2FAC190 men=120 flyer=0",
    # two calls 100 ms apart; each recorder tick prints one XA per pending call (duplicates by ms)
    "X 88200 881 1005 wh_main_brt_cav_pegasus_knights 1 0.001250 0.001250 1.000000 24 24",
    "XA 88300 1005 1 1.000000 24",
    "X 88300 882 1005 wh_main_brt_cav_pegasus_knights 1 0.001250 0.001250 1.000000 24 24",
    "XA 88400 1005 2 0.998723 24",
    "XA 88400 1005 1 0.998723 24",
    d_line(88400, "B31FCD00", 7, 2, "00000000"),
    d_line(88400, "B29557A0", 1, 2, "00000000"),
    "XA 88500 1005 3 0.997446 24",
    "XA 88500 1005 2 0.997446 24",
    d_line(88500, "B31FCD00", 7, 2, "00000000", v_hp=254),
    d_line(88500, "B29557A0", 1, 2, "00000000", v_hp=260),
    "XA 88600 1005 4 0.997446 24",
    "XA 88600 1005 3 0.997446 24",
    "XA 88700 1005 5 0.997446 24",
    "XA 88700 1005 4 0.997446 24",
    "XA 88800 1005 5 0.997446 24",
]


def run(lines):
    on, units, refl, dmg, hp, other = rrep.parse("\n".join(lines) + "\n")
    out, problems = rrep.cost_summary(units, dmg, other)
    return "\n".join(out), problems


class OverlappingCalls(unittest.TestCase):
    def test_two_calls_100_ms_apart_pass(self):
        text, problems = run(BASE)
        self.assertEqual(problems, [])
        self.assertIn("calls 2, p requested 0.0025, measured drop 0.0026", text)

    def test_a_call_with_no_drop_in_its_whole_window_still_fails(self):
        flat = [ln.replace("0.998723", "1.000000").replace("0.997446", "1.000000") for ln in BASE]
        _text, problems = run(flat)
        self.assertTrue(any("call at 88200, 88300 ms (p 0.0025) and no health change in 6 readings" in p
                            for p in problems), problems)

    def test_a_drop_after_the_window_does_not_count(self):
        late = [ln for ln in BASE if not ln.startswith("XA")] + [
            "XA 88300 1005 1 1.000000 24", "XA 88800 1005 5 1.000000 24", "XA 88900 1005 5 0.990000 24"]
        _text, problems = run(late)
        self.assertTrue(any("no health change" in p for p in problems), problems)


class OwnApplication(unittest.TestCase):
    def test_own_hits_are_not_ordinary_damage(self):
        text, _problems = run(BASE)
        self.assertIn("the cost's own applications 16, ordinary damage in the windows 0 (0.0000 of the unit), "
                      "attributable 0.0026", text)
        self.assertIn("OWN calls at 88200, 88300 ms: p 0.0025 of 24 x 261 = 15.7 wanted; applied 16 on 2 model(s): "
                      "B31FCD00 (max 261) 7 at 88400 ms, B29557A0 (max 261) 1 at 88400 ms", text)
        self.assertIn("outside every call's window: 0", text)

    def test_a_hit_with_an_attacker_stays_ordinary(self):
        lines = BASE + [d_line(88600, "B31FCD00", 30, 0, "B2FBC100")]
        text, _problems = run(lines)
        self.assertIn("the cost's own applications 16, ordinary damage in the windows 30", text)
        # an enemy's type-2 (ability) hit has an attacker: ordinary, not the cost's own
        lines = BASE + [d_line(88600, "B31FCD00", 12, 2, "B2FBC100")]
        text, _problems = run(lines)
        self.assertIn("the cost's own applications 16, ordinary damage in the windows 12", text)

    def test_a_stray_own_hit_is_listed(self):
        lines = BASE + [d_line(99000, "B31FCD00", 5, 2, "00000000")]
        text, _problems = run(lines)
        self.assertIn("outside every call's window: 1 (wh_main_brt_cav_pegasus_knights 5 at 99000)", text)


def need(path):
    if not path.is_file():
        raise AssertionError(f"required input missing: {path}")
    return path


class _Exe:
    pe = None

    @classmethod
    def read(cls, va, n):
        if cls.pe is None:
            import pefile
            cls.pe = pefile.PE(str(need(EXE)), fast_load=True)
        return cls.pe.get_data(va - cls.pe.OPTIONAL_HEADER.ImageBase, n)


class StaticReading(unittest.TestCase):
    def test_bracing_update_reads_no_enemy(self):
        # 0x143090a39..0x143090af0: attributes 3 / 4 of the soldier's own unit (+0x36c8), then the kv rules, then
        # "or byte [rbx+0x68], 8" -- no position, no other entity is read on the way
        code = _Exe.read(0x143090A39, 0x143090AF4 - 0x143090A39)
        self.assertTrue(code.endswith(bytes.fromhex("804B6808")))
        for pos in (bytes([0x88, 0, 0, 0]), bytes([0x90, 0, 0, 0])):       # +0x88 / +0x90 displacements
            self.assertNotIn(pos, code)

    def test_reflection_multiply(self):
        # [D51] the block 0x142e6004c..0x142e600af of the damage calculator 0x142e5fcb0
        self.assertEqual(_Exe.read(0x142E60052, 10), bytes.fromhex("F3410F10BC2470660000"))   # xmm7 = kv +0x6670
        self.assertEqual(_Exe.read(dive_reflect_asm.EXE_SITE, 5), dive_reflect_asm.REPLACED)  # mulss xmm8, xmm7
        self.assertEqual(_Exe.read(0x142E600B4, 3), bytes.fromhex("4084ED"))                  # test bpl, bpl next
        # the striker not braced jumps past the multiply (je 0x142e600b4), the charge factor below the threshold
        # jumps away (jb 0x142e6028a): the multiply runs only when every engine gate held
        self.assertEqual(_Exe.read(0x142E60089, 2), bytes.fromhex("7429"))
        self.assertEqual(0x142E6008B + 0x29, 0x142E600B4)
        self.assertEqual(_Exe.read(0x142E600A9, 2), bytes.fromhex("0F82"))
        self.assertEqual(0x142E600AF + struct.unpack("<i", _Exe.read(0x142E600AB, 4))[0], 0x142E6028A)
        # the getter: rdi->vfunc[+8], for the participant vtable 0x143ae0278 mov rax, [rcx + 8]; ret
        self.assertEqual(_Exe.read(0x142E600B9, 9), bytes.fromhex("488B07488BCFFF5008"))      # the engine calls it
        getter = struct.unpack("<Q", _Exe.read(0x143AE0278 + 8, 8))[0]
        self.assertEqual(getter, 0x1408D9B70)
        self.assertEqual(_Exe.read(getter, 5), dive_reflect_asm.GET_PLAIN)


class BattleEntry(unittest.TestCase):
    def test_reflect_wired(self):
        text = (TOOLS_DIR.parent / "script" / "battle" / "mod" / "flyer_dive.lua").read_text("utf-8")
        for needle in ("dive.set_brace(buffer, brace_rule.word(site.brace, s), brace_rule.reflect_word(site.brace, s))",
                       'bm:register_phase_change_callback("Deployed", function() read_brace("Deployed") end)',
                       "c.released, c.committed, c.closed, c.sped, c.ended, c.capped, c.engaged_body, c.braced, c.brace_repeat, "
                       "c.brace_noslot,\n        c.reflected)"):
            self.assertIn(needle, text)
        # [D64] one formatter (counts) for NOW and END
        self.assertEqual(text.count("c.brace_noslot,\n        c.reflected)"), 1)
        self.assertEqual(text.count("record(\"NOW \" .. line)"), 1)
        self.assertEqual(text.count("record(\"END \" .. counts(c))"), 1)
        self.assertNotIn("dive_cost", text)


if __name__ == "__main__":
    unittest.main()
