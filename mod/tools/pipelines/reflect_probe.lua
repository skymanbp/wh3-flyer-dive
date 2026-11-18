-- reflect_probe.lua — TEST-ONLY recorder for the impact-damage probe (update-1117 part C)
-- 测试专用：冲锋反制实测记录（地面骑兵正对照 + 飞兽各道）
--
-- Never in a player's pack: packed only by tools/pipelines/build_pin_on_hit_probe.py --reflect,
-- with the generated site table script/reflect_probe/reflect_probe_site.lua
-- (tools/pipelines/reflect_probe_asm.py: logger caves, every call, no flyer filter; d3-1118 added
-- rf_brace at the reflection check 0x14325bbec and rf_act1 / rf_act2 at the two per-soldier
-- action updates that call it).
-- Single player only (it installs caves). Installs at Deployed, after the take-off battle entry
-- installed its own caves at chunk scope (reflect_probe_asm.py docstring: the rf_dmg pattern
-- starts after pin_stamp's stolen bytes).
-- WRITES reflect_probe.txt next to Warhammer3.exe:
--   BATTLE <stamp> on|off <why>
--   UNIT <uid> <alliance> <key> obj=<id8> men=<n> flyer=<0|1>
--   R <ms> <tick> <reflector8> <charger8> <ret> <speed> <reflector unit8> <charger unit8>
--     <charger flyer> <reflector +0xbc> <reflector +0x6c>          every impact reflection
--   D <ms> <tick> <ret> <victim8> <victim unit8> <damage> <type> <flyer> <flyer entity8> <thread> <clock>
--                                                               every damage-applier call
--   C <ms> <which> <target if8> <source if8> <ret1> <ret2> <xmm0> <xmm6> <xmm7> <xmm8> <thread> <clock>
--     <[target+8]8> <[target+0x10]8> <[source+8]8> <[source+0x10]8>
--                                     [d10-1118] the damage calculator 0x142e5fcb0 passed its charge-reflect
--                                     test (which 1, rf_cgate) / applied the multiplier (2, rf_cmul); the
--                                     first C_LINES of them (floats as big-endian hex)
--   CS <ms> <which> <ret1> <ret2> n=<calls>    every 2 s, every C call since the last summary
--   B <ms> <tick> <reflector8> <reflector unit8> <reflector +0x318 hex8> <flag> <enemies> <x> <z> <radius>
--     <enemy8> <enemy unit8> <enemy +0x324> <x> <z>  (twice)   a call of the reflection check,
--                                     the first B_LINES of them (floats as big-endian hex)
--   A <ms> <tick> <which> <soldier8> <soldier unit8> <soldier +0x318> <action +0x38> <+0x48> <+0x7c>
--                                     a call of action update 1 / 2, the first A_LINES of them
--   BS <ms> <reflector unit8> <+0x318> <flag> <enemies> <first enemy +0x324> n=<calls>
--   AS <ms> <which> <soldier unit8> <+0x318> <action +0x38> n=<calls>
--                                     every 2 s: every call since the last summary, by those fields
--   U <ms> <uid>:<unary hp>:<men alive>:<in melee> ...          every 100 ms, every unit
--   S <ms> refl=<n> dmg=<n> brace=<n> act=<n> lost_refl=<n> lost_dmg=<n> lost_brace=<n> lost_act=<n>
--     cr=<n> lost_cr=<n>
--                                                                every 2 s
--   END
-- id8 = the low 8 hex digits of a pointer (the units' obj ids match a D / R line's unit8).
-- tools/pipelines/reflect_probe_report.py reads it.

local LOG_FILE = "reflect_probe.txt"
local CALLBACK = "reflect_probe_tick"
local SAMPLE_MS, SUMMARY_MS = 100, 2000
local B_LINES, A_LINES = 3000, 1000           -- d3-1118: raw lines kept; the summaries count all
local C_LINES = 5000                          -- d10-1118

local lines = {}
local function emit(s) lines[#lines + 1] = s end
local function flush()
    if #lines == 0 then return end
    local f = io.open(LOG_FILE, "a")
    if f then f:write(table.concat(lines, "\n") .. "\n"); f:close() end
    lines = {}
end

if not bm then emit("FAIL no bm"); flush(); return end
if not _G.memreader_plus then
    local chunk = loadfile("/script/_lib/mod/memreader_plus")
    if chunk then
        if core and type(core.get_env) == "function" then setfenv(chunk, core:get_env()) end
        pcall(chunk)
    end
end
local mr = _G.memreader_plus
local fmt = string.format
local function sub(s, i, j) return (string.sub_lua or string.sub)(s, i, j) end
local function u32(raw, at)
    local a, b, c, d = raw:byte(at + 1, at + 4)
    return a + b * 256 + c * 65536 + d * 16777216
end
local function i32(raw, at)
    local v = u32(raw, at)
    if v >= 2147483648 then v = v - 4294967296 end
    return v
end
local function hexle(raw)         -- little-endian bytes -> hex, most significant first
    local out = {}
    for i = #raw, 1, -1 do out[#out + 1] = fmt("%02X", raw:byte(i)) end
    return table.concat(out)
end
local function low8(raw) return sub(hexle(raw), 9, 16) end
local function f32hex(raw) return hexle(raw) end   -- the report decodes the float
local function id8(p) local t = mr.tostring(p); return sub(t, #t - 7, #t) end

local buf, site, l = nil, nil, nil

local function install()
    if not mr then return nil, "no memreader_plus" end
    local mp = false
    pcall(function() mp = bm:is_multiplayer() and true or false end)
    if mp then return nil, "multiplayer" end
    local ok, s = pcall(require, "script/reflect_probe/reflect_probe_site")
    if not ok or type(s) ~= "table" then return nil, "site: " .. tostring(s) end
    local h, refused = mr.patcher(s.owner)
    if not h then return nil, "patcher refused: " .. tostring(refused) end
    local api = h:sites(s.entries, function(t) emit("SITE " .. tostring(t)) end)
    if not api then return nil, "sites failed" end
    for _, name in ipairs(s.caves) do
        if not api.found(name) then return nil, name .. " not usable: " .. tostring(api.why(name)) end
    end
    local b = mr.game_alloc(s.layout.bytes)
    if not b then return nil, "game_alloc failed" end
    local zeros = string.rep("\0", 4096)
    for off = 0, s.layout.bytes - 1, 4096 do mr.write(b, off, sub(zeros, 1, math.min(4096, s.layout.bytes - off))) end
    mr.write(b, s.layout.magic_at, s.layout.magic)
    local given = {}
    for _, name in ipairs(s.caves) do given[name] = { buf = b } end
    local done, problem = api.install_feature(s.feature, given)
    if not done then return nil, "install failed: " .. tostring(problem) end
    return b, s
end

local units = {}
local function list_units()
    local alliances = bm:alliances()
    for a = 1, alliances:count() do
        local armies = alliances:item(a):armies()
        for j = 1, armies:count() do
            local us = armies:item(j):units()
            for k = 1, us:count() do
                local unit = us:item(k)
                local obj = mr.read_pointer(mr.ud_topointer(unit), 8)
                local flyer = mr.is_null(mr.read_pointer(obj, 0x3e30)) and 0 or 1
                units[#units + 1] = { uid = tostring(unit:unique_ui_id()), unit = unit }
                emit(fmt("UNIT %s %d %s obj=%s men=%d flyer=%d", tostring(unit:unique_ui_id()), a, unit:type(),
                    id8(obj), unit:number_of_men_alive(), flyer))
            end
        end
    end
end

local seen_r, seen_d, lost_r, lost_d, last_s = 0, 0, 0, 0, -SUMMARY_MS
local seen_b, seen_a, lost_b, lost_a, lines_b, lines_a = 0, 0, 0, 0, 0, 0
local agg_b, agg_a = {}, {}
local seen_c, lost_c, lines_c, agg_c = 0, 0, 0, {}

-- entries of one ring not read yet; `size` / `seq_at` default to the 64-byte rings (seq at +60)
local function drain(count_at, ring_at, slots, seen, lost, line, size, seq_at)
    size, seq_at = size or l.entry, seq_at or 60
    local count = u32(mr.read(buf, count_at, 4), 0)
    if count - seen > slots then
        lost = lost + (count - seen - slots)
        seen = count - slots
    end
    while seen < count do
        local e = mr.read(buf, ring_at + (seen % slots) * size, size)
        if u32(e, seq_at) ~= seen + 1 then break end       -- not written yet
        local text = line(e)
        if text then emit(text) end
        seen = seen + 1
    end
    return seen, lost, count
end

local function bump(agg, key) agg[key] = (agg[key] or 0) + 1 end

local function tick()
    local ms = bm:time_elapsed_ms()
    local nr, nd
    seen_r, lost_r, nr = drain(l.refl_count_at, l.refl_ring_at, l.refl_slots, seen_r, lost_r, function(e)
        return fmt("R %d %d %s %s %s %s %s %s %d %s %d", ms, u32(e, 28), low8(sub(e, 1, 8)), low8(sub(e, 9, 16)),
            hexle(sub(e, 17, 24)), f32hex(sub(e, 25, 28)), low8(sub(e, 33, 40)), low8(sub(e, 41, 48)),
            u32(e, 48), f32hex(sub(e, 53, 56)), u32(e, 56))
    end)
    seen_d, lost_d, nd = drain(l.dmg_count_at, l.dmg_ring_at, l.dmg_slots, seen_d, lost_d, function(e)
        return fmt("D %d %d %s %s %s %d %d %d %s %d %d", ms, u32(e, 32), hexle(sub(e, 1, 8)), low8(sub(e, 9, 16)),
            low8(sub(e, 17, 24)), i32(e, 24), u32(e, 28), u32(e, 36), low8(sub(e, 41, 48)), u32(e, 48), u32(e, 52))
    end)
    local nb, na
    seen_b, lost_b, nb = drain(l.brace_count_at, l.brace_ring_at, l.brace_slots, seen_b, lost_b, function(e)
        bump(agg_b, fmt("%s %s %d %d %s", low8(sub(e, 9, 16)), hexle(sub(e, 17, 20)), u32(e, 20), u32(e, 24),
            hexle(sub(e, 65, 68))))
        if lines_b >= B_LINES then return nil end
        lines_b = lines_b + 1
        return fmt("B %d %d %s %s %s %d %d %s %s %s %s %s %s %s %s %s %s %s %s %s", ms, u32(e, 28),
            low8(sub(e, 1, 8)), low8(sub(e, 9, 16)), hexle(sub(e, 17, 20)), u32(e, 20), u32(e, 24),
            f32hex(sub(e, 33, 36)), f32hex(sub(e, 37, 40)), f32hex(sub(e, 41, 44)),
            low8(sub(e, 49, 56)), low8(sub(e, 57, 64)), hexle(sub(e, 65, 68)), f32hex(sub(e, 69, 72)), f32hex(sub(e, 73, 76)),
            low8(sub(e, 81, 88)), low8(sub(e, 89, 96)), hexle(sub(e, 97, 100)), f32hex(sub(e, 101, 104)), f32hex(sub(e, 105, 108)))
    end, l.brace_entry, 124)
    seen_a, lost_a, na = drain(l.act_count_at, l.act_ring_at, l.act_slots, seen_a, lost_a, function(e)
        bump(agg_a, fmt("%d %s %s %s", u32(e, 24), low8(sub(e, 9, 16)), hexle(sub(e, 17, 20)), hexle(sub(e, 21, 24))))
        if lines_a >= A_LINES then return nil end
        lines_a = lines_a + 1
        return fmt("A %d %d %d %s %s %s %s %d %d", ms, u32(e, 28), u32(e, 24), low8(sub(e, 1, 8)),
            low8(sub(e, 9, 16)), hexle(sub(e, 17, 20)), hexle(sub(e, 21, 24)), u32(e, 32), u32(e, 36))
    end)
    local nc = 0
    if l.cr_ring_at then
        seen_c, lost_c, nc = drain(l.cr_count_at, l.cr_ring_at, l.cr_slots, seen_c, lost_c, function(e)
            bump(agg_c, fmt("%d %s %s", u32(e, 32), hexle(sub(e, 17, 24)), hexle(sub(e, 25, 32))))
            if lines_c >= C_LINES then return nil end
            lines_c = lines_c + 1
            return fmt("C %d %d %s %s %s %s %s %s %s %s %d %d %s %s %s %s", ms, u32(e, 32), low8(sub(e, 1, 8)),
                low8(sub(e, 9, 16)), hexle(sub(e, 17, 24)), hexle(sub(e, 25, 32)), f32hex(sub(e, 37, 40)),
                f32hex(sub(e, 41, 44)), f32hex(sub(e, 45, 48)), f32hex(sub(e, 57, 60)), u32(e, 48), u32(e, 52),
                low8(sub(e, 65, 72)), low8(sub(e, 73, 80)), low8(sub(e, 81, 88)), low8(sub(e, 89, 96)))
        end, l.cr_entry, 124)
    end
    local cells = {}
    for _, u in ipairs(units) do
        local hp, men, melee = -1, -1, false
        pcall(function() hp = u.unit:unary_hitpoints() end)
        pcall(function() men = u.unit:number_of_men_alive() end)
        pcall(function() melee = u.unit:is_in_melee() end)
        cells[#cells + 1] = fmt("%s:%.5f:%d:%s", u.uid, hp, men, melee and 1 or 0)
    end
    emit(fmt("U %d %s", ms, table.concat(cells, " ")))
    if ms - last_s >= SUMMARY_MS then
        last_s = ms
        for key, n in pairs(agg_b) do emit(fmt("BS %d %s n=%d", ms, key, n)) end
        for key, n in pairs(agg_a) do emit(fmt("AS %d %s n=%d", ms, key, n)) end
        for key, n in pairs(agg_c) do emit(fmt("CS %d %s n=%d", ms, key, n)) end
        agg_b, agg_a, agg_c = {}, {}, {}
        emit(fmt("S %d refl=%d dmg=%d brace=%d act=%d lost_refl=%d lost_dmg=%d lost_brace=%d lost_act=%d cr=%d lost_cr=%d",
            ms, nr, nd, nb, na, lost_r, lost_d, lost_b, lost_a, nc, lost_c))
    end
    flush()
end

bm:register_phase_change_callback("Deployed", function()
    local stamp = "?"
    pcall(function() stamp = os.date("%Y-%m-%d %H:%M:%S") end)
    local ok, b, s = pcall(install)
    if not ok or not b then
        emit(fmt("BATTLE %s off: %s", stamp, tostring(ok and s or b))); flush()
        return
    end
    buf, site, l = b, s, s.layout
    emit(fmt("BATTLE %s on: buffer %s", stamp, mr.tostring(buf)))
    pcall(list_units)
    mr.write(buf, l.mode_at, mr.uint32(1))
    flush()
    bm:repeat_callback(function()
        local tok, err = pcall(tick)
        if not tok then
            emit("STOP " .. tostring(err)); flush()
            pcall(function() bm:remove_callback(CALLBACK) end)
        end
    end, SAMPLE_MS, CALLBACK)
end)

bm:register_phase_change_callback("Complete", function()
    if not buf then return end
    pcall(function() mr.write(buf, l.mode_at, mr.uint32(0)) end)
    pcall(tick)
    pcall(function() bm:remove_callback(CALLBACK) end)
    emit("END"); flush()
end)
