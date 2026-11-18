#!/usr/bin/env python3
"""Air dive charge -- fully automated in-game test. [AIR-DIVE-AUTOTEST 2026-11-10]

One command, no human: launches Warhammer III straight into a scripted land
battle (high-elf flyers vs empire swordsmen), lets each flyer charge its own
swordsmen from a fixed distance, quits the game and prints the per-charge
numbers the movement recorder measured, with a machine-readable verdict.

ROUTE (ARCHITECTURE A14.1e): the game's own ``game_startup_mode battle <xml>``
script command, the one CA documents inside terrain/xml_battle/
battle_map_test.xml ("the game will load directly into the battle, bypassing
the frontend"). No frontend clicking, no campaign. The command goes in the
argv script file (used_mods.txt, the WH3MM contract auto_test.py already
uses); ``--startup-via user_script`` puts it in
%APPDATA%/The Creative Assembly/Warhammer3/scripts/user.script.txt instead.
Both are restored/removed afterwards, whatever happens.

PACKS ENABLED: the test pack (``--test-pack``, default flyer_dive_takeoff.pack, the
deployed canary; it must carry script/battle/mod/flyer_dive_probe.lua, the
recorder) and a helper pack this script writes and deploys for the run only:
``flyer_dive_autotest.pack`` = the battle xml + the driver
``pipelines/air_dive_autotest.lua`` (presses "start battle", takes script
control of every unit, lays the lanes out, orders the charges, writes DONE).
The helper pack is deleted from data/ after the run unless --keep-helper.

VERDICT (stdout last line ``VERDICT {json}`` + verdict.json in --out-dir):
PASS only if the driver reached DONE with every charge ordered, the recorder
wrote a BATTLE for this run (bytes appended after launch), EVERY lane's
flyer has a touchdown anchor next to its own target, and the driver's
hit-point record covers each touchdown. An empty, partial or missing record
is FAIL, never PASS (CLAUDE.md "判决不得退化"). PASS says the measurement is
complete; whether a lane ploughed is the lane's own ``plough`` field.
Exit 0 PASS, 1 FAIL, 3 BLOCKED (game already running).

PLOUGH [AIR-DIVE-W14 2026-11-11]: a lane ploughs when its target loses at
least PLOUGH_HP_LOSS of its hit points (``unit:unary_hitpoints()``, sampled
every 100 ms by the driver into flyer_dive_autotest_hp.txt) within
PLOUGH_WINDOW_S after the touchdown. In the 11-11 run the first is_in_melee
came 2.6 s (star dragon) and 3.3 s (griffon knights) after touchdown, so a
loss inside 1.5 s is the landing's impact, not ordinary melee. The loss at
LATE_WINDOW_S is reported too. Depth, touchdown speed, travel and peak speed
come from unit:position(), "the centre position of the main squad of the
unit" (assembly_kit/documentation/script/script/battle/battle_unit.html); the
battle_unit interface has no per-soldier position (only
position_of_officer(), one model), so for a multi-model flyer (recorder
men > 1) these numbers are dropped (None), never reported: on 11-11 the
griffon knights' centre jumped (a 162 m/s "touchdown") while riders landed,
and "-0.55 m deep" was the squad's middle while the user watched them charge
into the enemy.

LANE TERRAIN [AIR-DIVE-GRIFFON 2026-11-11]: lanes are NOT equivalent, so
they are picked by measured ground. Over 93 single-model touchdowns (star
dragon, Karl Franz on his Deathclaw, a griffon prince) the slot-489 plough
fired 33/33 level with the target and 20/60 uphill. Why (phase 3, 77
touchdowns on 7 lanes): the plough fires only when the flyer touches down
far enough from the nearest enemy (>= 6.5 m: 19/19, 6.0-6.5: 11/15,
< 6.0: 0/43, griffon radius 2.4; the limit moved ~1 m closer with radius
1.2, not with IMPACT_POS). On rising ground the flyer is still 0.36-0.47 m
up 7 m out (level lanes <= 0.18) and lands 3.5-5.5 m away. The lanes are
laid out in a FIXED frame (LANE_FRAME) at LANE_OFFSETS: two level lanes,
one nearly level, one deliberate uphill lane. Each lane reports
``target_ground_rise_m`` and ``peak_mps_after_touchdown`` (~20 = the plough
ran, ~0 = the flyer stopped; single models only, a multi-model unit's
position() alternates between models). Compare variants lane by lane: W8/W9
compared the dragon on a level lane with the griffon knights on an uphill
one, and "the dragon ploughs, the griffon knights don't" was that.

ENGAGE [AIR-DIVE-W15 2026-11-11] (``--scenario engage``): ENGAGE_FLYERS
start ENGAGE_DIST from their targets and both sides are ordered to attack
each other, so the flyer is in melee and its target keeps fighting it. At
BREATH_MS the flyer is ordered to use its own breath (the first of its
non-passive abilities in the installed breath set, air_dive_rules) on its
target; at AWAY_MS to run AWAY_M back. Every 100 ms the driver writes
flying / moving / in-melee / distance / ``can_perform_special_ability``.
Judged per lane (judge_engage): in melee at the breath order, whether the
engine allowed it then (``can_breath_at_order``), whether it fired (the
ability went on cooldown 1.5-4 s later; target hp lost in 4 s also
reported), and after the move-away order the seconds to take-off, to leaving
melee and to BROKE_CONTACT_M farther from the target. PASS only says the
record is complete.

ENTITY READ [ENGINE-ENTITY-READ-W1 2026-11-11]: ``--entity-read`` also
builds and enables the TEST-ONLY per-soldier reader ld_entity_read.pack
(``build_entity_read_minimod.py``, memory read-only, never in a published pack)
and adds, per lane, the target's men knocked (Derpy's knock slots 143-197)
and per-man hit-point loss in the PLOUGH_WINDOW_S after touchdown
(``lane["entity"]``), plus the record's own checks (``result["entity_read"]``:
the per-man sum against ``unit:unary_hitpoints()``, the +0x324 cross-tab).
With the flag on, a missing, stopped or failed record is a FAIL reason.
[AIR-DIVE-W16 2026-11-12] The reader also records each man's (and mount's)
+0x1c8 speed and +0xab0 collision-attack load and the lead model's (or his
mount's) +0x710 / +0x70c flight mode: a charge lane adds ``entity_5s`` (the same window to
LATE_WINDOW_S) and ``flyer_read`` (the flyer's counter rise and peak speed
from FLYER_READ_PRE_S before touchdown to LATE_WINDOW_S after); an engage
lane adds ``flight_after_away`` (flight mode, load, speed every reader
tick from the move-away order on). ``--flyers a,b,c`` replaces the lane
list of either scenario (the lane count follows it).

usage: python -P tools/pipelines/air_dive_autotest.py
           [--scenario charge|engage]
           [--test-pack flyer_dive_takeoff.pack] [--dist 250] [--spacing 250]
           [--lane-offsets a,b,c,d | spacing] [--offset 0]
           [--stagger 20] [--tail 40] [--timeout 900]
           [--startup-via argv|user_script] [--out-dir DIR] [--keep-helper]
       python -P tools/pipelines/air_dive_autotest.py --judge-only DIR
           (re-judge a finished run's saved status + probe slice + hp.txt)
/ 俯冲冲锋全自动实机测试：直接进脚本战斗、逐个冲锋、退出、出报告与判决。
"""
import os as _boot_os, sys as _boot_sys
_boot_sys.path.insert(0, _boot_os.path.dirname(
    _boot_os.path.dirname(_boot_os.path.abspath(__file__))))
