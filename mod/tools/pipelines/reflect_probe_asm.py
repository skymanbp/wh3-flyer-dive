"""TEST-ONLY: two logger caves for the impact-damage probe (update-1117 part C, user ruling D4).

Never in a player's pack: built only by pipelines/build_pin_on_hit_probe.py --reflect, together
with pipelines/reflect_probe.lua. Question: does a diving flyer that runs head-on into braced
``charge_reflection`` infantry get the engine's impact reflection, and how much damage does it
take per hit -- with a positive control (ground cavalry into the same braced spearmen), because
the earlier logger recorded only flyer participants, so its "0 reflections" was never shown to
mean "no reflection" (design.md section 1).

Exe 9.0.5, PE timestamp 0x6ae2a00b (both sites are checked against the installed exe by
``check_exe``; the site loader needs each pattern exactly once).

``rf_refl`` at the ENTRY of the impact reflection 0x1430afae4 (only caller 0x14325bf46 in
0x14325bbec). Entry: rcx ctx, rdx out ({u32 knock kind, i32 damage}, read back by the caller at
0x14325bf4b / 0x14325bf78), r8 the braced reflector, r9 the charger, [rsp+0x28] closing speed
(F32; the caller stores xmm7 at its [rsp+0x20] at 0x14325bf2d). EVERY call is logged (no flyer
filter: the positive control's charger is a ground unit). 64-byte entry:
  +0 u64 reflector   +8 u64 charger   +16 u64 return address   +24 f32 closing speed
  +28 u32 battle tick (charger, else reflector)   +32 u64 reflector unit [+0x2e8]
  +40 u64 charger unit [+0x2e8] (else its mount's)   +48 u32 charger is / rides a flyer (FC +0x128)
  +52 f32 reflector +0xbc (bracing multiplier, static read)   +56 u32 reflector +0x6c
  +60 u32 seq + 1 (written last)
``rf_dmg`` inside the damage applier 0x14325a9c4, at +0x54 (0x14325aa18: ``mov r15d,[rbp+0x6f];
mov r14d,eax; mov r13b,[rbp+0x67]; mov [rbp+0x57],eax``), i.e. after the applier scaled the damage
(eax, the applier's own rounding call 0x1405a1d2c touches only rax / xmm0) and before it uses it.
There rdx = the victim ([ctx+8], loaded at 0x14325a9e6 and still read at 0x14325aa41), rbp = entry
rsp - 0x3f, so [rbp+0x3f] = the return address and [rbp+0x6f] = the damage type (entry [rsp+0x30]).
Not at the entry: the shipped take-off cave pin_stamp owns the entry's first 10 bytes; this
site's pattern starts after them (0x14325a9ce), so it matches with or without pin_stamp. The
probe installs at Deployed, after the take-off battle entry installed pin_stamp at chunk scope
(pin_stamp's own pattern spans this site; installed the other way round, the take-off rule
would be off for that battle -- its BATTLE line says so). EVERY call is logged:
  +0 u64 return address   +8 u64 victim   +16 u64 victim unit [+0x2e8] (else its mount's)
  +24 i32 damage (scaled)   +28 u32 damage type   +32 u32 battle tick
  +36 u32 victim is / rides a flyer   +40 u64 the flying entity (0: none)   +60 u32 seq + 1
The reflection's own damage call is the applier call at 0x14325bf8b (type 0, damage = the
reflection's out +4), so its entries carry return address 0x14325bf90.

[D3-1118, after the 2026-11-18 runs: rf_refl was entered 0 times in 16 battles while rf_dmg saw
every melee and impact call] Three more loggers find out how far the engine gets towards a
reflection. Static read (d3-1118): the ONLY caller of 0x1430afae4 is 0x14325bbec, and that
function's only callers are two per-soldier action updates (0x14326a6ba in 0x14326a2bc,
0x14326ae9b in 0x14326a958). Inside 0x14325bbec each nearby enemy (r9 list) is skipped by one of
five tests, which the engine itself labels with debug strings: charger state +0x324 in
{12, 15, 16, 17} ("Interr"), outside the radius, closer than the inner radius ("Near"),
reflector +0x318 != 0x69 ("Back"), 0x1430751a8(reflector, charger +0x60) ("Immune"), and the
r8b flag or 0x143072fe8(charger) ("BACK").
``rf_brace`` at the ENTRY of 0x14325bbec: rdx = the reflector (the bracing soldier), r8b = the
caller's flag (+0x48 of its action object), r9 = the list of nearby enemies ({+4 u32 count,
+8 pointer array}), entry [rsp+0x30] = pointer to the radius (F32, compared with squared
distances). EVERY call is logged, 128-byte entry:
  +0 u64 reflector   +8 u64 reflector unit   +16 u32 reflector +0x318   +20 u32 r8b
  +24 u32 enemies in the list   +28 u32 battle tick   +32 f32 reflector x (+0x88)
  +36 f32 reflector z (+0x90)   +40 f32 radius   +48 / +80 the first two enemies: u64 entity,
  u64 unit, u32 state +0x324, f32 x, f32 z   +124 u32 seq + 1 (written last)
``rf_act1`` / ``rf_act2`` at the ENTRIES of the two action updates (rcx = the action object,
[rcx+8] its soldier): is any soldier running the action that can lead to a reflection at all?
64-byte entry: +0 u64 soldier   +8 u64 its unit   +16 u32 soldier +0x318   +20 u32 action +0x38
(the id 0x14326a2bc compares with the soldier's +0x318)   +24 u32 which (1 / 2)
+28 u32 battle tick   +32 u32 action byte +0x48   +36 u32 action byte +0x7c   +60 u32 seq + 1.

[d10-1118, D4: from the damage side] 17 runs reached neither rf_brace nor rf_act*, while rf_dmg logged ~680
calls a battle. The installed data (db.pack _kv_rules, local_en.pack unit_attributes) and this static read say
what "Charge Reflection" is in 9.0: the kv rules are fields of one object (registered at 0x1405c17ad /
0x1405c17c6: charge_reflect_damage_multiplier at +0x6610, its value at +0x6670 = 2.0;
charge_reflect_min_charge_factor_threshold at +0x6678, value +0x66d8 = 0.7). Their only battle reader is the
damage calculator 0x142e5fcb0 (args: r9 = the attack's source interface, 5th = its target, r12 = the kv
object): at 0x142e6005f it asks target->vfunc[0x48], at 0x142e6006c source->vfunc[0x38]; when both hold it
compares target's 0x143065f3c (charge factor) with 0.7 and at 0x142e600af multiplies the damage factor by
the 2.0 (``mulss xmm8, xmm7``). Its callers: 0x142e602ac (the impact reflection's 0x1430af180, the charge
collision's 0x1430b008c path, matched combat), 0x1430b0570 (the splash attack 0x143087068) and 0x142e3945c.
Which interface is which entity is NOT read statically, so the caves log raw candidates.
``rf_cgate`` at 0x142e60070 (both tests passed; stolen ``mov rax,[rdi]; mov rcx,rdi``) and ``rf_cmul`` at
0x142e600af (the multiplier applied; stolen ``mulss xmm8,xmm7``), one 128-byte ring, EVERY call:
  +0 u64 rdi (target interface)  +8 u64 rbx (source interface)  +16 u64 return address of 0x142e5fcb0
  +24 u64 the next return address up (valid when +16 is 0x142e60306, i.e. through 0x142e602ac)
  +32 u32 which (1 gate, 2 multiplier)  +36 f32 xmm0 (rf_cmul: the target's charge factor)
  +40 f32 xmm6 (rf_cmul: the threshold)  +44 f32 xmm7 (the multiplier)  +48 u32 thread id (gs:[0x48])
  +52 u32 clock  +56 f32 xmm8 (the damage factor before the multiply)  +64 / +72 u64 [rdi+8] / [rdi+0x10]
  +80 / +88 u64 [rbx+8] / [rbx+0x10] (candidates for the entities)  +124 u32 seq + 1
rf_dmg gains +48 u32 thread id and +52 u32 clock; clock = one counter all caves share (header +32), so a
multiplier and the damage call it feeds can be paired on one thread. ``APPLIER_CALLS`` classes each of the
applier's 25 call sites by its caller (pin_cave_asm's own notes and the callers' functions).

[d15-1118, D15] rf_dmg's entry grows to DMG_ENTRY (128) bytes; the fields above keep their offsets, the
sequence moves to +124, and it logs what the D15 design needs from every applier call:
  +56 u32 victim +0x318 (the soldier's action; 0x69 = braced, the engine's own test at 0x14325bdd6)
  +60 u32 verdict (type 5 / 6 only, else 0): 1 would-be cost (the mark is spent), 2 the mark expired (more
      than DIVE_COST_WINDOW_TICKS after the stamp), 3 fresh mark but the victim is not braced, 4 the attacker's
      mark is armed only (no touchdown yet), 5 the mark was already spent or expired
  +64 u64 r12 (the applier's attacker struct: its r9)  +72 u64 [r12] (the attacker entity; 0 if r12 is 0)
  +80 u64 the attacker's flying entity (the attacker itself when it has a flight controller, else the first of
      up to three +0x2e0 ancestors that has one; 0: none)
  +88 u32 victim +0xb18 (maximum hit points)  +92 u32 victim +0xb1c (current hit points)
  +96 u32 / +100 u32 the same two for the attacker's flying entity (0xFFFFFFFF when there is none)
  +104 u32 mark state seen (0xFFFFFFFF: not looked up -- not type 5 / 6 or no flying attacker; 0xFFFFFFFE: no
      dive buffer known; 0: no entry; 1 armed, 2 stamped, 3 spent, 4 expired)
  +108 u32 ticks since the entry's tick (the stamp; for an armed mark the arm), 0xFFFFFFFF when not looked up
  +112 u64 the attacker's unit (+0x2e8 of the attacker, else of its flying entity)
  +120 u32 the attacker's flying entity's size code (+0x74: 1 small .. 4 very large, the field the shipped
       take-off cave reads, anchor pin_layout_size; 0xFFFFFFFF when there is none)
The applier itself reads [r12] (0x14325aa9e) and [[r12]+0x2e8] (0x14325abde) on these paths, and the victim's
+0x58 / +0x2e8 / +0xb1c; the parent chain is the engine's own (0x14325d45e). Every pointer is null-checked.
The mark table and its event ring live in the dive buffer of the marked dive caves (dive_mark_asm.py); the
recorder writes that buffer's address at DIVE_AT before it switches the probe on (0 = no mark: logged as
0xFFFFFFFE). A spent / expired mark is changed with lock cmpxchg from "stamped" only, and the change is an
event in the dive buffer's ring (kinds 3 / 4) with the same layout as the dive caves' own events.
The C records (rf_cgate / rf_cmul) are unchanged: they share the clock with the D records (pair on thread +
clock), and [rdi+8] is not dereferenced (not every interface was shown to hold an entity there).

``python reflect_probe_asm.py [--write-site PATH]`` (keystone + unicorn) assembles the caves,
runs them in Unicorn against synthetic objects, runs mutated sources that must each fail, and
writes the site table to PATH (default: print only).
"""
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
import rolepath  # noqa: F401,E402 -- imported because it puts the role directories on sys.path

