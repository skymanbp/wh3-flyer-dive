"""[d15-1118 stage 5] The SHIPPED cost of a dive into braced spears: script/campaign/flyer_dive/lib/dive_cost.lua
reads the cave dv_cost's ring (layout and numbers from the generated data/dive_site.lua, the real file) and takes
the share through unit:reduce_hitpoints_unary(p, false), once per flyer unit per tick; lib/dive.lua's arm()
prepares the buffer. Run in LuaJIT against stubs (memreader Plus over a Lua table, a stub battle whose units
record their calls):

* two paying entries of one unit in one tick -> one call, p = summed shares / starting men; the observer's lines;
* no observer (a player's game) -> the same call, no observer lines;
* entries behind the arc / without charge reflection -> no call, counted;
* a share above the per-call ceiling, a unit too weak to keep its sliver -> no call (XREF);
* a unit not in the battle's list -> no call, one log line, no error; a unit that joined later is found again;
* an unknown size code, a call that raises -> no call / logged, tick() does not raise;
* an entry not written yet is read on the next tick; entries overwritten before they were read are counted;
* arm() clears the marks and the cost ring and writes the front-arc switch and cos bytes as the table says.
Then mutated modules that must each fail one of those cases. The report's COST section on synthetic records
follows (its stage-5 defects: tests/test_d15_stage5.py).
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
MOD_DIR = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path
import reflect_probe_report as rrep  # noqa: E402 -- because rolepath above puts pipelines/ on sys.path
import air_dive_rules  # noqa: E402 -- same reason (lib/)

# [D31] the shipped share of a very_large model (size code 4), the one the harness's entries carry; two paying models
# of a unit of four starting men -> p = 2 x SHARE / 4
SHARE = air_dive_rules.DIVE_COST_SHARE["very_large"]
P2 = 2 * SHARE / 4

COST_LUA = MOD_DIR / "script" / "campaign" / "flyer_dive" / "lib" / "dive_cost.lua"
DIVE_LUA = MOD_DIR / "script" / "campaign" / "flyer_dive" / "lib" / "dive.lua"
SITE_LUA = MOD_DIR / "script" / "campaign" / "flyer_dive" / "data" / "dive_site.lua"

HARNESS = r'''
local root, case = arg[1], arg[2]
package.path = root .. "/?.lua;" .. package.path
local site = dofile(root .. "/script/campaign/flyer_dive/data/dive_site.lua")
local l = site.layout
if case == "big" then site.cost.share_by_code[4] = 1.5 end
local function u32(v) return string.char(v % 256, math.floor(v / 256) % 256, math.floor(v / 65536) % 256,
    math.floor(v / 16777216) % 256) end
local function hexbytes(h) local t = {} for i = 15, 1, -2 do t[#t + 1] = string.char(tonumber(h:sub(i, i + 1), 16)) end
    return table.concat(t) end
local buf = { mem = {}, text = "0x0000000150000000" }
local function put(off, s) for i = 1, #s do buf.mem[off + i - 1] = s:byte(i) end end
local function get(off, n) local t = {} for i = 0, n - 1 do t[#t + 1] = string.char(buf.mem[off + i] or 0) end
    return table.concat(t) end
local out = {}
local function say(s) out[#out + 1] = s end
_G.memreader_plus = {
    read = function(p, off, n) local t = {} for i = 0, n - 1 do t[#t + 1] = string.char(p.mem[off + i] or 0) end
        return table.concat(t) end,
    write = function(p, off, s) for i = 1, #s do p.mem[off + i - 1] = s:byte(i) end end,
    uint32 = u32, tostring = function(p) return p.text end,
    ud_topointer = function(u) return { text = u.obj } end,
    read_pointer = function(p, off) if off == 8 then return { text = p.text } end return { text = "1" } end,
    is_null = function(p) return p == nil end,
    patcher = function() return { sites = function() return { found = function() return true end,
        why = function() end, cave_value = function() return nil end } end } end,
}
local mr = _G.memreader_plus
if case == "arm" then
    for off = l.mark_count_at, l.bytes + 15 do buf.mem[off] = 0xEE end
    local dive = require("script/campaign/flyer_dive/lib/dive")
    assert(dive.prepare(function() end), "prepare failed")
    dive.arm(buf)
    local dirty = 0
    for off = l.mark_count_at, l.bytes - 1 do
        if (off < l.cost_arc_on_at or off >= l.cost_arc_cos_at + 4)
                and (off < l.brace_word_at or off >= l.brace_word_at + 4) then
            if (buf.mem[off] or 0) ~= 0 then dirty = dirty + 1 end
        end
    end
    say(("ARM dirty %d, arc on %s, cos %s, brace word %s, after the buffer %d, mode %d"):format(dirty,
        tostring(get(l.cost_arc_on_at, 4) == u32(site.cost.front_arc and 1 or 0)),
        tostring(get(l.cost_arc_cos_at, 4) == site.cost.arc_cos_bytes),
        tostring(get(l.brace_word_at, 4) == u32(site.brace.default_word)), buf.mem[l.bytes] or -1,
        get(l.mode_at, 4):byte(1)))
    io.stdout:write(table.concat(out, "\n") .. "\n")
    return
end
if case ~= "noobserver" then _G.flyer_dive_cost_observer = function(s) say("OBS " .. s) end end
local hp = (case == "low") and 0.02 or 0.8
local flyer = { obj = "00000001BB00CC03",
    unique_ui_id = function() return 1005 end, type = function() return "wh_main_brt_cav_pegasus_knights" end,
    number_of_men_alive = function() return 2 end, initial_number_of_men = function() return 4 end,
    unary_hitpoints = function() return hp end,
    reduce_hitpoints_unary = function(_, p, hide)
        if case == "raise" then error("no such unit") end
        say(("CALL %.6f %s"):format(p, tostring(hide))); hp = hp - p end,
}
local soldiers = { obj = "000000015B000001",
    unique_ui_id = function() return 1007 end, type = function() return "wh_main_emp_inf_spearmen_1" end,
    number_of_men_alive = function() return 120 end, initial_number_of_men = function() return 120 end,
    unary_hitpoints = function() return 1.0 end,
    reduce_hitpoints_unary = function() say("CALL on the soldiers") end,
}
local listed = { soldiers }
if case ~= "missing" and case ~= "remap" then listed[#listed + 1] = flyer end
local bm = { alliances = function() return { count = function() return 1 end, item = function() return {
    armies = function() return { count = function() return 1 end, item = function() return {
        units = function() return { count = function() return #listed end, item = function(_, i) return listed[i] end }
        end } end } end } end } end }
local M = require("script/campaign/flyer_dive/lib/dive_cost")
local c = M.new(mr, buf, site, function(s) say("LOG " .. s) end)
c:map(bm)
if case == "remap" then listed[#listed + 1] = flyer end
local n = 0
local function entry(kind, size, seq, fly)
    local slot = n % l.cost_slots
    local at = l.cost_ring_at + slot * l.cost_entry
    put(at, hexbytes(fly or "00000001A1000010")); put(at + 8, hexbytes("00000001BB00CC03"))
    put(at + 16, hexbytes("000000015B000001")); put(at + 24, u32(501)); put(at + 28, u32(size or 4))
    put(at + 32, u32(0x3F800000)); put(at + 36, u32(kind)); put(at + 40, u32(0x6B)); put(at + 44, u32(seq or n + 1))
    n = n + 1
    put(l.cost_count_at, u32(n))
end
local k = site.cost.kinds
local function tick(ms)
    local ok, err = pcall(c.tick, c, ms, bm)
    if not ok then say("TICK ERROR " .. tostring(err)) end
end
if case == "arc" then entry(k.arc); entry(k.arc)
elseif case == "noattr" then entry(k.no_attribute)
elseif case == "badsize" then entry(k.pay, 9); entry(k.pay, 9)
elseif case == "unwritten" then entry(k.pay); entry(k.pay, 4, 0)
elseif case == "lost" then
    for i = 1, l.cost_slots + 5 do entry(k.arc) end
else entry(k.pay, 4, nil, "00000001A1000010"); entry(k.pay, 4, nil, "00000001A1000011") end
tick(1000)
if case == "unwritten" then put(l.cost_ring_at + 1 * l.cost_entry + 44, u32(2)) end
if case == "missing" then entry(k.pay) end
tick(1100)
tick(1200)
say("COUNTS " .. c:counts())
io.stdout:write(table.concat(out, "\n") .. "\n")
'''

CASES = ("on", "noobserver", "arc", "noattr", "big", "low", "missing", "remap", "badsize", "raise", "unwritten",
         "lost", "arm")
X_ON = f"OBS X 1000 501 1005 wh_main_brt_cav_pegasus_knights 2 {P2:.6f} {P2:.6f} 0.800000 2 4"


def run(cost_text, case, dive_text=None):
    luajit = shutil.which("luajit")
    if not luajit:
        raise AssertionError("luajit is required to run the cost module (no fallback)")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        lib = root / "script" / "campaign" / "flyer_dive" / "lib"
        data = root / "script" / "campaign" / "flyer_dive" / "data"
        lib.mkdir(parents=True)
        data.mkdir(parents=True)
        (lib / "dive_cost.lua").write_text(cost_text, encoding="utf-8")
        (lib / "dive.lua").write_text(dive_text or DIVE_LUA.read_text("utf-8"), encoding="utf-8")
        (lib / "cave_common.lua").write_bytes((DIVE_LUA.parent / "cave_common.lua").read_bytes())
        (data / "dive_site.lua").write_bytes(SITE_LUA.read_bytes())
        h = root / "h.lua"
        h.write_text(HARNESS, encoding="utf-8")
        proc = subprocess.run([luajit, str(h), str(root).replace("\\", "/"), case], capture_output=True, text=True,
                              cwd=td)
    if proc.returncode != 0:
        return None, proc.stderr[:400]
    return proc.stdout.splitlines(), ""


def problems(case, lines):
    """[why] the module's lines for ``case`` break the contract (empty: they keep it)."""
    if lines is None:
        return ["the harness did not run"]
    calls = [ln for ln in lines if ln.startswith("CALL")]
    obs = [ln for ln in lines if ln.startswith("OBS ")]
    counts = next((ln for ln in lines if ln.startswith("COUNTS ")), "")
    out = [f"raised: {ln}" for ln in lines if ln.startswith("TICK ERROR")]
    if case == "arm":
        if lines != ["ARM dirty 0, arc on true, cos true, brace word true, after the buffer 238, mode 1"]:
            out.append(f"arm {lines}")
        return out
    if case in ("on", "noobserver", "remap"):
        if calls != [f"CALL {P2:.6f} false"]:
            out.append(f"calls {calls}")
        if "calls 1, models paid 2," not in counts:
            out.append(f"counts {counts}")
        if not any(ln.startswith(f"LOG COST 1000 ms 1005 wh_main_brt_cav_pegasus_knights: 2 models paid, p {P2:.4f}")
                   for ln in lines):
            out.append("no COST log line")
    if case in ("on", "remap"):
        want = [X_ON, f"OBS XA 1100 1005 1 {0.8 - P2:.6f} 2", f"OBS XA 1200 1005 2 {0.8 - P2:.6f} 2"]
        if [ln for ln in obs if ln.split()[1] in ("X", "XA")] != want:
            out.append(f"observer {obs}")
        if obs.count("OBS XPAY 1000 501 1007 wh_main_emp_inf_spearmen_1 BB00CC03 A1000010 1.0000 6B") != 1:
            out.append(f"no XPAY line {obs}")
    stray = [ln for ln in lines if ln.split()[:1] and ln.split()[0] in ("X", "XA", "XREF", "XERR", "XPAY", "XARC",
                                                                       "XNOATTR")]
    if (case == "noobserver" and obs) or stray:
        out.append(f"observer lines without an observer {obs} {stray}")
    if case not in ("on", "noobserver", "remap", "unwritten") and calls:
        out.append(f"calls {calls}")
    if case == "arc" and ("braced but behind the arc 2," not in counts
                          or sum(ln.startswith("OBS XARC 1000 501 1007") for ln in obs) != 2):
        out.append(f"arc {counts} {obs}")
    if case == "noattr" and ("braced without charge reflection 1," not in counts
                             or "OBS XNOATTR 1000 501 1007 wh_main_emp_inf_spearmen_1 BB00CC03 A1000010" not in obs):
        out.append(f"noattr {counts} {obs}")
    if case == "big" and "OBS XREF 1000 501 1005 wh_main_brt_cav_pegasus_knights 2 0.750000 0.750000 0.800000 2 4" \
            not in obs:
        out.append(f"big {obs}")
    if case == "low" and f"OBS XREF 1000 501 1005 wh_main_brt_cav_pegasus_knights 2 {P2:.6f} -0.010000 0.020000 2 4" \
            not in obs:
        out.append(f"low {obs}")
    if case == "missing":
        logs = [ln for ln in lines if ln.startswith("LOG COST unit 00000001BB00CC03 not resolved")]
        if len(logs) != 1 or "unresolved 3," not in counts:
            out.append(f"missing {logs} {counts}")
        if sum(ln.startswith("OBS XERR") for ln in obs) != 2:
            out.append(f"missing observer {obs}")
    if case == "badsize" and ("unresolved 2," not in counts or not any("size code 9 has no share" in ln
                                                                        for ln in lines)):
        out.append(f"badsize {counts}")
    if case == "raise" and ("failed 2," not in counts or not any("the game's call raised" in ln for ln in lines)):
        out.append(f"raise {counts}")
    if case == "unwritten" and calls != [f"CALL {SHARE / 4:.6f} false", f"CALL {SHARE / 4:.6f} false"]:
        out.append(f"unwritten {calls}")
    if case == "lost" and ("entries lost 5" not in counts or "braced but behind the arc 64," not in counts):
        out.append(f"lost {counts}")
    return out


