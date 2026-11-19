"""Flyer physics dive: the three shipping code caves, their emulator check and
the generated site table. [AIR-DIVE-MP-DIVE-W1 2026-11-12, user rulings
CONTENT_LEDGER §C8-60 / §C8-61]

The rule (§C8-61): a flyer that charges from the air lands moving, keeps its
speed, and only the bodies it hits slow it -- no zeroing at touchdown, no
decelerating clip, no per-type depth. Measured and A/B-tested as test caves in
AIR-DIVE-CONTINUOUS-W1 (tools/pipelines/touchdown_probe_asm.py, §C11 steps
6-8); this file is the shipping subset of those caves without any logger.
Warhammer3.exe 9.0.5 (6ae2a00b); the game's own build check is the site
search (every pattern must match exactly once, with the expected bytes).

* ``dv_through`` (charge-goal chooser 0x143096e20, 29 bytes replaced): the
  engine gives a charge either the front-rank contact point (an entity in the
  air, +0x104 1 or 2, or a charge order with flag bit 2 -- single-model
  monsters carry it) or the through goal of a ground cavalry charge (target
  position + direction x the engine's own distance). For a flyer (own or
  ridden flight controller +0x128 / +0x2e0) it answers as for a ground
  charge with no flag. No distance is set here.
* ``dv_skip`` (melee attack dispatcher entry 0x143259794): while a flyer is
  in state 30 or 33 (+0x26c; 33 is the one tick every landing passes
  through) and its planar velocity (+0xe0 / +0xe8) is above SKIP_SPEED, no
  contact attack is started (the scalar speeds +0x23c / +0x1c8 read 0 on the
  landing tick, so they are not used).
  [AIR-DIVE-RELEASE-W1 2026-11-13] One exception: a MOVING attack (slot
  484-488, the attack object's word +8) asked for while the flyer is
  genuinely moving -- state 30 or 33 and the scalar speed +0x1c8 at or
  above SKIP_SPEED, which is never so on the landing tick -- goes ahead.
  Measured (test forks S / Q, runs S1_* / Q1_*, then the shipped pack): such
  an attack plays layered on the movement (state 30, slot 484, the flyer
  keeps 10-13 m/s), while a standing attack let through the same way (slot
  457, the manticore at touchdown) turned the flyer into a state-55 action
  and stopped it within 0.4 s. So the dive keeps CA's own charge strike (every renamed table has a
  484 since this lane, air_dive.dive_entries) and still never stands still to
  attack while fast.
* ``dv_keep`` (stop-flight wrapper entry 0x14308b420): under the same test,
  nothing ends a charging flyer's flight movement (the landing state's two
  methods and other movement states call it; after it the flyer is a ground
  mover in state 33 and its speed is gone within 0.1-0.3 s).

* [AIR-DIVE-RELEASE-W1 2026-11-13] five re-path call sites. With the three
  caves above some landings still lost their speed: 0x14307b4b0 (stop flight
  0x14307e438, then a ground re-path 0x143125b54) was called on a fast landed
  flyer. A logger cave at its entry (runs P1 / P2, CONTENT_LEDGER §C11
  AIR-DIVE-RELEASE-W1) named its callers on a fast landed flyer: the melee
  engage approach (a method of the attack behaviour, 0x14326390c; the call at
  0x143263cf5 re-paths the flyer onto its engage point once it is within
  reach of its target) and the charge order's (re)start method (vtable
  0x143ade800 slot 1, 0x143088b84; it re-paths through 0x14307b4b0 itself at
  0x143088d69 or through the ground path-to 0x14307b5b8 at 0x143088db5, which
  ends in 0x14307b4b0), and -- once, on the chimera (run M1_chim) -- the
  attack behaviour's own update (0x143092e88, the call at 0x143093e3c), and
  -- twice, on the griffon knights (run Z2_grif) -- the order's per-tick step
  to a point ahead of its entity (0x14309764c, the ground path-to at
  0x1430977f1). ``dv_engage``, ``dv_reorder``, ``dv_reorder_move``,
  ``dv_attack_move`` and ``dv_tick_move`` replace those five calls: while the mover (the entity or the flyer it
  rides) is ON THE GROUND (+0x104 0) yet still in flight movement (+0x710 not
  0) -- the landed dive and nothing else -- and passes the ``dv_keep`` test
  (state 30 / 33, planar velocity above SKIP_SPEED), the call is not made
  (the method goes on as when its own conditions skip it); otherwise the
  original callee is called with the original arguments. The two extra
  conditions are measured, not cautious: the griffon knights' P2 run showed
  hundreds of these re-paths on flyers walking on the ground (+0x710 0) or
  re-ordered in the air (+0x104 2), and none of those may be held. Once the
  collisions have slowed the flyer, every re-path is vanilla again.

* [AIR-DIVE-BRACE-W1 2026-11-14] ``dv_contact`` (melee-engage 0x143075dd8
  entry, the default vtable slot +0x4b0 -- 33 vtables; batch C showed the
  one override 0x143123338 is not the flyers'). A landed flyer that touched upright
  enemies (braced infantry are not knocked over, so they stay valid) was
  given the melee order (vtable 0x143ade470, +0x324 = 1) and stopped 1-14 m
  in (batch A, CONTENT_LEDGER §C11 AIR-DIVE-BRACE-W1). Two contact paths
  issue it, both through this vfunc: the pairwise collision's contact-engage
  0x14305dcac (stack: pair solver 0x143176c6c -> 0x1430731c8 -> 0x14305dcac)
  and the per-model update's own copy of the same test 0x143090e3c (seen
  once the first was held, batch B). Under the ``dv_engage`` test (landed,
  still in flight movement, fast) the cave returns at once; the collision
  itself (push, knock, collision attack) is untouched, and once the bodies
  hit have slowed the flyer below SKIP_SPEED it engages as vanilla. Counted
  on its own counter (+40; +32 before round 2).
* [AIR-DIVE-BRACE-W1 round 2] ``dv_settle`` (call site 0x143098cd1 in the
  entity vfunc +0x490 0x143098b04, its +0xb28 == 2 branch). With the melee
  order held, a second stop showed up on its own (batch E: wyverns x3, a
  terrorgheist): the movement goal +0x1e0 jumped to the flyer's own position
  with the charge order unchanged, then the 3.0 m/s-per-tick brake. Probe
  batch F logged the writer: stop-at-point 0x1431341b0 (+0x17c = 1, goal =
  the snapped +0x88 position, speed cap +0x180 = 0, +0x188 = 0), called from
  0x143098cd1, the vfunc being called by the entity update at 0x14308e934
  once +0xb20 is set (+0xb28 = 2; after a random delay since +0xb44 it
  settles the entity where it is). Under the ``dv_engage`` test the call is
  not made; the vfunc goes on as when its own timer has not run out, and once
  the flyer is below SKIP_SPEED the stop is vanilla again. Counted (+44).
* [AIR-DIVE-BRACE-W1] a moving state is 30, 33, or 0 on the ground (+0x104
  0): the storm dragon passes through state 0 on its touchdown tick.
* [AIR-DIVE-BRACE-W1 round 3, bounded slide] every hold (dv_skip, dv_keep,
  dv_contact and the call-site caves) holds a landed flyer only within
  SLIDE_RELEASE_M (20 m) of where it was first held (``_window_test``). With
  the holds unbounded the charge never ended: the flyer ran on to the
  through-goal about 48 m past the target, was re-ordered and charged back,
  and was never seen to stop in 8 s (packed A/B on mp_crossroads_flat:
  0/18 stopped, median travel 52.7 m; turn clips and deceleration put back
  changed neither). Past 20 m the hold ends for good (sticky, counted) and
  the engine's own engage / stop / brake take over; dv_through clears the
  entry when the flyer charges again in the air.
* [AIR-DIVE-BRACE-W1 round 4, bobbing] ``dv_commit`` (call site 0x14308f453
  in the order update 0x14308f2xx: the flight controller's re-plan test
  0x14303969c). Follower models of a multi-model flyer climbed back up about
  2 s after the unit's first model landed, in vanilla as much as with our
  caves: the order is re-pathed, the test says re-plan, and the order aborts
  the controller's landing (0x14304cea0: phase 4 / 5 -> 6, climb and go
  round). Probe batch BX1_g1: 28 of 28 approach aborts came from this call,
  0-2.7 m above the landing height. A controller on its landing approach
  within COMMIT_M (5 m) of the landing height is answered "no": the model
  lands, then takes the new path on the ground. Its landing point is moved
  LAND_AHEAD_M past the model's edge when it lies outside the band where the
  controller asks for the landing (0-10 m past the edge): left at the
  charge's through-goal, or put under the model, the request is never sent
  and the model hovers at the landing height (a 0.45 m flicker, probe
  FLB1_g1). Counted (+52).

All eleven only act on entities with a flight controller, so ground units are
untouched; both sides and the AI alike. The caves stay in the game for the
session (memreader Plus never removes a cave); mode 0 makes them pass every
call through, exactly the vanilla behaviour.

Buffer (game_alloc, LAYOUT): +0 u32 mode (1 on), +4 u32 allowed (Lua only:
the campaign's agreement said yes), +8 8 bytes MAGIC, +16 F32 skip speed,
+20 u32 skipped, +24 u32 throughs, +28 u32 kept, +32 u32 engage re-paths held
off, +36 u32 charge-order re-paths held off, +40 u32 melee engages held off,
+44 u32 blocked stops held off, +48 u32 slides ended, +52 u32 landings kept (counters for the battle
log), +64 the slide table (256 x 16 bytes: mover pointer, its | 1 once
released, 0 empty, 2 tombstone; F32 x, F32 z of the first hold; claimed with
lock cmpxchg16b, so the buffer must be 16-byte aligned), 64 + 4096 bytes.

usage (needs keystone-engine + unicorn; a scratch venv is enough):
  python dive_cave_asm.py                 assemble + emulator checks + mutants
  python dive_cave_asm.py --write-site    + write the site table
  python dive_cave_asm.py --check-exe     every site matches once in the exe
/ 物理俯冲的三个发货代码洞（不含记录器）、模拟器检查与位点表生成。
"""
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rolepath  # noqa: F401,E402 -- because importing it puts the role dirs (lib/) on sys.path
import cave_site_text  # noqa: E402 -- because the sys.path line above must run first (TEST-REPAIR-1113: one home)

HERE = Path(__file__).resolve().parent
MOD_DIR = HERE.parent.parent
SITE_LUA = Path("script/campaign/flyer_dive/data/dive_site.lua")
EXE = Path(r"D:/SteamLibrary/steamapps/common/Total War WARHAMMER III/Warhammer3.exe")

BUILD = "6ae2a00b"
OWNER, FEATURE = "flyer_dive", "dive"
MODE_AT, ALLOWED_AT, MAGIC_AT, SKIP_SPEED_AT = 0, 4, 8, 16
SKIPPED_AT, THROUGHS_AT, KEPT_AT = 20, 24, 28
ENGAGED_AT, REORDERED_AT = 32, 36            # [AIR-DIVE-RELEASE-W1] re-paths held off
CONTACT_AT, SETTLED_AT = 40, 44              # [AIR-DIVE-BRACE-W1] melee engages / blocked stops held off
# [AIR-DIVE-BRACE-W1 round 3, bounded slide] the hold window (_window_test): slides ended at RELEASED_AT, the
# table at SLIDE_AT (16-byte aligned: lock cmpxchg16b), SLIDE_SLOTS entries of 16 bytes
RELEASED_AT, SLIDE_AT, SLIDE_SLOTS = 48, 64, 256
# [AIR-DIVE-BRACE-W1 round 4, bobbing] landings kept (dv_commit) counted at COMMITTED_AT; a flight controller
# (entity +0x128): +0 its entity, +0x14 the landing point's height, +0x90 its phase (1 landed, 4 descending,
# 5 final approach, 6 go-around, read from the bob probe, 2026-11-15)
COMMITTED_AT = 52
# [FLYER-FIX-1117] a landed flyer's slide window ends for good at its first melee engage the engine takes
# (CLOSED_AT counts them), and a body the flyer hits that is already in melee with another unit is not
# carried (ENGAGED_BODY_AT counts those contacts): player report "dive or trash" 2026-11-17, a Jade Longma
# unit charged again into a melee it was already in dragged the enemy 20 m back into its own missile line.
CLOSED_AT, ENGAGED_BODY_AT = 56, 60
MELEE_OFF = 0x324                               # an entity's engage state (1 = engaged, 0x143075dd8 sets it)
ORDER_TARGET_OFF = 0x368                        # the entity's order (+0x330) target (+0x38: vfunc +0xc0)
UNIT_OFF = 0x2E8                                # the entity's unit
BODY_OFF = 0x18                                 # melee-engage parameters: the body touched (0x14305ad94)
FC_PHASE_OFF, FC_LAND_Y_OFF, POS_Y_OFF = 0x90, 0x14, 0x8C
FC_LAND_X_OFF, FC_LAND_Z_OFF = 0x10, 0x18          # the landing point's x, z (dv_commit moves it, see LAND_AHEAD_M)
RADIUS_OFF = 0xA0                                  # the entity's radius
# The controller's final approach (0x14301b60c) asks for the landing only while 0 < distance to the landing
# point minus the radius < LAND_EVENT_M (10 m, the constant at 0x14392df18; flag fc +0xa8). dv_commit puts the
# point LAND_AHEAD_M past the model's edge on the line to the old point when it is outside that band, so the
# request is sent and the model sets down a few metres on (probe FLB1_g1, 2026-11-15).
LAND_EVENT_M, LAND_AHEAD_M = 10.0, 5.0
# A model on its landing approach no lower than this above the landing height finishes landing when its
# order is re-pathed: the 28 approach aborts behind the bobbing were 0-2.7 m above it (BX1_g1), and a model
# still high on its descent keeps vanilla's re-plan (a new order mid-descent turns it in the air as before).
COMMIT_M = 5.0
POS_OFF = 0x88                                 # entity position x (+0x88), z (+0x90)
# A landed flyer keeps its speed only within this distance of where it was first held: the target's depth
# (6.5-8.1 m) plus its touchdown distance from the target's centre (5.6-7.8 m) is about 10-12 m (packed
# A/B batch, mp_crossroads_flat, 2026-11-14), so 20 m carries every flyer through the line and a body length
# out the far side; past it the engine's engage / stop / re-path take over and its own deceleration brakes.
SLIDE_RELEASE_M = 20.0
BUFFER_BYTES = 64 + 256 * 16                  # [AIR-DIVE-BRACE-W1 round 3] + the slide table
MAGIC = b"FLYDIVE3"                           # [FLYER-FIX-1117] two counters more: v2; 3: renamed (RENAME-1118)
SKIP_SPEED = 2.0                      # m/s: below it a landed flyer attacks / stops as vanilla
FC_OFF, PARENT_OFF, LAYER_OFF, FLAGS_OFF = 0x128, 0x2E0, 0x104, 0xC4
STATE_OFF, VEL_OFF = 0x26C, 0xE0
FLYMODE_OFF = 0x710                   # [AIR-DIVE-RELEASE-W1] 0 = a ground mover
MOVING_STATES = (30, 33)
# [AIR-DIVE-BRACE-W1 2026-11-14] state 0 counts as moving only on the ground (+0x104 0): the storm
# dragon's touchdown tick (runs A1_storm, CONTENT_LEDGER §C11 AIR-DIVE-BRACE-W1)
LANDED_IDLE_STATE = 0
SPEED_OFF = 0x1C8                     # [AIR-DIVE-RELEASE-W1] scalar speed (0 on the landing tick)
MOVING_ATTACK_SLOTS = (484, 488)      # MOVING_ATTACK_1..5: these may start while fast
BUF_PLACEHOLDER = 0x1122334455667788
RESUME_PLACEHOLDER = 0x8877665544332211
ORIG_PLACEHOLDER = 0x2233445566778899       # the original callee of a call-site cave

