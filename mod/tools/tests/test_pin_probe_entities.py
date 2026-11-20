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
local probe_path, cfg_text, ring_hex = arg[1], arg[2], arg[3] or ""
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
    patcher = function() return { sites = function() return { found = function() return true end,
        why = function() return "" end, install_feature = function() return true end } end } end,
    game_alloc = function() return _G.memreader_plus_calls end,
    write = function() end,
    uint32 = function(v) return string.char(v % 256, 0, 0, 0) end,
    read = function(p, off, n)        -- p.bytes[off] = the bytes stored there (the rest reads as zero)
        local b = p.bytes and p.bytes[off] or ""
        return (b .. string.rep("\0", n)):sub(1, n)
    end,
}
-- [D23-RUNS-1120] the call tracer, installed for real through a stand-in patcher; its buffer holds the bytes
-- the test passes as hex (counter at +16, call counters at +24, the ring at +64)
local function unhex(h) return (h:gsub("..", function(x) return string.char(tonumber(x, 16)) end)) end
local calls_buf = ptr({})
calls_buf.bytes = {}
if ring_hex ~= "" then
    local raw = unhex(ring_hex)
    calls_buf.bytes[16], calls_buf.bytes[24], calls_buf.bytes[64] = raw:sub(1, 4), raw:sub(5, 40), raw:sub(41)
end
package.preload["script/regroup_trace/regroup_trace_site"] = function()
    return { owner = "regroup_trace", feature = "regroup_trace", entries = {}, caves = { "rt_task1", "rt_mktask" },
        layout = { bytes = 320, mode_at = 0, magic_at = 8, magic = "RGTRACE1", count_at = 16, calls_at = 24,
            ring_at = 64, slots = 2, entry = 128 } }
end
_G.memreader_plus_calls = calls_buf
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
-- the order queue: empty at first; from step 3 one order at head 2 (unit +0x2a0 + 2 * 0x120 = +0x4e0)
obj.bytes = { [0x4e0] = "\x90\x96\xad\x43\x01\x00\x00\x00" .. "\x44\x33\x22\x11" .. string.rep("\0", 0x30)
    .. "\x05\x00\x00\x00", [0x3ca8] = "\0" }
local unit = { ud = ptr({ [8] = obj }) }
function unit:is_idle() return (obj.fields[0x2f88] or 0) == 0 end
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
step(function() fc_a.fields[0x90] = 2; fc_a.fields[0x44] = 30      -- 3: asked to take off (and an order)
    obj.fields[0x2f88] = 1; obj.fields[0x2f8c] = 2 end)
step(function() fc_a.fields[0x44] = 29; obj.fields[0x2f8c] = 40 end)  -- 4: only the countdown moved (head out of range)
step(function() ent_a.fields[0x104] = 2; fc_a.fields[0x90] = 3; fc_a.fields[0x44] = 0   -- 5: airborne
    obj.fields[0x2f8c] = 2 end)