class ShippedCost(unittest.TestCase):
    def test_cases(self):
        text = COST_LUA.read_text("utf-8")
        for case in CASES:
            lines, err = run(text, case)
            self.assertEqual(problems(case, lines), [], (case, err, lines))

    COST_MUTANTS = (
        ("models not counted", "    t.n = t.n + 1\n", "    t.n = 1\n"),
        ("shares not summed", "if share then t.share = t.share + share", "if share then t.share = share"),
        ("alive instead of initial", "init = unit:initial_number_of_men()", "init = unit:number_of_men_alive()"),
        ("hides bodies", "function() unit:reduce_hitpoints_unary(p, false) end", "function() unit:reduce_hitpoints_unary(p, true) end"),
        ("no sliver kept", "local p = math.min(want, before - self.c.keep)", "local p = want"),
        ("no ceiling", " or want > self.c.max_call then", " then"),
        ("unresolved unit silent", '            self:line(fmt("COST unit %s not resolved', '            (fmt("COST unit %s not resolved'),
        ("a raising call escapes", "local ok, err = pcall(function() unit:reduce_hitpoints_unary(p, false) end)",
         "local ok, err = true, unit:reduce_hitpoints_unary(p, false)"),
        ("unwritten entry read", "        if u32(e, 44) ~= self.seen + 1 then break end      -- not written yet\n", ""),
        ("every kind pays", "        if kind == k.pay then\n", "        if kind then\n"),
        ("no second walk", "        self:map(bm)                    -- a unit that joined", "        -- a unit that joined"),
        ("lost not counted", "        self.n.lost = self.n.lost + (count - self.seen - l.cost_slots)\n", ""),
        ("pays the victim's unit", "            local key = hex64(e, 8)\n", "            local key = hex64(e, 16)\n"),
        ("observer lines in a player's game", "    if type(o) == \"function\" then pcall(o, line) end",
         "    pcall(o or print, line)"),
    )
    DIVE_MUTANTS = (
        ("marks not cleared", "    if l.mark_count_at then mr_().write(buf, l.mark_count_at, ", "    if false then mr_().write(buf, l.mark_count_at, "),
        ("arc switch ignored", "put_u32(buf, l.cost_arc_on_at, site.cost.front_arc and 1 or 0)",
         "put_u32(buf, l.cost_arc_on_at, 0)"),
        ("arc cos not written", "        mr_().write(buf, l.cost_arc_cos_at, site.cost.arc_cos_bytes)\n", ""),
    )

    def test_mutants_fail(self):
        text = COST_LUA.read_text("utf-8").replace("\r\n", "\n")
        dive = DIVE_LUA.read_text("utf-8").replace("\r\n", "\n")
        survivors = []
        for label, old, new in self.COST_MUTANTS:
            self.assertEqual(text.count(old), 1, label)
            mutated = text.replace(old, new)
            if not any(problems(case, run(mutated, case)[0]) for case in CASES):
                survivors.append(label)
        for label, old, new in self.DIVE_MUTANTS:
            self.assertEqual(dive.count(old), 1, label)
            if not problems("arm", run(text, "arm", dive.replace(old, new))[0]):
                survivors.append(label)
        self.assertEqual(survivors, [])