# name: (pattern, at, stolen bytes, resume offset after the site or None)
CAVES = {
    "dv_through": ("41 8B 81 04 01 00 00 FF C8 83 F8 01 76 0C F6 87 C4 00 00 00 02 44 8A C3 74 03 41 B0 01",
                   0, "41 8B 81 04 01 00 00 FF C8", 29),
    "dv_skip": ("48 8B C4 48 89 58 08 48 89 70 10 48 89 78 18 4C 89 68 20 55 41 56 41 57 48 8B EC "
                "48 83 EC 40 48 8B 41 08 48 8B F9", 0, "48 8B C4 48 89 58 08", None),
    "dv_keep": ("40 53 48 83 EC 20 33 D2 48 8B D9 E8 08 30 FF FF 33 D2 48 8B CB",
                0, "40 53 48 83 EC 20 33 D2", None),
    # [AIR-DIVE-RELEASE-W1] 0x143263cef: movaps xmm2,xmm7 / mov rdx,rax / call 0x14307b4b0
    "dv_engage": ("0F 28 D7 48 8B D0 E8 ?? ?? ?? ?? 4C 8D 9C 24 A0 00 00 00",
                  0, "0F 28 D7 48 8B D0 E8", 11),
    # 0x143088d66: mov r9d,esi / call 0x14307b4b0 (then jmp 0x143088dba, left in place)
    "dv_reorder": ("44 8B CE E8 ?? ?? ?? ?? EB 4A F3 0F 10 87 9C 00 00 00",
                   0, "44 8B CE E8", 8),
    # 0x143088db0: movss [rbp+0x14],xmm0 / call 0x14307b5b8 (rcx = rdi, the order)
    "dv_reorder_move": ("F3 0F 11 45 14 E8 ?? ?? ?? ?? 48 8B 8F A8 00 00 00 48 85 C9",
                        0, "F3 0F 11 45 14 E8", 10),
    # 0x143093e30: movaps xmm2,xmm6 / mov rdx,rax / mov rcx,rsi / xor r9d,r9d /
    # call 0x14307b4b0 (then jmp 0x1430939af, left in place)
    "dv_attack_move": ("0F 28 D6 48 8B D0 48 8B CE 45 33 C9 E8 ?? ?? ?? ?? E9",
                       0, "0F 28 D6 48 8B D0 48 8B CE 45 33 C9 E8", 17),
    # 0x1430977eb: movss [rsp+0x74],xmm3 / call 0x14307b5b8 (rcx = rbx, the order) --
    # the order's per-tick step to a point ahead of its entity (0x14309764c,
    # called from the order update at 0x14308f3f5)
    "dv_tick_move": ("F3 0F 11 5C 24 74 E8 ?? ?? ?? ?? 0F 28 74 24 50 0F 28 7C 24 40",
                     0, "F3 0F 11 5C 24 74 E8", 11),
    # [AIR-DIVE-BRACE-W1] 0x143075dd8 entry: melee-engage (rcx = the entity that engages, rdx = the
    # parameters), the default vtable slot +0x4b0 (33 vtables; one class overrides it with
    # 0x143123338, which calls this). Both contact paths reach it: the pairwise collision's
    # contact-engage 0x14305dcac (call at 0x14305ddd8) and the per-model update's copy 0x143090e3c
    # (0x1430912de)
    "dv_contact": ("48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 8B 81 24 03 00 00 48 8B F2 48 8B D9 85 C0 74 2F",
                   0, "48 89 5C 24 08 48 89 74 24 10", None),
    # [AIR-DIVE-BRACE-W1 round 2] 0x143098cc8: mov rdx,rax / xor r8d,r8d / mov rcx,rdi /
    # call 0x1431341b0 (then jmp 0x143098cdb, left in place) -- in the entity vfunc +0x490
    # 0x143098b04, the +0xb28 == 2 branch: stop at the current position (goal +0x1e0 = the snapped
    # +0x88 position, speed cap +0x180 = 0, +0x17c = 1)
    "dv_settle": ("48 8B D0 45 33 C0 48 8B CF E8 ?? ?? ?? ?? EB 03 45 8A FD 48 8B CF",
                  0, "48 8B D0 45 33 C0 48 8B CF E8", 14),
    # [AIR-DIVE-BRACE-W1 round 4] 0x14308f453: mov r8,[rbx+0x38] / mov rcx,rdi / call 0x14303969c (the flight
    # controller rdi: re-plan for the order's new path?), then test al,al / je -- in the order update
    # 0x14308f2xx; on yes the order aborts the controller's landing (0x14304cea0 at 0x14308f474)
    "dv_commit": ("4C 8B 43 38 48 8B CF E8 ?? ?? ?? ?? 84 C0 74 1A 33 D2 44 89 7B 30",
                  0, "4C 8B 43 38 48 8B CF E8", 12),
}
# [AIR-DIVE-RELEASE-W1] call-site caves: where the original call's rel32 sits
# (memreader Plus ``reads``), the callee it must name, the instructions the
# cave redoes before the call, the mover's entity and its counter. Every
# jump into these functions that lands in a replaced range lands on its
# first byte (checked statically: 0x143088cb5 -> 0x143088d66,
# 0x143263c29 -> 0x143263cef; none into 0x143093e30..0x143093e40 or
# 0x1430977eb..0x1430977f5).
CALL_SITES = {
    "dv_engage": {"call_at": 6, "callee": 0x14307B4B0, "entity": "rcx", "counter": ENGAGED_AT,
                  "pre": "    movaps xmm2, xmm7\n    mov rdx, rax\n"},
    "dv_reorder": {"call_at": 3, "callee": 0x14307B4B0, "entity": "rcx", "counter": REORDERED_AT,
                   "pre": "    mov r9d, esi\n"},
    "dv_reorder_move": {"call_at": 5, "callee": 0x14307B5B8, "entity": "qword ptr [rdi + 8]",
                        "counter": REORDERED_AT, "pre": "    movss dword ptr [rbp + 0x14], xmm0\n"},
    "dv_attack_move": {"call_at": 12, "callee": 0x14307B4B0, "entity": "rsi", "counter": ENGAGED_AT,
                       "pre": "    movaps xmm2, xmm6\n    mov rdx, rax\n    mov rcx, rsi\n    xor r9d, r9d\n"},
    "dv_tick_move": {"call_at": 6, "callee": 0x14307B5B8, "entity": "qword ptr [rbx + 8]",
                     "counter": REORDERED_AT, "pre": "    movss dword ptr [rsp + 0x74], xmm3\n"},
    "dv_settle": {"call_at": 9, "callee": 0x1431341B0, "entity": "rdi", "counter": SETTLED_AT,
                  "pre": "    mov rdx, rax\n    xor r8d, r8d\n    mov rcx, rdi\n"},
    # [AIR-DIVE-BRACE-W1 round 4] not a skip on speed: commit_source (its own test, al = 0 when it skips)
    "dv_commit": {"call_at": 7, "callee": 0x14303969C, "entity": "rcx", "counter": COMMITTED_AT,
                  "pre": "    mov r8, qword ptr [rbx + 0x38]\n    mov rcx, rdi\n", "kind": "commit"},
}


def _fast_test(ent):
    """Flags after: 'jbe pass' skips unless ent is in a moving state and its
    planar velocity is above the skip speed (r10 = buffer; xmm0/1 saved).
    [AIR-DIVE-BRACE-W1] A moving state is 30, 33, or LANDED_IDLE_STATE (0)
    on the ground (+0x104 0) -- the storm dragon's touchdown tick."""
    return f"""
    cmp dword ptr [{ent} + {STATE_OFF:#x}], {MOVING_STATES[0]}
    je moving
    cmp dword ptr [{ent} + {STATE_OFF:#x}], {MOVING_STATES[1]}
    je moving
    cmp dword ptr [{ent} + {STATE_OFF:#x}], {LANDED_IDLE_STATE}
    jne pass
    cmp dword ptr [{ent} + {LAYER_OFF:#x}], 0
    jne pass
moving:
    lea rsp, [rsp - 32]
    movdqu xmmword ptr [rsp], xmm0
    movdqu xmmword ptr [rsp + 16], xmm1
    movss xmm0, dword ptr [{ent} + {VEL_OFF:#x}]
    mulss xmm0, xmm0
    movss xmm1, dword ptr [{ent} + {VEL_OFF + 8:#x}]
    mulss xmm1, xmm1
    addss xmm0, xmm1
    movss xmm1, dword ptr [r10 + {SKIP_SPEED_AT}]
    mulss xmm1, xmm1
    comiss xmm0, xmm1
    movdqu xmm0, xmmword ptr [rsp]
    movdqu xmm1, xmmword ptr [rsp + 16]
    lea rsp, [rsp + 32]
    jbe pass
"""


def _window_test(ent):
    """[AIR-DIVE-BRACE-W1 round 3] After a passed _fast_test: hold only within SLIDE_RELEASE_M of where this
    mover was first held since it last charged in the air. Table at SLIDE_AT, SLIDE_SLOTS x 16 bytes
    (qword key: 0 empty, 2 tombstone, the mover, the mover | 1 = released; dword x, dword z of the first
    hold), open addressing on key >> 4. First sight: claimed with one lock cmpxchg16b (key and point
    together, so no reader sees a key without its point), held. Past the radius: key | 1 (lock or), counted
    at RELEASED_AT, and 'jmp pass'. A released key, or a full table, passes at once. Falls through to the
    hold. Every register and xmm0 / xmm1 come back unchanged. A hold IN THE AIR (+0x104 not 0: dv_keep and
    dv_skip also hold a state-30 flyer on its way down) holds without touching the table, so the window
    starts where the flyer was first held on the ground (an airborne first hold would start it up to a
    dive-length before touchdown). Flags are not kept (every caller sets them again)."""
    d2 = struct.unpack("<I", struct.pack("<f", SLIDE_RELEASE_M * SLIDE_RELEASE_M))[0]
    return f"""
    cmp dword ptr [{ent} + {LAYER_OFF:#x}], 0
    jne wair
    push rax
    push rbx
    push rcx
    push rdx
    push r8
    push r9
    mov r9, {ent}
    lea rsp, [rsp - 32]
    movdqu xmmword ptr [rsp], xmm0
    movdqu xmmword ptr [rsp + 16], xmm1
    mov rax, r9
    shr rax, 4
    and eax, {SLIDE_SLOTS - 1}
    mov r8d, {SLIDE_SLOTS}
    xor ecx, ecx
wprobe:
    mov rdx, rax
    shl rdx, 4
    lea rbx, [r10 + rdx + {SLIDE_AT}]
    mov rdx, qword ptr [rbx]
    cmp rdx, r9
    je wfound
    xor rdx, 1
    cmp rdx, r9
    je wpass_out
    xor rdx, 1
    cmp rdx, 2
    jne wnot_tomb
    test rcx, rcx
    jne wnext
    mov rcx, rbx
    jmp wnext
wnot_tomb:
    test rdx, rdx
    jne wnext
    test rcx, rcx
    jne winsert
    mov rcx, rbx
    jmp winsert
wnext:
    inc eax
    and eax, {SLIDE_SLOTS - 1}
    dec r8d
    jne wprobe
    test rcx, rcx
    je wpass_out
winsert:
    mov r8, rcx
    mov rax, qword ptr [r8]
    mov rdx, qword ptr [r8 + 8]
    mov ecx, dword ptr [r9 + {POS_OFF + 8:#x}]
    shl rcx, 32
    mov ebx, dword ptr [r9 + {POS_OFF:#x}]
    or rcx, rbx
    mov rbx, r9
    lock cmpxchg16b xmmword ptr [r8]
    jmp whold
wfound:
    movss xmm0, dword ptr [r9 + {POS_OFF:#x}]
    subss xmm0, dword ptr [rbx + 8]
    mulss xmm0, xmm0
    movss xmm1, dword ptr [r9 + {POS_OFF + 8:#x}]
    subss xmm1, dword ptr [rbx + 12]
    mulss xmm1, xmm1
    addss xmm0, xmm1
    mov eax, {d2:#x}
    movd xmm1, eax
    comiss xmm0, xmm1
    jb whold
    lock or qword ptr [rbx], 1
    lock inc dword ptr [r10 + {RELEASED_AT}]
wpass_out:
    movdqu xmm0, xmmword ptr [rsp]
    movdqu xmm1, xmmword ptr [rsp + 16]
    lea rsp, [rsp + 32]
    pop r9
    pop r8
    pop rdx
    pop rcx
    pop rbx
    pop rax
    jmp pass
whold:
    movdqu xmm0, xmmword ptr [rsp]
    movdqu xmm1, xmmword ptr [rsp + 16]
    lea rsp, [rsp + 32]
    pop r9
    pop r8
    pop rdx
    pop rcx
    pop rbx
    pop rax
wair:
"""