import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import dive_mark_asm as mark  # noqa: E402 -- same reason (pipelines/)

OWNER, FEATURE = "reflect_probe", "reflect_probe"
SITE_REQUIRE = "script/reflect_probe/reflect_probe_site"     # Lua require name of the site table
REFL_PATTERN = ("48 8B C4 48 89 58 08 48 89 68 10 48 89 70 18 48 89 78 20 41 56 48 81 EC 40 01 00 00 "
                "0F 29 70 E8 48 8B F9 48 8B 41 08")
REFL_STOLEN = "48 8B C4 48 89 58 08 48 89 68 10"
# from 0x14325a9ce (after pin_stamp's 10 stolen bytes) to 0x14325aa26; the cave sits at +0x4a
DMG_PATTERN = ("41 55 41 56 41 57 48 8D 6C 24 F9 48 81 EC A0 00 00 00 0F 57 C0 48 8B DA 48 8B 51 08 "
               "4D 8B E1 48 8B F9 48 8B 42 58 4C 8B 90 40 04 00 00 41 8B C0 4D 8B 9A A8 00 00 00 "
               "F3 48 0F 2A C0 F3 41 0F 59 83 C0 02 00 00 E8 ?? ?? ?? ?? "
               "44 8B 7D 6F 44 8B F0 44 8A 6D 67 89 45 57 41 83 FF 02")
DMG_AT = 0x4A
DMG_STOLEN = "44 8B 7D 6F 44 8B F0 44 8A 6D 67 89 45 57"
REFLECT_DAMAGE_RETURN = 0x14325BF90      # the reflection's own applier call returns here
# [d3-1118] the reflection check 0x14325bbec and the two per-soldier action updates that call it
BRACE_PATTERN = ("48 8B C4 48 89 58 08 44 88 40 18 55 56 57 41 54 41 55 41 56 41 57 48 8D 6C 24 A0 "
                 "48 81 EC 60 01 00 00")
BRACE_STOLEN = "48 8B C4 48 89 58 08 44 88 40 18"
ACT1_PATTERN = ("48 8B C4 55 53 56 57 41 55 41 56 41 57 48 8D 68 A1 48 81 EC A0 00 00 00 48 8B 59 08 "
                "48 8B F1 0F 29 70 B8 0F 57 F6")
ACT1_STOLEN = "48 8B C4 55 53 56 57 41 55"
ACT2_PATTERN = ("48 8B C4 55 53 56 57 41 54 41 55 41 56 41 57 48 8D 68 A1 48 81 EC A8 00 00 00 "
                "0F 29 70 A8 48 8B F1 48 8B 49 08")
ACT2_STOLEN = "48 8B C4 55 53 56 57 41 54"
# [d10-1118] the damage calculator's charge-reflect test and multiplier (0x142e5fcb0)
CGATE_PATTERN = "84 C0 74 5B 48 8B 07 48 8B CF FF 50 08 48 85 C0 74 4D 48 8B 03"
CGATE_AT, CGATE_STOLEN = 4, "48 8B 07 48 8B CF"
CMUL_PATTERN = "E8 ?? ?? ?? ?? 0F 2F C6 0F 82 ?? ?? ?? ?? F3 44 0F 59 C7 40 84 ED 74 12"
CMUL_AT, CMUL_STOLEN = 14, "F3 44 0F 59 C7"
CALC_RET_FRAME = 0xC8                # 0x142e5fcb0: 5 pushes + sub rsp,0xa0 -> its return address
CALC_RET2_FRAME = 0x158              # through 0x142e602ac (3 pushes + sub rsp,0x70): the next one up
CALC_VIA_602AC = 0x142E60306
CALC_CALLERS = {0x142E60306: "0x142e602ac (impact reflection / charge collision / matched combat)",
                0x1430B077D: "0x1430b0570 (splash attack 0x143087068)", 0x142E39502: "0x142e3945c"}
CALC_CALLERS_2 = {0x1430ADDCC: "0x1430adabc", 0x1430AF7B4: "0x1430af180 (impact reflection, matched combat)",
                  0x1430B0284: "0x1430b008c (charge collision attack, hit processor)"}
EXE_SITES = {"rf_refl": 0x1430AFAE4, "rf_dmg": 0x14325AA18,   # build 6ae2a00b
             "rf_brace": 0x14325BBEC, "rf_act1": 0x14326A2BC, "rf_act2": 0x14326A958,
             "rf_cgate": 0x142E60070, "rf_cmul": 0x142E600AF}
# the applier 0x14325a9c4's 25 call sites (return address = call + 5) by caller
_APPLIER_SITES = {
    "hit processor 0x14326cd24 (melee weapon hit)": (0x14326CF5F, 0x14326D0C0, 0x14326D167, 0x14326D212),
    "hit processor twin 0x14325b54c": (0x14325B6DD, 0x14325B83E, 0x14325B8E5, 0x14325B990),
    "splash attack 0x143087068": (0x1430874D0,),
    "matched combat 0x142f72320": (0x142F724BF, 0x142F72529),
    "matched combat 0x142f8cc94": (0x142F8CE13, 0x142F8CEB8),
    "matched combat 0x142f8e0f8": (0x142F8E737, 0x142F8EBED),
    "charge collision attack 0x143060e44 (type 6)": (0x14306109D,),
    "impact 0x143061144 (type 5)": (0x143061961,),
    "ranged / explosion 0x1430aaa88": (0x1430AAB7F,),
    "impact reflection 0x14325bbec": (0x14325BF8B,),
    "unidentified 0x142f8f508": (0x142F8F673,), "unidentified 0x14306824c": (0x143068323,),
    "unidentified 0x14308c1d0": (0x14308C605,), "unidentified 0x1430be044": (0x1430BE1CB,),
    "unidentified 0x1430be2d4": (0x1430BE637,), "unidentified 0x1430bec08": (0x1430BED2B,),
}
APPLIER_CALLS = {site + 5: cls for cls, sites in _APPLIER_SITES.items() for site in sites}

MODE_AT, MAGIC_AT, REFL_COUNT_AT, DMG_COUNT_AT, BRACE_COUNT_AT, ACT_COUNT_AT = 0, 8, 16, 20, 24, 28
CLOCK_AT, CR_COUNT_AT = 32, 36       # [d10-1118]
DIVE_AT = 40                        # [d15-1118] u64: the marked dive caves' buffer (0: none)
# 2: + rf_brace, rf_act1, rf_act2 (d3-1118); 3: + rf_cgate, rf_cmul, clock; 4: rf_dmg 128 bytes, the D15 mark
MAGIC = b"RFPROBE4"
REFL_RING_AT, REFL_SLOTS = 64, 4096
DMG_RING_AT, DMG_SLOTS, DMG_ENTRY = REFL_RING_AT + REFL_SLOTS * 64, 16384, 128
ENTRY = 64
BRACE_RING_AT, BRACE_SLOTS, BRACE_ENTRY = DMG_RING_AT + DMG_SLOTS * DMG_ENTRY, 8192, 128
ACT_RING_AT, ACT_SLOTS = BRACE_RING_AT + BRACE_SLOTS * BRACE_ENTRY, 8192
CR_RING_AT, CR_SLOTS, CR_ENTRY = ACT_RING_AT + ACT_SLOTS * ENTRY, 8192, 128
BYTES = CR_RING_AT + CR_SLOTS * CR_ENTRY
STATE_OFF, POS_X, POS_Z, CHARGER_STATE = 0x318, 0x88, 0x90, 0x324
ACT_ID, ACT_FLAG1, ACT_FLAG2 = 0x38, 0x48, 0x7C
BUF = 0x1122334455667788
FC, PARENT, UNIT, BATTLE, TICKS, TICK = 0x128, 0x2E0, 0x2E8, 0x58, 0x440, 0x98
BRACE_MULT, IMMOVABLE = 0xBC, 0x6C
# [d15-1118] the D15 probe: the soldier's braced action, health fields, the window and the verdicts
BRACED, MAX_HP, CUR_HP, SIZE = 0x69, 0xB18, 0xB1C, 0x74
COST_WINDOW = air_dive_rules.DIVE_COST_WINDOW_TICKS
# [d15-1118, cost] the recorder's reduce_hitpoints_unary step: the share by the engine's size code 1..4
COST_SHARE_BY_CODE = [air_dive_rules.DIVE_COST_SHARE[s] for s in
                      sorted(air_dive_rules.TAKEOFF_SIZE_CODES, key=air_dive_rules.TAKEOFF_SIZE_CODES.get)]
