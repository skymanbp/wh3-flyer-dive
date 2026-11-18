"""[d10-1118, D4] What "Charge Reflection" is in 9.0, and the probe that finds its damage in a battle.

17 runs showed no impact reflection (rf_refl / rf_brace / rf_act* never entered) while the damage applier
logged ~680 calls a battle. Pinned here:

* the game's own data: the attribute ``charge_reflection`` (its English text: "When bracing, this unit causes
  additional damage when attacking charging enemies"), the kv rules charge_reflect_damage_multiplier = 2 and
  charge_reflect_min_charge_factor_threshold = 0.7, and the control target carrying the attribute;
* the static reading the probe stands on: those two rules are registered at kv-object +0x6610 / +0x6678 (their
  values at +0x60 further: the impact-reflection reads at 0x1430afb24 / 0x1430afb45 show the same +0x60 for
  rules registered at +0x2440 / +0x24a8), and the damage calculator 0x142e5fcb0 reads the values at
  0x142e60052 / 0x142e60091 and multiplies at 0x142e600af;
* the applier's call-site classes cover exactly its 25 call sites in the installed exe;
* the recorder (real file, LuaJIT, byte-backed buffer) writes the D lines' thread and clock and the C lines;
* the report pairs each multiplier with the next damage call on its thread and names the candidate field
  that equals that call's victim; a file without C lines is "not logged".
The caves' emulator check (rf_cgate, rf_cmul, the rf_dmg additions; 28 broken caves) needs keystone + unicorn
and runs in reflect_probe_asm.py before any probe pack is written.
"""
import os
import re
import shutil
import struct
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
import packfile  # noqa: E402 -- because rolepath above puts the tools dir on sys.path
import reflect_probe_asm as rpa  # noqa: E402 -- same reason (pipelines/)
import reflect_probe_report as rrep  # noqa: E402 -- same reason

