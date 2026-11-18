-- TEST-ONLY (AIR-DIVE-BRACE-W1): why does a landed flyer stop 5-14 m into braced infantry?
-- Built on the AIR-DIVE-RELEASE-W1 repath probe. Single player only. Lines in ld_brace_probe.txt:
--   R <ms> <seq> <uid> <ent8> <ret> <+0x26c> <vx> <vz> <+0x710> <+0x104> <r9d> <xmm2> <rdx> <slot> <stack hex>
--   A <ms> <seq> <uid> <ent8> <kind> <ret> <slot> <+0x26c> <vx> <vz> <fc low32> <flag> <cur slot> <+0x104> <parent8>
--   F <ms> <seq> <refl8> <refl uid> <charger8> <charger uid> <speed> <ret> <ch +0x26c> <ch vx> <ch vz> <ch slot> <refl +0x68> <refl +0x6c hex> <refl +0xbc>
--   T <ms> <uid> <ent8> <+0x26c> <slot> <+0x27c> <vx> <vz> <+0x710> <+0x104> <x> <z> <m +0x26c> <m slot>
--       | <+0x1c8> <+0x238> <+0x23c> <goal 1e0x> <goal 1e8z> <goal 7f8x> <goal 800z> <order vt8> <order tgt8> <+0xab0> <+0x324> <+0xb4> <+0xbc> <+0x68> <+0x6c hex>
--   N <ms> <uid> n10 n6 nfront braced immov bc_sum bc_max react nearest tgt_speed_mean front_braced front_react
--   M <ms> <seq> <uid> <ent8> <ret> <+0x26c> <vx> <vz> <+0x710> <+0x104> <[r8]> <[r8+4]> <slot> <stack hex>   (melee order ctor)
--   O <ms> ... same as M, for the 0x143aed8c8 order constructor 0x143255718
--   D <ms> <uid> <hex of 0xb00 bytes of the flying entity>   (landed, first 12 s after touchdown)
--   W <ms> <slot> <uid> <ent8> <new|released|tomb|empty> <x> <z>   (round 3: slide-window table changes)
local LOG_FILE = "ld_brace_probe.txt"
local CALLBACK = "ld_brace_probe_tick"
local DUMP_BYTES = 0xb00
local DUMP_WINDOW_MS = 12000
local NEAR_R = 10.0

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
local function sub(s, i, j) return (string.sub_lua or string.sub)(s, i, j) end
local function hex(raw)
    local out = {}
    for i = #raw, 1, -1 do out[#out + 1] = string.format("%02X", raw:byte(i)) end
    return table.concat(out)
end
local function hexfwd(raw)
    local out = {}
    for i = 1, #raw do out[#out + 1] = string.format("%02X", raw:byte(i)) end
    return table.concat(out)
end
local function u32(raw, at)
    local a, b, c, d = raw:byte(at + 1, at + 4)
    return a + b * 256 + c * 65536 + d * 16777216
end
local function low8(p) return sub(mr.tostring(p), -8) end

local function install()
    if not mr then return nil, "no memreader_plus" end
    local mp = false
    pcall(function() mp = bm:is_multiplayer() and true or false end)
    if mp then return nil, "multiplayer" end
    local ok, site = pcall(require, "script/ld_brace_probe/brace_probe_site")
    if not ok or type(site) ~= "table" then return nil, "site: " .. tostring(site) end
    local h, refused = mr.patcher(site.owner)
    if not h then return nil, "patcher refused: " .. tostring(refused) end
    local api = h:sites(site.entries, function(t) record("SITE " .. tostring(t)) end)
    if not api then return nil, "sites failed" end
    for _, n in ipairs({ "bp_log", "bp_act1", "bp_act2", "bp_refl", "bp_mel", "bp_ord", "bp_gset", "bp_stag" }) do
        if not api.found(n) then return nil, n .. " not usable: " .. tostring(api.why(n)) end
    end
    local l = site.layout
    local buf = api.cave_value("bp_log", "buf")
    if buf and not mr.is_null(buf) then return buf, site end
    buf = mr.game_alloc(l.bytes)
    if not buf then return nil, "game_alloc failed" end
    local zeros = string.rep("\0", 4096)
    for off = 0, l.bytes - 1, 4096 do mr.write(buf, off, sub(zeros, 1, math.min(4096, l.bytes - off))) end
    mr.write(buf, l.magic_at, l.magic)
    local done, problem = api.install_feature(site.feature, { bp_log = { buf = buf }, bp_act1 = { buf = buf },
        bp_act2 = { buf = buf }, bp_refl = { buf = buf }, bp_mel = { buf = buf }, bp_ord = { buf = buf },
        bp_gset = { buf = buf }, bp_stag = { buf = buf } })
    if not done then return nil, "install failed: " .. tostring(problem) end
    return buf, site
