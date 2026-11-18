-- ld_entity_read.lua — TEST-ONLY battle recorder: every soldier's position,
-- hit points and knock state, read from game memory.
-- 测试专用：战斗中逐兵模读位置、血量与击倒状态（只读内存，不写）。
--
-- [ENGINE-ENTITY-READ-W1 2026-11-11] User-approved (2026-11-11) for the
-- automated battle tests only. It ships ONLY in ld_entity_read.pack, built by
-- tools/pipelines/build_entity_read_minimod.py, never in ld_mod.pack, never to
-- players. It READS memory through memreader Plus (vendored, MIT) and never
-- writes game memory: no patch, no code cave, no memory write call.
--
-- WHERE THE NUMBERS COME FROM (no guessed offset):
--   * unit object = [ud_topointer(script unit) + 8]; +0xa4 live model count,
--     +0xa8 model pointer array; model +0x88/+0x8c/+0x90 position, +0xb18 max /
--     +0xb1c current hit points (a rider's on his mount, model +0x2e0), +0x278
--     current animation slot, read only when [+0x898] or [+0x284] is set.
--     Knock slots 143-197 (KNOCKBACK/KNOCKDOWN/KNOCKED_FLYING/getting up).
--     Source: Derpy's Third-Person Battles (DerpyNewb, MIT, 2026),
--     script/derpy_tp/platform.lua + combat.lua; license text ships next to
--     this file (script/ld_entity_read/LICENSE_derpy_third_person.txt).
--   * live checks (Derpy's check_men): model count == number_of_men_alive(),
--     every model's vtable inside Warhammer3.exe's image, the men's centre or
--     the nearest man within 5 m of unit:position().
--   * model +0x2e8 = back-pointer to his unit (Derpy steer; Tenzin's FPS DLL
--     logs the same field): MEASURED here (backref k/n), not trusted.
--   * model +0x324: No Knockdown Invincibility (ilhwana/Altius, Workshop
--     3820224735, no license terms; credited, withdrawn on objection) reads it
--     as an action state (14 knocked back .. 17 getting up) in the targetable
--     test (9.0.5 exe+0x3064fd8: mov ecx,[rcx+0x324], rcx = the same object
--     whose +0xb13 bit it tests); Derpy's comment says it is "not 0 on any tick
--     an order reached him". Measured in game 2026-11-12 (ENGINE-ENTITY-READ-W1
--     §C11): Altius is right -- every one of 14,756 man-samples in a knock slot
--     read 14..17, no man with a readable non-knock slot did, and it stays
--     readable when the slot read is gated. Recorded raw; the knock count is
--     made in entity_read_report.py.
--   * [AIR-DIVE-W16 2026-11-12] model +0x1c8 speed (F32, m/s) and +0xab0 the
--     collision-attack hit counter (I32): ENGINE-W1's static read of the
--     9.0.5 exe (air-dive-engine-w1_scratch/air_dive_engine.md section 1.2:
--     the collision attack needs [attacker+0x1c8] >= 1.0 and
--     [attacker+0xab0] < the weapon's collision_attack_max_targets, then
--     adds 1). Recorded raw for the man and his mount. Measured in game
--     2026-11-12 (AIR-DIVE-W16 runs cA_1 / cB_1): +0x1c8 is the speed (the
--     star dragon reads 15.0 at its charge and 20.0 in the plough clip);
--     +0xab0 is an F32, not a count -- it stays 0 on a flyer whose weapon has
--     collision_attack_max_targets 0 (stage A) and jumps the moment a flyer
--     with one lands (star dragon, 5 targets / 5 s: 4.5 at touchdown + 0.1 s,
--     down by 1.0 every 0.2 s to 0; manticore 4 / 3 s: up to 3.2, down 0.6
--     per 0.2 s): it is the collision-attack load, +1 per man hit and
--     decaying. It is read as F32.
--   * [AIR-DIVE-W16] the flight mode ENGINE-W1 found compared with 0 / 6 / 7
--     in the take-off transition (0x14304b700) is +0x710 of the MODEL, with a
--     sub-state at +0x70c (both I32): measured 2026-11-12 by dumping
--     +0x700..+0x71f of the unit object and of the first model on every tick
--     (AIR-DIVE-W16 engage runs): the unit object's +0x710 never changes
--     (0x100 on the star dragon), the model's reads 0 / 4 / 6 / 7 -- 6 only
--     while flying, 7 only while grounded, 4 from 0.2-3.6 s (sub 1 from 0.8-6.2 s) after a
--     move order given in melee, held through the take-off. Recorded as
--     f=<mode>/<sub> of
--     the first model, or of his mount when he rides one.
--   * the battle global: Altius' GLOBAL_SITE signature (Topple!, Workshop
--     3824557361, no license terms), RIP-relative disp at +3; the battle-object
--     offset (+10) and the two gate offsets (+16, +25) are read from the matched
--     code, not written here. Gate bytes must read 0/1 (Derpy's check).
--
-- FAILS LOUDLY: memreader missing, signature not found, battle object null, a
-- gate byte > 1, a unit failing its start check, a model vtable outside the
-- exe, impossible hit points, or a count mismatch / read error persisting
-- PERSIST ticks -> a "STOP <reason>" line and the recorder ends. A stopped
-- record is never a measurement (entity_read_report.py fails it).
--
-- WRITES ld_entity_read.txt next to Warhammer3.exe (appends; one BATTLE line
-- per battle):
--   BATTLE <stamp> build=<pe ts> global=<ptr> base=<ptr> hits=<n> sub=<hex> gates=<hex>,<hex> derpy_9_0_5=<agree|differ|other_build>
--   UNIT <uid> <alliance> <key> men=<initial>
--   CHECK <uid> ok n=<models> backref=<k>/<n> | CHECK <uid> FAIL <why>
--   T <ms>
--   U <uid> <men_alive> <models> <unary_hp> <sum_cur> <sum_max> f=<mode>/<sub> <models...>
--     model = id,x,z,cur,max,slot,st324,mslot,spd,hits,mspd,mhits,y,cmdvt  (id: low 8
--     hex of the model pointer; slot/mslot -1 when gated or no mount; mslot =
--     the mount's slot; spd/hits = +0x1c8 / +0xab0, mspd/mhits the mount's,
--     -1 without a mount)
--   END | STOP <why> | FAIL <why>

local LOG_FILE = "ld_entity_read.txt"
local TICK_MS = 200
local PERSIST = 5
local MAX_BYTES = 80 * 1024 * 1024
local CALLBACK_NAME = "ld_entity_read_tick"
local GLOBAL_SITE = "48 8B 05 ?? ?? ?? ?? 48 8B 88 68 04 00 00 80 B9 B0 03 00 00 00 75 ?? 80 B9 B1 03 00 00 00 75 ?? 48 8B 89 E8 44 06 00"
local DERPY_9_0_5 = { build = "6ae2a00b", battle = 0x448f208 }   -- Derpy BUILDS row, a cross-check only

local MODELS_N, MODELS_DATA, MODEL_POS = 0xa4, 0xa8, 0x88
local MODEL_HP_MAX, MODEL_HP = 0xb18, 0xb1c
local RIDER_PARENT, BACKREF, SLOT, STATE = 0x2e0, 0x2e8, 0x278, 0x324
local SPEED, HITS, FLIGHT, FLIGHT_SUB = 0x1c8, 0xab0, 0x710, 0x70c   -- [AIR-DIVE-W16] header
local CMD = 0x330   -- [AIR-DIVE-CONTINUOUS-W1] the model's current order object
-- [AIR-DIVE-CONTINUOUS-W1] TEST-ONLY raw dump (off unless the pack is built with
-- build_entity_read_minimod.py --dump): every DUMP_MS, the first DUMP_BYTES of
-- each unit's lead model entity (his mount's when he rides one) as hex, read
-- in exact 16-bit halves. Used to find which field carries the flyer's real
-- velocity and drops to 0 at touchdown (the order at +0x330 does not change,
-- §C11 AIR-DIVE-CONTINUOUS-W1). Line: D <uid> <ms> <hex, 4 digits per 2 bytes>
local DUMP_ON = false
local DUMP_MS, DUMP_BYTES, DUMP_CALLBACK = 100, 0xC00, "ld_entity_read_dump"
local dump_uids = {}

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
    end