def _window_clear(ent):
    """[AIR-DIVE-BRACE-W1 round 3] dv_through, for a flyer charging IN THE AIR (+0x104 not 0): tombstone the
    mover's slide entry (the mover is its mount when it rides one), so its next landing gets a new window.
    [FLYER-FIX-1117] Not when the charging entity is engaged in melee (+0x324 1): a re-charge out of a melee
    lands with its window closed (_window_close), so it does not drag the enemy it was fighting."""
    return f"""
    cmp dword ptr [{ent} + {LAYER_OFF:#x}], 0
    je wclr_done
    cmp dword ptr [{ent} + {MELEE_OFF:#x}], 1
    jne wclr_go
    push r11
    mov r11, qword ptr [{ent} + {PARENT_OFF:#x}]
    test r11, r11
    cmove r11, {ent}
{_window_close("r11")}    pop r11
    jmp wclr_done
wclr_go:
    push rax
    push rcx
    push rdx
    push r8
    mov rcx, {ent}
    mov rax, qword ptr [rcx + {PARENT_OFF:#x}]
    test rax, rax
    cmovne rcx, rax
    mov rax, rcx
    shr rax, 4
    and eax, {SLIDE_SLOTS - 1}
    mov r8d, {SLIDE_SLOTS}
wclr_probe:
    mov rdx, rax
    shl rdx, 4
    mov rdx, qword ptr [r10 + rdx + {SLIDE_AT}]
    test rdx, rdx
    je wclr_out
    and rdx, -2
    cmp rdx, rcx
    jne wclr_next
    mov rdx, rax
    shl rdx, 4
    mov qword ptr [r10 + rdx + {SLIDE_AT}], 2
    jmp wclr_out
wclr_next:
    inc eax
    and eax, {SLIDE_SLOTS - 1}
    dec r8d
    jne wclr_probe
wclr_out:
    pop r8
    pop rdx
    pop rcx
    pop rax
wclr_done:
"""


def _window_close(ent):
    """[FLYER-FIX-1117] End the mover's slide window for good: its entry (held or not yet released) is
    marked released (key | 1, counted once at CLOSED_AT); a mover with no entry gets one, already released,
    so a later ground re-charge in the same landing is never held (the window opens only on a fresh air
    charge, dv_through). A full table is left alone. Every register comes back; flags are not kept."""
    return f"""
    push rax
    push rbx
    push rcx
    push rdx
    push r8
    push r9
    mov r9, {ent}
    mov rax, r9
    shr rax, 4
    and eax, {SLIDE_SLOTS - 1}
    mov r8d, {SLIDE_SLOTS}
    xor ecx, ecx
cprobe:
    mov rdx, rax
    shl rdx, 4
    lea rbx, [r10 + rdx + {SLIDE_AT}]
    mov rdx, qword ptr [rbx]
    cmp rdx, r9
    je cfound
    xor rdx, 1
    cmp rdx, r9
    je cout
    xor rdx, 1
    cmp rdx, 2
    jne cnot_tomb
    test rcx, rcx
    jne cnext
    mov rcx, rbx
    jmp cnext
cnot_tomb:
    test rdx, rdx
    jne cnext
    test rcx, rcx
    jne cinsert
    mov rcx, rbx
    jmp cinsert
cnext:
    inc eax
    and eax, {SLIDE_SLOTS - 1}
    dec r8d
    jne cprobe
    test rcx, rcx
    je cout
cinsert:
    mov r8, rcx
    mov rax, qword ptr [r8]
    mov rdx, qword ptr [r8 + 8]
    mov ecx, dword ptr [r9 + {POS_OFF + 8:#x}]
    shl rcx, 32
    mov ebx, dword ptr [r9 + {POS_OFF:#x}]
    or rcx, rbx
    mov rbx, r9
    or rbx, 1
    lock cmpxchg16b xmmword ptr [r8]
    jne cout
    lock inc dword ptr [r10 + {CLOSED_AT}]
    jmp cout
cfound:
    lock bts qword ptr [rbx], 0
    jc cout
    lock inc dword ptr [r10 + {CLOSED_AT}]
cout:
    pop r9
    pop r8
    pop rdx
    pop rcx
    pop rbx
    pop rax
"""


def commit_source():
    """[AIR-DIVE-BRACE-W1 round 4, bobbing] dv_commit: redo the two instructions, then answer the re-plan
    test 0x14303969c "no" (al = 0, counted) for a flight controller (rcx) on its landing approach (phase 4
    or 5) whose entity is no more than COMMIT_M above the landing height, and, when the landing point is
    outside the band where the controller asks for the landing (0 < distance - radius < LAND_EVENT_M), move
    it LAND_AHEAD_M past the model's edge on the line to the old point -- otherwise the model hovers at the
    landing height (a 0.45 m flicker for 2.5-3 s: v1 left the point at the charge's through-goal, v2 put it
    under the model, both outside the band). Otherwise call the test with the original arguments. Mode 0:
    always called. Clobbers only what the call may (rax, rcx, r10, r11, xmm0-xmm5, flags)."""
    c = CALL_SITES["dv_commit"]
    bits = struct.unpack("<I", struct.pack("<f", COMMIT_M))[0]
    return f"""
{c["pre"]}    mov r10, {BUF_PLACEHOLDER:#x}
    cmp dword ptr [r10 + {MODE_AT}], 1
    jne pass
    mov eax, dword ptr [rcx + {FC_PHASE_OFF:#x}]
    sub eax, 4
    cmp eax, 1
    ja pass
    mov r11, qword ptr [rcx]
    test r11, r11
    je pass
    movss xmm0, dword ptr [r11 + {POS_Y_OFF:#x}]
    subss xmm0, dword ptr [rcx + {FC_LAND_Y_OFF:#x}]
    mov eax, {bits:#x}
    movd xmm1, eax
    comiss xmm0, xmm1
    ja pass
    movss xmm0, dword ptr [rcx + {FC_LAND_X_OFF:#x}]
    subss xmm0, dword ptr [r11 + {POS_OFF:#x}]
    movss xmm1, dword ptr [rcx + {FC_LAND_Z_OFF:#x}]
    subss xmm1, dword ptr [r11 + {POS_OFF + 8:#x}]
    movaps xmm2, xmm0
    mulss xmm2, xmm2
    movaps xmm3, xmm1
    mulss xmm3, xmm3
    addss xmm2, xmm3
    sqrtss xmm2, xmm2
    movss xmm3, dword ptr [r11 + {RADIUS_OFF:#x}]
    movaps xmm4, xmm2
    subss xmm4, xmm3
    xorps xmm5, xmm5
    comiss xmm4, xmm5
    jbe ahead
    mov eax, {struct.unpack("<I", struct.pack("<f", LAND_EVENT_M))[0]:#x}
    movd xmm5, eax
    comiss xmm4, xmm5
    jb inband
ahead:
    mov eax, {struct.unpack("<I", struct.pack("<f", 1e-3))[0]:#x}
    movd xmm5, eax
    comiss xmm2, xmm5
    jbe inband
    mov eax, {struct.unpack("<I", struct.pack("<f", LAND_AHEAD_M))[0]:#x}
    movd xmm5, eax
    addss xmm5, xmm3
    divss xmm5, xmm2
    mulss xmm0, xmm5
    addss xmm0, dword ptr [r11 + {POS_OFF:#x}]
    movss dword ptr [rcx + {FC_LAND_X_OFF:#x}], xmm0
    mulss xmm1, xmm5
    addss xmm1, dword ptr [r11 + {POS_OFF + 8:#x}]
    movss dword ptr [rcx + {FC_LAND_Z_OFF:#x}], xmm1
inband:
    lock inc dword ptr [r10 + {COMMITTED_AT}]
    xor eax, eax
    jmp back
pass:
    mov rax, {ORIG_PLACEHOLDER:#x}
    call rax
back:
    mov r11, {RESUME_PLACEHOLDER:#x}
    jmp r11
"""


def call_skip_source(name):
    """[AIR-DIVE-RELEASE-W1] Redo the instructions before the call, then skip
    the call for a fast moving flyer (counted) or make it with the original
    arguments; resume after it. Clobbers only what the call itself may
    (rax, r10, r11, flags); xmm0 / xmm1 kept by the speed test."""
    c = CALL_SITES[name]
    if c.get("kind") == "commit":
        return commit_source()
    return f"""
{c["pre"]}    mov r10, {BUF_PLACEHOLDER:#x}
    cmp dword ptr [r10 + {MODE_AT}], 1
    jne pass
    mov r11, {c["entity"]}
    mov rax, qword ptr [r11 + {PARENT_OFF:#x}]
    test rax, rax
    cmovne r11, rax
    mov rax, qword ptr [r11 + {FC_OFF:#x}]
    test rax, rax
    je pass
    cmp dword ptr [r11 + {LAYER_OFF:#x}], 0
    jne pass
    cmp dword ptr [r11 + {FLYMODE_OFF:#x}], 0
    je pass
{_fast_test("r11")}
{_window_test("r11")}    lock inc dword ptr [r10 + {c["counter"]}]
    jmp back
pass:
    mov rax, {ORIG_PLACEHOLDER:#x}
    call rax
back:
    mov r11, {RESUME_PLACEHOLDER:#x}
    jmp r11
"""


def cave_source(name):
    if name in CALL_SITES:
        return call_skip_source(name)
    if name == "dv_through":
        return f"""
    mov r10, {BUF_PLACEHOLDER:#x}
    cmp dword ptr [r10 + {MODE_AT}], 1
    jne orig
    mov r11, qword ptr [r9 + {FC_OFF:#x}]
    test r11, r11
    jne flyer
    mov r11, qword ptr [r9 + {PARENT_OFF:#x}]
    test r11, r11
    je orig
    mov r11, qword ptr [r11 + {FC_OFF:#x}]
    test r11, r11
    je orig
flyer:
{_window_clear("r9")}    lock inc dword ptr [r10 + {THROUGHS_AT}]
    mov r8b, bl
    jmp back
orig:
    mov eax, dword ptr [r9 + {LAYER_OFF:#x}]
    dec eax
    cmp eax, 1
    jbe one
    test byte ptr [rdi + {FLAGS_OFF:#x}], 2
    mov r8b, bl
    je back
one:
    mov r8b, 1
back:
    mov r11, {RESUME_PLACEHOLDER:#x}
    jmp r11
"""
    if name == "dv_skip":
        return f"""
    pushfq
    push r10
    push r11
    mov r10, {BUF_PLACEHOLDER:#x}
    cmp dword ptr [r10 + {MODE_AT}], 1
    jne pass
    mov rax, qword ptr [rcx + 8]
    test rax, rax
    je pass
    mov r11, qword ptr [rax]
    test r11, r11
    je pass
    mov rax, qword ptr [r11 + {PARENT_OFF:#x}]
    test rax, rax
    cmovne r11, rax
    mov rax, qword ptr [r11 + {FC_OFF:#x}]
    test rax, rax
    je pass
    cmp dword ptr [r11 + {STATE_OFF:#x}], {MOVING_STATES[0]}
    je slotchk
    cmp dword ptr [r11 + {STATE_OFF:#x}], {MOVING_STATES[1]}
    jne strict
slotchk:
    mov eax, dword ptr [r10 + {SKIP_SPEED_AT}]
    cmp dword ptr [r11 + {SPEED_OFF:#x}], eax
    jl strict
    mov rax, qword ptr [rcx + 8]
    movzx eax, word ptr [rax + 8]
    sub eax, {MOVING_ATTACK_SLOTS[0]}
    cmp eax, {MOVING_ATTACK_SLOTS[1] - MOVING_ATTACK_SLOTS[0]}
    jbe pass
strict:
{_fast_test("r11")}
{_window_test("r11")}    lock inc dword ptr [r10 + {SKIPPED_AT}]
    pop r11
    pop r10
    popfq
    ret
pass:
    pop r11
    pop r10
    popfq
"""
    if name == "dv_contact":
        # [FLYER-FIX-1117] 'pass' ends the slide window (the engine takes this melee engage), 'pure' does not
        # touch it (not a landed flyer); a body already in melee with another unit is never carried.
        return f"""
    pushfq
    push rax
    push r10
    push r11
    mov r10, {BUF_PLACEHOLDER:#x}
    cmp dword ptr [r10 + {MODE_AT}], 1
    jne pure
    mov r11, rcx
    test r11, r11
    je pure
    mov rax, qword ptr [r11 + {PARENT_OFF:#x}]
    test rax, rax
    cmovne r11, rax
    mov rax, qword ptr [r11 + {FC_OFF:#x}]
    test rax, rax
    je pure
    cmp dword ptr [r11 + {LAYER_OFF:#x}], 0
    jne pure
    cmp dword ptr [r11 + {FLYMODE_OFF:#x}], 0
    je pass
    test rdx, rdx
    je nobody
    mov rax, qword ptr [rdx + {BODY_OFF:#x}]
    test rax, rax
    je nobody
    cmp dword ptr [rax + {MELEE_OFF:#x}], 1
    jne nobody
    mov rax, qword ptr [rax + {ORDER_TARGET_OFF:#x}]
    test rax, rax
    je nobody
    mov rax, qword ptr [rax + {UNIT_OFF:#x}]
    cmp rax, qword ptr [rcx + {UNIT_OFF:#x}]
    je nobody
    lock inc dword ptr [r10 + {ENGAGED_BODY_AT}]
    jmp pass
nobody:
{_fast_test("r11")}
{_window_test("r11")}    lock inc dword ptr [r10 + {CONTACT_AT}]
    pop r11
    pop r10
    pop rax
    popfq
    ret
pass:
{_window_close("r11")}pure:
    pop r11
    pop r10
    pop rax
    popfq
"""
    if name == "dv_keep":
        return f"""
    pushfq
    push rax
    push r10
    push r11
    mov r10, {BUF_PLACEHOLDER:#x}
    cmp dword ptr [r10 + {MODE_AT}], 1
    jne pass
    mov rax, qword ptr [rcx + {FC_OFF:#x}]
    test rax, rax
    je pass
{_fast_test("rcx")}
{_window_test("rcx")}    lock inc dword ptr [r10 + {KEPT_AT}]
    pop r11
    pop r10
    pop rax
    popfq
    ret
pass:
    pop r11
    pop r10
    pop rax
    popfq
"""
    raise KeyError(name)


