-- flyer_dive_takeoff.lua — settings page for the Mod Configuration Tool (MCT, Workshop 2927955021)
-- 模组设置工具（MCT）里的设置页
--
-- [D10, owner ruling 2026-11-18] One setting: whether breath attacks may be used while engaged in melee. MCT is
-- optional: MCT alone loads this file (script/mct/settings/), and without MCT the battle uses the default
-- (data/breath_rows.lua default_on). The keys and the default come from that generated module, so this page and
-- the battle script (battle/mod/flyer_breath.lua) cannot disagree.
-- [D25 / D31, brace-solver-1120] Four more, in the same section: the braced-line switch, the braced mass against a
-- dive (k), the least share of the slowing a diving flyer takes (s*), and (D51, in place of D15's dive cost) the
-- Charge Reflection factor on flyers. Keys, defaults
-- and ranges come from the generated site table's `brace` block (data/dive_site.lua), which the battle script
-- (lib/brace_rule.lua) reads too. If that table does not load, the breath setting is still registered.
-- The page is English, or Simplified Chinese when the game's own text for the breath ability type is the
-- Simplified Chinese client's (common.get_localised_string; one language per string).
-- / 吹息一项（键与默认值取自 breath_rows）；阵列齐整对俯冲四项（取自 dive_site 的 brace），与战斗脚本同源。

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

-- client wording (local_cn.pack): 多人战役 / 多人战斗 / 主机; 阵列齐整 (bracing), 冲锋反制 (Charge Reflection),
-- 质量 (mass), 生命值 (health), 飞行部队 (flying units)
local TEXT = {
    en = {
        title = "Flyer Dive & Take-off",
        description = "Settings of the Flyer Dive & Take-off mod.",
        option = "Breath while engaged in melee",
        tooltip = "On: breath attacks can be used while the unit is engaged in melee, and dragons can breathe "
            .. "while on the ground. Off: as in the base game. In a multiplayer campaign the host's setting "
            .. "applies to every player; multiplayer battles outside a campaign always keep it on. Takes effect "
            .. "from the next battle.",
        brace_on = "Braced units against dives",
        brace_on_tip = "On: a flying unit that dives into the front of a braced unit is slowed by it as the two "
            .. "settings below say, and Charge Reflection hurts flying units more as the last setting says. "
            .. "Off: as in the base game. Units that cannot fly are never changed. "
            .. "In a multiplayer campaign the host's settings apply to every player; multiplayer battles outside "
            .. "a campaign always use the defaults. Takes effect from the next battle.",
        brace_k = "Braced mass against a dive",
        brace_k_tip = "How many times its braced mass a soldier counts for when a diving flyer hits its front. "
            .. "The game already makes a braced soldier heavier by rank and facing; this multiplies that. "
            .. "1 = as in the base game.",
        brace_share = "Dive slowing against braced units",
        brace_share_tip = "In the game a much bigger body takes only part of the slowing when it hits a smaller "
            .. "one (0.8 one size apart, 0.2 two, 0.1 three). A diving flyer that hits the front of a braced unit "
            .. "takes at least this part. 0 = as in the base game.",
        brace_reflect = "Charge Reflection damage to flying units",
        brace_reflect_tip = "The Charge Reflection damage a flying unit takes when it charges into a braced unit "
            .. "with Charge Reflection, as a multiple of the base game's. 1 = as in the base game.",
    },
    cn = {
        title = "飞兽俯冲与近战起飞",
        description = "飞兽俯冲与近战起飞模组的设置。",
        option = "陷入近战时可用吹息",
        tooltip = "开：部队陷入近战时也能使用吹息技能，龙落在地面上时也能吹息。关：与原版相同。多人战役里以主机的"
            .. "设置为准；战役之外的多人战斗始终为开。从下一场战斗起生效。",
        brace_on = "阵列齐整的部队抵御俯冲",
        brace_on_tip = "开：飞行部队俯冲撞上阵列齐整的部队正面时，按下面两项被它减速；冲锋反制对飞行部队的伤害按"
            .. "最后一项加重。关：与原版相同。不会飞的部队不受影响。多人战役里以主机"
            .. "的设置为准；战役之外的多人战斗始终用默认值。从下一场战斗起生效。",
        brace_k = "阵列齐整时抵御俯冲的质量倍数",
        brace_k_tip = "俯冲的飞行部队撞上阵列齐整的士兵正面时，士兵的质量按几倍计算。游戏本来就按排数与朝向加重阵列"
            .. "齐整的士兵，这一项在那之上再乘。1 为原版。",
        brace_share = "俯冲撞上阵列齐整部队时的减速比例",
        brace_share_tip = "游戏里体型大得多的一方撞上小的一方时只承受一部分减速（差一级 0.8，两级 0.2，三级 0.1）。"
            .. "俯冲的飞行部队撞上阵列齐整的部队正面时，至少承受这一比例。0 为原版。",
        brace_reflect = "冲锋反制对飞行部队的伤害倍数",
        brace_reflect_tip = "飞行部队冲锋撞上阵列齐整且有冲锋反制的部队时，所受冲锋反制伤害是原版的几倍。1 为原版。",
    },
}

local text = nil
local mod = nil
local ok, problem = pcall(function()
    text = simplified_chinese() and TEXT.cn or TEXT.en
    mod = mct:register_mod(rows.mct_mod)
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

-- [D31] the braced-line settings, in the same mod and section
local ok_site, site = pcall(require, "script/campaign/flyer_dive/data/dive_site")
local b = ok_site and type(site) == "table" and site.brace or nil
if not (ok and b) then
    if type(ModLog) == "function" then
        pcall(ModLog, "[flyer_dive_takeoff] braced-line settings not registered: "
            .. (ok and ("data/dive_site has no brace block: " .. tostring(site)) or "the page did not register"))
    end
    return
end
local ok_b, problem_b = pcall(function()
    if b.mct_mod ~= rows.mct_mod then error("the site table names another MCT mod: " .. tostring(b.mct_mod)) end
    local on = mod:add_new_option(b.mct_on, "checkbox")
    on:set_text(text.brace_on)
    on:set_tooltip_text(text.brace_on_tip)
    on:set_default_value(b.default_on == true)
    local function slider(key, label, tip, lo, hi, step, precision, default)
        local o = mod:add_new_option(key, "slider")
        o:set_text(label)
        o:set_tooltip_text(tip)
        o:slider_set_min_max(lo, hi)
        o:slider_set_step_size(step, precision)
        o:slider_set_precision(precision)
        o:set_default_value(default)
    end
    slider(b.mct_k, text.brace_k, text.brace_k_tip, b.k_min, b.k_max, b.k_step, 1, b.k)
    slider(b.mct_share, text.brace_share, text.brace_share_tip, b.share_min, b.share_max, b.share_step, 2, b.share)
    slider(b.mct_reflect, text.brace_reflect, text.brace_reflect_tip, b.reflect_min, b.reflect_max,
        b.reflect_step, 2, b.reflect)
end)
if not ok_b and type(ModLog) == "function" then
    pcall(ModLog, "[flyer_dive_takeoff] braced-line settings not registered: " .. tostring(problem_b))
end
