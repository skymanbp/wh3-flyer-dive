"""[d15-1118, maintainer] The test-only cost step of the D15 probe: reflect_probe.lua sums the would-be costs
(verdict 1 on the damage logger's entries) of one flyer unit per recorder tick and, with cost=1 in the autotest
command file, calls the game's unit:reduce_hitpoints_unary(p, false) once for that unit, p = summed shares /
unit:initial_number_of_men(). Run in LuaJIT against a stub battle (the unit object records its calls):

* two paying models of one unit in one tick -> one call with the summed p, then one XA reading per tick;
* switch off -> no call, an XOFF line with the same numbers;
* p above the per-call ceiling, or a unit too weak to keep its sliver -> no call, an XREF line;
* no unit object for the paying unit -> no call, a loud XERR line.
Then mutated recorders that must each fail one of those cases. The report's COST section is in
test_d15_probe.py's style below (FAILs on a call without an effect and on verdicts without a call).
"""
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
import reflect_probe_report as rrep  # noqa: E402 -- because rolepath above puts pipelines/ on sys.path

PROBE = TOOLS_DIR / "pipelines" / "reflect_probe.lua"

HARNESS = r'''
local probe_path, case = arg[1], arg[2]
local function u32(v) return string.char(v % 256, math.floor(v / 256) % 256, math.floor(v / 65536) % 256,
    math.floor(v / 16777216) % 256) end
local function u64(v) return u32(v % 4294967296) .. u32(math.floor(v / 4294967296)) end
local buf = { mem = {}, text = "0x0000000150000000" }
local function put(off, s) for i = 1, #s do buf.mem[off + i - 1] = s:byte(i) end end
local written = {}
local cmd_text = (case == "off") and "scenario=charge\n" or "dist=250\ncost=1\n"
io.open = function(name, mode)
    if mode == "r" then
        if name ~= "flyer_dive_autotest_cmd.txt" then return nil end
        return { lines = function() return cmd_text:gmatch("[^\n]+") end, close = function() end }
    end
    return { write = function(_, s) written[#written + 1] = s end, close = function() end }
end
local L = { bytes = 4096, mode_at = 0, magic_at = 8, magic = "RFPROBE4", refl_count_at = 16, refl_ring_at = 64,
    refl_slots = 4, dmg_count_at = 20, dmg_ring_at = 320, dmg_slots = 4, dmg_entry = 128, dive_at = 40,
    cost_window = 30, braced = 105, brace_count_at = 24, brace_ring_at = 960,
    brace_slots = 2, brace_entry = 128, act_count_at = 28, act_ring_at = 1216, act_slots = 2, entry = 64,
    clock_at = 32, cr_count_at = 36, cr_ring_at = 1344, cr_slots = 4, cr_entry = 128,
    cost_share = { 0.03, 0.03, 0.03, case == "big" and 1.5 or 0.03 }, cost_max_call = 0.5, cost_keep = 0.03,
    cost_follow = 2 }
package.preload["script/reflect_probe/reflect_probe_site"] = function()
    return { owner = "t", feature = "t", entries = {}, caves = { "rf_dmg" }, layout = L }
end
local calls, hp = {}, (case == "low") and 0.02 or 0.8
local unit = {
    unique_ui_id = function() return 1005 end, type = function() return "wh_main_brt_cav_pegasus_knights" end,
    number_of_men_alive = function() return 2 end, initial_number_of_men = function() return 4 end,
    unary_hitpoints = function() return hp end, is_in_melee = function() return true end,
    reduce_hitpoints_unary = function(_, p, hide) calls[#calls + 1] = { p, hide }; hp = hp - p end,
}
local one = function(x) return { count = function() return 1 end, item = function() return x end } end
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
    ud_topointer = function() return { text = "00000001BB00CC03" } end,
    read_pointer = function(p, off) if off == 8 then return p end return { text = "1" } end,
    is_null = function(p) return p.null == true end,
}
local phases, tick = {}, nil
bm = {
    is_multiplayer = function() return false end,
    alliances = function() return one({ armies = function() return one({ units = function() return one(unit) end })
        end }) end,
    register_phase_change_callback = function(_, name, fn) phases[name] = fn end,
    repeat_callback = function(_, fn) tick = fn end, remove_callback = function() end,
    time_elapsed_ms = function() return 1000 end,
}
dofile(probe_path)
phases.Deployed()
-- two paying models of one flyer unit (verdict 1, size code 4) in one tick
local attacker_unit = (case == "missing") and 0x1DEAD0001 or 0x1BB00CC03
for s = 0, 1 do
    local d = L.dmg_ring_at + s * L.dmg_entry
    put(d, u64(0x143061966)); put(d + 8, u64(0x15A000001 + s)); put(d + 16, u64(0x15B000001))
    put(d + 24, u32(30)); put(d + 28, u32(5)); put(d + 32, u32(500 + s)); put(d + 56, u32(0x69)); put(d + 60, u32(1))
    put(d + 72, u64(0x1A1000010 + s)); put(d + 80, u64(0x1A1000010 + s)); put(d + 112, u64(attacker_unit))
    put(d + 120, u32(4)); put(d + 124, u32(s + 1))
end
put(L.dmg_count_at, u32(2))
tick()
tick()
tick()
for _, chunk in ipairs(written) do io.stdout:write(chunk) end
for _, c in ipairs(calls) do io.stdout:write(string.format("CALL %.6f %s\n", c[1], tostring(c[2]))) end
'''

