"""The take-off recorder's per-entity lines (E), run for real in LuaJIT against a stand-in for game memory.

The recorder is test-only and reads memory through memreader Plus; here every pointer is a Lua table with the
fields the recorder reads, so the file itself runs unchanged: Deployed -> start() -> the sampling callback.
What is pinned:

* with ``entities 1`` an E line is written when an entity's airborne flag (+0x104) or its flight controller's
  phase (+0x90) changes, and NOT when only the countdown (+0x44) moves -- the line would otherwise be written
  every tick of every countdown;
* an entity without a controller is written with "-" and does not stop the record;
* each flyer's body size codes (+0x74) are written once (Z), with the same ids as the E lines;
* without the key no E line is written and the sampling period stays 200 ms (the record of earlier runs);
* ``sample <ms>`` is the period handed to the battle manager.

luajit missing is a failure, not a skip: a recorder nobody ran is not a recorder.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "pipelines" / "pin_on_hit_probe.lua"

HARNESS = r'''
local probe_path, cfg_text = arg[1], arg[2]
local NULL = { null = true, fields = {} }
local serial = 0
local function ptr(fields)
    serial = serial + 1
    return { fields = fields or {}, text = string.format("0x00000001A%07X", serial * 16) }
end
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
_G.memreader_plus = {
    read_pointer = function(p, off) return p.fields[off] or NULL end,
    read_int32 = function(p, off) return p.fields[off] or 0 end,
    read_float = function(p, off) return p.fields[off] or 0 end,
    is_null = function(p) return p.null == true end,
    tostring = function(p) return p.text end,
    ud_topointer = function(u) return u.ud end,
    read = function(_, _, n) return string.rep("\0", n) end,
}
package.preload["script/campaign/flyer_dive/lib/takeoff"] = function()
    return {
        find = function() return ptr(), true end,
        layout = function() return { table_slots = 32, entry_bytes = 16, table_at = 0, windows = { 45, 40, 35, 30, 45 } } end,
        arm = function() end,
        counters = function() return { stamps = 0, dropped = 0, held = 0, free = 0, unsized = 0, unmatched = 0 } end,
        state = function() return {} end,
    }
end
-- one flyer unit, two flight entities; the second has no flight controller
local ticks = ptr({ [0x98] = 1000 })
local battle = ptr({ [0x440] = ticks })
local fc_a = ptr({ [0x90] = 1, [0x44] = 0 })
local vt = ptr({})
local cmd = ptr({ [0] = vt })
local ent_a = ptr({ [0x104] = 0, [0x128] = fc_a, [0x58] = battle, [0x74] = 3, [0x88] = 10.5, [0x90] = -3.5,
    [0x8c] = 1.5, [0x324] = 1, [0x330] = cmd })
local ent_b = ptr({ [0x104] = 0, [0x58] = battle, [0x74] = 3 })
local list = ptr({ [0] = ent_a, [8] = ent_b })
local ctl = ptr({})
local obj = ptr({ [0x3e30] = ctl, [0x184] = 2, [0x188] = list })
local unit = { ud = ptr({ [8] = obj }) }
function unit:unique_ui_id() return 7 end
function unit:type() return "test_flyer" end
function unit:number_of_men_alive() return 2 end
function unit:position() return { get_x = function() return 10.5 end, get_z = function() return -3.5 end,
    get_y = function() return 1.5 end } end
function unit:is_moving() return true end
function unit:is_in_melee() return false end
function unit:is_currently_flying() return true end
local one = function(x) return { count = function() return 1 end, item = function() return x end } end
local phases, sampler, period, ms = {}, nil, nil, 0
bm = {
    alliances = function() return one({ armies = function() return one({ units = function() return one(unit) end }) end }) end,
    register_phase_change_callback = function(_, name, fn) phases[name] = fn end,
    repeat_callback = function(_, fn, every) sampler, period = fn, every end,
    remove_callback = function() end,
    time_elapsed_ms = function() ms = ms + 100; return ms end,
}
dofile(probe_path)
phases.Deployed()
local function step(change)
    if change then change() end
    ticks.fields[0x98] = ticks.fields[0x98] + 1
    sampler()
end
step()                                                             -- 1: first sight
step()                                                             -- 2: nothing changed
step(function() fc_a.fields[0x90] = 2; fc_a.fields[0x44] = 30 end) -- 3: asked to take off
step(function() fc_a.fields[0x44] = 29 end)                        -- 4: only the countdown moved
step(function() ent_a.fields[0x104] = 2; fc_a.fields[0x90] = 3; fc_a.fields[0x44] = 0 end)   -- 5: airborne
print("PERIOD " .. tostring(period))
for _, chunk in ipairs(written) do io.stdout:write(chunk) end
'''


def run(cfg_text):
    luajit = shutil.which("luajit")
    if not luajit:
        raise AssertionError("luajit is required to run the recorder (no fallback)")
    with tempfile.TemporaryDirectory() as td:
        harness = Path(td) / "harness.lua"
        harness.write_text(HARNESS, encoding="utf-8")
        proc = subprocess.run([luajit, str(harness), str(PROBE), cfg_text], capture_output=True, text=True,
                              cwd=td)
    if proc.returncode != 0:
        raise AssertionError(f"the recorder did not run: {proc.stderr.strip()[:400]}")
    return proc.stdout.splitlines()


class EntityLines(unittest.TestCase):
    def test_written_on_flag_or_phase_change_only(self):
        lines = run("entities 1\nsample 100")
        self.assertFalse([ln for ln in lines if ln.startswith("FAIL")], lines)
        cells = [ln.split(" ")[4:] for ln in lines if ln.startswith("E ")]
        # first sight, asked to take off, airborne; steps 2 and 4 write nothing
        self.assertEqual(len(cells), 3, lines)
        first, asked, airborne = cells
        self.assertEqual([c.split(":")[1:] for c in first], [["0", "1", "0"], ["0", "-", "-"]])
        self.assertEqual(asked[0].split(":")[1:], ["0", "2", "30"])
        self.assertEqual(airborne[0].split(":")[1:], ["2", "3", "0"])
        # the entity without a controller is still in every line
        self.assertTrue(all(c[1].endswith(":0:-:-") for c in cells), cells)

    def test_line_carries_battle_tick_and_unit(self):
        lines = run("entities 1")
        e = [ln.split(" ") for ln in lines if ln.startswith("E ")]
        self.assertEqual([p[3] for p in e], ["7", "7", "7"])
        self.assertEqual([int(p[2]) for p in e], [1001, 1003, 1005])

    def test_body_size_written_once(self):
        lines = run("entities 1")
        z = [ln.split(" ") for ln in lines if ln.startswith("Z ")]
        self.assertEqual(len(z), 1, lines)
        self.assertEqual(z[0][2], "7")
        self.assertEqual([c.split(":")[1] for c in z[0][3:]], ["3", "3"])
        e_ids = [c.split(":")[0] for c in next(ln for ln in lines if ln.startswith("E ")).split(" ")[4:]]
        self.assertEqual([c.split(":")[0] for c in z[0][3:]], e_ids)

    def test_period_is_the_configured_one(self):
        self.assertIn("PERIOD 100", run("entities 1\nsample 100"))
        self.assertIn("PERIOD 200", run("entities 1"))

    def test_track_lines(self):
        lines = run("entities 1\nsample 100\ntrack 1")
        self.assertFalse([ln for ln in lines if ln.startswith("FAIL")], lines)
        q = [ln for ln in lines if ln.startswith("Q ")]
        p = [ln for ln in lines if ln.startswith("P ")]
        self.assertEqual(len(q), 5, lines)
        self.assertEqual(q[0].split(" ")[3:], ["7", "10.5", "-3.5", "1.5", "mv=1", "melee=0", "fly=1", "men=2"])
        self.assertEqual(len(p), 5)
        self.assertEqual(p[0].split(" ")[4].split(":")[1:], ["10.5", "-3.5", "1.5"])
        # M is written once (nothing in it changes), C once (the stand-in controller never changes)
        self.assertEqual(len([ln for ln in lines if ln.startswith("M ")]), 1, lines)
        self.assertEqual(len([ln for ln in lines if ln.startswith("C ")]), 1, lines)
        c = next(ln for ln in lines if ln.startswith("C "))
        self.assertEqual(c.split(" ")[4:], ["00000000"] * 16)
        self.assertTrue(next(ln for ln in lines if ln.startswith("BATTLE ")).endswith("track=1"))

    def test_track_off_by_default(self):
        lines = run("entities 1\nsample 100")
        self.assertFalse([ln for ln in lines if ln.startswith(("Q ", "P ", "C ", "M "))], lines)

    def test_off_by_default(self):
        lines = run("window 0")
        self.assertFalse([ln for ln in lines if ln.startswith(("E ", "Z "))], lines)
        self.assertIn("PERIOD 200", lines)
        battle = [ln for ln in lines if ln.startswith("BATTLE ")]
        self.assertEqual(len(battle), 1)
        self.assertTrue(battle[0].endswith("sample=200 entities=0"), battle)


if __name__ == "__main__":
    unittest.main()
