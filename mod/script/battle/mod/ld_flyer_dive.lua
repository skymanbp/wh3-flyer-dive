-- ld_flyer_dive.lua — battle entry for the physics dive
-- 物理俯冲的战斗入口
--
-- [AIR-DIVE-MP-DIVE-W1 2026-11-12, user rulings CONTENT_LEDGER §C8-60 / §C8-61]
-- The dive and its caves: lib/ld_flyer_dive.lua. Same rules as the take-off
-- battle entry (battle/mod/ld_flyer_takeoff.lua), because the battle runs in
-- lockstep on every player's machine:
--   * single player (custom or campaign battle): install the caves and start.
--   * multiplayer campaign battle: start only when the campaign's agreement
--     step (campaign/mod/ld_flyer_dive.lua) found every player's game in
--     agreement -- it leaves "allowed" in the caves' buffer.
--   * any other multiplayer battle (custom / quick / ranked): [FLYER-MP-BATTLE-W1
--     2026-11-15, user ruling] install the caves and start, as in single
--     player -- no agreement is possible outside a campaign; the game's own
--     mod / data / exe checks keep every player on the same code (why and the
--     remaining risk: lib/ld_cave_common.lua start_battle).
-- Lines go to ld_flyer_dive.txt next to Warhammer3.exe (one BATTLE line with
-- the cave version, one END line with the counters) -- the file both players
-- send back after a test.
-- / 单机与战役外的联机战斗装洞并生效；联机战役战斗看战役协商写下的"允许"。

local LOG_FILE = "ld_flyer_dive.txt"

local function log(text)
    if type(ModLog) == "function" then pcall(ModLog, text) end
    if type(out) == "function" then pcall(out, text) end
end

-- record(line): timestamped append to LOG_FILE; one home in lib/ld_cave_common
-- (TEST-REPAIR-1113). Loaded first, before bm / memreader_plus are checked,
-- because it has no dependency; if even it fails, the failure goes to the
-- game log instead. / 记录行函数共用一处；它无依赖，故最先载入。
local common_ok, common = pcall(require, "script/campaign/lore_disasters/lib/ld_cave_common")
local record
if common_ok and type(common) == "table" then
    record = common.recorder(LOG_FILE)
else
    log("[" .. LOG_FILE .. "] ERROR: lib/ld_cave_common did not load: " .. tostring(common))
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

local loaded, dive = pcall(require, "script/campaign/lore_disasters/lib/ld_flyer_dive")
if not loaded or type(dive) ~= "table" then
    log("[ld_flyer_dive] ERROR: module failed to load: " .. tostring(dive))
    record("FAIL module did not load: " .. tostring(dive))
    return
end

local mp, from_campaign = false, false
pcall(function() mp = bm:is_multiplayer() and true or false end)
pcall(function() from_campaign = bm:is_from_campaign() and true or false end)

-- The buffer when the rule runs in this battle, else nil.
local buffer, how = nil, nil
local ok, problem = pcall(function()
    buffer, how = common.start_battle(dive, log, mp, from_campaign)  -- one home: lib/ld_cave_common
    if buffer then dive.arm(buffer) end
end)
if not ok then
    pcall(dive.pass_through, buffer)
    buffer, how = nil, "off (error: " .. tostring(problem) .. ")"
end
local okv, site = pcall(require, "script/campaign/lore_disasters/data/ld_flyer_dive_site")
record(("BATTLE mp=%s campaign=%s %s, caves format %s built for %s"):format(tostring(mp), tostring(from_campaign),
    tostring(how), tostring(okv and site.format), tostring(okv and site.build)))

local COUNTS = "flyer charges aimed through %d, contact attacks held off %d, flight stops held off %d, "
    .. "engage re-paths held off %d, charge-order re-paths held off %d, melee engages held off %d, "
    .. "blocked stops held off %d, slides ended %d, landings kept %d"
local TICK_NAME, TICK_MS = "ld_flyer_dive_counts", 10000

-- Every 10 s, a NOW line when the counters changed: the END line needs the
-- battle's Complete phase, which a player who quits mid-battle (or a test
-- harness that kills the game) never reaches. / 每 10 秒计数有变才记一行。
if buffer then
    local last = nil
    pcall(function()
        bm:repeat_callback(function()
            local ok, c = pcall(dive.counters, buffer)
            if not ok then
                pcall(function() bm:remove_callback(TICK_NAME) end)
                return
            end
            local line = COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered, c.contact, c.settled,
                c.released, c.committed)
            if line ~= last then
                last = line
                record("NOW " .. line)
            end
        end, TICK_MS, TICK_NAME)
    end)
end

bm:register_phase_change_callback("Complete", function()
    if not buffer then return end
    pcall(function() bm:remove_callback(TICK_NAME) end)
    pcall(function()
        local c = dive.counters(buffer)
        dive.pass_through(buffer)
        record("END " .. COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered, c.contact, c.settled,
            c.released, c.committed))
    end)
end)
