"""TEST-ONLY (AIR-DIVE-BRACE-W1): patch the scratch copy of the air-dive autotest harness
(copied from air-dive-continuous-w1 8b2d96173, the checkout with --targets; main's copy lost --targets).
  1. the targets get the same CA quest-battle setup as the flyers (skirmish off, fire at will off, melee on),
     each call reported; every target's position is logged every 0.5 s (TT lines) so a retreat shows
  2. --map / --catchment / --environment pick the battle map (defaults: the old ult_plains_infield_a)
  3. --scenario survey: the targets are teleported over a grid around the lane frame and each point's
     ground height and placed position are logged (S lines) -- the map flatness probe
Every replacement must apply exactly once."""
from pathlib import Path

H = Path(__file__).resolve().parent / "harness"


def edit(name, reps):
    p = H / name
    t = p.read_text("utf-8")
    for a, b in reps:
        assert t.count(a) == 1, f"{name}: {t.count(a)} x {a[:70]!r}"
        t = t.replace(a, b)
    p.write_text(t, "utf-8", newline="\n")
    print("patched", name)


edit("air_dive_autotest.py", [
    ("""_ld_sys.path.insert(0, _ld_os.path.dirname(
    _ld_os.path.dirname(_ld_os.path.abspath(__file__))))""",
     """# [AIR-DIVE-BRACE-W1 scratch copy] the tools of the checkout this harness came from
_ld_sys.path.insert(0, r"D:\\Projects\\.worktrees\\lore_disaster\\air-dive-continuous-w1\\mod\\tools")"""),
    ("""            f"\\t\\t<catchment_area>{CATCHMENT}</catchment_area>\\n"
            "\\t</battle_map_definition>\\n</battle>\\n")""",
     """            + (f"\\t\\t<catchment_area>{CATCHMENT}</catchment_area>\\n" if CATCHMENT else "")
            + "\\t</battle_map_definition>\\n</battle>\\n")"""),
    ("""    ap.add_argument("--scenario", choices=("charge", "engage", "move"), default="charge",""",
     """    ap.add_argument("--map", default=None, help="[BRACE-W1] terrain/battles/<map>/ (default MAP_NAME)")
    ap.add_argument("--catchment", default=None, help="[BRACE-W1] catchment ('-' = none)")
    ap.add_argument("--environment", default=None, help="[BRACE-W1] weather environment group key")
    ap.add_argument("--scenario", choices=("charge", "engage", "move", "survey"), default="charge","""),
    ("""    args = ap.parse_args(argv)
    if args.dist is None:""",
     """    args = ap.parse_args(argv)
    global MAP_NAME, CATCHMENT, ENVIRONMENT
    if args.map:
        MAP_NAME = f"terrain/battles/{args.map}/"
    if args.catchment:
        CATCHMENT = "" if args.catchment == "-" else args.catchment
    if args.environment:
        ENVIRONMENT = args.environment
    if args.dist is None:"""),
    ("""            + (f"scenario=move\\nmove_m={MOVE_M}\\nturn_m={TURN_M}\\nturn_ms={TURN_MS}\\n"
               if args.scenario == "move" else "")""",
     """            + (f"scenario=move\\nmove_m={MOVE_M}\\nturn_m={TURN_M}\\nturn_ms={TURN_MS}\\n"
               if args.scenario == "move" else "")
            + ("scenario=survey\\n" if args.scenario == "survey" else "")"""),
])

# the f-string join above needs the closing piece of the old line kept: check the result parses
import ast
ast.parse((H / "air_dive_autotest.py").read_text("utf-8"))

edit("air_dive_autotest.lua", [
    ("""        status(fmt("lane %d melee_setup skirmish_off=%s fire_at_will_off=%s melee_on=%s",
            i, tostring(r1), tostring(r2), tostring(r3)))
    end
""", """        status(fmt("lane %d melee_setup skirmish_off=%s fire_at_will_off=%s melee_on=%s",
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
"""),
    ("""    if cfg.scenario == "move" then
        run_move(lanes, ux, uz, px, pz)
        return
    end
""", """    if cfg.scenario == "move" then
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
"""),
])