def assemble(name, source=None):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_64
    code, _ = Ks(KS_ARCH_X86, KS_MODE_64).asm(source or cave_source(name), 0x1000)
    code = bytes(code)
    wants = ([BUF_PLACEHOLDER] + ([RESUME_PLACEHOLDER] if CAVES[name][3] else [])
             + ([ORIG_PLACEHOLDER] if name in CALL_SITES else []))
    for ph in wants:
        if code.count(struct.pack("<Q", ph)) != 1:
            raise SystemExit(f"[dive_cave_asm] REFUSING: placeholder {ph:#x} not in {name} exactly once")
    return code


# --- emulator checks ----------------------------------------------------------
def _uc():
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
    return Uc(UC_ARCH_X86, UC_MODE_64)


def _fill(code, buf, resume=0, orig=0):
    return (code.replace(struct.pack("<Q", BUF_PLACEHOLDER), struct.pack("<Q", buf))
            .replace(struct.pack("<Q", RESUME_PLACEHOLDER), struct.pack("<Q", resume))
            .replace(struct.pack("<Q", ORIG_PLACEHOLDER), struct.pack("<Q", orig)))


FAST, SLOW = (0.9, -14.97), (1.0, -1.0)
# [d15-1118] every rig's instruction budget is multiplied by this (1 here; the test-only marked caves of
# dive_mark_asm.py run more instructions per call and raise it while the shipped cases run on them)
STEP_FACTOR = 1


def check_through(code):
    """mode 1 + flyer (own or ridden) -> r8b = bl whatever +0x104 and the order
    flags hold, counted; otherwise the original's r8b (1 when +0x104 is 1 or 2
    or flag bit 2 is set, else bl); always resumes, other registers kept."""
    from unicorn import x86_const as X
    CODE, RESUME, BUF, STACK, OBJ = 0x100000, 0x120000, 0x200000, 0x400000, 0x500000
    keep = (X.UC_X86_REG_RCX, X.UC_X86_REG_RDX, X.UC_X86_REG_RBX, X.UC_X86_REG_RSI, X.UC_X86_REG_RDI,
            X.UC_X86_REG_RBP, X.UC_X86_REG_R9, X.UC_X86_REG_R15, X.UC_X86_REG_RSP)
    BL, fails, n = 0x5A, [], 0
    for mode in (1, 0):
        for fc_self, fc_parent in ((True, None), (False, True), (False, False), (False, None)):
            for layer in (0, 1, 2, 3):
                for flags in (0x0A, 0x04, 0x02, 0x00):
                    n += 1
                    mu = _uc()
                    for base, size in ((CODE, 0x1000), (RESUME, 0x1000), (BUF, 0x2000), (STACK, 0x10000),
                                       (OBJ, 0x10000)):
                        mu.mem_map(base, size)
                    mu.mem_write(CODE, _fill(code, BUF, RESUME))
                    mu.mem_write(RESUME, b"\x90")
                    mu.mem_write(BUF + MODE_AT, struct.pack("<I", mode))
                    ent, parent, order = OBJ + 0x1000, OBJ + 0x3000, OBJ + 0x5000
                    mu.mem_write(ent + LAYER_OFF, struct.pack("<i", layer))
                    mu.mem_write(ent + FC_OFF, struct.pack("<Q", 0x77 if fc_self else 0))
                    mu.mem_write(ent + PARENT_OFF, struct.pack("<Q", parent if fc_parent is not None else 0))
                    mu.mem_write(parent + FC_OFF, struct.pack("<Q", 0x88 if fc_parent else 0))
                    mu.mem_write(order + FLAGS_OFF, struct.pack("<I", flags))
                    vals = {X.UC_X86_REG_RCX: 0xC1, X.UC_X86_REG_RDX: 0xD1, X.UC_X86_REG_RBX: 0xB100 | BL,
                            X.UC_X86_REG_RSI: 0x51, X.UC_X86_REG_RDI: order, X.UC_X86_REG_RBP: 0xB7,
                            X.UC_X86_REG_R8: 0x8888_7700, X.UC_X86_REG_R9: ent, X.UC_X86_REG_R15: 0xF5,
                            X.UC_X86_REG_RSP: STACK + 0x8000, X.UC_X86_REG_RAX: 0x5555_0000_1234}
                    for r, v in vals.items():
                        mu.reg_write(r, v)
                    mu.emu_start(CODE, RESUME + 1, count=100 * STEP_FACTOR)
                    flyer = fc_self or bool(fc_parent)
                    want = BL if (mode == 1 and flyer) else (1 if layer in (1, 2) or flags & 2 else BL)
                    r8 = mu.reg_read(X.UC_X86_REG_R8)
                    cnt = struct.unpack("<I", bytes(mu.mem_read(BUF + THROUGHS_AT, 4)))[0]
                    bad = [r for r in keep if mu.reg_read(r) != vals[r]]
                    if (mu.reg_read(X.UC_X86_REG_RIP) != RESUME + 1 or r8 & 0xFF != want or r8 >> 8 != 0x8888_77
                            or bad or cnt != (1 if mode == 1 and flyer else 0)):
                        fails.append(f"through mode {mode} self {fc_self} parent {fc_parent} layer {layer} "
                                     f"flags {flags:#x}: r8 {r8:#x} want {want:#x} count {cnt} changed {bad}")
    return fails, n


def _ret_or_pass(name, code, build, want_ret):
    """Run ``code`` whose mover is set up by ``build(mu, obj)``; it must return
    to the caller (want_ret) or fall through to the cave end. -> (ok, why)."""
    from unicorn import UcError, x86_const as X
    CODE, BUF, STACK, OBJ, RET = 0x100000, 0x200000, 0x400000, 0x500000, 0x130000
    mu = _uc()
    for base, size in ((CODE, 0x1000), (BUF, 0x2000), (STACK, 0x10000), (OBJ, 0x10000), (RET, 0x1000)):
        mu.mem_map(base, size)
    mu.mem_write(CODE, _fill(code, BUF) + b"\x90")
    mu.mem_write(RET, b"\x90")
    mu.mem_write(BUF + SKIP_SPEED_AT, struct.pack("<f", SKIP_SPEED))
    rcx, mode = build(mu, OBJ, BUF)
    rsp = STACK + 0x8000
    mu.mem_write(rsp, struct.pack("<Q", RET))
    contact = name == "dv_contact"
    vals = {X.UC_X86_REG_RCX: rcx, X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_RBX: 0xB1,
            X.UC_X86_REG_RBP: 0xB2, X.UC_X86_REG_RSI: 0xB3, X.UC_X86_REG_RDI: 0xB4, X.UC_X86_REG_R12: 0xC1,
            X.UC_X86_REG_R15: 0xC4, X.UC_X86_REG_R8: 0x8E8E, X.UC_X86_REG_RDX: OBJ + 0xF000 if contact else 0xD5,
            X.UC_X86_REG_EFLAGS: 0x202,
            X.UC_X86_REG_XMM0: 0x1111_2222_3333_4444_5555_6666_7777_8888,
            X.UC_X86_REG_XMM1: 0x9999_AAAA_BBBB_CCCC_DDDD_EEEE_FFFF_0000}
    if name in ("dv_keep", "dv_contact"):
        vals.update({X.UC_X86_REG_RAX: 0xAAAA, X.UC_X86_REG_R10: 0x1010, X.UC_X86_REG_R11: 0x1111})
    for r, v in vals.items():
        mu.reg_write(r, v)
    end = CODE + len(code)
    fault = None
    try:
        mu.emu_start(CODE, RET if want_ret else end, count=200 * STEP_FACTOR)
    except UcError as e:              # the cave went the other way: a failing case, reported below
        fault = str(e)
    rip, rsp_after = mu.reg_read(X.UC_X86_REG_RIP), mu.reg_read(X.UC_X86_REG_RSP)
    counter = {"dv_skip": SKIPPED_AT, "dv_contact": CONTACT_AT}.get(name, KEPT_AT)
    cnt = struct.unpack("<I", bytes(mu.mem_read(BUF + counter, 4)))[0]
    bad = [r for r in vals if r != X.UC_X86_REG_RSP and mu.reg_read(r) != vals[r]
           and not (name == "dv_skip" and r == X.UC_X86_REG_RAX)]
    ok = ((rip == RET and rsp_after == rsp + 8 and cnt == 1) if want_ret
          else (rip == end and rsp_after == rsp and cnt == 0))
    return ok and not bad and not fault, f"rip {rip:#x} rsp {rsp_after - rsp:+d} count {cnt} changed {bad} {fault or ''}"


def _mover(mu, ent, flyer, state, vel, layer=0):
    mu.mem_write(ent + FC_OFF, struct.pack("<Q", 0x77 if flyer else 0))
    mu.mem_write(ent + STATE_OFF, struct.pack("<i", state))
    mu.mem_write(ent + VEL_OFF, struct.pack("<fff", vel[0], 0.0, vel[1]))
    mu.mem_write(ent + LAYER_OFF, struct.pack("<i", layer))


NAN = float("nan")
# (mode, flyer, state, velocity, want the early return); the third is the
# landing tick measured in KS2_dragon (+0x23c 0, velocity still 15 m/s)
FAST_CASES = ((1, True, 30, FAST, True), (1, True, 33, (0.28, -11.35), True), (1, True, 30, (-10.6, -10.6), True),
              (1, True, 30, (0.0, 0.0), False), (1, True, 30, SLOW, False), (1, True, 33, (0.0, 0.0), False),
              (1, True, 55, FAST, False), (1, False, 30, FAST, False), (0, True, 30, FAST, False),
              (1, True, 30, (NAN, 3.0), False),
              # [AIR-DIVE-BRACE-W1] the storm dragon's touchdown tick (state 0, 12.5 m/s, on the ground)
              (1, True, 0, (-0.38, -12.48), True), (1, True, 0, (0.0, 0.0), False))
# [AIR-DIVE-BRACE-W1] (case, layer): state 0 in the air is not the landing tick
KEEP_LAYER_CASES = (((1, True, 0, (-0.38, -12.48), False), 2), ((1, True, 0, (-0.38, -12.48), False), 1),
                    ((1, True, 30, FAST, True), 2), ((1, True, 0, (-0.38, -12.48), True), 0))


# [AIR-DIVE-RELEASE-W1] (attack slot, scalar speed +0x1c8) for FAST_CASES, plus
# the moving-attack exception: (case, slot, scalar speed, want the early return)
SKIP_EXTRA = (((1, True, 30, FAST, None), 484, 15.0, False),     # genuinely moving: the strike goes ahead
              ((1, True, 30, FAST, None), 488, 15.0, False),
              ((1, True, 30, FAST, None), 489, 15.0, True),      # a jump attack is not a moving attack
              ((1, True, 30, FAST, None), 457, 15.0, True),      # a standing attack still waits
              ((1, True, 30, FAST, None), 484, 0.0, True),       # the landing tick (scalar 0)
              ((1, True, 30, FAST, None), 484, 1.5, True),
              ((1, True, 33, FAST, None), 484, 11.0, False),     # state 33 too (run Q1_mant)
              ((1, True, 55, FAST, None), 484, 11.0, False),     # an action: dv_skip passes it as before
              ((1, True, 30, FAST, None), 483, 15.0, True),
              ((1, True, 30, FAST, None), 484, -15.0, True))


def check_skip(code):
    fails, n = [], 0
    cases = [(c, 457, 0.0, c[4]) for c in FAST_CASES] + [
        ((m, f, st, v, None), slot, sp, want) for (m, f, st, v, _w), slot, sp, want in SKIP_EXTRA]
    for via_parent in (False, True):
        for (mode, flyer, state, vel, _w), slot, scalar, want in cases:
            n += 1

            def build(mu, obj, buf):
                ctx, attack, ent, parent = obj + 0x100, obj + 0x200, obj + 0x1000, obj + 0x3000
                mu.mem_write(buf + MODE_AT, struct.pack("<I", mode))
                mu.mem_write(ctx + 8, struct.pack("<Q", attack))
                mu.mem_write(attack, struct.pack("<Q", ent))
                mu.mem_write(attack + 8, struct.pack("<H", slot))
                mu.mem_write(ent + PARENT_OFF, struct.pack("<Q", parent if via_parent else 0))
                mover = parent if via_parent else ent
                _mover(mu, mover, flyer, state, vel)
                mu.mem_write(mover + SPEED_OFF, struct.pack("<f", scalar))
                return ctx, mode
            ok, why = _ret_or_pass("dv_skip", code, build, want)
            if not ok:
                fails.append(f"skip mode {mode} parent {via_parent} flyer {flyer} state {state} vel {vel} "
                             f"slot {slot} scalar {scalar}: {why}")
    return fails, n


def check_keep(code):
    fails, n = [], 0
    for (mode, flyer, state, vel, want), layer in [(c, 0) for c in FAST_CASES] + list(KEEP_LAYER_CASES):
        n += 1

        def build(mu, obj, buf):
            ent = obj + 0x1000
            mu.mem_write(buf + MODE_AT, struct.pack("<I", mode))
            _mover(mu, ent, flyer, state, vel, layer)
            return ent, mode
        ok, why = _ret_or_pass("dv_keep", code, build, want)
        if not ok:
            fails.append(f"keep mode {mode} flyer {flyer} state {state} vel {vel} layer {layer}: {why}")
    return fails, n


