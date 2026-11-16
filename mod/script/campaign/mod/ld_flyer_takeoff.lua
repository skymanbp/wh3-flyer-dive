-- ld_flyer_takeoff.lua — campaign entry for the flyer take-off rule
-- 飞兽近战起飞规则的战役入口
--
-- [AIR-DIVE-TAKEOFF-W1 2026-11-12, user rulings 2026-11-12, CONTENT_LEDGER
-- §C8-57 and §C8-58] Same shape as campaign/mod/ld_army_cap.lua: memreader_plus
-- is loaded (it ships pinned in ld_mod.pack), the cave sites are searched at
-- load, and on the first tick memreader_plus's agreement step runs with those
-- sites. In single player it applies at once; in multiplayer the caves go in
-- only when every player's game agrees (feature mode "same"; the agreement's
-- format is derived from the cave code, so a different version of the caves
-- disagrees as "another version of the mod"), otherwise the rule is off for
-- everyone and every game keeps its own engaged check. The decision is left
-- in the caves' buffer ("allowed") for the campaign's battles
-- (battle/mod/ld_flyer_takeoff.lua), which are another Lua state. The caves
-- stay for the session and do nothing until a battle starts the rule.
-- The rule itself: lib/ld_flyer_takeoff.lua.
-- / 首帧经 memreader_plus 协商；单机直接生效，联机须各端一致（含同一版代码洞），
--   否则对所有人关闭。结果写进洞的缓冲区，供本战役的战斗读取。

local function log(text)
    if type(ModLog) == "function" then pcall(ModLog, text) end
    if type(out) == "function" then pcall(out, text) end
end

local loaded, takeoff = pcall(require, "script/campaign/lore_disasters/lib/ld_flyer_takeoff")
if not loaded or type(takeoff) ~= "table" then
    log("[ld_flyer_takeoff] ERROR: module failed to load: " .. tostring(takeoff))
    return
end

if not _G.memreader_plus then
    local chunk = loadfile("/script/_lib/mod/memreader_plus")
    if chunk then
        setfenv(chunk, core:get_env())
        pcall(chunk)
    end
end

-- The sites are searched at load; their loader object is the agreement's
-- `sites` (without sites the agreement turns every feature off, agree.lua
-- feature_state). / 位点在加载时查找，作为协商的 sites。
local prepared, prepare_why = takeoff.prepare(log)
if not prepared then log("[ld_flyer_takeoff] sites not ready: " .. tostring(prepare_why)) end
local FEATURE = takeoff.feature() or "takeoff"
-- What an earlier campaign of this game session decided does not carry over:
-- off until this campaign's agreement answers. / 上一个战役的结论不沿用。
takeoff.forbid("waiting for this campaign's agreement", log)
local agreed = false

local function apply_on()
    local buffer, why = takeoff.install(log)
    if not buffer then return why or "not installed" end
    takeoff.set_allowed(buffer, true)
    log("[ld_flyer_takeoff] allowed for this campaign's battles")
    return nil
end

local function agree()
    if agreed then return end
    agreed = true
    if not prepared then
        takeoff.forbid("sites not ready: " .. tostring(prepare_why), log)
        return
    end
    local agree_fn = _G.memreader_plus_agree
    if type(agree_fn) ~= "function" then
        -- Without the agreement step a multiplayer game cannot be kept in step:
        -- apply only in single player. / 无协商步骤时只在单机生效。
        if cm:is_multiplayer() then
            takeoff.forbid("memreader_plus agreement step missing (update memreader_plus)", log)
        else
            local why = apply_on()
            if why then takeoff.forbid(why, log) end
        end
        return
    end
    local ok, done, problem = pcall(agree_fn, takeoff.owner(), {
        features = { [FEATURE] = "same" },
        sites = takeoff.sites(),
        format = takeoff.format(),
        title = "Lore Disasters flyer take-off",
        apply = function(_, on, why)
            if not on[FEATURE] then
                takeoff.forbid(("%s off: %s"):format(FEATURE, tostring(why and why[FEATURE])), log)
                return { [FEATURE] = "off" }
            end
            local problem_here = apply_on()
            if problem_here then
                takeoff.forbid(problem_here, log)
                return { [FEATURE] = problem_here }
            end
            return nil
        end,
    })
    if not ok or not done then
        takeoff.forbid("agreement did not start: " .. tostring(ok and problem or done), log)
    end
end

-- First tick, with the first FactionTurnStart as a fallback (project memory:
-- first tick is not always reliable). / 首帧，另以首个回合开始兜底。
cm:add_first_tick_callback(function() agree() end)
core:add_listener("ld_flyer_takeoff_first_turn", "FactionTurnStart", function() return not agreed end,
    function() agree() end, false)
