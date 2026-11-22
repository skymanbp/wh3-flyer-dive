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
--   sample <ms>      default 200; the sampling period (100 = one battle tick)
--   entities <0|1>   default 0; 1 = also write the E lines
--   track <0|1>      default 0; 1 = also write the Q / P / C / M lines [regroup-1119, D23]: where every
--                    model of a flyer unit is, tick by tick (see below). Meant with "sample 100".
--   calls <0|1>      default 0; 1 = also write the G / GC lines [regroup-1119, D23]: who lands a flying model and
--                    who flips its unit's stay-down flag. Needs the pack built with build_pin_on_hit_probe.py
--                    --regroup-trace (the site table script/regroup_trace/regroup_trace_site); without it a FAIL
--                    line is written and the record goes on without the G lines.
--   regroup <0|1>    default 1 [D23, REGROUP-FIX-1120]; 0 = the take-off caves' regroup part only counts what it
--                    would skip and lets the engine's charge run (the one-pack A/B; the shipped scripts never
--                    turn it off). Its counters go into the S lines (rg_*).
--   trace <0|1>      default 0; 1 = also write the T lines [d10-1118]. Needs the traced caves
--                    (a pack built with build_pin_on_hit_probe.py --trace-from); with the shipped
--                    caves it writes a FAIL line and records without the trace.
-- WRITES pin_probe.txt next to Warhammer3.exe:
--   BATTLE <stamp> window=<n> mode=<m> table=<entries> sample=<ms> entities=<0|1>[ trace=1]
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
--   E <ms> <tick> <uid> <id>:<fly>:<phase>:<count> ...
--                                 [INGAME-1118] with "entities 1": every living
--                                 flight entity of one flyer, when a <fly> or a
--                                 <phase> of that unit changed. fly = entity
--                                 +0x104 (2 = airborne), phase = its flight
--                                 controller's +0x90 (1 -> 2 when asked to take
--                                 off, 3 once airborne), count = the
--                                 controller's +0x44 (the engine's own countdown
--                                 before lift-off); "-" for the last two when
--                                 the entity has no controller (+0x128 null).
--                                 Offsets: this project's own static read and
--                                 measurement, AIR-DIVE-TAKEOFF-W1 2026-11-12
--                                 (docs/HISTORY.md; the take-off sequence is
--                                 written out in takeoff_gate_report.py).
--   Z <ms> <uid> <id>:<size> ...  with "entities 1", once per flyer: each living
--                                 flight entity's body size code (entity +0x74:
--                                 1 small .. 4 very large, the field the hold
--                                 cave reads; pin_cave_asm.py SIZE_OFF)
--   Q <ms> <tick> <uid> <x> <z> <y> mv=<0|1> melee=<0|1> fly=<0|1> men=<n>   [regroup-1119] with "track 1":
--                                 every unit (flyer or not): the script's own position and flags, each sample
--   P <ms> <tick> <uid> <id>:<x>:<z>:<y> ...   [regroup-1119] with "track 1": the position of every living
--                                 flight entity of one flyer unit, each sample (entity +0x88 / +0x90 / +0x8c,
--                                 the model position of the toughness-blast entity reader; same objects as
--                                 the flight list if the mean of P agrees with Q: checked by the report)
--   C <ms> <tick> <uid> <hex32> ...  [regroup-1119] with "track 1": the unit's flight controller
--                                 ([unit +0x3e30]) as 16 int32, bytes +8 .. +0x47, when any changed
--   M <ms> <tick> <uid> <id>:<s324>:<c330>:<vt> ...  [regroup-1119] with "track 1": per flight entity the
--                                 model state +0x324, the pointer at +0x330 and the first 8 bytes behind it
--                                 (low 8 hex digits each; "-" = null or unreadable), when any changed
--   G <ms> <tick> <kind> <uid> <entity8> <ret16> <rdx16> <aux16> <air8> <state8> <stay8> <rcx8>  [regroup-1119] with
--                                 "calls 1": one call of a traced engine function (regroup_trace_asm.py): kind 1 =
--                                 landing request 0x14303fab4, 2 = landing cancel 0x14304cea0 at stage 4 / 5,
--                                 3 = a command's target changed 0x143084b10, 4 = the order stay down / fly
--                                 0x1430439c0, 5 = the charge command given to a model 0x143076060 (aux = the stack qword at [rsp+16], rdx = [rsp+8]), 6 = the virtual method 0x143123514 that calls it (ret = the unit-level caller, aux = the qword after it). ret = the return address (the caller), aux = stage / old target /
--                                 r8b, air = entity +0x104, state = entity +0x324, stay = the unit controller's +8
--                                 (ffffffff: none). All hex, from bytes (game Lua numbers are float32).
--                                 [D23-RUNS-1120] kind 7 / 8 = the per-model task handler 0x142f7f600 / 0x142f8ff54
--                                 just before it gives the charge command (rcx8 = the task, ret = the handler's
--                                 caller, rdx = [task+0x10], aux = [task] the vtable), with the extra tokens
--                                   t18= t58= t68= (qwords [task+0x18/0x58/0x68]) f74= f80= t84= sn= (u32
--                                   [task+0x74/0x80/0x84/0x8]; t84 is the f32 due time's bits);
--                                 kind 9 = the task's creator 0x143077c68 (ret = who creates it, rdx = the
--                                 parameters, aux = their +0x18 target), with p00= .. p30= (their seven qwords).
--   GC <ms> land=<n> cancel=<n> target=<n> stay=<n> order=<n> stub=<n> task1=<n> task2=<n> mktask=<n> lost=<n>
--                                 [regroup-1119] every 2 s with "calls 1": every call of the traced functions so far
--                                 (the ring only holds the filtered ones)
--   O <ms> <tick> <uid> n=<count> head=<i> vt=<hex16|-> sn=<hex8|-> a3c=<hex8|-> busy=<hex2> idle=<0|1|?>
--                                 [D23-RUNS-1120] with "track 1", right after each Q line: the unit's order queue
--                                 (this project's static read of Warhammer3.exe 9.0.5, D23-RUNS-1120): a ring of 40
--                                 orders, count at unit +0x2f88, head at +0x2f8c, the order being carried out at
--                                 unit +0x2a0 + head * 0x120 (0x14303b470 / 0x14303c75c); vt = its vtable (the
--                                 order's class), sn = its u32 serial (+8, the battle's counter +0x440 -> +0x9c),
--                                 a3c = its u32 +0x3c (set from the order push's second argument, meaning not read);
--                                 "-" when count is 0 or count / head are out of range. busy = unit +0x3ca8 (the
--                                 script's is_idle 0x14303b4b0 = count 0 and this byte 0); idle = unit:is_idle()
--                                 from the script, so the report can check the offsets against the game
--   T <tick> <uid> <id>:<token>,<token>,... ...
--                                 [d10-1118] with "trace 1": what the take-off
--                                 caves saw of each flight entity in one battle
--                                 tick, in the order it happened (tools/pipelines/
--                                 takeoff_trace_asm.py). Tokens <kind><phase>.<count>
--                                 with phase = FC +0x90 and count = FC +0x44 at
--                                 that moment:
--                                   u  the flight update 0x143053bd4 ran (state
--                                      before its state machine); suffix s = FC +8
--                                      ("stay down") set, g = FC +0x64 set
--                                   f / h  the take-off check was asked and the
--                                      rule answered free / held; suffix !u = no
--                                      living entity carries this FC, !n = no
--                                      model / unit / tick to judge by
--                                   p  the check was asked and passed to the game's
--                                      own check (mode 2)
--                                   x  a melee hit was recorded on this entity; suffix r =
--                                      the stamp cave raised its countdown 0 -> 1 (D11: a
--                                      model in phase 1 or 2 hit at countdown 0 must reach
--                                      the take-off check before it can lift); the token
--                                      shows the countdown from BEFORE the raise
--                                 id = the entity's id as in E lines ("?" + the FC's
--                                 id when no living flight entity carries it; uid "?"
--                                 then); a tick that cannot be read is -1
--   S <ms> <tick> stamps=<n> dropped=<n> held=<n> free=<n> unsized=<n> unmatched=<n>
--     used=<entries> stray=<n>[ rg_off=<0|1> rg_calls=<n> rg_skipped=<n> rg_would=<n> rg_queued=<n>
--     rg_unheld=<n>][ u_held=<n> u_stamps=<n> u_dropped=<n> u_ticks=<n> (D39)][ repick=<n> (D44)][ chargewait=<n> (D46)][ trace=<entries> trace_lost=<n>]
--                                 rg_*: [D23] the regroup caves' counters (pin_cave_asm.py), when the
--                                 take-off caves carry them
--                                 every 2 s; stray = entries that never were
--                                 in a flyer's list
--   END | FAIL <why>
-- id = the low 8 hex digits of a pointer.

local LOG_FILE, CFG_FILE = "pin_probe.txt", "pin_probe.cfg"
local CALLBACK_NAME = "pin_on_hit_probe_tick"
local SAMPLE_MS, SUMMARY_MS = 200, 2000
local U_ENT_N, U_ENT, U_CTL = 0x184, 0x188, 0x3e30
local E_FLY, E_FC, FC_COUNT, FC_PHASE, E_SIZE = 0x104, 0x128, 0x44, 0x90, 0x74
local E_POS, E_STATE, E_CMD, CTL_FROM, CTL_INTS = 0x88, 0x324, 0x330, 8, 16     -- [regroup-1119]
local U_ORD_N, U_ORD_HEAD, U_ORD_AT, ORD_SIZE, ORD_SLOTS, U_BUSY = 0x2f88, 0x2f8c, 0x2a0, 0x120, 40, 0x3ca8  -- [D23-RUNS-1120]
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
    local cfg = { window = 0, mode = 1, sample = SAMPLE_MS, entities = 0, trace = 0, track = 0, calls = 0,
        regroup = 1 }
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
local all_units = {}              -- {uid, unit} of every unit [regroup-1119]
local flyers = {}                 -- {uid, unit, obj, list = "id id ..", n, alive, struck}
local ever, seen = {}, {}         -- ids that were in a flyer's list; id -> "tick:hits" last written
local last_summary = -SUMMARY_MS
local with_tracks = false          -- cfg "track 1": the Q / P / C / M lines [regroup-1119]
local with_entities = false       -- cfg "entities 1": the E lines
local trace = nil                 -- cfg "trace 1" with traced caves: {seen, lost}

local function u32le(s, at)       -- 4 bytes at 1-based `at`; exact below 2^24 (game Lua numbers are float32)
    local a, b, c, d = s:byte(at, at + 3)
    return a + b * 256 + c * 65536 + d * 16777216
end
local function all_ff(s, at) return s:byte(at) == 255 and s:byte(at + 1) == 255 and s:byte(at + 2) == 255
    and s:byte(at + 3) == 255 end
local function low8(s, at)        -- the low 8 hex digits of the u64 at `at`
    local a, b, c, d = s:byte(at, at + 3)
    return fmt("%02X%02X%02X%02X", d, c, b, a)
end
local TRACE_LETTER = { "u", "f", "h", "p", "x", "x" }   -- 6 = a hit whose countdown was raised

-- [d10-1118] the trace entries written since the last sample, as T lines grouped by tick and unit
local function drain_trace(owner_of_fc, owner_of_entity)
    local count = u32le(mr.read(buffer, layout.trace_count_at, 4), 1)
    if count - trace.seen > layout.trace_slots then
        trace.lost = trace.lost + (count - trace.seen - layout.trace_slots)
        trace.seen = count - layout.trace_slots
    end
    local ticks, order = {}, {}
    while trace.seen < count do
        local slot = trace.seen % layout.trace_slots
        local n = math.min(count - trace.seen, layout.trace_slots - slot, 128)
        local chunk = mr.read(buffer, layout.trace_ring_at + slot * layout.trace_entry, n * layout.trace_entry)
        local stop = false
        for i = 0, n - 1 do
            local at = i * layout.trace_entry + 1
            if u32le(chunk, at + 28) ~= trace.seen + 1 then stop = true; break end   -- not written yet
            local kind = u32le(chunk, at + 20)
            local key = low8(chunk, at)
            local owner = ((kind == 5 or kind == 6) and owner_of_entity or owner_of_fc)[key]
            local id, uid = owner and owner[1] or ("?" .. key), owner and owner[2] or "?"
            local tick = all_ff(chunk, at + 8) and -1 or u32le(chunk, at + 8)
            local tok = fmt("%s%d.%d", TRACE_LETTER[kind] or ("k" .. kind), u32le(chunk, at + 16), u32le(chunk, at + 12))
            if kind == 1 then
                local extra = u32le(chunk, at + 24)
                if extra >= 256 then tok = tok .. "s" end
                if extra % 256 ~= 0 then tok = tok .. "g" end
            elseif kind == 6 then
                tok = tok .. "r"
            elseif kind == 2 or kind == 3 then
                if all_ff(chunk, at + 24) then tok = tok .. "!n"
                elseif chunk:byte(at + 24) == 254 and chunk:byte(at + 25) == 255 and chunk:byte(at + 26) == 255
                    and chunk:byte(at + 27) == 255 then tok = tok .. "!u" end
            end
            local per_tick = ticks[tick]
            if not per_tick then per_tick = {}; ticks[tick] = per_tick; order[#order + 1] = tick end
            local per_unit = per_tick[uid]
            if not per_unit then per_unit = { ids = {}, toks = {} }; per_tick[uid] = per_unit end
            if not per_unit.toks[id] then per_unit.ids[#per_unit.ids + 1] = id; per_unit.toks[id] = {} end
            local list = per_unit.toks[id]
            list[#list + 1] = tok
            trace.seen = trace.seen + 1
        end
        if stop then break end
    end
    table.sort(order)
    for _, tick in ipairs(order) do
        local uids = {}
        for uid in pairs(ticks[tick]) do uids[#uids + 1] = uid end
        table.sort(uids)
        for _, uid in ipairs(uids) do
            local per_unit, cells = ticks[tick][uid], {}
            for _, id in ipairs(per_unit.ids) do cells[#cells + 1] = id .. ":" .. table.concat(per_unit.toks[id], ",") end
            emit(fmt("T %d %s %s", tick, uid, table.concat(cells, " ")))
        end
    end
end

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

-- [regroup-1119] the call tracer: four logger caves on the landing request / landing cancel / set-target / stay-down
-- order (regroup_trace_asm.py), installed here when cfg "calls 1".
local calls = nil                 -- {buf, layout, seen, lost}
local function hex_bytes(s, at, n)    -- n bytes at 1-based `at`, little-endian -> hex text, most significant first
    local out = {}
    for i = at + n - 1, at, -1 do out[#out + 1] = fmt("%02x", s:byte(i)) end
    return table.concat(out)
end
local function install_calls()
    local ok, s = pcall(require, "script/regroup_trace/regroup_trace_site")
    if not ok or type(s) ~= "table" then return nil, "the call tracer's site table is not in the pack: " .. tostring(s) end
    local mp = false
    pcall(function() mp = bm:is_multiplayer() and true or false end)
    if mp then return nil, "multiplayer" end
    local h, refused = mr.patcher(s.owner)
    if not h then return nil, "patcher refused: " .. tostring(refused) end
    local api = h:sites(s.entries, function(txt) emit("SITE " .. tostring(txt)) end)
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
    mr.write(b, s.layout.mode_at, mr.uint32(1))
    return { buf = b, l = s.layout, seen = 0, lost = 0, last = "" }
end

local function drain_calls(ms, uid_of)
    local c, l = calls, calls.l
    local count = u32le(mr.read(c.buf, l.count_at, 4), 1)
    if count - c.seen > l.slots then
        c.lost = c.lost + (count - c.seen - l.slots)
        c.seen = count - l.slots
    end
    while c.seen < count do
        local slot = c.seen % l.slots
        local n = math.min(count - c.seen, l.slots - slot, 128)
        local chunk = mr.read(c.buf, l.ring_at + slot * l.entry, n * l.entry)
        local stop = false
        for i = 0, n - 1 do
            local at = i * l.entry + 1
            if u32le(chunk, at + 60) ~= c.seen + 1 then stop = true; break end    -- claimed, not written yet
            local ent8 = string.upper(hex_bytes(chunk, at + 8, 4))
            local kind = u32le(chunk, at + 28)
            local extra = ""
            if kind == 7 or kind == 8 or kind == 15 or kind == 16 or kind == 17 then   -- the task's fields (+64;
                                                    -- 15 / 16 [D46]: the task's start / update entries)
                extra = fmt(" t18=%s t58=%s t68=%s f74=%s f80=%s t84=%s sn=%s", hex_bytes(chunk, at + 64, 8),
                    hex_bytes(chunk, at + 72, 8), hex_bytes(chunk, at + 80, 8), hex_bytes(chunk, at + 88, 4),
                    hex_bytes(chunk, at + 92, 4), hex_bytes(chunk, at + 96, 4), hex_bytes(chunk, at + 100, 4))
                if kind == 17 then                  -- [D46] rt_tdone: the move's +0x30, the model's +0x710
                    extra = extra .. fmt(" m30=%s m710=%s", hex_bytes(chunk, at + 104, 4), hex_bytes(chunk, at + 108, 4))
                end
            elseif kind == 10 then                  -- [D42] rt_pop: the clear-queue loop's caller (0 = not from it)
                extra = " c2=" .. hex_bytes(chunk, at + 64, 8) .. " c3=" .. hex_bytes(chunk, at + 72, 8)   -- [CRAWL-1122] one level up
            elseif kind == 14 then                  -- [D45] rt_pursue: state, target unit, own model count, answer
                extra = fmt(" st=%s tgt=%s own=%d yes=%d", hex_bytes(chunk, at + 64, 8), hex_bytes(chunk, at + 72, 8),
                    u32le(chunk, at + 80), u32le(chunk, at + 84))
            elseif kind == 9 then                   -- the new task's parameters
                local p = {}
                for i = 0, 6 do p[#p + 1] = fmt("p%02x=%s", 8 * i, hex_bytes(chunk, at + 64 + 8 * i, 8)) end
                extra = " " .. table.concat(p, " ")
            end
            emit(fmt("G %d %s %d %s %s %s %s %s %s %s %s %s", ms, all_ff(chunk, at + 24) and "-1" or tostring(u32le(chunk, at + 24)),
                kind, tostring(uid_of[ent8] or "?"), ent8, hex_bytes(chunk, at + 16, 8),
                hex_bytes(chunk, at + 32, 8), hex_bytes(chunk, at + 40, 8), hex_bytes(chunk, at + 48, 4),
                hex_bytes(chunk, at + 52, 4), hex_bytes(chunk, at + 56, 4), hex_bytes(chunk, at, 4)) .. extra)
            c.seen = c.seen + 1
        end
        if stop then break end
    end
    local raw = mr.read(c.buf, l.calls_at, 68)
    local line = fmt("land=%d cancel=%d target=%d stay=%d order=%d stub=%d task1=%d task2=%d mktask=%d pop=%d done=%d pick=%d flyq=%d pursue=%d tstart=%d tupd=%d tdone=%d lost=%d",
        u32le(raw, 1), u32le(raw, 5), u32le(raw, 9), u32le(raw, 13), u32le(raw, 17), u32le(raw, 21), u32le(raw, 25),
        u32le(raw, 29), u32le(raw, 33), u32le(raw, 37), u32le(raw, 41), u32le(raw, 45), u32le(raw, 49), u32le(raw, 53), u32le(raw, 57), u32le(raw, 61), u32le(raw, 65), c.lost)
    if line ~= c.last then
        c.last = line
        emit(fmt("GC %d %s", ms, line))
    end
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

-- [regroup-1119] the Q / P / C / M lines (cfg "track 1"). Only reads.
local function sample_tracks(ms, now)
    local qs = {}
    for _, u in ipairs(all_units) do
        local ok, line = pcall(function()
            local p = u.unit:position()
            return fmt("Q %d %d %s %.1f %.1f %.1f mv=%d melee=%d fly=%d men=%d", ms, now, tostring(u.uid),
                p:get_x(), p:get_z(), p:get_y(), u.unit:is_moving() and 1 or 0, u.unit:is_in_melee() and 1 or 0,
                u.unit:is_currently_flying() and 1 or 0, u.unit:number_of_men_alive())
        end)
        emit(ok and line or fmt("Q %d %d %s FAIL %s", ms, now, tostring(u.uid), tostring(line)))
        -- [D23-RUNS-1120] the unit's order queue (see O in the header); counts and indexes are small integers
        local n, head = mr.read_int32(u.obj, U_ORD_N), mr.read_int32(u.obj, U_ORD_HEAD)
        local vt, sn, a3c = "-", "-", "-"
        if n >= 1 and n <= ORD_SLOTS and head >= 0 and head < ORD_SLOTS then
            local raw = mr.read(u.obj, U_ORD_AT + head * ORD_SIZE, 0x40)
            vt, sn, a3c = hex_bytes(raw, 1, 8), hex_bytes(raw, 9, 4), hex_bytes(raw, 0x3d, 4)
        end
        local idle = "?"
        pcall(function() idle = u.unit:is_idle() and "1" or "0" end)
        emit(fmt("O %d %d %s n=%d head=%d vt=%s sn=%s a3c=%s busy=%s idle=%s", ms, now, tostring(u.uid), n, head, vt,
            sn, a3c, hex_bytes(mr.read(u.obj, U_BUSY, 1), 1, 1), idle))
    end
    for _, f in ipairs(flyers) do
        local cells, mcells, mkey = {}, {}, {}
        for i, e in ipairs(f.ents) do
            cells[i] = fmt("%s:%.1f:%.1f:%.1f", f.ids[i], mr.read_float(e, E_POS), mr.read_float(e, E_POS + 8),
                mr.read_float(e, E_POS + 4))
            local cmd, vt = "-", "-"
            local okp, ptr = pcall(mr.read_pointer, e, E_CMD)
            if okp and not mr.is_null(ptr) then
                cmd = id_of(ptr)
                local okv, v = pcall(mr.read_pointer, ptr, 0)
                if okv and not mr.is_null(v) then vt = id_of(v) end
            end
            local cell = fmt("%s:%d:%s:%s", f.ids[i], mr.read_int32(e, E_STATE), cmd, vt)
            mcells[i] = cell
            mkey[i] = fmt("%s:%d:%s", f.ids[i], mr.read_int32(e, E_STATE), vt)
        end
        emit(fmt("P %d %d %s %s", ms, now, tostring(f.uid), table.concat(cells, " ")))
        local msig = table.concat(mkey, " ")
        if msig ~= f.msig then
            f.msig = msig
            emit(fmt("M %d %d %s %s", ms, now, tostring(f.uid), table.concat(mcells, " ")))
        end
        local ctl = mr.read_pointer(f.obj, U_CTL)
        if not mr.is_null(ctl) then
            local ints, raw = {}, mr.read(ctl, CTL_FROM, 4 * CTL_INTS)     -- bytes, not numbers: float32 Lua
            for k = 0, CTL_INTS - 1 do
                local a, b, c, d = raw:byte(4 * k + 1, 4 * k + 4)
                ints[#ints + 1] = fmt("%02x%02x%02x%02x", d, c, b, a)
            end
            local csig = table.concat(ints, " ")
            if csig ~= f.csig then
                f.csig = csig
                emit(fmt("C %d %d %s %s", ms, now, tostring(f.uid), csig))
            end
        end
    end
end

local function sample()
    local ms = bm:time_elapsed_ms()
    -- the living flight entities of every flyer
    for _, f in ipairs(flyers) do
        local n = mr.read_int32(f.obj, U_ENT_N)
        local ids, ents = {}, {}
        f.first = nil
        if n > 0 and n <= 256 then
            local data = mr.read_pointer(f.obj, U_ENT)
            for i = 0, n - 1 do
                local e = mr.read_pointer(data, i * 8)
                if not mr.is_null(e) then
                    f.first = f.first or e
                    ids[#ids + 1] = id_of(e)
                    ents[#ents + 1] = e
                    ever[ids[#ids]] = true
                end
            end
        end
        local list = table.concat(ids, " ")
        if list ~= f.list then
            f.list, f.ids = list, ids
            emit(fmt("L %d %s %d %s", ms, tostring(f.uid), #ids, list))
        end
        f.ents = ents
    end
    local now = tick_now()
    if with_entities then
        for _, f in ipairs(flyers) do
            if not f.sized and #f.ents > 0 then
                f.sized = true
                local sizes = {}
                for i, e in ipairs(f.ents) do sizes[i] = fmt("%s:%d", f.ids[i], mr.read_int32(e, E_SIZE)) end
                emit(fmt("Z %d %s %s", ms, tostring(f.uid), table.concat(sizes, " ")))
            end
            local cells, key = {}, {}
            for i, e in ipairs(f.ents) do
                local fly, fc = mr.read_int32(e, E_FLY), mr.read_pointer(e, E_FC)
                if mr.is_null(fc) then
                    cells[i] = fmt("%s:%d:-:-", f.ids[i], fly)
                    key[i] = fmt("%s:%d:-", f.ids[i], fly)
                else
                    local phase = mr.read_int32(fc, FC_PHASE)
                    cells[i] = fmt("%s:%d:%d:%d", f.ids[i], fly, phase, mr.read_int32(fc, FC_COUNT))
                    key[i] = fmt("%s:%d:%d", f.ids[i], fly, phase)
                end
            end
            local sig = table.concat(key, " ")
            if sig ~= f.esig then
                f.esig = sig
                emit(fmt("E %d %d %s %s", ms, now, tostring(f.uid), table.concat(cells, " ")))
            end
        end
    end
    if with_tracks then sample_tracks(ms, now) end
    if calls then
        local uid_of = {}
        for _, f in ipairs(flyers) do
            for i = 1, #(f.ids or {}) do uid_of[f.ids[i]] = f.uid end
        end
        drain_calls(ms, uid_of)
    end
    if trace then
        local by_fc, by_entity = {}, {}
        for _, f in ipairs(flyers) do
            for i, e in ipairs(f.ents) do
                local owner = { f.ids[i], tostring(f.uid) }
                by_entity[f.ids[i]] = owner
                local fc = mr.read_pointer(e, E_FC)
                if not mr.is_null(fc) then by_fc[id_of(fc)] = owner end
            end
        end
        drain_trace(by_fc, by_entity)
    end
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
            ms, now, c.stamps, c.dropped, c.held, c.free, c.unsized, c.unmatched, used, stray)
            .. (c.regroup and fmt(" rg_off=%d rg_calls=%d rg_skipped=%d rg_would=%d rg_queued=%d rg_unheld=%d",
                c.regroup.off, c.regroup.calls, c.regroup.skipped, c.regroup.would, c.regroup.queued,
                c.regroup.unheld) or "")
            .. (c.unit and fmt(" u_held=%d u_stamps=%d u_dropped=%d u_ticks=%d", c.unit.held, c.unit.stamps,
                c.unit.dropped, c.unit.ticks) or "")
            .. (c.repick and fmt(" repick=%d", c.repick) or "")
            .. (c.keep and fmt(" keep=%d", c.keep) or "")   -- [D67]
            .. (c.chargewait and fmt(" chargewait=%d", c.chargewait) or "")
            .. (trace and fmt(" trace=%d trace_lost=%d", trace.seen, trace.lost) or ""))
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
    takeoff.arm(buffer, windows, cfg.mode, cfg.regroup == 0)
    with_entities = cfg.entities == 1
    with_tracks = cfg.track == 1
    if cfg.calls == 1 then
        local c, why = install_calls()
        if c then
            calls = c
            emit("CALLS on: caves installed")
        else
            emit("FAIL calls 1 asked, but " .. tostring(why))
        end
    end
    emit(fmt("BATTLE %s window=%d mode=%d table=%d sample=%d entities=%d", stamp, cfg.window, cfg.mode,
        layout.table_slots, cfg.sample, cfg.entities) .. (cfg.trace == 1 and " trace=1" or "")
        .. (cfg.track == 1 and " track=1" or "") .. (cfg.calls == 1 and " calls=1" or "")
        .. (cfg.regroup == 0 and " regroup=0" or ""))
    if cfg.trace == 1 then
        if not layout.trace_ring_at then
            emit("FAIL trace 1 asked, but the take-off caves in the game carry no trace "
                .. "(deploy the pack built with build_pin_on_hit_probe.py --trace-from)")
        else
            -- off; ring and counter to 0, so an entry of an earlier battle in this session can never pass
            -- the seq test of a slot claimed but not yet written; then on
            mr.write(buffer, layout.trace_on_at, mr.uint32(0))
            local zeros, span = string.rep("\0", 4096), layout.trace_slots * layout.trace_entry
            for off = 0, span - 1, 4096 do
                mr.write(buffer, layout.trace_ring_at + off, sub(zeros, 1, math.min(4096, span - off)))
            end
            mr.write(buffer, layout.trace_count_at, mr.uint32(0))
            mr.write(buffer, layout.trace_on_at, mr.uint32(1))
            trace = { seen = 0, lost = 0 }
        end
    end
    each_unit(function(alliance, unit)
        local obj = mr.read_pointer(mr.ud_topointer(unit), 8)
        local flyer = not mr.is_null(mr.read_pointer(obj, U_CTL))
        all_units[#all_units + 1] = { uid = unit:unique_ui_id(), unit = unit, obj = obj }
        if flyer then flyers[#flyers + 1] = { uid = unit:unique_ui_id(), unit = unit, obj = obj } end
        emit(fmt("UNIT %s %d %s obj=%s flyer=%d", tostring(unit:unique_ui_id()), alliance, unit:type(),
            id_of(obj), flyer and 1 or 0))
    end)
    flush()
    bm:repeat_callback(function()
        local done, err = pcall(sample)
        if not done then emit("FAIL tick " .. tostring(err)); flush(); bm:remove_callback(CALLBACK_NAME) end
    end, math.max(cfg.sample, 50), CALLBACK_NAME)
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