def check_contact(code):
    """[AIR-DIVE-BRACE-W1] dv_contact returns at once (counted) only for a flyer (own or ridden)
    that is on the ground, still in flight movement and fast; everything else falls through."""
    fails, n = [], 0
    # (case from FAST_CASES, layer, flight mode)
    cases = ([(c, 0, 4) for c in FAST_CASES]
             + [((1, True, 30, FAST, False), 2, 4), ((1, True, 30, FAST, False), 1, 4),
                ((1, True, 30, FAST, False), 0, 0), ((1, True, 33, FAST, True), 0, 6),
                ((1, True, 0, (-0.38, -12.48), False), 2, 4)])
    for via_parent in (False, True):
        for (mode, flyer, state, vel, want), layer, flymode in cases:
            n += 1

            def build(mu, obj, buf):
                ent, parent = obj + 0x1000, obj + 0x3000
                mu.mem_write(buf + MODE_AT, struct.pack("<I", mode))
                mu.mem_write(ent + PARENT_OFF, struct.pack("<Q", parent if via_parent else 0))
                mover = parent if via_parent else ent
                _mover(mu, mover, flyer, state, vel, layer)
                mu.mem_write(mover + FLYMODE_OFF, struct.pack("<i", flymode))
                return ent, mode
            ok, why = _ret_or_pass("dv_contact", code, build, want)
            if not ok:
                fails.append(f"contact mode {mode} parent {via_parent} flyer {flyer} state {state} vel {vel} "
                             f"layer {layer} flight {flymode}: {why}")
    # a null body falls through
    n += 1
    ok, why = _ret_or_pass("dv_contact", code, lambda mu, obj, buf: (mu.mem_write(buf + MODE_AT, struct.pack(
        "<I", 1)), (0, 1))[1], False)
    if not ok:
        fails.append(f"contact null body: {why}")
    return fails, n


def check_call_skip(name, code):
    """[AIR-DIVE-RELEASE-W1] mode 1 + a fast moving flyer (own, or the flyer
    the entity rides): the callee is not called, the counter rises, it
    resumes; otherwise the callee is called once with the original arguments
    (the redone instructions included) and it resumes. Callee-saved
    registers, xmm0 / xmm1 / xmm6 / xmm7 and rsp come back unchanged."""
    from unicorn import UC_HOOK_CODE, UcError
    from unicorn import x86_const as X
    CODE, RESUME, ORIG, BUF, STACK, OBJ = 0x100000, 0x120000, 0x130000, 0x200000, 0x400000, 0x500000
    c = CALL_SITES[name]
    keep = (X.UC_X86_REG_RBX, X.UC_X86_REG_RSI, X.UC_X86_REG_RDI, X.UC_X86_REG_RBP, X.UC_X86_REG_R12,
            X.UC_X86_REG_R15, X.UC_X86_REG_XMM0, X.UC_X86_REG_XMM1, X.UC_X86_REG_XMM6, X.UC_X86_REG_XMM7)
    fails, n = [], 0
    # (layer, flight mode): only a landed flyer still in flight movement is held
    cases = [(c_, 0, 4) for c_ in FAST_CASES] + [((1, True, 30, FAST, False), 2, 4),
                                                 ((1, True, 30, FAST, False), 0, 0),
                                                 ((1, True, 33, FAST, True), 0, 6)]
    for via_parent in (False, True):
        for (mode, flyer, state, vel, want_skip), layer, flymode in cases:
            n += 1
            mu = _uc()
            for base, size in ((CODE, 0x1000), (RESUME, 0x1000), (ORIG, 0x1000), (BUF, 0x2000),
                               (STACK, 0x10000), (OBJ, 0x10000)):
                mu.mem_map(base, size)
            mu.mem_write(CODE, _fill(code, BUF, RESUME, ORIG))
            mu.mem_write(RESUME, b"\x90")
            mu.mem_write(ORIG, b"\xc3")          # the callee: returns at once
            mu.mem_write(BUF + MODE_AT, struct.pack("<I", mode))
            mu.mem_write(BUF + SKIP_SPEED_AT, struct.pack("<f", SKIP_SPEED))
            ent, parent, order, frame = OBJ + 0x1000, OBJ + 0x3000, OBJ + 0x5000, STACK + 0x6000
            mu.mem_write(order + 8, struct.pack("<Q", ent))
            mu.mem_write(ent + PARENT_OFF, struct.pack("<Q", parent if via_parent else 0))
            _mover(mu, parent if via_parent else ent, flyer, state, vel)
            mover = parent if via_parent else ent
            mu.mem_write(mover + LAYER_OFF, struct.pack("<i", layer))
            mu.mem_write(mover + FLYMODE_OFF, struct.pack("<i", flymode))
            rsp = STACK + 0x8000
            vals = {X.UC_X86_REG_RCX: ent if c["entity"] == "rcx" else order, X.UC_X86_REG_RSP: rsp,
                    X.UC_X86_REG_RDI: ent if c["entity"] == "rdi" else order, X.UC_X86_REG_R8: 0x8E8E, X.UC_X86_REG_RBX: order if name == "dv_tick_move" else 0xB1,
                    X.UC_X86_REG_XMM3: 0x41200000,
                    X.UC_X86_REG_RSI: ent if c["entity"] == "rsi" else 0x5E5,
                    X.UC_X86_REG_RBP: frame, X.UC_X86_REG_R12: 0xC1, X.UC_X86_REG_R15: 0xC4,
                    X.UC_X86_REG_RAX: 0xFEED, X.UC_X86_REG_RDX: 0xD5, X.UC_X86_REG_R9: 0x99,
                    X.UC_X86_REG_XMM0: 0x41700000, X.UC_X86_REG_XMM1: 0x9999_AAAA,
                    X.UC_X86_REG_XMM2: 0x1234, X.UC_X86_REG_XMM6: 0x6666, X.UC_X86_REG_XMM7: 0x7777}
            for r, v in vals.items():
                mu.reg_write(r, v)
            calls = []

            def on_call(uc, _addr, _size, _data, calls=calls):
                calls.append((uc.reg_read(X.UC_X86_REG_RCX), uc.reg_read(X.UC_X86_REG_RDX),
                              uc.reg_read(X.UC_X86_REG_R9), uc.reg_read(X.UC_X86_REG_XMM2),
                              uc.reg_read(X.UC_X86_REG_RSP), uc.reg_read(X.UC_X86_REG_R8)))
            mu.hook_add(UC_HOOK_CODE, on_call, begin=ORIG, end=ORIG)
            fault = None
            try:
                mu.emu_start(CODE, RESUME + 1, count=300 * STEP_FACTOR)
            except UcError as exc:            # a fault is a failing case, reported below
                fault = str(exc)
            cnt = struct.unpack("<I", bytes(mu.mem_read(BUF + c["counter"], 4)))[0]
            bad = [r for r in keep if mu.reg_read(r) != vals[r]]
            want_args = {"dv_engage": (ent, 0xFEED, 0x99, 0x7777), "dv_reorder": (ent, 0xD5, 0x5E5, 0x1234),
                         "dv_reorder_move": (order, 0xD5, 0x99, 0x1234),
                         "dv_attack_move": (ent, 0xFEED, 0, 0x6666),
                         "dv_tick_move": (order, 0xD5, 0x99, 0x1234),
                         "dv_settle": (ent, 0xFEED, 0x99, 0x1234)}[name]
            stored = struct.unpack("<f", bytes(mu.mem_read(frame + 0x14, 4)))[0]
            ok = (mu.reg_read(X.UC_X86_REG_RIP) == RESUME + 1 and mu.reg_read(X.UC_X86_REG_RSP) == rsp
                  and not bad and not fault)
            if want_skip:
                ok = ok and cnt == 1 and not calls
            else:
                ok = (ok and cnt == 0 and len(calls) == 1 and calls[0][:4] == want_args
                      and calls[0][4] == rsp - 8)
            if name == "dv_reorder_move" and stored != 15.0:
                ok = False
            if name == "dv_tick_move" and struct.unpack("<f", bytes(mu.mem_read(rsp + 0x74, 4)))[0] != 10.0:
                ok = False
            if name == "dv_settle" and calls and calls[0][5] != 0:      # the redone xor r8d, r8d
                ok = False
            if not ok:
                fails.append(f"{name} mode {mode} parent {via_parent} flyer {flyer} state {state} vel {vel} "
                             f"layer {layer} flight {flymode}: "
                             f"count {cnt} calls {calls} changed {bad} {fault or ''}")
    return fails, n


def _window_rig(hold_code, through_code):
    """[AIR-DIVE-BRACE-W1 round 3] One machine, one buffer, both caves: the slide table must persist from
    call to call. -> (mu, hold(ent, x, z) -> 'held' / 'passed' / why, through(ent, layer), buffer)."""
    from unicorn import UC_HOOK_CODE, UcError
    from unicorn import x86_const as X
    HOLD, THR, RESUME, BUF, STACK, OBJ, RET = 0x100000, 0x110000, 0x120000, 0x200000, 0x400000, 0x500000, 0x130000
    mu = _uc()
    for base, size in ((HOLD, 0x1000), (THR, 0x1000), (RESUME, 0x1000), (BUF, 0x2000), (STACK, 0x10000),
                       (OBJ, 0x10000), (RET, 0x1000)):
        mu.mem_map(base, size)
    mu.mem_write(HOLD, _fill(hold_code, BUF) + b"\x90")
    mu.mem_write(THR, _fill(through_code, BUF, RESUME) + b"\x90")
    mu.mem_write(RET, b"\x90")
    mu.mem_write(RESUME, b"\x90")
    mu.mem_write(BUF + MODE_AT, struct.pack("<I", 1))
    mu.mem_write(BUF + SKIP_SPEED_AT, struct.pack("<f", SKIP_SPEED))
    end = HOLD + len(hold_code)
    stop = {}

    def on_code(uc, addr, _size, _data):
        stop["at"] = addr
        uc.emu_stop()
    for at in (RET, end, RESUME):
        mu.hook_add(UC_HOOK_CODE, on_code, begin=at, end=at)
    keep = (X.UC_X86_REG_RAX, X.UC_X86_REG_RBX, X.UC_X86_REG_RCX, X.UC_X86_REG_RDX, X.UC_X86_REG_RSI,
            X.UC_X86_REG_RDI, X.UC_X86_REG_RBP, X.UC_X86_REG_R8, X.UC_X86_REG_R9, X.UC_X86_REG_R10,
            X.UC_X86_REG_R11, X.UC_X86_REG_R12, X.UC_X86_REG_R15, X.UC_X86_REG_XMM0, X.UC_X86_REG_XMM1)

    params = OBJ + 0xF000

    def hold(ent, x, z, body=0):
        mu.mem_write(ent + POS_OFF, struct.pack("<f", x))
        mu.mem_write(ent + POS_OFF + 8, struct.pack("<f", z))
        mu.mem_write(params + BODY_OFF, struct.pack("<Q", body))
        rsp = STACK + 0x8000
        mu.mem_write(rsp, struct.pack("<Q", RET))
        vals = {r: 0x1000 + i for i, r in enumerate(keep)}
        vals[X.UC_X86_REG_RCX] = ent
        vals[X.UC_X86_REG_RDX] = params
        vals[X.UC_X86_REG_XMM0] = 0x1111_2222_3333_4444_5555_6666_7777_8888
        vals[X.UC_X86_REG_XMM1] = 0x9999_AAAA_BBBB_CCCC_DDDD_EEEE_FFFF_0000
        for r, v in vals.items():
            mu.reg_write(r, v)
        mu.reg_write(X.UC_X86_REG_RSP, rsp)
        mu.reg_write(X.UC_X86_REG_EFLAGS, 0x202)
        stop.clear()
        try:
            mu.emu_start(HOLD, 0, count=8000 * STEP_FACTOR)
        except UcError as exc:        # a fault is a failing case, reported by the caller
            return f"fault {exc}"
        bad = [r for r in vals if mu.reg_read(r) != vals[r]]
        if bad:
            return f"changed {bad}"
        if stop.get("at") == RET and mu.reg_read(X.UC_X86_REG_RSP) == rsp + 8:
            return "held"
        if stop.get("at") == end and mu.reg_read(X.UC_X86_REG_RSP) == rsp:
            return "passed"
        return f"stopped at {stop.get('at')} rsp {mu.reg_read(X.UC_X86_REG_RSP) - rsp:+d}"

    def through(ent, layer):
        mu.mem_write(ent + LAYER_OFF, struct.pack("<i", layer))
        for r, v in ((X.UC_X86_REG_R9, ent), (X.UC_X86_REG_RDI, OBJ + 0x9000), (X.UC_X86_REG_RBX, 0x5A),
                     (X.UC_X86_REG_RSP, STACK + 0x8000)):
            mu.reg_write(r, v)
        stop.clear()
        try:
            mu.emu_start(THR, 0, count=4000 * STEP_FACTOR)
        except UcError:               # a fault is a failing case: the caller sees False
            return False
        mu.mem_write(ent + LAYER_OFF, struct.pack("<i", 0))
        return stop.get("at") == RESUME
    return mu, hold, through, BUF


def _released(mu, buf):
    return struct.unpack("<I", bytes(mu.mem_read(buf + RELEASED_AT, 4)))[0]


def _slot_keys(mu, buf):
    raw = bytes(mu.mem_read(buf + SLIDE_AT, SLIDE_SLOTS * 16))
    return [struct.unpack_from("<Q", raw, i * 16)[0] for i in range(SLIDE_SLOTS)]


