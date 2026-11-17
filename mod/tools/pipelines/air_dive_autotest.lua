-- ld_air_dive_autotest.lua — battle-side driver for the air-dive charge test
-- 飞兽俯冲自动测试：战斗内驱动——自动开战、摆位、逐个下冲锋令、报完成。
--
-- [AIR-DIVE-AUTOTEST 2026-11-10] The user hand-tested every air-dive canary in
-- a custom battle. This replaces the hands. tools/pipelines/air_dive_autotest.py
-- starts the game straight into the battle defined by the generated xml
-- (game_startup_mode battle <xml>; CA's own terrain/xml_battle/
-- battle_map_test.xml documents the mechanism) and ships this file at
-- script/battle/mod/ld_air_dive_autotest.lua in a helper pack that is enabled
-- for that one run only. Never part of ld_mod.pack or ld_air_dive.pack.
--
-- INERT unless ld_air_dive_autotest_cmd.txt exists in the game's working
-- directory (the folder of Warhammer3.exe). The control file carries
-- key=value lines: dist (start distance, m), spacing (lane spacing, m),
-- settle_ms, stagger_ms, tail_ms, lanes (number of flyer/target pairs),
-- offset (shift of the whole lane block), centre_x / centre_z / axis_x /
-- axis_z (a fixed lane frame, all four or none), lane_off_<i> (lane i's position
-- along the lanes, m; overrides offset + spacing for that lane -- the lanes
-- are picked by measured ground rise, see LANE TERRAIN in the Python driver).
--
-- WHAT IT DOES
--   1. Presses button_battle_start (the loading-screen "start battle" and the
--      deployment panel's button share this id: CA's autorun.lua presses it
--      when the finish_deployment panel opens) from the Deployment phase until
--      the Deployed phase (never earlier: see clicker()).
--   2. On Deployed: takes script control of every unit of both alliances
--      (so neither the player side nor the AI moves anything on its own),
--      teleports lane i's target (xml script_name target_<i>) and flyer
--      (flyer_<i>) onto a line through the midpoint of the two armies, lanes
--      `spacing` apart, flyer `dist` from its target, both facing each other.
--   3. After settle_ms, orders flyer i to attack target i at a run
--      (unitcontroller:attack_unit(target, true, true), CA's own call in
--      lib_battle_script_unit.lua:1928); lane i+1 starts stagger_ms later.
--   4. tail_ms after the last order writes DONE. The Python side then quits
--      the game and reads ld_air_dive_probe.txt (the movement recorder in the
--      dive pack measures movement) and ld_air_dive_autotest_hp.txt (below).
--   5. [AIR-DIVE-W14 2026-11-11] From the charge setup to DONE, every 100 ms,
--      each lane's target hit points: "H <ms> <lane> <unary_hitpoints>
--      <number_of_men_alive>" in ld_air_dive_autotest_hp.txt. The plough is
--      judged on these (target hit-point loss right after touchdown), not on
--      the flyer's position: unit:position() is "the centre position of the
--      main squad of the unit" (assembly_kit/documentation/script/script/
--      battle/battle_unit.html), and the battle_unit interface has no
--      per-soldier position (only position_of_officer, one model), so for a
--      multi-model flyer (griffon knights) the centre only says where the
--      squad's middle is while riders land one by one.
-- Status lines go to ld_air_dive_autotest_status.txt, stamped with battle
-- time in ms (or "real<n>" before the battle clock runs).
--
-- API provenance (CA's scripts, data_script.pack, read 2026-11-10):
--   bm:register_phase_change_callback   _lib/lib_battle_manager.lua:1227
--   bm:repeat_real_callback / remove_real_callback  lib_battle_manager.lua:1975
--   bm:callback                          lib_battle_manager.lua:1932
--   script_unit:new_by_reference(army, script_name)  lib_battle_script_unit.lua:68
--   sunit.uc:take_control / teleport_to_location / attack_unit
--                                        lib_battle_script_unit.lua:1060 / :556 / :1928
--   v(x, z) 2D battle vector             lib_battle_misc.lua:17
--   bearing = atan2(dx, dz) in radians   lib_convex_area.lua:604 (get_bearing),
--     teleport takes degrees (r_to_d)    quest_battles/*/battle_script.lua
--   uic:SetOpacity(255,true) + SimulateLClick  autorun.lua:70-73
--   unit:unary_hitpoints()               battle_unit.html (Unit Strength:
--     "hitpoint strength of all soldiers ... unary fraction of the initial")

local CMD_FILE = "ld_air_dive_autotest_cmd.txt"
local STATUS_FILE = "ld_air_dive_autotest_status.txt"
local HP_FILE = "ld_air_dive_autotest_hp.txt"   -- [AIR-DIVE-W14]

local probe = io.open(CMD_FILE, "r")
if not probe then return end            -- no control file: completely inert
local cfg = { dist = 250, spacing = 250, settle_ms = 3000,
              stagger_ms = 20000, tail_ms = 30000, lanes = 3, offset = 0,
              lane_off = {}, centre_x = false, centre_z = false,
              axis_x = false, axis_z = false }
-- [AIR-DIVE-W15] string keys: scenario (charge | engage) and breath (a comma
-- list of ability keys the Python side derived as breaths)
cfg.scenario, cfg.breath = "charge", {}
cfg.engage_ms, cfg.breath_ms, cfg.away_ms, cfg.away_m = 3000, 15000, 25000, 150
-- [AIR-DIVE-TAKEOFF-W1 2026-11-12] melee_off_<i>=<ms>: from that battle time
-- lane i's target has the engine attribute melee_disabled (it stays in contact
-- but does not attack; 0 = from the start). CYCLE scenario (scenario=cycle):
-- flyer and target attack each other at engage_ms; when cycle_away_ms >= 0
-- the flyer is ordered away (away_m back, at a run) cycle_away_ms after each
-- attack order and attacks again cycle_back_ms later, until engage_ms +
-- fight_ms, then DONE; every 100 ms "F <ms> <lane> <flyer unary hp> <flyer
-- men> <target unary hp> <target men> <flying> <in melee>" in the hp file.
-- retreat_<i>=<ms>: from that battle time lane i's target withdraws 80 m
-- straight away from its flyer, at a run (the enemy stops attacking).
cfg.melee_off, cfg.retreat = {}, {}
cfg.fight_ms, cfg.cycle_away_ms, cfg.cycle_back_ms = 90000, -1, 6000
-- [FLYER-FIX-1117 2026-11-17] PUSH scenarios (player report "dive or trash": a unit already in melee was
-- dragged back into its own missile line when the flyer charged it again).
--   scenario=recharge: flyer i attacks target i at settle_ms; recharge_ms later (and every recharge_gap_ms,
--     recharge_count times) the same attack order is given again while they are in melee.
--   scenario=assist: ally i (the flyer's side, xml script_name ally_<i>) and target i attack each other at
--     settle_ms; assist_ms later flyer i attacks target i, which is then already in melee with the ally
--     (re-charges as for recharge, timed from that attack).
--   Every 100 ms: "P <ms> <lane> <target x> <target z> <flyer x> <flyer z> <target in melee>
--     <flyer in melee> <flyer flying>" in the hp file; DONE at settle_ms + push_ms.
--   cam_lane=<i> (any scenario): every cam_every_ms the camera looks at lane i's target from the side,
--     cam_dist m away and cam_up m up, so the Python side's screenshots show that lane.
cfg.recharge_ms, cfg.recharge_gap_ms, cfg.recharge_count = 15000, 15000, 1
cfg.assist_ms, cfg.push_ms = 12000, 45000
cfg.recharge_away_ms = 0       -- > 0: a move-away order (away_m back) this long before each re-charge
cfg.cam_lane, cfg.cam_every_ms, cfg.cam_dist, cfg.cam_up = 0, 500, 45, 22
cfg.cam_flyer = 0          -- 1: follow lane cam_lane's flyer instead of its target
for line in probe:lines() do
    local k, val = line:match("^%s*([%w_]+)%s*=%s*([%d%.%-]+)%s*$")
    if k and cfg[k] ~= nil then cfg[k] = tonumber(val) end
    local li = k and k:match("^lane_off_(%d+)$")
    if li then cfg.lane_off[tonumber(li)] = tonumber(val) end
    local mi = k and k:match("^melee_off_(%d+)$")
    if mi then cfg.melee_off[tonumber(mi)] = tonumber(val) end
    local ri = k and k:match("^retreat_(%d+)$")
    if ri then cfg.retreat[tonumber(ri)] = tonumber(val) end
    local sk, sval = line:match("^%s*(scenario)%s*=%s*([%w_]+)%s*$")
    if sk then cfg.scenario = sval end
    local blist = line:match("^%s*breath%s*=%s*([%w_,]+)%s*$")
    if blist then
        for key in blist:gmatch("[^,]+") do cfg.breath[key] = true end
    end
end
probe:close()

local fmt = string.format
local real_ticks = 0

local function stamp()
    local ok, ms = pcall(function() return bm:time_elapsed_ms() end)
    if ok and type(ms) == "number" and ms > 0 then return tostring(ms) end
    return "real" .. real_ticks
end

local function status(line)
    local f = io.open(STATUS_FILE, "a")
    if f then f:write(stamp() .. " " .. line .. "\n"); f:close() end
end

if not bm then
    status("FAIL bm unavailable at chunk scope")
    return
end

status(fmt("harness_loaded dist=%s spacing=%s settle_ms=%s stagger_ms=%s tail_ms=%s lanes=%s",
    cfg.dist, cfg.spacing, cfg.settle_ms, cfg.stagger_ms, cfg.tail_ms, cfg.lanes))

-- ---------------------------------------------------------------- clicking
local function bfs_find(root, target)
    local queue, seen = { root }, 0
    while #queue > 0 and seen < 6000 do
        local uic = table.remove(queue, 1)
        seen = seen + 1
        if uic:Id() == target then return uic end
        for i = 0, uic:ChildCount() - 1 do
            queue[#queue + 1] = UIComponent(uic:Find(i))
        end
    end
    return nil
end

local function dump_tree(root, depth, max_depth, out)
    if depth > max_depth then return end
    for i = 0, root:ChildCount() - 1 do
        local child = UIComponent(root:Find(i))
        out[#out + 1] = string.rep("  ", depth) .. child:Id()
            .. (child:Visible() and "" or " [hidden]")
        dump_tree(child, depth + 1, max_depth, out)
    end
end

local phase = "loading"
local clicks = 0
local dumped = false
local CLICK_IDS = { "button_battle_start" }
local CLICKER = "ld_air_dive_autotest_clicker"

local function clicker()
    real_ticks = real_ticks + 1
    if phase == "Deployed" or phase == "VictoryCountdown" or phase == "Complete" then
        bm:remove_real_callback(CLICKER)
        return
    end
    local root = core:get_ui_root()
    -- [AIR-DIVE-TAKEOFF-W1 2026-11-12] No click before the game reports the
    -- Deployment phase. Evidence (status files of every lane's runs): 125 runs
    -- never clicked before Deployment and all started on their first click;
    -- the one run that did (eV2: "400 click ... phase=loading", 300 ms before
    -- "700 phase Deployment") ignored its next 654 clicks and hung until the
    -- 900 s timeout, its 120 s dump showing the button visible and no modal
    -- panel. No run ever needed a pre-Deployment click. Each click now also
    -- records what it pressed, so a recurrence has its state on file.
    if phase ~= "Deployment" then return end
    for _, id in ipairs(CLICK_IDS) do
        local uic = bfs_find(root, id)
        if uic and uic:Visible() then
            local function q(m) local ok, v = pcall(function() return uic[m](uic) end); return ok and tostring(v) or "?" end
            local parent = "?"
            pcall(function() parent = UIComponent(uic:Parent()):Id() end)
            uic:SetOpacity(255, true)
            uic:SimulateLClick()
            clicks = clicks + 1
            status(fmt("click %s n=%d phase=%s parent=%s state=%s interactive=%s from_root=%s", id, clicks,
                phase, parent, q("CurrentState"), q("IsInteractive"), q("VisibleFromRoot")))
        end
    end
    if real_ticks == 120 and not dumped then
        -- two minutes without reaching Deployed: leave the UI tree as evidence
        dumped = true
        local lines = {}
        dump_tree(root, 0, 7, lines)
        status("dump_begin phase=" .. phase)
        local f = io.open(STATUS_FILE, "a")
        if f then f:write(table.concat(lines, "\n") .. "\n"); f:close() end
        status("dump_end nodes=" .. #lines)
    end
end

-- ------------------------------------------------------------- the charges
local function find_sunit(name)
    local alliances = bm:alliances()
    for a = 1, alliances:count() do
        local armies = alliances:item(a):armies()
        for j = 1, armies:count() do
            local army = armies:item(j)
            local ok, found = pcall(function() return army:units():item(name) end)
            if ok and found then
                return script_unit:new_by_reference(army, name), a
            end
        end
    end
    return nil
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

-- [AIR-DIVE-W15 2026-11-11] ENGAGE scenario (cfg.scenario == "engage"):
-- every flyer and its target attack each other from a short distance; once
-- they are in melee each flyer is ordered to use its breath on its target
-- (breath_ms) and later to move away at a run (away_ms). Every 100 ms, per
-- lane: "E <ms> <lane> <flying> <moving> <in_melee> <dist> <can_breath>"
-- in the hp file (can_breath = unit:can_perform_special_ability(breath),
-- battle_unit.html "Returns whether the unit can perform the specified
-- special ability"; "-" when the lane has no breath). Orders:
-- unitcontroller:perform_special_ability(key, target unit) and
-- goto_location(position, move fast), battle_unitcontroller.html.
local hp_line
local function run_engage(lanes, ux, uz)
    local keys = {}
    for i, lane in ipairs(lanes) do
        local ok, owned = pcall(function()
            return lane.flyer.unit:owned_non_passive_special_abilities()
        end)
        local names, pick = {}, nil
        if ok and type(owned) == "table" then
            for _, key in ipairs(owned) do
                names[#names + 1] = key
                if cfg.breath[key] and not pick then pick = key end
            end
        end
        keys[i] = pick
        status(fmt("abilities %d owned=%s breath=%s", i,
            table.concat(names, ","), tostring(pick)))
    end
    bm:repeat_callback(function()
        local now = bm:time_elapsed_ms()
        for i, lane in ipairs(lanes) do
            local ok, line = pcall(function()
                local u, t = lane.flyer.unit, lane.target.unit
                local p, q = u:position(), t:position()
                local dx, dz = q:get_x() - p:get_x(), q:get_z() - p:get_z()
                local can = "-"
                if keys[i] then can = tostring(u:can_perform_special_ability(keys[i])) end
                return fmt("E %d %d %s %s %s %.2f %s", now, i,
                    tostring(u:is_currently_flying()), tostring(u:is_moving()),
                    tostring(u:is_in_melee()), math.sqrt(dx * dx + dz * dz), can)
            end)
            hp_line(ok and line or fmt("EFAIL %d %d %s", now, i, tostring(line)))
        end
    end, 100, "ld_air_dive_autotest_engage")
    bm:callback(function()
        for i, lane in ipairs(lanes) do
            local ok, err = pcall(function()
                lane.flyer.uc:attack_unit(lane.target.unit, true, true)
                lane.target.uc:attack_unit(lane.flyer.unit, true, true)
            end)
            status(fmt("engage %d ordered ok=%s %s", i, tostring(ok), ok and "" or tostring(err)))
        end
    end, cfg.engage_ms)
    bm:callback(function()
        for i, lane in ipairs(lanes) do
            if keys[i] then
                local u = lane.flyer.unit
                local ok, err = pcall(function()
                    status(fmt("breath %d key=%s melee=%s flying=%s can=%s", i, keys[i],
                        tostring(u:is_in_melee()), tostring(u:is_currently_flying()),
                        tostring(u:can_perform_special_ability(keys[i]))))
                    lane.flyer.uc:perform_special_ability(keys[i], lane.target.unit)
                end)
                status(fmt("breath %d ordered ok=%s %s", i, tostring(ok), ok and "" or tostring(err)))
            end
        end
    end, cfg.breath_ms)
    bm:callback(function()
        for i, lane in ipairs(lanes) do
            local ok, err = pcall(function()
                local p = lane.flyer.unit:position()
                local x, z = p:get_x() - ux * cfg.away_m, p:get_z() - uz * cfg.away_m
                status(fmt("away %d ordered melee=%s flying=%s to=%.1f,%.1f", i,
                    tostring(lane.flyer.unit:is_in_melee()),
                    tostring(lane.flyer.unit:is_currently_flying()), x, z))
                lane.flyer.uc:goto_location(v(x, z), true)
            end)
            if not ok then status(fmt("FAIL away %d order: %s", i, tostring(err))) end
        end
    end, cfg.away_ms)
    bm:callback(function()
        bm:remove_callback("ld_air_dive_autotest_engage")
        bm:remove_callback("ld_air_dive_autotest_hp")
        hp_line(nil)
        status("DONE")
    end, cfg.away_ms + cfg.tail_ms)
end

-- [FLYER-FIX-1117] PUSH scenarios (see the cfg header)
local function run_push(lanes, ux, uz)
    bm:repeat_callback(function()
        local now = bm:time_elapsed_ms()
        for i, lane in ipairs(lanes) do
            local ok, line = pcall(function()
                local u, t = lane.flyer.unit, lane.target.unit
                local p, q = u:position(), t:position()
                return fmt("P %d %d %.2f %.2f %.2f %.2f %s %s %s", now, i, q:get_x(), q:get_z(),
                    p:get_x(), p:get_z(), tostring(t:is_in_melee()), tostring(u:is_in_melee()),
                    tostring(u:is_currently_flying()))
            end)
            hp_line(ok and line or fmt("PFAIL %d %d %s", now, i, tostring(line)))
        end
    end, 100, "ld_air_dive_autotest_push")
    local function attack(n)
        for i, lane in ipairs(lanes) do
            local ok, err = pcall(function()
                lane.flyer.uc:attack_unit(lane.target.unit, true, true)
            end)
            status(fmt("push attack %d #%d ok=%s melee=%s flying=%s target_melee=%s %s", i, n, tostring(ok),
                tostring(lane.flyer.unit:is_in_melee()), tostring(lane.flyer.unit:is_currently_flying()),
                tostring(lane.target.unit:is_in_melee()), ok and "" or tostring(err)))
        end
    end
    if cfg.scenario == "assist" then
        bm:callback(function()
            for i, lane in ipairs(lanes) do
                local ok, err = pcall(function()
                    lane.ally.uc:attack_unit(lane.target.unit, true, true)
                    lane.target.uc:attack_unit(lane.ally.unit, true, true)
                end)
                status(fmt("push ally %d engage ok=%s %s", i, tostring(ok), ok and "" or tostring(err)))
            end
        end, cfg.settle_ms)
    end
    -- the flyer's first attack, then recharge_count more; with recharge_away_ms > 0 each re-charge is
    -- preceded by a move-away order (away_m back, at a run) that many ms earlier: the cycle charge
    local t1 = cfg.settle_ms + (cfg.scenario == "assist" and cfg.assist_ms or 0)
    bm:callback(function() attack(1) end, t1)
    for k = 1, cfg.recharge_count do
        local tk = t1 + cfg.recharge_ms + (k - 1) * cfg.recharge_gap_ms
        if cfg.recharge_away_ms > 0 then
            bm:callback(function()
                for i, lane in ipairs(lanes) do
                    local ok, err = pcall(function()
                        local p = lane.flyer.unit:position()
                        lane.flyer.uc:goto_location(v(p:get_x() - ux * cfg.away_m, p:get_z() - uz * cfg.away_m), true)
                    end)
                    status(fmt("push away %d #%d ok=%s %s", i, k, tostring(ok), ok and "" or tostring(err)))
                end
            end, tk - cfg.recharge_away_ms)
        end
        bm:callback(function() attack(k + 1) end, tk)
    end
    bm:callback(function()
        bm:remove_callback("ld_air_dive_autotest_push")
        bm:remove_callback("ld_air_dive_autotest_hp")
        hp_line(nil)
        status("DONE")
    end, cfg.settle_ms + cfg.push_ms)
end

-- [AIR-DIVE-TAKEOFF-W1] CYCLE scenario (see the cfg header)
local function run_cycle(lanes, ux, uz)
    local t_end = cfg.engage_ms + cfg.fight_ms
    bm:repeat_callback(function()
        local now = bm:time_elapsed_ms()
        for i, lane in ipairs(lanes) do
            local ok, line = pcall(function()
                local u, t = lane.flyer.unit, lane.target.unit
                return fmt("F %d %d %.5f %d %.5f %d %s %s", now, i, u:unary_hitpoints(),
                    u:number_of_men_alive(), t:unary_hitpoints(), t:number_of_men_alive(),
                    tostring(u:is_currently_flying()), tostring(u:is_in_melee()))
            end)
            hp_line(ok and line or fmt("FFAIL %d %d %s", now, i, tostring(line)))
        end
    end, 100, "ld_air_dive_autotest_cycle")
    local function attack(n)
        for i, lane in ipairs(lanes) do
            local ok, err = pcall(function()
                lane.flyer.uc:attack_unit(lane.target.unit, true, true)
                if n == 1 then lane.target.uc:attack_unit(lane.flyer.unit, true, true) end
            end)
            status(fmt("cycle attack %d #%d ok=%s %s", i, n, tostring(ok), ok and "" or tostring(err)))
        end
    end
    local function away(n)
        for i, lane in ipairs(lanes) do
            local ok, err = pcall(function()
                local p = lane.flyer.unit:position()
                lane.flyer.uc:goto_location(v(p:get_x() - ux * cfg.away_m, p:get_z() - uz * cfg.away_m), true)
            end)
            status(fmt("cycle away %d #%d ok=%s %s", i, n, tostring(ok), ok and "" or tostring(err)))
        end
    end
    local t, n = cfg.engage_ms, 1
    bm:callback(function() attack(1) end, t)
    if cfg.cycle_away_ms >= 0 then
        while true do
            local ta = t + cfg.cycle_away_ms
            local tb = ta + cfg.cycle_back_ms
            if tb >= t_end then break end
            local k = n
            bm:callback(function() away(k) end, ta)
            bm:callback(function() attack(k + 1) end, tb)
            t, n = tb, n + 1
        end
    end
    bm:callback(function()
        bm:remove_callback("ld_air_dive_autotest_cycle")
        bm:remove_callback("ld_air_dive_autotest_hp")
        hp_line(nil)
        status("DONE")
    end, t_end)
end

local function run()
    -- script control of everything: nothing moves unless ordered
    local controlled = 0
    each_unit(function(_, unit)
        local s = script_unit:new(unit)
        if s then s:take_control(); s:halt(); controlled = controlled + 1 end
    end)

    local lanes = {}
    for i = 1, cfg.lanes do
        local flyer, fa = find_sunit("flyer_" .. i)
        local target, ta = find_sunit("target_" .. i)
        if not flyer or not target then
            status(fmt("FAIL lane %d missing flyer=%s target=%s", i,
                tostring(flyer ~= nil), tostring(target ~= nil)))
            return
        end
        if fa == ta then
            status(fmt("FAIL lane %d flyer and target in the same alliance %d", i, fa))
            return
        end
        lanes[i] = { flyer = flyer, target = target }
        if cfg.scenario == "assist" then          -- [FLYER-FIX-1117] the flyer side's infantry
            local ally, aa = find_sunit("ally_" .. i)
            if not ally or aa ~= fa then
                status(fmt("FAIL lane %d ally missing or not on the flyer's side (%s)", i, tostring(aa)))
                return
            end
            lanes[i].ally = ally
        end
    end

    -- axis: from the flyers' side to the targets' side, through the middle
    local fx, fz, tx, tz = 0, 0, 0, 0
    for i = 1, #lanes do
        local fp, tp = lanes[i].flyer.unit:position(), lanes[i].target.unit:position()
        fx, fz = fx + fp:get_x(), fz + fp:get_z()
        tx, tz = tx + tp:get_x(), tz + tp:get_z()
    end
    local n = #lanes
    fx, fz, tx, tz = fx / n, fz / n, tx / n, tz / n
    local cx, cz = (fx + tx) / 2, (fz + tz) / 2
    local ux, uz = tx - fx, tz - fz
    local norm = math.sqrt(ux * ux + uz * uz)
    if norm < 1 then ux, uz, norm = 0, 1, 1 end
    ux, uz = ux / norm, uz / norm
    -- [AIR-DIVE-GRIFFON] a fixed lane frame: the deployment-derived centre and
    -- axis move with the army composition, the measured lane terrain does not
    if cfg.centre_x and cfg.centre_z and cfg.axis_x and cfg.axis_z then
        cx, cz = cfg.centre_x, cfg.centre_z
        local an = math.sqrt(cfg.axis_x ^ 2 + cfg.axis_z ^ 2)
        ux, uz = cfg.axis_x / an, cfg.axis_z / an
    end
    local px, pz = uz, -ux                      -- perpendicular, along the lanes
    local face_target = math.deg(math.atan2(ux, uz))
    local face_flyer = math.deg(math.atan2(-ux, -uz))
    status(fmt("layout controlled=%d centre=%.1f,%.1f axis=%.3f,%.3f armies_apart=%.1f",
        controlled, cx, cz, ux, uz, norm))

    for i, lane in ipairs(lanes) do
        -- [AIR-DIVE-GRIFFON] offset shifts the whole lane block along the lanes
        local off = cfg.lane_off[i] or (cfg.offset + (i - (n + 1) / 2) * cfg.spacing)
        local lx, lz = cx + px * off, cz + pz * off
        local t_x, t_z = lx + ux * cfg.dist / 2, lz + uz * cfg.dist / 2
        local f_x, f_z = lx - ux * cfg.dist / 2, lz - uz * cfg.dist / 2
        lane.target.uc:teleport_to_location(v(t_x, t_z), face_flyer, 40)
        lane.flyer.uc:teleport_to_location(v(f_x, f_z), face_target, 20)
        if lane.ally then   -- [FLYER-FIX-1117] 30 m in front of the target, facing it
            lane.ally.uc:teleport_to_location(v(t_x - ux * 30, t_z - uz * 30), face_target, 40)
        end
        status(fmt("lane %d flyer=%s uid=%s at=%.1f,%.1f target=%s uid=%s at=%.1f,%.1f",
            i, tostring(lane.flyer.unit:type()), tostring(lane.flyer.unit:unique_ui_id()),
            f_x, f_z, tostring(lane.target.unit:type()),
            tostring(lane.target.unit:unique_ui_id()), t_x, t_z))
    end

    -- A missile flyer under attack_unit shoots or kites instead of closing:
    -- run 2's skycutter (bows) never came within 80 m of its target. CA turns
    -- these behaviours off before scripted attacks (quest battle scripts:
    -- change_behaviour_active("skirmish"/"fire_at_will", false)), plus melee mode
    -- (script_unit:set_melee_mode -> uc:melee). Each call is reported.
    for i, lane in ipairs(lanes) do
        local uc = lane.flyer.uc
        local r1 = pcall(function() uc:change_behaviour_active("skirmish", false, false) end)
        local r2 = pcall(function() uc:change_behaviour_active("fire_at_will", false, false) end)
        local r3 = pcall(function() uc:melee(true) end)
        status(fmt("lane %d melee_setup skirmish_off=%s fire_at_will_off=%s melee_on=%s",
            i, tostring(r1), tostring(r2), tostring(r3)))
    end

    -- [AIR-DIVE-W14] every 100 ms: each target's hit points (header step 5)
    local hp_buf = {}
    local function hp_flush()
        if #hp_buf == 0 then return end
        local f = io.open(HP_FILE, "a")
        if f then f:write(table.concat(hp_buf, "\n") .. "\n"); f:close() end
        hp_buf = {}
    end
    -- [AIR-DIVE-W15] the engage sampler writes through the same buffer;
    -- nil flushes
    hp_line = function(line)
        if line == nil then hp_flush() else hp_buf[#hp_buf + 1] = line end
    end
    local hp_ticks = 0
    bm:repeat_callback(function()
        hp_ticks = hp_ticks + 1
        local now = bm:time_elapsed_ms()
        for i, lane in ipairs(lanes) do
            local ok, hp, men = pcall(function()
                return lane.target.unit:unary_hitpoints(),
                    lane.target.unit:number_of_men_alive()
            end)
            if ok and type(hp) == "number" then
                hp_buf[#hp_buf + 1] = fmt("H %d %d %.5f %d", now, i, hp, men or -1)
            else
                hp_buf[#hp_buf + 1] = fmt("HFAIL %d %d %s", now, i, tostring(hp))
            end
        end
        if hp_ticks % 10 == 0 then hp_flush() end
    end, 100, "ld_air_dive_autotest_hp")

    -- every 2 s: where each ordered flyer is relative to its target (evidence
    -- for a lane that never closes; the recorder only writes inside 80 m)
    local ordered = {}
    bm:repeat_callback(function()
        for i, lane in ipairs(lanes) do
            if ordered[i] then
                pcall(function()
                    local p, q = lane.flyer.unit:position(), lane.target.unit:position()
                    local dx, dz = q:get_x() - p:get_x(), q:get_z() - p:get_z()
                    status(fmt("track %d dist=%.1f y=%.1f flying=%s moving=%s melee=%s",
                        i, math.sqrt(dx * dx + dz * dz), p:get_y(),
                        tostring(lane.flyer.unit:is_currently_flying()),
                        tostring(lane.flyer.unit:is_moving()),
                        tostring(lane.flyer.unit:is_in_melee())))
                end)
            end
        end
    end, 2000, "ld_air_dive_autotest_track")

    -- [AIR-DIVE-TAKEOFF-W1] melee_off_<i>: the target stops attacking
    for i, lane in ipairs(lanes) do
        local at = cfg.melee_off[i]
        if at then
            bm:callback(function()
                local ok, err = pcall(function()
                    lane.target.unit:set_stat_attribute("melee_disabled", true)
                end)
                status(fmt("melee_off %d ok=%s %s", i, tostring(ok), ok and "" or tostring(err)))
            end, math.max(at, 1))
        end
        -- retreat_<i>: the target withdraws (away from its flyer, at a run);
        -- melee_disabled does not stop a unit already fighting (measured:
        -- hits on the flyer kept landing for 5 s after it, cP1/cP2)
        local rt = cfg.retreat[i]
        if rt then
            bm:callback(function()
                local ok, err = pcall(function()
                    local tp, fp = lane.target.unit:position(), lane.flyer.unit:position()
                    local dx, dz = tp:get_x() - fp:get_x(), tp:get_z() - fp:get_z()
                    local d = math.max(math.sqrt(dx * dx + dz * dz), 0.1)
                    lane.target.uc:goto_location(v(tp:get_x() + dx / d * 80, tp:get_z() + dz / d * 80), true)
                end)
                status(fmt("retreat %d ok=%s %s", i, tostring(ok), ok and "" or tostring(err)))
            end, math.max(rt, 1))
        end
    end
    -- [FLYER-FIX-1117] the camera on one lane, from the side
    local cl = lanes[cfg.cam_lane]
    if cl then
        bm:repeat_callback(function()
            pcall(function()
                local q = (cfg.cam_flyer > 0 and cl.flyer or cl.target).unit:position()
                bm:camera():move_to(v(q:get_x() + px * cfg.cam_dist - ux * 10, q:get_y() + cfg.cam_up,
                    q:get_z() + pz * cfg.cam_dist - uz * 10), v(q:get_x(), q:get_y() + 2, q:get_z()), 0, false, 0)
            end)
        end, cfg.cam_every_ms, "ld_air_dive_autotest_cam")
        status(fmt("camera on lane %d", cfg.cam_lane))
    end
    if cfg.scenario == "cycle" then
        run_cycle(lanes, ux, uz)
        return
    end
    if cfg.scenario == "recharge" or cfg.scenario == "assist" then
        run_push(lanes, ux, uz)
        return
    end
    if cfg.scenario == "engage" then
        run_engage(lanes, ux, uz)
        return
    end
    for i, lane in ipairs(lanes) do
        local at = cfg.settle_ms + (i - 1) * cfg.stagger_ms
        bm:callback(function()
            ordered[i] = true
            local ok, err = pcall(function()
                lane.flyer.uc:attack_unit(lane.target.unit, true, true)
            end)
            if ok then
                local p = lane.flyer.unit:position()
                local q = lane.target.unit:position()
                local dx, dz = q:get_x() - p:get_x(), q:get_z() - p:get_z()
                status(fmt("charge %d ordered uid=%s dist=%.1f", i,
                    tostring(lane.flyer.unit:unique_ui_id()), math.sqrt(dx * dx + dz * dz)))
            else
                status(fmt("FAIL charge %d order: %s", i, tostring(err)))
            end
        end, at)
    end
    local done_at = cfg.settle_ms + (n - 1) * cfg.stagger_ms + cfg.tail_ms
    bm:callback(function()
        bm:remove_callback("ld_air_dive_autotest_track")
        bm:remove_callback("ld_air_dive_autotest_hp")
        hp_flush()
        status("DONE")
    end, done_at)
end

-- ----------------------------------------------------------------- phases
for _, name in ipairs({ "Deployment", "VictoryCountdown", "Complete" }) do
    bm:register_phase_change_callback(name, function()
        phase = name
        status("phase " .. name)
    end)
end
bm:register_phase_change_callback("Deployed", function()
    phase = "Deployed"
    status("phase Deployed")
    local ok, err = pcall(run)
    if not ok then status("FAIL run: " .. tostring(err)) end
end)
bm:repeat_real_callback(function()
    local ok, err = pcall(clicker)
    if not ok then status("ERROR clicker: " .. tostring(err)) end
end, 1000, CLICKER)
