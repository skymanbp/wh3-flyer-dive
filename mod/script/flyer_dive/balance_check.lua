-- balance_check.lua — does the balance submod pair with this main pack?
-- 平衡子模组与主包是否同一版本
--
-- [balance split 2026-11-17, user ruling] Breath-while-engaged and the mass
-- cut ship in a second pack, flyer_dive_balance.pack, whose battle_entities
-- rows are the main pack's full rows plus the cut mass. A submod built for a
-- different main version would silently put that other version's cells back
-- (its rows win), so both packs carry the build stamp of the run that built
-- them (pipelines/build_air_dive_minimod.py): the main pack in
-- script/flyer_dive/main_stamp.lua, the submod in
-- script/flyer_dive/balance_stamp.lua. The main battle entry
-- (battle/mod/ld_flyer_dive.lua) writes line(require) to ld_flyer_dive.txt.
-- / 两个包都带同一次建包的戳；主包的战斗入口把比对结果写进日志。
--
-- Pure module: no core/cm/bm calls; `req` is the game's require (a test
-- passes its own). / 纯模块。

local M = {}

M.MAIN = "script/flyer_dive/main_stamp"
M.BALANCE = "script/flyer_dive/balance_stamp"

-- The BALANCE line for the battle log.
function M.line(req)
    local okm, main = pcall(req, M.MAIN)
    if not okm or type(main) ~= "table" or type(main.main) ~= "string" then
        return "BALANCE check failed: the main pack's stamp did not load (" .. tostring(main) .. ")"
    end
    local okb, balance = pcall(req, M.BALANCE)
    if not okb or type(balance) ~= "table" then
        return "BALANCE submod not loaded (main " .. main.main .. ")"
    end
    if balance.built_for_main == main.main then
        return "BALANCE submod loaded, built for this main version " .. main.main
    end
    return "BALANCE MISMATCH: balance submod built for a different main version (submod built for "
        .. tostring(balance.built_for_main) .. ", main is " .. main.main
        .. "); its flyer rows put that version's values back -- update both mods"
end

return M
