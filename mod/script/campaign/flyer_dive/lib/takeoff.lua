-- takeoff.lua — flyers are held on the ground only while struck (memreader_plus code caves)
-- 飞兽只在挨打时被按在地上：经 memreader_plus 装两个代码洞，全体飞行单位
--
-- [AIR-DIVE-TAKEOFF-W1 2026-11-12] A flyer ordered away from melee is asked to
-- take off, then waits on a 3.0 s timer that the game holds at full for as
-- long as its engaged check says the model is busy -- any contact, struck or not.
-- THE RULE [D3, user ruling 2026-11-17, docs/DECISIONS.md]: a flying model that
-- was hit by a melee attack within the last N seconds cannot take off; N by its
-- own body size (small 5.5, medium 5.0, large 4.5, very large 4.0 s [D37]; a ridden
-- unit: its mount's), decided for each model on its own. Every flying unit,
-- both sides, AI included. One cave, at the engine's damage applier, records every damaging
-- melee hit (the engine's own damage type 0: weapon hits, splash attacks,
-- matched combat; not charges, impacts, ranged or abilities) on the flying
-- entity it lands on [FLYER-TAKEOFF-HITS 2026-11-16]; one answers the timer
-- in place of the engaged check (source, emulator check and sites:
-- tools/pipelines/pin_cave_asm.py; the site table and buffer layout
-- data/takeoff_site.lua are generated from it).
-- / 每个飞行兵模按自己的体型（小 5.5、中 5.0、大 4.5、超大 4.0 秒，D37；骑乘看坐骑），最近 N 秒内近战挨打就不能起飞，
--   否则 3 秒后离地（D3）。一个洞在扣血函数入口记全部近战命中（含横扫与对决动作），一个洞代替原版的交战判定
--   逐个兵模回答起飞计时。
-- [D23, 2026-11-20] Two more caves, in the engine's per-model charge-task
-- handlers: when a model is in the air, its unit has no order in its queue
-- and another model of the unit is held on the ground by the rule above, the
-- engine's charge that would pull it back to the held model is skipped. A
-- player's order (an order in the queue) passes. / 部队没有命令时，已起飞的
--   兵模不再被引擎拉回被按住的兵模身边；玩家下的命令照常执行。
--
-- The caves stay in the game for the session (memreader Plus never removes a
-- cave), so "off" is mode 0: nothing is recorded and the game's own engaged
-- check answers, exactly as without the mod. Buffer +allowed_at holds
-- "allowed", written by the campaign's agreement step and read by the
-- campaign's battles (a battle is another Lua state and cannot ask the
-- agreement). / 洞装上后整个会话都在；"关"＝模式 0，行为与不装相同。
--
-- Pure module: no core/cm/bm calls (required modules compile in the bare _G).
-- The entry scripts (campaign/mod and battle/mod flyer_takeoff.lua) decide
-- WHEN the rule may apply (multiplayer rules) and pass a log function in.
-- / 纯模块；何时可生效（联机规则）由两个入口脚本决定。

local M = {}
local cave = require("script/campaign/flyer_dive/lib/cave_common")  -- shared installed() scan (TEST-REPAIR-1113)

local site, sites = nil, nil
local tried, tried_why = false, nil
local state = { status = "not_started", why = nil }
local log = function() end

