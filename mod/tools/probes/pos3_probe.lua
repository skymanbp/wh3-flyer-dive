-- pos3: same as pos2 but every unit of alliance 1, with each unit's entity list read the same way (unit +0x184/+0x188;
-- for a non-flyer this list is assumed to hold its soldiers too -- checked by the report against the unit count)
-- smallflyer per-model position + state probe (pos2: adds speed +0x1c8 F32, move state +0x26c, action slot +0x278,
-- model state +0x324; offsets as docs/SPEC.md pillar 2 item 4 and entity_read_report.STATE_KNOCK)
-- smallflyer per-model position probe (lane-only, never shipped): every 200 ms for 90 s after Deployed, the
-- position of every living flight entity of every flight-controller unit (unit +0x184 count / +0x188 array, as
-- flyer_size_probe.lua), read at entity +0x88 (x) / +0x90 (z), the model position the regroup-1119 probe uses
-- (pin_on_hit_probe.lua E_POS, checked there against the unit position). Memory read-only.
-- Writes smallflyer_pos.txt next to Warhammer3.exe:
--   BATTLE <stamp> / UNIT <uid> <alliance> <unit key> n=<entities> / P <ms> <uid> <x:z> <x:z> ... / END | FAIL
local LOG_FILE = "smallflyer_pos3.txt"
local U_ENT_N, U_ENT, U_CTL, E_POS = 0x184, 0x188, 0x3e30, 0x88
local TICK_MS, RUN_MS = 100, 90000
local fmt = string.format
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
local flyers, t0 = {}, 0
local function sample()
    local ms = bm:time_elapsed_ms()
    for _, f in ipairs(flyers) do
        local n = mr.read_int32(f.obj, U_ENT_N)
        if n > 0 and n <= 256 then
            local data = mr.read_pointer(f.obj, U_ENT)
            local cells = {}
            for i = 0, n - 1 do
                local e = mr.read_pointer(data, i * 8)
                if not mr.is_null(e) then
                    cells[#cells + 1] = fmt("%.1f:%.1f:%.1f:%d:%d:%d", mr.read_float(e, E_POS), mr.read_float(e, E_POS + 8),
                        mr.read_float(e, 0x1c8), mr.read_int32(e, 0x26c), mr.read_int32(e, 0x278), mr.read_int32(e, 0x324))
                end
            end
            emit(fmt("P %d %s %s", ms, tostring(f.uid), table.concat(cells, " ")))
        end
    end
    if ms - t0 >= RUN_MS then
        bm:remove_callback("smallflyer_pos3")
        emit("END")
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
                if a == 1 then   -- pos3: every unit of the charging side (ground cavalry included), not only flyers
                    flyers[#flyers + 1] = { uid = unit:unique_ui_id(), obj = obj }
                    emit(fmt("UNIT %s %d %s n=%d", tostring(unit:unique_ui_id()), a, unit:type(),
                        mr.read_int32(obj, U_ENT_N)))
                end
            end
        end
    end
    if #flyers == 0 then emit("FAIL no unit with a flight controller") end
    t0 = bm:time_elapsed_ms()
    flush()
    bm:repeat_callback(function()
        local ok, err = pcall(sample)
        if not ok then emit("FAIL sample " .. tostring(err)); flush() end
    end, TICK_MS, "smallflyer_pos3")
end
if bm and type(bm.register_phase_change_callback) == "function" then
    bm:register_phase_change_callback("Deployed", function()
        local ok, err = pcall(start)
        if not ok then emit("FAIL start " .. tostring(err)); flush() end
    end)
end