V_COST, V_EXPIRED, V_NOT_BRACED, V_ARMED_ONLY, V_ALREADY = 1, 2, 3, 4, 5
NOT_LOOKED, NO_DIVE_BUF = 0xFFFFFFFF, 0xFFFFFFFE
CHAIN = 4                           # the attacker and up to three +0x2e0 ancestors


def _tick(reg, out, tag):
    """battle tick of entity ``reg`` into ``out`` (32-bit), 0 when a link is null; rax scratch."""
    return f"""
    xor {out}, {out}
    test {reg}, {reg}
    jz tick_{tag}
    mov rax, qword ptr [{reg} + {BATTLE:#x}]
    test rax, rax
    jz tick_{tag}
    mov rax, qword ptr [rax + {TICKS:#x}]
    test rax, rax
    jz tick_{tag}
    mov {out}, dword ptr [rax + {TICK:#x}]
tick_{tag}:
"""


REFL_PUSHES = 6


def refl_source(mutate=None):
    s = f"""
    pushfq
    push rax
    push rcx
    push rdx
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    mov edx, 1
    lock xadd dword ptr [r10 + {REFL_COUNT_AT}], edx
    mov r11d, edx
    and r11d, {REFL_SLOTS - 1}
    shl r11, 6
    lea r11, [r10 + r11 + {REFL_RING_AT}]
    inc edx
    mov dword ptr [r11 + 60], 0
    push rdx
    mov qword ptr [r11], r8
    mov qword ptr [r11 + 8], r9
    mov rax, qword ptr [rsp + {8 * (REFL_PUSHES + 1)}]
    mov qword ptr [r11 + 16], rax
    mov eax, dword ptr [rsp + {8 * (REFL_PUSHES + 1) + 0x28}]
    mov dword ptr [r11 + 24], eax
    {_tick("r9", "ecx", "charger")}
    test ecx, ecx
    jnz have_tick
    {_tick("r8", "ecx", "reflector")}
have_tick:
    mov dword ptr [r11 + 28], ecx
    xor eax, eax
    xor ecx, ecx
    mov dword ptr [r11 + 52], ecx
    mov dword ptr [r11 + 56], ecx
    test r8, r8
    jz no_r8
    mov rax, qword ptr [r8 + {UNIT:#x}]
    mov ecx, dword ptr [r8 + {BRACE_MULT:#x}]
    mov dword ptr [r11 + 52], ecx
    mov ecx, dword ptr [r8 + {IMMOVABLE:#x}]
    mov dword ptr [r11 + 56], ecx
no_r8:
    mov qword ptr [r11 + 32], rax
    xor eax, eax
    xor ecx, ecx
    test r9, r9
    jz no_r9
    mov rax, qword ptr [r9 + {UNIT:#x}]
    cmp qword ptr [r9 + {FC:#x}], 0
    setne cl
    mov rdx, qword ptr [r9 + {PARENT:#x}]
    test rdx, rdx
    jz no_r9
    test rax, rax
    jnz parent_fc
    mov rax, qword ptr [rdx + {UNIT:#x}]
parent_fc:
    cmp qword ptr [rdx + {FC:#x}], 0
    je no_r9
    mov ecx, 1
no_r9:
    mov qword ptr [r11 + 40], rax
    mov dword ptr [r11 + 48], ecx
    pop rdx
    mov dword ptr [r11 + 60], edx
done:
    pop r11
    pop r10
    pop rdx
    pop rcx
    pop rax
    popfq
"""
    return _mutate(s, mutate)


def _attacker():
    """[d15-1118] r12 -> +64; [r12] -> +72; its flying entity -> +80 with its health; its unit -> +112.
    Uses rax, rcx, r8 (free here: saved by the cave or pushed by _d15)."""
    return f"""
    mov qword ptr [r11 + 64], r12
    test r12, r12
    jz att_done
    mov rcx, qword ptr [r12]
    mov qword ptr [r11 + 72], rcx
    test rcx, rcx
    jz att_done
    mov rax, qword ptr [rcx + {UNIT:#x}]
    mov qword ptr [r11 + 112], rax
    mov r8d, {CHAIN}
att_chain:
    cmp qword ptr [rcx + {FC:#x}], 0
    jne att_fly
    mov rcx, qword ptr [rcx + {PARENT:#x}]
    test rcx, rcx
    jz att_done
    dec r8d
    jnz att_chain
    jmp att_done
att_fly:
    mov qword ptr [r11 + 80], rcx
    mov eax, dword ptr [rcx + {MAX_HP:#x}]
    mov dword ptr [r11 + 96], eax
    mov eax, dword ptr [rcx + {CUR_HP:#x}]
    mov dword ptr [r11 + 100], eax
    mov eax, dword ptr [rcx + {SIZE:#x}]
    mov dword ptr [r11 + 120], eax
    cmp qword ptr [r11 + 112], 0
    jne att_done
    mov rax, qword ptr [rcx + {UNIT:#x}]
    mov qword ptr [r11 + 112], rax
att_done:
"""


def _d15():
    """[d15-1118] The D15 fields and the mark (rdx = the victim, kept; r10 = this buffer, r11 = the entry;
    rbx rdx rsi r8 r13 are pushed here and popped at the end; r9d (the seq) is not touched)."""
    return f"""
    push rbx
    push rdx
    push rsi
    push r8
    push r13
    mov dword ptr [r11 + 96], -1
    mov dword ptr [r11 + 100], -1
    mov dword ptr [r11 + 120], -1
    mov dword ptr [r11 + 104], {NOT_LOOKED}
    mov dword ptr [r11 + 108], -1
    mov dword ptr [r11 + 56], -1
    mov dword ptr [r11 + 88], -1
    mov dword ptr [r11 + 92], -1
    test rdx, rdx
    jz d15_novictim
    mov eax, dword ptr [rdx + {STATE_OFF:#x}]
    mov dword ptr [r11 + 56], eax
    mov eax, dword ptr [rdx + {MAX_HP:#x}]
    mov dword ptr [r11 + 88], eax
    mov eax, dword ptr [rdx + {CUR_HP:#x}]
    mov dword ptr [r11 + 92], eax
d15_novictim:
{_attacker()}    mov eax, dword ptr [rbp + 0x6f]
    cmp eax, 5
    je d15_type
    cmp eax, 6
    jne d15_done
d15_type:
    mov r13, qword ptr [r11 + 80]
    test r13, r13
    jz d15_done
    mov rsi, qword ptr [r10 + {DIVE_AT}]
    test rsi, rsi
    jnz d15_buf
    mov dword ptr [r11 + 104], {NO_DIVE_BUF}
    jmp d15_done
d15_buf:
{mark.find("rsi", "r13", False, "rf")}    mov dword ptr [r11 + 104], 0
    test rdx, rdx
    jz d15_done
    mov eax, dword ptr [rdx + 8]
    mov dword ptr [r11 + 104], eax
    mov ebx, dword ptr [r11 + 32]
    mov ecx, ebx
    sub ecx, dword ptr [rdx + 12]
    mov dword ptr [r11 + 108], ecx
    cmp eax, {mark.STAMPED}
    je d15_stamped
    mov dword ptr [r11 + 60], {V_ALREADY}
    cmp eax, {mark.ARMED}
    jne d15_done
    mov dword ptr [r11 + 60], {V_ARMED_ONLY}
    jmp d15_done
d15_stamped:
    cmp ecx, {COST_WINDOW}
    jbe d15_fresh
    mov eax, {mark.STAMPED}
    mov r8d, {mark.EXPIRED}
    lock cmpxchg dword ptr [rdx + 8], r8d
    jne d15_raced
    mov dword ptr [r11 + 60], {V_EXPIRED}
    mov edx, ecx
{mark.event("rsi", "r13", mark.EV_EXPIRED, "rfx")}    jmp d15_done
d15_fresh:
    cmp dword ptr [r11 + 56], {BRACED}
    je d15_cost
    mov dword ptr [r11 + 60], {V_NOT_BRACED}
    jmp d15_done
d15_cost:
    mov eax, {mark.STAMPED}
    mov r8d, {mark.SPENT}
    lock cmpxchg dword ptr [rdx + 8], r8d
    jne d15_raced
    mov dword ptr [r11 + 60], {V_COST}
    mov edx, ecx
{mark.event("rsi", "r13", mark.EV_SPENT, "rfc")}    jmp d15_done
d15_raced:
    mov dword ptr [r11 + 60], {V_ALREADY}
d15_done:
    pop r13
    pop r8
    pop rsi
    pop rdx
    pop rbx
"""


