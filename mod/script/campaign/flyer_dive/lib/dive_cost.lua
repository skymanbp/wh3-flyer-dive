-- dive_cost.lua — a dive into braced charge-reflection infantry costs the diving models a share of their health
-- 俯冲撞上站定的冲锋反制步兵：俯冲的模型按自身最大生命值的一个比例付出代价
--
-- [D15, d15-1118 stage 5; docs/DECISIONS.md D15] The cave dv_cost (tools/pipelines/dive_cost_asm.py) judges
-- every impact / charge-collision hit of a flying model on a soldier during the first ticks after a dive's
-- touchdown, on the game's own inputs (the dive mark, the soldier's bracing flag, its unit's charge-reflection
-- attribute, the front arc of the game's bracing angle), and writes one ring entry per judged contact into the
-- dive caves' buffer. This module reads that ring (memreader Plus, the channel lib/dive.lua's counters use),
-- sums the paying models of one flyer unit per call of tick(), and takes the share through the game's own
-- battle-script command unit:reduce_hitpoints_unary(p, false), p = the models' shares / the unit's starting
-- number of soldiers, never more than cost.max_call in one call and never below cost.keep of the unit's health.
-- Numbers: the site table's `cost` (generated from tools/lib/air_dive_rules.py).
-- A unit object that cannot be resolved costs nothing and gives one log line; nothing here raises to its caller
-- except a broken buffer read, which the battle entry catches and logs once.
-- When _G.flyer_dive_cost_observer is a function (the test-only recorder sets it), every entry and call is also
-- handed to it as a line in the recorder's format.
--
-- Pure module: no core/cm/bm calls at load (required modules compile in the bare _G).

local M = {}
M.__index = M

local fmt = string.format
local function sub(s, i, j) return (string.sub_lua or string.sub)(s, i, j) end

local LINES_MAX = 50                    -- COST lines per battle in the battle log (the counters go on)

local function u32(raw, at)
    local a, b, c, d = raw:byte(at + 1, at + 4)
    return a + b * 256 + c * 65536 + d * 16777216
end

