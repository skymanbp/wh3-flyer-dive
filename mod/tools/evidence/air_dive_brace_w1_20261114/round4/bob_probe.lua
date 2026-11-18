-- TEST-ONLY (AIR-DIVE-BRACE-W1 round 4): why do follower models of a multi-model flyer climb back up after
-- the lead lands? Every 100 ms, for every multi-model flying unit (more than one model, flight controller set):
--   B <ms> <uid> <i> <body8> <+0x104 layer> <+0x710 flight> <+0x26c state> <y +0x8c> <vy +0xe4> <x> <z>
--       <goal +0x1e0> <goal +0x1e8> <+0x180 cap> <order vt8>
-- and, from the first landed model of the unit until 12 s later, for models 0..MAX_DUMP-1:
--   E <ms> <uid> <i> <hex of 0x900 bytes of the body>
--   C <ms> <uid> <i> <fc8> <hex of 0x300 bytes of the flight controller (+0x128)>
-- Lines go to ld_bob_probe.txt in the game folder.
local LOG_FILE = "ld_bob_probe.txt"
local CALLBACK = "ld_bob_probe_tick"
local BODY_BYTES, FC_BYTES, MAX_DUMP, WINDOW_MS = 0x900, 0x300, 12, 12000

local function record(line)
    local f = io.open(LOG_FILE, "a")
    if f then f:write(line .. "\n"); f:close() end
end
if not bm then record("FAIL no bm"); return end
if not _G.memreader_plus then
    local chunk = loadfile("/script/_lib/mod/memreader_plus")
    if chunk then
        if core and type(core.get_env) == "function" then setfenv(chunk, core:get_env()) end
        pcall(chunk)
    end
end
local mr = _G.memreader_plus
if not mr then record("FAIL no memreader"); return end
local function sub(s, i, j) return (string.sub_lua or string.sub)(s, i, j) end
local function low8(p) return sub(mr.tostring(p), -8) end
local function hexfwd(raw)
    local out = {}
    for i = 1, #raw do out[#out + 1] = string.format("%02X", raw:byte(i)) end
    return table.concat(out)
end
local stamp = "?"
pcall(function() stamp = os.date("%Y-%m-%d %H:%M:%S") end)
record("BATTLE " .. stamp)

local landed_at = {}      -- uid -> ms of the unit's first landed model
local function tick()
    local ms = bm:time_elapsed_ms()
    local alliances = bm:alliances()
    for a = 1, alliances:count() do
        local armies = alliances:item(a):armies()
        for j = 1, armies:count() do
            local units = armies:item(j):units()
            for k = 1, units:count() do
                local unit = units:item(k)
                local uid = "?"
                pcall(function() uid = tostring(unit:unique_ui_id()) end)
                local obj = mr.read_pointer(mr.ud_topointer(unit), 8)
                if not mr.is_null(obj) then
                    local n, data = mr.read_int32(obj, 0xa4), mr.read_pointer(obj, 0xa8)
                    local first = n > 1 and mr.read_pointer(data, 0) or nil
                    local fb = first and not mr.is_null(first) and (function()
                        local p = mr.read_pointer(first, 0x2e0)
                        return mr.is_null(p) and first or p
                    end)() or nil
                    if fb and not mr.is_null(mr.read_pointer(fb, 0x128)) then
                        for i = 0, n - 1 do
                            local m = mr.read_pointer(data, i * 8)
                            if not mr.is_null(m) then
                                local p = mr.read_pointer(m, 0x2e0)
                                local b = mr.is_null(p) and m or p
                                local lay = mr.read_int32(b, 0x104)
                                if lay == 0 and not landed_at[uid] then landed_at[uid] = ms end
                                record(("B %d %s %d %s %d %d %d %.3f %.3f %.2f %.2f %.2f %.2f %.2f %s"):format(ms, uid, i,
                                    low8(b), lay, mr.read_int32(b, 0x710), mr.read_int32(b, 0x26c),
                                    mr.read_float(b, 0x8c), mr.read_float(b, 0xe4), mr.read_float(b, 0x88),
                                    mr.read_float(b, 0x90), mr.read_float(b, 0x1e0), mr.read_float(b, 0x1e8),
                                    mr.read_float(b, 0x180), low8(mr.read_pointer(b, 0x330))))
                                local t0 = landed_at[uid]
                                if t0 and ms - t0 <= WINDOW_MS and i < MAX_DUMP then
                                    record(("E %d %s %d %s"):format(ms, uid, i, hexfwd(mr.read(b, 0, BODY_BYTES))))
                                    local fc = mr.read_pointer(b, 0x128)
                                    if not mr.is_null(fc) then
                                        record(("C %d %s %d %s %s"):format(ms, uid, i, low8(fc),
                                            hexfwd(mr.read(fc, 0, FC_BYTES))))
                                    end
                                end
                            end
                        end
                    end
                end
            end
        end
    end
end

bm:register_phase_change_callback("Deployed", function()
    bm:repeat_callback(function()
        local ok, err = pcall(tick)
        if not ok then
            record("STOP " .. tostring(err))
            pcall(function() bm:remove_callback(CALLBACK) end)
        end
    end, 100, CALLBACK)
end)
bm:register_phase_change_callback("Complete", function()
    pcall(function() bm:remove_callback(CALLBACK) end)
    record("END")
end)
