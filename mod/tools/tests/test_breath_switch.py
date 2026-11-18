"""The breath-while-engaged setting (owner ruling 2026-11-18, docs/DECISIONS.md D10), run for real in LuaJIT.

The shipped usage-flag table is the "on" state; "off" is the battle script putting CA's dropped locks back by
hand. The three shipped files run unchanged here against stand-ins for the game (bm, core, get_mct, units),
with the data module the build generates from the installed game's rows. What is pinned:

* the decision: multiplayer -> on whatever MCT says; no MCT -> the default (on); MCT on / off -> that; MCT
  failing or holding no boolean -> the default;
* the locks: an ability whose engaged_in_melee row was dropped is disabled while its unit is in melee, one
  whose grounded row was dropped also while not flying; enabled again when neither holds; the game is called
  only on a change; a unit without a listed ability is never touched; a unit whose calls fail does not stop the
  walk;
* the battle entry: on -> one BREATH on line and no poll; off -> a BREATH off line, a poll every poll_ms that
  disables a breath in melee, an END line with the counters; the setting is read once MCT has its values;
* the MCT page: registers one checkbox under the data module's keys with its default, English text on an
  English client and Simplified Chinese on a Simplified Chinese one (never both in one string), and does
  nothing without MCT.
luajit and the installed game are required inputs: missing either is a failure, not a skip.
/ 接战吹息开关：在 LuaJIT 里跑真文件；判定、逐兵加锁解锁、战斗入口、MCT 设置页。
"""
import json
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
import build_air_dive_minimod as mini  # noqa: E402 -- same reason (pipelines/)

MOD_DIR = TOOLS_DIR.parent
STAR = "wh2_main_unit_abilities_star_dragons_breath"      # engaged_in_melee + grounded dropped
FROST = "wh2_dlc10_unit_abilities_frost_breath"           # engaged_in_melee only

_ROWS = None


def rows_lua():
    """The data module exactly as the build writes it from the installed game."""
    global _ROWS
    if _ROWS is None:
        db = mini.GAME_DIR / "db.pack"
        if not db.is_file():
            raise AssertionError(f"required installed db.pack missing: {db}")
        _w, removed, _b = air_dive_rules.breath_usage_writer(db, db.parent / "local_en.pack")
        _ROWS = air_dive_rules.breath_switch_lua(removed).decode("utf-8")
    return _ROWS


COMMON = r'''
local MOD, ROWS = arg[1], arg[2]
package.path = MOD .. "/?.lua;" .. package.path
local f = assert(io.open(ROWS, "rb")); local rows_text = f:read("*a"); f:close()
package.preload["script/campaign/flyer_dive/data/breath_rows"] = function() return assert(loadstring(rows_text))() end
local written = {}
local real_open = io.open
io.open = function(path, mode)
    if path == "flyer_breath.txt" then
        return { write = function(_, s) written[#written + 1] = s end, close = function() end }
    end
    return real_open(path, mode)
end
local function dump()
    for _, s in ipairs(written) do io.stdout:write(s) end
end
local function fake_unit(uid, owned)
    local u = { uid = uid, owned = owned, melee = false, flying = true, calls = {} }
    function u:unique_ui_id() return self.uid end
    function u:owned_non_passive_special_abilities() return self.owned end
    function u:is_in_melee() return self.melee end
    function u:is_currently_flying() return self.flying end
    function u:disable_special_ability(key, disable)
        self.calls[#self.calls + 1] = key .. "=" .. tostring(disable)
    end
    return u
end
'''

DECIDE_CASE = r'''
local switch = require("script/campaign/flyer_dive/lib/breath_switch")
local rows = require("script/campaign/flyer_dive/data/breath_rows")
local function show(on, why) print(tostring(on) .. "|" .. why) end
show(switch.decide(rows, true, function() return false end))
show(switch.decide(rows, false, nil))
show(switch.decide(rows, false, function() return true end))
show(switch.decide(rows, false, function() return false end))
show(switch.decide(rows, false, function() return nil end))
show(switch.decide(rows, false, function() error("boom", 0) end))
local seen = {}
switch.decide(rows, false, function(m, o) seen[1], seen[2] = m, o; return true end)
print("KEYS " .. seen[1] .. " " .. seen[2])
'''

