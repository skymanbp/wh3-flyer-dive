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
--      when the finish_deployment panel opens) until the Deployed phase.
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
-- [AIR-DIVE-CONTINUOUS-W1] MOVE scenario: an ordinary (non-charge) run order
-- away from the targets, then a 90-degree turn order (run_move below)
cfg.move_m, cfg.turn_m, cfg.turn_ms = 200, 120, 40000
for line in probe:lines() do
    local k, val = line:match("^%s*([%w_]+)%s*=%s*([%d%.%-]+)%s*$")
    if k and cfg[k] ~= nil then cfg[k] = tonumber(val) end
    local li = k and k:match("^lane_off_(%d+)$")
    if li then cfg.lane_off[tonumber(li)] = tonumber(val) end
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
    -- [AIR-DIVE-TAKEOFF-W1 2026-11-12, the same guard as that lane] no click
    -- before the game reports Deployment: a click during loading made every
    -- later click be ignored (their run eV2; here M_dragon 2026-11-12 15:42,
    -- "click ... n=1 phase=loading", then 600+ ignored clicks to the timeout)
    if phase ~= "Deployment" then return end
    local root = core:get_ui_root()
    for _, id in ipairs(CLICK_IDS) do
        local uic = bfs_find(root, id)
        if uic and uic:Visible() then
            uic:SetOpacity(255, true)
            uic:SimulateLClick()
            clicks = clicks + 1
            status(fmt("click %s n=%d phase=%s", id, clicks, phase))
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

-- [AIR-DIVE-CONTINUOUS-W1] every flyer, at settle_ms, is ordered to run
-- move_m straight away from its target (goto_location(position, move fast),
-- battle_unitcontroller.html); at turn_ms to run turn_m to its side (a
-- 90-degree turn). No attack order: this measures how a flyer stops and
-- turns on an ordinary move. "move <k> <lane> to=<x>,<z>" in the status.
local function run_move(lanes, ux, uz, px, pz)
    local function order(k, dx, dz)
        for i, lane in ipairs(lanes) do
            local ok, err = pcall(function()
                local p = lane.flyer.unit:position()
                local x, z = p:get_x() + dx, p:get_z() + dz
                lane.flyer.uc:goto_location(v(x, z), true)
                status(fmt("move %d %d to=%.1f,%.1f from=%.1f,%.1f flying=%s", k, i, x, z,
                    p:get_x(), p:get_z(), tostring(lane.flyer.unit:is_currently_flying())))
            end)
            if not ok then status(fmt("FAIL move %d %d order: %s", k, i, tostring(err))) end
        end
    end
    bm:callback(function() order(1, -ux * cfg.move_m, -uz * cfg.move_m) end, cfg.settle_ms)
    bm:callback(function() order(2, px * cfg.turn_m, pz * cfg.turn_m) end, cfg.turn_ms)
    bm:callback(function()
        bm:remove_callback("ld_air_dive_autotest_hp")
        hp_line(nil)
        status("DONE")
    end, cfg.turn_ms + cfg.tail_ms)
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
    -- [AIR-DIVE-BRACE-W1] the targets too: Free Company Militia are a skirmish unit and backed off
    -- before contact (user, 2026-11-14). Same CA quest-battle calls, each reported.
    for i, lane in ipairs(lanes) do
        local uc = lane.target.uc
        local r1, e1 = pcall(function() uc:change_behaviour_active("skirmish", false, false) end)
        local r2, e2 = pcall(function() uc:change_behaviour_active("fire_at_will", false, false) end)
        local r3, e3 = pcall(function() uc:melee(true) end)
        status(fmt("lane %d target_setup skirmish_off=%s fire_at_will_off=%s melee_on=%s %s",
            i, tostring(r1), tostring(r2), tostring(r3),
            (r1 and r2 and r3) and "" or (tostring(e1) .. " " .. tostring(e2) .. " " .. tostring(e3))))
    end
    -- every 0.5 s each target's position (TT <ms> <lane> <x> <z> <y> <moving>): a retreat before contact shows
    bm:repeat_callback(function()
        local now = bm:time_elapsed_ms()
        for i, lane in ipairs(lanes) do
            pcall(function()
                local q = lane.target.unit:position()
                status(fmt("TT %d %d %.2f %.2f %.2f %s", now, i, q:get_x(), q:get_z(), q:get_y(),
                    tostring(lane.target.unit:is_moving())))
            end)
        end
    end, 500, "ld_air_dive_autotest_ttrack")

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

    if cfg.scenario == "engage" then
        run_engage(lanes, ux, uz)
        return
    end
    if cfg.scenario == "move" then
        run_move(lanes, ux, uz, px, pz)
        return
    end
    if cfg.scenario == "survey" then
        -- [AIR-DIVE-BRACE-W1] flatness probe: the targets visit a grid around the lane frame (cx, cz;
        -- along the lanes px, pz; along the attack ux, uz); 0.4 s after each teleport its position is
        -- logged: S <across> <along> <want_x> <want_z> <x> <z> <y>
        local pts = {}
        for a = -150, 150, 50 do
            for b = -700, 700, 50 do pts[#pts + 1] = { b, a } end
        end
        local k = 0
        local function step()
            for i, lane in ipairs(lanes) do
                local p = pts[k + i]
                if p then
                    local wx, wz = cx + px * p[1] + ux * p[2], cz + pz * p[1] + uz * p[2]
                    pcall(function() lane.target.uc:teleport_to_location(v(wx, wz), face_flyer, 20) end)
                    bm:callback(function()
                        local ok, q = pcall(function() return lane.target.unit:position() end)
                        if ok and q then
                            status(fmt("S %d %d %.1f %.1f %.2f %.2f %.3f", p[1], p[2], wx, wz,
                                q:get_x(), q:get_z(), q:get_y()))
                        else
                            status(fmt("SFAIL %d %d", p[1], p[2]))
                        end
                    end, 400)
                end
            end
            k = k + #lanes
            if k < #pts then
                bm:callback(step, 600)
            else
                bm:callback(function() status("DONE") end, 1000)
            end
        end
        bm:callback(step, cfg.settle_ms)
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