def check_window(hold_code, through_code):
    """[AIR-DIVE-BRACE-W1 round 3] The slide window, through dv_keep (rcx = the flyer): held within
    SLIDE_RELEASE_M of the first hold, released for good past it (counted once), a fresh window after an
    airborne charge (dv_through on the same flyer, not a ground one), flyers independent, a full table
    passes uncounted, and every register comes back on both exits."""
    fails, n = [], 0
    mu, hold, through, buf = _window_rig(hold_code, through_code)
    a, b = 0x501000, 0x503000
    for ent in (a, b):
        _mover(mu, ent, True, 30, FAST)
    r = SLIDE_RELEASE_M
    steps = [("a first hold", a, 3.0, 4.0, "held", 0), ("a 14 m out", a, 13.0, 14.0, "held", 0),
             ("b first hold far away", b, 300.0, 300.0, "held", 0),
             ("a just inside", a, 3.0 + r * 0.99, 4.0, "held", 0),
             ("a just past", a, 3.0 + r * 0.6, 4.0 + r * 0.81, "passed", 1),
             ("a back near the start: released for good", a, 3.0, 4.0, "passed", 1),
             ("b still inside its own window", b, 310.0, 300.0, "held", 1)]
    for label, ent, x, z, want, rel in steps:
        n += 1
        got = hold(ent, x, z)
        if got != want or _released(mu, buf) != rel:
            fails.append(f"window {label}: {got} released {_released(mu, buf)} (want {want}, {rel})")
    n += 1
    if not through(a, 0) or a not in [k & ~1 for k in _slot_keys(mu, buf)]:
        fails.append("window: a ground charge (layer 0) must not clear the entry")
    n += 1
    if not through(a, 2) or a in [k & ~1 for k in _slot_keys(mu, buf)] or 2 not in _slot_keys(mu, buf):
        fails.append("window: an airborne charge must tombstone the flyer's entry")
    for label, ent, x, z, want, rel in (("a new window after the air charge", a, 100.0, 100.0, "held", 1),
                                        ("a 15 m into the new window", a, 115.0, 100.0, "held", 1),
                                        ("a past the new window", a, 125.0, 100.0, "passed", 2)):
        n += 1
        got = hold(ent, x, z)
        if got != want or _released(mu, buf) != rel:
            fails.append(f"window {label}: {got} released {_released(mu, buf)} (want {want}, {rel})")
    # an airborne hold (state 30, layer 2) holds and leaves the table alone; the window starts on the ground
    c = 0x505000
    _mover(mu, c, True, 30, FAST, layer=2)
    n += 1
    got = hold(c, 500.0, 500.0)
    if got != "held" or c in [k & ~1 for k in _slot_keys(mu, buf)]:
        fails.append(f"window airborne hold: {got}, in the table {c in [k & ~1 for k in _slot_keys(mu, buf)]}")
    mu.mem_write(c + LAYER_OFF, struct.pack("<i", 0))
    for label, x, want, rel in (("c lands 30 m on", 530.0, "held", 2), ("c 15 m on the ground", 545.0, "held", 2),
                                ("c 21 m on the ground", 551.0, "passed", 3)):
        n += 1
        got = hold(c, x, 500.0)
        if got != want or _released(mu, buf) != rel:
            fails.append(f"window {label}: {got} released {_released(mu, buf)} (want {want}, {rel})")
    # a full table (no empty slot, no tombstone): a new flyer passes, uncounted
    mu2, hold2, _thr2, buf2 = _window_rig(hold_code, through_code)
    mu2.mem_write(buf2 + SLIDE_AT, b"".join(struct.pack("<QQ", 0x7000_0000 + 0x10 * (i + 1), 0)
                                            for i in range(SLIDE_SLOTS)))
    _mover(mu2, a, True, 30, FAST)
    n += 1
    got = hold2(a, 0.0, 0.0)
    if got != "passed" or _released(mu2, buf2) != 0:
        fails.append(f"window full table: {got} released {_released(mu2, buf2)} (want passed, 0)")
    return fails, n


def check_window_ridden(contact_code, through_code):
    """[AIR-DIVE-BRACE-W1 round 3] A rider (dv_contact, rcx = the rider): the window is keyed on the
    mount; released past the radius; and an airborne charge of the rider (dv_through) clears the mount's
    entry."""
    fails, n = [], 0
    mu, hold, through, buf = _window_rig(contact_code, through_code)
    rider, mount = 0x501000, 0x503000
    mu.mem_write(rider + PARENT_OFF, struct.pack("<Q", mount))
    _mover(mu, mount, True, 30, FAST)
    mu.mem_write(mount + FLYMODE_OFF, struct.pack("<i", 4))

    def at(x, z):
        mu.mem_write(mount + POS_OFF, struct.pack("<f", x))
        mu.mem_write(mount + POS_OFF + 8, struct.pack("<f", z))
        return hold(rider, 0.0, 0.0)          # the rider's own position must not matter
    n += 1
    got = at(0.0, 0.0)
    keys = [k & ~1 for k in _slot_keys(mu, buf)]
    if got != "held" or mount not in keys or rider in keys:
        fails.append(f"window ridden: {got}, keyed on the mount {mount in keys}, on the rider {rider in keys}")
    for label, x, want, rel in (("mount 15 m", 15.0, "held", 0), ("mount past", 25.0, "passed", 1),
                                ("mount back: released", 1.0, "passed", 1)):
        n += 1
        got = at(x, 0.0)
        if got != want or _released(mu, buf) != rel:
            fails.append(f"window ridden {label}: {got} released {_released(mu, buf)} (want {want}, {rel})")
    n += 1
    if not through(rider, 2) or mount in [k & ~1 for k in _slot_keys(mu, buf)]:
        fails.append("window ridden: the rider's airborne charge must clear the mount's entry")
    n += 1
    got = at(1.0, 0.0)
    if got != "held":
        fails.append(f"window ridden after the air charge: {got} (want held)")
    return fails, n


def _counter(mu, buf, at):
    return struct.unpack("<I", bytes(mu.mem_read(buf + at, 4)))[0]


def check_engaged(contact_code, through_code):
    """[FLYER-FIX-1117] dv_contact + dv_through on one buffer. A body already in melee (+0x324 1) whose
    target belongs to another unit is not carried: the engage goes through, counted, and the window closes.
    A body in melee with the flyer's own unit (this charge's own contact) or not in melee is carried. The
    first engage the engine takes ends the window for good, so a ground re-charge from that melee is never
    held; an air re-charge ordered while engaged keeps it closed, a fresh air charge opens a new one."""
    fails, n = [], 0
    mu, hold, through, buf = _window_rig(contact_code, through_code)
    obj = 0x500000
    f, g, e, t_other, t_own = obj + 0x1000, obj + 0x3000, obj + 0x5000, obj + 0x7000, obj + 0x9000
    unit_f, unit_x = 0x6600_0000, 0x7700_0000
    for ent in (f, g):
        _mover(mu, ent, True, 30, FAST)
        mu.mem_write(ent + FLYMODE_OFF, struct.pack("<i", 4))
        mu.mem_write(ent + UNIT_OFF, struct.pack("<Q", unit_f))
    mu.mem_write(t_other + UNIT_OFF, struct.pack("<Q", unit_x))
    mu.mem_write(t_own + UNIT_OFF, struct.pack("<Q", unit_f))

    def body(state, target):
        mu.mem_write(e + MELEE_OFF, struct.pack("<i", state))
        mu.mem_write(e + ORDER_TARGET_OFF, struct.pack("<Q", target))
        return e

    def speed(ent, fast):
        v = FAST if fast else SLOW
        mu.mem_write(ent + VEL_OFF, struct.pack("<fff", v[0], 0.0, v[1]))

    def step(label, got, want, counts):
        nonlocal n
        n += 1
        have = {k: _counter(mu, buf, at) for k, at in (("contact", CONTACT_AT), ("body", ENGAGED_BODY_AT),
                                                       ("closed", CLOSED_AT), ("released", RELEASED_AT))}
        if got != want or any(have[k] != v for k, v in counts.items()):
            fails.append(f"engaged {label}: {got} {have} (want {want}, {counts})")
    # a fresh landing: free bodies, and bodies fighting this flyer's own unit, are carried
    step("fresh: a free body", hold(f, 0.0, 0.0, body(0, 0)), "held", {"contact": 1, "body": 0, "closed": 0})
    step("fresh: no body", hold(f, 1.0, 0.0, 0), "held", {"contact": 2})
    step("fresh: a body fighting this unit", hold(f, 2.0, 0.0, body(1, t_own)), "held", {"contact": 3, "body": 0})
    step("fresh: a body in another state", hold(f, 3.0, 0.0, body(0x13, t_other)), "held", {"contact": 4, "body": 0})
    step("fresh: engaged, no target", hold(f, 3.5, 0.0, body(1, 0)), "held", {"contact": 5, "body": 0})
    # a body locked in melee with another unit: not carried, the window ends
    step("a body fighting another unit", hold(f, 4.0, 0.0, body(1, t_other)), "passed",
         {"contact": 5, "body": 1, "closed": 1})
    step("then a free body: window closed", hold(f, 5.0, 0.0, body(0, 0)), "passed",
         {"contact": 5, "body": 1, "closed": 1})
    # a second flyer: blocked (slow) -> the engine engages -> window closed; a ground re-charge is not held
    step("g first hold", hold(g, 100.0, 0.0, body(0, 0)), "held", {"contact": 6, "closed": 1})
    speed(g, False)
    step("g slowed: the engine engages", hold(g, 104.0, 0.0, body(0, 0)), "passed", {"contact": 6, "closed": 2})
    speed(g, True)
    n += 1
    if not through(g, 0):
        fails.append("engaged: a ground re-charge must resume")
    step("g ground re-charge into its melee", hold(g, 106.0, 0.0, body(1, t_own)), "passed",
         {"contact": 6, "closed": 2, "released": 0})
    # an air re-charge ordered while engaged keeps the window closed
    mu.mem_write(g + MELEE_OFF, struct.pack("<i", 1))
    n += 1
    if not through(g, 2):
        fails.append("engaged: an air re-charge must resume")
    mu.mem_write(g + MELEE_OFF, struct.pack("<i", 0))
    step("g lands from a re-charge out of melee", hold(g, 130.0, 0.0, body(0, 0)), "passed",
         {"contact": 6, "closed": 2})
    # a fresh air charge (not engaged) opens a new window
    n += 1
    if not through(g, 2):
        fails.append("engaged: a fresh air charge must resume")
    step("g lands from a fresh charge", hold(g, 200.0, 0.0, body(0, 0)), "held", {"contact": 7, "closed": 2})
    # a flyer that engaged without ever being held gets a closed entry: its later fast contacts are not held
    h = obj + 0xB000
    _mover(mu, h, True, 30, SLOW)
    mu.mem_write(h + FLYMODE_OFF, struct.pack("<i", 4))
    step("h slow first engage", hold(h, 300.0, 0.0, body(0, 0)), "passed", {"contact": 7, "closed": 3})
    n += 1
    if (h | 1) not in _slot_keys(mu, buf):
        fails.append("engaged: a flyer engaging with no entry must get a released one")
    speed(h, True)
    step("h fast again: not held", hold(h, 301.0, 0.0, body(0, 0)), "passed", {"contact": 7, "closed": 3})
    # a landed ground mover (+0x710 0) engaging closes its window too
    k = obj + 0xD000
    _mover(mu, k, True, 30, FAST)
    step("k ground mover engages", hold(k, 400.0, 0.0, body(0, 0)), "passed", {"contact": 7, "closed": 4})
    # an airborne flyer and a ground unit never touch the table
    a, u = obj + 0xE000, obj + 0xE800
    _mover(mu, a, True, 30, FAST, layer=2)
    mu.mem_write(a + FLYMODE_OFF, struct.pack("<i", 4))
    _mover(mu, u, False, 30, FAST)
    before = _slot_keys(mu, buf)
    step("airborne contact", hold(a, 0.0, 0.0, body(1, t_other)), "passed", {"body": 1, "closed": 4})
    step("ground unit contact", hold(u, 0.0, 0.0, body(1, t_other)), "passed", {"body": 1, "closed": 4})
    n += 1
    if _slot_keys(mu, buf) != before:
        fails.append("engaged: an airborne flyer or a ground unit changed the table")
    return fails, n


def check_engaged_ridden(contact_code, through_code):
    """[FLYER-FIX-1117] A rider (rcx) on a flying mount: the engaged-body test reads the rider's unit, the
    closed window is the mount's, and a rider's air re-charge out of melee keeps the mount's window closed."""
    fails, n = [], 0
    mu, hold, through, buf = _window_rig(contact_code, through_code)
    rider, mount, e, t = 0x501000, 0x503000, 0x505000, 0x507000
    mu.mem_write(rider + PARENT_OFF, struct.pack("<Q", mount))
    mu.mem_write(rider + UNIT_OFF, struct.pack("<Q", 0x6600_0000))
    _mover(mu, mount, True, 30, FAST)
    mu.mem_write(mount + FLYMODE_OFF, struct.pack("<i", 4))
    mu.mem_write(t + UNIT_OFF, struct.pack("<Q", 0x6600_0000))
    mu.mem_write(e + MELEE_OFF, struct.pack("<i", 1))
    mu.mem_write(e + ORDER_TARGET_OFF, struct.pack("<Q", t))
    n += 1
    got = hold(rider, 0.0, 0.0, e)
    if got != "held":
        fails.append(f"engaged ridden: a body fighting the rider's own unit: {got} (want held)")
    mu.mem_write(t + UNIT_OFF, struct.pack("<Q", 0x7700_0000))
    n += 1
    got = hold(rider, 0.0, 0.0, e)
    keys = _slot_keys(mu, buf)
    if got != "passed" or (mount | 1) not in keys or any(k & ~1 == rider for k in keys):
        fails.append(f"engaged ridden: a body fighting another unit: {got}, mount closed {(mount | 1) in keys}")
    # the rider re-charges in the air while engaged: the mount's entry stays closed
    mu.mem_write(rider + MELEE_OFF, struct.pack("<i", 1))
    n += 1
    if not through(rider, 2) or (mount | 1) not in _slot_keys(mu, buf):
        fails.append("engaged ridden: an air re-charge out of melee must keep the mount's window closed")
    mu.mem_write(rider + MELEE_OFF, struct.pack("<i", 0))
    n += 1
    if not through(rider, 2) or any(k & ~1 == mount for k in _slot_keys(mu, buf)):
        fails.append("engaged ridden: a fresh air charge must clear the mount's entry")
    # with no entry left, a re-charge out of melee writes a closed one for the mount, none for the rider
    mu.mem_write(rider + MELEE_OFF, struct.pack("<i", 1))
    n += 1
    keys = _slot_keys(mu, buf) if through(rider, 2) else []
    if (mount | 1) not in keys or any(k & ~1 == rider for k in keys):
        fails.append("engaged ridden: a re-charge out of melee with no entry must close the mount's window")
    mu.mem_write(rider + MELEE_OFF, struct.pack("<i", 0))
    return fails, n


