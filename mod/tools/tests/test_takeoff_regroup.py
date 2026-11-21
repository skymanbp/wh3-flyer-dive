"""[D23, REGROUP-FIX-1120] The take-off caves' regroup part, outside the emulator.

The machine code, its emulator cases and its broken variants live in ``pipelines/pin_cave_asm.py`` (keystone +
unicorn; run it to regenerate the site table). Here, with the installed game and luajit as required inputs
(missing either is a failure, not a skip):

* the decoding the regroup caves rest on holds in the installed exe (``pin_cave_asm.decode_check``), and each
  of its checks turns red when the reading it guards is wrong (negative proofs);
* the generated site table carries the two caves, their resume offsets and the counters' layout;
* ``lib/takeoff.lua`` gives each cave its own resume address (the regroup caves site + 22, the hold cave
  site + 8, the stamp cave none), still gives every cave the hold's resume for a table of the older form (the
  traced test table), and arms / reads the regroup words.
"""
import os
import re
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
import pin_cave_asm  # noqa: E402 -- same reason (pipelines/)

MOD_DIR = TOOLS_DIR.parent
SITE_FILE = MOD_DIR / air_dive_rules.TAKEOFF_SITE_LUA_PATH
GAME_EXE = Path(os.environ.get("WH3_GAME_EXE", str(pin_cave_asm.EXE)))


def _exe():
    if not GAME_EXE.is_file():
        raise RuntimeError(f"required installed game exe missing: {GAME_EXE}")
    return GAME_EXE


class Decoding(unittest.TestCase):
    def test_the_installed_exe_decodes_as_the_caves_rely_on(self):
        self.assertEqual(pin_cave_asm.decode_check(_exe()), [])

    def test_sites_and_resume_points(self):
        found = pin_cave_asm.check_exe(_exe())
        self.assertEqual((found["pin_regroup1"], found["pin_regroup2"]), (0x142F7F706, 0x142F8FFC4))
        # the skip resumes at the return addresses the call tracer logged for the charge command (D23-RUNS-1120)
        self.assertEqual(found["pin_regroup1"] + pin_cave_asm.RESUME_AT["pin_regroup1"], 0x142F7F71C)
        self.assertEqual(found["pin_regroup2"] + pin_cave_asm.RESUME_AT["pin_regroup2"], 0x142F8FFDA)

    def _broken(self, name, value, want):
        real = getattr(pin_cave_asm, name)
        setattr(pin_cave_asm, name, value)
        try:
            probs = pin_cave_asm.decode_check(_exe())
        finally:
            setattr(pin_cave_asm, name, real)
        self.assertTrue(any(want in p for p in probs), probs)

    def test_negative_resume_one_instruction_early(self):
        # resuming at the call's mov rax,[rcx]: not the done-mark, and it reads rcx the call would have set
        self._broken("REGROUP_SKIP", 13, "is not mov byte ptr [rbx + 0x80], 1")
        self._broken("REGROUP_SKIP", 13, "reads ['rcx']")

    def test_negative_wrong_copy_function(self):
        self._broken("PARAM_COPY", 0x14303FAB4, "is not the parameter copy")

    def test_negative_wrong_mov_rbx(self):
        self._broken("REGROUP_HANDLERS", {"pin_regroup1": (0x142F7F600, 0x142F7F606),
                                          "pin_regroup2": (0x142F8FF54, 0x142F8FF61)}, "no mov rbx, rcx")

    def test_negative_wrong_handler_start(self):
        self._broken("REGROUP_HANDLERS", {"pin_regroup1": (0x142F7F602, 0x142F7F60A),
                                          "pin_regroup2": (0x142F8FF54, 0x142F8FF61)}, "does not start push rbx")


class SiteTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SITE_FILE.read_text(encoding="utf-8")

    def test_caves_resume_and_layout(self):
        self.assertIn("caves = { 'pin_stamp', 'pin_hold', 'pin_regroup1', 'pin_regroup2' },", self.text)
        self.assertIn("resume_at = { pin_hold = 8, pin_regroup1 = 22, pin_regroup2 = 22 },", self.text)
        self.assertIn("regroup_off_at = 64, regroup_calls_at = 68,", self.text)
        self.assertIn("regroup_skipped_at = 72, regroup_would_at = 76,", self.text)
        self.assertIn("regroup_queued_at = 80, regroup_unheld_at = 84,", self.text)
        self.assertIn("table_at = 128, table_slots = 8192,", self.text)
        self.assertNotIn("hold = 'pin_hold'", self.text)

    def test_regroup_bytes_read_the_measured_fields(self):
        for name in ("pin_regroup1", "pin_regroup2"):
            block = re.search(rf"name = '{name}',.*?bytes = '([^']*)'", self.text, re.S).group(1)
            with self.subTest(cave=name):
                self.assertEqual(block.count("{buf:8}"), 1)
                self.assertEqual(block.count("{resume:8}"), 1)
                self.assertIn("88 2F 00 00", block)          # unit +0x2f88, the order count
                self.assertIn("04 01 00 00", block)          # entity +0x104, airborne state
                self.assertIn("E8 02 00 00", block)          # entity +0x2e8, the unit