CASES = ("on", "off", "big", "low", "missing")


def run(probe_text, case):
    luajit = shutil.which("luajit")
    if not luajit:
        raise AssertionError("luajit is required to run the recorder (no fallback)")
    with tempfile.TemporaryDirectory() as td:
        h, p = Path(td) / "h.lua", Path(td) / "probe.lua"
        h.write_text(HARNESS, encoding="utf-8")
        p.write_text(probe_text, encoding="utf-8")
        proc = subprocess.run([luajit, str(h), str(p), case], capture_output=True, text=True, cwd=td)
    if proc.returncode != 0:
        return None, proc.stderr[:400]
    return proc.stdout.splitlines(), ""


def problems(case, lines):
    """[why] the recorder's lines for ``case`` break the contract (empty: they keep it)."""
    if lines is None:
        return ["the harness did not run"]
    calls = [ln for ln in lines if ln.startswith("CALL ")]
    xs = [ln for ln in lines if ln.split()[:1] == ["X"]]
    out = []
    if not any(ln == ("COST on (cost=1)" if case != "off" else "COST off (no cost=1 in flyer_dive_autotest_cmd.txt)")
               for ln in lines):
        out.append("COST line")
    if case == "on":
        if calls != ["CALL 0.015000 false"]:
            out.append(f"calls {calls}")
        if xs != ["X 1000 501 1005 wh_main_brt_cav_pegasus_knights 2 0.015000 0.015000 0.800000 2 4"]:
            out.append(f"X lines {xs}")
        xa = [ln for ln in lines if ln.startswith("XA ")]
        if xa != ["XA 1000 1005 1 0.785000 2", "XA 1000 1005 2 0.785000 2"]:
            out.append(f"XA lines {xa}")
    else:
        if calls:
            out.append(f"calls {calls}")
        want = {"off": "XOFF 1000 501 1005 wh_main_brt_cav_pegasus_knights 2 0.015000 0.015000 0.800000 2 4",
                "big": "XREF 1000 501 1005 wh_main_brt_cav_pegasus_knights 2 0.750000 0.750000 0.800000 2 4",
                "low": "XREF 1000 501 1005 wh_main_brt_cav_pegasus_knights 2 0.015000 -0.010000 0.020000 2 4",
                "missing": "XERR 1000 501 DEAD0001 no unit object: the cost of 2 models not applied"}[case]
        if want not in lines:
            out.append(f"no line {want!r}: {[ln for ln in lines if ln.startswith('X')]}")
    return out