def check_commit(code):
    """[AIR-DIVE-BRACE-W1 round 4] dv_commit: a controller on its landing approach (phase 4 / 5) within
    COMMIT_M of its landing height gets al = 0 (counted, the test not called); any other phase, a higher
    model, a null entity, or mode 0 calls the test once with the original arguments (rcx = rdi, rdx kept,
    r8 = [rbx + 0x38], r9b kept) and keeps its answer. Non-volatile registers and rsp come back."""
    from unicorn import UC_HOOK_CODE, UcError
    from unicorn import x86_const as X
    CODE, RESUME, ORIG, BUF, STACK, OBJ = 0x100000, 0x120000, 0x130000, 0x200000, 0x400000, 0x500000
    keep = (X.UC_X86_REG_RBX, X.UC_X86_REG_RSI, X.UC_X86_REG_RDI, X.UC_X86_REG_RBP, X.UC_X86_REG_R12,
            X.UC_X86_REG_R15, X.UC_X86_REG_XMM6, X.UC_X86_REG_XMM7)
    fails, n = [], 0
    # (mode, phase, height above the landing point, entity present, want the skip)
    cases = [(1, 4, 0.0, True, True), (1, 5, 1.7, True, True), (1, 5, COMMIT_M - 0.01, True, True),
             (1, 5, COMMIT_M + 0.01, True, False), (1, 4, 30.0, True, False), (1, 3, 0.5, True, False),
             (1, 6, 0.5, True, False), (1, 1, 0.0, True, False), (1, 2, 0.0, True, False),
             (0, 5, 1.0, True, False), (1, 5, 1.0, False, False), (1, 5, -0.5, True, True)]
    # (landing point, where dv_commit must leave it) for a model at (704.5, -101.25), radius 1.7: the
    # through-goal far ahead -> 6.7 m on the same line; already in the band (5 m on) -> kept; under the
    # model's edge (1 m on) -> 6.7 m on that line; exactly under the model -> kept (no direction)
    far = (718.0, -160.0)
    dx, dz = far[0] - 704.5, far[1] + 101.25
    k = 6.7 / (dx * dx + dz * dz) ** 0.5
    points = [(far, (704.5 + dx * k, -101.25 + dz * k)), ((704.5, -96.25), (704.5, -96.25)),
              ((705.5, -101.25), (704.5 + 6.7, -101.25)), ((704.5, -101.25), (704.5, -101.25))]
    for (mode, phase, dh, has_ent, want_skip), (pt, want_pt) in [(c_, p_) for c_ in cases for p_ in points]:
        pt = tuple(struct.unpack("<f", struct.pack("<f", v))[0] for v in pt)
        for answer in (0, 1):
            n += 1
            mu = _uc()
            for base, size in ((CODE, 0x1000), (RESUME, 0x1000), (ORIG, 0x1000), (BUF, 0x2000),
                               (STACK, 0x10000), (OBJ, 0x10000)):
                mu.mem_map(base, size)
            mu.mem_write(CODE, _fill(code, BUF, RESUME, ORIG))
            mu.mem_write(RESUME, b"\x90")
            mu.mem_write(ORIG, (b"\xb0\x01" if answer else b"\x30\xc0") + b"\xc3")   # mov al,1 / xor al,al; ret
            mu.mem_write(BUF + MODE_AT, struct.pack("<I", mode))
            fc, ent, order = OBJ + 0x1000, OBJ + 0x3000, OBJ + 0x5000
            mu.mem_write(fc, struct.pack("<Q", ent if has_ent else 0))
            mu.mem_write(fc + FC_LAND_Y_OFF, struct.pack("<f", 577.31))
            mu.mem_write(fc + FC_PHASE_OFF, struct.pack("<I", phase))
            mu.mem_write(ent + POS_Y_OFF, struct.pack("<f", 577.31 + dh))
            mu.mem_write(ent + POS_OFF, struct.pack("<f", 704.5))
            mu.mem_write(ent + POS_OFF + 8, struct.pack("<f", -101.25))
            mu.mem_write(ent + RADIUS_OFF, struct.pack("<f", 1.7))
            mu.mem_write(fc + FC_LAND_X_OFF, struct.pack("<f", pt[0]))
            mu.mem_write(fc + FC_LAND_Z_OFF, struct.pack("<f", pt[1]))
            mu.mem_write(order + 0x38, struct.pack("<Q", 0xC0FFEE))
            rsp = STACK + 0x8000
            vals = {X.UC_X86_REG_RDI: fc, X.UC_X86_REG_RBX: order, X.UC_X86_REG_RSP: rsp,
                    X.UC_X86_REG_RDX: order + 0x90, X.UC_X86_REG_R9: 0x01, X.UC_X86_REG_RCX: 0xBAD,
                    X.UC_X86_REG_R8: 0xBAD, X.UC_X86_REG_RAX: 0x5555_0000_0101, X.UC_X86_REG_RSI: 0x51,
                    X.UC_X86_REG_RBP: 0xB7, X.UC_X86_REG_R12: 0xC1, X.UC_X86_REG_R15: 0xF5,
                    X.UC_X86_REG_XMM6: 0x6666, X.UC_X86_REG_XMM7: 0x7777}
            for r, v in vals.items():
                mu.reg_write(r, v)
            calls = []
            mu.hook_add(UC_HOOK_CODE, lambda uc, _a, _s, _d, calls=calls: calls.append(
                (uc.reg_read(X.UC_X86_REG_RCX), uc.reg_read(X.UC_X86_REG_RDX), uc.reg_read(X.UC_X86_REG_R8),
                 uc.reg_read(X.UC_X86_REG_R9) & 0xFF, uc.reg_read(X.UC_X86_REG_RSP))), begin=ORIG, end=ORIG)
            fault = None
            try:
                mu.emu_start(CODE, RESUME + 1, count=200 * STEP_FACTOR)
            except UcError as exc:            # a fault is a failing case, reported below
                fault = str(exc)
            cnt = struct.unpack("<I", bytes(mu.mem_read(BUF + COMMITTED_AT, 4)))[0]
            al = mu.reg_read(X.UC_X86_REG_RAX) & 0xFF
            bad = [r for r in keep if mu.reg_read(r) != vals[r]]
            ok = (mu.reg_read(X.UC_X86_REG_RIP) == RESUME + 1 and mu.reg_read(X.UC_X86_REG_RSP) == rsp
                  and not bad and not fault)
            land = struct.unpack("<f", bytes(mu.mem_read(fc + FC_LAND_X_OFF, 4)))[0], \
                struct.unpack("<f", bytes(mu.mem_read(fc + FC_LAND_Z_OFF, 4)))[0]
            if want_skip:
                ok = ok and cnt == 1 and not calls and al == 0 and all(abs(a - b) < 1e-3 for a, b in zip(land, want_pt))
            else:
                ok = (ok and cnt == 0 and len(calls) == 1 and calls[0][:4] == (fc, order + 0x90, 0xC0FFEE, 1)
                      and calls[0][4] == rsp - 8 and al == answer and land == pt)
            if not ok:
                fails.append(f"commit mode {mode} phase {phase} dh {dh} entity {has_ent} answer {answer}: "
                             f"count {cnt} al {al} calls {calls} changed {bad} {fault or ''}")
    return fails, n


def _keep_and_window(code):
    f1, n1 = check_keep(code)
    f2, n2 = check_window(code, assemble("dv_through"))
    return f1 + f2, n1 + n2


def _through_and_window(code):
    f1, n1 = check_through(code)
    f2, n2 = check_window(assemble("dv_keep"), code)
    f3, n3 = check_window_ridden(assemble("dv_contact"), code)
    f4, n4 = check_engaged(assemble("dv_contact"), code)
    f5, n5 = check_engaged_ridden(assemble("dv_contact"), code)
    return f1 + f2 + f3 + f4 + f5, n1 + n2 + n3 + n4 + n5


def _contact_and_window(code):
    f1, n1 = check_contact(code)
    f2, n2 = check_window_ridden(code, assemble("dv_through"))
    f3, n3 = check_engaged(code, assemble("dv_through"))
    f4, n4 = check_engaged_ridden(code, assemble("dv_through"))
    return f1 + f2 + f3 + f4, n1 + n2 + n3 + n4


CHECKS = {"dv_through": _through_and_window, "dv_skip": check_skip, "dv_keep": _keep_and_window,
          "dv_engage": lambda code: check_call_skip("dv_engage", code),
          "dv_reorder": lambda code: check_call_skip("dv_reorder", code),
          "dv_reorder_move": lambda code: check_call_skip("dv_reorder_move", code),
          "dv_attack_move": lambda code: check_call_skip("dv_attack_move", code),
          "dv_tick_move": lambda code: check_call_skip("dv_tick_move", code),
          "dv_contact": _contact_and_window,
          "dv_settle": lambda code: check_call_skip("dv_settle", code),
          "dv_commit": check_commit}

