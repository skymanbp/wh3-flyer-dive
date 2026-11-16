-- ld_cave_common.lua — pieces the memreader_plus code-cave modules share
-- memreader_plus 代码洞模块共用的三件：已装洞缓冲区的查找、战斗入口的开关判定与记录行
--
-- [TEST-REPAIR-1113 2026-11-13] Lua_Dup_Census (L1) found two bodies copied
-- across the cave lanes of 11-12: `installed()` in lib/ld_flyer_dive.lua and
-- lib/ld_flyer_takeoff.lua (same scan of the caves' shared buffer, only the
-- site table differs), and `record()` in the three battle entries
-- battle/mod/ld_engine_resist.lua / ld_flyer_dive.lua / ld_flyer_takeoff.lua
-- (same timestamped append, only the file name differs). One home here; each
-- caller passes the part that differed. Behaviour is unchanged.
-- / 两组同体函数各归一处，调用方传入原本不同的那一项（位点表 / 日志文件名）。
--
-- Pure module: no core/cm/bm calls (required modules compile in the bare _G),
-- no require of its own, so a battle entry can load it first, before bm or
-- memreader_plus is checked. / 纯模块、无依赖：战斗入口可在任何检查之前先载入它。

local M = {}

-- The buffer the installed caves of `site` share and how many are installed:
-- nil, 0 when none is; nil, -1 when they disagree or the buffer is not ours.
-- `mr` is memreader_plus, `sites` the site-loader api found for `site`.
function M.installed(mr, site, sites)
    local buf, count = nil, 0
    for _, name in ipairs(site.caves) do
        local b = sites.cave_value(name, "buf")
        if b and not mr.is_null(b) then
            if buf and mr.tostring(b) ~= mr.tostring(buf) then return nil, -1 end
            buf, count = buf or b, count + 1
        end
    end
    if buf and mr.read(buf, site.layout.magic_at, #site.layout.magic) ~= site.layout.magic then
        return nil, -1
    end
    return buf, count
end

-- [FLYER-MP-BATTLE-W1 2026-11-15, user ruling "让多人战斗也生效"] How a cave
-- rule starts in this battle; one home for the two flyer battle entries
-- (battle/mod/ld_flyer_dive.lua / ld_flyer_takeoff.lua), which had the same
-- branch. `rule` is the rule module (find / allowed / pass_through / install),
-- `mp` / `from_campaign` the battle's bm:is_multiplayer() / is_from_campaign().
-- Returns the buffer when the rule runs (the caller arms it), and the BATTLE
-- line's "on / off (why)". May throw (the caller pcalls it).
--   * multiplayer campaign battle: unchanged -- the campaign's memreader
--     agreement decides ("allowed" in the caves' buffer).
--   * any other battle, single player or multiplayer (custom / quick /
--     ranked): install the caves and start. Nothing can agree between players
--     in a battle outside a campaign: memreader Plus's agreement is campaign
--     only (agree.lua listen() / find_host() refuse elsewhere; its messages go
--     through CampaignUI.TriggerCampaignScriptEvent), and the battle script
--     API has no message between players. What keeps the players' games equal
--     there is the game itself: it refuses to join players whose mods, data or
--     executable differ (Warhammer3.exe: mp_mod_checksum_pass "mod(layout)
--     checksum", mp_data_checksum_pass, "Exe checksum"; loc
--     network_error_incompatible_mod "Incompatible mod version"), so every
--     player runs this script on the same game code. What it cannot cover --
--     memreader Plus blocked on one machine, a cave install failing on one
--     side -- leaves that game vanilla while the others run the rule: the
--     game's own desync check ends or resyncs the battle, and the BATTLE line
--     names the reason on the machine that failed.
-- / 联机战役战斗照旧看战役协商；其他战斗（单机与战役外的联机战斗）一律装洞
--   并生效：战役外没有可协商的通道，靠游戏自身的模组 / 数据 / 程序校验保证
--   各端同一脚本同一代码；一端装洞失败则那一端是原版，由游戏的不同步检测处理。
function M.start_battle(rule, log, mp, from_campaign)
    if mp and from_campaign then
        local found, complete = rule.find(log)
        if found and complete and rule.allowed(found) then
            return found, "on (the campaign's agreement)"
        end
        rule.pass_through(found)
        return nil, found and "off (the campaign's agreement did not allow it)"
            or "off (no caves: the campaign did not install them)"
    end
    local buffer, why = rule.install(log)
    if buffer then return buffer, mp and "on (multiplayer battle)" or "on (single player)" end
    if mp then
        return nil, "off (" .. tostring(why) .. "; multiplayer battle: this game stays vanilla, "
            .. "a player whose game has the rule on goes out of sync)"
    end
    return nil, "off (" .. tostring(why) .. ")"
end

-- A battle entry's record(line): appends "<timestamp> <line>" to `log_file`
-- next to Warhammer3.exe (the file both players send back after a test).
function M.recorder(log_file)
    return function(line)
        local stamp = "?"
        pcall(function() stamp = os.date("%Y-%m-%d %H:%M:%S") end)
        local f = io.open(log_file, "a")
        if f then f:write(stamp .. " " .. line .. "\n"); f:close() end
    end
end

return M