def _x(kind, ms, tick, p, before, uid="1005", key="wh2_main_hef_mon_star_dragon", n=1, init=1):
    return f"{kind} {ms} {tick} {uid} {key} {n} {p:.6f} {p:.6f} {before:.6f} 1 {init}"


def _d(ms, verdict, vunit="F0000001", victim="A1000020", dmg=0, att_unit="F0000001"):
    h = lambda v: f"{v & 0xFFFFFFFF:08X}"  # noqa: E731 -- because a one-line formatter reads clearer inline
    return (f"D {ms} 1 0000000143061966 {victim} {vunit} {dmg} 5 1 {victim} 7 {ms} 00000069 {h(verdict)} "
            f"A1000020 A1000020 {h(9400)} {h(9100)} {h(9400)} {h(9100)} 00000002 00000001 {att_unit} 00000004")


BASE = ["BATTLE x on: buffer 0", "UNIT 1005 1 wh2_main_hef_mon_star_dragon obj=F0000001 men=1 flyer=1",
        "COST shipped: lib/dive_cost.lua, observed"]
PAY = "XPAY 33000 330 1007 wh_main_emp_inf_spearmen_1 F0000001 A1000020 0.9000 6B"


class CostReport(unittest.TestCase):
    def _summary(self, lines, keys=None):
        on, units, refl, dmg, hp, other = rrep.parse("\n".join(BASE + lines) + "\n")
        return rrep.cost_summary(units, dmg, other, keys)

    def test_call_with_effect(self):
        out, probs = self._summary([_d(33000, 1), PAY, _x("X", 33000, 330, 0.03, 0.9),
                                    "XA 33100 1005 1 0.870000 1", "XA 33200 1005 2 0.870000 1"],
                                   {"wh_main_emp_inf_spearmen_1"})
        self.assertEqual(probs, [])
        text = "\n".join(out)
        self.assertIn("COST wh2_main_hef_mon_star_dragon uid 1005: calls 1, p requested 0.0300, measured drop 0.0300",
                      text)
        self.assertIn("dv_cost entries: paid 1 (cos [0.9]), behind the arc 0 (cos []), no charge reflection 0", text)

    def test_call_without_effect_fails(self):
        _out, probs = self._summary([_d(33000, 1), PAY, _x("X", 33000, 330, 0.03, 0.9),
                                     "XA 33100 1005 1 0.900000 1", "XA 33200 1005 2 0.900000 1"])
        self.assertTrue(any("no health change" in p for p in probs), probs)

    def test_verdicts_without_call_fail(self):
        _out, probs = self._summary([_d(33000, 1)])
        self.assertTrue(any("verdicts but no cost line" in p for p in probs), probs)

    def test_a_contact_behind_the_arc_is_not_a_missing_call(self):
        _out, probs = self._summary([_d(33000, 1), PAY.replace("XPAY", "XARC").replace("0.9000", "-0.5000")])
        self.assertEqual(probs, [])

    def test_ordinary_damage_is_subtracted(self):
        out, probs = self._summary([_d(33000, 1), PAY, _x("X", 33000, 330, 0.03, 0.9), _d(33050, 0, dmg=94),
                                    "XA 33100 1005 1 0.860000 1"])
        self.assertEqual(probs, [])
        self.assertIn("ordinary damage in the windows 94 (0.0100 of the unit), attributable 0.0300",
                      "\n".join(out))

    def test_cross_checks(self):
        # the cave paid a soldier the game data says lacks charge reflection, or skipped one that has it
        _out, probs = self._summary([PAY, _x("X", 33000, 330, 0.03, 0.9), "XA 33100 1005 1 0.870000 1"], set())
        self.assertTrue(any("XPAY on wh_main_emp_inf_spearmen_1, which the game data says lacks" in p for p in probs),
                        probs)
        _out, probs = self._summary(["XNOATTR 33000 330 1007 wh_main_emp_inf_spearmen_1 F0000001 A1000020"],
                                    {"wh_main_emp_inf_spearmen_1"})
        self.assertTrue(any("XNOATTR on wh_main_emp_inf_spearmen_1, which the game data says has" in p
                            for p in probs), probs)
        # paying entries the calls do not account for
        _out, probs = self._summary([PAY, PAY, _x("X", 33000, 330, 0.03, 0.9), "XA 33100 1005 1 0.870000 1"])
        self.assertTrue(any("2 paying entries but calls for 1 models" in p for p in probs), probs)

    def test_errors_fail(self):
        _out, probs = self._summary([_d(33000, 1), "XERR 33000 330 DEAD0001 no unit object: x"])
        self.assertTrue(any("XERR" in p for p in probs), probs)


if __name__ == "__main__":
    unittest.main()
