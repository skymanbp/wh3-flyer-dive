"""[d10-1118, D11] The take-off trace: what the caves saw of each flight entity in each tick, and which
explanation of the take-off gap a record supports.

The gap (docs/STATUS.md, series 3 run 3): a manticore whose countdown had long run out was hit at tick 204,
ordered away at 205 and airborne at 206, earlier than its window. (1) the engine does not ask the take-off
check when the countdown is 0, or (2) the check is asked less often than once per tick.

What is pinned:
* the traced site table (``pipelines/takeoff_trace_site.lua``) was generated from the current traced sources,
  which include the shipped caves' own sha: a change to the shipped caves makes it stale; it names the three
  caves and every shipped anchor, carries the trace layout and a magic of its own, and the installed exe holds
  every site exactly once (pin_tick at the static read's address);
* the recorder (real file, LuaJIT, memory stand-in holding the trace ring byte for byte as the caves write it)
  turns the trace on only when asked, writes T lines grouped by tick and unit in the order of the entries,
  waits for an entry claimed but not yet written, names an FC no living entity carries "?<id>", and says FAIL
  when "trace 1" meets caves without a trace;
* the report explains an early take-off from those lines: (1), (2), both or neither with the reason; and a
  battle recorded with trace=1 but no T line is a problem;
* ``build_pin_on_hit_probe.py --trace-from`` swaps exactly the take-off site table and adds the recorder.
The emulator check of the caves (the shipped check run twice on the traced caves, the trace entries, 17
broken caves) needs keystone + unicorn and runs in takeoff_trace_asm.py before it writes the table.
luajit missing is a failure, not a skip.
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
import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import pin_cave_asm  # noqa: E402 -- same reason (pipelines/)
import pin_probe_report as rep  # noqa: E402 -- same reason
import takeoff_trace_asm as tt  # noqa: E402 -- same reason
from cave_site_cases import loader_pattern_limit  # noqa: E402 -- because it follows the sys.path bootstrap above

PROBE = TOOLS_DIR / "pipelines" / "pin_on_hit_probe.lua"
MOD_DIR = TOOLS_DIR.parent
GAME_EXE = Path(os.environ.get(
    "WH3_GAME_EXE", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III\Warhammer3.exe"))


class TraceSiteTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = tt.check_site_file()

    def test_generated_from_the_current_sources(self):
        self.assertIn(f"source_sha = '{tt.source_sha()}'", self.text)

    def test_stale_when_the_shipped_caves_change(self):
        real = pin_cave_asm.source_sha
        pin_cave_asm.source_sha = lambda: "0" * 64
        try:
            with self.assertRaises(RuntimeError):
                tt.check_site_file()
        finally:
            pin_cave_asm.source_sha = real

    def test_shipped_table_untouched(self):
        self.assertTrue(pin_cave_asm.check_site_file(MOD_DIR))
        shipped = (MOD_DIR / air_dive_rules.TAKEOFF_SITE_LUA_PATH).read_text(encoding="utf-8")
        self.assertNotIn("pin_tick", shipped)
        self.assertNotIn("trace_ring_at", shipped)

    def test_three_caves_every_anchor(self):
        named = re.findall(r"name = '([a-z_]+)', feature = '([a-z_]+)', kind = '([a-z]+)'", self.text)
        want = ([(n, pin_cave_asm.FEATURE, "cave") for n in tt.CAVES]
                + [(n, pin_cave_asm.FEATURE, "anchor") for n in pin_cave_asm.ANCHORS])
        self.assertEqual(named, want)
        self.assertIn("caves = { 'pin_stamp', 'pin_hold', 'pin_tick' },", self.text)
        self.assertIn(f"hold = '{pin_cave_asm.HOLD_NAME}', resume_at = {pin_cave_asm.HOLD_RESUME_AT},", self.text)

    def test_trace_layout_and_own_magic(self):
        self.assertIn(f"trace_on_at = {tt.TRACE_ON_AT}, trace_count_at = {tt.TRACE_COUNT_AT},", self.text)
        self.assertIn(f"trace_ring_at = {tt.TRACE_RING_AT}, trace_entry = 32, trace_slots = {tt.TRACE_SLOTS},",
                      self.text)
        self.assertIn(f"bytes = {tt.BYTES},", self.text)
        self.assertEqual(tt.TRACE_AT, pin_cave_asm.BUFFER_BYTES)        # after the shipped table, not over it
        self.assertIn("magic = 'FLYPINT9'", self.text)
        self.assertNotEqual(tt.MAGIC, pin_cave_asm.MAGIC)
        for win in air_dive_rules.takeoff_window_table():
            self.assertIn(str(win), self.text)

    def test_tick_cave_bytes(self):
        block = self.text[self.text.index("name = 'pin_tick'"):]
        block = block[:block.index("},")]
        self.assertEqual(block.count("{buf:8}"), 1)
        self.assertNotIn("{resume:8}", block)                           # it falls through to the stolen bytes
        self.assertIn(f"pattern = '{tt.TICK_PATTERN}'", block)
        self.assertIn(f"at = {tt.TICK_AT}, expect = '{tt.TICK_STOLEN}'", block)
        self.assertLessEqual(len(tt.TICK_PATTERN.split()), loader_pattern_limit())
        self.assertNotEqual(tt.TICK_PATTERN.split()[0], "??")
        # the bytes start by saving the flags and end by restoring them (every register comes back)
        hexes = block[block.index("bytes = '") + 9:].split("'")[0].split()
        self.assertEqual(hexes[0], "9C")
        self.assertEqual(hexes[-1], "9D")

    def test_every_site_once_in_the_installed_exe(self):
        if not GAME_EXE.is_file():
            self.fail(f"the installed exe is a required input: {GAME_EXE}")
        found = tt.check_exe(GAME_EXE)
        self.assertEqual(found[tt.TICK_NAME], tt.TICK_EXE_SITE)
        self.assertEqual(found["pin_hold"], 0x143053CFB)


# ---- the recorder, run for real ------------------------------------------------------------------------
# the stand-in layout's windows: the ones the shipped table carries (air_dive_rules, D37)
WINDOWS_LUA = "{ " + ", ".join(str(w) for w in air_dive_rules.takeoff_window_table()) + " }"
HARNESS = r'''
local probe_path, cfg_text, with_trace = arg[1], arg[2], arg[3] == "1"
local NULL = { null = true, fields = {} }
local serial = 0
local function ptr(fields)
    serial = serial + 1
    return { fields = fields or {}, text = string.format("0x00000001A%07X", serial * 16) }
end
local function le(text, n)             -- little-endian bytes of the pointer text's low n bytes
    local hex, out = string.sub(text, -16), {}
    for i = 8, 9 - n, -1 do out[#out + 1] = string.char(tonumber(string.sub(hex, 2 * i - 1, 2 * i), 16)) end
    return table.concat(out)
end
local function u32(v) return string.char(v % 256, math.floor(v / 256) % 256, math.floor(v / 65536) % 256,
    math.floor(v / 16777216) % 256) end
local written = {}
io.open = function(path, mode)
    if path == "pin_probe.cfg" then
        local lines, i = {}, 0
        for l in (cfg_text .. "\n"):gmatch("(.-)\n") do if l ~= "" then lines[#lines + 1] = l end end
        if #lines == 0 then return nil end
        return { lines = function() return function() i = i + 1; return lines[i] end end, close = function() end }
    end
    return { write = function(_, s) written[#written + 1] = s end, close = function() end }
end
local buf = ptr()
buf.mem = {}
local function mem_write(off, s)
    for i = 1, #s do local b = s:byte(i); buf.mem[off + i - 1] = (b ~= 0) and b or nil end
end
_G.memreader_plus = {
    read_pointer = function(p, off) return p.fields[off] or NULL end,
    read_int32 = function(p, off) return p.fields[off] or 0 end,
    is_null = function(p) return p.null == true end,
    tostring = function(p) return p.text end,
    ud_topointer = function(u) return u.ud end,
    read = function(p, off, n)
        if not p.mem then return string.rep("\0", n) end
        local out = {}
        for i = 0, n - 1 do out[#out + 1] = string.char(p.mem[off + i] or 0) end
        return table.concat(out)
    end,
    write = function(p, off, s) if p.mem then mem_write(off, s) end end,
    uint32 = u32,
}
local L = { table_slots = 32, entry_bytes = 16, table_at = 0, windows = @WINDOWS@ }
if with_trace then
    L.trace_on_at, L.trace_count_at, L.trace_ring_at, L.trace_entry, L.trace_slots = 1024, 1028, 1088, 32, 8
end
package.preload["script/campaign/flyer_dive/lib/takeoff"] = function()
    return {
        find = function() return buf, true end,
        layout = function() return L end,
        arm = function() end,
        counters = function() return { stamps = 0, dropped = 0, held = 0, free = 0, unsized = 0, unmatched = 0 } end,
        state = function() return {} end,
    }
end
local ticks = ptr({ [0x98] = 1000 })
local battle = ptr({ [0x440] = ticks })
local fc_a = ptr({ [0x90] = 1, [0x44] = 0 })
local ent_a = ptr({ [0x104] = 0, [0x128] = fc_a, [0x58] = battle, [0x74] = 3 })
local stranger_fc = ptr()
local list = ptr({ [0] = ent_a })
local obj = ptr({ [0x3e30] = ptr(), [0x184] = 1, [0x188] = list })
local unit = { ud = ptr({ [8] = obj }) }
function unit:unique_ui_id() return 7 end
function unit:type() return "test_flyer" end
function unit:number_of_men_alive() return 1 end
local one = function(x) return { count = function() return 1 end, item = function() return x end } end
local phases, sampler, ms = {}, nil, 0
bm = {
    alliances = function() return one({ armies = function() return one({ units = function() return one(unit) end }) end }) end,
    register_phase_change_callback = function(_, name, fn) phases[name] = fn end,
    repeat_callback = function(_, fn) sampler = fn end,
    remove_callback = function() end,
    time_elapsed_ms = function() ms = ms + 100; return ms end,
}
-- a cave writes one trace entry: claim (count + 1), seq 0, fields, seq last (``torn``: stop before the fields)
local function cave(key, kind, count, phase, extra, torn)
    local n = 0
    local c = buf.mem
    local raw = ""
    for i = 0, 3 do raw = raw .. string.char(c[L.trace_count_at + i] or 0) end
    n = raw:byte(1) + raw:byte(2) * 256 + raw:byte(3) * 65536
    mem_write(L.trace_count_at, u32(n + 1))
    local at = L.trace_ring_at + (n % L.trace_slots) * 32
    mem_write(at + 28, u32(0))
    if torn then return at, n end
    mem_write(at, le(key.text, 8))
    mem_write(at + 8, u32(ticks.fields[0x98]))
    mem_write(at + 12, u32(count)); mem_write(at + 16, u32(phase)); mem_write(at + 20, u32(kind))
    mem_write(at + 24, u32(extra or 0)); mem_write(at + 28, u32(n + 1))
end
local function finish(at, n, key, kind, count, phase, tick)
    mem_write(at, le(key.text, 8)); mem_write(at + 8, u32(tick))
    mem_write(at + 12, u32(count)); mem_write(at + 16, u32(phase)); mem_write(at + 20, u32(kind))
    mem_write(at + 24, u32(0)); mem_write(at + 28, u32(n + 1))
end
local function hit_table(tick, hits)
    mem_write(0, le(ent_a.text, 8)); mem_write(8, u32(tick)); mem_write(12, u32(hits))
end
dofile(probe_path)
phases.Deployed()
local function step(change)
    ticks.fields[0x98] = ticks.fields[0x98] + 1
    if change then change() end
    sampler()
end
step()                                                                  -- 1001: first sight
if with_trace then
    step(function()                                                     -- 1002: update, check (free), then a hit
        cave(fc_a, 1, 0, 1, 0)
        cave(fc_a, 2, 0, 1, 35)
        cave(ent_a, 6, 0, 1, 1)                                         -- the raised kind (D11)
        hit_table(1002, 1)
        cave(stranger_fc, 1, 7, 2, 0x100)
    end)
    local at, n
    step(function()                                                     -- 1003: phase 2 at countdown 0, no check
        fc_a.fields[0x90] = 2
        cave(fc_a, 1, 0, 2, 0)
        at, n = cave(fc_a, 1, 0, 2, 0, true)                            -- claimed, not yet written
    end)
    step(function()                                                     -- 1004: the torn entry lands; airborne
        finish(at, n, fc_a, 1, 0, 2, 1004)
        ent_a.fields[0x104] = 2; fc_a.fields[0x90] = 3
    end)
else
    step(function() cave = nil end)
end
for _, chunk in ipairs(written) do io.stdout:write(chunk) end
'''


def run(cfg_text, with_trace=True):
    luajit = shutil.which("luajit")
    if not luajit:
        raise AssertionError("luajit is required to run the recorder (no fallback)")
    with tempfile.TemporaryDirectory() as td:
        harness = Path(td) / "harness.lua"
        harness.write_text(HARNESS.replace("@WINDOWS@", WINDOWS_LUA), encoding="utf-8")
        proc = subprocess.run([luajit, str(harness), str(PROBE), cfg_text, "1" if with_trace else "0"],
                              capture_output=True, text=True, cwd=td)
    if proc.returncode != 0:
        raise AssertionError(f"the recorder did not run: {proc.stderr.strip()[:600]}")
    return proc.stdout.splitlines()


class Recorder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = run("entities 1\nsample 100\ntrace 1")

    def test_no_fail(self):
        self.assertFalse([ln for ln in self.lines if ln.startswith("FAIL")], self.lines)
        self.assertTrue(next(ln for ln in self.lines if ln.startswith("BATTLE ")).endswith("entities=1 trace=1"))

    def test_t_lines_in_order_grouped_by_tick(self):
        t = [ln for ln in self.lines if ln.startswith("T ")]
        ent = next(ln for ln in self.lines if ln.startswith("Z ")).split(" ")[3].split(":")[0]
        self.assertEqual([ln for ln in t if " 7 " in ln],
                         [f"T 1002 7 {ent}:u1.0,f1.0,x1.0r", f"T 1003 7 {ent}:u2.0", f"T 1004 7 {ent}:u2.0"], self.lines)

    def test_unknown_fc_named_and_flags(self):
        t = [ln for ln in self.lines if ln.startswith("T ") and " ? " in ln]
        self.assertEqual(len(t), 1, self.lines)
        self.assertRegex(t[0], r"^T 1002 \? \?[0-9A-F]{8}:u2\.7s$")

    def test_summary_counts_the_trace(self):
        s = [ln for ln in self.lines if ln.startswith("S ")]
        self.assertTrue(s and s[0].endswith("trace=0 trace_lost=0"), s)

    def test_the_report_explains_the_gap_as_1(self):
        rows, problems = rep.judge(rep.parse("\n".join(self.lines) + "\n"))
        gaps = [g for r in rows for g in r["gaps"]]
        self.assertEqual(len(gaps), 1, (rows, problems))
        self.assertEqual(gaps[0]["verdict"], "(1) not asked when the countdown is 0", gaps[0])
        self.assertEqual(gaps[0]["last_hit"], 1002)

    def test_trace_off_by_default(self):
        lines = run("entities 1\nsample 100")
        self.assertFalse([ln for ln in lines if ln.startswith(("T ", "FAIL"))], lines)
        self.assertTrue(next(ln for ln in lines if ln.startswith("BATTLE ")).endswith("entities=1"))
        self.assertFalse([ln for ln in lines if "trace=" in ln], lines)

    def test_trace_asked_without_traced_caves_fails_loudly(self):
        lines = run("entities 1\ntrace 1", with_trace=False)
        self.assertTrue([ln for ln in lines if ln.startswith("FAIL trace 1 asked")], lines)
        self.assertFalse([ln for ln in lines if ln.startswith("T ")], lines)


# ---- the report on synthetic records ---------------------------------------------------------------------
LARGE = air_dive_rules.TAKEOFF_SIZE_CODES["large"]


def record(t_lines, trace_header=True):
    head = ("BATTLE 2026-11-18 05:00:00 window=0 mode=1 table=8192 sample=100 entities=1"
            + (" trace=1" if trace_header else ""))
    lines = [head, "UNIT 7 1 wh2_dlc10_def_mon_feral_manticore_0 obj=AAAA0000 flyer=1", f"Z 100 7 E1:{LARGE}",
             "E 100 190 7 E1:0:1:100", "H 20500 205 E1:204:1"]
    lines += t_lines
    lines += ["E 20500 205 7 E1:0:2:0", "E 20600 206 7 E1:2:3:0"]
    return "\n".join(lines) + "\n"


def gap(text):
    rows, problems = rep.judge(rep.parse(text))
    gaps = [g for r in rows for g in r["gaps"]]
    assert len(gaps) == 1, (rows, problems)
    return gaps[0], problems


class Explain(unittest.TestCase):
    def test_1_not_asked_at_countdown_0(self):
        g, _p = gap(record(["T 203 7 E1:u1.0,f1.0", "T 204 7 E1:u1.0,f1.0,x1.0", "T 205 7 E1:u2.0",
                            "T 206 7 E1:u2.0"]))
        self.assertEqual(g["verdict"], "(1) not asked when the countdown is 0")
        self.assertIn("205 u2.0", g["reason"])
        self.assertEqual(g["sequence"][0], "203: u1.0,f1.0")

    def test_2_a_tick_without_update(self):
        g, _p = gap(record(["T 204 7 E1:u1.0,f1.0,x1.0", "T 206 7 E1:u2.0"]))
        self.assertTrue(g["verdict"].startswith("both") or g["verdict"].startswith("(2)"), g)
        self.assertIn("ticks without an update: [205]", g["reason"])

    def test_2_the_gate_skipped_an_ask(self):
        g, _p = gap(record(["T 204 7 E1:u1.0,f1.0,x1.0", "T 205 7 E1:u1.0", "T 206 7 E1:u2.5"]))
        self.assertEqual(g["verdict"], "(2) asked less often than once per tick", g)
        self.assertIn("205 u1.0", g["reason"])

    def test_neither_when_asked_after_the_hit_and_answered_free(self):
        g, _p = gap(record(["T 204 7 E1:u1.0,x1.0", "T 205 7 E1:u1.0,f1.0", "T 206 7 E1:u2.0"]))
        self.assertEqual(g["verdict"], "neither")
        self.assertIn("answered free", g["reason"])

    def test_neither_when_unmatched(self):
        g, _p = gap(record(["T 204 7 E1:u1.0,x1.0", "T 205 7 E1:u1.0,f1.0!u", "T 206 7 E1:u2.0"]))
        self.assertEqual(g["verdict"], "neither")
        self.assertIn("could not judge", g["reason"])

    def test_the_hit_is_cut_where_it_happened_in_its_tick(self):
        # the ask before the hit in the hit's own tick is not an ask after the hit
        g, _p = gap(record(["T 204 7 E1:u1.0,f1.0,x1.0", "T 205 7 E1:u2.0", "T 206 7 E1:u2.0"]))
        self.assertEqual(g["verdict"], "(1) not asked when the countdown is 0")

    def test_unexplained_without_trace(self):
        g, problems = gap(record([]))
        self.assertEqual(g["verdict"], "unexplained")
        self.assertIn("trace=1 but has no T line", " ".join(problems))

    def test_census(self):
        per_tick, gate = rep.trace_census(rep.parse(record(
            ["T 203 7 E1:u1.0,f1.0", "T 204 7 E1:u1.0,f1.0,x1.0", "T 205 7 E1:u2.0", "T 207 7 E1:u2.30,h2.30"])))
        self.assertEqual(per_tick, {0: 1, 1: 4, 2: 0})
        self.assertEqual(gate, {"should, asked": 3, "should, not asked": 0, "should not, asked": 0,
                                "should not, not asked": 1})


# ---- the pack builder -----------------------------------------------------------------------------------
class TraceBuilder(unittest.TestCase):
    def _pack(self, td, entries):
        import packfile
        path = Path(td) / "base.pack"
        packfile.write_pack_file(str(path), entries, packfile.PACK_TYPE_MOD)
        return path

    def test_swaps_the_site_table_and_adds_the_recorder(self):
        import build_pin_on_hit_probe as pin
        with tempfile.TemporaryDirectory() as td:
            base = self._pack(td, [(air_dive_rules.TAKEOFF_SITE_LUA_PATH, b"return {}\n"),
                                   ("script/battle/mod/flyer_takeoff.lua", b"-- entry\n")])
            out = dict(pin.trace_entries(base))
        self.assertEqual(out[air_dive_rules.TAKEOFF_SITE_LUA_PATH],
                         tt.check_site_file().replace("\r\n", "\n").encode("utf-8"))
        self.assertEqual(out["script/battle/mod/flyer_takeoff.lua"], b"-- entry\n")
        self.assertIn(pin.PROBE_PACK_PATH, out)

    def test_refuses_without_the_site_table_or_with_the_recorder(self):
        import build_pin_on_hit_probe as pin
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit):
                pin.trace_entries(self._pack(td, [("script/x.lua", b"x")]))
            with self.assertRaises(SystemExit):
                pin.trace_entries(self._pack(td, [(air_dive_rules.TAKEOFF_SITE_LUA_PATH, b"r"),
                                                  (pin.PROBE_PACK_PATH, b"p")]))

    def test_refuses_a_shipped_name(self):
        import build_pin_on_hit_probe as pin
        with self.assertRaises(SystemExit):
            pin.main(["--out", "flyer_dive_takeoff.pack", "--trace-from", "x.pack"])


if __name__ == "__main__":
    unittest.main()