-- 8 little-endian bytes -> 16 upper-case hex digits (a pointer never goes through a number: float32)
local function hex64(raw, at)
    local t = {}
    for i = at + 8, at + 1, -1 do t[#t + 1] = fmt("%02X", raw:byte(i)) end
    return table.concat(t)
end

-- memreader Plus's text of a pointer -> the same 16 digits; nil when it is not one
local function norm(text)
    local t = string.upper(string.gsub(string.gsub(tostring(text), "^0[xX]", ""), "[^%x]", ""))
    if #t == 0 or #t > 16 then return nil end
    return string.rep("0", 16 - #t) .. t
end

-- F32 bits -> a number, for the observer's lines only
local function f32(raw, at)
    local b1, b2, b3, b4 = raw:byte(at + 1, at + 4)
    local sign = b4 >= 128 and -1 or 1
    local e = (b4 % 128) * 2 + math.floor(b3 / 128)
    local m = (b3 % 128) * 65536 + b2 * 256 + b1
    if e == 0 then return 0 end
    if e == 255 then return sign * math.huge end
    return sign * (1 + m / 8388608) * 2 ^ (e - 127)
end

-- one battle: `mr` memreader Plus, `buf` the dive caves' buffer, `site` the dive site table, `record` the battle
-- log's line writer
function M.new(mr, buf, site, record)
    local self = setmetatable({}, M)
    self.mr, self.buf, self.l, self.c = mr, buf, site.layout, site.cost
    self.record = type(record) == "function" and record or function() end
    self.units, self.unknown, self.pending = {}, {}, {}
    self.seen, self.lines = 0, 0
    self.n = { calls = 0, models = 0, arc = 0, no_attribute = 0, unresolved = 0, refused = 0, failed = 0, lost = 0 }
    return self
end

function M:observe(line)
    local o = _G.flyer_dive_cost_observer
    if type(o) == "function" then pcall(o, line) end
end

function M:line(text)
    if self.lines >= LINES_MAX then return end
    self.lines = self.lines + 1
    pcall(self.record, text)
end

-- the battle's units by their engine object (the ring's unit fields); true when the walk finished
function M:map(bm)
    local mr = self.mr
    return pcall(function()
        local alliances = bm:alliances()
        for a = 1, alliances:count() do
            local armies = alliances:item(a):armies()
            for j = 1, armies:count() do
                local us = armies:item(j):units()
                for k = 1, us:count() do
                    local unit = us:item(k)
                    local ok, obj = pcall(function() return mr.read_pointer(mr.ud_topointer(unit), 8) end)
                    local key = ok and obj and norm(mr.tostring(obj))
                    if key then self.units[key] = unit end
                end
            end
        end
    end)
end

local function about(unit)
    local uid, key = "?", "?"
    pcall(function() uid = tostring(unit:unique_ui_id()) end)
    pcall(function() key = tostring(unit:type()) end)
    return uid, key
end

-- the readings after a call, for the observer (cost.follow ticks)
function M:follow(ms)
    if #self.pending == 0 then return end
    local keep = {}
    for _, c in ipairs(self.pending) do
        c.k = c.k + 1
        local hp, men = -1, -1
        pcall(function() hp = c.unit:unary_hitpoints() end)
        pcall(function() men = c.unit:number_of_men_alive() end)
        self:observe(fmt("XA %d %s %d %.6f %d", ms, c.uid, c.k, hp, men))
        if c.k < self.c.follow then keep[#keep + 1] = c end
    end
    self.pending = keep
end

-- one flyer unit's paying models of this tick: one call
function M:apply(key, t, ms, bm)
    local unit = self.units[key]
    if not unit and bm then
        self:map(bm)                    -- a unit that joined after the first walk (reinforcements)
        unit = self.units[key]
    end
    if not unit then
        self.n.unresolved = self.n.unresolved + t.n
        if not self.unknown[key] then
            self.unknown[key] = true
            self:line(fmt("COST unit %s not resolved: %d paying models not charged (no error)", key, t.n))
        end
        self:observe(fmt("XERR %d %d %s no unit object: the cost of %d models not applied", ms, t.tick,
            sub(key, 9, 16), t.n))
        return
    end
    local uid, utype = about(unit)
    if t.bad then
        self.n.unresolved = self.n.unresolved + t.n
        self:line(fmt("COST %s %s: size code %s has no share, %d models not charged", uid, utype, tostring(t.bad), t.n))
        self:observe(fmt("XERR %d %d %s %s size code %s has no share: the cost of %d models not applied", ms, t.tick,
            uid, utype, tostring(t.bad), t.n))
        return
    end
    local init, before, men = -1, -1, -1
    pcall(function() init = unit:initial_number_of_men() end)
    pcall(function() before = unit:unary_hitpoints() end)
    pcall(function() men = unit:number_of_men_alive() end)
    local want = init > 0 and t.share / init or -1
    local p = math.min(want, before - self.c.keep)
    local head = fmt("%d %d %s %s %d %.6f %.6f %.6f %d %d", ms, t.tick, uid, utype, t.n, want, p, before, men, init)
    if init <= 0 or before < 0 or p <= 0 or want > self.c.max_call then
        self.n.refused = self.n.refused + t.n
        self:observe("XREF " .. head)
        return
    end
    local ok, err = pcall(function() unit:reduce_hitpoints_unary(p, false) end)
    if not ok then
        self.n.failed = self.n.failed + t.n
        self:line(fmt("COST %s %s: the game's call raised: %s", uid, utype, tostring(err)))
        self:observe("XERR " .. head .. " the call raised: " .. tostring(err))
        return
    end
    self.n.calls, self.n.models = self.n.calls + 1, self.n.models + t.n
    self:line(fmt("COST %d ms %s %s: %d models paid, p %.4f of the unit (health %.4f before)", ms, uid, utype, t.n, p,
        before))
    self:observe("X " .. head)
    if type(_G.flyer_dive_cost_observer) == "function" then
        self.pending[#self.pending + 1] = { unit = unit, uid = uid, k = 0 }
    end
end

-- the observer's line for one ring entry (victim unit resolved when it can be)
function M:note(kind, e, ms)
    local k = self.c.kinds
    local victim = self.units[hex64(e, 16)]
    local vuid, vkey = "?", "?"
    if victim then vuid, vkey = about(victim) end
    local tail = fmt("%d %d %s %s %s %s", ms, u32(e, 24), vuid, vkey, sub(hex64(e, 8), 9, 16), sub(hex64(e, 0), 9, 16))
    if kind == k.no_attribute then
        self:observe("XNOATTR " .. tail)
    else
        self:observe(fmt("%s %s %.4f %02X", kind == k.pay and "XPAY" or "XARC", tail, f32(e, 32), u32(e, 40)))
    end
end

-- once per battle-script tick: read the new ring entries, then one call per paying flyer unit
function M:tick(ms, bm)
    self:follow(ms)
    local l, mr, buf, k = self.l, self.mr, self.buf, self.c.kinds
    local count = u32(mr.read(buf, l.cost_count_at, 4), 0)
    if count - self.seen > l.cost_slots then
        self.n.lost = self.n.lost + (count - self.seen - l.cost_slots)
        self.seen = count - l.cost_slots
    end
    local tally, order = {}, {}
    while self.seen < count do
        local e = mr.read(buf, l.cost_ring_at + (self.seen % l.cost_slots) * l.cost_entry, l.cost_entry)
        if u32(e, 44) ~= self.seen + 1 then break end      -- not written yet
        self.seen = self.seen + 1
        local kind = u32(e, 36)
        self:note(kind, e, ms)
        if kind == k.pay then
            local key = hex64(e, 8)
            local t = tally[key]
            if not t then
                t = { n = 0, share = 0, tick = 0 }
                tally[key] = t
                order[#order + 1] = key
            end
            t.n = t.n + 1
            local share = self.c.share_by_code[u32(e, 28)]
            if share then t.share = t.share + share else t.bad = u32(e, 28) end
            if u32(e, 24) > t.tick then t.tick = u32(e, 24) end
        elseif kind == k.arc then
            self.n.arc = self.n.arc + 1
        elseif kind == k.no_attribute then
            self.n.no_attribute = self.n.no_attribute + 1
        end
    end
    for _, key in ipairs(order) do self:apply(key, tally[key], ms, bm) end
end

-- the battle log's counters
function M:counts()
    local n = self.n
    return fmt("dive costs: calls %d, models paid %d, braced but behind the arc %d, braced without charge reflection "
        .. "%d, unresolved %d, refused %d, failed %d, entries lost %d", n.calls, n.models, n.arc, n.no_attribute,
        n.unresolved, n.refused, n.failed, n.lost)
end

return M
