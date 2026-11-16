-- ld_flyer_takeoff.lua — flyers are held on the ground only while struck (memreader_plus code caves)
-- 飞兽只在挨打时被按在地上：经 memreader_plus 装两个代码洞，全体飞行单位
--
-- [AIR-DIVE-TAKEOFF-W1 2026-11-12, user rulings 2026-11-12, CONTENT_LEDGER
-- §C8-57 and §C8-58] A flyer ordered away from melee is asked to take off,
-- then waits on a 3.0 s timer that the game holds at full for as long as its
-- engaged check says the model is busy -- any contact, struck or not.
-- THE RULE: a flying unit is held only while MORE THAN HALF of its living
-- models were struck in melee within the last 1.5 s (15 battle ticks); a
-- single-model unit (one living model) uses its one model, struck within the
-- last 3.0 s (30 ticks; §C8-78, user ruling 2026-11-16). Every flying unit,
-- both sides, AI included. One cave, at the engine's damage applier, records every damaging
-- melee hit (the engine's own damage type 0: weapon hits, splash attacks,
-- matched combat; not charges, impacts, ranged or abilities) on the flying
-- entity it lands on [FLYER-TAKEOFF-HITS 2026-11-16]; one answers the timer
-- in place of the engaged check (source, emulator check and sites:
-- tools/pipelines/pin_cave_asm.py; the site table and buffer layout
-- data/ld_flyer_takeoff_site.lua are generated from it).
-- / 过半存活模型在最近 1.5 秒内近战挨打才按住（只剩一个存活模型时为 3 秒，§C8-78），否则 3 秒后离地。一个洞在扣血函数入口
--   记全部近战命中（含横扫与对决动作），一个洞代替原版的交战判定回答起飞计时。
--
-- The caves stay in the game for the session (memreader Plus never removes a
-- cave), so "off" is mode 0: nothing is recorded and the game's own engaged
-- check answers, exactly as without the mod. Buffer +allowed_at holds
-- "allowed", written by the campaign's agreement step and read by the
-- campaign's battles (a battle is another Lua state and cannot ask the
-- agreement). / 洞装上后整个会话都在；"关"＝模式 0，行为与不装相同。
--
-- Pure module: no core/cm/bm calls (required modules compile in the bare _G).
-- The entry scripts (campaign/mod and battle/mod ld_flyer_takeoff.lua) decide
-- WHEN the rule may apply (multiplayer rules) and pass a log function in.
-- / 纯模块；何时可生效（联机规则）由两个入口脚本决定。

local M = {}
local cave = require("script/campaign/lore_disasters/lib/ld_cave_common")  -- shared installed() scan (TEST-REPAIR-1113)

local site, sites = nil, nil
local tried, tried_why = false, nil
local state = { status = "not_started", why = nil }
local log = function() end

local function say(text) pcall(log, "[ld_flyer_takeoff] " .. text) end
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
        local ok, data = pcall(require, "script/campaign/lore_disasters/data/ld_flyer_takeoff_site")
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
    -- every cave site and every anchor (the engine fields the caves read)
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

-- The agreement step's site list (nil before prepare succeeded).
function M.sites() return sites end
function M.owner() return site and site.owner end
function M.feature() return site and site.feature end
function M.format() return site and site.format end

local function put_u32(buf, off, v) mr_().write(buf, off, mr_().uint32(v)) end
local function u32(buf, off)
    local a, b, c, d = mr_().read(buf, off, 4):byte(1, 4)
    return a + b * 256 + c * 65536 + d * 16777216
end

-- The buffer the installed caves share and how many caves are installed:
-- nil, 0 when none is; nil, -1 when they disagree or the buffer is not ours.
-- (one home: lib/ld_cave_common.lua)
local function installed() return cave.installed(mr_(), site, sites) end

-- Install the caves, or find the ones an earlier battle / the campaign of
-- this session installed. Returns the buffer (mode untouched: a new one is
-- off), or nil and why. Never throws. / 装洞或找到本会话已装的洞；返回缓冲区。
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
            local zeros = string.rep("\0", 1024)
            for off = 0, layout.bytes - 1, 1024 do
                mr.write(have, off, sub(zeros, 1, math.min(1024, layout.bytes - off)))
            end
            mr.write(have, layout.magic_at, layout.magic)
        end
        -- the hold cave answers, then continues after the engaged check it replaces
        local hold = api.address(site.hold)
        if not hold then return nil, "the hold site has no address" end
        local resume = mr.add(hold, site.resume_at)
        local given = {}
        for _, name in ipairs(site.caves) do given[name] = { buf = have, resume = resume } end
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

-- The buffer of caves already in the game, without installing any (battles of
-- a multiplayer campaign: the campaign's agreement decided). Returns buffer,
-- complete (every cave in place); nil when there is none. Never throws.
function M.find(log_fn)
    if type(log_fn) == "function" then log = log_fn end
    if not M.prepare() then return nil, false end
    local ok, buf, count = pcall(installed)
    if not ok or not buf then return nil, false end
    return buf, count == #site.caves
end

-- Start the rule for a battle: caves off while the table and the counters
-- are cleared (the entries are this battle's entity pointers), then the
-- windows (multi-model, then single-model §C8-78), then the mode last. mode 1
-- = the rule; 2 = record hits only, the game's own check still answers
-- (tests). / 清表后开规则，模式最后写。
function M.arm(buf, window, mode, window_single)
    local mr, layout = mr_(), site.layout
    put_u32(buf, layout.mode_at, 0)
    local zeros = string.rep("\0", 1024)
    local span = layout.table_slots * layout.entry_bytes
    for off = 0, span - 1, 1024 do
        mr.write(buf, layout.table_at + off, sub(zeros, 1, math.min(1024, span - off)))
    end
    for _, at in ipairs({ layout.stamps_at, layout.dropped_at, layout.held_at, layout.free_at }) do
        put_u32(buf, at, 0)
    end
    put_u32(buf, layout.window_at, window or layout.window)
    put_u32(buf, layout.window_single_at, window_single or layout.window_single)
    put_u32(buf, layout.mode_at, mode or 1)
end

-- Mode 0: nothing recorded, the game's own engaged check answers. / 回到原版行为。
function M.pass_through(buf)
    if buf then put_u32(buf, site.layout.mode_at, 0) end
end

function M.set_allowed(buf, on) put_u32(buf, site.layout.allowed_at, on and 1 or 0) end
function M.allowed(buf) return mr_().read(buf, site.layout.allowed_at, 4) == "\1\0\0\0" end

-- {window, mode, stamps, dropped, held, free}: the header as it stands.
function M.counters(buf)
    local l = site.layout
    return { window = u32(buf, l.window_at), mode = u32(buf, l.mode_at),
        stamps = u32(buf, l.stamps_at), dropped = u32(buf, l.dropped_at),
        held = u32(buf, l.held_at), free = u32(buf, l.free_at) }
end

function M.layout() return site and site.layout end

-- Turn the rule off for this session's later battles too (the campaign's
-- agreement said no, or has not answered yet). Nothing to do when no cave of
-- ours is in the game. / 关闭并撤销"允许"；没装洞时无事可做。
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
