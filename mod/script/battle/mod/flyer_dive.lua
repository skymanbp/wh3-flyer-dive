-- flyer_dive.lua — battle entry for the physics dive
-- 物理俯冲的战斗入口
--
-- [AIR-DIVE-MP-DIVE-W1 2026-11-12, user rulings CONTENT_LEDGER §C8-60 / §C8-61]
-- The dive and its caves: lib/dive.lua. Same rules as the take-off
-- battle entry (battle/mod/flyer_takeoff.lua), because the battle runs in
-- lockstep on every player's machine:
--   * single player (custom or campaign battle): install the caves and start.
--   * multiplayer campaign battle: start only when the campaign's agreement
--     step (campaign/mod/flyer_dive.lua) found every player's game in
--     agreement -- it leaves "allowed" in the caves' buffer.
--   * any other multiplayer battle (custom / quick / ranked): [FLYER-MP-BATTLE-W1
--     2026-11-15, user ruling] install the caves and start, as in single
--     player -- no agreement is possible outside a campaign; the game's own
--     mod / data / exe checks keep every player on the same code (why and the
--     remaining risk: lib/cave_common.lua start_battle).
-- Lines go to flyer_dive.txt next to Warhammer3.exe (one BATTLE line with
-- the cave version, one END line with the counters) -- the file both players
-- send back after a test.
-- / 单机与战役外的联机战斗装洞并生效；联机战役战斗看战役协商写下的"允许"。

local LOG_FILE = "flyer_dive.txt"

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

local loaded, dive = pcall(require, "script/campaign/flyer_dive/lib/dive")
if not loaded or type(dive) ~= "table" then
    log("[flyer_dive] ERROR: module failed to load: " .. tostring(dive))
    record("FAIL module did not load: " .. tostring(dive))
    return
end

local mp, from_campaign = false, false
pcall(function() mp = bm:is_multiplayer() and true or false end)
pcall(function() from_campaign = bm:is_from_campaign() and true or false end)

-- The buffer when the rule runs in this battle, else nil.
local buffer, how = nil, nil
local ok, problem = pcall(function()
    buffer, how = common.start_battle(dive, log, mp, from_campaign)  -- one home: lib/cave_common
    if buffer then dive.arm(buffer) end
end)
if not ok then
    pcall(dive.pass_through, buffer)
    buffer, how = nil, "off (error: " .. tostring(problem) .. ")"
end
local okv, site = pcall(require, "script/campaign/flyer_dive/data/dive_site")
record(("BATTLE mp=%s campaign=%s %s, caves format %s built for %s"):format(tostring(mp), tostring(from_campaign),
    tostring(how), tostring(okv and site.format), tostring(okv and site.build)))

local COUNTS = "flyer charges aimed through %d, contact attacks held off %d, flight stops held off %d, "
    .. "engage re-paths held off %d, charge-order re-paths held off %d, melee engages held off %d, "
    .. "blocked stops held off %d, slides ended %d, landings kept %d, "
    .. "slides ended by melee %d, slides ended by speeding up again %d, "
    .. "bodies already in melee not carried %d, braced masses scaled %d, "
    .. "braced steps left to the engine %d, braced masses scaled with no slide entry %d, "
    .. "Charge Reflection hits on flyers raised %d"
-- [D64] braced masses are scaled once per soldier met (first meetings); the later steps of the same pair are the
-- engine's own; a flyer with no slide entry yet is scaled but not remembered
local function counts(c)
    return COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered, c.contact, c.settled,
        c.released, c.committed, c.closed, c.sped, c.engaged_body, c.braced, c.brace_repeat, c.brace_noslot,
        c.reflected)
end
local TICK_NAME, TICK_MS = "flyer_dive_counts", 10000

-- [D31 / D51] The braced-line settings (lib/brace_rule.lua): master switch, k, s*, the reflection factor. MCT is optional; it
-- holds its values once every battle script has loaded (ScriptEventAllModsLoaded, MctInitialized), so they are read
-- on whichever comes first, without MCT at once; Deployed reads them too if neither came. Until then dv_brace runs on
-- the defaults dive.arm wrote. One BRACE line says what is in force and why.
-- / 阵列齐整对俯冲的设置：MCT 有值后读一次，写入 dv_brace 的设置字；一行 BRACE 记录生效的设置。
local brace = nil                      -- {on, k, share, reflect, why} once read
local brace_ok, brace_rule = pcall(require, "script/campaign/flyer_dive/lib/brace_rule")
if not brace_ok or type(brace_rule) ~= "table" then
    record("BRACE defaults stay: lib/brace_rule did not load: " .. tostring(brace_rule))
    brace_rule = nil
end

local function read_mct(mod_key, option_key)
    local mct = get_mct()
    local mod = mct and mct:get_mod_by_key(mod_key)
    if not mod then return nil end
    local option = mod:get_option_by_key(option_key)
    if not option then return nil end
    return option:get_finalized_setting()
end

local function read_brace(when)
    if brace or not (buffer and brace_rule and okv and type(site) == "table" and type(site.brace) == "table") then
        return
    end
    local done, problem = pcall(function()
        local s = brace_rule.decide(site.brace, mp, from_campaign, type(get_mct) == "function" and read_mct or nil)
        dive.set_brace(buffer, brace_rule.word(site.brace, s), brace_rule.reflect_word(site.brace, s))
        brace = s
        record(("BRACE %s (%s; read on %s)"):format(brace_rule.describe(site.brace, s), s.why, when))
    end)
    if not done then record("BRACE defaults stay: " .. tostring(problem)) end
end

if buffer and brace_rule then
    local waits = false
    if type(get_mct) == "function" and type(core) == "table" then
        waits = pcall(function()
            core:add_listener("flyer_dive_brace_mct", "MctInitialized", true, function() read_brace("MctInitialized") end,
                false)
            core:add_listener("flyer_dive_brace_mods_loaded", "ScriptEventAllModsLoaded", true,
                function() read_brace("ScriptEventAllModsLoaded") end, false)
        end)
    end
    if not waits then read_brace("load (no MCT)") end
end

-- [D51] D15's dive cost (its battle module) is gone: Charge Reflection on flyers is dv_reflect's, inside the
-- engine. Deployed still reads the settings if neither MCT event came.
if buffer and brace_rule then
    pcall(function() bm:register_phase_change_callback("Deployed", function() read_brace("Deployed") end) end)
end

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
            local line = counts(c)
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
    pcall(function() bm:remove_callback(COST_NAME) end)
    pcall(function()
        local c = dive.counters(buffer)
        dive.pass_through(buffer)
        record("END " .. counts(c))
    end)
end)