print("PERIOD " .. tostring(period))
for _, chunk in ipairs(written) do io.stdout:write(chunk) end
'''


def run(cfg_text, ring_hex=""):
    luajit = shutil.which("luajit")
    if not luajit:
        raise AssertionError("luajit is required to run the recorder (no fallback)")
    with tempfile.TemporaryDirectory() as td:
        harness = Path(td) / "harness.lua"
        harness.write_text(HARNESS, encoding="utf-8")
        proc = subprocess.run([luajit, str(harness), str(PROBE), cfg_text, ring_hex], capture_output=True, text=True,
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

    def test_order_lines(self):
        """[D23-RUNS-1120] one O line right after each Q line: the order queue's count / head, the order at head
        (vtable, serial +8, +0x3c), unit +0x3ca8 and the script's is_idle; '-' when empty or out of range."""
        lines = run("entities 1\nsample 100\ntrack 1")
        self.assertFalse([ln for ln in lines if ln.startswith("FAIL")], lines)
        o = [ln.split(" ") for ln in lines if ln.startswith("O ")]
        self.assertEqual(len(o), 5, lines)
        for i, ln in enumerate(lines):
            if ln.startswith("Q "):
                self.assertTrue(lines[i + 1].startswith("O " + " ".join(ln.split(" ")[1:4]) + " "), lines[i:i + 2])
        self.assertEqual(o[0][3:], ["7", "n=0", "head=0", "vt=-", "sn=-", "a3c=-", "busy=00", "idle=1"])
        self.assertEqual(o[2][3:], ["7", "n=1", "head=2", "vt=0000000143ad9690", "sn=11223344", "a3c=00000005",
                                    "busy=00", "idle=0"])
        self.assertEqual(o[3][4:7], ["n=1", "head=40", "vt=-"])
        self.assertEqual(o[4][6], "vt=0000000143ad9690")

    def test_call_lines_of_the_task_caves(self):
        """[D23-RUNS-1120] G lines of kinds 7 (task) and 9 (creator) carry the 128-byte entries' extension, the GC
        line all nine counters; the report parses them back with every field."""
        import struct
        import sys
        sys.path.insert(0, str(PROBE.parent))
        import regroup_trace_report as rep

        def entry(seq, kind, rcx, ent, ret, rdx, aux, ext):
            head = struct.pack("<QQQIIQQIIII", rcx, ent, ret, 486, kind, rdx, aux, 2, 0, 1, seq + 1)
            return head + ext + bytes(128 - len(head) - len(ext))
        task = entry(0, 7, 0x77770000, 0xB3AC45D0, 0x142F6B847, 0x5000, 0x143AD9690,
                     struct.pack("<QQQIIII", 0x11112222, 0xC0FFEE00, 0xA0A0A0A0, 4, 0, 0x41200000, 0x1234))
        mk = entry(1, 9, 0xB3AC45D0, 0xB3AC45D0, 0x143123456, 0x7000, 0xC0FFEE00,
                   struct.pack("<7Q", 1, 2, 3, 0xC0FFEE00, 5, 0xA0A0A0A0, 0))
        counters = struct.pack("<9I", 3, 0, 1, 0, 1, 1, 1, 0, 1)
        lines = run("entities 1\nsample 100\ntrack 1\ncalls 1", (struct.pack("<I", 2) + counters + task + mk).hex())
        self.assertFalse([ln for ln in lines if ln.startswith("FAIL")], lines)
        self.assertIn("CALLS on: caves installed", lines)
        g = [ln for ln in lines if ln.startswith("G ")]
        self.assertEqual(len(g), 2, lines)
        self.assertEqual(g[0].split(" ")[3], "7")
        self.assertTrue(g[0].endswith(" t18=0000000011112222 t58=00000000c0ffee00 t68=00000000a0a0a0a0 f74=00000004 "
                                      "f80=00000000 t84=41200000 sn=00001234"), g[0])
        self.assertTrue(g[1].endswith(" p00=0000000000000001 p08=0000000000000002 p10=0000000000000003 "
                                      "p18=00000000c0ffee00 p20=0000000000000005 p28=00000000a0a0a0a0 "
                                      "p30=0000000000000000"), g[1])
        gc = next(ln for ln in lines if ln.startswith("GC "))
        self.assertTrue(gc.endswith("land=3 cancel=0 target=1 stay=0 order=1 stub=1 task1=1 task2=0 mktask=1 lost=0"),
                        gc)
        rec, problems = rep.parse("\n".join(lines))
        self.assertEqual(problems, [])
        kinds = {x["kind"]: x for x in rec["g"]}
        self.assertEqual(set(kinds[7]["ext"]), set(rep.TASK_KEYS))
        self.assertEqual(set(kinds[9]["ext"]), set(rep.MK_KEYS))
        self.assertEqual((kinds[7]["ret"], kinds[7]["aux"], kinds[7]["rcx"]), (0x142F6B847, 0x143AD9690, "77770000"))
        self.assertTrue(all(k in rec["gc"] for k in rep.GC_KEYS))

    def test_track_off_by_default(self):
        lines = run("entities 1\nsample 100")
        self.assertFalse([ln for ln in lines if ln.startswith(("Q ", "P ", "C ", "M ", "O "))], lines)

    def test_off_by_default(self):
        lines = run("window 0")
        self.assertFalse([ln for ln in lines if ln.startswith(("E ", "Z "))], lines)
        self.assertIn("PERIOD 200", lines)
        battle = [ln for ln in lines if ln.startswith("BATTLE ")]
        self.assertEqual(len(battle), 1)
        self.assertTrue(battle[0].endswith("sample=200 entities=0"), battle)


if __name__ == "__main__":
    unittest.main()