LUA_HARNESS = r"""
local MOD, FORM = arg[1], arg[2]
package.path = MOD .. "/?.lua;" .. package.path
local mem, next_alloc = {}, 0x10000000
local addresses = { pin_stamp = 0x14325a9c4, pin_hold = 0x143053cfb, pin_regroup1 = 0x142f7f706,
                    pin_regroup2 = 0x142f8ffc4 }
local installed, given_seen = {}, nil
local mr = {}
function mr.game_alloc(n) local a = next_alloc; next_alloc = next_alloc + 0x100000; return a end
function mr.write(p, off, s) for i = 1, #s do mem[p + off + i - 1] = s:byte(i) end end
function mr.read(p, off, n) local t = {} for i = 0, n - 1 do t[#t + 1] = string.char(mem[p + off + i] or 0) end
    return table.concat(t) end
function mr.add(p, o) return p + o end
function mr.tostring(p) return string.format("%X", p) end
function mr.is_null(p) return p == nil or p == 0 end
function mr.uint32(v) local t = {} for i = 1, 4 do t[i] = string.char(v % 256); v = math.floor(v / 256) end
    return table.concat(t) end
function mr.patcher(owner)
    local h = {}
    function h:sites(entries, log)
        local api = {}
        function api.found(name) return true end
        function api.why(name) return nil end
        function api.address(name) return addresses[name] end
        function api.install_feature(feature, given)
            given_seen = given
            for name, g in pairs(given) do installed[name] = g.buf end
            return true
        end
        function api.cave_value(name, ph) if ph == "buf" then return installed[name] end end
        return api
    end
    return h
end
_G.memreader_plus = mr
local site = dofile(MOD .. "/script/campaign/flyer_dive/data/takeoff_site.lua")
if FORM == "old" then          -- the older single-resume form (the traced table's)
    site.resume_at, site.hold = 8, "pin_hold"
end
package.preload["script/campaign/flyer_dive/data/takeoff_site"] = function() return site end
local takeoff = require("script/campaign/flyer_dive/lib/takeoff")
local buf = takeoff.install(function(t) end)
assert(buf, "install failed: " .. tostring(takeoff.state().why))
local names = {}
for name in pairs(given_seen) do names[#names + 1] = name end
table.sort(names)
for _, name in ipairs(names) do
    local g = given_seen[name]
    print(string.format("GIVEN %s buf=%s resume=%s", name, g.buf and "yes" or "no",
        g.resume and string.format("%X", g.resume) or "none"))
end
local l = site.layout
mr.write(buf, l.regroup_skipped_at, mr.uint32(7))
mr.write(buf, l.regroup_calls_at, mr.uint32(9))
takeoff.arm(buf, nil, 1, true)
local c = takeoff.counters(buf)
print(string.format("ARM_OFF mode=%d off=%d calls=%d skipped=%d", c.mode, c.regroup.off, c.regroup.calls,
    c.regroup.skipped))
mr.write(buf, l.regroup_skipped_at, mr.uint32(3))
takeoff.arm(buf)
c = takeoff.counters(buf)
print(string.format("ARM_ON mode=%d off=%d skipped=%d", c.mode, c.regroup.off, c.regroup.skipped))
"""


class LuaInstall(unittest.TestCase):
    def run_lua(self, form):
        luajit = shutil.which("luajit")
        if not luajit:
            raise AssertionError("luajit is required (no fallback)")
        with tempfile.TemporaryDirectory() as td:
            harness = Path(td) / "h.lua"
            harness.write_text(LUA_HARNESS, encoding="utf-8")
            proc = subprocess.run([luajit, str(harness), str(MOD_DIR), form], capture_output=True, text=True,
                                  timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        return proc.stdout.splitlines()

    def test_each_cave_gets_its_own_resume(self):
        out = self.run_lua("new")
        self.assertIn("GIVEN pin_stamp buf=yes resume=none", out)
        self.assertIn(f"GIVEN pin_hold buf=yes resume={0x143053cfb + 8:X}", out)
        self.assertIn(f"GIVEN pin_regroup1 buf=yes resume={0x142f7f71c:X}", out)
        self.assertIn(f"GIVEN pin_regroup2 buf=yes resume={0x142f8ffda:X}", out)

    def test_the_older_form_gives_every_cave_the_hold_resume(self):
        out = self.run_lua("old")
        for name in ("pin_stamp", "pin_hold", "pin_regroup1", "pin_regroup2"):
            self.assertIn(f"GIVEN {name} buf=yes resume={0x143053cfb + 8:X}", out)

    def test_arm_clears_the_counters_and_sets_the_test_word_only_when_asked(self):
        out = self.run_lua("new")
        self.assertIn("ARM_OFF mode=1 off=1 calls=0 skipped=0", out)
        self.assertIn("ARM_ON mode=1 off=0 skipped=0", out)


if __name__ == "__main__":
    unittest.main()