class CostStep(unittest.TestCase):
    def test_cases(self):
        text = PROBE.read_text("utf-8")
        for case in CASES:
            lines, err = run(text, case)
            self.assertEqual(problems(case, lines), [], (case, err))

    MUTANTS = (
        ("calls once per model", "    tally = {}\nend\n", "end\n"),
        ("ignores the switch", "            elseif not cost_on then\n", "            elseif false then\n"),
        ("no ceiling", " or want > l.cost_max_call then", " then"),
        ("alive instead of initial", "init = u.unit:initial_number_of_men()", "init = u.unit:number_of_men_alive()"),
        ("hides bodies", "u.unit:reduce_hitpoints_unary(p, false)", "u.unit:reduce_hitpoints_unary(p, true)"),
        ("no sliver kept", "local p = math.min(want, before - l.cost_keep)", "local p = want"),
        ("missing unit silent", '            emit(fmt("XERR %d %d %s no unit object', '            (fmt("XERR %d %d %s no unit object'),
        ("no reading after", '        emit(fmt("XA %d %s %d %.6f %d"', '        (fmt("XA %d %s %d %.6f %d"'),
        ("switch default on", 'local cost_on, cost_why = false,', 'local cost_on, cost_why = true,'),
    )

    def test_mutants_fail(self):
        text = PROBE.read_text("utf-8").replace("\r\n", "\n")
        survivors = []
        for label, old, new in self.MUTANTS:
            self.assertEqual(text.count(old), 1, label)
            mutated = text.replace(old, new)
            if not any(problems(case, run(mutated, case)[0]) for case in CASES):
                survivors.append(label)
        self.assertEqual(survivors, [])


def _x(kind, ms, tick, p, before, uid="1005", key="wh2_main_hef_mon_star_dragon", n=1, init=1):
    return f"{kind} {ms} {tick} {uid} {key} {n} {p:.6f} {p:.6f} {before:.6f} 1 {init}"


def _d(ms, verdict, vunit="F0000001", victim="A1000020", dmg=0, att_unit="F0000001"):
    h = lambda v: f"{v & 0xFFFFFFFF:08X}"  # noqa: E731 -- because a one-line formatter reads clearer inline
    return (f"D {ms} 1 0000000143061966 {victim} {vunit} {dmg} 5 1 {victim} 7 {ms} 00000069 {h(verdict)} "
            f"A1000020 A1000020 {h(9400)} {h(9100)} {h(9400)} {h(9100)} 00000002 00000001 {att_unit} 00000004")


BASE = ["BATTLE x on: buffer 0", "UNIT 1005 1 wh2_main_hef_mon_star_dragon obj=F0000001 men=1 flyer=1",
        "COST on (cost=1)"]


class CostReport(unittest.TestCase):
    def _summary(self, lines):
        on, units, refl, dmg, hp, other = rrep.parse("\n".join(BASE + lines) + "\n")
        return rrep.cost_summary(units, dmg, other)

    def test_call_with_effect(self):
        out, probs = self._summary([_d(33000, 1), _x("X", 33000, 330, 0.03, 0.9),
                                    "XA 33100 1005 1 0.870000 1", "XA 33200 1005 2 0.870000 1"])
        self.assertEqual(probs, [])
        text = "\n".join(out)
        self.assertIn("COST wh2_main_hef_mon_star_dragon uid 1005: calls 1, p requested 0.0300, measured drop 0.0300",
                      text)

    def test_call_without_effect_fails(self):
        _out, probs = self._summary([_d(33000, 1), _x("X", 33000, 330, 0.03, 0.9),
                                     "XA 33100 1005 1 0.900000 1", "XA 33200 1005 2 0.900000 1"])
        self.assertTrue(any("no health change" in p for p in probs), probs)

    def test_verdicts_without_call_fail(self):
        _out, probs = self._summary([_d(33000, 1)])
        self.assertTrue(any("verdicts but no cost line" in p for p in probs), probs)

    def test_ordinary_damage_is_subtracted(self):
        out, probs = self._summary([_d(33000, 1), _x("X", 33000, 330, 0.03, 0.9), _d(33050, 0, dmg=94),
                                    "XA 33100 1005 1 0.860000 1"])
        self.assertEqual(probs, [])
        self.assertIn("ordinary damage in the windows 94 (0.0100 of the unit), attributable 0.0300",
                      "\n".join(out))

    def test_errors_and_switch_off(self):
        _out, probs = self._summary([_d(33000, 1), "XERR 33000 330 DEAD0001 no unit object: x"])
        self.assertTrue(any("XERR" in p for p in probs), probs)
        on, units, refl, dmg, hp, other = rrep.parse("\n".join(
            [BASE[0], BASE[1], "COST off (no cost=1 in flyer_dive_autotest_cmd.txt)", _d(33000, 1),
             _x("XOFF", 33000, 330, 0.03, 0.9)]) + "\n")
        out, probs = rrep.cost_summary(units, dmg, other)
        self.assertEqual(probs, [])
        self.assertIn("would-have calls 1", "\n".join(out))


if __name__ == "__main__":
    unittest.main()
