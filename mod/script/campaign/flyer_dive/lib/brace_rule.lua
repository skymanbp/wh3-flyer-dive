-- brace_rule.lua — the braced-line settings (D25 / D31 / D51): read them from MCT, turn them into dv_brace's word
-- and dv_reflect's factor word
-- 阵列齐整对俯冲的设置（D25 / D31 / D51）：从 MCT 读出，换成代码洞 dv_brace 的设置字与 dv_reflect 的倍数字
--
-- [D31, brace-solver-1120] Four settings in the mod's MCT section (beside the breath switch): the master switch,
-- k (a braced soldier's mass against a diving flyer, x the engine's own braced mass), s* (the least share of the
-- slowing a diving flyer takes against a braced front) and, since D51 in place of D15's dive cost, the Charge
-- Reflection factor on flyers. Defaults and ranges: the site table's `brace` (generated from
-- tools/lib/air_dive_rules.py).
--   * master off: both words are 0 (each cave gives the vanilla result).
--   * the word: k in hundredths in the low 16 bits, s* in hundredths in bits 16-23 -- whole numbers below 2^24,
--     exact in the game's float32 numbers (air_dive_rules.brace_word computes the same).
--   * the reflection word: the factor in hundredths (air_dive_rules.reflect_word).
-- [D14 / D31] A multiplayer CAMPAIGN battle reads MCT like a single-player one (MCT hands every machine the host's
-- settings). A multiplayer battle OUTSIDE a campaign uses the defaults: each machine there reads its own MCT values
-- and these settings change the battle simulation (maintainer's call, the breath switch's reason in D14).
-- A setting MCT does not hold, or holds outside its range, falls back to its default and says so.
--
-- Pure module: no core / bm / get_mct here (battle/mod/flyer_dive.lua passes them in), so it runs unchanged in
-- LuaJIT tests. / 纯模块：不直接调用 core / bm / get_mct，由战斗入口传入。

local M = {}

local EPS = 1e-4                -- an MCT slider value is a float32 (3.4 reads 3.4000000953...)

local function round(x) return math.floor(x + 0.5) end

local function defaults(b)
    return { on = b.default_on == true, k = b.k, share = b.share, reflect = b.reflect }
end

-- settings {on, k, share, reflect, why}. `b` is the site table's brace block; `mp` / `from_campaign` the battle's
-- bm:is_multiplayer() / is_from_campaign(); `read_mct(mod_key, option_key)` returns the value MCT holds (nil when
-- MCT is not installed).
function M.decide(b, mp, from_campaign, read_mct)
    local s = defaults(b)
    if mp and not from_campaign then
        s.why = "multiplayer battle outside a campaign: MCT shares no setting between the players there, "
            .. "the defaults apply"
        return s
    end
    if type(read_mct) ~= "function" then
        s.why = "default (MCT not installed)"
        return s
    end
    local notes = {}
    local function take(field, key, valid)
        local ok, v = pcall(read_mct, b.mct_mod, key)
        if not ok then
            notes[#notes + 1] = field .. " default (reading MCT failed: " .. tostring(v) .. ")"
        elseif v == nil then
            notes[#notes + 1] = field .. " default (MCT holds no setting)"
        elseif not valid(v) then
            notes[#notes + 1] = field .. " default (MCT holds " .. tostring(v) .. ")"
        else
            s[field] = v
        end
    end
    local function within(lo, hi)
        return function(v) return type(v) == "number" and v >= lo - EPS and v <= hi + EPS end
    end
    take("on", b.mct_on, function(v) return type(v) == "boolean" end)
    take("k", b.mct_k, within(b.k_min, b.k_max))
    take("share", b.mct_share, within(b.share_min, b.share_max))
    take("reflect", b.mct_reflect, within(b.reflect_min, b.reflect_max))
    s.why = mp and "MCT, multiplayer campaign" or "MCT"
    if #notes > 0 then s.why = s.why .. "; " .. table.concat(notes, "; ") end
    return s
end

local function clamp(x, lo, hi) return math.max(lo, math.min(hi, x)) end

-- k and s* in hundredths, inside the sliders' ranges
local function parts(b, s)
    local k = clamp(round(s.k * b.scale), round(b.k_min * b.scale), round(b.k_max * b.scale))
    local sh = clamp(round(s.share * b.scale), round(b.share_min * b.scale), round(b.share_max * b.scale))
    return k, sh
end

-- dv_brace's u32: 0 when the switch is off
function M.word(b, s)
    if not s.on then return 0 end
    local k, sh = parts(b, s)
    return k + sh * 65536
end

-- dv_reflect's u32: the factor in hundredths inside the slider's range; 0 when the switch is off
function M.reflect_word(b, s)
    if not s.on then return 0 end
    return clamp(round(s.reflect * b.scale), round(b.reflect_min * b.scale), round(b.reflect_max * b.scale))
end

-- the BRACE line's text
function M.describe(b, s)
    if not s.on then return "off: braced units against a dive and Charge Reflection on flyers as in the base game" end
    local k, sh = parts(b, s)
    local r = M.reflect_word(b, s)
    return ("on: braced mass x%d.%02d against a diving flyer, its share of the slowing at least %d.%02d, word %d, "
        .. "Charge Reflection on flyers x%d.%02d, word %d"):format(math.floor(k / 100), k % 100, math.floor(sh / 100),
        sh % 100, M.word(b, s), math.floor(r / 100), r % 100, r)
end

return M