KEEPER_CASE = r'''
local switch = require("script/campaign/flyer_dive/lib/breath_switch")
local rows = require("script/campaign/flyer_dive/data/breath_rows")
local dragon = fake_unit(1, { "STAR", "some_other_ability" })
local hydra = fake_unit(2, { "FROST" })
local foot = fake_unit(3, { "some_other_ability" })
local broken = fake_unit(4, { "STAR" })
function broken:is_in_melee() error("gone", 0) end
local units = { dragon, hydra, foot, broken }
local k = switch.keeper(rows)
local function step(label)
    k:step(function(fn) for _, u in ipairs(units) do fn(u) end end)
    print(label .. " dragon=" .. table.concat(dragon.calls, ",") .. " hydra=" .. table.concat(hydra.calls, ",")
        .. " foot=" .. table.concat(foot.calls, ","))
    dragon.calls, hydra.calls, foot.calls = {}, {}, {}
end
step("flying")                                                          -- nothing locked
dragon.flying = false; hydra.flying = false; step("landed")            -- dragon: grounded lock; hydra none
dragon.flying = true; dragon.melee = true; hydra.melee = true; step("melee")   -- dragon stays; hydra locks
step("again")                                                           -- no change, no call
dragon.melee = false; hydra.melee = false; step("free")                 -- both released
print("COUNTS " .. k:counts())
'''

ENTRY_CASE = r'''
local MODE = arg[3]               -- "none" (no MCT) | "on" | "off" | "mp_off" | "stub" (arg[4]: the test stand-in)
local listeners, callbacks, phases = {}, {}, {}
local dragon = fake_unit(7, { "STAR" })
dragon.flying, dragon.melee = true, true
local units = { count = function() return 1 end, item = function() return dragon end }
local army = { units = function() return units end, num_reinforcement_units = function() return 0 end }
local armies = { count = function() return 1 end, item = function() return army end }
local alliance = { armies = function() return armies end }
local alliances = { count = function() return 1 end, item = function() return alliance end }
bm = {
    alliances = function() return alliances end,
    is_multiplayer = function() return MODE == "mp_off" end,
    repeat_callback = function(_, fn, ms, name) callbacks[#callbacks + 1] = { fn = fn, ms = ms, name = name } end,
    remove_callback = function() end,
    register_phase_change_callback = function(_, phase, fn) phases[phase] = fn end,
}
core = { add_listener = function(_, name, event, cond, fn) listeners[#listeners + 1] = { event = event, fn = fn } end }
if MODE == "stub" then
    local f = assert(io.open(arg[4], "rb")); local stub = f:read("*a"); f:close()
    assert(loadstring(stub))()
elseif MODE ~= "none" then
    local value = (MODE == "on")
    get_mct = function()
        return { get_mod_by_key = function(_, m)
            return { get_option_by_key = function(_, o)
                return { get_finalized_setting = function() return value end }
            end }
        end }
    end
end
dofile(MOD .. "/script/battle/mod/flyer_breath.lua")
print("LISTENERS " .. #listeners .. " CALLBACKS_BEFORE " .. #callbacks)
for _, l in ipairs(listeners) do if l.event == "ScriptEventAllModsLoaded" then l.fn() end end
for _, l in ipairs(listeners) do if l.event == "MctInitialized" then l.fn() end end
print("CALLBACKS " .. #callbacks)
for _, c in ipairs(callbacks) do
    if c.name == "flyer_breath_poll" then print("POLL_MS " .. c.ms); c.fn(); c.fn() end
end
print("DRAGON " .. table.concat(dragon.calls, ","))
if phases.Complete then phases.Complete() end
dump()
'''