end

local function stop(why)
    if stopped then return end
    emit("STOP " .. why)
    stopped = true
    flush()
    pcall(function() bm:remove_callback(CALLBACK_NAME) end)
    pcall(function() bm:remove_callback(DUMP_CALLBACK) end)
end

-- memreader Plus normally loads from script/_lib/mod first; load it if not
local mr = _G.memreader_plus
if not mr then
    local chunk = loadfile("/script/_lib/mod/memreader_plus")
    if chunk then pcall(chunk) end
    mr = _G.memreader_plus
end

local function u16(p, off) return mr.read_uint16(p, off) end
-- a 32-bit value in exact 16-bit halves: game Lua numbers are float32 (Derpy)
local function i32_exact(p, off)
    local lo, hi = u16(p, off), u16(p, off + 2)
    if hi >= 0x8000 then hi = hi - 0x10000 end
    return hi, lo
end
local function rva_ptr(base, p, off)
    local hi, lo = i32_exact(p, off)
    return mr.add(mr.add(base, hi * 0x10000), lo)
end

local G = {}   -- base, image_end, lo, hi, battle

local function resolve_global()
    local base = mr.base
    local pe = mr.read_int32(base, 0x3c)
    G.build = fmt("%04x%04x", u16(base, pe + 10), u16(base, pe + 8))
    G.image_end = rva_ptr(base, base, pe + 0x50)   -- SizeOfImage
    G.lo, G.hi = mr.tostring(base), mr.tostring(G.image_end)
    local at, count = mr.find_pattern(GLOBAL_SITE)
    if not at or mr.is_null(at) or not count or count < 1 then
        return nil, "GLOBAL_SITE signature not found (count " .. tostring(count) .. ")"
    end
    local hi, lo = i32_exact(at, 3)
    local global = mr.add(mr.add(mr.add(at, 7), hi * 0x10000), lo)
    local sub = mr.read_int32(at, 10)
    local gate_a, gate_b = mr.read_int32(at, 16), mr.read_int32(at, 25)
    if sub <= 0 or sub > 0x10000 or gate_a <= 0 or gate_a > 0x10000 or gate_b ~= gate_a + 1 then
        return nil, fmt("signature operands look wrong: sub=%s gates=%s,%s", sub, gate_a, gate_b)
    end
    local g = mr.read_pointer(global, 0)
    if mr.is_null(g) then return nil, "battle global is null" end
    local b = mr.read_pointer(g, sub)
    if mr.is_null(b) then return nil, "battle object is null" end
    local ga, gb = mr.read_uint8(b, gate_a), mr.read_uint8(b, gate_b)
    if ga > 1 or gb > 1 then return nil, fmt("gate bytes read %d and %d", ga, gb) end
    -- Derpy's 9.0.5 table, a cross-check only (the signature is what is used)
    G.global_s, G.base_s = mr.tostring(global), mr.tostring(base)
    G.count, G.sub, G.gate_a, G.gate_b = count, sub, gate_a, gate_b
    G.derpy = "other_build"
    if G.build == DERPY_9_0_5.build then
        local expect = mr.add(mr.add(base, 0x4480000), DERPY_9_0_5.battle - 0x4480000)
        G.derpy = mr.eq(global, expect) and "agree" or "differ"
    end
    return true
