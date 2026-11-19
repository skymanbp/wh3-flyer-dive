-- dive.lua — the physics dive: a landing flyer keeps its speed, only the bodies it hits slow it
-- 物理俯冲：落地的飞兽保留速度，只被撞到的身体减慢（经 memreader_plus 装八个代码洞）
--
-- [AIR-DIVE-MP-DIVE-W1 2026-11-12, user rulings CONTENT_LEDGER §C8-60 / §C8-61]
-- Eight code caves (source, emulator check and sites:
-- tools/pipelines/dive_cave_asm.py; the site table data/dive_site.lua
-- is generated from it): a flyer's charge is aimed through the enemy like a
-- ground cavalry charge (the engine's own distance), and while a landed flyer
-- is still faster than the skip speed it neither starts a contact attack nor
-- stops its flight movement, nor [AIR-DIVE-RELEASE-W1] is it re-pathed by the
-- melee engage approach, a restart or per-tick step of its charge order or its attack
-- behaviour's update (five call-site caves). Every flyer, both sides, AI included; ground units
-- are never touched (each cave first checks for a flight controller).
--
-- The caves stay in the game for the session (memreader Plus never removes a
-- cave), so "off" is mode 0: every call passes through, exactly vanilla.
-- Buffer +allowed_at holds "allowed", written by the campaign's agreement step
-- and read by the campaign's battles (another Lua state). Same shape as
-- lib/takeoff.lua.
-- / 洞装上后整个会话都在；"关"＝模式 0，行为与不装相同。
--
-- Pure module: no core/cm/bm calls (required modules compile in the bare _G).

local M = {}
local cave = require("script/campaign/flyer_dive/lib/cave_common")  -- shared installed() scan (TEST-REPAIR-1113)

local site, sites = nil, nil
local tried, tried_why = false, nil
local state = { status = "not_started", why = nil }
local log = function() end

local function say(text) pcall(log, "[flyer_dive] " .. text) end
local function sub(s, i, j) return (string.sub_lua or string.sub)(s, i, j) end
local function mr_() return _G.memreader_plus end

local function failed(why)
    state.status, state.why = "failed", tostring(why)
    say("ERROR: " .. state.why)
    return nil, state.why
end

local function search()
    local mr = mr_()
    if not mr then
        return nil, "memreader_plus did not load (" .. tostring(_G.memreader_plus_load_error or "no reason given") .. ")"
    end
    if type(mr.patcher) ~= "function" then return nil, "memreader_plus has no patcher (too old)" end
    if not site then
        local ok, data = pcall(require, "script/campaign/flyer_dive/data/dive_site")
        if not ok or type(data) ~= "table" or type(data.entries) ~= "table" or type(data.layout) ~= "table" then
            return nil, "site table did not load: " .. tostring(data)
        end
        site = data
    end
    local h, refused = mr.patcher(site.owner)
    if not h then return nil, "patcher refused: " .. tostring(refused) end
    if type(h.sites) ~= "function" then return nil, "memreader_plus has no site loader (too old)" end
    local ok, found = pcall(function() return h:sites(site.entries, function(t) say(t) end) end)
    if not ok or not found then return nil, "site search failed: " .. tostring(found) end
    for _, entry in ipairs(site.entries) do
        if not found.found(entry.name) then
            return nil, ("%s not usable: %s"):format(entry.name, tostring(found.why(entry.name)))
        end
    end
    return found
end

-- Find the sites (once per Lua state). Returns the site-loader api, or nil and why.
function M.prepare(log_fn)
    if type(log_fn) == "function" then log = log_fn end
    if not tried then
        tried = true
        sites, tried_why = search()
    end
    return sites, tried_why
end

function M.sites() return sites end
function M.owner() return site and site.owner end
function M.feature() return site and site.feature end
function M.format() return site and site.format end
function M.layout() return site and site.layout end

local function put_u32(buf, off, v) mr_().write(buf, off, mr_().uint32(v)) end
local function u32(buf, off)
    local a, b, c, d = mr_().read(buf, off, 4):byte(1, 4)
    return a + b * 256 + c * 65536 + d * 16777216
end

-- The buffer the installed caves share and how many are installed: nil, 0 when
-- none is; nil, -1 when they disagree or the buffer is not ours.
-- (one home: lib/cave_common.lua)
local function installed() return cave.installed(mr_(), site, sites) end

-- Install the caves, or find the ones an earlier battle / the campaign of this
-- session installed. Returns the buffer (a new one is off), or nil and why.
-- Never throws. / 装洞或找到本会话已装的洞；返回缓冲区。
function M.install(log_fn)
    if type(log_fn) == "function" then log = log_fn end
    local api, why = M.prepare()
    if not api then return failed("not installed: " .. tostring(why)) end
    local ok, buf, reason = pcall(function()
        local mr, layout = mr_(), site.layout
        local have, count = installed()
        if count < 0 then return nil, "caves of another layout hold the sites" end
        if have and count == #site.caves then return have end
        if not have then
            have = mr.game_alloc(layout.bytes)
            if not have then return nil, "game_alloc failed" end
            -- [AIR-DIVE-BRACE-W1 round 3] the slide table is claimed with lock cmpxchg16b: 16-byte aligned
            if sub(mr.tostring(have), -1) ~= "0" then return nil, "buffer not 16-byte aligned" end
            mr.write(have, 0, string.rep("\0", layout.bytes))
            mr.write(have, layout.magic_at, layout.magic)
            -- F32 bits generated from the cave source (game Lua numbers are float32)
            put_u32(have, layout.skip_speed_at, site.skip_speed_bits)
        end
        local given = {}
        for _, name in ipairs(site.caves) do
            given[name] = { buf = have }
            local off = site.resume_at[name]
            if off then
                local at = api.address(name)
                if not at then return nil, name .. " has no address" end
                given[name].resume = mr.add(at, off)
            end
        end
        local done, problem = api.install_feature(site.feature, given)
        if not done then return nil, tostring(problem) end
        local now, placed = installed()
        if not now or placed ~= #site.caves then return nil, "not every cave is in place after the install" end
        say(("installed %d caves (built for %s), buffer %s"):format(placed, tostring(site.build), mr.tostring(now)))
        return now
    end)
    if not ok then return failed("not installed: " .. tostring(buf)) end
    if not buf then return failed("not installed: " .. tostring(reason)) end
    state.status, state.why = "installed", nil
    return buf
end

-- The buffer of caves already in the game, without installing any. Returns
-- buffer, complete; nil when there is none. Never throws.
function M.find(log_fn)
    if type(log_fn) == "function" then log = log_fn end
    if not M.prepare() then return nil, false end
    local ok, buf, count = pcall(installed)
    if not ok or not buf then return nil, false end
    return buf, count == #site.caves
end

-- Start the dive for a battle: counters cleared, then the mode last.
function M.arm(buf)
    local l = site.layout
    put_u32(buf, l.mode_at, 0)
    for _, at in ipairs({ l.skipped_at, l.throughs_at, l.kept_at, l.engaged_at, l.reordered_at,
            l.contact_at, l.settled_at, l.released_at, l.committed_at, l.closed_at, l.engaged_body_at }) do
        put_u32(buf, at, 0)
    end
    -- [AIR-DIVE-BRACE-W1 round 3] the slide table holds entity pointers of the last battle: cleared
    local zeros = string.rep("\0", l.slide_slots * 16)
    mr_().write(buf, l.slide_at, zeros)
    put_u32(buf, l.skip_speed_at, site.skip_speed_bits)
    -- [D15, d15-1118 stage 5] the dive marks and the cost ring of the last battle are cleared; the front-arc
    -- switch and the game's cos(bracing_attack_angle) are written as the site table carries them (raw F32
    -- bytes: a game Lua number is float32 and could not carry the bits exactly)
    if l.mark_count_at then mr_().write(buf, l.mark_count_at, string.rep("\0", l.bytes - l.mark_count_at)) end
    if site.cost and l.cost_arc_on_at then
        mr_().write(buf, l.cost_arc_cos_at, site.cost.arc_cos_bytes)
        put_u32(buf, l.cost_arc_on_at, site.cost.front_arc and 1 or 0)
    end
    put_u32(buf, l.mode_at, 1)