local function say(text) pcall(log, "[flyer_takeoff] " .. text) end
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
        local ok, data = pcall(require, "script/campaign/flyer_dive/data/takeoff_site")
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
-- (one home: lib/cave_common.lua)
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
        -- each cave that does not fall through to its own bytes resumes at its site + resume_at[name]
        -- (the hold cave after the engaged check it replaces; the regroup caves after the skipped call).
        -- A table with one hold resume (resume_at a number: the traced test table) gives it to every cave.
        local given = {}
        if type(site.resume_at) == "table" then
            for _, name in ipairs(site.caves) do
                given[name] = { buf = have }
                local off = site.resume_at[name]
                if off then
                    local at = api.address(name)
                    if not at then return nil, name .. " has no address" end
                    given[name].resume = mr.add(at, off)
                end
            end
        else
            local hold = api.address(site.hold)
            if not hold then return nil, "the hold site has no address" end
            local resume = mr.add(hold, site.resume_at)
            for _, name in ipairs(site.caves) do given[name] = { buf = have, resume = resume } end
        end
        -- [D44] a cave that calls an engine function: the two found addresses must be the table's distance apart
        for _, d in ipairs(site.distances or {}) do
            local a, b = api.address(d.from), api.address(d.to)
            if not a or not b then return nil, "no address for " .. tostring(d.from) .. " / " .. tostring(d.to) end
            if mr.tostring(mr.add(a, d.bytes)) ~= mr.tostring(b) then
                return nil, d.to .. " is not " .. tostring(d.bytes) .. " bytes after " .. d.from .. " (game patched?)"
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
-- are cleared (the entries are this battle's entity pointers), then the five
-- windows (size code 1..4, then an unknown code; `windows` = a list of five to
-- use instead of the ruled ones, tests only), then the mode last. mode 1 = the
-- rule; 2 = record hits only, the game's own check still answers (tests).
-- `regroup_off` (tests only, the recorder's "regroup 0"): the regroup caves count what they would skip and let
-- the engine's call run; the shipped scripts never pass it, so a battle always starts with them on.
-- / 清表后写五个窗口（体型 1..4 与未知体型），模式最后写。
function M.arm(buf, windows, mode, regroup_off)
    local mr, layout = mr_(), site.layout
    put_u32(buf, layout.mode_at, 0)
    local zeros = string.rep("\0", 1024)
    -- the model table, then [D39] the unit table (both hold this battle's pointers)
    for _, t in ipairs({ { layout.table_at, layout.table_slots }, { layout.unit_table_at, layout.unit_slots } }) do
        if t[1] then
            local span = t[2] * layout.entry_bytes
            for off = 0, span - 1, 1024 do
                mr.write(buf, t[1] + off, sub(zeros, 1, math.min(1024, span - off)))
            end
        end
    end
    for _, at in ipairs({ layout.stamps_at, layout.dropped_at, layout.unmatched_at, layout.held_at,
            layout.free_at, layout.unsized_at, layout.regroup_calls_at, layout.regroup_skipped_at,
            layout.regroup_would_at, layout.regroup_queued_at, layout.regroup_unheld_at,
            layout.unit_held_at, layout.unit_stamps_at, layout.unit_dropped_at, layout.repick_at,
            layout.chargewait_at }) do
        if at then put_u32(buf, at, 0) end
    end
    if layout.regroup_off_at then put_u32(buf, layout.regroup_off_at, regroup_off and 1 or 0) end
    local use = windows or layout.windows
    for i = 1, #layout.windows do
        put_u32(buf, layout.windows_at + 4 * (i - 1), use[i] or layout.windows[i])
    end
    if layout.unit_ticks_at then put_u32(buf, layout.unit_ticks_at, layout.unit_ticks) end
    put_u32(buf, layout.mode_at, mode or 1)
end

-- Mode 0: nothing recorded, the game's own engaged check answers. / 回到原版行为。
function M.pass_through(buf)
    if buf then put_u32(buf, site.layout.mode_at, 0) end
end

function M.set_allowed(buf, on) put_u32(buf, site.layout.allowed_at, on and 1 or 0) end
function M.allowed(buf) return mr_().read(buf, site.layout.allowed_at, 4) == "\1\0\0\0" end

-- {windows, mode, stamps, dropped, unmatched, held, free, unsized, regroup = {off, calls, skipped, would,
-- queued, unheld} or nil, unit = {ticks, held, stamps, dropped} or nil (D39)}: the header as it stands.
function M.counters(buf)
    local l = site.layout
    local windows = {}
    for i = 1, #l.windows do windows[i] = u32(buf, l.windows_at + 4 * (i - 1)) end
    local regroup = nil
    if l.regroup_calls_at then
        regroup = { off = u32(buf, l.regroup_off_at), calls = u32(buf, l.regroup_calls_at),
            skipped = u32(buf, l.regroup_skipped_at), would = u32(buf, l.regroup_would_at),
            queued = u32(buf, l.regroup_queued_at), unheld = u32(buf, l.regroup_unheld_at) }
    end
    local unit = nil
    if l.unit_ticks_at then
        unit = { ticks = u32(buf, l.unit_ticks_at), held = u32(buf, l.unit_held_at),
            stamps = u32(buf, l.unit_stamps_at), dropped = u32(buf, l.unit_dropped_at) }
    end
    return { windows = windows, mode = u32(buf, l.mode_at),
        stamps = u32(buf, l.stamps_at), dropped = u32(buf, l.dropped_at),
        unmatched = u32(buf, l.unmatched_at), held = u32(buf, l.held_at),
        free = u32(buf, l.free_at), unsized = u32(buf, l.unsized_at), regroup = regroup, unit = unit,
        repick = l.repick_at and u32(buf, l.repick_at) or nil,
        chargewait = l.chargewait_at and u32(buf, l.chargewait_at) or nil }
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