end

local function obj_of(unit) return mr.read_pointer(mr.ud_topointer(unit), 8) end

local function in_image(p)
    local s = mr.tostring(mr.read_pointer(p, 0))
    return s >= G.lo and s < G.hi
end

local function short_id(p)
    local s = mr.tostring(p)
    return (string.sub_lua or string.sub)(s, -8)   -- house rule: 9.0 native sub crashes on negative indexes (§A14.1d)
end

local function slot_of(m)
    if mr.is_null(mr.read_pointer(m, 0x898)) and mr.read_int32(m, 0x284) == 0 then return -1 end
    return mr.read_uint16(m, SLOT)
end

local function call(unit, method)
    local ok, v = pcall(function() return unit[method](unit) end)
    if ok then return v end
    return nil
end

-- every unit of every army (main units + reinforcement sets)
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

-- Derpy's check_men + the measured back-pointer
local function check_unit(unit)
    local obj = obj_of(unit)
    if mr.is_null(obj) then return false, "unit object is null" end
    local n = mr.read_int32(obj, MODELS_N)
    local alive = unit:number_of_men_alive()
    if n < 1 or n ~= alive then return false, fmt("model count %d against %d men", n, alive) end
    local data = mr.read_pointer(obj, MODELS_DATA)
    local q = unit:position()
    local qx, qz, near, sx, sz, back = q:get_x(), q:get_z(), 1e18, 0, 0, 0
    for k = 0, n - 1 do
        local m = mr.read_pointer(data, k * 8)
        if mr.is_null(m) then return false, "null model pointer " .. k end
        if not in_image(m) then return false, "a model type is not in the game's exe" end
        local x, z = mr.read_float(m, MODEL_POS), mr.read_float(m, MODEL_POS + 8)
        near = math.min(near, (x - qx) ^ 2 + (z - qz) ^ 2)
        sx, sz = sx + x, sz + z
        if mr.eq(mr.read_pointer(m, BACKREF), obj) then back = back + 1 end
        local cur, mx = mr.read_int32(m, MODEL_HP), mr.read_int32(m, MODEL_HP_MAX)
        local mount = mr.read_pointer(m, RIDER_PARENT)
        if not mr.is_null(mount) then
            cur, mx = mr.read_int32(mount, MODEL_HP), mr.read_int32(mount, MODEL_HP_MAX)
        end
        if mx <= 0 or cur < 0 or cur > mx then return false, fmt("model %d hit points %d/%d", k, cur, mx) end
    end
    local centre = (sx / n - qx) ^ 2 + (sz / n - qz) ^ 2
    if not (near <= 25 or centre <= 25) then
        return false, fmt("the men centre %d m from the unit, the nearest %d m",
            math.floor(math.sqrt(centre)), math.floor(math.sqrt(near)))
    end
    return true, n, back