end

local ok, buf, site = pcall(install)
local stamp = "?"
pcall(function() stamp = os.date("%Y-%m-%d %H:%M:%S") end)
if not ok or not buf then
    record(("BATTLE %s off: %s"):format(stamp, tostring(ok and site or buf)))
    return
end
local l = site.layout
mr.write(buf, l.count_at, mr.uint32(0))
mr.write(buf, l.act_count_at, mr.uint32(0))
mr.write(buf, l.refl_count_at, mr.uint32(0))
mr.write(buf, l.mel_count_at, mr.uint32(0))
mr.write(buf, l.ord_count_at, mr.uint32(0))
mr.write(buf, l.gset_count_at, mr.uint32(0))
mr.write(buf, l.stag_count_at, mr.uint32(0))
record(("BATTLE %s on: buffer %s"):format(stamp, mr.tostring(buf)))

-- unit / model registry, refreshed every second
local owner_of, reg_ms = {}, -1
local flyers = {}          -- { uid, e(flying entity), m(model), alliance }
local models_by_all = {}   -- alliance -> { {uid, m}, ... }
local function refresh(ms)
    if ms - reg_ms < 1000 then return end
    owner_of, flyers, models_by_all, reg_ms = {}, {}, {}, ms
    local alliances = bm:alliances()
    for a = 1, alliances:count() do
        local list = {}
        models_by_all[a] = list
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
                    for i = 0, n - 1 do
                        local m = mr.read_pointer(data, i * 8)
                        if not mr.is_null(m) then
                            owner_of[low8(m)] = uid
                            local p = mr.read_pointer(m, 0x2e0)
                            if not mr.is_null(p) then owner_of[low8(p)] = uid end
                            local e = mr.is_null(p) and m or p
                            if i < 4 and not mr.is_null(mr.read_pointer(e, 0x128)) then
                                flyers[#flyers + 1] = { uid, e, m, a }
                            end
                            list[#list + 1] = { uid, m }
                        end
                    end
                end
            end
        end
    end
end

local touch = {}   -- flyer entity low8 -> ms of first landed sample (reset when airborne again)
local function sample(ms)
    for _, f in ipairs(flyers) do
        local e, m = f[2], f[3]
        local key = low8(e)
        local x, z = mr.read_float(e, 0x88), mr.read_float(e, 0x90)
        local vx, vz = mr.read_float(e, 0xe0), mr.read_float(e, 0xe8)
        local layer = mr.read_int32(e, 0x104)
        local order_tgt = mr.read_pointer(e, 0x330 + 0x38)
        record(("T %d %s %s %d %d %d %.2f %.2f %d %d %.2f %.2f %d %d | %.2f %.2f %.2f %.2f %.2f %.2f %.2f %s %s %.2f %d %.1f %.3f %d %s"):format(
            ms, f[1], key, mr.read_int32(e, 0x26c), u32(mr.read(e, 0x278, 2) .. string.char(0, 0), 0), mr.read_int32(e, 0x27c),
            vx, vz, mr.read_int32(e, 0x710), layer, x, z, mr.read_int32(m, 0x26c),
            u32(mr.read(m, 0x278, 2) .. string.char(0, 0), 0),
            mr.read_float(e, 0x1c8), mr.read_float(e, 0x238), mr.read_float(e, 0x23c),
            mr.read_float(e, 0x1e0), mr.read_float(e, 0x1e8), mr.read_float(e, 0x7f8), mr.read_float(e, 0x800),
            low8(mr.read_pointer(e, 0x330)), mr.is_null(order_tgt) and "0" or low8(order_tgt),
            mr.read_float(e, 0xab0), mr.read_int32(e, 0x324), mr.read_float(e, 0xb4), mr.read_float(e, 0xbc),
            mr.read(e, 0x68, 1):byte(1), hex(mr.read(e, 0x6c, 4))))
        if layer ~= 0 then
            touch[key] = nil
        else
            touch[key] = touch[key] or ms
            if ms - touch[key] <= DUMP_WINDOW_MS then
                record(("D %d %s %s"):format(ms, f[1], hexfwd(mr.read(e, 0, DUMP_BYTES))))
                -- neighbours: every model of the other alliances within NEAR_R
                local sp = math.sqrt(vx * vx + vz * vz)
                local ux, uz = 0, 0
                if sp > 0.2 then ux, uz = vx / sp, vz / sp end
                local n10, n6, nfront, braced, immov, bcs, bcm, react, nearest = 0, 0, 0, 0, 0, 0, 0, 0, 999
                local tsp, fbr, frc = 0, 0, 0
                for a, list in pairs(models_by_all) do
                    if a ~= f[4] then
                        for _, mm in ipairs(list) do
                            local s = mm[2]
                            local dx, dz = mr.read_float(s, 0x88) - x, mr.read_float(s, 0x90) - z
                            local d = math.sqrt(dx * dx + dz * dz)
                            if d < NEAR_R then
                                n10 = n10 + 1
                                if d < nearest then nearest = d end
                                local b68 = mr.read(s, 0x68, 1):byte(1)
                                local f6c = u32(mr.read(s, 0x6c, 4), 0)
                                local bc = mr.read_float(s, 0xbc)
                                local rc = mr.read_int32(s, 0x324)
                                local isb = (b68 % 16 >= 8)
                                local isi = (math.floor(f6c / 65536) % 2 == 1)
                                if isb then braced = braced + 1 end
                                if isi then immov = immov + 1 end
                                bcs = bcs + bc
                                if bc > bcm then bcm = bc end
                                if rc ~= 0 then react = react + 1 end
                                local svx, svz = mr.read_float(s, 0xe0), mr.read_float(s, 0xe8)
                                tsp = tsp + math.sqrt(svx * svx + svz * svz)
                                if d < 6.0 then
                                    n6 = n6 + 1
                                    if dx * ux + dz * uz > 0 then
                                        nfront = nfront + 1
                                        if isb then fbr = fbr + 1 end
                                        if rc ~= 0 then frc = frc + 1 end
                                    end
                                end
                            end
                        end
                    end
                end
                record(("N %d %s %d %d %d %d %d %.2f %.2f %d %.2f %.2f %d %d"):format(ms, f[1], n10, n6, nfront, braced,
                    immov, bcs, bcm, react, nearest, n10 > 0 and tsp / n10 or 0, fbr, frc))
            end
        end
    end
end

local act_seen = 0
local function drain_act(ms)
    local count = u32(mr.read(buf, l.act_count_at, 4), 0)
    if count - act_seen > l.act_slots then
        record(("LOSTA %d"):format(count - act_seen - l.act_slots))
        act_seen = count - l.act_slots
    end
    while act_seen < count do
        local at = l.act_ring_at + (act_seen % l.act_slots) * l.act_entry
        local e = mr.read(buf, at, 64)
        local ent = sub(hex(sub(e, 1, 8)), -8)
        record(("A %d %d %s %s %d %s %d %d %.2f %.2f %s %d %d %d %s"):format(ms, u32(e, 16), tostring(owner_of[ent] or "?"), ent,
            u32(e, 20), hex(sub(e, 9, 16)), u32(e, 24), mr.read_int32(buf, at + 28), mr.read_float(buf, at + 32),
            mr.read_float(buf, at + 36), hex(sub(e, 41, 44)), u32(e, 44), e:byte(49) + e:byte(50) * 256, mr.read_int32(buf, at + 52),
            sub(hex(sub(e, 57, 64)), -8)))
        act_seen = act_seen + 1
    end
end

local refl_seen = 0
local function drain_refl(ms)
    local count = u32(mr.read(buf, l.refl_count_at, 4), 0)
    if count - refl_seen > l.refl_slots then
        record(("LOSTF %d"):format(count - refl_seen - l.refl_slots))
        refl_seen = count - l.refl_slots
    end
    while refl_seen < count do
        local at = l.refl_ring_at + (refl_seen % l.refl_slots) * l.refl_entry
        local e = mr.read(buf, at, 64)
        local r8 = sub(hex(sub(e, 1, 8)), -8)
        local r9 = sub(hex(sub(e, 9, 16)), -8)
        record(("F %d %d %s %s %s %s %.2f %s %d %.2f %.2f %d %d %s %.3f"):format(ms, u32(e, 16), r8, tostring(owner_of[r8] or "?"),
            r9, tostring(owner_of[r9] or "?"), mr.read_float(buf, at + 24), hex(sub(e, 29, 36)), mr.read_int32(buf, at + 36),
            mr.read_float(buf, at + 40), mr.read_float(buf, at + 44), u32(e, 48) % 65536, u32(e, 52), hex(sub(e, 57, 60)),
            mr.read_float(buf, at + 60)))
        refl_seen = refl_seen + 1
    end
end

local mel_seen = 0
local function drain_mel(ms)
    local count = u32(mr.read(buf, l.mel_count_at, 4), 0)
    if count - mel_seen > l.mel_slots then
        record(("LOSTM %d"):format(count - mel_seen - l.mel_slots))
        mel_seen = count - l.mel_slots
    end
    while mel_seen < count do
        local at = l.mel_ring_at + (mel_seen % l.mel_slots) * l.mel_entry
        local e = mr.read(buf, at, 64)
        local ent = sub(hex(sub(e, 1, 8)), -8)
        record(("M %d %d %s %s %s %d %.2f %.2f %d %d %d %d %d %s"):format(ms, u32(e, 16), tostring(owner_of[ent] or "?"),
            ent, hex(sub(e, 9, 16)), mr.read_int32(buf, at + 20), mr.read_float(buf, at + 24),
            mr.read_float(buf, at + 28), mr.read_int32(buf, at + 32), mr.read_int32(buf, at + 36),
            mr.read_int32(buf, at + 40), mr.read_int32(buf, at + 44), e:byte(57) + e:byte(58) * 256,
            hexfwd(mr.read(buf, at + 64, 384))))
        mel_seen = mel_seen + 1
    end
end

local ord_seen = 0
local function drain_ord(ms)
    local count = u32(mr.read(buf, l.ord_count_at, 4), 0)
    if count - ord_seen > l.ord_slots then
        record(("LOSTO %d"):format(count - ord_seen - l.ord_slots))
        ord_seen = count - l.ord_slots
    end
    while ord_seen < count do
        local at = l.ord_ring_at + (ord_seen % l.ord_slots) * l.ord_entry
        local e = mr.read(buf, at, 64)
        local ent = sub(hex(sub(e, 1, 8)), -8)
        record(("O %d %d %s %s %s %d %.2f %.2f %d %d %d %d %d %s"):format(ms, u32(e, 16), tostring(owner_of[ent] or "?"),
            ent, hex(sub(e, 9, 16)), mr.read_int32(buf, at + 20), mr.read_float(buf, at + 24),
            mr.read_float(buf, at + 28), mr.read_int32(buf, at + 32), mr.read_int32(buf, at + 36),
            mr.read_int32(buf, at + 40), mr.read_int32(buf, at + 44), e:byte(57) + e:byte(58) * 256,
            hexfwd(mr.read(buf, at + 64, 384))))
        ord_seen = ord_seen + 1
    end
end

-- [round 2] G = stop-at-point 0x1431341b0 (goal x z, r8), K = vfunc 0x143098b04 (+0xb28, +0xb11, +0x88 x z)
local function drain_ent(ms, tag, count_at, ring_at, slots, entry, seen_ref)
    local count = u32(mr.read(buf, count_at, 4), 0)
    if count - seen_ref[1] > slots then
        record(("LOST%s %d"):format(tag, count - seen_ref[1] - slots))
        seen_ref[1] = count - slots
    end
    while seen_ref[1] < count do
        local at = ring_at + (seen_ref[1] % slots) * entry
        local e = mr.read(buf, at, 64)
        local ent = sub(hex(sub(e, 1, 8)), -8)
        local x1, x2
        if tag == "G" then
            x1 = ("%.2f %.2f %d"):format(mr.read_float(buf, at + 40), mr.read_float(buf, at + 44), mr.read_int32(buf, at + 48))
        else
            x1 = ("%d %d %.2f %.2f"):format(mr.read_int32(buf, at + 40), mr.read_int32(buf, at + 44),
                mr.read_float(buf, at + 48), mr.read_float(buf, at + 52))
        end
        record(("%s %d %d %s %s %s %d %.2f %.2f %d %d %s %d %s"):format(tag, ms, u32(e, 16), tostring(owner_of[ent] or "?"),
            ent, hex(sub(e, 9, 16)), mr.read_int32(buf, at + 20), mr.read_float(buf, at + 24),
            mr.read_float(buf, at + 28), mr.read_int32(buf, at + 32), mr.read_int32(buf, at + 36), x1,
            e:byte(57) + e:byte(58) * 256, hexfwd(mr.read(buf, at + 64, 384))))
        seen_ref[1] = seen_ref[1] + 1
    end
end
local gset_seen, stag_seen = { 0 }, { 0 }

local seen = 0
-- [round 3] the slide-window table of the shipped caves: one W line per slot change
--   W <ms> <slot> <uid> <ent8> <new|released|tomb|empty> <x> <z>
local dive_ok, dive = pcall(require, "script/campaign/lore_disasters/lib/ld_flyer_dive")
local dbuf, wseen = nil, {}
local function drain_window(ms)
    if not dive_ok then return end
    if not dbuf then dbuf = dive.find() end
    local dl = dive.layout()
    if not dbuf or not dl or not dl.slide_at then return end
    local raw = mr.read(dbuf, dl.slide_at, dl.slide_slots * 16)
    for i = 0, dl.slide_slots - 1 do
        local e = sub(raw, i * 16 + 1, i * 16 + 16)
        if e ~= wseen[i] then
            local kraw = sub(e, 1, 8)
            local khex = hex(kraw)      -- hex() prints the little-endian qword most significant byte first
            local lo = kraw:byte(1)
            local state = "new"
            if khex == "0000000000000000" then state = "empty"
            elseif khex == "0000000000000002" then state = "tomb"
            elseif lo % 2 == 1 then state = "released" end
            local key = string.char(kraw:byte(1) - (lo % 2)) .. sub(kraw, 2, 8)
            local ent = sub(hex(key), -8)
            record(("W %d %d %s %s %s %.2f %.2f"):format(ms, i, tostring(owner_of[ent] or "?"), ent, state,
                mr.read_float(dbuf, dl.slide_at + i * 16 + 8), mr.read_float(dbuf, dl.slide_at + i * 16 + 12)))
            wseen[i] = e
        end
    end
end

local function tick()
    local ms = bm:time_elapsed_ms()
    pcall(drain_window, ms)
    local rok, rerr = pcall(refresh, ms)
    if not rok then record("RERR " .. tostring(rerr)) end
    pcall(drain_act, ms)
    pcall(drain_refl, ms)
    pcall(drain_mel, ms)
    pcall(drain_ord, ms)
    pcall(drain_ent, ms, "G", l.gset_count_at, l.gset_ring_at, l.gset_slots, l.gset_entry, gset_seen)
    pcall(drain_ent, ms, "K", l.stag_count_at, l.stag_ring_at, l.stag_slots, l.stag_entry, stag_seen)
    local sok, serr = pcall(sample, ms)
    if not sok then record("SERR " .. tostring(serr)) end
    local count = u32(mr.read(buf, l.count_at, 4), 0)
    if count - seen > l.slots then
        record(("LOST %d"):format(count - seen - l.slots))
        seen = count - l.slots
    end
    while seen < count do
        local at = l.ring_at + (seen % l.slots) * l.entry
        local e = mr.read(buf, at, 64)
        local ent = sub(hex(sub(e, 1, 8)), -8)
        record(("R %d %d %s %s %s %d %.2f %.2f %d %d %d %s %s %d %s"):format(ms, u32(e, 16), tostring(owner_of[ent] or "?"),
            ent, hex(sub(e, 9, 16)), mr.read_int32(buf, at + 20), mr.read_float(buf, at + 24),
            mr.read_float(buf, at + 28), mr.read_int32(buf, at + 32), mr.read_int32(buf, at + 36),
            mr.read_int32(buf, at + 40), hex(sub(e, 45, 48)), hex(sub(e, 49, 56)), e:byte(57) + e:byte(58) * 256,
            hexfwd(mr.read(buf, at + 64, 384))))
        seen = seen + 1
    end
end

bm:register_phase_change_callback("Deployed", function()
    mr.write(buf, l.mode_at, mr.uint32(1))
    -- [opt-in] battle speed for this run (series.py --speed=N writes the file; absent = 1x)
    local sf = io.open("ld_brace_speed.txt", "r")
    if sf then
        local n = tonumber(sf:read("*l") or "")
        sf:close()
        if n and n > 1 then
            local sok, serr = pcall(function() bm:modify_battle_speed(n, true) end)
            record(("SPEED %s %s"):format(tostring(n), sok and "set" or ("failed " .. tostring(serr))))
        end
    end
    bm:repeat_callback(function()
        local tok, err = pcall(tick)
        if not tok then
            record("STOP " .. tostring(err))
            pcall(function() bm:remove_callback(CALLBACK) end)
        end
    end, 100, CALLBACK)
end)

bm:register_phase_change_callback("Complete", function()
    pcall(function() mr.write(buf, l.mode_at, mr.uint32(0)) end)
    pcall(tick)
    pcall(function() bm:remove_callback(CALLBACK) end)
    record(("END %d"):format(seen))
end)