MCT_CASE = r'''
local CLIENT = arg[3]             -- "en" | "cn" | "none"
local reg = {}
common = { get_localised_string = function(key)
    if key ~= "unit_ability_types_onscreen_name_wh_type_breath" then return "" end
    return CLIENT == "cn" and "[[img:ui/battle ui/ability_icons/icon_spell_breath.png]][[/img]]吹息"
        or "[[img:ui/battle ui/ability_icons/icon_spell_breath.png]][[/img]]Breath"
end }
if CLIENT ~= "none" then
    get_mct = function()
        return { register_mod = function(_, key)
            reg.mod = key
            local mod = {}
            function mod:set_title(t) reg.title = t end
            function mod:set_author(t) reg.author = t end
            function mod:set_description(t) reg.description = t end
            function mod:add_new_option(k, kind)
                reg.option, reg.kind = k, kind
                local o = {}
                function o:set_text(t) reg.text = t end
                function o:set_tooltip_text(t) reg.tooltip = t end
                function o:set_default_value(v) reg.default = v end
                return o
            end
            return mod
        end }
    end
end
dofile(MOD .. "/script/mct/settings/flyer_dive_takeoff.lua")
for _, k in ipairs({ "mod", "option", "kind", "default", "title", "text", "tooltip", "description" }) do
    print(k .. "=" .. tostring(reg[k]))
end
'''


def stub_file(td, value):
    import build_breath_mct_stub as stub
    path, data = stub.stub_entry(value)
    out = Path(td) / Path(path).name
    out.write_bytes(data)
    return str(out)


def run(case, *extra):
    luajit = shutil.which("luajit")
    if not luajit:
        raise AssertionError("luajit is required to run the breath switch (no fallback)")
    with tempfile.TemporaryDirectory() as td:
        rows = Path(td) / "breath_rows.lua"
        rows.write_text(rows_lua(), encoding="utf-8")
        harness = Path(td) / "case.lua"
        harness.write_text((COMMON + case).replace('"STAR"', json.dumps(STAR)).replace('"FROST"', json.dumps(FROST)),
                           encoding="utf-8")
        proc = subprocess.run([luajit, str(harness), str(MOD_DIR), str(rows), *extra], capture_output=True,
                              cwd=td)
    if proc.returncode != 0:
        raise AssertionError(f"the case did not run: {proc.stderr.decode('utf-8', 'replace').strip()[:600]}")
    return proc.stdout.decode("utf-8").splitlines()


class Data(unittest.TestCase):
    def test_both_kinds_of_lock_are_in_the_shipped_rows(self):
        text = rows_lua()
        self.assertIn(f'["{STAR}"] = {{ "in_melee", "not_flying" }}', text)
        self.assertIn(f'["{FROST}"] = {{ "in_melee" }}', text)
        self.assertIn(f'mct_mod = "{air_dive_rules.BREATH_SWITCH_MCT_MOD}"', text)
        self.assertIn(f'mct_option = "{air_dive_rules.BREATH_SWITCH_MCT_OPTION}"', text)
        self.assertIn("default_on = true", text)

    def test_unknown_flag_is_refused(self):
        with self.assertRaises(RuntimeError):
            air_dive_rules.breath_switch_lua([{"special_ability": "x", "invalid_usage_flag": "climbing"}])
        with self.assertRaises(RuntimeError):
            air_dive_rules.breath_switch_lua([])


class Decide(unittest.TestCase):
    def test_decision(self):
        lines = run(DECIDE_CASE)
        on = [ln.split("|", 1) for ln in lines[:6]]
        self.assertEqual([o for o, _w in on], ["true", "true", "true", "false", "true", "true"])
        self.assertIn("multiplayer", on[0][1])
        self.assertIn("MCT not installed", on[1][1])
        self.assertEqual(on[2][1], "MCT")
        self.assertEqual(on[3][1], "MCT")
        self.assertIn("holds no setting", on[4][1])
        self.assertIn("reading MCT failed: boom", on[5][1])
        self.assertEqual(lines[6], f"KEYS {air_dive_rules.BREATH_SWITCH_MCT_MOD} "
                                   f"{air_dive_rules.BREATH_SWITCH_MCT_OPTION}")


class Keeper(unittest.TestCase):
    def test_locks_follow_the_dropped_rows(self):
        lines = run(KEEPER_CASE)
        self.assertEqual(lines[0], "flying dragon= hydra= foot=")
        self.assertEqual(lines[1], f"landed dragon={STAR}=true hydra= foot=")
        self.assertEqual(lines[2], f"melee dragon= hydra={FROST}=true foot=")
        self.assertEqual(lines[3], "again dragon= hydra= foot=")
        self.assertEqual(lines[4], f"free dragon={STAR}=false hydra={FROST}=false foot=")
        # the broken unit counts one error per step and the walk went on (the others were handled)
        self.assertEqual(lines[5], "COUNTS breath locks set 2, released 2, units with a listed breath 3, "
                                   "unit errors 5")


