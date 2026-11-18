-- flyer_breath.lua — battle entry for the breath-while-engaged setting (D10)
-- 接战时吹息开关的战斗入口（D10）
--
-- The setting lives in the Mod Configuration Tool (script/mct/settings/flyer_dive_takeoff.lua). MCT is optional:
-- without it the default applies. MCT reads its saved values after every battle script has loaded
-- (ScriptEventAllModsLoaded, which its own listener hears first) and then fires MctInitialized, so the setting is
-- read on whichever of the two comes first; without MCT (or without core) at once.
--   * on  (default, and every multiplayer battle): nothing to do -- the shipped usage-flag table already lets
--     breath through.
--   * off: lib/breath_switch keeps CA's two locks by hand, every poll_ms of battle time
--     (bm:repeat_callback, "a timer synchronised to the battle model").
-- Lines go to flyer_breath.txt next to Warhammer3.exe: one BREATH line saying on / off and why, NOW lines while
-- the counters change (every 10 s), one END line.
-- / 设置在 MCT；无 MCT 用默认（开）。开：什么都不做；关：按原版限制逐兵锁住吹息。联机战斗一律为开。

local LOG_FILE = "flyer_breath.txt"
local POLL_NAME, TICK_NAME, TICK_MS = "flyer_breath_poll", "flyer_breath_counts", 10000

local function log(text)
    if type(ModLog) == "function" then pcall(ModLog, text) end
    if type(out) == "function" then pcall(out, text) end
end

local common_ok, common = pcall(require, "script/campaign/flyer_dive/lib/cave_common")
local record
if common_ok and type(common) == "table" then
    record = common.recorder(LOG_FILE)
else
    log("[" .. LOG_FILE .. "] ERROR: lib/cave_common did not load: " .. tostring(common))
    record = function() end
end

if not bm then
    record("FAIL bm unavailable at chunk scope")
    return
end

local rows_ok, rows = pcall(require, "script/campaign/flyer_dive/data/breath_rows")
local switch_ok, switch = pcall(require, "script/campaign/flyer_dive/lib/breath_switch")
if not (rows_ok and type(rows) == "table" and switch_ok and type(switch) == "table") then
    record("FAIL breath switch did not load: " .. tostring(rows_ok and switch or rows)
        .. " (breath while engaged stays on: the shipped table)")
    return
end

-- every unit of every army: main units plus each reinforcement set
local function each_unit(fn)
    local alliances = bm:alliances()
    for a = 1, alliances:count() do
        local armies = alliances:item(a):armies()
        for j = 1, armies:count() do
            local army = armies:item(j)
            local lists = { army:units() }
            local ok, n = pcall(function() return army:num_reinforcement_units() end)
            if ok and n then
                for i = 1, n do lists[#lists + 1] = army:get_reinforcement_units(i) end
            end
            for _, units in ipairs(lists) do
                for i = 1, units:count() do fn(units:item(i)) end
            end
        end
    end
end

local function read_mct(mod_key, option_key)
    local mct = get_mct()
    local mod = mct and mct:get_mod_by_key(mod_key)
    if not mod then return nil end
    local option = mod:get_option_by_key(option_key)
    if not option then return nil end
    return option:get_finalized_setting()
end

local begun = false
local function begin(when)
    if begun then return end
    begun = true
    local mp = false
    pcall(function() mp = bm:is_multiplayer() and true or false end)
    local on, why = switch.decide(rows, mp, type(get_mct) == "function" and read_mct or nil)
    local n = 0
    for _ in pairs(rows.abilities) do n = n + 1 end
    if on then
        record(("BREATH on (%s; read on %s): breath while engaged allowed for %d abilities"):format(why, when, n))
        return
    end
    local keeper = switch.keeper(rows)
    local ok, problem = pcall(function()
        bm:repeat_callback(function() keeper:step(each_unit) end, rows.poll_ms, POLL_NAME)
    end)
    if not ok then
        record("FAIL breath off but the poll did not start: " .. tostring(problem))
        return
    end
    record(("BREATH off (%s; read on %s): %d abilities locked by hand every %d ms"):format(why, when, n, rows.poll_ms))
    local last = nil
    pcall(function()
        bm:repeat_callback(function()
            local line = keeper:counts()
            if line ~= last then
                last = line
                record("NOW " .. line .. (keeper.last_error and (", last error " .. keeper.last_error) or ""))
            end
        end, TICK_MS, TICK_NAME)
    end)
    bm:register_phase_change_callback("Complete", function()
        pcall(function() bm:remove_callback(POLL_NAME) end)
        pcall(function() bm:remove_callback(TICK_NAME) end)
        record("END " .. keeper:counts())
    end)
end

local waits = false
if type(get_mct) == "function" and type(core) == "table" then
    waits = pcall(function()
        core:add_listener("flyer_breath_mct", "MctInitialized", true, function() begin("MctInitialized") end, false)
        core:add_listener("flyer_breath_mods_loaded", "ScriptEventAllModsLoaded", true,
            function() begin("ScriptEventAllModsLoaded") end, false)
    end)
end
if not waits then begin("load (no MCT)") end