def dmg_source(mutate=None):
    zero = "".join(f"    mov qword ptr [r11 + {o}], rax\n" for o in range(0, DMG_ENTRY, 8))
    s = f"""
    pushfq
    push rax
    push rcx
    push r9
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    mov r9d, 1
    lock xadd dword ptr [r10 + {DMG_COUNT_AT}], r9d
    mov r11d, r9d
    and r11d, {DMG_SLOTS - 1}
    shl r11, 7
    mov rcx, {DMG_RING_AT}
    add r11, rcx
    add r11, r10
    xor eax, eax
{zero}    mov rcx, qword ptr [rbp + 0x3f]
    mov qword ptr [r11], rcx
    mov qword ptr [r11 + 8], rdx
    mov ecx, dword ptr [rsp + 32]
    mov dword ptr [r11 + 24], ecx
    mov ecx, dword ptr [rbp + 0x6f]
    mov dword ptr [r11 + 28], ecx
    {_tick("rdx", "ecx", "victim")}
    mov dword ptr [r11 + 32], ecx
    xor eax, eax
    xor ecx, ecx
    test rdx, rdx
    jz no_victim
    mov rax, qword ptr [rdx + {UNIT:#x}]
    mov rcx, rdx
    cmp qword ptr [rdx + {FC:#x}], 0
    jne flyer
    mov rcx, qword ptr [rdx + {PARENT:#x}]
    test rcx, rcx
    jz no_flyer
    test rax, rax
    jnz parent_fc
    mov rax, qword ptr [rcx + {UNIT:#x}]
parent_fc:
    cmp qword ptr [rcx + {FC:#x}], 0
    jne flyer
no_flyer:
    jmp unit_out
flyer:
    mov qword ptr [r11 + 40], rcx
    mov dword ptr [r11 + 36], 1
unit_out:
no_victim:
    mov qword ptr [r11 + 16], rax
    mov eax, dword ptr gs:[0x48]
    mov dword ptr [r11 + 48], eax
    mov eax, 1
    lock xadd dword ptr [r10 + {CLOCK_AT}], eax
    mov dword ptr [r11 + 52], eax
{_d15()}    inc r9d
    mov dword ptr [r11 + 124], r9d
done:
    pop r11
    pop r10
    pop r9
    pop rcx
    pop rax
    popfq
"""
    return _mutate(s, mutate)


BRACE_PUSHES = 5                    # flags + rax rcx r10 r11 (the seq push comes after)


def _enemy(n, at):
    """log enemy ``n`` of the list r9 at entry offset ``at``; rax / rcx / r10 scratch."""
    return f"""
    cmp dword ptr [r9 + 4], {n + 1}
    jb enemy_end_{n}
    mov rax, qword ptr [r9 + 8]
    test rax, rax
    jz enemy_end_{n}
    mov rax, qword ptr [rax + {8 * n}]
    test rax, rax
    jz enemy_end_{n}
    mov qword ptr [r11 + {at}], rax
    mov r10, qword ptr [rax + {UNIT:#x}]
    mov qword ptr [r11 + {at + 8}], r10
    mov r10d, dword ptr [rax + {CHARGER_STATE:#x}]
    mov dword ptr [r11 + {at + 16}], r10d
    mov r10d, dword ptr [rax + {POS_X:#x}]
    mov dword ptr [r11 + {at + 20}], r10d
    mov r10d, dword ptr [rax + {POS_Z:#x}]
    mov dword ptr [r11 + {at + 24}], r10d
enemy_end_{n}:
"""


def brace_source(mutate=None):
    zero = "".join(f"    mov qword ptr [r11 + {o}], rax\n" for o in range(0, BRACE_ENTRY, 8))
    s = f"""
    pushfq
    push rax
    push rcx
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    mov ecx, 1
    lock xadd dword ptr [r10 + {BRACE_COUNT_AT}], ecx
    mov r11d, ecx
    and r11d, {BRACE_SLOTS - 1}
    shl r11, 7
    mov rax, {BRACE_RING_AT}
    add r11, rax
    add r11, r10
    inc ecx
    push rcx
    xor eax, eax
{zero}    mov qword ptr [r11], rdx
    movzx ecx, r8b
    mov dword ptr [r11 + 20], ecx
    mov rax, qword ptr [rsp + {8 * (BRACE_PUSHES + 1) + 0x30}]
    test rax, rax
    jz no_radius
    mov ecx, dword ptr [rax]
    mov dword ptr [r11 + 40], ecx
no_radius:
    {_tick("rdx", "ecx", "reflector")}
    mov dword ptr [r11 + 28], ecx
    test rdx, rdx
    jz no_reflector
    mov rax, qword ptr [rdx + {UNIT:#x}]
    mov qword ptr [r11 + 8], rax
    mov ecx, dword ptr [rdx + {STATE_OFF:#x}]
    mov dword ptr [r11 + 16], ecx
    mov ecx, dword ptr [rdx + {POS_X:#x}]
    mov dword ptr [r11 + 32], ecx
    mov ecx, dword ptr [rdx + {POS_Z:#x}]
    mov dword ptr [r11 + 36], ecx
no_reflector:
    test r9, r9
    jz no_list
    mov ecx, dword ptr [r9 + 4]
    mov dword ptr [r11 + 24], ecx
{_enemy(0, 48)}{_enemy(1, 80)}no_list:
    pop rcx
    mov dword ptr [r11 + 124], ecx
done:
    pop r11
    pop r10
    pop rcx
    pop rax
    popfq
"""
    return _mutate(s, mutate)


def act_source(which, mutate=None):
    zero = "".join(f"    mov qword ptr [r11 + {o}], rax\n" for o in range(0, ENTRY, 8))
    s = f"""
    pushfq
    push rax
    push rcx
    push rdx
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    mov edx, 1
    lock xadd dword ptr [r10 + {ACT_COUNT_AT}], edx
    mov r11d, edx
    and r11d, {ACT_SLOTS - 1}
    shl r11, 6
    mov rax, {ACT_RING_AT}
    add r11, rax
    add r11, r10
    inc edx
    xor eax, eax
{zero}    mov dword ptr [r11 + 24], {which}
    test rcx, rcx
    jz fin
    mov eax, dword ptr [rcx + {ACT_ID:#x}]
    mov dword ptr [r11 + 20], eax
    movzx eax, byte ptr [rcx + {ACT_FLAG1:#x}]
    mov dword ptr [r11 + 32], eax
    movzx eax, byte ptr [rcx + {ACT_FLAG2:#x}]
    mov dword ptr [r11 + 36], eax
    mov rcx, qword ptr [rcx + 8]
    test rcx, rcx
    jz fin
    mov qword ptr [r11], rcx
    mov rax, qword ptr [rcx + {UNIT:#x}]
    mov qword ptr [r11 + 8], rax
    mov eax, dword ptr [rcx + {STATE_OFF:#x}]
    mov dword ptr [r11 + 16], eax
    {_tick("rcx", "r10d", "soldier")}
    mov dword ptr [r11 + 28], r10d
fin:
    mov dword ptr [r11 + 60], edx
done:
    pop r11
    pop r10
    pop rdx
    pop rcx
    pop rax
    popfq
"""
    return _mutate(s, mutate)


CR_PUSHES = 6                       # flags + rax rcx rdx r10 r11


def _candidates(reg, at):
    return f"""
    test {reg}, {reg}
    jz cand_end_{reg}
    mov rax, qword ptr [{reg} + 8]
    mov qword ptr [r11 + {at}], rax
    mov rax, qword ptr [{reg} + 0x10]
    mov qword ptr [r11 + {at + 8}], rax
cand_end_{reg}:
"""


def cr_source(which, mutate=None):
    """[d10-1118] rf_cgate (which 1) / rf_cmul (2) inside the damage calculator 0x142e5fcb0."""
    zero = "".join(f"    mov qword ptr [r11 + {o}], rax\n" for o in range(0, CR_ENTRY, 8))
    s = f"""
    pushfq
    push rax
    push rcx
    push rdx
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    mov edx, 1
    lock xadd dword ptr [r10 + {CR_COUNT_AT}], edx
    mov r11d, edx
    and r11d, {CR_SLOTS - 1}
    shl r11, 7
    mov rax, {CR_RING_AT}
    add r11, rax
    add r11, r10
    inc edx
    xor eax, eax
{zero}    mov qword ptr [r11], rdi
    mov qword ptr [r11 + 8], rbx
    mov rax, qword ptr [rsp + {8 * CR_PUSHES + CALC_RET_FRAME:#x}]
    mov qword ptr [r11 + 16], rax
    mov rcx, {CALC_VIA_602AC:#x}
    cmp rax, rcx
    jne no_ret2
    mov rax, qword ptr [rsp + {8 * CR_PUSHES + CALC_RET2_FRAME:#x}]
    mov qword ptr [r11 + 24], rax
no_ret2:
    mov dword ptr [r11 + 32], {which}
    movss dword ptr [r11 + 36], xmm0
    movss dword ptr [r11 + 40], xmm6
    movss dword ptr [r11 + 44], xmm7
    movss dword ptr [r11 + 56], xmm8
    mov eax, dword ptr gs:[0x48]
    mov dword ptr [r11 + 48], eax
    mov eax, 1
    lock xadd dword ptr [r10 + {CLOCK_AT}], eax
    mov dword ptr [r11 + 52], eax
{_candidates("rdi", 64)}{_candidates("rbx", 80)}    mov dword ptr [r11 + 124], edx
done:
    pop r11
    pop r10
    pop rdx
    pop rcx
    pop rax
    popfq
"""
    return _mutate(s, mutate)


def _mutate(s, mutate):
    if mutate:
        old, new = mutate
        if s.count(old) != 1:
            raise SystemExit(f"mutant: {old!r} found {s.count(old)} times")
        s = s.replace(old, new)
    return s


SOURCES = {"rf_refl": refl_source, "rf_dmg": dmg_source, "rf_brace": brace_source,
           "rf_act1": lambda mutate=None: act_source(1, mutate),
           "rf_act2": lambda mutate=None: act_source(2, mutate),
           "rf_cgate": lambda mutate=None: cr_source(1, mutate),
           "rf_cmul": lambda mutate=None: cr_source(2, mutate)}


def assemble(name, mutate=None):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_64
    code = bytes(Ks(KS_ARCH_X86, KS_MODE_64).asm(SOURCES[name](mutate), 0x1000)[0])
    if code.count(struct.pack("<Q", BUF)) != 1:
        raise SystemExit(f"{name}: the buffer placeholder must appear exactly once")
    return code