end

-- Mode 0: every call passes through (vanilla). / 回到原版行为。
function M.pass_through(buf)
    if buf then put_u32(buf, site.layout.mode_at, 0) end
end

function M.set_allowed(buf, on) put_u32(buf, site.layout.allowed_at, on and 1 or 0) end
function M.allowed(buf) return mr_().read(buf, site.layout.allowed_at, 4) == "\1\0\0\0" end

-- {mode, skipped, throughs, kept, engaged, reordered, contact, settled}: contact
-- attacks not started for a fast landed flyer, flyer charges aimed through,
-- flight stops held off, engage-approach and charge-order re-paths held off,
-- melee engages held off, blocked stops held off (AIR-DIVE-BRACE-W1).
function M.counters(buf)
    local l = site.layout
    return { mode = u32(buf, l.mode_at), skipped = u32(buf, l.skipped_at),
        throughs = u32(buf, l.throughs_at), kept = u32(buf, l.kept_at),
        engaged = u32(buf, l.engaged_at), reordered = u32(buf, l.reordered_at),
        contact = u32(buf, l.contact_at), settled = u32(buf, l.settled_at),
        released = u32(buf, l.released_at), committed = u32(buf, l.committed_at),
        -- [FLYER-FIX-1117] slide windows ended by the first melee engage; contacts with a body already in
        -- melee with another unit, not carried
        closed = u32(buf, l.closed_at), engaged_body = u32(buf, l.engaged_body_at) }
end

-- Off for this session's later battles too (the agreement said no or has not
-- answered yet). / 关闭并撤销"允许"。
function M.forbid(why, log_fn)
    if type(log_fn) == "function" then log = log_fn end
    local buf = M.find()
    if buf then
        pcall(function()
            M.pass_through(buf)
            M.set_allowed(buf, false)
        end)
    end
    state.status, state.why = "off", tostring(why)
    say("off: " .. tostring(why))
    return true
end

function M.state() return { status = state.status, why = state.why } end

return M