import rolepath  # noqa: F401  (role directories on sys.path)

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import air_dive_probe_report
import entity_read_report
from game_process import ensure_steam, game_error_dialog as error_dialog
# [AIR-DIVE-W12] only the game this driver launched is ever closed; resist_autotest reads these as ada.*
from game_process import OwnGame, ProcessProbeStalled, game_pids  # noqa: F401 -- because they are re-exported
import ctypes
import threading
KEEP_BEHIND = OwnGame.keep_behind
from packfile import PACK_TYPE_MOD, PackFile, write_pack_file

GAME_ROOT = Path(os.environ.get(
    "WH3_ROOT", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III"))
DATA_DIR = GAME_ROOT / "data"
USED_MODS = GAME_ROOT / "used_mods.txt"
USER_SCRIPT = (Path(os.environ.get("APPDATA", "")) / "The Creative Assembly"
               / "Warhammer3" / "scripts" / "user.script.txt")
CMD_FILE = GAME_ROOT / "flyer_dive_autotest_cmd.txt"
STATUS_FILE = GAME_ROOT / "flyer_dive_autotest_status.txt"
HP_FILE = GAME_ROOT / "flyer_dive_autotest_hp.txt"   # [AIR-DIVE-W14]
PROBE_LOG = GAME_ROOT / "flyer_dive_probe.txt"
HELPER_PACK = "flyer_dive_autotest.pack"
PROBE_PACK_PATH = "script/battle/mod/flyer_dive_probe.lua"
DRIVER_SOURCE = Path(__file__).resolve().parent / "air_dive_autotest.lua"
DRIVER_PACK_PATH = "script/battle/mod/flyer_dive_autotest.lua"  # Lua: forward slashes
XML_PACK_PATH = "terrain\\xml_battle\\flyer_dive_autotest.xml"   # VFS: backslashes
# [ENGINE-ENTITY-READ-W1] the optional per-soldier reader (module docstring)
ENTITY_PACK = "ld_entity_read.pack"
ENTITY_LOG = GAME_ROOT / "ld_entity_read.txt"
# where a run's report goes when --out-dir is not given; FLYER_AUTOTEST_RUNS_DIR overrides it
RUNS_DIR = Path(os.environ.get("FLYER_AUTOTEST_RUNS_DIR",
                               r"D:\Projects\.worktrees\wh3-flyer-dive\autotest_runs"))

# The lanes: one flyer per lane, each charging its own swordsmen.
FLYERS = (
    "wh2_main_hef_mon_star_dragon",
    "wh2_dlc15_hef_inf_mistwalkers_griffon_knights_0",
    "wh3_dlc27_hef_veh_skycutter_bows",
    # [AIR-DIVE-GRIFFON] the deliberate uphill lane (LANE_OFFSETS[3])
    "wh2_main_hef_mon_star_dragon",
)
TARGET = "wh_main_emp_inf_swordsmen"
# [AIR-DIVE-W15 2026-11-11] ENGAGE scenario (--scenario engage, module
# docstring ENGAGE): flyers that start in melee. Two dragons whose breath CA
# blocks in melee and while grounded, the multi-model griffon knights and a
# great eagle (no breath; take-off only).
ENGAGE_FLYERS = (
    "wh2_main_hef_mon_star_dragon",
    "wh2_main_hef_mon_sun_dragon",
    "wh2_dlc15_hef_inf_mistwalkers_griffon_knights_0",
    "wh2_main_hef_mon_great_eagle",
)
ENGAGE_DIST = 40.0         # start distance, m: they meet within seconds
ENGAGE_MS, BREATH_MS, AWAY_MS = 3000, 15000, 25000
AWAY_M = 150.0             # the move-away order goes this far back
BREATH_WINDOW_S = 4.0      # cooldown / target hp read this long after the order
BROKE_CONTACT_M = 30.0     # flyer this much farther from its target than at the order
# Generals: an xml army is led by a lord (CA's sample gives each army one).
# Keys from docs/VANILLA_REFERENCE.md; they stay where they spawn, halted.
HEF_FACTION, HEF_GENERAL = "wh2_main_hef_eataine", "wh2_main_hef_cha_prince_0"
EMP_FACTION, EMP_GENERAL = "wh_main_emp_empire", "wh_main_emp_cha_general_0"
# names-table ids CA's battle_map_test.xml uses for its two generals
GENERAL_NAMES = ("2147360906", "2147359620")
# terrain/battles/ult_plains_infield_a/battle_locations_map.xml: catchment_01
# is in the land_normal list (flat Ulthuan plains, no trees on the lanes).
MAP_NAME = "terrain/battles/ult_plains_infield_a/"
CATCHMENT = "catchment_01"
# Without a <weather> block the first run crashed while the battle loaded
# (2026-11-10 18:14:06, READ 0x0 at Warhammer3.exe+0x18B45A7, "<empty_file_name>"
# next to terrain texture paths in the faulting object). CA's sample names
# Weather\battle\wh_ult_05.environment, which 9.0 no longer ships; the map's
# own environments.csv lists day_clear_02, shipped as this group in data.pack.
ENVIRONMENT = "weather\\battle\\wh_day_clear_02.environment_group"
MIN_FLYER_SAMPLES = 20
# [AIR-DIVE-W14] plough = target hit-point loss right after touchdown
# (module docstring PLOUGH). Unary fractions of the target's starting hp.
PLOUGH_WINDOW_S = 1.5
LATE_WINDOW_S = 5.0
PLOUGH_HP_LOSS = 0.01
HP_MATCH_S = 0.5        # an hp sample counts for an instant within this
FLYER_READ_PRE_S = 2.0  # [AIR-DIVE-W16] the flyer's counter is read from here before touchdown
# position-derived numbers dropped for a multi-model flyer (docstring PLOUGH)
CENTRE_ONLY_FIELDS = ("touchdown_speed_mps", "travel_after_touchdown_m",
                      "time_to_stop_s", "stopped", "depth_into_target_m",
                      "dist_to_target_centroid_m", "target_ground_rise_m",
                      "peak_mps_after_touchdown")
# [AIR-DIVE-GRIFFON 2026-11-11] The lanes are laid out in this FIXED frame
# (centre, charge axis): the frame the driver derived from the deployment moved
# with the army composition (centre 7.4,-10.6 / -3.8,-4.6 / 5.4,-10.7 for three
# lane sets), so a lane offset did not name the same ground twice. Offsets
# along the lanes, measured in this frame (module docstring LANE TERRAIN):
# -250 and -160 touch down level with the target (rise -0.11..0.01 m, plough
# 8/8 griffon-prince touchdowns), +160 nearly level (0.18..0.19, 2/3); +80 is
# the deliberate uphill test lane (0.47..0.80 m, 0/3).
LANE_FRAME = {"centre_x": -3.8, "centre_z": -4.6, "axis_x": 0.024, "axis_z": -1.0}
LANE_OFFSETS = (-250.0, -160.0, 160.0, 80.0)


# ------------------------------------------------------------------ pack
def resolve_lane_offsets(spec, n):
    """Lane positions along the lanes. ``spec`` None: LANE_OFFSETS when it has
    one entry per lane, else refuse (a lane set without measured ground must
    say so with 'spacing'); 'spacing': () so the driver uses spacing/offset;
    else a comma list of exactly ``n`` numbers."""
    if spec is None:
        if len(LANE_OFFSETS) != n:
            raise SystemExit(
                f"[air_dive_autotest] REFUSING: {n} lanes but LANE_OFFSETS has "
                f"{len(LANE_OFFSETS)}; pass --lane-offsets (measured ground) or "
                "--lane-offsets spacing")
        return LANE_OFFSETS
    if spec == "spacing":
        return ()
    vals = tuple(float(x) for x in spec.split(","))
    if len(vals) != n:
        raise SystemExit(f"[air_dive_autotest] REFUSING: --lane-offsets has "
                         f"{len(vals)} values for {n} lanes")
    return vals


def unit_xml(name, key, general_name=None):
    """One <unit> of CA's battle_map_test.xml format. [TEST-REPAIR-1113] also
    resist_autotest's (one home)."""
    gen = ""
    if general_name:
        gen = (f"\t\t\t\t<general>\n\t\t\t\t\t<name>{general_name}</name>\n"
               "\t\t\t\t\t<star_rating level=\"0\"/>\n\t\t\t\t</general>\n")
    return (f"\t\t\t<unit script_name=\"{name}\">\n"
            f"\t\t\t\t<unit_type type=\"{key}\"/>\n"
            "\t\t\t\t<unit_experience level=\"0\"/>\n" + gen +
            "\t\t\t</unit>\n")


def alliance_xml(idx, faction, units):
    """One <alliance> (one army, kill-or-rout victory) of that format."""
    return (f"\t<alliance id=\"{idx}\">\n\t\t<army>\n"
            f"\t\t\t<faction>{faction}</faction>\n" + "".join(units) +
            "\t\t</army>\n\t\t<victory_condition>\n"
            "\t\t\t<kill_or_rout_enemy></kill_or_rout_enemy>\n"
            "\t\t</victory_condition>\n\t</alliance>\n")


def battle_xml(flyers=FLYERS, target=TARGET, ally=None):
    """The battle definition, CA's battle_map_test.xml format (UTF-16).
    [FLYER-FIX-1117] ``ally``: one unit of that key per lane on the flyers' side (``ally_<i>``)."""
    unit, alliance = unit_xml, alliance_xml
    hef = [unit("general_hef", HEF_GENERAL, GENERAL_NAMES[0])]
    hef += [unit(f"flyer_{i}", k) for i, k in enumerate(flyers, 1)]
    if ally:
        hef += [unit(f"ally_{i}", ally) for i in range(1, len(flyers) + 1)]
    emp = [unit("general_emp", EMP_GENERAL, GENERAL_NAMES[1])]
    emp += [unit(f"target_{i}", target) for i in range(1, len(flyers) + 1)]
    text = ("<?xml version=\"1.0\"?>\n"
            "<!-- generated by tools/pipelines/air_dive_autotest.py -->\n"
            "<battle>\n" + alliance(0, HEF_FACTION, hef) +
            alliance(1, EMP_FACTION, emp) +
            "\t<battle_description>\n\t\t<time_of_day>day</time_of_day>\n"
            "\t\t<season>Summer</season>\n"
            "\t\t<precipitation_type>dry</precipitation_type>\n"
            "\t\t<timeout_winning_alliance_index>1</timeout_winning_alliance_index>\n"
            "\t</battle_description>\n"
            "\t<sea_surface_name>wind_level_1</sea_surface_name>\n"
            "\t<weather>\n\t\t<prevailing_wind x=\"1.00\" y=\"0.00\"/>\n"
            f"\t\t<environment_key>{ENVIRONMENT}</environment_key>\n"
            "\t</weather>\n"
            "\t<battle_map_definition>\n"
            f"\t\t<name>{MAP_NAME}</name>\n"
            f"\t\t<catchment_area>{CATCHMENT}</catchment_area>\n"
            "\t</battle_map_definition>\n</battle>\n")
    return text.replace("\n", "\r\n").encode("utf-16")   # BOM + LE, as CA's


def helper_entries(flyers=FLYERS, target=TARGET, ally=None):
    driver = DRIVER_SOURCE.read_bytes()
    if b"flyer_dive_autotest_cmd.txt" not in driver:
        raise SystemExit("[air_dive_autotest] REFUSING: the driver Lua does not "
                         "name its control file -- wrong source?")
    return [(XML_PACK_PATH, battle_xml(flyers, target, ally)), (DRIVER_PACK_PATH, driver)]


PUSH_SCENARIOS = ("recharge", "assist")
PUSH_WINDOW_S = 25.0    # [FLYER-FIX-1117] how long after the push order the target's travel is measured (a re-charge may take off and dive again)


def parse_push(text):
    """{lane: [(t_s, tx, tz, fx, fz, target_melee, flyer_melee, flying)]} from the P lines."""
    out = {}
    for raw in (text or "").splitlines():
        parts = raw.split()
        if len(parts) == 10 and parts[0] == "P":
            out.setdefault(int(parts[2]), []).append(
                (int(parts[1]) / 1000.0, float(parts[3]), float(parts[4]), float(parts[5]),
                 float(parts[6]), parts[7] == "true", parts[8] == "true", parts[9] == "true"))
    for rows in out.values():
        rows.sort()
    return out


def judge_push(status_lines, hp_text, lanes_expected, scenario):
    """[FLYER-FIX-1117] Per lane: the push order (scenario recharge: the second attack order, given while
    in melee; assist: the flyer's first attack order, its target already fighting the ally) and the
    target's centre travel along the charge axis (flyer start -> target start; + = pushed back) from that
    order to PUSH_WINDOW_S after it, plus the largest such travel. PASS only says the record is complete."""
    reasons, lanes_out = [], []
    rows = parse_push(hp_text)
    want_n = 2 if scenario == "recharge" else 1
    orders = {}
    for ln in status_lines:
        parts = ln.split()
        if len(parts) >= 5 and parts[1] == "push" and parts[2] == "attack":
            try:
                t_ms = int(parts[0])
            except ValueError:
                continue
            lane, n = int(parts[3]), int(parts[4].lstrip("#"))
            kv = dict(p.split("=", 1) for p in parts[5:] if "=" in p)
            if n == want_n:
                orders[lane] = (t_ms / 1000.0, kv)
    if not any(ln.split(" ", 1)[-1].startswith("DONE") for ln in status_lines):
        reasons.append("driver never reached DONE")
    for lane in range(1, lanes_expected + 1):
        r = rows.get(lane) or []
        o = orders.get(lane)
        if not r or o is None:
            reasons.append(f"lane {lane}: no position record or no push order #{want_n}")
            lanes_out.append({"lane": lane})
            continue
        t0, kv = o
        start = r[0]
        ax, az = start[1] - start[3], start[2] - start[4]
        n = (ax * ax + az * az) ** 0.5 or 1.0
        ax, az = ax / n, az / n
        before = [x for x in r if x[0] <= t0]
        win = [x for x in r if t0 <= x[0] <= t0 + PUSH_WINDOW_S]
        if not before or not win or win[-1][0] < t0 + PUSH_WINDOW_S - 0.5:
            reasons.append(f"lane {lane}: position record does not cover the push window")
            lanes_out.append({"lane": lane})
            continue
        b = before[-1]
        travel = [((x[1] - b[1]) * ax + (x[2] - b[2]) * az) for x in win]
        lanes_out.append({"lane": lane, "order_s": t0, "order_state": kv,
                          "target_in_melee_at_order": b[5], "flyer_in_melee_at_order": b[6],
                          "target_back_travel_m": round(travel[-1], 2),
                          "target_back_travel_max_m": round(max(travel), 2),
                          "flyer_flying_in_window_s": round(sum(0.1 for x in win if x[7]), 1)})
    return {"verdict": "FAIL" if reasons else "PASS", "reasons": reasons, "lanes": lanes_out}


def breath_keys():
    """[AIR-DIVE-W15] Every installed breath ability (air_dive_rules, the rule
    the build applies): the driver orders the lane flyer's own breath from it."""
    import air_dive_rules
    _kept, _removed, breath, _h = air_dive_rules.installed_breath_table(
        DATA_DIR / "db.pack", DATA_DIR / "local_en.pack")
    return sorted(breath)


def check_test_pack(name):
    """None if the test pack is deployed and carries the recorder, else why."""
    path = DATA_DIR / name
    if not path.is_file():
        return f"test pack {path} is not deployed"
    paths = {e.path.replace("\\", "/").lower() for e in PackFile.open(path).entries}
    if PROBE_PACK_PATH not in paths:
        return (f"test pack {name} has no {PROBE_PACK_PATH}: nothing would "
                "record the charges (build it with build_air_dive_minimod.py --probe)")
    return None


# --------------------------------------------------------------- process
# [AIR-DIVE-W12] process helpers moved to lib/game_process.py (imported above)


CRASH_DIR = (Path(os.environ.get("APPDATA", "")) / "The Creative Assembly"
             / "Warhammer3" / "crash_report")


def new_crash_dumps(since_epoch):
    if not CRASH_DIR.is_dir():
        return []
    return [p for p in CRASH_DIR.glob("*.mdmp") if p.stat().st_mtime >= since_epoch]


def crash_verdict(since_epoch):
    import crash_watch   # decodes the dump: code, faulting module+offset, C++ throws
    verdict, lines = crash_watch.postmortem(since_epoch)
    return verdict + " | " + " | ".join(lines)


def read_status():
    if not STATUS_FILE.is_file():
        return []
    return STATUS_FILE.read_text("utf-8", errors="replace").splitlines()


def has(lines, word):
    return any(ln.split(" ", 1)[-1].startswith(word) for ln in lines)


# ----------------------------------------------------------------- judge
def lane_uids(status_lines):
    """{lane: (flyer_uid, flyer_key, target_uid)} from the driver's lane lines."""
    out = {}
    for ln in status_lines:
        parts = ln.split()
        if len(parts) >= 8 and parts[1] == "lane" and parts[3].startswith("flyer="):
            kv = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
            uids = [p.split("=", 1)[1] for p in parts[3:] if p.startswith("uid=")]
            if len(uids) == 2:
                out[int(parts[2])] = (uids[0], kv.get("flyer"), uids[1])
    return out


def parse_hp(text):
    """{lane: [(t_s, unary_hp, men_alive)]} from the driver's hp file, plus
    the HFAIL lines (an engine call that failed)."""
    out, fails = {}, []
    for raw in (text or "").splitlines():
        parts = raw.split()
        if len(parts) == 5 and parts[0] == "H":
            out.setdefault(int(parts[2]), []).append(
                (int(parts[1]) / 1000.0, float(parts[3]), int(parts[4])))
        elif parts and parts[0] == "HFAIL":
            fails.append(raw)
    for rows in out.values():
        rows.sort()
    return out, fails


def hp_at(rows, t, before):
    """The hp sample nearest t on the given side (before: last <= t, else
    first >= t), within HP_MATCH_S; None if there is none."""
    if before:
        cand = [r for r in rows if r[0] <= t + 1e-6]
        r = cand[-1] if cand else None
    else:
        cand = [r for r in rows if r[0] >= t - 1e-6]
        r = cand[0] if cand else None
    if r is None or abs(r[0] - t) > HP_MATCH_S:
        return None
    return r


def plough_numbers(rows, t0):
    """Target hp loss after a touchdown at t0, or (None, why)."""
    h0 = hp_at(rows, t0, before=True)
    h1 = hp_at(rows, t0 + PLOUGH_WINDOW_S, before=False)
    h5 = hp_at(rows, t0 + LATE_WINDOW_S, before=False)
    if h0 is None or h1 is None or h5 is None:
        return None, (f"no target hit-point sample within {HP_MATCH_S}s of "
                      f"touchdown {t0}s, +{PLOUGH_WINDOW_S}s or +{LATE_WINDOW_S}s")
    loss1, loss5 = h0[1] - h1[1], h0[1] - h5[1]
    return {"target_hp_at_touchdown": round(h0[1], 4),
            "target_hp_loss_1_5s": round(loss1, 4),
            "target_hp_loss_5s": round(loss5, 4),
            "target_men_lost_1_5s": h0[2] - h1[2],
            "target_men_lost_5s": h0[2] - h5[2],
            "plough": loss1 >= PLOUGH_HP_LOSS}, None


def judge(status_lines, probe_text, hp_text, lanes_expected=len(FLYERS),
          entity_text=None):
    """Machine verdict dict. Any missing piece is a FAIL reason.
    ``entity_text``: the per-soldier reader's slice (None: not enabled)."""
    reasons, lanes_out = [], []
    ent = None
    if entity_text is not None:
        ebattles = entity_read_report.parse_text(entity_text)
        if not ebattles:
            reasons.append("entity reader: no BATTLE line in this run's slice")
        else:
            ent = ebattles[-1]
            for p in entity_read_report.problems(ent):
                reasons.append("entity reader: " + p)
    hp_rows, hp_fails = parse_hp(hp_text)
    if not hp_rows:
        reasons.append("the driver wrote no target hit-point record")
    for ln in hp_fails[:3]:
        reasons.append("driver hp call failed: " + ln)
    for word in ("harness_loaded", "phase Deployed", "DONE"):
        if not has(status_lines, word):
            reasons.append(f"driver never wrote '{word}'")
    for ln in status_lines:
        body = ln.split(" ", 1)[-1]
        if body.startswith("FAIL") or body.startswith("ERROR"):
            reasons.append("driver: " + body)
    for i in range(1, lanes_expected + 1):
        if not has(status_lines, f"charge {i} ordered"):
            reasons.append(f"charge {i} was never ordered")
    lanes = lane_uids(status_lines)
    if len(lanes) != lanes_expected:
        reasons.append(f"driver laid out {len(lanes)} lanes, expected {lanes_expected}")

    header = None
    rows, battle = [], None
    tmp_battles = air_dive_probe_report.parse_text(probe_text)
    if not tmp_battles:
        reasons.append("the recorder wrote no BATTLE line during this run")
    else:
        if len(tmp_battles) > 1:
            reasons.append(f"{len(tmp_battles)} BATTLE lines in this run's slice, expected 1")
        battle = tmp_battles[-1]
        header = battle["header"]
        for note in battle["notes"]:
            if note.startswith("ERROR") or note.startswith("STOP") or note.startswith("FAIL"):
                reasons.append("recorder: " + note)
        rows = air_dive_probe_report.report(battle)

    for i in sorted(lanes):
        f_uid, f_key, t_uid = lanes[i]
        lane = {"lane": i, "flyer": f_key, "flyer_uid": f_uid, "target_uid": t_uid}
        if battle is None:
            lane["status"] = "FAIL"
            lane["why"] = "no recorder battle"
            lanes_out.append(lane)
            continue
        n = len(battle["samples"].get(f_uid, []))
        lane["samples"] = n
        mine = [r for r in rows if r["uid"] == f_uid]
        touch = [r for r in mine if r["anchor"].startswith("touchdown")
                 and r["target"] == t_uid]
        lane["all_anchors"] = [{k: r[k] for k in ("anchor", "t", "target_key",
                                                  "speed_in", "travel_after_m")}
                               for r in mine]
        if f_uid not in battle["units"]:
            lane["status"], lane["why"] = "FAIL", "recorder never saw this flyer"
        elif n < MIN_FLYER_SAMPLES:
            lane["status"] = "FAIL"
            lane["why"] = f"only {n} samples near an enemy (< {MIN_FLYER_SAMPLES})"
        elif not touch:
            lane["status"] = "FAIL"
            lane["why"] = "no touchdown next to its own target"
        else:
            r = touch[0]
            multi = battle["units"][f_uid].get("men", 0) > 1
            lane.update({
                "status": "OK", "anchor": r["anchor"], "t": r["t"],
                "touchdown_speed_mps": r["speed_in"],
                "travel_after_touchdown_m": r["travel_after_m"],
                "time_to_stop_s": r["time_to_stop_s"], "stopped": r["stopped"],
                "depth_into_target_m": r["advance_into_target_m"],
                "target_tracked": r["target_tracked"],
                "dist_to_target_centroid_m": r["dist_to_target_centroid"],
                "in_melee_at_end": r["in_melee_at_end"],
                # [AIR-DIVE-GRIFFON] lane terrain and the jump-attack verdict
                # (module docstring LANE TERRAIN)
                "target_ground_rise_m": r["target_ground_rise_m"],
                "peak_mps_after_touchdown": r["peak_mps_after"],
                "touchdowns": len(touch)})
            # [AIR-DIVE-W14] the plough is the target's hit-point loss
            lane["flyer_men"] = battle["units"][f_uid].get("men", 0)
            melee = [a["t"] for a in lane["all_anchors"]
                     if a["anchor"] == "melee" and a["t"] >= r["t"]]
            lane["first_melee_after_touchdown_s"] = (
                round(melee[0] - r["t"], 2) if melee else None)
            if multi:
                for k in CENTRE_ONLY_FIELDS:
                    lane[k] = None
                lane["position_note"] = (
                    "multi-model flyer: unit:position() is the centre of the "
                    "main squad and the API has no per-soldier position, so "
                    "depth/speed/travel are not reported")
            if ent is not None:
                w = entity_read_report.window(ent, t_uid, r["t"], PLOUGH_WINDOW_S)
                lane["entity"] = w
                lane["entity_5s"] = entity_read_report.window(
                    ent, t_uid, r["t"], LATE_WINDOW_S)
                lane["flyer_read"] = entity_read_report.flyer_track(
                    ent, f_uid, r["t"] - FLYER_READ_PRE_S,
                    FLYER_READ_PRE_S + LATE_WINDOW_S)
                if w is None:
                    lane["status"] = "FAIL"
                    lane["why"] = "entity reader has no sample around touchdown"
            nums, why = plough_numbers(hp_rows.get(i, []), r["t"])
            if nums is None:
                lane["status"], lane["why"] = "FAIL", why
            else:
                lane.update(nums)
        if lane["status"] != "OK":
            reasons.append(f"lane {i} ({f_key}): {lane['why']}")
        lanes_out.append(lane)
    verdict = "PASS" if not reasons else "FAIL"
    out = {"verdict": verdict, "reasons": reasons, "recorder_header": header,
           "lanes": lanes_out}
    if ent is not None:
        out["entity_read"] = entity_read_report.summary(ent)
    return out


def print_table(result):
    print(result.get("recorder_header") or "(no recorder header)")
    hdr = ("lane", "flyer", "status", "plough", "hp lost 1.5s", "hp lost 5s",
           "men lost 1.5s/5s", "melee after s", "v_touch m/s", "depth m",
           "peak m/s")
    print("  " + " | ".join(hdr))

    def pct(v):
        return "-" if v is None else f"{v * 100:.1f}%"
    for ln in result["lanes"]:
        if ln["status"] == "OK":
            cells = (ln["lane"], ln["flyer"], "OK", ln["plough"],
                     pct(ln["target_hp_loss_1_5s"]), pct(ln["target_hp_loss_5s"]),
                     f'{ln["target_men_lost_1_5s"]}/{ln["target_men_lost_5s"]}',
                     ln["first_melee_after_touchdown_s"],
                     ln["touchdown_speed_mps"], ln["depth_into_target_m"],
                     ln["peak_mps_after_touchdown"])
        else:
            cells = (ln["lane"], ln["flyer"], "FAIL: " + ln.get("why", "?"),
                     "-", "-", "-", "-", "-", "-", "-", "-")
        print("  " + " | ".join(str(c) for c in cells))
    for r in result["reasons"]:
        print("  reason:", r)


# ---------------------------------------------------------- engage judge
def parse_engage(text):
    """{lane: [(t_s, flying, moving, in_melee, dist_m, can_breath)]} from the
    driver's E lines (can_breath None for a lane without a breath), plus the
    EFAIL lines."""
    out, fails = {}, []
    tf = {"true": True, "false": False, "-": None}
    for raw in (text or "").splitlines():
        p = raw.split()
        if len(p) == 8 and p[0] == "E":
            out.setdefault(int(p[2]), []).append(
                (int(p[1]) / 1000.0, tf[p[3]], tf[p[4]], tf[p[5]], float(p[6]), tf[p[7]]))
        elif p and p[0] == "EFAIL":
            fails.append(raw)
    for rows in out.values():
        rows.sort()
    return out, fails


def _status_events(status_lines, word, first_key=None):
    """{lane: (t_s, {k: v})} of the driver's first '<word> <lane> ...' line
    per lane (optionally only lines whose first field starts with
    ``first_key``), t from the line's battle-ms stamp."""
    out = {}
    for ln in status_lines:
        p = ln.split()
        if not (len(p) >= 4 and p[0].isdigit() and p[1] == word and p[2].isdigit()):
            continue
        if first_key and not p[3].startswith(first_key):
            continue
        kv = dict(x.split("=", 1) for x in p[3:] if "=" in x)
        out.setdefault(int(p[2]), (int(p[0]) / 1000.0, kv))
    return out


def judge_engage(status_lines, hp_text, lanes_expected, entity_text=None):
    """[AIR-DIVE-W15] Per lane: was the flyer in melee and able to breathe
    when its breath was ordered, did the breath fire (the ability went on
    cooldown: can_perform true at the order, false 1.5-4 s later), and how
    soon after the move-away order did the flyer take off, leave melee and
    get BROKE_CONTACT_M farther from its target. PASS only says the record
    is complete; the answers are lane fields."""
    reasons, lanes_out = [], []
    ent = None
    if entity_text is not None:
        ebattles = entity_read_report.parse_text(entity_text)
        if not ebattles:
            reasons.append("entity reader: no BATTLE line in this run's slice")
        else:
            ent = ebattles[-1]
            for p in entity_read_report.problems(ent):
                reasons.append("entity reader: " + p)
    rows, fails = parse_engage(hp_text)
    hp_rows, _hfails = parse_hp(hp_text)
    for ln in fails[:3]:
        reasons.append("driver engage sample failed: " + ln)
    for word in ("harness_loaded", "phase Deployed", "DONE"):
        if not has(status_lines, word):
            reasons.append(f"driver never wrote '{word}'")
    for ln in status_lines:
        body = ln.split(" ", 1)[-1]
        if body.startswith("FAIL") or body.startswith("ERROR"):
            reasons.append("driver: " + body)
    lanes = lane_uids(status_lines)
    abil = _status_events(status_lines, "abilities")
    breath_at = _status_events(status_lines, "breath", "key=")
    away = _status_events(status_lines, "away")
    for i in range(1, lanes_expected + 1):
        lane = {"lane": i, "flyer": lanes.get(i, (None, None, None))[1]}
        samples = rows.get(i, [])
        why = []
        if not samples:
            why.append("no engage samples")
        key = abil.get(i, (0, {}))[1].get("breath")
        lane["breath_key"] = None if key in (None, "nil") else key
        if lane["breath_key"]:
            if i not in breath_at:
                why.append("breath never ordered")
            else:
                tb, kv = breath_at[i]
                lane.update({"breath_t": tb, "melee_at_breath": kv.get("melee") == "true",
                             "flying_at_breath": kv.get("flying") == "true",
                             "can_breath_at_order": kv.get("can") == "true"})
                if not lane["melee_at_breath"]:
                    why.append("not in melee when the breath was ordered")
                h0 = hp_at(hp_rows.get(i, []), tb, before=True)
                h1 = hp_at(hp_rows.get(i, []), tb + BREATH_WINDOW_S, before=False)
                if h0 is None or h1 is None:
                    why.append("no target hp around the breath order")
                else:
                    lane["target_hp_loss_after_breath"] = round(h0[1] - h1[1], 4)
                after = [r[5] for r in samples if tb + 1.5 <= r[0] <= tb + BREATH_WINDOW_S]
                lane["can_breath_after"] = after[-1] if after else None
                lane["breath_fired"] = bool(lane["can_breath_at_order"] and after
                                            and not any(after))
        if i not in away:
            why.append("move-away never ordered")
        elif samples:
            ta = away[i][0]
            at = [r for r in samples if r[0] >= ta]
            if not at:
                why.append("no samples after the move-away order")
            else:
                d0 = at[0][4]
                lane.update({"away_t": ta, "melee_at_away": at[0][3],
                             "flying_at_away": at[0][1], "dist_at_away_m": d0})

                def first(pred):
                    return next((round(r[0] - ta, 1) for r in at if pred(r)), None)
                lane["takeoff_s"] = first(lambda r: r[1])
                lane["out_of_melee_s"] = first(lambda r: r[3] is False)
                lane["broke_contact_s"] = first(lambda r: r[4] >= d0 + BROKE_CONTACT_M)
                for secs in (5, 10):
                    near = [r for r in at if r[0] >= ta + secs]
                    lane[f"dist_after_{secs}s_m"] = near[0][4] if near else None
                if not lane["melee_at_away"]:
                    why.append("not in melee when the move-away was ordered")
                f_uid = lanes.get(i, (None,))[0]
                if ent is not None and f_uid is not None:
                    lane["flight_after_away"] = [
                        (round(tt - ta, 1), fm, hits, round(spd, 2), alive)
                        for tt, fm, hits, spd, alive
                        in entity_read_report.series(ent, f_uid)
                        if ta - 1.0 <= tt <= ta + 15.0]
        lane["status"] = "OK" if not why else "FAIL"
        if why:
            lane["why"] = "; ".join(why)
            reasons.append(f"lane {i} ({lane['flyer']}): {lane['why']}")
        lanes_out.append(lane)
    out = {"verdict": "PASS" if not reasons else "FAIL", "reasons": reasons,
           "scenario": "engage", "lanes": lanes_out}
    if ent is not None:
        out["entity_read"] = entity_read_report.summary(ent)
    return out


def print_engage(result):
    hdr = ("lane", "flyer", "status", "breath", "melee@order", "can@order",
           "fired", "hp lost 4s", "take-off s", "out of melee s",
           "broke contact s", "dist 0/5/10 s")
    print("  " + " | ".join(hdr))
    for ln in result["lanes"]:
        hp = ln.get("target_hp_loss_after_breath")
        cells = (ln["lane"], ln["flyer"],
                 ln["status"] + (": " + ln["why"] if ln.get("why") else ""),
                 ln.get("breath_key") or "-", ln.get("melee_at_breath", "-"),
                 ln.get("can_breath_at_order", "-"), ln.get("breath_fired", "-"),
                 "-" if hp is None else f"{hp * 100:.1f}%", ln.get("takeoff_s"),
                 ln.get("out_of_melee_s"), ln.get("broke_contact_s"),
                 f'{ln.get("dist_at_away_m")}/{ln.get("dist_after_5s_m")}/'
                 f'{ln.get("dist_after_10s_m")}')
        print("  " + " | ".join(str(c) for c in cells))
    for r in result["reasons"]:
        print("  reason:", r)


# ------------------------------------------------------------------- run
def lane_flyers(args):
    """[AIR-DIVE-W16] The lane list: ``--flyers`` or the scenario's own."""
    if getattr(args, "flyers", None):
        keys = tuple(k.strip() for k in args.flyers.split(",") if k.strip())
        if not keys:
            raise SystemExit("[air_dive_autotest] REFUSING: --flyers is empty")
        return keys
    return ENGAGE_FLYERS if args.scenario == "engage" else FLYERS


class Restore:
    """Puts used_mods.txt / user.script.txt / control file / helper pack back."""

    def __init__(self):
        self.saved = {}

    def save(self, path):
        self.saved[path] = path.read_bytes() if path.is_file() else None

    def restore(self):
        for path, data in self.saved.items():
            try:
                if data is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.write_bytes(data)
            except OSError as exc:
                print(f"[air_dive_autotest] WARNING could not restore {path}: {exc}")


def grab_window(own, path):
    """[FLYER-FIX-1117] Save the GAME window only (PrintWindow, PW_RENDERFULLCONTENT), never the screen: other
    windows on top of it (the user's own programs) must not end up in a test record. False: no window."""
    import ctypes
    import ctypes.wintypes as wt
    from PIL import Image
    wins = own._own_windows()
    if not wins:
        return False
    hwnd = wins[0]
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return False
    hdc = user32.GetDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    try:
        user32.PrintWindow(hwnd, mdc, 3)          # PW_CLIENTONLY | PW_RENDERFULLCONTENT
        buf = ctypes.create_string_buffer(w * h * 4)

        class BIH(ctypes.Structure):
            _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                        ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                        ("biClrImportant", wt.DWORD)]
        bih = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
        Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(path, quality=80)
        return True
    finally:
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(hwnd, hdc)


# [FLYER-FIX-1117] the Workshop memreader Plus (the test pack's declared prerequisite) for a run without
# the entity reader, which carried its own copy: --memreader
MEMREADER_DIR = Path(os.environ.get("MEMREADER_DIR",
                                    r"D:\SteamLibrary\steamapps\workshop\content\1142710\3811098873"))


def write_startup(via, test_pack, restore, extra_packs=(), memreader=False, before_packs=()):
    """[d3-1118] ``before_packs`` are listed in used_mods.txt ahead of the test pack, ``extra_packs``
    after the helper pack, in the order given (the pack-order experiment needs both sides)."""
    mod_lines = [f'mod "{p}";' for p in before_packs]
    mod_lines += [f'mod "{test_pack}";', f'mod "{HELPER_PACK}";']
    mod_lines += [f'mod "{p}";' for p in extra_packs]
    if memreader:
        if not (MEMREADER_DIR / "memreader_plus.pack").is_file():
            raise SystemExit(f"[air_dive_autotest] REFUSING: no memreader_plus.pack in {MEMREADER_DIR}")
        mod_lines += [f'add_working_directory "{MEMREADER_DIR}";', 'mod "memreader_plus.pack";']
    startup = f"game_startup_mode battle {XML_PACK_PATH};"
    restore.save(USED_MODS)
    if via == "argv":
        USED_MODS.write_text("\n".join(mod_lines + [startup]) + "\n", encoding="utf-8")
    else:
        restore.save(USER_SCRIPT)
        USED_MODS.write_text("\n".join(mod_lines) + "\n", encoding="utf-8")
        USER_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
        USER_SCRIPT.write_text(startup + "\n", encoding="utf-8")


def run(args):
    try:
        running = game_pids()
    except ProcessProbeStalled as exc:
        return {"verdict": "BLOCKED", "reasons": [
            f"cannot tell whether Warhammer3.exe is running ({exc}); "
            "not launching"], "lanes": []}
    if running:
        return {"verdict": "BLOCKED", "reasons": [
            "Warhammer3.exe is already running (the user may be playing); "
            "not launching"], "lanes": []}
    problem = check_test_pack(args.test_pack)
    if problem:
        return {"verdict": "FAIL", "reasons": [problem], "lanes": []}
    steam = ensure_steam()
    if steam:
        return {"verdict": "FAIL", "reasons": ["steam: " + steam], "lanes": []}

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    restore = Restore()
    helper = DATA_DIR / HELPER_PACK
    restore.save(helper)
    restore.save(CMD_FILE)
    # [AIR-DIVE-W14] HP_FILE is NOT restored: restore() runs before the read
    # below and would delete it (first W14 run: hp record lost that way)
    probe_offset = PROBE_LOG.stat().st_size if PROBE_LOG.is_file() else 0
    entity_offset = ENTITY_LOG.stat().st_size if ENTITY_LOG.is_file() else 0
    reasons, timeline = [], []
    t0 = time.time()

    def note(msg):
        stamp = f"{time.time() - t0:7.1f}s"
        timeline.append(f"{stamp} {msg}")
        print(f"[air_dive_autotest] {stamp} {msg}", flush=True)

    flyers = lane_flyers(args)
    lane_offsets = resolve_lane_offsets(args.lane_offsets, len(flyers))
    own = None
    try:
        write_pack_file(str(helper), helper_entries(flyers, args.target, args.ally), PACK_TYPE_MOD)
        if STATUS_FILE.exists():
            STATUS_FILE.unlink()
        if HP_FILE.exists():
            HP_FILE.unlink()
        CMD_FILE.write_text(
            f"dist={args.dist}\nspacing={args.spacing}\noffset={args.offset}\nsettle_ms=3000\n"
            f"stagger_ms={int(args.stagger * 1000)}\ntail_ms={int(args.tail * 1000)}\n"
            f"lanes={len(flyers)}\n"
            + (f"scenario={args.scenario}\n" if args.scenario in PUSH_SCENARIOS else "")
            + (f"cam_lane={args.cam_lane}\n" if args.cam_lane else "")
            + (f"scenario=engage\nengage_ms={ENGAGE_MS}\nbreath_ms={BREATH_MS}\n"
               f"away_ms={AWAY_MS}\naway_m={AWAY_M}\n"
               f"breath={','.join(breath_keys())}\n"
               if args.scenario == "engage" else "")
            + "".join(f"{k}={v}\n" for k, v in LANE_FRAME.items())
            + "".join(f"lane_off_{i}={o}\n"
                      for i, o in enumerate(lane_offsets, 1))
            + "".join(f"{kv.strip()}\n" for kv in (args.cmd or "").split(",") if kv.strip()),
            encoding="utf-8")
        extra = ()
        if args.entity_read:
            import build_entity_read_minimod
            entity_pack = DATA_DIR / ENTITY_PACK
            restore.save(entity_pack)     # removed again after the run
            build_entity_read_minimod.main(["--out", str(entity_pack)])
            extra = (ENTITY_PACK,)
        for p in tuple(args.pack_before) + tuple(args.pack_after):
            if not (DATA_DIR / p).is_file():
                raise SystemExit(f"[air_dive_autotest] REFUSING: {p} is not in {DATA_DIR}")
        extra = extra + tuple(args.pack_after)
        write_startup(args.startup_via, args.test_pack, restore, extra, args.memreader,
                      before_packs=tuple(args.pack_before))
        note("used_mods: " + " | ".join(USED_MODS.read_text("utf-8").splitlines()))
        note(f"launch: mods {args.test_pack} + {HELPER_PACK}, "
             f"startup via {args.startup_via}")
        own = OwnGame()
        # [AIR-DIVE-BRACE-W1 2026-11-15] --window behind: the game window is kept at the bottom of the
        # z-order without activation and the foreground goes back to the window that had it before the
        # launch, so the test no longer jumps in front of the user. Not minimised: a minimised game froze
        # its battle (probe MWMSA1_g1 / MWPB1_g1 -- Lua timers ran, no unit moved after its order).
        # normal = the old behaviour.
        behind = args.window == "behind"
        win_stop = threading.Event()
        win_count = [0, 0, 0, 0]
        previous = ctypes.windll.user32.GetForegroundWindow() if (behind and os.name == "nt") else None
        subprocess.Popen(["cmd", "/c",
                          f'start /d "{GAME_ROOT}" Warhammer3.exe used_mods.txt;'],
                         cwd=str(GAME_ROOT))
        if behind:
            def _keep_behind():
                while not win_stop.wait(0.25):
                    try:
                        sent, held, back, restored = KEEP_BEHIND(own, previous)
                    except OSError as exc:     # a window that went away mid-call: logged, next tick retries
                        note(f"window: keep_behind failed once ({exc})")
                        continue
                    win_count[0] += 1 if sent else 0
                    win_count[1] += 1 if held else 0
                    win_count[2] += 1 if back else 0
                    if restored:
                        win_count[3] += restored
                        note(f"window: found minimised, restored without activation ({restored})")
            threading.Thread(target=_keep_behind, daemon=True).start()
        note(f"window mode: {args.window}")
        seen_pid = False
        last_len = 0
        shots_started, shots_stop = False, threading.Event()
        prio_done = False
        while True:
            time.sleep(3)
            elapsed = time.time() - t0
            try:
                alive = own.alive()
            except ProcessProbeStalled:
                # unknown is not "exited": keep the last answer; the DONE /
                # crash dump / timeout checks below still end the wait
                alive = seen_pid
            if alive and not seen_pid:
                seen_pid = True
                note("Warhammer3.exe is running")
            if alive and not prio_done:
                own.lower_priority()
                prio_done = True
            lines = read_status()
            for ln in lines[last_len:]:
                if not ln.startswith("  "):     # skip UI dump body
                    note("driver: " + ln)
            last_len = len(lines)
            # [FLYER-FIX-1117] screenshots of the GAME window (grab_window) while the battle runs, on their
            # own thread: this loop polls every 3 s, so --shots below that would not be honoured here
            if args.shots and not shots_started and has(lines, "phase Deployed"):
                shots_started = True

                def _shots():
                    shots_dir = out_dir / "shots"
                    shots_dir.mkdir(exist_ok=True)
                    n = 0
                    while not shots_stop.wait(args.shots):
                        try:
                            if grab_window(own, shots_dir / f"{n:04d}_{time.time() - t0:07.1f}s.jpg"):
                                n += 1
                        except Exception as exc:  # a missed frame is logged, the run goes on
                            note(f"screenshot failed: {exc}")
                threading.Thread(target=_shots, daemon=True).start()
            if has(lines, "DONE"):
                time.sleep(3)              # recorder flushes every second
                break
            if any(ln.split(" ", 1)[-1].startswith("FAIL") for ln in lines):
                reasons.append("driver reported FAIL (see status)")
                break
            dumps = new_crash_dumps(t0)
            if dumps:
                # the crash handler keeps the process alive while it writes the
                # dump; wait for it to settle, then name the root cause (A14.10)
                time.sleep(10)
                reasons.append("game crashed: " + crash_verdict(t0))
                break
            if seen_pid and not alive:
                reasons.append(f"the game exited after {elapsed:.0f}s before DONE")
                break
            if not seen_pid and elapsed > 120:
                reasons.append("Warhammer3.exe never started within 120s")
                break
            if elapsed > 60 and int(elapsed) % 15 < 3:
                dialog = error_dialog()
                if dialog:
                    reasons.append("game error dialog: " + dialog.replace("\n", " | "))
                    break
            if not has(lines, "harness_loaded") and elapsed > args.load_timeout:
                reasons.append(f"the driver never loaded in a battle within "
                               f"{args.load_timeout}s (did the game start the "
                               f"xml battle? check lua_mod_log.txt)")
                break
            if elapsed > args.timeout:
                reasons.append(f"timeout {args.timeout}s before DONE")
                break
    finally:
        if "shots_stop" in locals():
            shots_stop.set()
        if own is not None and args.window == "behind":
            win_stop.set()
            note(f"window: kept behind on {win_count[0]} tick(s); the game held the foreground on {win_count[1]} "
                 f"tick(s), handed back {win_count[2]} time(s), restored from minimised {win_count[3]} time(s)")
        # [AIR-DIVE-W12] only the game this run launched (OwnGame)
        if own is not None:
            own.kill()
            # run 2: 3 s after Stop-Process the exiting game still held the
            # helper pack open (WinError 32); wait until the process is really
            # gone (run 3: the killed game took about 2 minutes to leave the
            # process table)
            own.wait_gone(180)
        time.sleep(1)
        restore.restore()
        note("game stopped, startup files restored")

    status_lines = read_status()
    hp_text = HP_FILE.read_text("utf-8", errors="replace") if HP_FILE.is_file() else ""
    probe_text = ""
    if PROBE_LOG.is_file():
        with open(PROBE_LOG, "rb") as f:
            f.seek(probe_offset)
            probe_text = f.read().decode("utf-8", errors="replace")
    (out_dir / "status.txt").write_text("\n".join(status_lines) + "\n",
                                        encoding="utf-8", newline="\n")
    (out_dir / "probe_slice.txt").write_text(probe_text, encoding="utf-8",
                                             newline="\n")
    (out_dir / "hp.txt").write_text(hp_text, encoding="utf-8", newline="\n")
    entity_text = None
    if args.entity_read:
        entity_text = ""
        if ENTITY_LOG.is_file():
            with open(ENTITY_LOG, "rb") as f:
                f.seek(entity_offset)
                entity_text = f.read().decode("utf-8", errors="replace")
        (out_dir / "entity_read_slice.txt").write_text(
            entity_text, encoding="utf-8", newline="\n")
    (out_dir / "timeline.txt").write_text("\n".join(timeline) + "\n",
                                          encoding="utf-8", newline="\n")
    if args.scenario == "engage":
        result = judge_engage(status_lines, hp_text, len(flyers), entity_text=entity_text)
    elif args.scenario in PUSH_SCENARIOS:
        result = judge_push(status_lines, hp_text, len(flyers), args.scenario)
    else:
        result = judge(status_lines, probe_text, hp_text, len(flyers),
                       entity_text=entity_text)
    result["reasons"] = reasons + result["reasons"]
    if reasons:
        result["verdict"] = "FAIL"
    result.update({"scenario": args.scenario, "test_pack": args.test_pack, "dist_m": args.dist,
                   "spacing_m": args.spacing, "offset_m": args.offset,
                   "lane_offsets_m": list(lane_offsets), "lane_frame": LANE_FRAME,
                   "out_dir": str(out_dir),
                   "startup_via": args.startup_via})
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--test-pack", default="flyer_dive_takeoff.pack")
    ap.add_argument("--scenario", choices=("charge", "engage") + PUSH_SCENARIOS, default="charge",
                    help="charge: the dive charge lanes; engage (AIR-DIVE-W15): "
                         "flyers in melee use their breath, then move away")
    ap.add_argument("--dist", type=float, default=None,
                    help=f"flyer start distance from its target, m (charge 250, "
                         f"engage {ENGAGE_DIST})")
    ap.add_argument("--spacing", type=float, default=250.0,
                    help="distance between lanes, m")
    ap.add_argument("--offset", type=float, default=0.0,
                    help="shift of the whole lane block along the lanes, m "
                         "(AIR-DIVE-GRIFFON: see LANE TERRAIN)")
    ap.add_argument("--lane-offsets",
                    help="comma list, one position per lane along the lanes, m "
                         "(default LANE_OFFSETS when the lane count matches; "
                         "'spacing' = the old --spacing / --offset layout)")
    ap.add_argument("--stagger", type=float, default=20.0,
                    help="seconds between one lane's charge order and the next")
    # [AIR-DIVE-W14] 40 not 30: the last lane touched down 29.5 s after its
    # order on 11-11, and the plough judge needs hit points to touchdown + 5 s
    ap.add_argument("--tail", type=float, default=40.0,
                    help="seconds recorded after the last charge order")
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--load-timeout", type=float, default=300.0)
    ap.add_argument("--window", choices=("behind", "normal"), default="normal",
                    help="behind: keep the game window at the bottom of the z-order without taking focus "
                         "(AIR-DIVE-BRACE-W1 2026-11-15). NOT safe for results: 3 of 48 behind runs froze their "
                         "battle (orders never executed, as when minimised; 0 of 464 normal runs did), so the "
                         "default stays normal and minimised is not offered")
    ap.add_argument("--startup-via", choices=("argv", "user_script"), default="argv")
    ap.add_argument("--out-dir")
    ap.add_argument("--keep-helper", action="store_true",
                    help="leave flyer_dive_autotest.pack in data/ afterwards")
    ap.add_argument("--entity-read", action="store_true",
                    help="also enable the TEST-ONLY per-soldier reader "
                         "(ld_entity_read.pack, built for the run and removed)")
    ap.add_argument("--flyers",
                    help="AIR-DIVE-W16: comma list of land unit keys, one lane each "
                         "(default: the scenario's own list)")
    # [AIR-DIVE-TAKEOFF-W1 2026-11-12] the enemy unit of every lane, and extra
    # driver control lines (comma list of key=value, written after the
    # scenario's own, so a later key wins: e.g. scenario=cycle,fight_ms=90000,
    # melee_off_2=0 -- see the cfg header of air_dive_autotest.lua)
    ap.add_argument("--target", default=TARGET,
                    help="land unit key of every lane's enemy unit")
    ap.add_argument("--cmd", help="extra driver control lines, comma list of key=value")
    # [FLYER-FIX-1117] the push scenarios' ally, the camera lane and screenshots
    # [d3-1118] the pack-order experiment: packs already deployed in data/ (never copied or
    # removed by the driver), enabled before the test pack / after the helper pack
    ap.add_argument("--pack-before", action="append", default=[], metavar="PACK",
                    help="a pack in data/ listed in used_mods.txt before the test pack (repeatable)")
    ap.add_argument("--pack-after", action="append", default=[], metavar="PACK",
                    help="a pack in data/ listed in used_mods.txt after the helper pack (repeatable)")
    ap.add_argument("--memreader", action="store_true",
                    help="also enable the Workshop memreader Plus (MEMREADER_DIR), the caves' prerequisite")
    ap.add_argument("--ally", help="scenario assist: land unit key of the flyer side's infantry, one per lane")
    ap.add_argument("--cam-lane", type=int, default=0, help="keep the camera on this lane's target (0: off)")
    ap.add_argument("--shots", type=float, default=0.0,
                    help="save a screenshot every this many seconds of the battle (0: none)")
    ap.add_argument("--judge-only", metavar="DIR",
                    help="re-judge a saved run (status.txt + probe_slice.txt)")
    args = ap.parse_args(argv)
    if args.dist is None:
        args.dist = ENGAGE_DIST if args.scenario == "engage" else 250.0
    if args.judge_only:
        d = Path(args.judge_only)
        hp = (d / "hp.txt").read_text("utf-8") if (d / "hp.txt").is_file() else ""
        status = (d / "status.txt").read_text("utf-8").splitlines()
        ent_p = d / "entity_read_slice.txt"
        ent_t = ent_p.read_text("utf-8") if ent_p.is_file() else None
        if args.scenario == "engage":
            result = judge_engage(status, hp, len(lane_flyers(args)), entity_text=ent_t)
            result["scenario"] = "engage"
        else:
            result = judge(status, (d / "probe_slice.txt").read_text("utf-8"), hp,
                           len(lane_flyers(args)), entity_text=ent_t)
    else:
        if not args.out_dir:
            args.out_dir = str(RUNS_DIR / time.strftime("%Y%m%d_%H%M%S"))
        result = run(args)
        if args.keep_helper:
            write_pack_file(str(DATA_DIR / HELPER_PACK), helper_entries(
                lane_flyers(args)), PACK_TYPE_MOD)
        Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        (Path(args.out_dir) / "verdict.json").write_text(
            json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    if result.get("scenario") == "engage":
        print_engage(result)
    elif args.scenario in PUSH_SCENARIOS:
        print(json.dumps(result.get("lanes"), indent=1))
    else:
        print_table(result)
    print("VERDICT " + json.dumps(result, separators=(",", ":")))
    return {"PASS": 0, "BLOCKED": 3}.get(result["verdict"], 1)


if __name__ == "__main__":
    sys.exit(main())
