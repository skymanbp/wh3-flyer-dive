-- breath_mct_stub.lua — TEST ONLY: a stand-in for the Mod Configuration Tool that holds fixed values
-- 仅供测试：代替 MCT，只回答固定的设置值
--
-- Never in a player's pack: packed only by tools/pipelines/build_breath_mct_stub.py, which fills in the tags, as
-- script/_lib/mod/zz_flyer_breath_mct_stub.lua (the battle loads script/_lib/mod/ before script/battle/mod/, so
-- battle/mod/flyer_breath.lua finds get_mct). When the real MCT is loaded it defines get_mct first
-- (script/_lib/mod/!glib_init.lua sorts before this file) and this stub does nothing. It fires no event: the battle
-- entry reads the setting on ScriptEventAllModsLoaded, which the game's mod loader fires after every battle script
-- (script/_lib/lib_mod_loader.lua).
-- [D31] It answers the breath option with the value above and the braced-line options with OTHER (an empty
-- table: MCT holds none of them, so battle/mod/flyer_dive.lua uses their defaults); any other option is not there.
if type(get_mct) == "function" then return end

local VALUE = "@VALUE@" == "on"
local BREATH_KEY = "@BREATH_KEY@"
local OTHER = @OTHER@
local mod = { get_option_by_key = function(_, key)
    local v
    if key == BREATH_KEY then v = VALUE else v = OTHER[key] end
    if v == nil then return nil end
    return { get_finalized_setting = function() return v end }
end }
local mct = { get_mod_by_key = function() return mod end }
function get_mct() return mct end
if type(ModLog) == "function" then
    pcall(ModLog, "[breath_mct_stub] test stand-in for MCT, breath while engaged = @VALUE@, braced line @SUMMARY@")
end
