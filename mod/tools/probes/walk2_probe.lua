-- generated from the installed db.pack by the lane (body = mount entity or man_entity; man = man_entity)
local SPEEDS = {
    ["wh2_dlc10_def_mon_feral_manticore_0"] = { 2.2, 7.0, 2.2, 7.0 },
    ["wh2_dlc15_hef_inf_mistwalkers_griffon_knights_0"] = { 3.0, 7.0, 1.5, 3.4 },
    ["wh2_main_hef_cha_prince_0"] = { 1.5, 3.6, 1.5, 3.6 },
    ["wh2_main_hef_mon_star_dragon"] = { 3.0, 6.5, 3.0, 6.5 },
    ["wh2_main_lzd_mon_carnosaur_0"] = { 2.5, 7.5, 2.5, 7.5 },
    ["wh3_dlc20_chs_inf_chosen_mtze_halberds"] = { 1.5, 2.8, 1.5, 2.8 },
    ["wh_dlc07_brt_cav_royal_hippogryph_knights_0"] = { 2.5, 7.0, 1.5, 3.3 },
    ["wh_dlc08_nor_mon_war_mammoth_0"] = { 2.6, 5.6, 2.6, 5.6 },
    ["wh_main_brt_cav_pegasus_knights"] = { 2.0, 8.2, 1.5, 3.3 },
    ["wh_main_emp_cha_general_0"] = { 1.5, 3.4, 1.5, 3.4 },
    ["wh_main_emp_inf_spearmen_1"] = { 1.5, 3.0, 1.5, 3.0 },
    ["wh_main_emp_inf_swordsmen"] = { 1.5, 3.0, 1.5, 3.0 },
}
-- walk2_probe (lane-only, never shipped): battle_entities.walk_speed behind one pointer of the entity (D64).
-- 3 s after Deployed, for every unit of both alliances: its first entity (unit +0x184 / +0x188) and, when it has
-- one, the entity it rides (+0x2e0). For every qword at +0 .. +0x1000 whose high dword is 1 .. 0x7fff (a user-
-- space pointer; float pairs and small integers never are), the floats at +0 .. +0x200 behind it: a hit is a
-- float equal to the unit's walk speed (table above, from db.pack) with its run speed within 0x20 bytes after it.
-- Memory read-only. Writes walk2_probe.txt next to Warhammer3.exe:
--   BATTLE / H <uid> <key> <which: e | mount> <entity off> <record off> <walk> <run off> / N <uid> <key> <which> <pointers scanned> / END | FAIL
local LOG_FILE = "walk2_probe.txt"
local U_ENT_N, U_ENT, PARENT = 0x184, 0x188, 0x2e0
local fmt = string.format
local function write(lines)
    local f = io.open(LOG_FILE, "a")
    if f then f:write(table.concat(lines, "\n") .. "\n"); f:close() end
end
local mr = _G.memreader_plus
if not mr then
    local chunk = loadfile("/script/_lib/mod/memreader_plus")
    if chunk then pcall(chunk) end
    mr = _G.memreader_plus
end
local function near(a, b) return a and math.abs(a - b) < 0.001 end
-- memreader raises 'failed to read memory' on an unreadable address (run walk2_probe, 2026-11-22): every read here
-- is guarded, an unreadable one is skipped
local function safe(fn, p, o) local ok, v = pcall(fn, p, o); if ok then return v end end
local function scan(lines, uid, key, which, e, walk, run)
    local scanned = 0
    for eoff = 0, 0x1000, 8 do
        local hi = safe(mr.read_int32, e, eoff + 4)
        local lo = safe(mr.read_int32, e, eoff)
        if hi and hi >= 1 and hi <= 0x7fff and lo and lo ~= 0 then
            local p = safe(mr.read_pointer, e, eoff)
            if p and not mr.is_null(p) then
                scanned = scanned + 1
                for o = 0, 0x200, 4 do
                    if near(safe(mr.read_float, p, o), walk) then
                        for d = 4, 0x20, 4 do
                            if near(safe(mr.read_float, p, o + d), run) then
                                lines[#lines + 1] = fmt("H %s %s %s %x %x %.3f %x", uid, key, which, eoff, o, walk, o + d)
                            end
                        end
                    end
                end
            end
        end
    end
    lines[#lines + 1] = fmt("N %s %s %s %d", uid, key, which, scanned)
end
local function dump()
    local lines = {}
    if not mr then write({ "FAIL memreader_plus not loaded" }); return end
    lines[#lines + 1] = "BATTLE"
    local alliances = bm:alliances()
    for a = 1, alliances:count() do
        local armies = alliances:item(a):armies()
        for j = 1, armies:count() do
            local units = armies:item(j):units()
            for k = 1, units:count() do
                local unit = units:item(k)
                local key, uid = unit:type(), tostring(unit:unique_ui_id())
                local sp = SPEEDS[key]
                local obj = mr.read_pointer(mr.ud_topointer(unit), 8)
                local n = mr.read_int32(obj, U_ENT_N)
                if sp and n > 0 and n <= 256 then
                    local e = mr.read_pointer(mr.read_pointer(obj, U_ENT), 0)
                    if not mr.is_null(e) then
                        scan(lines, uid, key, "e_body", e, sp[1], sp[2])
                        if sp[3] ~= sp[1] then scan(lines, uid, key, "e_man", e, sp[3], sp[4]) end
                        local m = mr.read_pointer(e, PARENT)
                        if not mr.is_null(m) then scan(lines, uid, key, "mount", m, sp[1], sp[2]) end
                    end
                end
            end
        end
    end
    lines[#lines + 1] = "END"
    write(lines)
end
if bm and type(bm.register_phase_change_callback) == "function" then
    bm:register_phase_change_callback("Deployed", function()
        bm:callback(function()
            local ok, err = pcall(dump)
            if not ok then write({ "FAIL dump " .. tostring(err) }) end
        end, 3000, "walk2_probe")
    end)
end
