-- ld_air_dive_probe.lua — battle-side movement recorder for the air-dive lane
-- 飞兽俯冲探针：战斗中每 0.1 秒记录接敌单位的位置、速度与状态。
--
-- [AIR-DIVE-W4 2026-11-09] W2 and W3 changed the land clip's metadata and its
-- run-out, and both times the user saw the same thing in a custom battle: the
-- flyer lands at the enemy's front rank and stops. Three file-level guesses
-- failed, so this measures what the engine actually does with the body. It
-- ships ONLY in the standalone ld_air_dive.pack / ld_air_dive_probe.pack built
-- by tools/pipelines/build_air_dive_minimod.py --probe, never in ld_mod.pack;
-- tools/pipelines/air_dive_probe_report.py reads what it writes.
--
-- WHAT IT WRITES: ld_air_dive_probe.txt in the game's working directory (the
-- folder of Warhammer3.exe, same relative-path convention as ld_battle_probe /
-- ld_selftest). Appends; every battle starts with a "BATTLE" line.
--   UNIT  <uid> <alliance> <key> fly=<can_fly> men=<initial men> class=<unit_class>
--   S <ms> <uid> <x> <y> <z> <spd> <bearing> <cur_fly> <moving> <fast> <melee>
--     <alive> <near_uid> <near_dist> <near_x> <near_z> <near_bearing>
--   (spd = horizontal m/s since this unit's previous sample; booleans 1/0,
--    "na" when the engine call failed)
--
-- COST: one position() per unit per tick, nearest-enemy search in plain Lua,
-- rows written only for units within GATE_M of an enemy. Small units (flyers,
-- monsters, cavalry, chariots: initial men <= SMALL_MEN) are sampled every
-- tick; big infantry, which is mostly the target formation, every 5th tick.
-- The file stops growing at MAX_BYTES.
--
-- API provenance (CA's own scripts, data_script.pack, verified 2026-11-09):
--   bm:register_phase_change_callback  _lib/lib_battle_manager.lua:1227
--   bm:repeat_callback / remove_callback  lib_battle_manager.lua:1943 / :1952
--   bm:time_elapsed_ms                 lib_battle_manager.lua:2123 (self:)
--   bm:alliances() :armies() :units() :count() :item()
--                                      lib_battle_manager.lua:802, ld_incarnate_watch
--   army:num_reinforcement_units / get_reinforcement_units
--                                      lib_battle_script_unit.lua:95 / :105
--   unit:position() vec:get_x/get_y/get_z  lib_battle_cutscene.lua:1805-1807
--   unit:bearing() (degrees)           lib_battle_cutscene.lua:1834 (d_to_r)
--   unit:unique_ui_id()                lib_battle_script_unit.lua:210
--   unit:type()                        ld_incarnate_watch.lua (unit key)
--   unit:can_fly()                     battle/wh_battle_advice.lua:989
--   unit:is_currently_flying()         quest_battles/drycha/coeddil_unchained/battle_script.lua:566
--   unit:is_moving()                   quest_battles/astragoth/black_hammer_of_hashut/battle_script.lua:375
--   unit:is_moving_fast()              lib_battle_script_unit.lua:691
--   unit:is_in_melee()                 lib_battle_script_unit.lua:773
--   unit:number_of_men_alive / initial_number_of_men  lib_battle_script_unit.lua
--   unit:unit_class()                  lib_battle_advice.lua:876
-- Every engine call is wrapped so a missing method records "na" instead of
-- killing the probe (lib_core pcall would otherwise swallow it silently).
--
-- Chunk scope on purpose: the battle loader loads mod files but never calls a
-- function named after the file (see ld_battle_probe.lua header).

local LOG_FILE = "ld_air_dive_probe.txt"
local VARIANT = "@VARIANT@"   -- substituted by build_air_dive_minimod.py
local TICK_MS = 100
local GATE_M = 80
local SMALL_MEN = 48
local BIG_EVERY = 5
local MAX_BYTES = 30 * 1024 * 1024
local CALLBACK_NAME = "ld_air_dive_probe_tick"

local fmt = string.format

local buffer, written, stopped = {}, 0, false

local function flush()
    if #buffer == 0 then return end
    local f = io.open(LOG_FILE, "a")
    if not f then buffer = {}; return end
    local chunk = table.concat(buffer, "\n") .. "\n"
    f:write(chunk)
    f:close()
    written = written + #chunk
    buffer = {}
end

local function emit(line)
    if stopped then return end
    buffer[#buffer + 1] = line
    if written > MAX_BYTES then
        buffer[#buffer + 1] = "STOP max_bytes"
        stopped = true
        flush()
    end
end

local function call(unit, method)
    local ok, value = pcall(function() return unit[method](unit) end)
    if ok then return value end
    return nil
end

local function b(v)
    if v == nil then return "na" end
    return v and "1" or "0"
end

-- every unit of an army: main units plus each reinforcement set
local function each_unit(fn)
    local alliances = bm:alliances()
    for a = 1, alliances:count() do
        local armies = alliances:item(a):armies()
        for j = 1, armies:count() do
            local army = armies:item(j)
            local lists = { army:units() }
            local ok, n = pcall(function() return army:num_reinforcement_units() end)
            if ok and n then
                for k = 1, n do lists[#lists + 1] = army:get_reinforcement_units(k) end
            end
            for _, units in ipairs(lists) do
                for k = 1, units:count() do fn(a, units:item(k)) end
            end
        end
    end
end

local known = {}      -- uid -> { small = bool, last_x, last_z, last_ms }
local tick_no = 0

local function tick()
    if stopped then return end
    tick_no = tick_no + 1
    local now = bm:time_elapsed_ms()
    local snap = {}
    each_unit(function(alliance, unit)
        local uid = call(unit, "unique_ui_id")
        if uid == nil then return end
        local alive = call(unit, "number_of_men_alive") or 0
        if alive <= 0 then return end
        local pos = call(unit, "position")
        if pos == nil then return end
        local info = known[uid]
        if not info then
            local men = call(unit, "initial_number_of_men") or 0
            local fly = call(unit, "can_fly")
            info = { small = (fly == true) or (men > 0 and men <= SMALL_MEN) }
            known[uid] = info
            emit(fmt("UNIT %s %d %s fly=%s men=%d class=%s", tostring(uid),
                alliance, tostring(call(unit, "type")), b(fly), men,
                tostring(call(unit, "unit_class"))))
        end
        snap[#snap + 1] = { uid = uid, a = alliance, u = unit, info = info,
            alive = alive, x = pos:get_x(), y = pos:get_y(), z = pos:get_z() }
    end)
    for i = 1, #snap do
        local s = snap[i]
        local best, bd2 = nil, GATE_M * GATE_M
        for j = 1, #snap do
            local e = snap[j]
            if e.a ~= s.a then
                local dx, dz = e.x - s.x, e.z - s.z
                local d2 = dx * dx + dz * dz
                if d2 < bd2 then best, bd2 = e, d2 end
            end
        end
        local info = s.info
        local spd = -1
        if info.last_ms and now > info.last_ms then
            local dx, dz = s.x - info.last_x, s.z - info.last_z
            spd = math.sqrt(dx * dx + dz * dz) * 1000 / (now - info.last_ms)
        end
        if best and (info.small or tick_no % BIG_EVERY == 0) then
            local u = s.u
            emit(fmt("S %d %s %.2f %.2f %.2f %.2f %.1f %s %s %s %s %d %s %.2f %.2f %.2f %.1f",
                now, tostring(s.uid), s.x, s.y, s.z, spd,
                call(u, "bearing") or -1,
                b(call(u, "is_currently_flying")), b(call(u, "is_moving")),
                b(call(u, "is_moving_fast")), b(call(u, "is_in_melee")),
                s.alive, tostring(best.uid), math.sqrt(bd2), best.x, best.z,
                call(best.u, "bearing") or -1))
            info.last_x, info.last_z, info.last_ms = s.x, s.z, now
        elseif not best then
            info.last_ms = nil   -- out of range: speed restarts on re-entry
        else
            info.last_x, info.last_z, info.last_ms = s.x, s.z, now
        end
    end
    if tick_no % 10 == 0 then flush() end
end

local function start()
    local stamp = "?"
    pcall(function() stamp = os.date("%Y-%m-%d %H:%M:%S") end)
    emit(fmt("BATTLE %s variant=%s tick_ms=%d gate_m=%d", stamp, VARIANT,
        TICK_MS, GATE_M))
    flush()
    bm:repeat_callback(function()
        local ok, err = pcall(tick)
        if not ok then
            emit("ERROR " .. tostring(err))
            flush()
            stopped = true
            bm:remove_callback(CALLBACK_NAME)
        end
    end, TICK_MS, CALLBACK_NAME)
end

if bm and type(bm.register_phase_change_callback) == "function" then
    bm:register_phase_change_callback("Deployed", function()
        local ok, err = pcall(start)
        if not ok then emit("ERROR start " .. tostring(err)); flush() end
    end)
    bm:register_phase_change_callback("Complete", function()
        pcall(function() bm:remove_callback(CALLBACK_NAME) end)
        emit("END")
        flush()
    end)
else
    local f = io.open(LOG_FILE, "a")
    if f then f:write("FAIL bm unavailable at chunk scope\n"); f:close() end
end