end

local units = {}   -- uid -> { unit, ok, bad, err }

local function dump_tick()
    if stopped then return end
    local ms = bm:time_elapsed_ms()
    for uid, unit in pairs(dump_uids) do
        if unit:number_of_men_alive() > 0 then
            local obj = obj_of(unit)
            local m = mr.read_pointer(mr.read_pointer(obj, MODELS_DATA), 0)
            local mount = mr.read_pointer(m, RIDER_PARENT)
            if not mr.is_null(mount) then m = mount end
            local hex = {}
            for off = 0, DUMP_BYTES - 2, 2 do hex[#hex + 1] = fmt("%04x", u16(m, off)) end
            emit(fmt("D %s %d %s", tostring(uid), ms, table.concat(hex)))
        end
    end
    flush()
end

local function sample_unit(uid, rec)
    local unit = rec.unit
    local alive = unit:number_of_men_alive()
    local obj = obj_of(unit)
    local n = mr.read_int32(obj, MODELS_N)
    if alive <= 0 and n <= 0 then return "dead" end
    if n ~= alive then return "count" , fmt("model count %d against %d men", n, alive) end
    local data = mr.read_pointer(obj, MODELS_DATA)
    local parts, sum_cur, sum_max, mounts = {}, 0, 0, {}
    local mf = {}   -- [AIR-DIVE-BRACE-W1 scratch] per-model body flight +0x710, layer +0x104, state +0x26c, +0xe4
    for k = 0, n - 1 do
        local m = mr.read_pointer(data, k * 8)
        if mr.is_null(m) or not in_image(m) then return "fatal", "a model type is not in the game's exe" end
        local x, z = mr.read_float(m, MODEL_POS), mr.read_float(m, MODEL_POS + 8)
        -- [AIR-DIVE-CONTINUOUS-W1] height (+0x8c), of the mount when he rides one
        local y_of = mr.read_float(m, MODEL_POS + 4)
        local mount = mr.read_pointer(m, RIDER_PARENT)
        local hp_of, mslot, mspd, mhits = m, -1, -1, -1
        if not mr.is_null(mount) then
            hp_of, mslot = mount, slot_of(mount)
            mspd, mhits = mr.read_float(mount, SPEED), mr.read_float(mount, HITS)
            y_of = mr.read_float(mount, MODEL_POS + 4)
        end
        local cur, mx = mr.read_int32(hp_of, MODEL_HP), mr.read_int32(hp_of, MODEL_HP_MAX)
        if mx <= 0 or cur < 0 or cur > mx then return "fatal", fmt("model hit points %d/%d", cur, mx) end
        local key = mr.tostring(hp_of)
        if not mounts[key] then
            mounts[key] = true
            sum_cur, sum_max = sum_cur + cur, sum_max + mx
        end
        -- [AIR-DIVE-CONTINUOUS-W1] the current order's vtable: +0x330 is the
        -- order object the engine's own collision-attack test reads
        -- (air-dive-engine-w1 static notes "当前命令 [+0x330] 攻击/冲锋类
        -- (虚表 +0x60 / +0x70)"), held inline, so the qword there IS its vtable
        -- (measured: one more dereference gives a scalar-deleting destructor
        -- shared by five vtables); the mount's when he rides one
        local cmd_of = mr.is_null(mount) and m or mount
        local vt = mr.tostring(mr.read_pointer(cmd_of, CMD))
        local body = mr.is_null(mount) and m or mount
        mf[#mf + 1] = fmt("%s,%d,%d,%d,%.2f,%.2f", short_id(m), mr.read_int32(body, FLIGHT),
            mr.read_int32(body, 0x104), mr.read_int32(body, 0x26c), mr.read_float(body, 0xe4), y_of)
        parts[#parts + 1] = fmt("%s,%.1f,%.1f,%d,%d,%d,%d,%d,%.2f,%.2f,%.2f,%.2f,%.2f,%s", short_id(m), x, z,
            cur, mx, slot_of(m), mr.read_int32(m, STATE), mslot,
            mr.read_float(m, SPEED), mr.read_float(m, HITS), mspd, mhits, y_of, vt)
    end
    local unary = call(unit, "unary_hitpoints") or -1
    local lead = mr.read_pointer(data, 0)
    local lead_mount = mr.read_pointer(lead, RIDER_PARENT)
    if not mr.is_null(lead_mount) then lead = lead_mount end
    emit(fmt("U %s %d %d %.4f %d %d f=%d/%d %s", tostring(uid), alive, n, unary, sum_cur, sum_max,
        mr.read_int32(lead, FLIGHT), mr.read_int32(lead, FLIGHT_SUB), table.concat(parts, " ")))
    if n > 1 then emit(fmt("MF %s %s", tostring(uid), table.concat(mf, " "))) end
    return "ok"
end

local function tick()
    if stopped then return end
    emit(fmt("T %d", bm:time_elapsed_ms()))
    for uid, rec in pairs(units) do
        local ok, kind, why = pcall(sample_unit, uid, rec)
        if not ok then kind, why = "read", tostring(kind) end
        if kind == "ok" or kind == "dead" then
            rec.bad = 0
        elseif kind == "fatal" then
            stop(fmt("unit %s: %s", tostring(uid), why))
            return
        else
            rec.bad = rec.bad + 1
            if rec.bad >= PERSIST then
                stop(fmt("unit %s: %s for %d ticks", tostring(uid), why, rec.bad))
                return
            end
        end
    end
    flush()
end

local function start()
    if not mr then
        emit("FAIL memreader_plus not loaded: " .. tostring(_G.memreader_plus_load_error))
        stopped = true
        flush()
        return
    end
    local stamp = "?"
    pcall(function() stamp = os.date("%Y-%m-%d %H:%M:%S") end)
    local ok, res, why = pcall(resolve_global)
    if not ok or not res then
        emit("BATTLE " .. stamp)
        emit("FAIL " .. tostring(ok and why or res))
        stopped = true
        flush()
        return
    end
    emit(fmt("BATTLE %s build=%s global=%s base=%s hits=%s sub=0x%x gates=0x%x,0x%x derpy_9_0_5=%s tick_ms=%d",
        stamp, G.build, G.global_s, G.base_s, tostring(G.count),
        G.sub, G.gate_a, G.gate_b, G.derpy, TICK_MS))
    local failed = nil
    each_unit(function(alliance, unit)
        if failed then return end
        local uid = call(unit, "unique_ui_id")
        if uid == nil then return end
        emit(fmt("UNIT %s %d %s men=%d", tostring(uid), alliance, tostring(call(unit, "type")),
            call(unit, "initial_number_of_men") or -1))
        if (call(unit, "number_of_men_alive") or 0) <= 0 then return end
        local cok, good, n, back = pcall(check_unit, unit)
        if not cok then
            failed = fmt("unit %s check threw: %s", tostring(uid), tostring(good))
        elseif not good then
            failed = fmt("unit %s check: %s", tostring(uid), tostring(n))
        else
            emit(fmt("CHECK %s ok n=%d backref=%d/%d", tostring(uid), n, back, n))
            units[uid] = { unit = unit, bad = 0 }
            -- the lead model of every unit: a ground cavalry charge's goal is read off its
            -- lead horse to compare with a landed flyer's (§C8-53, mirror vanilla)
            if DUMP_ON and n >= 1 then dump_uids[uid] = unit end
        end
    end)
    if failed then
        stop(failed)
        return
    end
    flush()
    bm:repeat_callback(function()
        local tok, err = pcall(tick)
        if not tok then stop("ERROR " .. tostring(err)) end
    end, TICK_MS, CALLBACK_NAME)
    if DUMP_ON then
        emit(fmt("DUMP ms=%d bytes=0x%x", DUMP_MS, DUMP_BYTES))
        bm:repeat_callback(function()
            local tok, err = pcall(dump_tick)
            if not tok then stop("ERROR dump " .. tostring(err)) end
        end, DUMP_MS, DUMP_CALLBACK)
    end
end

if bm and type(bm.register_phase_change_callback) == "function" then
    bm:register_phase_change_callback("Deployed", function()
        local ok, err = pcall(start)
        if not ok then stop("ERROR start " .. tostring(err)) end
    end)
    bm:register_phase_change_callback("Complete", function()
        pcall(function() bm:remove_callback(CALLBACK_NAME) end)
        pcall(function() bm:remove_callback(DUMP_CALLBACK) end)
        emit("END")
        flush()
    end)
else
    local f = io.open(LOG_FILE, "a")
    if f then f:write("FAIL bm unavailable at chunk scope\n"); f:close() end
end
