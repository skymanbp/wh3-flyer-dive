-- flyer_size_probe.lua — TEST-ONLY reader: the candidate engine size field of every flying model
-- 测试专用：读每个飞行兵模的候选体型字段
--
-- [update-1117 B, user ruling D3 2026-11-17: take-off window by body size]
-- Never in a player's pack: packed only by tools/pipelines/build_pin_on_hit_probe.py
-- --size-read. Memory read-only (memreader Plus read calls; no write, no cave).
-- Question it answers: does the engine entity hold the battle_entities ``size``
-- class at +0x74? The static read (design.md section 2, work list item 2) found
-- [entity+0x74] compared as an ordered integer between a pushing and a pushed
-- model in the knock code (0x14306155b: <= 1 cannot knock flying; 0x143061598:
-- class difference > 1 swaps a constant); which integer is which size is not
-- known statically.
-- For every unit with a flight controller (unit +0x3e30), each living flight
-- entity (unit +0x184 count / +0x188 array; the flight controller's own entity,
-- i.e. the mount of a ridden unit): one line with the raw bytes +0x60..+0xbf
-- (96 bytes, hex), so the report reads +0x74 (int32) and the neighbours without
-- a second run. Read at Deployed and again READ_AGAIN_MS later (the value must
-- not change).
-- WRITES flyer_size_probe.txt next to Warhammer3.exe:
--   BATTLE <stamp>
--   UNIT <uid> <alliance> <unit key> n=<flight entities>
--   E <ms> <uid> <index> <entity id> <hex of +0x60..+0xbf>
--   END | FAIL <why>
-- tools/pipelines/flyer_size_probe_report.py joins it with the installed tables.

local LOG_FILE = "flyer_size_probe.txt"
local U_ENT_N, U_ENT, U_CTL = 0x184, 0x188, 0x3e30
local FIRST, SPAN = 0x60, 0x60
local READ_AGAIN_MS = 10000
local CALLBACK_NAME = "flyer_size_probe_again"

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

local function hex(bytes)
    local out = {}
    for i = 1, #bytes do out[i] = fmt("%02x", bytes:byte(i)) end
    return table.concat(out)
end

local flyers = {}

local function read_all()
    local ms = bm:time_elapsed_ms()
    for _, f in ipairs(flyers) do
        local n = mr.read_int32(f.obj, U_ENT_N)
        if n > 0 and n <= 256 then
            local data = mr.read_pointer(f.obj, U_ENT)
            for i = 0, n - 1 do
                local e = mr.read_pointer(data, i * 8)
                if not mr.is_null(e) then
                    emit(fmt("E %d %s %d %s %s", ms, tostring(f.uid), i, id_of(e), hex(mr.read(e, FIRST, SPAN))))
                end
            end
        end
    end
    flush()
end

local function start()
    if not mr then emit("FAIL memreader_plus not loaded"); flush(); return end
    local stamp = "?"
    pcall(function() stamp = os.date("%Y-%m-%d %H:%M:%S") end)
    emit("BATTLE " .. stamp)
    local alliances = bm:alliances()
    for a = 1, alliances:count() do
        local armies = alliances:item(a):armies()
        for j = 1, armies:count() do
            local units = armies:item(j):units()
            for k = 1, units:count() do
                local unit = units:item(k)
                local obj = mr.read_pointer(mr.ud_topointer(unit), 8)
                if not mr.is_null(mr.read_pointer(obj, U_CTL)) then
                    flyers[#flyers + 1] = { uid = unit:unique_ui_id(), obj = obj }
                    emit(fmt("UNIT %s %d %s n=%d", tostring(unit:unique_ui_id()), a, unit:type(),
                        mr.read_int32(obj, U_ENT_N)))
                end
            end
        end
    end
    if #flyers == 0 then emit("FAIL no unit with a flight controller in this battle") end
    read_all()
    bm:callback(function()
        local ok, err = pcall(read_all)
        if not ok then emit("FAIL second read " .. tostring(err)) end
        emit("END"); flush()
    end, READ_AGAIN_MS, CALLBACK_NAME)
end

if bm and type(bm.register_phase_change_callback) == "function" then
    bm:register_phase_change_callback("Deployed", function()
        local ok, err = pcall(start)
        if not ok then emit("FAIL start " .. tostring(err)); flush() end
    end)
end