GAME = Path(os.environ.get("WH3_ROOT", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III"))
EXE, DATA = GAME / "Warhammer3.exe", GAME / "data"
PROBE = TOOLS_DIR / "pipelines" / "reflect_probe.lua"


def need(path):
    if not path.is_file():
        raise AssertionError(f"required input missing: {path}")
    return path


class _Exe:
    pe = None

    @classmethod
    def load(cls):
        if cls.pe is None:
            import pefile
            cls.pe = pefile.PE(str(need(EXE)), fast_load=True)
        return cls.pe

    @classmethod
    def read(cls, va, n):
        pe = cls.load()
        return pe.get_data(va - pe.OPTIONAL_HEADER.ImageBase, n)


class StaticReading(unittest.TestCase):
    def _registration(self, at, field, name):
        # lea rcx,[rsi+field]; mov r9,rbx; mov r8,rdi; lea rdx,[rip+name]
        code = _Exe.read(at, 20)
        self.assertEqual(code[:3], b"\x48\x8d\x8e")
        self.assertEqual(struct.unpack_from("<I", code, 3)[0], field)
        self.assertEqual(code[13:16], b"\x48\x8d\x15")
        target = at + 20 + struct.unpack_from("<i", code, 16)[0]
        self.assertEqual(_Exe.read(target, len(name) + 1), name.encode() + b"\0")

    def test_rules_registered_at_their_fields(self):
        self._registration(0x1405C17AC, 0x6610, "charge_reflect_damage_multiplier")
        self._registration(0x1405C17C5, 0x6678, "charge_reflect_min_charge_factor_threshold")
        self._registration(0x1405C07F3, 0x24A8, "impact_reflection_knockback_chance")

    def test_value_is_sixty_bytes_in(self):
        # the impact reflection reads +0x24a0 (rule at +0x2440: impact_reflection_final_damage_modifier) and
        # +0x2508 (rule at +0x24a8: impact_reflection_knockback_chance)
        self.assertEqual(_Exe.read(0x1430AFB24, 8), bytes.fromhex("F3 0F 10 B0 A0 24 00 00".replace(" ", "")))
        self.assertEqual(_Exe.read(0x1430AFB45, 6), bytes.fromhex("8B B0 08 25 00 00".replace(" ", "")))

    def test_the_calculator_reads_and_multiplies(self):
        self.assertEqual(_Exe.read(0x142E60052, 10), bytes.fromhex("F3410F10BC2470660000"))   # movss xmm7,[r12+0x6670]
        self.assertEqual(_Exe.read(0x142E60091, 10), bytes.fromhex("F3410F10B424D8660000"))   # movss xmm6,[r12+0x66d8]
        self.assertEqual(_Exe.read(0x142E600AF, 5), bytes.fromhex("F3440F59C7"))             # mulss xmm8,xmm7
        self.assertEqual(rpa.EXE_SITES["rf_cmul"], 0x142E600AF)

    def test_applier_classes_cover_every_call_site(self):
        import numpy as np
        pe = _Exe.load()
        base, target, found = pe.OPTIONAL_HEADER.ImageBase, 0x14325A9C4, set()
        for sec in pe.sections:
            if not sec.Characteristics & 0x20000000:
                continue
            a = np.frombuffer(sec.get_data(), dtype=np.uint8)
            at = np.nonzero(a[:-5] == 0xE8)[0]
            disp = (a[at + 1].astype(np.int64) | (a[at + 2].astype(np.int64) << 8)
                    | (a[at + 3].astype(np.int64) << 16) | (a[at + 4].astype(np.int64) << 24))
            disp = np.where(disp >= 2 ** 31, disp - 2 ** 32, disp)
            va = base + sec.VirtualAddress + at
            found |= {int(x) + 5 for x in va[va + 5 + disp == target]}
        self.assertEqual(len(found), 25)
        self.assertEqual(found, set(rpa.APPLIER_CALLS))
        self.assertEqual(rpa.APPLIER_CALLS[rpa.REFLECT_DAMAGE_RETURN], "impact reflection 0x14325bbec")


class GameData(unittest.TestCase):
    @staticmethod
    def _kv():
        out = {}
        with packfile.PackFile.open(str(need(DATA / "db.pack"))) as p:
            for e in p.entries:
                if not e.path.replace("\\", "/").lower().startswith("db/_kv_rules_tables/"):
                    continue
                d, at = p.read_file(e), 0
                if d[:4] == b"\xfd\xfe\xfc\xff":
                    at = 6 + 2 * struct.unpack_from("<H", d, 4)[0]
                if d[at:at + 4] == b"\xfc\xfd\xfe\xff":
                    at += 8
                n, at = struct.unpack_from("<I", d, at + 1)[0], at + 5
                for _ in range(n):
                    ln = struct.unpack_from("<H", d, at)[0]
                    key = d[at + 2:at + 2 + ln].decode()
                    out[key] = struct.unpack_from("<f", d, at + 2 + ln)[0]
                    at += 6 + ln
                if at != len(d):
                    raise AssertionError(f"{e.path} decoded to {at} of {len(d)}")
        if not out:
            raise AssertionError("no _kv_rules table in db.pack")
        return out

    def test_kv_rules(self):
        kv = self._kv()
        self.assertEqual(kv["charge_reflect_damage_multiplier"], 2.0)
        self.assertAlmostEqual(kv["charge_reflect_min_charge_factor_threshold"], 0.7, places=6)
        self.assertEqual(kv["impact_reflection_final_damage_modifier"], 1.0)
        self.assertEqual(kv["impact_reflection_knockback_chance"], 75.0)

    def test_attribute_text(self):
        with packfile.PackFile.open(str(need(DATA / "local_en.pack"))) as p:
            blob = b"".join(p.read_file(e) for e in p.entries if e.path.endswith("unit_attributes__.loc"))
        for needle in ("this unit causes additional damage when attacking charging enemies",
                       "negates the [[img:icon_charge]][[/img]]charge bonus of any large attacker"):
            self.assertIn(needle.encode("utf-16-le"), blob)       # loc records are UTF-16LE at odd offsets too


# ---- the recorder ---------------------------------------------------------------------------------------
HARNESS = r'''
local probe_path = arg[1]
local function u32(v) return string.char(v % 256, math.floor(v / 256) % 256, math.floor(v / 65536) % 256,
    math.floor(v / 16777216) % 256) end
local function u64(v) return u32(v % 4294967296) .. u32(math.floor(v / 4294967296)) end
local NULL = { null = true }
local buf = { mem = {}, text = "0x0000000150000000" }
local function put(off, s) for i = 1, #s do buf.mem[off + i - 1] = s:byte(i) end end
local written = {}
io.open = function() return { write = function(_, s) written[#written + 1] = s end, close = function() end } end
local L = { bytes = 4096, mode_at = 0, magic_at = 8, magic = "RFPROBE3", refl_count_at = 16, refl_ring_at = 64,
    refl_slots = 4, dmg_count_at = 20, dmg_ring_at = 320, dmg_slots = 4, brace_count_at = 24, brace_ring_at = 576,
    brace_slots = 2, brace_entry = 128, act_count_at = 28, act_ring_at = 832, act_slots = 2, entry = 64,
    clock_at = 32, cr_count_at = 36, cr_ring_at = 960, cr_slots = 4, cr_entry = 128 }
package.preload["script/reflect_probe/reflect_probe_site"] = function()
    return { owner = "t", feature = "t", entries = {}, caves = { "rf_dmg" }, layout = L }
end
_G.memreader_plus = {
    patcher = function() return { sites = function() return {
        found = function() return true end, why = function() end,
        install_feature = function() return true end } end } end,
    game_alloc = function() return buf end,
    read = function(p, off, n) local t = {} for i = 0, n - 1 do t[#t + 1] = string.char(p.mem[off + i] or 0) end
        return table.concat(t) end,
    write = function(p, off, s) put(off, s) end,
    uint32 = u32,
    tostring = function(p) return p.text end,
    read_pointer = function() return NULL end, is_null = function() return true end,
    ud_topointer = function() return NULL end,
}
local phases, tick = {}, nil
bm = {
    is_multiplayer = function() return false end,
    alliances = function() return { count = function() return 0 end } end,
    register_phase_change_callback = function(_, name, fn) phases[name] = fn end,
    repeat_callback = function(_, fn) tick = fn end, remove_callback = function() end,
    time_elapsed_ms = function() return 1000 end,
}
dofile(probe_path)
phases.Deployed()
-- one damage call (victim 0xAB00CD01, thread 7, clock 12) and one multiplier (thread 7, clock 11)
local d = L.dmg_ring_at
put(d, u64(0x14326D217)); put(d + 8, u64(0x1AB00CD01)); put(d + 16, u64(0x1EE00FF02)); put(d + 24, u32(40))
put(d + 28, u32(0)); put(d + 32, u32(500)); put(d + 36, u32(1)); put(d + 40, u64(0x1AB00CD01))
put(d + 48, u32(7)); put(d + 52, u32(12)); put(d + 60, u32(1)); put(L.dmg_count_at, u32(1))
local c = L.cr_ring_at
put(c, u64(0x1C0000010)); put(c + 8, u64(0x1D0000020)); put(c + 16, u64(0x142E60306)); put(c + 24, u64(0x1430AF7B4))
put(c + 32, u32(2)); put(c + 36, string.char(0x9A, 0x99, 0x59, 0x3F)); put(c + 40, string.char(0x33, 0x33, 0x33, 0x3F))
put(c + 44, string.char(0, 0, 0, 0x40)); put(c + 48, u32(7)); put(c + 52, u32(11))
put(c + 56, string.char(0, 0, 0xA0, 0x3F)); put(c + 64, u64(0x1AB00CD01)); put(c + 124, u32(1)); put(L.cr_count_at, u32(1))
tick()
for _, chunk in ipairs(written) do io.stdout:write(chunk) end
'''


class Recorder(unittest.TestCase):
    def test_d_and_c_lines(self):
        luajit = shutil.which("luajit")
        if not luajit:
            raise AssertionError("luajit is required to run the recorder (no fallback)")
        with tempfile.TemporaryDirectory() as td:
            h = Path(td) / "h.lua"
            h.write_text(HARNESS, encoding="utf-8")
            proc = subprocess.run([luajit, str(h), str(PROBE)], capture_output=True, text=True, cwd=td)
        self.assertEqual(proc.returncode, 0, proc.stderr[:600])
        lines = proc.stdout.splitlines()
        self.assertFalse([ln for ln in lines if ln.startswith(("STOP", "FAIL"))], lines)
        self.assertIn("D 1000 500 000000014326D217 AB00CD01 EE00FF02 40 0 1 AB00CD01 7 12",
                      lines)
        c = next(ln for ln in lines if ln.startswith("C ")).split()
        self.assertEqual(c[1:7], ["1000", "2", "C0000010", "D0000020", "0000000142E60306", "00000001430AF7B4"])
        self.assertAlmostEqual(rrep.f32(c[7]), 0.85, places=5)
        self.assertEqual((rrep.f32(c[9]), rrep.f32(c[10]), c[11], c[12], c[13]), (2.0, 1.25, "7", "11", "AB00CD01"))
        self.assertTrue(any(ln.startswith("CS 1000 2 0000000142E60306 00000001430AF7B4 n=1") for ln in lines), lines)
        self.assertTrue(any(ln.startswith("S ") and ln.endswith("cr=1 lost_cr=0") for ln in lines), lines)
        # and the report reads the same lines
        on, units, refl, dmg, hp, other = rrep.parse("BATTLE x on: buffer\n" + "\n".join(lines) + "\n")
        out = rrep.charge_reflect_summary(other, dmg, units)
        self.assertTrue(out[0].startswith("CHARGE REFLECT GATE 0 calls"), out)
        self.assertIn("MULTIPLIER APPLIED 1", out[0])
        self.assertTrue(any("multiplier fed: hit processor 0x14326cd24 (melee weapon hit)" in ln for ln in out), out)
        self.assertTrue(any(ln.startswith("CANDIDATES") and "[target+8] 1/1" in ln and "[source+8] 0/1" in ln
                            for ln in out), out)


class Report(unittest.TestCase):
    def test_old_file_is_not_logged(self):
        self.assertEqual(rrep.charge_reflect_summary(["S 1 refl=0 dmg=3"], [], {}),
                         ["CHARGE REFLECT not logged (probe file older than rf_cgate / rf_cmul)"])

    def test_logged_but_never_applied(self):
        out = rrep.charge_reflect_summary(["S 1 refl=0 dmg=3 brace=0 act=0 lost_refl=0 lost_dmg=0 lost_brace=0 "
                                           "lost_act=0 cr=0 lost_cr=0"], [], {})
        self.assertEqual(out[0], "CHARGE REFLECT GATE 0 calls (both of the calculator's tests passed), "
                                 "MULTIPLIER NOT APPLIED 0 calls")

    def test_pairs_on_the_same_thread_only(self):
        dmg = [{"ret": "000000014326D217", "unit": "AA", "victim": "V1", "type": 0, "thread": 9, "clock": 5},
               {"ret": "000000014325BF90", "unit": "BB", "victim": "V2", "type": 0, "thread": 7, "clock": 6}]
        other = ["C 1 2 T S 0000000142E60306 0 3F59999A 3F333333 40000000 3FA00000 7 4 V2 0 0 0",
                 "CS 1 2 0000000142E60306 0 n=1"]
        out = rrep.charge_reflect_summary(other, dmg, {})
        self.assertTrue(any("multiplier fed: impact reflection 0x14325bbec on BB" in ln for ln in out), out)

    def test_call_class(self):
        self.assertEqual(rrep.call_class("0000000143061966"), "impact 0x143061144 (type 5)")
        self.assertEqual(rrep.call_class("00000001400000FF"), "unknown call site")


if __name__ == "__main__":
    unittest.main()