# --- emulator ---------------------------------------------------------------
CODE, B, STACK, OBJ = 0x100000, 0x200000, 0x2000000, 0x3000000
RET, SPEED = 0x14325BF4B, 9.25
TEB, THREAD = 0x5000000, 0x2A3C


def _machine(code):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
    mu = Uc(UC_ARCH_X86, UC_MODE_64)
    mu.mem_map(CODE, 0x10000)
    mu.mem_map(B, ((BYTES + 0xFFFF) // 0x10000) * 0x10000)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(OBJ, 0x100000)
    mu.mem_map(TEB, 0x1000)
    mu.mem_write(TEB + 0x48, struct.pack("<I", THREAD))
    from unicorn import x86_const as X
    mu.reg_write(X.UC_X86_REG_GS_BASE, TEB)
    mu.mem_write(CODE, code.replace(struct.pack("<Q", BUF), struct.pack("<Q", B)))
    return mu


def _entities(mu, tick=4321):
    """six synthetic entities sharing one battle; each its own synthetic unit."""
    e = [OBJ + 0x10000 * (i + 1) for i in range(6)]
    battle, ticks = OBJ + 0x90000, OBJ + 0x98000
    for x in e:
        mu.mem_write(x + BATTLE, struct.pack("<Q", battle))
        mu.mem_write(x + UNIT, struct.pack("<Q", 0xAA0000 + x))
    mu.mem_write(battle + TICKS, struct.pack("<Q", ticks))
    mu.mem_write(ticks + TICK, struct.pack("<I", tick))
    return e


def _run(mu, code, regs_in, flags):
    from unicorn import x86_const as X
    names = ("rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "r8", "r9", "r10", "r11",
             "r12", "r13", "r14", "r15", "rsp", "eflags")
    vals = {n: 0x5150 + i for i, n in enumerate(names)}
    vals["eflags"] = flags
    vals.update(regs_in)
    for n, v in vals.items():
        mu.reg_write(getattr(X, "UC_X86_REG_" + n.upper()), v)
    mu.emu_start(CODE, CODE + len(code), count=10_000)
    return [n for n, v in vals.items() if mu.reg_read(getattr(X, "UC_X86_REG_" + n.upper())) != v]


def _u32(mu, at):
    return struct.unpack("<I", bytes(mu.mem_read(at, 4)))[0]


def check(mutate=None, which=None):
    """[failure] of the caves (``which`` one built from the ``mutate`` (old, new) edit) on synthetic calls."""
    fails = []
    if which in (None, "rf_refl"):
        code = assemble("rf_refl", mutate if which == "rf_refl" else None)
        for name, mode, kind, want in (("ground charger", 1, "ground", 0), ("flying charger", 1, "flyer", 1),
                                       ("rider of a flyer", 1, "rider", 1), ("off", 0, "ground", None),
                                       ("null reflector", 1, "null8", 0), ("null charger", 1, "null9", 0)):
            for flags in (0x202, 0x8D7):
                mu = _machine(code)
                e = _entities(mu)
                r8, r9 = e[0], e[1]
                mu.mem_write(r8 + BRACE_MULT, struct.pack("<f", 5.5))
                mu.mem_write(r8 + IMMOVABLE, struct.pack("<I", 0x10))
                if kind == "flyer":
                    mu.mem_write(r9 + FC, struct.pack("<Q", 0x77))
                elif kind == "rider":
                    mu.mem_write(r9 + PARENT, struct.pack("<Q", e[2]))
                    mu.mem_write(e[2] + FC, struct.pack("<Q", 0x77))
                if kind == "null8":
                    r8 = 0
                if kind == "null9":
                    r9 = 0
                mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
                mu.mem_write(B + REFL_COUNT_AT, struct.pack("<I", REFL_SLOTS + 7))
                rsp = STACK + 0x4000
                mu.mem_write(rsp, struct.pack("<Q", RET) + bytes(0x20) + struct.pack("<f", SPEED) + bytes(12))
                changed = _run(mu, code, {"rcx": 0x9999, "rdx": 0x8888, "r8": r8, "r9": r9, "rsp": rsp}, flags)
                if changed:
                    fails.append(f"rf_refl {name}/{flags:#x}: registers changed {changed}")
                cnt = _u32(mu, B + REFL_COUNT_AT) - (REFL_SLOTS + 7)
                ent = bytes(mu.mem_read(B + REFL_RING_AT + 7 * ENTRY, ENTRY))
                if want is None:
                    if cnt or any(ent):
                        fails.append(f"rf_refl {name}: logged in mode 0")
                    continue
                got = struct.unpack_from("<QQQfIQQIfII", ent, 0)
                exp = (r8, r9, RET, SPEED, 4321 if (r8 or r9) else 0,
                       (0xAA0000 + r8) if r8 else 0, (0xAA0000 + r9) if r9 else 0, want,
                       5.5 if r8 else 0.0, 0x10 if r8 else 0, REFL_SLOTS + 8)
                if (cnt, got) != (1, exp):
                    fails.append(f"rf_refl {name}: count {cnt} entry {got} want {exp}")
    if which in (None, "rf_dmg"):
        fails += _check_dmg(mutate if which == "rf_dmg" else None)
    if which in (None, "rf_brace"):
        fails += _check_brace(mutate if which == "rf_brace" else None)
    for act, n in (("rf_act1", 1), ("rf_act2", 2)):
        if which in (None, act):
            fails += _check_act(act, n, mutate if which == act else None)
    for cr, n in (("rf_cgate", 1), ("rf_cmul", 2)):
        if which in (None, cr):
            fails += _check_cr(cr, n, mutate if which == cr else None)
    return fails


DIVEB = 0x6000000                   # [d15-1118] the marked dive caves' buffer in the emulator


def _dmg_call(code, mode, victim, attacker_struct, dtype, dive, flags, slot=3):
    """One rf_dmg call -> (mu, count delta, entry bytes, registers changed)."""
    mu = _machine(code)
    mu.mem_map(DIVEB, 0x2000)
    for w in dive:
        w(mu)
    mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
    mu.mem_write(B + DIVE_AT, struct.pack("<Q", DIVEB if dive else 0))
    mu.mem_write(B + DMG_COUNT_AT, struct.pack("<I", DMG_SLOTS + slot))
    mu.mem_write(B + CLOCK_AT, struct.pack("<I", 41))
    frame = STACK + 0x6000                   # rbp = entry rsp - 0x3f
    mu.mem_write(frame + 0x3F, struct.pack("<Q", REFLECT_DAMAGE_RETURN))
    mu.mem_write(frame + 0x6F, struct.pack("<I", dtype))
    mu.mem_write(B + DMG_RING_AT + slot * DMG_ENTRY, b"\xEE" * DMG_ENTRY)     # a reused slot: junk
    regs = {"rdx": victim, "rax": 0xFFFFFFFF00000033, "rbp": frame, "rsp": STACK + 0x4000,
            "r12": attacker_struct, "r13": 0x1313, "rsi": 0x5151, "rbx": 0xB0B0}
    return mu, regs, frame, slot


def _check_dmg(mutate):
    """[d15-1118] rf_dmg on synthetic calls. The fields kept from RFPROBE3 (return address, victim and its unit,
    damage, type, tick, flyer, thread, clock) at the 128-byte layout, a junk slot, the mode switch; then the D15
    fields and the mark: a would-be cost spends a fresh stamped mark once (a second contact in the same dive
    gets nothing), a rider is judged on its mount, a soldier that is not braced, a mark past the window, an
    armed-only mark, no entry, no dive buffer, a ground attacker, no attacker, type 0 never judged; every
    register and the flags kept."""
    fails = []
    code = assemble("rf_dmg", mutate)
    for name, mode, kind, want_flyer in (("ground victim", 1, "ground", 0), ("flying victim", 1, "flyer", 1),
                                         ("rider of a flyer", 1, "rider", 1), ("null victim", 1, "null", 0),
                                         ("off", 0, "ground", None),
                                         ("rider without unit: the mount's unit", 1, "rider_nounit", 1)):
        for flags in (0x202, 0x8D7):
            mu, regs, frame, slot = _dmg_call(code, mode, 0, 0, 5, [], flags)
            e = _entities(mu, tick=777)
            victim, flyer, unit = e[0], 0, 0xAA0000 + e[0]
            if kind == "flyer":
                mu.mem_write(victim + FC, struct.pack("<Q", 0x77))
                flyer = victim
            elif kind in ("rider", "rider_nounit"):
                mu.mem_write(victim + PARENT, struct.pack("<Q", e[2]))
                mu.mem_write(e[2] + FC, struct.pack("<Q", 0x77))
                flyer = e[2]
                if kind == "rider_nounit":
                    mu.mem_write(victim + UNIT, struct.pack("<Q", 0))
                    unit = 0xAA0000 + e[2]
            elif kind == "null":
                victim, unit = 0, 0
            regs["rdx"] = victim
            try:
                changed = _run(mu, code, regs, flags)
            except Exception as exc:          # unicorn's UcError: a fault is a failing case
                fails.append(f"rf_dmg {flags:#x}: fault {exc}")
                continue
            if changed:
                fails.append(f"rf_dmg {name}/{flags:#x}: registers changed {changed}")
            cnt = _u32(mu, B + DMG_COUNT_AT) - (DMG_SLOTS + slot)
            ent = bytes(mu.mem_read(B + DMG_RING_AT + slot * DMG_ENTRY, DMG_ENTRY))
            if want_flyer is None:
                if cnt or ent != b"\xEE" * DMG_ENTRY:
                    fails.append(f"rf_dmg {name}: logged in mode 0")
                continue
            got = struct.unpack_from("<QQQiIIIQII", ent, 0) + struct.unpack_from("<I", ent, 124)
            exp = (REFLECT_DAMAGE_RETURN, victim, unit, 0x33, 5, 777 if victim else 0, want_flyer,
                   flyer, THREAD, 41, DMG_SLOTS + slot + 1)
            if _u32(mu, B + CLOCK_AT) != 42:
                fails.append(f"rf_dmg {name}: clock not advanced")
            if (cnt, got) != (1, exp):
                fails.append(f"rf_dmg {name}: count {cnt} entry {got} want {exp}")
    fails += _check_dmg_mark(code)
    return fails


def _check_dmg_mark(code):
    """The D15 fields and verdicts (see _check_dmg). The mark table is the dive buffer's (dive_mark_asm)."""
    fails = []
    NOW = 4321
    W = COST_WINDOW

    def table(key, state, tick):
        def w(mu):
            slot = (key >> 4) & (mark.MARK_SLOTS - 1)
            mu.mem_write(DIVEB + mark.MARK_TABLE_AT + slot * 16, struct.pack("<QII", key, state, tick))
        return w
    # (label, attacker, victim +0x318, mark state, mark tick, damage type, verdict, state seen, age,
    #  table state after, events added [(kind, extra)])
    cases = (
        ("would-be cost", "flyer", 0x69, mark.STAMPED, NOW - 21, 5, V_COST, 2, 21, mark.SPENT, [(3, 21)]),
        ("type 6 cost", "flyer", 0x69, mark.STAMPED, NOW - 3, 6, V_COST, 2, 3, mark.SPENT, [(3, 3)]),
        ("second contact in the same dive", "flyer", 0x69, mark.SPENT, NOW - 22, 5, V_ALREADY, 3, 22,
         mark.SPENT, []),
        ("rider: judged on its mount", "rider", 0x69, mark.STAMPED, NOW - 10, 6, V_COST, 2, 10, mark.SPENT,
         [(3, 10)]),
        ("soldier not braced", "flyer", 0x31, mark.STAMPED, NOW - 10, 5, V_NOT_BRACED, 2, 10, mark.STAMPED, []),
        ("past the window", "flyer", 0x69, mark.STAMPED, NOW - (W + 1), 5, V_EXPIRED, 2, W + 1, mark.EXPIRED,
         [(4, W + 1)]),
        ("at the window's end", "flyer", 0x69, mark.STAMPED, NOW - W, 5, V_COST, 2, W, mark.SPENT, [(3, W)]),
        ("armed only (no touchdown)", "flyer", 0x69, mark.ARMED, NOW - 2, 5, V_ARMED_ONLY, 1, 2, mark.ARMED, []),
        ("no entry", "flyer", 0x69, None, 0, 5, 0, 0, -1, None, []),
        ("no dive buffer", "flyer", 0x69, "nobuf", 0, 5, 0, NO_DIVE_BUF, -1, None, []),
        ("ground attacker", "ground", 0x69, mark.STAMPED, NOW - 2, 5, 0, NOT_LOOKED, -1, mark.STAMPED, []),
        ("no attacker", "none", 0x69, mark.STAMPED, NOW - 2, 5, 0, NOT_LOOKED, -1, mark.STAMPED, []),
        ("type 0 is never judged", "flyer", 0x69, mark.STAMPED, NOW - 2, 0, 0, NOT_LOOKED, -1, mark.STAMPED, []),
    )
    for (label, att_kind, state318, mstate, mtick, dtype, want_v, want_seen, want_age, want_after,
         want_ev) in cases:
        for flags in (0x202, 0x8D7):
            mu, regs, frame, slot = _dmg_call(code, 1, 0, 0, dtype, [], flags)
            e = _entities(mu, tick=NOW)
            victim, att, mount = e[0], e[1], e[2]
            mu.mem_write(victim + STATE_OFF, struct.pack("<I", state318))
            mu.mem_write(victim + MAX_HP, struct.pack("<II", 1200, 950))
            fly = 0
            if att_kind == "flyer":
                mu.mem_write(att + FC, struct.pack("<Q", 0x77))
                fly = att
            elif att_kind == "rider":
                mu.mem_write(att + PARENT, struct.pack("<Q", mount))
                mu.mem_write(mount + FC, struct.pack("<Q", 0x77))
                fly = mount
            if fly:
                mu.mem_write(fly + MAX_HP, struct.pack("<II", 9400, 9100))
                mu.mem_write(fly + SIZE, struct.pack("<I", 4))
            astruct = OBJ + 0xA0000
            mu.mem_write(astruct, struct.pack("<Q", 0 if att_kind == "none" else att))
            if mstate == "nobuf":
                mu.mem_write(B + DIVE_AT, struct.pack("<Q", 0))
            else:
                mu.mem_write(B + DIVE_AT, struct.pack("<Q", DIVEB))
                if mstate is not None and fly:
                    table(fly, mstate, mtick)(mu)
            regs.update({"rdx": victim, "r12": astruct})
            try:
                changed = _run(mu, code, regs, flags)
            except Exception as exc:          # unicorn's UcError: a fault is a failing case
                fails.append(f"rf_dmg {flags:#x}: fault {exc}")
                continue
            tag = f"rf_dmg mark {label}/{flags:#x}"
            if changed:
                fails.append(f"{tag}: registers changed {changed}")
            ent = bytes(mu.mem_read(B + DMG_RING_AT + slot * DMG_ENTRY, DMG_ENTRY))
            v318, verdict, r12, a_ent, a_fly, vmax, vcur, amax, acur, seen, age, a_unit = struct.unpack_from(
                "<IIQQQIIIIIiQ", ent, 56)
            exp_unit = 0 if att_kind == "none" else 0xAA0000 + att
            want = (state318, want_v, astruct, 0 if att_kind == "none" else att, fly, 1200, 950,
                    9400 if fly else 0xFFFFFFFF, 9100 if fly else 0xFFFFFFFF, want_seen & 0xFFFFFFFF, want_age,
                    exp_unit, 4 if fly else 0xFFFFFFFF)
            got = (v318, verdict, r12, a_ent, a_fly, vmax, vcur, amax, acur, seen, age, a_unit,
                   _u32(mu, B + DMG_RING_AT + slot * DMG_ENTRY + 120))
            if got != want:
                fails.append(f"{tag}: entry {got} want {want}")
            if fly and mstate not in (None, "nobuf"):
                slotk = (fly >> 4) & (mark.MARK_SLOTS - 1)
                after = struct.unpack("<QII", bytes(mu.mem_read(DIVEB + mark.MARK_TABLE_AT + slotk * 16, 16)))
                if after[1] != want_after:
                    fails.append(f"{tag}: mark state after {after[1]} want {want_after}")
            n_ev = _u32(mu, DIVEB + mark.MARK_COUNT_AT)
            evs = []
            for s in range(n_ev):
                raw = bytes(mu.mem_read(DIVEB + mark.MARK_RING_AT + s * mark.MARK_ENTRY, mark.MARK_ENTRY))
                ev_ent, ev_unit, ev_tick, ev_kind, ev_extra, ev_seq = struct.unpack("<QQIIiI", raw)
                evs.append((ev_kind, ev_extra))
                if (ev_ent, ev_unit, ev_tick, ev_seq) != (fly, 0xAA0000 + fly, NOW, s + 1):
                    fails.append(f"{tag}: event {s} {(hex(ev_ent), hex(ev_unit), ev_tick, ev_seq)}")
            if evs != want_ev:
                fails.append(f"{tag}: events {evs} want {want_ev}")
            if _u32(mu, B + DMG_RING_AT + slot * DMG_ENTRY + 124) != DMG_SLOTS + slot + 1:
                fails.append(f"{tag}: sequence not written")
    return fails


def _check_cr(name_site, which, mutate):
    """rf_cgate / rf_cmul on synthetic calls: every field (the xmm values, both return addresses through
    0x142e602ac and only the first otherwise, the candidates), the mode switch, null interfaces, a junk
    slot, every register and xmm register unchanged."""
    from unicorn import x86_const as X
    fails = []
    code = assemble(name_site, mutate)
    xmm = {0: 0.85, 6: 0.7, 7: 2.0, 8: 1.25}
    for name, mode, ret1, nulls in (("through 0x142e602ac", 1, CALC_VIA_602AC, False),
                                    ("from the splash path", 1, 0x1430B077D, False),
                                    ("null interfaces", 1, CALC_VIA_602AC, True), ("off", 0, CALC_VIA_602AC, False)):
        for flags in (0x202, 0x8D7):
            mu = _machine(code)
            a, b = OBJ + 0x20000, OBJ + 0x30000
            mu.mem_write(a + 8, struct.pack("<QQ", 0xA8, 0xA10))
            mu.mem_write(b + 8, struct.pack("<QQ", 0xB8, 0xB10))
            for r, v in xmm.items():
                mu.reg_write(getattr(X, f"UC_X86_REG_XMM{r}"), struct.unpack("<I", struct.pack("<f", v))[0])
            mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
            mu.mem_write(B + CR_COUNT_AT, struct.pack("<I", CR_SLOTS + 2))
            mu.mem_write(B + CLOCK_AT, struct.pack("<I", 900))
            slot = B + CR_RING_AT + 2 * CR_ENTRY
            mu.mem_write(slot, b"\xEE" * CR_ENTRY)
            rsp = STACK + 0x2000
            mu.mem_write(rsp + CALC_RET_FRAME, struct.pack("<Q", ret1))
            mu.mem_write(rsp + CALC_RET2_FRAME, struct.pack("<Q", 0x1430AF7B4))
            ia, ib = (0, 0) if nulls else (a, b)
            before_x = [mu.reg_read(getattr(X, f"UC_X86_REG_XMM{r}")) for r in (0, 6, 7, 8)]
            changed = _run(mu, code, {"rdi": ia, "rbx": ib, "rsp": rsp}, flags)
            if changed:
                fails.append(f"{name_site} {name}/{flags:#x}: registers changed {changed}")
            if [mu.reg_read(getattr(X, f"UC_X86_REG_XMM{r}")) for r in (0, 6, 7, 8)] != before_x:
                fails.append(f"{name_site} {name}: an xmm register changed")
            cnt = _u32(mu, B + CR_COUNT_AT) - (CR_SLOTS + 2)
            ent = bytes(mu.mem_read(slot, CR_ENTRY))
            if mode == 0:
                if cnt or ent != b"\xEE" * CR_ENTRY:
                    fails.append(f"{name_site} {name}: logged in mode 0")
                continue
            want = bytearray(CR_ENTRY)
            struct.pack_into("<QQQQI", want, 0, ia, ib, ret1, 0x1430AF7B4 if ret1 == CALC_VIA_602AC else 0, which)
            struct.pack_into("<fff", want, 36, xmm[0], xmm[6], xmm[7])
            struct.pack_into("<II", want, 48, THREAD, 900)
            struct.pack_into("<f", want, 56, xmm[8])
            if not nulls:
                struct.pack_into("<QQQQ", want, 64, 0xA8, 0xA10, 0xB8, 0xB10)
            struct.pack_into("<I", want, 124, CR_SLOTS + 3)
            if cnt != 1 or ent != bytes(want) or _u32(mu, B + CLOCK_AT) != 901:
                fails.append(f"{name_site} {name}/{flags:#x}: count {cnt}, entry differs at "
                             f"{[i for i in range(CR_ENTRY) if ent[i] != want[i]][:8]}")
    return fails


def _check_brace(mutate):
    """rf_brace on synthetic calls: every field of the 128-byte entry, the mode switch, null links
    and a ring slot full of junk (a reused slot must not keep stale fields)."""
    fails = []
    code = assemble("rf_brace", mutate)
    cases = (("two enemies", 1, 2, True, True), ("one enemy", 1, 1, True, True),
             ("no enemy", 1, 0, True, True), ("null list", 1, None, True, True),
             ("null reflector", 1, 2, False, True), ("null radius pointer", 1, 2, True, False),
             ("off", 0, 2, True, True))
    for name, mode, n, has_refl, has_radius in cases:
        for flags in (0x202, 0x8D7):
            mu = _machine(code)
            e = _entities(mu, tick=909)
            refl, en = e[0], e[1:3]
            mu.mem_write(refl + STATE_OFF, struct.pack("<I", 0x69))
            mu.mem_write(refl + POS_X, struct.pack("<ff", 12.5, 0.0))
            mu.mem_write(refl + POS_Z, struct.pack("<f", -40.25))
            for k, x in enumerate(en):
                mu.mem_write(x + CHARGER_STATE, struct.pack("<I", 30 + k))
                mu.mem_write(x + POS_X, struct.pack("<f", 14.0 + k))
                mu.mem_write(x + POS_Z, struct.pack("<f", -33.0 - k))
            lst, arr, radius = OBJ + 0xA0000, OBJ + 0xA1000, OBJ + 0xA2000
            mu.mem_write(arr, struct.pack("<QQ", *en))
            mu.mem_write(lst, struct.pack("<II", 0, n or 0) + struct.pack("<Q", arr))
            mu.mem_write(radius, struct.pack("<f", 36.0))
            mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
            mu.mem_write(B + BRACE_COUNT_AT, struct.pack("<I", BRACE_SLOTS + 5))
            slot = B + BRACE_RING_AT + 5 * BRACE_ENTRY
            mu.mem_write(slot, b"\xEE" * BRACE_ENTRY)
            rsp = STACK + 0x4000
            mu.mem_write(rsp, struct.pack("<Q", 0x14326A6BF) + bytes(0x28)
                         + struct.pack("<Q", radius if has_radius else 0) + bytes(8))
            regs = {"rdx": refl if has_refl else 0, "r8": 0x5151515151515101,
                    "r9": lst if n is not None else 0, "rsp": rsp}
            changed = _run(mu, code, regs, flags)
            if changed:
                fails.append(f"rf_brace {name}/{flags:#x}: registers changed {changed}")
            cnt = _u32(mu, B + BRACE_COUNT_AT) - (BRACE_SLOTS + 5)
            ent = bytes(mu.mem_read(slot, BRACE_ENTRY))
            if mode == 0:
                if cnt or ent != b"\xEE" * BRACE_ENTRY:
                    fails.append(f"rf_brace {name}: logged in mode 0")
                continue
            want = bytearray(BRACE_ENTRY)
            r = refl if has_refl else 0
            struct.pack_into("<QQIIII", want, 0, r, (0xAA0000 + r) if r else 0, 0x69 if r else 0, 1,
                             n or 0, 909 if r else 0)
            struct.pack_into("<fff", want, 32, 12.5 if r else 0.0, -40.25 if r else 0.0,
                             36.0 if has_radius else 0.0)
            for k in range(min(n or 0, 2)):
                x = en[k]
                struct.pack_into("<QQIff", want, 48 + 32 * k, x, 0xAA0000 + x, 30 + k, 14.0 + k, -33.0 - k)
            struct.pack_into("<I", want, 124, BRACE_SLOTS + 6)
            if cnt != 1 or ent != bytes(want):
                fails.append(f"rf_brace {name}/{flags:#x}: count {cnt}, entry differs at "
                             f"{[i for i in range(BRACE_ENTRY) if ent[i] != want[i]][:8]}")
    return fails


def _check_act(name_site, which, mutate):
    """rf_act1 / rf_act2 on synthetic calls: every field, the mode switch, null links, junk slot."""
    fails = []
    code = assemble(name_site, mutate)
    for name, mode, kind in (("soldier", 1, "ok"), ("null soldier", 1, "nosoldier"),
                             ("null action", 1, "noaction"), ("off", 0, "ok")):
        for flags in (0x202, 0x8D7):
            mu = _machine(code)
            e = _entities(mu, tick=606)
            soldier, action = e[0], OBJ + 0xB0000
            mu.mem_write(soldier + STATE_OFF, struct.pack("<I", 0x69))
            mu.mem_write(action + 8, struct.pack("<Q", 0 if kind == "nosoldier" else soldier))
            mu.mem_write(action + ACT_ID, struct.pack("<I", 0x6A))
            mu.mem_write(action + ACT_FLAG1, b"\x01")
            mu.mem_write(action + ACT_FLAG2, b"\x02")
            mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
            mu.mem_write(B + ACT_COUNT_AT, struct.pack("<I", ACT_SLOTS + 9))
            slot = B + ACT_RING_AT + 9 * ENTRY
            mu.mem_write(slot, b"\xEE" * ENTRY)
            changed = _run(mu, code, {"rcx": 0 if kind == "noaction" else action, "rsp": STACK + 0x4000},
                           flags)
            if changed:
                fails.append(f"{name_site} {name}/{flags:#x}: registers changed {changed}")
            cnt = _u32(mu, B + ACT_COUNT_AT) - (ACT_SLOTS + 9)
            ent = bytes(mu.mem_read(slot, ENTRY))
            if mode == 0:
                if cnt or ent != b"\xEE" * ENTRY:
                    fails.append(f"{name_site} {name}: logged in mode 0")
                continue
            want = bytearray(ENTRY)
            s = soldier if kind == "ok" else 0
            struct.pack_into("<QQIIII", want, 0, s, (0xAA0000 + s) if s else 0, 0x69 if s else 0,
                             0 if kind == "noaction" else 0x6A, which, 606 if s else 0)
            if kind != "noaction":
                struct.pack_into("<II", want, 32, 1, 2)
            struct.pack_into("<I", want, 60, ACT_SLOTS + 10)
            if cnt != 1 or ent != bytes(want):
                fails.append(f"{name_site} {name}/{flags:#x}: count {cnt}, entry differs at "
                             f"{[i for i in range(ENTRY) if ent[i] != want[i]][:8]}")
    return fails


MUTANTS = (
    ("rf_refl", "mov qword ptr [r11 + 8], r9", "mov qword ptr [r11 + 8], r8"),
    ("rf_refl", f"[rsp + {8 * (REFL_PUSHES + 1) + 0x28}]", f"[rsp + {8 * (REFL_PUSHES + 1) + 0x20}]"),
    ("rf_refl", f"mov rax, qword ptr [rsp + {8 * (REFL_PUSHES + 1)}]",
     f"mov rax, qword ptr [rsp + {8 * REFL_PUSHES}]"),
    ("rf_refl", "    mov ecx, 1\nno_r9:", "    nop\nno_r9:"),
    ("rf_refl", "    pop rdx\n    mov dword ptr [r11 + 60], edx", "    pop rdx\n    mov dword ptr [r11 + 60], 0"),
    ("rf_dmg", "mov rcx, qword ptr [rbp + 0x3f]", "mov rcx, qword ptr [rbp + 0x37]"),
    ("rf_dmg", "mov ecx, dword ptr [rbp + 0x6f]", "mov ecx, dword ptr [rbp + 0x67]"),
    ("rf_dmg", "mov ecx, dword ptr [rsp + 32]", "mov ecx, dword ptr [rsp + 24]"),
    ("rf_dmg", "    mov qword ptr [r11 + 40], rax\n", "    nop\n"),
    # [d15-1118] the D15 fields and the mark
    ("rf_dmg", f"    cmp dword ptr [r11 + 56], {BRACED}\n    je d15_cost\n", "    jmp d15_cost\n"),
    ("rf_dmg", f"    cmp ecx, {COST_WINDOW}\n    jbe d15_fresh\n", "    jmp d15_fresh\n"),
    ("rf_dmg", f"    mov r8d, {mark.SPENT}\n", f"    mov r8d, {mark.STAMPED}\n"),
    ("rf_dmg", "    mov rcx, qword ptr [r12]\n", "    mov rcx, rdx\n"),
    ("rf_dmg", "    cmp eax, 6\n    jne d15_done\n", "    jmp d15_done\n"),
    ("rf_dmg", "    cmp eax, 6\n    jne d15_done\n", "    nop\n"),
    ("rf_dmg", f"    mov rcx, qword ptr [rcx + {PARENT:#x}]\n", "    xor ecx, ecx\n"),
    ("rf_dmg", "    mov dword ptr [rcx + 20], 3\n", "    mov dword ptr [rcx + 20], 4\n"),
    ("rf_dmg", "    mov dword ptr [r11 + 124], r9d\n", "    nop\n"),
    ("rf_dmg", f"    mov eax, dword ptr [rdx + {MAX_HP:#x}]\n", f"    mov eax, dword ptr [rdx + {CUR_HP:#x}]\n"),
    ("rf_dmg", "    jnz d15_buf\n", "    jmp d15_buf\n"),
    ("rf_dmg", f"    mov eax, dword ptr [rcx + {SIZE:#x}]\n", "    mov eax, 3\n"),
    ("rf_dmg", f"    mov eax, dword ptr [rcx + {MAX_HP:#x}]\n", "    mov eax, -1\n"),
    ("rf_dmg", "    pop r9\n", "    pop rax\n"),
    ("rf_brace", f"[rsp + {8 * (BRACE_PUSHES + 1) + 0x30}]", f"[rsp + {8 * (BRACE_PUSHES + 1) + 0x28}]"),
    ("rf_brace", f"mov ecx, dword ptr [rdx + {STATE_OFF:#x}]", "mov ecx, dword ptr [rdx + 0x31c]"),
    ("rf_brace", "cmp dword ptr [r9 + 4], 2", "cmp dword ptr [r9 + 4], 3"),
    ("rf_brace", "    pop rcx\n    mov dword ptr [r11 + 124], ecx", "    pop rcx\n    nop"),
    ("rf_brace", "    movzx ecx, r8b\n", "    xor ecx, ecx\n"),
    ("rf_brace", "    mov qword ptr [r11 + 64], rax\n", "    nop\n"),
    ("rf_act1", "mov dword ptr [r11 + 24], 1", "mov dword ptr [r11 + 24], 2"),
    ("rf_act1", f"mov eax, dword ptr [rcx + {ACT_ID:#x}]", "mov eax, dword ptr [rcx + 0x3c]"),
    ("rf_act2", f"mov eax, dword ptr [rcx + {STATE_OFF:#x}]", "mov eax, dword ptr [rcx + 0x31c]"),
    ("rf_act2", "    mov dword ptr [r11 + 60], edx\n", "    nop\n"),
    ("rf_dmg", "mov eax, dword ptr gs:[0x48]", "mov eax, dword ptr gs:[0x40]"),
    ("rf_dmg", f"lock xadd dword ptr [r10 + {CLOCK_AT}], eax", f"mov eax, dword ptr [r10 + {CLOCK_AT}]"),
    ("rf_cgate", f"[rsp + {8 * CR_PUSHES + CALC_RET_FRAME:#x}]", f"[rsp + {8 * (CR_PUSHES - 1) + CALC_RET_FRAME:#x}]"),
    ("rf_cgate", "    jne no_ret2\n", "    nop\n"),
    ("rf_cgate", "movss dword ptr [r11 + 44], xmm7", "movss dword ptr [r11 + 44], xmm6"),
    ("rf_cmul", "mov dword ptr [r11 + 32], 2", "mov dword ptr [r11 + 32], 1"),
    ("rf_cmul", "mov rax, qword ptr [rbx + 0x10]", "mov rax, qword ptr [rbx + 0x18]"),
    ("rf_cmul", "movss dword ptr [r11 + 56], xmm8", "nop"),
)


def negative_controls():
    """[mutant] whose broken cave passed every case (must be empty)."""
    return [m for m in MUTANTS if not check(m[1:], which=m[0])]


def _regex(pattern):
    return re.compile(b"".join(b"." if t == "??" else re.escape(bytes([int(t, 16)]))
                               for t in pattern.split()), re.S)


SITES = {"rf_refl": (REFL_PATTERN, 0, REFL_STOLEN), "rf_dmg": (DMG_PATTERN, DMG_AT, DMG_STOLEN),
         "rf_brace": (BRACE_PATTERN, 0, BRACE_STOLEN), "rf_act1": (ACT1_PATTERN, 0, ACT1_STOLEN),
         "rf_act2": (ACT2_PATTERN, 0, ACT2_STOLEN),
         "rf_cgate": (CGATE_PATTERN, CGATE_AT, CGATE_STOLEN), "rf_cmul": (CMUL_PATTERN, CMUL_AT, CMUL_STOLEN)}


def check_exe(exe_path):
    """{cave: virtual address}: each pattern exactly once in the exe's code with the stolen bytes
    at the site, and at the address of the static read (EXE_SITES); refuses otherwise."""
    import pefile
    pe = pefile.PE(str(exe_path), fast_load=True)
    code = [(pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress, s.get_data())
            for s in pe.sections if s.Characteristics & 0x20000000]
    found = {}
    for name, (pattern, at, stolen) in SITES.items():
        want = bytes.fromhex(stolen.replace(" ", ""))
        hits = [va + m.start() + at for va, data in code for m in _regex(pattern).finditer(data)
                if data[m.start() + at:m.start() + at + len(want)] == want]
        if hits != [EXE_SITES[name]]:
            raise SystemExit(f"[reflect_probe] REFUSING: {name} found at {[hex(h) for h in hits]}, "
                             f"want {EXE_SITES[name]:#x} (another build?)")
        found[name] = hits[0]
    return found


def _template(code):
    out, i, mark = [], 0, struct.pack("<Q", BUF)
    while i < len(code):
        if code[i:i + 8] == mark:
            out.append("{buf:8}")
            i += 8
        else:
            out.append(f"{code[i]:02X}")
            i += 1
    return " ".join(out)


def site_lua(codes):
    lines = ["-- TEST-ONLY, generated by tools/pipelines/reflect_probe_asm.py; never in a player's pack",
             "return {", f"    owner = '{OWNER}', feature = '{FEATURE}',", "    entries = {"]
    for n in SOURCES:
        pattern, at, stolen = SITES[n]
        lines += [f"        {{ name = '{n}', feature = '{FEATURE}', kind = 'cave',",
                  f"          pattern = '{pattern}', at = {at}, expect = '{stolen}',",
                  f"          bytes = '{_template(codes[n])}' }},"]
    lines += ["    },", "    caves = { " + ", ".join(f"'{n}'" for n in SOURCES) + " },",
              f"    layout = {{ bytes = {BYTES}, mode_at = {MODE_AT}, magic_at = {MAGIC_AT}, "
              f"magic = '{MAGIC.decode()}',",
              f"        refl_count_at = {REFL_COUNT_AT}, refl_ring_at = {REFL_RING_AT}, "
              f"refl_slots = {REFL_SLOTS},",
              f"        dmg_count_at = {DMG_COUNT_AT}, dmg_ring_at = {DMG_RING_AT}, dmg_slots = {DMG_SLOTS}, "
              f"dmg_entry = {DMG_ENTRY}, dive_at = {DIVE_AT}, cost_window = {COST_WINDOW}, braced = {BRACED},",
              "        cost_share = { " + ", ".join(repr(v) for v in COST_SHARE_BY_CODE) + " }, "
              f"cost_max_call = {air_dive_rules.DIVE_COST_MAX_CALL}, "
              f"cost_keep = {air_dive_rules.DIVE_COST_KEEP_UNARY}, "
              f"cost_follow = {air_dive_rules.DIVE_COST_FOLLOW_TICKS},",
              f"        brace_count_at = {BRACE_COUNT_AT}, brace_ring_at = {BRACE_RING_AT}, "
              f"brace_slots = {BRACE_SLOTS}, brace_entry = {BRACE_ENTRY},",
              f"        act_count_at = {ACT_COUNT_AT}, act_ring_at = {ACT_RING_AT}, act_slots = {ACT_SLOTS},",
              f"        clock_at = {CLOCK_AT}, cr_count_at = {CR_COUNT_AT}, cr_ring_at = {CR_RING_AT}, "
              f"cr_slots = {CR_SLOTS}, cr_entry = {CR_ENTRY},",
              f"        entry = {ENTRY} }},", "}"]
    return "\n".join(lines) + "\n"


def build_site():
    """(site Lua text, report): assemble, emulator check, negative controls; refuses on any failure."""
    codes = {n: assemble(n) for n in SOURCES}
    fails = check()
    survivors = [] if fails else negative_controls()
    if fails or survivors:
        raise SystemExit("[reflect_probe] REFUSING: "
                         + "; ".join(fails + [f"mutant not caught: {m}" for m in survivors]))
    return site_lua(codes), (f"caves {', '.join(f'{n} {len(c)} B' for n, c in codes.items())}; "
                             f"emulator PASS; {len(MUTANTS)} mutants, each caught")


def main(argv):
    exe = Path(r"D:/SteamLibrary/steamapps/common/Total War WARHAMMER III/Warhammer3.exe")
    found = check_exe(exe)
    text, report = build_site()
    print(report + "; exe sites " + ", ".join(f"{k} {v:#x}" for k, v in found.items()))
    if "--write-site" in argv:
        out = Path(argv[argv.index("--write-site") + 1])
        out.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