class Entry(unittest.TestCase):
    def test_off_polls_and_locks(self):
        lines = run(ENTRY_CASE, "off")
        self.assertIn("LISTENERS 2 CALLBACKS_BEFORE 0", lines)   # waits for MCT's values
        self.assertIn(f"POLL_MS {air_dive_rules.BREATH_SWITCH_POLL_MS}", lines)
        self.assertIn(f"DRAGON {STAR}=true", lines)              # one call: the second poll changes nothing
        breath = [ln for ln in lines if " BREATH " in ln]
        self.assertEqual(len(breath), 1, lines)                  # read once although both events fired
        self.assertIn("BREATH off (MCT; read on ScriptEventAllModsLoaded)", breath[0])
        self.assertTrue([ln for ln in lines if " END breath locks set 1, released 0" in ln], lines)

    def test_on_does_nothing(self):
        for mode, why in (("on", "BREATH on (MCT;"), ("none", "BREATH on (default (MCT not installed); read on load"),
                          ("mp_off", "BREATH on (multiplayer battle")):
            with self.subTest(mode=mode):
                lines = run(ENTRY_CASE, mode)
                self.assertIn("CALLBACKS 0", lines)
                self.assertIn("DRAGON ", lines)
                breath = [ln for ln in lines if " BREATH " in ln]
                self.assertEqual(len(breath), 1, lines)
                self.assertIn(why, breath[0])
                self.assertFalse([ln for ln in lines if " END " in ln or " FAIL " in ln], lines)


class TestStandIn(unittest.TestCase):
    """The test-only MCT stand-in the in-game check loads (pipelines/build_breath_mct_stub.py)."""

    def test_stub_turns_it_off_and_on(self):
        with tempfile.TemporaryDirectory() as td:
            off = run(ENTRY_CASE, "stub", stub_file(td, "off"))
            on = run(ENTRY_CASE, "stub", stub_file(td, "on"))
        self.assertTrue([ln for ln in off if " BREATH off (MCT;" in ln], off)
        self.assertIn(f"DRAGON {STAR}=true", off)
        self.assertTrue([ln for ln in on if " BREATH on (MCT;" in ln], on)
        self.assertIn("CALLBACKS 0", on)

    def test_stub_refuses_other_values_and_shipped_name(self):
        import build_breath_mct_stub as stub
        with self.assertRaises(SystemExit):
            stub.stub_entry("maybe")
        with self.assertRaises(SystemExit):
            stub.main(["--value", "off", "--out", "x/flyer_dive_takeoff.pack"])


class MctPage(unittest.TestCase):
    def page(self, client):
        return dict(ln.split("=", 1) for ln in run(MCT_CASE, client))

    def test_registers_one_checkbox(self):
        page = self.page("en")
        self.assertEqual(page["mod"], air_dive_rules.BREATH_SWITCH_MCT_MOD)
        self.assertEqual(page["option"], air_dive_rules.BREATH_SWITCH_MCT_OPTION)
        self.assertEqual(page["kind"], "checkbox")
        self.assertEqual(page["default"], str(air_dive_rules.BREATH_SWITCH_DEFAULT_ON).lower())

    def test_one_language_per_client(self):
        en, cn = self.page("en"), self.page("cn")
        for key in ("title", "text", "tooltip", "description"):
            with self.subTest(key=key):
                self.assertFalse(any("一" <= ch <= "鿿" for ch in en[key]), en[key])
                self.assertTrue(any("一" <= ch <= "鿿" for ch in cn[key]), cn[key])
                self.assertFalse(any("a" <= ch.lower() <= "z" for ch in cn[key]), cn[key])
        self.assertEqual(cn["text"], "陷入近战时可用吹息")

    def test_without_mct_nothing_happens(self):
        page = self.page("none")
        self.assertEqual(page["mod"], "nil")


if __name__ == "__main__":
    unittest.main()
