-- flyer_takeoff.lua — battle entry for the flyer take-off rule
-- 飞兽近战起飞规则的战斗入口
--
-- [AIR-DIVE-TAKEOFF-W1 2026-11-12; the rule since D3, 2026-11-17: each flying
-- model by its own body size] The rule and
-- its caves: lib/takeoff.lua. The battle simulation runs in lockstep
-- on every player's machine, so the rule is only safe when every machine
-- applies it:
--   * single player (custom or campaign battle): install the caves and start
--     the rule.
--   * multiplayer campaign battle: start it only when the campaign's
--     agreement step (campaign/mod/flyer_takeoff.lua) found every player's
--     game in agreement -- it leaves "allowed" in the caves' buffer; no caves
--     or not allowed = off.
--   * any other multiplayer battle (custom / quick / ranked): [FLYER-MP-BATTLE-W1
--     2026-11-15, user ruling] install the caves and start, as in single
--     player -- no agreement is possible outside a campaign; the game's own
--     mod / data / exe checks keep every player on the same code (why and the
--     remaining risk: lib/cave_common.lua start_battle).
-- The rule starts when the battle script loads (the table of struck models is
-- cleared: it holds the last battle's entities) and goes back to off when the
-- battle completes. Lines go to flyer_takeoff.txt next to Warhammer3.exe.
-- / 单机与战役外的联机战斗装洞并生效；联机战役战斗看战役协商写下的"允许"。
--   战斗脚本加载时清表并开启，战斗结束回到关闭。每场战斗在游戏目录记两行。
--
-- Chunk scope on purpose: the battle loader loads mod files but never executes
-- a function named after the file.

local LOG_FILE = "flyer_takeoff.txt"

local function log(text)
    if type(ModLog) == "function" then pcall(ModLog, text) end
    if type(out) == "function" then pcall(out, text) end
end

-- record(line): timestamped append to LOG_FILE; one home in lib/cave_common
-- (TEST-REPAIR-1113). Loaded first, before bm / memreader_plus are checked,
-- because it has no dependency; if even it fails, the failure goes to the
-- game log instead. / 记录行函数共用一处；它无依赖，故最先载入。
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

if not _G.memreader_plus then
    local chunk = loadfile("/script/_lib/mod/memreader_plus")
    if chunk then
        if core and type(core.get_env) == "function" then setfenv(chunk, core:get_env()) end
        pcall(chunk)
    end
end

local loaded, takeoff = pcall(require, "script/campaign/flyer_dive/lib/takeoff")
if not loaded or type(takeoff) ~= "table" then
    log("[flyer_takeoff] ERROR: module failed to load: " .. tostring(takeoff))
    record("FAIL module did not load: " .. tostring(takeoff))
    return
end

local mp, from_campaign = false, false
pcall(function() mp = bm:is_multiplayer() and true or false end)
pcall(function() from_campaign = bm:is_from_campaign() and true or false end)

-- The buffer when the rule runs in this battle, else nil.
local buffer, how = nil, nil
local ok, problem = pcall(function()
    buffer, how = common.start_battle(takeoff, log, mp, from_campaign)  -- one home: lib/cave_common
    if buffer then takeoff.arm(buffer) end
end)
if not ok then
    pcall(takeoff.pass_through, buffer)
    buffer, how = nil, "off (error: " .. tostring(problem) .. ")"
end
local windows = buffer and takeoff.layout() and takeoff.layout().windows
record(("BATTLE mp=%s campaign=%s %s%s"):format(tostring(mp), tostring(from_campaign), tostring(how),
    windows and (", windows by size small/medium/large/very large/unknown " .. table.concat(windows, "/")
        .. " ticks") or ""))

bm:register_phase_change_callback("Complete", function()
    if not buffer then return end
    pcall(function()
        local c = takeoff.counters(buffer)
        -- the table's entities die with the battle: back to off / 表随战斗失效
        takeoff.pass_through(buffer)
        local rg = c.regroup
        record(("END melee hits on flyers %d (%d not recorded), answers hold %d / free %d, unknown size %d, unmatched %d"):format(
            c.stamps, c.dropped, c.held, c.free, c.unsized, c.unmatched)
            .. (rg and (", regroup (D23) skipped %d of %d (would %d, queued %d, no held model %d)"):format(
                rg.skipped, rg.calls, rg.would, rg.queued, rg.unheld) or "")
            .. (c.unit and (", unit rule (D39) held %d, unit hits %d (%d not recorded), %d ticks"):format(
                c.unit.held, c.unit.stamps, c.unit.dropped, c.unit.ticks) or ""))
    end)
end)
