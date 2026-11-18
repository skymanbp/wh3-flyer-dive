-- pin_on_hit_probe.lua — TEST-ONLY recorder for the flyer take-off rule
-- 测试专用：记录飞兽近战起飞规则在一场战斗里记下了什么、回答了什么
--
-- [AIR-DIVE-TAKEOFF-W1 2026-11-12] Never in a player's pack: packed only by
-- tools/pipelines/build_pin_on_hit_probe.py, next to the shipped take-off
-- scripts (battle/mod/flyer_takeoff.lua installs the caves and starts the
-- rule; this script only reads the caves' buffer through
-- lib/takeoff.lua and, when asked, restarts the rule with another
-- window or mode).
-- CONFIG pin_probe.cfg next to Warhammer3.exe, "key value" lines:
--   window <ticks>   default 0 = the shipped windows by body size (D3); any
--                    other value is written to all five window slots
--   mode <1|2>       default 1; 2 = hits recorded, the game's own engaged
--                    check still answers (the vanilla arm, with the record)
-- WRITES pin_probe.txt next to Warhammer3.exe:
--   BATTLE <stamp> window=<n> mode=<m> table=<entries>
--   UNIT <uid> <alliance> <key> obj=<id> flyer=<0|1>
--   L <ms> <uid> <n> <id> ...     a flyer's living flight entities (unit +0x184
--                                 / +0x188), at the start and when they change
--   H <ms> <tick> <id>:<tick>:<hits> ...   table entries that changed
--   U <ms> <tick> <uid>:<living>:<men alive>:<struck in the window> ...
--                                 (the window: the configured one, else the
--                                 longest shipped window; per-size answers are
--                                 the caves' own, counted in S)
--                                 while any flyer has a struck model, or when
--                                 a count changed
--   S <ms> <tick> stamps=<n> dropped=<n> held=<n> free=<n> unsized=<n> unmatched=<n>
--     used=<entries> stray=<n>
--                                 every 2 s; stray = entries that never were
--                                 in a flyer's list
--   END | FAIL <why>
-- id = the low 8 hex digits of a pointer.

local LOG_FILE, CFG_FILE = "pin_probe.txt", "pin_probe.cfg"
local CALLBACK_NAME = "pin_on_hit_probe_tick"
local SAMPLE_MS, SUMMARY_MS = 200, 2000
local U_ENT_N, U_ENT, U_CTL = 0x184, 0x188, 0x3e30
local BATTLE_OFF, TICKS_OFF, TICK_OFF = 0x58, 0x440, 0x98
local BLOCK = 256                                   -- bytes compared at once when scanning the table

local fmt = string.format
local sub = string.sub_lua or string.sub
local lines = {}
local function emit(s) lines[#lines + 1] = s end
local function flush()
    if #lines == 0 then return end
    local f = io.open(LOG_FILE, "a")
    if f then f:write(table.concat(lines, "\n") .. "\n"); f:close() end
    lines = {}
end

local mr = _G.memreader_plus
if not mr then
    local chunk = loadfile("/script/_lib/mod/memreader_plus")
    if chunk then pcall(chunk) end
    mr = _G.memreader_plus
end

local function id_of(p)
    local text = mr.tostring(p)
    return sub(text, #text - 7, #text)
end

local function read_cfg(defaults)
    local cfg = { window = 0, mode = 1 }
    local f = io.open(CFG_FILE, "r")
    if not f then return cfg end
    for line in f:lines() do
        local k, v = line:match("^%s*(%a+)%s+(%d+)")
        if k and cfg[k] ~= nil then cfg[k] = tonumber(v) end
    end
    f:close()
    return cfg
end

local function each_unit(fn)
    local alliances = bm:alliances()
    for a = 1, alliances:count() do
        local armies = alliances:item(a):armies()
        for j = 1, armies:count() do
            local units = armies:item(j):units()
            for k = 1, units:count() do fn(a, units:item(k)) end
        end
    end
end

local takeoff, buffer, layout, window = nil, nil, nil, nil
local flyers = {}                 -- {uid, unit, obj, list = "id id ..", n, alive, struck}
local ever, seen = {}, {}         -- ids that were in a flyer's list; id -> "tick:hits" last written
local last_summary = -SUMMARY_MS

-- {id = {tick, hits}} of every table entry, read in 4096-byte pieces
local function read_table()
    local map, used = {}, 0
    local zero = string.rep("\0", BLOCK)
    local span = layout.table_slots * layout.entry_bytes
    for off = 0, span - 1, 4096 do
        local piece = mr.read(buffer, layout.table_at + off, math.min(4096, span - off))
        for b = 0, #piece - 1, BLOCK do
            local block = sub(piece, b + 1, b + BLOCK)
            if block ~= zero then
                for e = 0, #block - 1, layout.entry_bytes do
                    local k1, k2, k3, k4, k5, k6, k7, k8, t1, t2, t3, t4, h1, h2, h3, h4 =
                        block:byte(e + 1, e + 16)
                    if k1 + k2 + k3 + k4 + k5 + k6 + k7 + k8 > 0 then
                        used = used + 1
                        map[fmt("%02X%02X%02X%02X", k4, k3, k2, k1)] = {
                            t1 + t2 * 256 + t3 * 65536 + t4 * 16777216,
                            h1 + h2 * 256 + h3 * 65536 + h4 * 16777216 }
                    end
                end
            end
        end
    end
    return map, used
end

local function tick_now()
    for _, f in ipairs(flyers) do
        if f.first then
            local battle = mr.read_pointer(f.first, BATTLE_OFF)
            if not mr.is_null(battle) then
                local ticks = mr.read_pointer(battle, TICKS_OFF)
                if not mr.is_null(ticks) then return mr.read_int32(ticks, TICK_OFF) end
            end
        end
    end
    return -1
end

local function sample()
    local ms = bm:time_elapsed_ms()
    -- the living flight entities of every flyer
    for _, f in ipairs(flyers) do
        local n = mr.read_int32(f.obj, U_ENT_N)
        local ids = {}
        f.first = nil
        if n > 0 and n <= 256 then
            local data = mr.read_pointer(f.obj, U_ENT)
            for i = 0, n - 1 do
                local e = mr.read_pointer(data, i * 8)
                if not mr.is_null(e) then
                    f.first = f.first or e
                    ids[#ids + 1] = id_of(e)
                    ever[ids[#ids]] = true
                end
            end
        end
        local list = table.concat(ids, " ")
        if list ~= f.list then
            f.list, f.ids = list, ids
            emit(fmt("L %d %s %d %s", ms, tostring(f.uid), #ids, list))
        end
    end
    local now = tick_now()
    local map, used = read_table()
    local changed, stray = {}, 0
    for id, e in pairs(map) do
        local sig = e[1] .. ":" .. e[2]
        if seen[id] ~= sig then
            seen[id] = sig
            changed[#changed + 1] = id .. ":" .. sig
        end
        if not ever[id] then stray = stray + 1 end
    end
    if #changed > 0 then
        table.sort(changed)
        emit(fmt("H %d %d %s", ms, now, table.concat(changed, " ")))
    end
    local cells, tell = {}, false
    for _, f in ipairs(flyers) do
        local struck = 0
        for _, id in ipairs(f.ids or {}) do
            local e = map[id]
            if e and now >= e[1] and now - e[1] < window then struck = struck + 1 end
        end
        local alive = -1
        pcall(function() alive = f.unit:number_of_men_alive() end)
        local n = #(f.ids or {})
        if struck > 0 or n ~= f.n or alive ~= f.alive or struck ~= f.struck then tell = true end
        f.n, f.alive, f.struck = n, alive, struck
        cells[#cells + 1] = fmt("%s:%d:%d:%d", tostring(f.uid), n, alive, struck)
    end
    if tell then emit(fmt("U %d %d %s", ms, now, table.concat(cells, " "))) end
    if ms - last_summary >= SUMMARY_MS then
        last_summary = ms
        local c = takeoff.counters(buffer)
        emit(fmt("S %d %d stamps=%d dropped=%d held=%d free=%d unsized=%d unmatched=%d used=%d stray=%d",
            ms, now, c.stamps, c.dropped, c.held, c.free, c.unsized, c.unmatched, used, stray))
    end
    flush()
end

local function start()
    if not mr then emit("FAIL memreader_plus not loaded"); flush(); return end
    local ok, lib = pcall(require, "script/campaign/flyer_dive/lib/takeoff")
    if not ok or type(lib) ~= "table" then emit("FAIL the take-off module did not load: " .. tostring(lib)); flush(); return end
    takeoff = lib
    local complete
    buffer, complete = takeoff.find()
    layout = takeoff.layout()
    local stamp = "?"
    pcall(function() stamp = os.date("%Y-%m-%d %H:%M:%S") end)
    if not buffer or not complete then
        emit("BATTLE " .. stamp)
        emit("FAIL the take-off caves are not in the game: " .. tostring(takeoff.state().why))
        flush()
        return
    end
    local cfg = read_cfg(layout)
    local windows = nil
    window = 0
    if cfg.window > 0 then
        windows = {}
        for i = 1, #layout.windows do windows[i] = cfg.window end
        window = cfg.window
    else
        for _, w in ipairs(layout.windows) do window = math.max(window, w) end
    end
    takeoff.arm(buffer, windows, cfg.mode)
    emit(fmt("BATTLE %s window=%d mode=%d table=%d", stamp, cfg.window, cfg.mode, layout.table_slots))
    each_unit(function(alliance, unit)
        local obj = mr.read_pointer(mr.ud_topointer(unit), 8)
        local flyer = not mr.is_null(mr.read_pointer(obj, U_CTL))
        if flyer then flyers[#flyers + 1] = { uid = unit:unique_ui_id(), unit = unit, obj = obj } end
        emit(fmt("UNIT %s %d %s obj=%s flyer=%d", tostring(unit:unique_ui_id()), alliance, unit:type(),
            id_of(obj), flyer and 1 or 0))
    end)
    flush()
    bm:repeat_callback(function()
        local done, err = pcall(sample)
        if not done then emit("FAIL tick " .. tostring(err)); flush(); bm:remove_callback(CALLBACK_NAME) end
    end, SAMPLE_MS, CALLBACK_NAME)
end

if bm and type(bm.register_phase_change_callback) == "function" then
    bm:register_phase_change_callback("Deployed", function()
        local ok, err = pcall(start)
        if not ok then emit("FAIL start " .. tostring(err)); flush() end
    end)
    bm:register_phase_change_callback("Complete", function()
        pcall(function() bm:remove_callback(CALLBACK_NAME) end)
        emit("END"); flush()
    end)
end