# negative controls: each mutant must fail at least one case
MUTANTS = (
    ("through ignores the switch", "dv_through", "    jne orig\n    mov r11, qword ptr [r9 + 0x128]",
     "    nop\n    mov r11, qword ptr [r9 + 0x128]"),
    ("through keeps the flag", "dv_through", "    mov r8b, bl\n    jmp back", "    mov r8b, 1\n    jmp back"),
    ("through misses a ridden flyer", "dv_through", "    mov r11, qword ptr [r11 + 0x128]\n", "    mov r11, 0\n"),
    ("skip on the old scalar speed", "dv_skip", "movss xmm0, dword ptr [r11 + 0xe0]",
     "movss xmm0, dword ptr [r11 + 0x23c]"),
    ("skip on state 30 only", "dv_skip", "    je moving\n", "    jne pass\n"),
    ("skip ignores the speed", "dv_skip", "    lea rsp, [rsp + 32]\n    jbe pass\n",
     "    lea rsp, [rsp + 32]\n    nop\n"),
    ("skip lets every attack of a moving flyer through", "dv_skip", "    cmp eax, 4\n    jbe pass\n",
     "    jmp pass\n"),
    ("skip lets the landing tick through", "dv_skip", "    jl strict\n", "    nop\n"),
    ("keep for ground units too", "dv_keep", "    test rax, rax\n    je pass\n", "    test rax, rax\n    nop\n"),
    ("keep forgets xmm0", "dv_keep", "    movdqu xmm0, xmmword ptr [rsp]\n", ""),
    ("keep forgets the landed state 0", "dv_keep", "    cmp dword ptr [rcx + 0x26c], 0\n    jne pass\n",
     "    jmp pass\n"),
    ("keep holds state 0 in the air too", "dv_keep", "    cmp dword ptr [rcx + 0x104], 0\n    jne pass\nmoving:",
     "moving:"),
    ("engage forgets the landed state 0", "dv_engage", "    cmp dword ptr [r11 + 0x26c], 0\n    jne pass\n",
     "    jmp pass\n"),
    ("engage skips every call", "dv_engage", "    jbe pass\n", "    nop\n"),
    ("engage forgets xmm2", "dv_engage", "    movaps xmm2, xmm7\n", ""),
    ("engage misses a ridden flyer", "dv_engage", "    cmovne r11, rax\n", ""),
    ("engage in the air too", "dv_engage", "    cmp dword ptr [r11 + 0x104], 0\n    jne pass\n", ""),
    ("engage for ground movers too", "dv_engage", "    cmp dword ptr [r11 + 0x710], 0\n    je pass\n", ""),
    ("reorder forgets r9", "dv_reorder", "    mov r9d, esi\n", ""),
    ("reorder for ground units too", "dv_reorder", "    test rax, rax\n    je pass\n",
     "    test rax, rax\n    nop\n"),
    ("reorder move forgets the store", "dv_reorder_move", "    movss dword ptr [rbp + 0x14], xmm0\n", ""),
    ("attack move forgets the zero r9", "dv_attack_move", "    xor r9d, r9d\n", ""),
    ("attack move forgets the callee's entity", "dv_attack_move", "    mov rcx, rsi\n", ""),
    ("reorder move on the order, not its entity", "dv_reorder_move", "    mov r11, qword ptr [rdi + 8]\n",
     "    mov r11, rdi\n"),
    ("contact holds every body", "dv_contact", "    jbe pass\n", "    nop\n"),
    ("contact misses a ridden flyer", "dv_contact", "    cmovne r11, rax\n", ""),
    ("contact in the air too", "dv_contact", "    cmp dword ptr [r11 + 0x104], 0\n    jne pure\n    cmp dword ptr [r11 + 0x710]",
     "    cmp dword ptr [r11 + 0x710]"),
    ("contact for ground movers too", "dv_contact", "    cmp dword ptr [r11 + 0x710], 0\n    je pass\n", ""),
    ("contact for ground units too", "dv_contact", "    mov rax, qword ptr [r11 + 0x128]\n    test rax, rax\n    je pure\n",
     "    mov rax, qword ptr [r11 + 0x128]\n    test rax, rax\n    nop\n"),
    ("contact on the wrong register", "dv_contact", "    mov r11, rcx\n", "    mov r11, rdx\n"),
    ("contact forgets rax", "dv_contact", "    pop rax\n    popfq\n    ret\n", "    pop r11\n    popfq\n    ret\n"),
    ("tick move forgets the store", "dv_tick_move", "    movss dword ptr [rsp + 0x74], xmm3\n", ""),
    ("tick move on the order, not its entity", "dv_tick_move", "    mov r11, qword ptr [rbx + 8]\n",
     "    mov r11, rbx\n"),
    ("settle forgets the zero r8", "dv_settle", "    xor r8d, r8d\n", ""),
    ("settle forgets the callee's entity", "dv_settle", "    mov rcx, rdi\n", ""),
    ("settle forgets the goal", "dv_settle", "    mov rdx, rax\n", ""),
    ("settle holds every body", "dv_settle", "    jbe pass\n", "    nop\n"),
    ("settle in the air too", "dv_settle", "    cmp dword ptr [r11 + 0x104], 0\n    jne pass\n", ""),
    ("settle for ground movers too", "dv_settle", "    cmp dword ptr [r11 + 0x710], 0\n    je pass\n", ""),
    ("settle misses a ridden flyer", "dv_settle", "    cmovne r11, rax\n", ""),
    ("settle on the old counter", "dv_settle", "    lock inc dword ptr [r10 + 44]\n", "    lock inc dword ptr [r10 + 36]\n"),
    ("contact on the shared counter", "dv_contact", "    lock inc dword ptr [r10 + 40]\n",
     "    lock inc dword ptr [r10 + 32]\n"),
    # [AIR-DIVE-BRACE-W1 round 3] the slide window
    ("window never releases", "dv_keep", "    jb whold\n", "    jmp whold\n"),
    ("window starts in the air", "dv_keep", "    jne wair\n", "    nop\n"),
    # [AIR-DIVE-BRACE-W1 round 4] the landing commit
    ("commit at any height", "dv_commit", "    ja pass\n    movss xmm0, dword ptr [rcx + 0x10]",
     "    nop\n    movss xmm0, dword ptr [rcx + 0x10]"),
    ("commit in every phase", "dv_commit", "    cmp eax, 1\n    ja pass\n", "    cmp eax, 1\n    nop\n"),
    ("commit answers yes", "dv_commit", "    xor eax, eax\n    jmp back\n", "    mov eax, 1\n    jmp back\n"),
    ("commit in mode 0 too", "dv_commit", "    cmp dword ptr [r10 + 0], 1\n    jne pass\n",
     "    cmp dword ptr [r10 + 0], 1\n    nop\n"),
    ("commit forgets r8", "dv_commit", "    mov r8, qword ptr [rbx + 0x38]\n", ""),
    ("commit keeps the far landing point", "dv_commit", "    movss dword ptr [rcx + 0x10], xmm0\n", ""),
    ("commit moves only x", "dv_commit", "    movss dword ptr [rcx + 0x18], xmm1\n", ""),
    ("commit moves a point already in the band", "dv_commit", "    jb inband\n", "    nop\n"),
    ("commit ignores the radius", "dv_commit", "    addss xmm5, xmm3\n", ""),
    ("commit leaves a point under the model", "dv_commit", "    jbe ahead\n", "    jbe inband\n"),
    ("commit on the settle counter", "dv_commit", "    lock inc dword ptr [r10 + 52]\n",
     "    lock inc dword ptr [r10 + 44]\n"),
    ("window releases at once", "dv_keep", "    jb whold\n", "    nop\n"),
    ("window not sticky", "dv_keep", "    lock or qword ptr [rbx], 1\n", ""),
    ("window release uncounted", "dv_keep", "    lock inc dword ptr [r10 + 48]\n", ""),
    ("window on x only", "dv_keep", "    addss xmm0, xmm1\n    mov eax", "    mov eax"),
    ("window forgets xmm1 on release", "dv_keep",
     "    movdqu xmm1, xmmword ptr [rsp + 16]\n    lea rsp, [rsp + 32]\n    pop r9\n",
     "    lea rsp, [rsp + 32]\n    pop r9\n"),
    ("window full table holds", "dv_keep", "    test rcx, rcx\n    je wpass_out\n",
     "    test rcx, rcx\n    je whold\n"),
    ("window ignores a released key", "dv_contact", "    xor rdx, 1\n    cmp rdx, r9\n    je wpass_out\n",
     "    xor rdx, 1\n    cmp rdx, r9\n    nop\n"),
    ("through never clears", "dv_through", "    mov qword ptr [r10 + rdx + 64], 2\n", ""),
    ("through clears on a ground charge", "dv_through", "    je wclr_done\n", "    nop\n"),
    ("through clears the rider, not the mount", "dv_through", "    cmovne rcx, rax\n", ""),
    # [FLYER-FIX-1117] engaged bodies and the first engage
    ("contact carries a body in another unit's melee", "dv_contact",
     "    lock inc dword ptr [r10 + 60]\n    jmp pass\n", "    jmp nobody\n"),
    ("contact ignores whose melee the body is in", "dv_contact",
     "    cmp rax, qword ptr [rcx + 0x2e8]\n    je nobody\n", "    cmp rax, qword ptr [rcx + 0x2e8]\n    nop\n"),
    ("contact counts any engage state", "dv_contact",
     "    cmp dword ptr [rax + 0x324], 1\n    jne nobody\n", "    cmp dword ptr [rax + 0x324], 1\n    nop\n"),
    ("contact leaves the window open on the first engage", "dv_contact",
     "    lock bts qword ptr [rbx], 0\n", "    bt qword ptr [rbx], 0\n"),
    ("close inserts an open entry", "dv_contact", "    or rbx, 1\n    lock cmpxchg16b", "    lock cmpxchg16b"),
    ("close uncounted", "dv_contact", "    jc cout\n    lock inc dword ptr [r10 + 56]\n", "    jc cout\n"),
    ("engaged body uncounted", "dv_contact", "    lock inc dword ptr [r10 + 60]\n", ""),
    ("contact closes for a ground unit", "dv_contact", "    je pure\n    cmp dword ptr [r11 + 0x104], 0\n",
     "    je pass\n    cmp dword ptr [r11 + 0x104], 0\n"),
    ("contact closes for an airborne flyer", "dv_contact", "    cmp dword ptr [r11 + 0x104], 0\n    jne pure\n",
     "    cmp dword ptr [r11 + 0x104], 0\n    jne pass\n"),
    ("through clears an engaged re-charge", "dv_through", "    jne wclr_go\n", "    jmp wclr_go\n"),
    ("through closes the rider, not the mount", "dv_through",
     "    mov r11, qword ptr [r9 + 0x2e0]\n    test r11, r11\n    cmove r11, r9\n", "    mov r11, r9\n"),
)


def run_checks():
    codes, fails, counts = {}, [], {}
    for name in CAVES:
        codes[name] = assemble(name)
        f, n = CHECKS[name](codes[name])
        fails += f
        counts[name] = n
    survivors = []
    for label, name, old, new in MUTANTS:
        src = cave_source(name)
        if src.count(old) < 1:
            raise SystemExit(f"[dive_cave_asm] REFUSING: mutant {label!r} does not apply")
        f, _n = CHECKS[name](assemble(name, src.replace(old, new, 1)))
        if not f:
            survivors.append(label)
    return codes, fails, counts, survivors


# --- site table -----------------------------------------------------------------
def layout():
    return {"bytes": BUFFER_BYTES, "mode_at": MODE_AT, "allowed_at": ALLOWED_AT, "magic_at": MAGIC_AT,
            "magic": MAGIC.decode(), "skip_speed_at": SKIP_SPEED_AT, "skipped_at": SKIPPED_AT,
            "throughs_at": THROUGHS_AT, "kept_at": KEPT_AT, "engaged_at": ENGAGED_AT,
            "reordered_at": REORDERED_AT, "contact_at": CONTACT_AT, "settled_at": SETTLED_AT,
            "released_at": RELEASED_AT, "slide_at": SLIDE_AT, "slide_slots": SLIDE_SLOTS,
            "committed_at": COMMITTED_AT, "closed_at": CLOSED_AT, "engaged_body_at": ENGAGED_BODY_AT}


def source_sha():
    norm = lambda s: "\n".join(line.strip() for line in s.splitlines() if line.strip())
    blob = json.dumps({"caves": {n: [list(CAVES[n]), norm(cave_source(n)),
                                     CALL_SITES[n]["call_at"] if n in CALL_SITES else None] for n in CAVES},
                       "layout": layout(), "skip_speed": SKIP_SPEED, "owner": OWNER,
                       "feature": FEATURE, "build": BUILD}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def agreement_format():
    """The agreement step's ``format`` (whole, exact in a float32): players whose
    caves differ are told they run another version."""
    return 2 + int(source_sha()[:5], 16)


def template(code):
    return cave_site_text.bytes_template(code, BUF_PLACEHOLDER, RESUME_PLACEHOLDER,
                                         {ORIG_PLACEHOLDER: "{orig:8}"})


def site_lua(codes):
    skip_bits = struct.unpack("<I", struct.pack("<f", SKIP_SPEED))[0]
    if struct.unpack("<f", struct.pack("<f", float(skip_bits)))[0] != skip_bits:
        # game Lua numbers are float32: a value Lua writes with mr.uint32 must be exact in it
        raise SystemExit(f"[dive_cave_asm] REFUSING: skip speed bits {skip_bits:#x} are not exact in a float32")
    lines = [
        "-- dive_site.lua -- GENERATED by tools/pipelines/dive_cave_asm.py",
        "-- (--write-site); do not edit, rerun the generator. Pure data.",
        "-- [AIR-DIVE-MP-DIVE-W1 2026-11-12, §C8-61] The physics dive: three code caves",
        "-- (the charge goal of a flyer is the ground charge's through goal; a landed",
        "-- flyer that is still fast neither attacks nor stops flying), plus five",
        "-- call-site caves (AIR-DIVE-RELEASE-W1: nor is it re-pathed), as memreader",
        "-- Plus site-loader entries, plus the buffer layout lib/dive.lua writes.",
        "-- / 物理俯冲：代码洞的位点表与缓冲区布局（生成物）。",
        "return {",
        f"    owner = '{OWNER}',",
        f"    feature = '{FEATURE}',",
        "    entries = {",
    ]
    for name, (pattern, at, stolen, _resume) in CAVES.items():
        lines += cave_site_text.cave_entry_lines(
            name, FEATURE, pattern, at, stolen, template(codes[name]),
            CALL_SITES[name]["call_at"] if name in CALL_SITES else None)
    lay = layout()
    lines += [
        "    },",
        "    caves = { " + ", ".join(f"'{n}'" for n in CAVES) + " },",
        "    resume_at = { " + ", ".join(f"{n} = {CAVES[n][3]}" for n in CAVES if CAVES[n][3]) + " },",
        "    layout = {",
        "        " + ", ".join(f"{k} = {v!r}".replace('"', "'") for k, v in lay.items()) + ",",
        "    },",
        f"    skip_speed = {SKIP_SPEED}, skip_speed_bits = {skip_bits},",
        f"    format = {agreement_format()},",
        f"    build = '{BUILD}',",
        f"    source_sha = '{source_sha()}',",
        "}",
    ]
    return "\n".join(lines) + "\n"


def check_site_file(mod_dir=MOD_DIR):
    """Offline (no keystone): the committed site table matches these sources. [D15, d15-1118 stage 5] The table
    is written by dive_cost_asm.py (these caves with the dive mark, plus dv_cost); its source sha folds in this
    file's source_sha(), so its check is this file's check too."""
    import dive_cost_asm
    return dive_cost_asm.check_site_file(mod_dir)


def check_exe(exe_path=EXE):
    """Offline: every site matches exactly once in the exe's code with the
    expected bytes at the site. Returns {name: virtual address}."""
    import pefile
    pe = pefile.PE(str(exe_path), fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    code = [(base + s.VirtualAddress, s.get_data()) for s in pe.sections if s.Characteristics & 0x20000000]
    found = {}
    for name, (pattern, at, stolen, _r) in CAVES.items():
        rx = re.compile(b"".join(b"." if t == "??" else re.escape(bytes([int(t, 16)])) for t in pattern.split()),
                        re.S)
        hits = [va + m.start() for va, data in code for m in rx.finditer(data)]
        if len(hits) != 1:
            raise RuntimeError(f"[dive_cave_asm] REFUSING: {name} matches {len(hits)} times in {exe_path}")
        want = bytes(int(t, 16) for t in stolen.split())
        sec_va, data = next((va, d) for va, d in code if va <= hits[0] < va + len(d))
        got = data[hits[0] - sec_va + at:hits[0] - sec_va + at + len(want)]
        if got != want:
            raise RuntimeError(f"[dive_cave_asm] REFUSING: {name} site bytes {got.hex()} != {want.hex()}")
        found[name] = hits[0] + at
        if name in CALL_SITES:      # [AIR-DIVE-RELEASE-W1] the call still names its callee
            off = hits[0] - sec_va + CALL_SITES[name]["call_at"]
            dest = hits[0] + CALL_SITES[name]["call_at"] + 5 + struct.unpack_from("<i", data, off + 1)[0]
            if data[off] != 0xE8 or dest != CALL_SITES[name]["callee"]:
                raise RuntimeError(f"[dive_cave_asm] REFUSING: {name} calls {dest:#x}, "
                                   f"not {CALL_SITES[name]['callee']:#x}")
    return found


def main(argv):
    if "--check-exe" in argv:
        print("[dive_cave_asm] exe sites:", {k: hex(v) for k, v in check_exe().items()})
    codes, fails, counts, survivors = run_checks()
    if fails:
        raise SystemExit("[dive_cave_asm] emulator check FAILED:\n  " + "\n  ".join(fails))
    if survivors:
        raise SystemExit(f"[dive_cave_asm] REFUSING: mutants passed every case: {survivors}")
    print(f"[dive_cave_asm] caves {', '.join(f'{n} {len(codes[n])} B' for n in codes)}; emulator cases "
          f"{counts}; {len(MUTANTS)} mutants each caught")
    if "--write-site" in argv:
        # [D15, d15-1118 stage 5] this table alone would drop the dive mark and dv_cost
        raise SystemExit("[dive_cave_asm] REFUSING: the shipped dive site table is written by dive_cost_asm.py "
                         "--write-site (these caves with D15)")


if __name__ == "__main__":
    main(sys.argv[1:])
