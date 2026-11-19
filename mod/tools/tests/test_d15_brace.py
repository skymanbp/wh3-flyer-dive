"""[d15-1118 round 3] What "bracing" is in the installed game, and the D15 probe's use of it.

run_d15_cost showed the soldier's +0x318 at 0xc / 0x0 at every contact (never 0x69), so the first bracing test
could not pass. Pinned here from the installed exe and data:

* the damage calculator's attack interface (vtable 0x143ae0278, built by 0x1430a2b78 with [+8] = the entity):
  slot 0x50 is 0x1408fc020 = the entity's +0x68 bit 3, slot 0x38 0x1430b7a44 = a unit attribute test (id 0x27
  through 0x1414755e0), slot 0x48 0x1430b8f38 = the charge-factor test (0x143065f3c);
* the bracing update that sets that bit: 0x143090af0 ``or byte [rbx+0x68], 8`` right before it stores the
  bracing multiplier at +0xbc (0x143090af9: the reflection logger's "+0xbc bracing multiplier" is confirmed);
* the unit's braced fraction +0x3c18 (the share of its entities with +0x68 bit 3, 0x14304e78f) compared with
  unit_braced_status_threshold at 0x143041c4e / 0x143041c56 (kv +0x6740, registered at 0x1405c17de);
* the game data: 129 land units carry charge_reflection, wh_main_emp_inf_spearmen_1 among them and
  wh_main_emp_inf_swordsmen not (the control target); the threshold is 0.75;
* the probe's report: the bracing distribution, the verdicts by reason, the re-charge evidence.
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
import reflect_probe_asm as rpa  # noqa: E402 -- because rolepath above puts pipelines/ on sys.path
import reflect_probe_report as rrep  # noqa: E402 -- same reason
import unit_attributes  # noqa: E402 -- same reason (lib/)

GAME = Path(os.environ.get("WH3_ROOT", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III"))
EXE, DB = GAME / "Warhammer3.exe", GAME / "data" / "db.pack"


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
    def test_interface_vtable(self):
        # 0x1430a2b84: lea rax,[rip+0xa3d6ed] -> 0x143ae0278, stored at [rcx]; [rcx+8] = rdx (the entity)
        code = _Exe.read(0x1430A2B84, 0x1F)
        self.assertEqual(code[:3], b"\x48\x8d\x05")
        self.assertEqual(0x1430A2B8B + struct.unpack_from("<i", code, 3)[0], 0x143AE0278)
        self.assertIn(b"\x48\x89\x51\x08", code)
        slots = {s: struct.unpack("<Q", _Exe.read(0x143AE0278 + s, 8))[0] for s in (0x38, 0x48, 0x50)}
        self.assertEqual(slots, {0x38: 0x1430B7A44, 0x48: 0x1430B8F38, 0x50: 0x1408FC020})
        # slot 0x50: mov rax,[rcx+8]; movzx eax,byte [rax+0x68]; shr al,3; and al,1; ret
        self.assertEqual(_Exe.read(0x1408FC020, 14), bytes.fromhex("488B41080FB64068C0E8032401C3"))
        # slot 0x38: the unit's attribute 0x27 (lea edx,[rax+0x27]; call 0x1414755e0)
        self.assertEqual(_Exe.read(0x1430B7A61, 3), bytes.fromhex("8D5027"))

    def test_bracing_update_sets_the_bit_and_the_multiplier(self):
        # or byte [rbx+0x68],8 ; divss xmm7,xmm9 ; movss [rbx+0xbc],xmm9
        self.assertEqual(_Exe.read(0x143090AF0, 4), bytes.fromhex("804B6808"))
        self.assertEqual(_Exe.read(0x143090AF9, 9), bytes.fromhex("F3440F118BBC000000"))
        self.assertEqual(rpa.BRACE_FLAGS, 0x68)
        self.assertEqual(rpa.BRACED_BIT, 0x8)

    def test_unit_fraction_against_the_threshold(self):
        # movss xmm0,[rax+0x6740] ; comiss xmm0,[rbx+0x3c18] ; setb al
        self.assertEqual(_Exe.read(0x143041C4E, 18), bytes.fromhex("F30F108040670000" "0F2F83183C0000" "0F92C0"))
        # registration: lea rcx,[rsi+0x66e0] (value at +0x60) with the rule's name
        self.assertEqual(_Exe.read(0x1405C17DE, 7), bytes.fromhex("488D8EE0660000"))
        # the unit fraction: movss xmm0,[rdi+0x3c18] after test byte [rcx+0x68],8
        self.assertEqual(_Exe.read(0x14304E789, 4), bytes.fromhex("F6416808"))
        self.assertEqual(rpa.UNIT_BRACED, 0x3C18)


class GameData(unittest.TestCase):
    def test_attribute_set_and_threshold(self):
        units = unit_attributes.units_with_attribute(need(DB), "charge_reflection")
        self.assertEqual(len(units), 129)
        self.assertIn("wh_main_emp_inf_spearmen_1", units)
        self.assertNotIn("wh_main_emp_inf_swordsmen", units)        # the control target
        self.assertEqual(unit_attributes.kv_rules(need(DB))["unit_braced_status_threshold"], 0.75)

    def test_site_table_carries_them(self):
        text = rpa.site_lua({n: b"\x90" for n in rpa.SOURCES}, (["a_unit", "b_unit"], 0.75))
        self.assertIn("    braced_threshold = 0.75,", text)
        self.assertIn("        ['a_unit'] = true,", text)
        self.assertIn("braced_bit = 8", text)


def _d(ms, verdict, v68, mark=2, frac=0.8, att_unit="F0000001", fly="A1000020"):
    h = lambda v: f"{v & 0xFFFFFFFF:08X}"  # noqa: E731 -- because a one-line formatter reads clearer inline
    fb = struct.unpack(">I", struct.pack(">f", frac))[0]
    return (f"D {ms} 1 0000000143061966 5A000001 5B000001 30 5 0 00000000 7 {ms} {h(v68)} {h(verdict)} {h(fb)} "
            f"0000000C {fly} {fly} {h(1200)} {h(950)} {h(9424)} {h(9424)} {h(mark)} 00000001 {att_unit} 00000004")


LINES = [
    "BATTLE x on: buffer 0",
    "MARK on: dive buffer 00007FF4DFFA0010, window 30 ticks",
    "UNIT 1002 1 wh2_main_hef_mon_star_dragon obj=F0000001 men=1 flyer=1",
    "UNIT 1007 2 wh_main_emp_inf_spearmen_1 obj=5B000001 men=120 flyer=0",
    "M 30000 300 1 A1000020 F0000001 00000000",
    "M 32500 325 2 A1000020 F0000001 00000003",
    _d(32500, 3, 0x04, frac=0.2),
    _d(32600, 1, 0x0C, frac=0.9),
    "M 32600 326 3 A1000020 F0000001 00000001",
    _d(32700, 5, 0x0C, mark=3),
    # a multiply inside the window after the stamp (the dive itself) is not a re-charge
    "C 33000 2 E0 E1 0000000142E60306 00000001430B0284 3F800000 3F333333 40000000 3F800000 7 9 A1000020 0 5B 0",
    # a ground re-charge much later: charge-factor multiplies on the dragon, no new arm
    "C 45000 2 E0 E1 0000000142E60306 00000001430B0284 3F800000 3F333333 40000000 3F800000 7 9 A1000020 0 5B 0",
    "C 46000 2 E0 E1 0000000142E60306 00000001430B0284 3F000000 3F333333 40000000 3F800000 7 9 A1000020 0 5B 0",
    "S 47000 refl=0 dmg=3 brace=0 act=0 lost_refl=0 lost_dmg=0 lost_brace=0 lost_act=0 cr=2 lost_cr=0 mark=3 "
    "lost_mark=0",
]


class Report(unittest.TestCase):
    def test_bracing_verdicts_recharge(self):
        on, units, refl, dmg, hp, other = rrep.parse("\n".join(LINES) + "\n")
        out, problems = rrep.dive_cost_summary(on, units, dmg, other, 0.75)
        self.assertEqual(problems, [])
        text = "\n".join(out)
        # the contact after the cost (mark already spent) is not a stamped-mark contact
        self.assertIn("BRACING at 2 contacts with a stamped mark: soldier +0x68 {'bit 3 set': 1, 'bit 3 clear': 1} "
                      "(values {'0x04': 1, '0x0c': 1}); unit +0x3c18 {'<=0.25': 1, '<=1.0': 1}, unit fraction above "
                      "the threshold 0.75: 1/2", text)
        self.assertIn("VERDICTS {'already spent': 1, 'soldier not braced': 1, 'would-be cost': 1}", text)
        # one multiply after the window (factor 1.0); the 0.5 one does not count; one arm in the battle
        self.assertIn("RECHARGE arms 1, multiplies (charge factor >= 0.7) on its models more than 30 ticks after "
                      "its last stamp 1", text)
        self.assertIn("soldier 5A000001 of wh_main_emp_inf_spearmen_1 braced (+0x68 0x0c)", text)

    def test_noattr_lines_counted(self):
        lines = LINES + ["COST on (cost=1)", "XNOATTR 32600 326 1007 wh_main_emp_inf_swordsmen F0000001 A1000020"]
        on, units, refl, dmg, hp, other = rrep.parse("\n".join(lines) + "\n")
        out, problems = rrep.cost_summary(units, dmg, other)
        self.assertEqual(problems, [])
        self.assertIn("COST wh2_main_hef_mon_star_dragon uid 1002: 1 braced contacts skipped, the soldier's unit lacks "
                      "charge_reflection (wh_main_emp_inf_swordsmen)", "\n".join(out))
        out, problems = rrep.cost_summary(units, dmg, [ln for ln in other if not ln.startswith("XNOATTR")])
        self.assertTrue(any("would-be cost verdicts but no cost line" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
