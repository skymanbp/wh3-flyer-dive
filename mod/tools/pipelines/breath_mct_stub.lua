-- breath_mct_stub.lua — TEST ONLY: a stand-in for the Mod Configuration Tool that holds one value
-- 仅供测试：代替 MCT，只回答一个设置值
--
-- Never in a player's pack: packed only by tools/pipelines/build_breath_mct_stub.py, which fills in the value tag, as
-- script/_lib/mod/zz_flyer_breath_mct_stub.lua (the battle loads script/_lib/mod/ before script/battle/mod/, so
-- battle/mod/flyer_breath.lua finds get_mct). When the real MCT is loaded it defines get_mct first
-- (script/_lib/mod/!glib_init.lua sorts before this file) and this stub does nothing. It fires no event: the battle
-- entry reads the setting on ScriptEventAllModsLoaded, which the game's mod loader fires after every battle script
-- (script/_lib/lib_mod_loader.lua).
if type(get_mct) == "function" then return end

local VALUE = "@VALUE@" == "on"
local option = { get_finalized_setting = function() return VALUE end }
local mod = { get_option_by_key = function() return option end }
local mct = { get_mod_by_key = function() return mod end }
function get_mct() return mct end
if type(ModLog) == "function" then pcall(ModLog, "[breath_mct_stub] test stand-in for MCT, breath while engaged = @VALUE@") end
