-- flyer_dive_takeoff.lua — settings page for the Mod Configuration Tool (MCT, Workshop 2927955021)
-- 模组设置工具（MCT）里的设置页
--
-- [D10, owner ruling 2026-11-18] One setting: whether breath attacks may be used while engaged in melee. MCT is
-- optional: MCT alone loads this file (script/mct/settings/), and without MCT the battle uses the default
-- (data/breath_rows.lua default_on). The keys and the default come from that generated module, so this page and
-- the battle script (battle/mod/flyer_breath.lua) cannot disagree.
-- The page is English, or Simplified Chinese when the game's own text for the breath ability type is the
-- Simplified Chinese client's (common.get_localised_string; one language per string).
-- / 只有一项：陷入近战时可否使用吹息。键与默认值取自生成的 breath_rows，与战斗脚本同源。

local mct = type(get_mct) == "function" and get_mct() or nil
if not mct then return end

local ok_rows, rows = pcall(require, "script/campaign/flyer_dive/data/breath_rows")
if not ok_rows or type(rows) ~= "table" then
    if type(ModLog) == "function" then
        pcall(ModLog, "[flyer_dive_takeoff] MCT page not registered: data/breath_rows did not load: " .. tostring(rows))
    end
    return
end

-- The Simplified Chinese client names CA's breath ability type 吹息 (local_cn.pack,
-- unit_ability_types_onscreen_name_wh_type_breath); any other client does not.
local function simplified_chinese()
    local ok, text = pcall(common.get_localised_string, "unit_ability_types_onscreen_name_wh_type_breath")
    return ok and type(text) == "string" and (string.find_lua or string.find)(text, "吹息", 1, true) ~= nil
end

local TEXT = {
    en = {
        title = "Flyer Dive & Take-off",
        description = "Settings of the Flyer Dive & Take-off mod.",
        option = "Breath while engaged in melee",
        tooltip = "On: breath attacks can be used while the unit is engaged in melee, and dragons can breathe "
            .. "while on the ground. Off: as in the base game. In a multiplayer campaign the host's setting "
            .. "applies to every player; multiplayer battles outside a campaign always keep it on. Takes effect "
            .. "from the next battle.",
    },
    -- client wording (local_cn.pack): 多人战役 / 多人战斗 / 主机
    cn = {
        title = "飞兽俯冲与近战起飞",
        description = "飞兽俯冲与近战起飞模组的设置。",
        option = "陷入近战时可用吹息",
        tooltip = "开：部队陷入近战时也能使用吹息技能，龙落在地面上时也能吹息。关：与原版相同。多人战役里以主机的"
            .. "设置为准；战役之外的多人战斗始终为开。从下一场战斗起生效。",
    },
}

local ok, problem = pcall(function()
    local text = simplified_chinese() and TEXT.cn or TEXT.en
    local mod = mct:register_mod(rows.mct_mod)
    mod:set_title(text.title)
    mod:set_author("skymanbp")
    mod:set_description(text.description)
    local option = mod:add_new_option(rows.mct_option, "checkbox")
    option:set_text(text.option)
    option:set_tooltip_text(text.tooltip)
    option:set_default_value(rows.default_on == true)
end)
if not ok and type(ModLog) == "function" then
    pcall(ModLog, "[flyer_dive_takeoff] MCT page not registered: " .. tostring(problem))
end
