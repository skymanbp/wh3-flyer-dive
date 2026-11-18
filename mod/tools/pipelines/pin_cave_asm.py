"""Machine code of the pin-on-hit take-off caves, their emulator check and the
generated site table.

[D3, user ruling 2026-11-17, docs/DECISIONS.md; implemented D3-1118] RULE:
a flying MODEL is held on the ground (its take-off countdown re-armed) only
while it was struck in melee within the last N battle ticks, N by its own
body size (``air_dive_rules.takeoff_window_table``: small 45, medium 40,
large 35, very large 30 = 4.5 / 4.0 / 3.5 / 3.0 s). Each model is judged on
its own: in a unit of many, the struck ones stay down and the others may
lift off. A ridden unit is judged on its mount (the flying entity, the one
that carries the flight controller). Contact without hits, ranged and
explosion hits, and a charge's collision damage do not hold it. Replaces the
whole-unit rules of §C8-58 / §C8-78 and, before them, the first take-off
patch (the countdown always ran, so a flyer left 3.0 s after the order
whatever was hitting it).

Two caves in Warhammer3.exe 9.0.5 (6ae2a00b), installed by memreader Plus
through the generated site table (``--write-site``):

STAMP ``pin_stamp`` at the entry of the damage applier 0x14325a9c4, which
every kind of damage on a model goes through (25 call sites). Entry: rcx =
damage context ([ctx+8] = the victim entity, the applier's own first read),
r8d = damage, [rsp+0x30] = the damage type (6th argument; the applier keeps
it in r15d and compares it with 2 and 4). The caller writes the type: 0 for
melee -- the hit processor 0x14326cd24 and its immediate twin 0x14325b54c
(single-target weapon hits), the splash attack 0x143087068 (a lord, hero or
monster striking several models in its arc), the matched-combat steps
0x142f72320 / 0x142f8e0f8 / 0x142f8cc94 (synced duel animations) -- 6 for a
charge's collision attack 0x143060e44, 5 for an impact 0x143061144, 1..4
for ranged / explosion 0x1430aaa88, 2 / 3 for abilities and the rest.
For type 0 with damage > 0 the cave finds the flying entity the hit lands on
-- the victim itself when it has a flight controller (entity +0x128), else
the first one up its parent chain (+0x2e0, rider -> mount; at most CHAIN_MAX
entities, the engine walks the same chain at 0x14325d45e) -- and writes the
battle tick into that entity's table entry (claimed with lock cmpxchg on
first use). A victim that is no flyer costs the two reads. Stolen bytes: the
applier's first instructions ``mov [rsp+0x10],rbx; push rbp; push rsi;
push rdi; push r12`` (10 bytes, no jump, nothing rip-relative). Every
register and the flags come back unchanged.
[D11, gapfix-1118] RAISE: in mode 1, after recording the hit, the stamp cave
looks at that flying entity's flight controller FC; when its countdown
FC+0x44 is 0 and its phase FC+0x90 is one of RAISE_PHASES (1 on the ground,
2 take-off requested), and a living flight entity of its unit carries FC (the
hold cave's own test), it raises the countdown to RAISE_TO with
``lock cmpxchg`` (0 -> 1 only). Measured (series 4 run 1, traced caves):
every hit lands after that tick's flight update, and the next update lifts a
phase-2 model at countdown 0 in its state machine (0x14301b8d4) BEFORE the
gate 0x143053ce3, which asks the rule only when the countdown is above 0 or
the phase is 1 -- so a model hit at countdown 0 and ordered away at once left
without the rule being asked. With the countdown at 1 the state machine does
not lift, the gate asks, and a "held" answer re-arms 30 ticks. The engine
decrements the countdown only after the gate (0x143053d8b, which writes back
nothing when it read 0), so the 1 reaches the gate. The compare-exchange
never lowers a countdown and never replaces one the engine wrote meanwhile.
Mode 2 (record only) does not raise: the stock check stays untouched there.
[FLYER-TAKEOFF-HITS 2026-11-16] Replaces two stamps inside the hit processor
and its twin (0x14326ce15 / 0x14325b597), which saw only single-target
weapon hits. A logger at the applier entry (custom battles, four flyers
each) counted the damaging melee calls on flyers those two recorded:
against swordsmen 126 of 129, against chosen 193 of 198, against a chaos
lord (splash) 4 of 26, against a giant (splash + matched combat) 2 of 54 --
a flyer fought by a lord, hero or monster was almost never held.

HOLD ``pin_hold`` at 0x143053cfb, in the per-model flight update 0x143053bd4,
where the stock code asks the engaged check ``call 0x143026588(rcx = FC)``
whether to re-arm the take-off countdown FC+0x44 (30 ticks). Stolen bytes:
``mov rcx,rbx`` + that call (8 bytes). rbx = FC, [FC] = model, [model+0x2e8]
= unit, [model+0x58] -> the battle tick; unit +0x184 (count) / +0x188 (array
of pointers) = its living flight entities (the engine's own loop over them,
0x14305018b, reads each one's FC at +0x128; the list shrinks when a model
dies). Mode 1 [D3-1118]: the cave finds the living flight entity whose FC is
rbx (the model asking: the flying body, i.e. the mount of a ridden unit; the
stamp cave keys the same entity), reads its size code at +0x74 (1 small ..
4 very large, measured 2026-11-18; anchor ``pin_layout_size``), takes the
window for that code from the buffer (any other value: the unknown-size
window, counted), and answers al = 1 (hold) when that entity's table entry is
younger than the window, else al = 0; then it jumps to the instruction after
the call (``test al,al``), skipping the engaged check. An FC that no living
entity of its unit carries is answered "free" and counted (``unmatched``).
Any other mode: the cave does nothing and the original check runs.
Registers a call may clobber change (rax rcx rdx r8-r11, flags); rbx rsi rdi
rbp r12-r15 rsp come back unchanged (the cave touches none of them).

Buffer (game_alloc, little endian), 64-byte header then the table:
  +0  u32 unused (0)             +4  u32 mode: 0 off, 1 the rule, 2 record
  +8  u32 stamps (hits recorded)     only (stamps kept, stock hold; tests)
  +12 u32 allowed (Lua only: the campaign's agreement said yes)
  +16 8 bytes MAGIC              +24 u32 dropped (no free entry in reach)
  +28 u32 unmatched (an FC no living entity of its unit carries)
  +32 u32 "hold" answers         +36 u32 "free" answers (mode 1)
  +40 u32 unsized (answers that used the unknown-size window)
  +44 5 x u32 windows in ticks: size code 1, 2, 3, 4, then unknown size
  +64 TABLE_SLOTS x 16 bytes: u64 flying entity, u32 tick, u32 hits
Entry of pointer p: slot ((p>>4) ^ (p>>17) ^ (p>>30)) & (TABLE_SLOTS-1), then
linear probing, at most PROBES entries. Entries are never freed inside a
battle; the Lua side clears the table when a battle loads. A hit that finds
no entry in reach is dropped (counted), so a full table errs towards "free".

The site table also carries ANCHORS: pieces of the engine's own code that use
the same fields (the flight-entity list, the unit back-reference, the battle
tick, the parent link, the size code) and the callers that pass a non-melee damage type
(charge 6, impact 5, ranged 1..4); the stamp site's own pattern pins the
applier's victim, damage and damage-type reads. The site loader needs every
one exactly once, so a game update that moves a field turns the feature off
instead of letting the caves read the wrong memory.

``python pin_cave_asm.py`` (needs keystone + unicorn) assembles the caves,
runs them in Unicorn against synthetic objects (see ``check``), then runs the
same cases against mutated sources that must each fail (``MUTANTS``).
``--write-site`` writes the site table when everything passed. Importing the
module needs neither package: ``check_site_file`` / ``check_exe`` are what
build_air_dive_minimod.py calls.
"""
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
import rolepath  # noqa: F401 -- because the import puts the role directories on sys.path

import air_dive_rules
import cave_site_text  # TEST-REPAIR-1113: the template and entry lines have one home

OWNER = air_dive_rules.TAKEOFF_OWNER
FEATURE = air_dive_rules.TAKEOFF_FEATURE
BUILD = air_dive_rules.TAKEOFF_BUILD
SITE_LUA = air_dive_rules.TAKEOFF_SITE_LUA_PATH
# [D3-1118] windows by the engine's size code 1..4, then the unknown-size window
WINDOWS = tuple(air_dive_rules.takeoff_window_table())
SIZE_CODES = dict(air_dive_rules.TAKEOFF_SIZE_CODES)

# --- buffer layout ----------------------------------------------------------
MODE_AT, STAMPS_AT, ALLOWED_AT, MAGIC_AT = 4, 8, 12, 16
DROPPED_AT, UNMATCHED_AT, HELD_AT, FREE_AT, UNSIZED_AT = 24, 28, 32, 36, 40
WINDOWS_AT = 44                     # 5 x u32, ends at 64
TABLE_AT, ENTRY_BYTES = 64, 16
TABLE_SLOTS = 8192                  # power of two
PROBES = 64
BUFFER_BYTES = TABLE_AT + TABLE_SLOTS * ENTRY_BYTES
# 2: +40 single-model window (§C8-78); 3: renamed (RENAME-1118); 4: per model by body size (D3)
# 5: the stamp cave raises a 0 countdown before lift-off (D11, gapfix-1118)
MAGIC = b"FLYPINS5"
MAX_MODELS = 1024                   # a larger flight list is not judged (free)
CHAIN_MAX = 4                       # victim + three ancestors
BUFFER_PLACEHOLDER = 0x1122334455667788
RESUME_PLACEHOLDER = 0x8877665544332211

# --- engine fields (9.0.5; each one is pinned by an anchor below) -----------
FC_OFF = 0x128                      # entity -> its flight controller (0: no flyer)
PARENT_OFF = 0x2E0                  # entity -> the entity it rides (0: none)
UNIT_OFF = 0x2E8                    # entity -> its unit
BATTLE_OFF, TICKS_OFF, TICK_OFF = 0x58, 0x440, 0x98
LIST_COUNT_OFF, LIST_OFF = 0x184, 0x188   # unit: living flight entities
SIZE_OFF = 0x74                     # flying entity: body size code 1..4 (D3-1118)
COUNT_OFF, PHASE_OFF = 0x44, 0x90   # FC: take-off countdown, flight phase (D11)
# [D11] the stamp cave's raise: a 0 countdown of a model in one of these phases becomes RAISE_TO
RAISE_TO = air_dive_rules.TAKEOFF_GAP_RAISE_TO
RAISE_PHASES = tuple(air_dive_rules.TAKEOFF_GAP_RAISE_PHASES)

# --- sites ------------------------------------------------------------------
# name -> (pattern, at, expected original bytes, "stamp" / "hold")
CAVES = {
    # 0x14325a9c4, the damage applier: the 7 pushes and lea rbp,[rsp-7] put the
    # damage type at [rbp+0x6f] = entry [rsp+0x30]; mov rdx,[rcx+8] (victim);
    # mov eax,r8d (damage); mov r15d,[rbp+0x6f]; cmp r15d,2
    "pin_stamp": ("48 89 5C 24 10 55 56 57 41 54 41 55 41 56 41 57 48 8D 6C 24 F9 "
                  "48 81 EC A0 00 00 00 0F 57 C0 48 8B DA 48 8B 51 08 4D 8B E1 48 8B F9 "
                  "48 8B 42 58 4C 8B 90 40 04 00 00 41 8B C0 4D 8B 9A A8 00 00 00 "
                  "F3 48 0F 2A C0 F3 41 0F 59 83 C0 02 00 00 E8 ?? ?? ?? ?? "
                  "44 8B 7D 6F 44 8B F0 44 8A 6D 67 89 45 57 41 83 FF 02", 0,
                  "48 89 5C 24 10 55 56 57 41 54", "stamp"),
    "pin_hold": ("48 8B CB E8 ?? ?? ?? ?? 84 C0 0F 84 ?? ?? ?? ?? 44 38 63 64 74", 0,
                 "48 8B CB E8", "hold"),
}
HOLD_NAME, HOLD_RESUME_AT = "pin_hold", 8      # resume at `test al,al`
MELEE = 0                                      # the applier's damage type of a melee hit
TYPE_ARG = 0x30                                # entry rsp offset of the damage type
# name -> (pattern, what it pins)
ANCHORS = {
    # 0x14305018b: cmp [rdx+0x184],r14d; jbe; mov rax,[rdx+0x188]; mov ecx,ebp;
    #              mov r8,[rax+rcx*8]; mov rdi,[r8+0x128]; test rdi,rdi
    "pin_layout_list": ("44 39 B2 84 01 00 00 0F 86 ?? ?? ?? ?? 48 8B 82 88 01 00 00 "
                        "8B CD 4C 8B 04 C8 49 8B B8 28 01 00 00 48 85 FF",
                        "unit +0x184/+0x188 flight entities, entity +0x128 FC"),
    # 0x14326d2d8 (hit processor, parry branch): mov rcx,[rdi+0x2e8]; test; je; call; mov [rbp+0xb1],al
    "pin_layout_unit": ("48 8B 8F E8 02 00 00 48 85 C9 74 ?? E8 ?? ?? ?? ?? 88 85 B1 00 00 00",
                        "entity +0x2e8 unit"),
    # 0x14308fc27: mov rax,[rdi+0x58]; mov rcx,[rax+0x440]; mov eax,[rcx+0x98]; cmp [rdi+0xae4],eax; jae
    "pin_layout_tick": ("48 8B 47 58 48 8B 88 40 04 00 00 8B 81 98 00 00 00 39 87 E4 0A 00 00 73",
                        "entity +0x58 -> +0x440 -> +0x98 battle tick"),
    # 0x14325d45e: mov rax,[rdi+0x2e0]; jmp; mov rdi,rax; mov rax,[rax+0x2e0]; test rax,rax; jne; mov rax,[rdi]
    "pin_layout_parent": ("48 8B 87 E0 02 00 00 EB ?? 48 8B F8 48 8B 80 E0 02 00 00 "
                          "48 85 C0 75 F1 48 8B 07",
                          "entity +0x2e0 parent chain"),
    # 0x143061598 (knock code): mov eax,[rsi+0x74]; cmp eax,[rdi+0x74]; jle; sub eax,[rdi+0x74];
    # cmp eax,1 -- the engine orders two entities by this field. Read in game 2026-11-18 on every
    # flying entity: 1 small, 2 medium, 3 large, 4 very large (ingame_1118 item2_1, item6_1, item6_2).
    "pin_layout_size": ("8B 46 74 3B 47 74 7E ?? 2B 47 74 83 F8 01",
                        "entity +0x74 body size code"),
    # the callers whose damage must not hold a flyer pass a non-melee type:
    # 0x143061087 charge's collision attack: mov dword [rsp+0x28],6 before its applier call
    "pin_kind_charge": ("C7 44 24 28 06 00 00 00 C6 44 24 20 01 F3 0F 11 45 0F 48 89 7D E7 E8",
                        "damage type 6: a charge's collision attack"),
    # 0x143061945 impact: mov dword [rsp+0x28],5
    "pin_kind_impact": ("4C 8D 4C 24 70 C7 44 24 28 05 00 00 00 48 8D 95 90 00 00 00 49 8B CC "
                        "C6 44 24 20 01 E8", "damage type 5: an impact"),
    # 0x1430aab65 ranged / explosion: and r8d,3; inc r8d; mov [rsp+0x28],r8d (1..4)
    "pin_kind_ranged": ("41 83 E0 03 41 FF C0 88 5C 24 30 44 89 44 24 28 44 8B C0 88 54 24 20 "
                        "48 8B D7 E8", "damage type 1..4: ranged and explosions"),
}


def slot_of(pointer):
    """The caves' home slot of an entity pointer."""
    return ((pointer >> 4) ^ (pointer >> 17) ^ (pointer >> 30)) & (TABLE_SLOTS - 1)


def _mutated(text, kind, mutate):
    """``text`` with the (kind, old, new) edits of ``mutate`` meant for this kind of cave."""
    for target, old, new in mutate:
        if target != kind:
            continue
        if text.count(old) != 1:
            raise SystemExit(f"mutant: {old!r} found {text.count(old)} times in the {kind} "
                             "source, want 1")
        text = text.replace(old, new)
    return text


def _tick(reg_model, out32, fail):
    """now (u32) of the battle of model ``reg_model`` into ``out32``; rax scratch."""
    return f"""
        mov rax, [{reg_model} + {BATTLE_OFF:#x}]
        test rax, rax
        jz {fail}
        mov rax, [rax + {TICKS_OFF:#x}]
        test rax, rax
        jz {fail}
        mov {out32}, dword ptr [rax + {TICK_OFF:#x}]
    """


def _hash(key, out, scratch):
    """slot_of(``key``) into the 32-bit half of ``out`` (64-bit names in)."""
    out32 = {"rax": "eax"}[out]
    return f"""
        mov {out}, {key}
        shr {out}, 4
        mov {scratch}, {key}
        shr {scratch}, 17
        xor {out}, {scratch}
        mov {scratch}, {key}
        shr {scratch}, 30
        xor {out}, {scratch}
        and {out32}, {TABLE_SLOTS - 1}
    """


STAMP_PUSHES = 8                    # flags + 7 registers


def _phase_test(reg, yes, no):
    """Jump to ``yes`` when ``reg`` holds one of RAISE_PHASES, else to ``no``."""
    if not RAISE_PHASES or any(not isinstance(p, int) or p < 0 for p in RAISE_PHASES):
        raise SystemExit(f"[pin_cave_asm] REFUSING: raise phases {RAISE_PHASES!r}")
    return "".join(f"        cmp {reg}, {p}\n        je {yes}\n" for p in RAISE_PHASES) + f"        jmp {no}"


def stamp_source(mutate=()):
    return _mutated(f"""
        pushfq
        push rax
        push rcx
        push rdx
        push r8
        push r9
        push r10
        push r11
        mov r10, {BUFFER_PLACEHOLDER:#x}
        cmp dword ptr [r10 + {MODE_AT}], 0
        je done
        cmp dword ptr [rsp + {8 * STAMP_PUSHES + TYPE_ARG:#x}], {MELEE}
        jne done
        cmp r8d, 0
        jle done
        mov rcx, qword ptr [rcx + 8]
        test rcx, rcx
        jz done
        mov edx, {CHAIN_MAX}
    find_fc:
        cmp qword ptr [rcx + {FC_OFF:#x}], 0
        jne keyed
        mov rcx, [rcx + {PARENT_OFF:#x}]
        test rcx, rcx
        jz done
        dec edx
        jnz find_fc
        jmp done
    keyed:
        {_tick("rcx", "r8d", "done")}
        lock inc dword ptr [r10 + {STAMPS_AT}]
        {_hash("rcx", "rax", "rdx")}
        mov r9d, eax
        mov r11d, {PROBES}
    probe:
        mov edx, r9d
        shl rdx, 4
        lea rdx, [r10 + rdx + {TABLE_AT}]
        mov rax, [rdx]
        cmp rax, rcx
        je write
        test rax, rax
        jnz next
        lock cmpxchg [rdx], rcx
        je write
        cmp rax, rcx
        je write
    next:
        inc r9d
        and r9d, {TABLE_SLOTS - 1}
        dec r11d
        jnz probe
        lock inc dword ptr [r10 + {DROPPED_AT}]
        jmp done
    write:
        mov dword ptr [rdx + 8], r8d
        lock inc dword ptr [rdx + 12]
    raise:
        cmp dword ptr [r10 + {MODE_AT}], 1
        jne raise_done
        mov r8, qword ptr [rcx + {FC_OFF:#x}]
        test r8, r8
        jz raise_done
        cmp dword ptr [r8 + {COUNT_OFF:#x}], 0
        jne raise_done
        mov eax, dword ptr [r8 + {PHASE_OFF:#x}]
{_phase_test("eax", "raise_live", "raise_done")}
    raise_live:
        mov rdx, qword ptr [rcx + {UNIT_OFF:#x}]
        test rdx, rdx
        jz raise_done
        mov eax, dword ptr [rdx + {LIST_COUNT_OFF:#x}]
        lea r9d, [rax - 1]
        cmp r9d, {MAX_MODELS - 1}
        ja raise_done
        mov rdx, qword ptr [rdx + {LIST_OFF:#x}]
        test rdx, rdx
        jz raise_done
    raise_own:
        mov r9, qword ptr [rdx]
        test r9, r9
        jz raise_next
        cmp qword ptr [r9 + {FC_OFF:#x}], r8
        je raise_found
    raise_next:
        add rdx, 8
        dec eax
        jnz raise_own
        jmp raise_done
    raise_found:
        xor eax, eax
        mov edx, {RAISE_TO}
        lock cmpxchg dword ptr [r8 + {COUNT_OFF:#x}], edx
    raise_done:
    done:
        pop r11
        pop r10
        pop r9
        pop r8
        pop rdx
        pop rcx
        pop rax
        popfq
    """, "stamp", mutate)


def hold_source(mutate=()):
    return _mutated(f"""
        mov r9, {BUFFER_PLACEHOLDER:#x}
        cmp dword ptr [r9 + {MODE_AT}], 1
        jne passthrough
        mov rcx, [rbx]
        test rcx, rcx
        jz free
        mov rdx, [rcx + {UNIT_OFF:#x}]
        test rdx, rdx
        jz free
        {_tick("rcx", "r8d", "free")}
        mov ecx, dword ptr [rdx + {LIST_COUNT_OFF:#x}]
        lea eax, [rcx - 1]
        cmp eax, {MAX_MODELS - 1}
        ja free
        mov rdx, [rdx + {LIST_OFF:#x}]
        test rdx, rdx
        jz free
    own:
        mov rax, [rdx]
        test rax, rax
        jz own_next
        cmp qword ptr [rax + {FC_OFF:#x}], rbx
        je found
    own_next:
        add rdx, 8
        dec ecx
        jnz own
        lock inc dword ptr [r9 + {UNMATCHED_AT}]
        jmp free
    found:
        mov rcx, rax
        mov eax, dword ptr [rcx + {SIZE_OFF:#x}]
        dec eax
        cmp eax, 3
        jbe sized
        lock inc dword ptr [r9 + {UNSIZED_AT}]
        mov eax, 4
    sized:
        mov r10d, dword ptr [r9 + rax*4 + {WINDOWS_AT}]
        {_hash("rcx", "rax", "rdx")}
        mov r11d, {PROBES}
    look:
        mov edx, eax
        shl rdx, 4
        lea rdx, [r9 + rdx + {TABLE_AT}]
        cmp [rdx], rcx
        je hit
        cmp qword ptr [rdx], 0
        je free
        inc eax
        and eax, {TABLE_SLOTS - 1}
        dec r11d
        jnz look
        jmp free
    hit:
        mov eax, r8d
        sub eax, dword ptr [rdx + 8]
        cmp eax, r10d
        jae free
        lock inc dword ptr [r9 + {HELD_AT}]
        mov eax, 1
        jmp resume
    free:
        lock inc dword ptr [r9 + {FREE_AT}]
        xor eax, eax
    resume:
        mov r11, {RESUME_PLACEHOLDER:#x}
        jmp r11
    passthrough:
    """, "hold", mutate)


def cave_source(name, mutate=()):
    return hold_source(mutate) if CAVES[name][3] == "hold" else stamp_source(mutate)


def layout():
    return {"bytes": BUFFER_BYTES, "mode_at": MODE_AT,
            "stamps_at": STAMPS_AT, "allowed_at": ALLOWED_AT, "magic_at": MAGIC_AT,
            "magic": MAGIC.decode(), "dropped_at": DROPPED_AT, "unmatched_at": UNMATCHED_AT,
            "held_at": HELD_AT, "free_at": FREE_AT, "unsized_at": UNSIZED_AT,
            "table_at": TABLE_AT, "table_slots": TABLE_SLOTS, "entry_bytes": ENTRY_BYTES,
            "windows_at": WINDOWS_AT, "windows": list(WINDOWS),
            "size_codes": dict(sorted(SIZE_CODES.items())), "size_at": SIZE_OFF}


def source_sha():
    """sha256 over the three cave sources (with the placeholders), the sites,
    the anchors and the layout. The site table records it, so an edit here
    without regenerating is caught offline (``check_site_file``)."""
    norm = lambda s: "\n".join(line.strip() for line in s.splitlines() if line.strip())
    blob = json.dumps({"caves": {n: [list(CAVES[n][:3]), norm(cave_source(n))] for n in CAVES},
                       "anchors": {n: ANCHORS[n][0] for n in ANCHORS},
                       "hold": [HOLD_NAME, HOLD_RESUME_AT], "layout": layout(),
                       "owner": OWNER, "feature": FEATURE, "build": BUILD}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def agreement_format():
    """The agreement step's ``format`` (a whole number, exact in a 32-bit
    float): players whose caves differ are told they run another version."""
    return 2 + int(source_sha()[:5], 16)


def assemble(name, mutate=()):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_64
    code, _ = Ks(KS_ARCH_X86, KS_MODE_64).asm(cave_source(name, mutate), 0x1000)
    return bytes(code)


def bytes_template(code):
    """The site loader's cave template: hex bytes with {buf:8} / {resume:8}."""
    return cave_site_text.bytes_template(code, BUFFER_PLACEHOLDER, RESUME_PLACEHOLDER)


def filled(code, buffer, resume):
    """``code`` with the two placeholders filled the way the site loader does."""
    for ph, value in ((BUFFER_PLACEHOLDER, buffer), (RESUME_PLACEHOLDER, resume)):
        code = code.replace(struct.pack("<Q", ph), struct.pack("<Q", value))
    return code


# --- emulator ---------------------------------------------------------------
CODE, BUF, STACK, OBJ, WORLD, BLOCK, UNIT, RESUME = (
    0x100000, 0x200000, 0x400000, 0x500000, 0x600000, 0x700000, 0x800000, 0x900000)
BATTLE, TICKS, ARRAY = WORLD, WORLD + 0x10000, UNIT + 0x10000
FCS, FC_STRIDE, FCS_BYTES = 0xA00000, 0x100, 0x200000     # one flight controller per flyer
BIG, BIG_STRIDE, BIG_BYTES = 0x1000000, 0x400, 0x120000   # entities of the large-unit cases
FLAGS = 0x0247
CODE_OF = {size: code for size, code in SIZE_CODES.items()}
WINDOW_OF = {size: WINDOWS[code - 1] for size, code in SIZE_CODES.items()}
UNKNOWN_WINDOW = WINDOWS[4]
BODY_SIZES_IN_ORDER = air_dive_rules.BODY_SIZES


def model_at(index):
    """Address of synthetic model ``index`` (0..63)."""
    return OBJ + index * 0x1000


# A synthetic model whose home slot is the table's last one (wrap-around).
EDGE_MODEL = OBJ + 0x1FD70


class Machine:
    """The caves and one battle's memory in Unicorn."""

    def __init__(self, mutate=()):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
        import unicorn.x86_const as x
        self.x = x
        self.all = (x.UC_X86_REG_RAX, x.UC_X86_REG_RBX, x.UC_X86_REG_RCX, x.UC_X86_REG_RDX,
                    x.UC_X86_REG_RSI, x.UC_X86_REG_RDI, x.UC_X86_REG_RBP, x.UC_X86_REG_R8,
                    x.UC_X86_REG_R9, x.UC_X86_REG_R10, x.UC_X86_REG_R11, x.UC_X86_REG_R12,
                    x.UC_X86_REG_R13, x.UC_X86_REG_R14, x.UC_X86_REG_R15)
        self.callee_saved = (x.UC_X86_REG_RBX, x.UC_X86_REG_RSI, x.UC_X86_REG_RDI,
                             x.UC_X86_REG_RBP, x.UC_X86_REG_R12, x.UC_X86_REG_R13,
                             x.UC_X86_REG_R14, x.UC_X86_REG_R15)
        uc = self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        uc.mem_map(CODE, 0x10000)
        uc.mem_map(BUF, 0x10000 * ((BUFFER_BYTES + 0xFFFF) // 0x10000))
        uc.mem_map(STACK, 0x10000)
        uc.mem_map(OBJ, 0x40000)
        uc.mem_map(WORLD, 0x20000)
        uc.mem_map(BLOCK, 0x10000)
        uc.mem_map(UNIT, 0x20000)
        uc.mem_map(RESUME, 0x1000)
        uc.mem_map(FCS, FCS_BYTES)
        uc.mem_map(BIG, BIG_BYTES)
        uc.mem_write(RESUME, b"\xf4")
        self.code = {}
        for i, name in enumerate(CAVES):
            code = filled(_assembled(name, tuple(mutate)), BUF, RESUME)
            self.code[name] = (CODE + 0x1000 * i, len(code))
            uc.mem_write(CODE + 0x1000 * i, code)
        self.reset()

    # -- the battle's memory
    def reset(self, windows=WINDOWS, mode=1):
        self.uc.mem_write(BUF, bytes(BUFFER_BYTES))
        self.uc.mem_write(BUF + MODE_AT, struct.pack("<I", mode))
        self.uc.mem_write(BUF + WINDOWS_AT, struct.pack("<5I", *windows))
        self.uc.mem_write(BUF + MAGIC_AT, MAGIC)
        self.uc.mem_write(OBJ, bytes(0x40000))
        self.uc.mem_write(FCS, bytes(FCS_BYTES))
        self.uc.mem_write(BIG, bytes(BIG_BYTES))
        self.living([])
        self.models, self.fc_of = set(), {}
        self.now(0)

    def living(self, entities, count=None, array=True):
        """The unit's living flight entities (addresses, 0 = a null entry); ``count``
        overrides the list length, ``array=False`` writes a null array pointer."""
        n = len(entities) if count is None else count
        self.uc.mem_write(UNIT + LIST_COUNT_OFF, struct.pack("<I", n & 0xFFFFFFFF))
        self.uc.mem_write(UNIT + LIST_OFF, struct.pack("<Q", ARRAY if array else 0))
        self.uc.mem_write(ARRAY, bytes(0x4000))
        self.uc.mem_write(ARRAY, b"".join(struct.pack("<Q", e) for e in entities))

    def fc_state(self, entity, count, phase, force=0, stay=0):
        """Write the countdown (+0x44), phase (+0x90), +0x64 byte and +8 of ``entity``'s FC.
        The four bytes before and after the countdown and the phase are filled with a
        non-zero pattern first: a cave that reads either one from a neighbouring offset
        then sees neither a 0 countdown nor a raise phase, and the raise cases fail."""
        fc = self.fc_of[entity]
        for off in (COUNT_OFF, PHASE_OFF):
            self.uc.mem_write(fc + off - 4, b"\x5a" * 12)
        self.uc.mem_write(fc + COUNT_OFF, struct.pack("<I", count & 0xFFFFFFFF))
        self.uc.mem_write(fc + PHASE_OFF, struct.pack("<I", phase & 0xFFFFFFFF))
        self.uc.mem_write(fc + 0x64, bytes([force]))
        self.uc.mem_write(fc + 0x08, struct.pack("<Q", stay))
        return fc

    def countdown(self, entity):
        return struct.unpack("<I", self.uc.mem_read(self.fc_of[entity] + COUNT_OFF, 4))[0]

    def now(self, tick, battle=True, ticks=True):
        self._battle = BATTLE if battle else 0
        self.uc.mem_write(BATTLE + TICKS_OFF, struct.pack("<Q", TICKS if ticks else 0))
        self.uc.mem_write(TICKS + TICK_OFF, struct.pack("<I", tick & 0xFFFFFFFF))
        for at in self.models:
            self.uc.mem_write(at + BATTLE_OFF, struct.pack("<Q", self._battle))

    def model(self, index, fc=True, parent=None, unit=UNIT, at=None, size="medium"):
        """A synthetic entity: with or without a flight controller (its own,
        whose first field points back at it), riding ``parent`` (a model
        index) or nothing, with the size code of body size ``size`` at +0x74
        (or a raw integer). ``at`` = an address instead of an index."""
        at = model_at(index) if at is None else at
        self.models.add(at)
        fc_at = 0
        if fc:
            fc_at = self.fc_of.get(at) or FCS + FC_STRIDE * (len(self.fc_of) + 1)
            self.fc_of[at] = fc_at
            self.uc.mem_write(fc_at, struct.pack("<Q", at))
        code = CODE_OF[size] if isinstance(size, str) else size
        self.uc.mem_write(at + FC_OFF, struct.pack("<Q", fc_at))
        self.uc.mem_write(at + SIZE_OFF, struct.pack("<i", code))
        self.uc.mem_write(at + PARENT_OFF,
                          struct.pack("<Q", model_at(parent) if parent is not None else 0))
        self.uc.mem_write(at + UNIT_OFF, struct.pack("<Q", unit))
        self.uc.mem_write(at + BATTLE_OFF, struct.pack("<Q", self._battle))
        return at

    def flyers(self, n, size="medium", big=False):
        """``n`` flying entities of one size (indices 1.. or the large region)."""
        if big:
            return [self.model(None, at=BIG + BIG_STRIDE * i, size=size) for i in range(n)]
        return [self.model(1 + i, size=size) for i in range(n)]

    def put(self, entity, tick, hits=0, slot=None):
        """Insert the way the stamp cave does (or at a forced ``slot``)."""
        if slot is None:
            slot = slot_of(entity)
            while self.raw(slot)[0] not in (0, entity):
                slot = (slot + 1) % TABLE_SLOTS
        self.uc.mem_write(BUF + TABLE_AT + ENTRY_BYTES * slot,
                          struct.pack("<QII", entity, tick & 0xFFFFFFFF, hits))
        return slot

    def raw(self, slot):
        return struct.unpack("<QII", self.uc.mem_read(BUF + TABLE_AT + ENTRY_BYTES * slot,
                                                      ENTRY_BYTES))

    def find(self, entity):
        """[(slot, tick, hits)] of every entry holding ``entity`` -- a scan of
        the whole table, independent of the hash."""
        table = bytes(self.uc.mem_read(BUF + TABLE_AT, TABLE_SLOTS * ENTRY_BYTES))
        key, out, at = struct.pack("<Q", entity), [], 0
        while True:
            at = table.find(key, at)
            if at < 0:
                return out
            if at % ENTRY_BYTES == 0:
                out.append((at // ENTRY_BYTES,) + struct.unpack_from("<II", table, at + 8))
            at += 1

    def used(self):
        table = bytes(self.uc.mem_read(BUF + TABLE_AT, TABLE_SLOTS * ENTRY_BYTES))
        return sum(1 for key, _tick, _hits in struct.iter_unpack("<QII", table) if key)

    def head(self, at):
        return struct.unpack("<I", self.uc.mem_read(BUF + at, 4))[0]

    # -- one run of a cave
    def _registers(self):
        for i, r in enumerate(self.all):
            self.uc.reg_write(r, 0x5150 + i)
        self.uc.reg_write(self.x.UC_X86_REG_RSP, STACK + 0x8000)
        self.uc.reg_write(self.x.UC_X86_REG_EFLAGS, FLAGS)

    def stamp(self, kind, damage, victim, site="pin_stamp", rearm=None):
        """One damage-applier call through the stamp cave: ``kind`` = the damage
        type, ``victim`` = an entity address or 0 (in the context rcx points at).
        ``rearm`` = (FC address, value): another thread's write, made right after the
        cave's FIRST read of that FC's countdown (the update re-arming it while the
        cave decides) -- the cave must then leave the engine's value alone."""
        from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UcError
        x, uc = self.x, self.uc
        begin, size = self.code[site]
        self._registers()
        uc.mem_write(BLOCK, struct.pack("<QQ", model_at(0x3E), victim))   # +0: an entity without FC
        uc.reg_write(x.UC_X86_REG_RCX, BLOCK)
        uc.reg_write(x.UC_X86_REG_R8, 0xA5A5A5A500000000 | (damage & 0xFFFFFFFF))
        sp = STACK + 0x8000
        uc.mem_write(sp, struct.pack("<Q", 0x14326CF64) + bytes(TYPE_ARG - 8)
                     + struct.pack("<I", kind & 0xFFFFFFFF) + b"\x77" * 12)
        before = {r: uc.reg_read(r) for r in self.all}
        hooks, state = [], {"read": False, "done": False}
        if rearm is not None:
            at, value = rearm[0] + COUNT_OFF, rearm[1]

            def on_read(_mu, _access, address, _size, _value, _data):
                if address == at and not state["done"]:
                    state["read"] = True

            def on_code(mu, _address, _size, _data):
                if state["read"] and not state["done"]:          # the instruction after that read
                    mu.mem_write(at, struct.pack("<I", value))
                    state["done"] = True
            hooks = [uc.hook_add(UC_HOOK_MEM_READ, on_read), uc.hook_add(UC_HOOK_CODE, on_code,
                                                                          begin=begin, end=begin + size)]
        try:
            uc.emu_start(begin, begin + size, count=100_000)
        except UcError:                       # a fault is a failed case, not a crashed check
            pass
        for h in hooks:
            uc.hook_del(h)
        return {"ran to the end": uc.reg_read(x.UC_X86_REG_RIP) == begin + size,
                "registers": all(uc.reg_read(r) == v for r, v in before.items()),
                "rsp": uc.reg_read(x.UC_X86_REG_RSP) == STACK + 0x8000,
                "flags": (uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFF) == FLAGS,
                "rearmed": state["done"]}

    def hold(self, living, asker, count=None, fc_model=True, unit=True, array=True, fc=None):
        """The hold cave for the flight controller of ``asker`` (an entity
        made by ``model``; ``fc`` = another FC address instead), in a unit
        whose living flight entities are ``living`` (addresses; ``count``
        overrides the list length). ``fc_model=False``: the FC's model field
        is null; ``unit=False``: the model's unit is null."""
        from unicorn import UC_HOOK_CODE, UcError
        x, uc = self.x, self.uc
        begin, size = self.code[HOLD_NAME]
        self._registers()
        fc_at = self.fc_of[asker] if fc is None else fc
        uc.mem_write(fc_at, struct.pack("<Q", asker if fc_model else 0))
        uc.mem_write(asker + UNIT_OFF, struct.pack("<Q", UNIT if unit else 0))
        self.living(living, count, array)
        uc.reg_write(x.UC_X86_REG_RBX, fc_at)
        before = {r: uc.reg_read(r) for r in self.callee_saved}
        heads = (STAMPS_AT, DROPPED_AT, HELD_AT, FREE_AT, UNMATCHED_AT, UNSIZED_AT)
        counters = tuple(self.head(h) for h in heads)
        landed = []

        def at_resume(mu, address, _size, _data):
            landed.append(address)
            mu.emu_stop()
        hook = uc.hook_add(UC_HOOK_CODE, at_resume, begin=RESUME, end=RESUME)
        crashed = False
        try:
            uc.emu_start(begin, begin + size, count=2_000_000)
        except UcError:
            crashed = True
        uc.hook_del(hook)
        rip = uc.reg_read(x.UC_X86_REG_RIP)
        after = tuple(self.head(h) for h in heads)
        where = ("crash" if crashed else "resume" if landed
                 else ("through" if rip == begin + size else hex(rip)))
        return {"where": where,
                "al": uc.reg_read(x.UC_X86_REG_RAX) & 0xFF,
                "callee-saved": all(uc.reg_read(r) == v for r, v in before.items()),
                "rsp": uc.reg_read(x.UC_X86_REG_RSP) == STACK + 0x8000,
                "counters": tuple(b - a for a, b in zip(counters, after))}


_ASSEMBLED = {}


def _assembled(name, mutate):
    if (name, mutate) not in _ASSEMBLED:
        _ASSEMBLED[(name, mutate)] = assemble(name, mutate)
    return _ASSEMBLED[(name, mutate)]


def _keys(n, base=0x1F4E0A2C0, stride=0x1240):
    """n synthetic entity pointers (never followed by the hold cave)."""
    return [base + stride * i for i in range(n)]


def check(mutate=()):
    """([failure], number of checks) of the caves built from the (optionally
    mutated) sources."""
    failures, count = [], [0]
    m = Machine(mutate)

    def expect(name, got, want):
        count[0] += 1
        if got != want:
            failures.append(f"{name}: got {got!r}, want {want!r}")

    def clean(name, r):
        for k in ("ran to the end", "registers", "rsp", "flags"):
            expect(f"{name}: {k}", r[k], True)

    # ---- stamp cave (damage-applier entry) ---------------------------------
    for site in ("pin_stamp",):
        tag = site + " "
        # which damage types record: melee (0) only -- not ranged (1..4), the
        # rest (2 / 3), impact (5), a charge's collision attack (6) -- and only damage > 0
        for kind, dmg, want in ((0, 40, True), (1, 40, False), (2, 40, False), (3, 40, False),
                                (4, 40, False), (5, 40, False), (6, 40, False), (7, 40, False),
                                (0x100, 40, False), (-1, 40, False),
                                (0, 0, False), (0, -5, False), (0, 1, True)):
            m.reset()
            m.now(1000)
            flyer = m.model(1)
            clean(f"{tag}kind={kind} dmg={dmg}", m.stamp(kind, dmg, flyer, site))
            expect(f"{tag}kind={kind} dmg={dmg} entry", m.find(flyer),
                   [(slot_of(flyer), 1000, 1)] if want else [])
            expect(f"{tag}kind={kind} dmg={dmg} stamps", m.head(STAMPS_AT), 1 if want else 0)
            expect(f"{tag}kind={kind} dmg={dmg} entries used", m.used(), 1 if want else 0)
        # who is keyed
        m.reset(); m.now(500)
        clean(tag + "null victim", m.stamp(MELEE, 40, 0, site))
        expect(tag + "null victim: nothing written", (m.used(), m.head(STAMPS_AT)), (0, 0))
        m.reset(); m.now(500)
        walker = m.model(1, fc=False)
        clean(tag + "victim without FC or parent", m.stamp(MELEE, 40, walker, site))
        expect(tag + "victim without FC or parent: nothing written",
               (m.used(), m.head(STAMPS_AT)), (0, 0))
        m.reset(); m.now(500)
        mount = m.model(2)
        rider = m.model(1, fc=False, parent=2)
        clean(tag + "rider on a flying mount", m.stamp(MELEE, 40, rider, site))
        expect(tag + "rider on a flying mount: the mount is stamped", m.find(mount),
               [(slot_of(mount), 500, 1)])
        expect(tag + "rider on a flying mount: the rider is not", m.find(rider), [])
        m.reset(); m.now(500)
        m.model(2, fc=False)
        m.model(1, fc=False, parent=2)
        clean(tag + "rider on a ground mount", m.stamp(MELEE, 40, model_at(1), site))
        expect(tag + "rider on a ground mount: nothing written", (m.used(), m.head(STAMPS_AT)), (0, 0))
        for depth, want in ((CHAIN_MAX - 1, True), (CHAIN_MAX, False)):
            m.reset(); m.now(500)
            for i in range(depth + 1):                      # model 1 rides 2 rides 3 ...
                m.model(1 + i, fc=(i == depth), parent=(2 + i) if i < depth else None)
            clean(f"{tag}flyer {depth} links up", m.stamp(MELEE, 40, model_at(1), site))
            expect(f"{tag}flyer {depth} links up: stamped", m.find(model_at(1 + depth)),
                   [(slot_of(model_at(1 + depth)), 500, 1)] if want else [])
        # null battle links
        for name, kw in (("null battle", {"battle": False}), ("null tick block", {"ticks": False})):
            m.reset()
            flyer = m.model(1)
            m.now(500, **kw)
            clean(tag + name, m.stamp(MELEE, 40, flyer, site))
            expect(tag + name + ": nothing written", (m.used(), m.head(STAMPS_AT)), (0, 0))
        # modes
        for mode, want in ((0, False), (1, True), (2, True)):
            m.reset(mode=mode); m.now(77)
            flyer = m.model(1)
            clean(f"{tag}mode {mode}", m.stamp(MELEE, 40, flyer, site))
            expect(f"{tag}mode {mode} entry", m.find(flyer),
                   [(slot_of(flyer), 77, 1)] if want else [])
        # repeat, collisions, the probe budget, wrap-around
        m.reset(); m.now(900)
        flyer = m.model(1)
        other = _keys(1)[0]
        m.put(other, 850)
        m.stamp(MELEE, 40, flyer, site)
        m.now(940)
        clean(tag + "repeat", m.stamp(MELEE, 12, flyer, site))
        expect(tag + "repeat: one entry, newest tick, two hits", m.find(flyer),
               [(slot_of(flyer), 940, 2)])
        expect(tag + "repeat: another entity's entry kept", m.find(other), [(slot_of(other), 850, 0)])
        m.reset(); m.now(900)
        flyer = m.model(1)
        home = slot_of(flyer)
        for k in range(3):
            m.put(0x7000000000 + k, 5, slot=(home + k) % TABLE_SLOTS)
        clean(tag + "collision", m.stamp(MELEE, 40, flyer, site))
        expect(tag + "collision: three entries past home", m.find(flyer),
               [((home + 3) % TABLE_SLOTS, 900, 1)])
        m.reset(); m.now(900)
        flyer = m.model(1)
        home = slot_of(flyer)
        for k in range(PROBES):
            m.put(0x7000000000 + k, 5, slot=(home + k) % TABLE_SLOTS)
        clean(tag + "no entry in reach", m.stamp(MELEE, 40, flyer, site))
        expect(tag + "no entry in reach: dropped, nothing overwritten",
               (m.find(flyer), m.head(DROPPED_AT), m.head(STAMPS_AT), m.used()),
               ([], 1, 1, PROBES))
        m.reset(); m.now(900)
        flyer = m.model(1)
        home = slot_of(flyer)
        for k in range(PROBES - 1):
            m.put(0x7000000000 + k, 5, slot=(home + k) % TABLE_SLOTS)
        clean(tag + "last entry in reach", m.stamp(MELEE, 40, flyer, site))
        expect(tag + "last entry in reach: taken", m.find(flyer),
               [((home + PROBES - 1) % TABLE_SLOTS, 900, 1)])
        # wrap-around: a flyer whose home is the table's last slot
        m.reset(); m.now(900)
        flyer = m.model(None, at=EDGE_MODEL)
        expect(tag + "wrap-around: the edge model's home is the last slot", slot_of(flyer),
               TABLE_SLOTS - 1)
        m.put(0x7000000000, 5, slot=TABLE_SLOTS - 1)
        m.put(0x7000000001, 5, slot=0)
        clean(tag + "wrap-around", m.stamp(MELEE, 40, flyer, site))
        expect(tag + "wrap-around: slot 1", m.find(flyer), [(1, 900, 1)])

        # [D11] the raise: a 0 countdown in RAISE_PHASES becomes RAISE_TO, nothing else changes
        for phase in range(0, 7):
            for cd in (0, 1, 5, 30):
                raised = cd == 0 and phase in RAISE_PHASES
                m.reset(); m.now(600)
                flyer = m.model(1)
                m.living([m.model(2), flyer])
                m.fc_state(flyer, cd, phase)
                name = f"{tag}raise phase {phase} countdown {cd}"
                clean(name, m.stamp(MELEE, 40, flyer, site))
                expect(name + ": countdown", m.countdown(flyer), RAISE_TO if raised else cd)
                expect(name + ": hit still recorded", m.find(flyer), [(slot_of(flyer), 600, 1)])
                expect(name + ": the other model's countdown", m.countdown(model_at(2)), 0)
        # ridden: the mount (the entity with the FC) is raised
        m.reset(); m.now(600)
        mount = m.model(2)
        rider = m.model(1, fc=False, parent=2)
        m.living([mount])
        m.fc_state(mount, 0, 2)
        clean(tag + "raise through a rider", m.stamp(MELEE, 40, rider, site))
        expect(tag + "raise through a rider: the mount's countdown", m.countdown(mount), RAISE_TO)
        # who is not raised: a non-melee hit, a zero hit, mode 0 / 2, no flyer, not living
        for name, kind, dmg, mode in (("ranged hit", 1, 40, 1), ("charge collision", 6, 40, 1),
                                      ("zero damage", MELEE, 0, 1), ("mode 0", MELEE, 40, 0),
                                      ("mode 2 (record only)", MELEE, 40, 2)):
            m.reset(mode=mode); m.now(600)
            flyer = m.model(1)
            m.living([flyer])
            m.fc_state(flyer, 0, 2)
            clean(f"{tag}no raise: {name}", m.stamp(kind, dmg, flyer, site))
            expect(f"{tag}no raise: {name}: countdown", m.countdown(flyer), 0)
        m.reset(); m.now(600)
        walker = m.model(1, fc=False)
        m.living([walker])
        clean(tag + "no raise: victim without FC", m.stamp(MELEE, 40, walker, site))
        expect(tag + "no raise: victim without FC: nothing written", (m.used(), m.head(STAMPS_AT)), (0, 0))
        for name, kw in (("not in the living list", {"entities": "others"}),
                         ("living list of null entries", {"entities": "nulls"}),
                         ("null unit", {"unit": False}), ("null entity array", {"array": False}),
                         ("count 0", {"count": 0}), ("count -1", {"count": -1}),
                         (f"count {MAX_MODELS + 1}", {"count": MAX_MODELS + 1})):
            m.reset(); m.now(600)
            flyer = m.model(1, unit=UNIT if kw.get("unit", True) else 0)
            other = m.model(2)
            ents = {"others": [other], "nulls": [0, 0]}.get(kw.get("entities"), [other, flyer])
            m.living(ents, kw.get("count"), kw.get("array", True))
            m.fc_state(flyer, 0, 2)
            m.fc_state(other, 0, 2)
            clean(f"{tag}no raise: {name}", m.stamp(MELEE, 40, flyer, site))
            expect(f"{tag}no raise: {name}: countdown", (m.countdown(flyer), m.countdown(other)), (0, 0))
            expect(f"{tag}no raise: {name}: hit still recorded", m.find(flyer), [(slot_of(flyer), 600, 1)])
        # another thread re-arms the countdown while the cave decides: its value is kept
        for value in (30, 7):
            m.reset(); m.now(600)
            flyer = m.model(1)
            m.living([flyer])
            fc = m.fc_state(flyer, 0, 2)
            r = m.stamp(MELEE, 40, flyer, site, rearm=(fc, value))
            clean(f"{tag}raise race (engine writes {value})", r)
            expect(f"{tag}raise race (engine writes {value}): the write happened", r["rearmed"], True)
            expect(f"{tag}raise race (engine writes {value}): kept", m.countdown(flyer), value)
        # repeated hits: raised once, a second hit at 1 leaves it at 1
        m.reset(); m.now(600)
        flyer = m.model(1)
        m.living([flyer])
        m.fc_state(flyer, 0, 1)
        m.stamp(MELEE, 40, flyer, site)
        m.stamp(MELEE, 40, flyer, site)
        expect(tag + "raise twice: countdown", m.countdown(flyer), RAISE_TO)

    # ---- hold cave ----------------------------------------------------------
    def hold_case(name, sizes, ask, struck, now, want, windows=WINDOWS, mode=1, extra=(),
                  unmatched=0, unsized=0, **kw):
        """A unit of len(``sizes``) flying entities (body sizes or raw codes), the
        one at index ``ask`` asking; ``struck`` = {index: tick}; ``extra`` =
        [(pointer, tick)] entries of other entities; ``want`` = 1 hold / 0 free /
        None pass-through. kw: list = the living list as indices (None = a null
        entry), asker_in_list, big, and the hold() / now() knobs."""
        m.reset(windows=windows, mode=mode)
        m.now(now, battle=kw.pop("battle", True), ticks=kw.pop("ticks", True))
        big = kw.pop("big", False)
        ents = [m.model(None, at=(BIG + BIG_STRIDE * i) if big else model_at(1 + i), size=s)
                for i, s in enumerate(sizes)]
        order = kw.pop("list", list(range(len(ents))))
        living = [ents[i] if i is not None else 0 for i in order]
        for i, tick in struck.items():
            m.put(ents[i], tick)
        for entity, tick in extra:
            m.put(entity, tick)
        r = m.hold(living, ents[ask], **kw)
        expect(f"hold {name}: where", r["where"], "through" if want is None else "resume")
        expect(f"hold {name}: callee-saved registers", r["callee-saved"], True)
        expect(f"hold {name}: rsp", r["rsp"], True)
        if want is None:
            expect(f"hold {name}: counters", r["counters"], (0, 0, 0, 0, 0, 0))
        else:
            expect(f"hold {name}: al", r["al"], want)
            expect(f"hold {name}: counters", r["counters"],
                   (0, 0, want, 1 - want, unmatched, unsized))

    # the four windows, at the edge, one model of each size alone
    for size in BODY_SIZES_IN_ORDER:
        w = WINDOW_OF[size]
        hold_case(f"{size} struck this tick", [size], 0, {0: 1000}, 1000, 1)
        hold_case(f"{size} struck {w - 1} ticks ago", [size], 0, {0: 1000 - (w - 1)}, 1000, 1)
        hold_case(f"{size} struck {w} ticks ago", [size], 0, {0: 1000 - w}, 1000, 0)
        hold_case(f"{size} struck {w + 1} ticks ago", [size], 0, {0: 1000 - (w + 1)}, 1000, 0)
        hold_case(f"{size} never struck", [size], 0, {}, 1000, 0)
    # the order of the four (smaller waits longer): struck 32 ticks ago
    for size, want in (("very_large", 0), ("large", 1), ("medium", 1), ("small", 1)):
        hold_case(f"{size} struck 32 ticks ago", [size], 0, {0: 968}, 1000, want)
    for size, want in (("very_large", 0), ("large", 0), ("medium", 1), ("small", 1)):
        hold_case(f"{size} struck 37 ticks ago", [size], 0, {0: 963}, 1000, want)
    for size, want in (("very_large", 0), ("large", 0), ("medium", 0), ("small", 1)):
        hold_case(f"{size} struck 42 ticks ago", [size], 0, {0: 958}, 1000, want)
    # an unknown size code: the unknown-size window (the longest), counted
    for code in (0, 5, 6, -1, 0x7FFFFFFF, -0x80000000):
        hold_case(f"size code {code} struck {UNKNOWN_WINDOW - 1} ticks ago", [code], 0,
                  {0: 1000 - (UNKNOWN_WINDOW - 1)}, 1000, 1, unsized=1)
        hold_case(f"size code {code} struck {UNKNOWN_WINDOW} ticks ago", [code], 0,
                  {0: 1000 - UNKNOWN_WINDOW}, 1000, 0, unsized=1)
        hold_case(f"size code {code} never struck", [code], 0, {}, 1000, 0, unsized=1)
    # each model on its own (D3): a unit of eight
    eight = ["medium"] * 8
    hold_case("8 models, only the asker struck", eight, 5, {5: 995}, 1000, 1)
    hold_case("8 models, all but the asker struck", eight, 5,
              {i: 995 for i in range(8) if i != 5}, 1000, 0)
    hold_case("8 models, all struck", eight, 0, {i: 995 for i in range(8)}, 1000, 1)
    hold_case("8 models, the asker struck 40 ticks ago, the rest now", eight, 3,
              {**{i: 1000 for i in range(8)}, 3: 960}, 1000, 0)
    hold_case("8 models, the asker is last in the list", eight, 7, {7: 999}, 1000, 1)
    hold_case("mixed sizes: the asker's own size decides (very large, 31 ago)",
              ["small", "very_large", "small"], 1, {0: 969, 1: 969, 2: 969}, 1000, 0)
    hold_case("mixed sizes: the asker's own size decides (small, 31 ago)",
              ["small", "very_large", "small"], 2, {0: 969, 1: 969, 2: 969}, 1000, 1)
    # another unit's entries do not hold
    others = _keys(8, base=0x2A1B3C4D0)
    hold_case("eight of another unit struck", eight, 0, {}, 1000, 0,
              extra=[(k, 995) for k in others])
    hold_case("the asker struck among another unit's entries", eight, 0, {0: 995}, 1000, 1,
              extra=[(k, 995) for k in others])
    # the asking FC no living entity carries (it died, or the list is another unit's)
    hold_case("asker not in the living list", eight, 0, {0: 995}, 1000, 0,
              list=list(range(1, 8)), unmatched=1)
    hold_case("living list only null entries", eight, 0, {0: 995}, 1000, 0,
              list=[None, None], unmatched=1)
    hold_case("null entry before the asker", eight, 2, {2: 995}, 1000, 1, list=[None, 2, 5])
    hold_case("FC of no entity at all", eight, 0, {0: 995}, 1000, 0, unmatched=1,
              fc=FCS + FCS_BYTES - FC_STRIDE)
    # broken links, odd counts
    hold_case("mode 0 passes through", eight, 0, {0: 995}, 1000, None, mode=0)
    hold_case("mode 2 passes through", eight, 0, {0: 995}, 1000, None, mode=2)
    hold_case("null model in the FC", eight, 0, {0: 995}, 1000, 0, fc_model=False)
    hold_case("null unit", eight, 0, {0: 995}, 1000, 0, unit=False)
    hold_case("null battle", eight, 0, {0: 995}, 1000, 0, battle=False)
    hold_case("null tick block", eight, 0, {0: 995}, 1000, 0, ticks=False)
    hold_case("null entity array", eight, 0, {0: 995}, 1000, 0, array=False)
    hold_case("count 0", eight, 0, {0: 995}, 1000, 0, count=0)
    hold_case("count -1", eight, 0, {0: 995}, 1000, 0, count=-1)
    hold_case(f"count {MAX_MODELS + 1}", eight, 0, {0: 995}, 1000, 0, count=MAX_MODELS + 1)
    hold_case(f"{MAX_MODELS} models, the last one asks", ["small"] * MAX_MODELS, MAX_MODELS - 1,
              {MAX_MODELS - 1: 990}, 1000, 1, big=True)
    hold_case(f"{MAX_MODELS} models, the first one asks, unstruck", ["small"] * MAX_MODELS, 0,
              {i: 990 for i in range(1, MAX_MODELS)}, 1000, 0, big=True)
    # windows come from the buffer (the Lua side writes them)
    hold_case("windows all 0: never held", ["small"], 0, {0: 1000}, 1000, 0,
              windows=(0, 0, 0, 0, 0))
    hold_case("windows 5: struck 4 ago", ["large"], 0, {0: 996}, 1000, 1, windows=(5,) * 5)
    hold_case("windows 5: struck 5 ago", ["large"], 0, {0: 995}, 1000, 0, windows=(5,) * 5)
    hold_case("only the large slot 50: large struck 49 ago", ["large"], 0, {0: 951}, 1000, 1,
              windows=(1, 1, 50, 1, 1))
    hold_case("only the large slot 50: medium struck 49 ago", ["medium"], 0, {0: 951}, 1000, 0,
              windows=(1, 1, 50, 1, 1))
    hold_case("only the unknown slot 50: code 9 struck 49 ago", [9], 0, {0: 951}, 1000, 1,
              windows=(1, 1, 1, 1, 50), unsized=1)
    # tick arithmetic
    hold_case("tick wrap", ["small"], 0, {0: 0xFFFFFFFE}, 3, 1)
    hold_case("stamp ahead of now", ["small"], 0, {0: 1001}, 1000, 0)
    hold_case("first tick of a battle, empty table", eight, 0, {}, 0, 0)
    # entries away from home
    for far, want in ((3, 1), (PROBES - 1, 1), (PROBES, 0)):
        m.reset(); m.now(1000)
        ent = m.model(1, size="small")
        home = slot_of(ent)
        for k in range(far):
            m.put(0x7000000000 + k, 5, slot=(home + k) % TABLE_SLOTS)
        m.put(ent, 995, slot=(home + far) % TABLE_SLOTS)
        r = m.hold([ent], ent)
        expect(f"hold entry {far} past home: al", (r["where"], r["al"]), ("resume", want))
    m.reset(); m.now(1000)
    edge = m.model(None, at=EDGE_MODEL, size="small")
    m.put(0x7000000000, 5, slot=TABLE_SLOTS - 1)
    m.put(edge, 995, slot=0)
    r = m.hold([edge], edge)
    expect("hold entry wrapped to slot 0: al", (r["where"], r["al"]), ("resume", 1))
    m.reset(); m.now(1000)
    ent = m.model(1, size="small")
    m.put(ent, 995, slot=slot_of(ent) + 1)                 # home empty: not searched further
    r = m.hold([ent], ent)
    expect("hold entry behind an empty home is not found: al", (r["where"], r["al"]), ("resume", 0))

    # ---- stamp -> hold, the two caves on one table -------------------------
    def unit_of(indices, riders=False, size="medium", rider_size="small"):
        """Flight entities (models with an FC); with ``riders`` each is ridden
        by model index + 0x20 (of size ``rider_size``) and the riders are the victims."""
        ents, victims = [], []
        for i in indices:
            ents.append(m.model(i, size=size))
            victims.append(m.model(i + 0x20, fc=False, parent=i, size=rider_size)
                           if riders else ents[-1])
        return ents, victims

    for riders in (False, True):
        who = "riders" if riders else "flyers"
        w = WINDOW_OF["medium"]
        m.reset(); m.now(2000)
        ents, victims = unit_of(range(1, 9), riders)
        m.stamp(MELEE, 30, victims[2])
        expect(f"round trip {who}: the struck model is held", m.hold(ents, ents[2])["al"], 1)
        expect(f"round trip {who}: its unstruck neighbour is free", m.hold(ents, ents[3])["al"], 0)
        m.stamp(6, 30, victims[3])                          # a charge's collision attack
        m.stamp(1, 30, victims[3])                          # a ranged hit
        expect(f"round trip {who}: non-melee damage does not hold", m.hold(ents, ents[3])["al"], 0)
        m.stamp(MELEE, 30, victims[3])
        expect(f"round trip {who}: a melee hit does", m.hold(ents, ents[3])["al"], 1)
        expect(f"round trip {who}: stamps", m.head(STAMPS_AT), 2)
        m.now(2000 + w - 1)
        expect(f"round trip {who}: {w - 1} ticks later (medium)", m.hold(ents, ents[2])["al"], 1)
        m.now(2000 + w)
        expect(f"round trip {who}: {w} ticks later (medium)", m.hold(ents, ents[2])["al"], 0)
        m.stamp(MELEE, 30, victims[2])
        expect(f"round trip {who}: struck again", m.hold(ents, ents[2])["al"], 1)
        expect(f"round trip {who}: it died (gone from the list)", m.hold(ents[3:], ents[2])["al"], 0)
        m.reset(mode=2); m.now(3000)
        ents, victims = unit_of(range(1, 9), riders)
        for v in victims:
            m.stamp(MELEE, 30, v)
        expect(f"round trip {who}: mode 2 records", m.head(STAMPS_AT), 8)
        expect(f"round trip {who}: mode 2 leaves the stock check", m.hold(ents, ents[0])["where"],
               "through")
    # [D11] the gap: hit at countdown 0, take-off requested -- the raise makes the next update ask,
    # and the hold cave (asked with the countdown at 1) holds it
    m.reset(); m.now(5000)
    ents, victims = unit_of(range(1, 5), riders=True)
    m.living(ents)
    m.fc_state(ents[1], 0, 2)
    m.stamp(MELEE, 30, victims[1])
    expect("gap: countdown raised", m.countdown(ents[1]), RAISE_TO)
    m.now(5001)
    expect("gap: the next question is held", m.hold(ents, ents[1])["al"], 1)
    # a ridden unit uses its mount's size, not the rider's (D3): a medium mount (40) under a
    # small rider (45), struck 42 ticks before the question
    m.reset(); m.now(4000)
    ents, victims = unit_of([1], riders=True, size="medium", rider_size="small")
    m.stamp(MELEE, 30, victims[0])
    m.now(4000 + WINDOW_OF["medium"] + 2)
    expect("ridden: judged on the mount's size", m.hold(ents, ents[0])["al"], 0)
    m.reset(); m.now(4000)
    ents, victims = unit_of([1], riders=True, size="small", rider_size="very_large")
    m.stamp(MELEE, 30, victims[0])
    m.now(4000 + WINDOW_OF["very_large"] + 2)
    expect("ridden: a small mount under a very large rider is held", m.hold(ents, ents[0])["al"], 1)
    return failures, count[0]


# Source edits that break the rule: the cases above must catch each one.
MUTANTS = (
    ("the window's last tick counts", "hold", "cmp eax, r10d\n        jae free",
     "cmp eax, r10d\n        ja free"),
    ("the size code used as the index without -1", "hold", "dec eax\n", "nop\n"),
    ("no bound on the size code", "hold", "jbe sized", "jmp sized"),
    ("an unknown size frees", "hold", "mov eax, 4\n", "jmp free\n"),
    ("an unknown size gets the very-large window", "hold", "mov eax, 4\n", "mov eax, 3\n"),
    ("unknown sizes not counted", "hold", f"lock inc dword ptr [r9 + {UNSIZED_AT}]", "nop"),
    ("the window table read one slot off", "hold", f"[r9 + rax*4 + {WINDOWS_AT}]",
     f"[r9 + rax*4 + {WINDOWS_AT + 4}]"),
    ("the size read from the wrong field", "hold", f"[rcx + {SIZE_OFF:#x}]", "[rcx + 0x70]"),
    ("the first living entity taken for the asking model", "hold",
     f"cmp qword ptr [rax + {FC_OFF:#x}], rbx\n        je found",
     f"cmp qword ptr [rax + {FC_OFF:#x}], rbx\n        jmp found"),
    ("null list entries followed", "hold", "jz own_next", "nop"),
    ("unmatched FCs not counted", "hold", f"lock inc dword ptr [r9 + {UNMATCHED_AT}]", "nop"),
    ("mode 2 answers", "hold", "jne passthrough", "je passthrough"),
    ("no probe limit on the lookup", "hold", "jnz look\n        jmp free",
     "jmp look\n        jmp free"),
    ("the lookup does not stop at an empty entry", "hold", "je free\n        inc eax",
     "nop\n        inc eax"),
    ("the two caves hash differently", "hold", "shr rdx, 17", "shr rdx, 16"),
    ("zero-damage hits recorded", "stamp", "jle done", "jl done"),
    ("non-melee damage recorded", "stamp", "jne done\n        cmp r8d, 0",
     "nop\n        cmp r8d, 0"),
    ("the damage type read from the wrong stack slot", "stamp",
     f"[rsp + {8 * STAMP_PUSHES + TYPE_ARG:#x}]", f"[rsp + {8 * STAMP_PUSHES + TYPE_ARG - 8:#x}]"),
    ("the victim read from the wrong context field", "stamp", "mov rcx, qword ptr [rcx + 8]",
     "mov rcx, qword ptr [rcx + 0]"),
    ("entities without a flight controller recorded", "stamp", "jne keyed", "jmp keyed"),
    ("riders not followed to the mount", "stamp", f"mov edx, {CHAIN_MAX}", "mov edx, 1"),
    ("mode 0 still records", "stamp", "je done\n        cmp dword ptr [rsp",
     "nop\n        cmp dword ptr [rsp"),
    # [D11] the raise
    ("raise regardless of phase", "stamp", "jmp raise_done\n    raise_live:",
     "jmp raise_live\n    raise_live:"),
    # (no early test and a plain store: the precheck alone is only a shortcut, cmpxchg is the guard)
    ("raise when the countdown is above 0", "stamp",
     (f"cmp dword ptr [r8 + {COUNT_OFF:#x}], 0\n        jne raise_done",
      f"xor eax, eax\n        mov edx, {RAISE_TO}\n        lock cmpxchg dword ptr [r8 + {COUNT_OFF:#x}], edx"),
     (f"cmp dword ptr [r8 + {COUNT_OFF:#x}], 0\n        nop",
      f"mov dword ptr [r8 + {COUNT_OFF:#x}], {RAISE_TO}")),
    ("raise writes 0", "stamp", f"mov edx, {RAISE_TO}\n", "mov edx, 0\n"),
    ("raise with a plain store (overwrites the engine's write)", "stamp",
     f"xor eax, eax\n        mov edx, {RAISE_TO}\n        lock cmpxchg dword ptr [r8 + {COUNT_OFF:#x}], edx",
     f"mov dword ptr [r8 + {COUNT_OFF:#x}], {RAISE_TO}"),
    ("raise in mode 2", "stamp", f"cmp dword ptr [r10 + {MODE_AT}], 1\n        jne raise_done",
     f"cmp dword ptr [r10 + {MODE_AT}], 0\n        je raise_done"),
    ("raise without the living-list test", "stamp", "    raise_live:\n", "    raise_live:\n        jmp raise_found\n"),
    ("raise the wrong field", "stamp", f"lock cmpxchg dword ptr [r8 + {COUNT_OFF:#x}], edx",
     f"lock cmpxchg dword ptr [r8 + {COUNT_OFF + 4:#x}], edx"),
    ("raise phase 3 too", "stamp", "jmp raise_done\n    raise_live:",
     "cmp eax, 3\n        je raise_live\n        jmp raise_done\n    raise_live:"),
)


def negative_controls():
    """[mutant name] whose broken cave passed every case (must be empty)."""
    survivors = []
    for name, kind, old, new in MUTANTS:
        # old / new: one edit, or tuples of edits applied together
        edits = tuple(zip(old, new)) if isinstance(old, tuple) else ((old, new),)
        failures, _n = check(tuple((kind, o, n) for o, n in edits))
        if not failures:
            survivors.append(name)
    return survivors


# --- site table -------------------------------------------------------------
def site_lua(codes):
    """The generated Lua data module. ``codes`` = {cave name: assembled bytes}."""
    lines = [
        "-- takeoff_site.lua -- GENERATED by tools/pipelines/pin_cave_asm.py",
        "-- (--write-site); do not edit, rerun the generator. Pure data.",
        "-- [D3, user ruling 2026-11-17] A flying model is held on the ground only",
        "-- while it was struck in melee within the last N battle ticks, N by its own",
        "-- body size (`layout.windows`: size code 1 small .. 4 very large, then an",
        "-- unknown code): two code caves (one records every melee hit at the damage",
        "-- applier, one answers each model's take-off countdown) and the anchors",
        "-- that pin the engine fields and damage types they rely on, as memreader",
        "-- Plus site-loader entries (handle:sites), plus the buffer layout",
        "-- lib/takeoff.lua writes.",
        "-- / 每个飞行兵模按自己的体型，最近 N 秒内近战挨打才被按在地上：两个代码洞与",
        "--   锚点的位点表、缓冲区布局（生成物）。",
        "return {",
        f"    owner = '{OWNER}',",
        f"    feature = '{FEATURE}',",
        "    entries = {",
    ]
    for name, (pattern, at, expect, _role) in CAVES.items():
        lines += cave_site_text.cave_entry_lines(
            name, FEATURE, pattern, at, expect, bytes_template(codes[name]))
    for name, (pattern, pins) in ANCHORS.items():
        lines += [
            f"        -- {pins}",
            f"        {{ name = '{name}', feature = '{FEATURE}', kind = 'anchor',",
            f"          pattern = '{pattern}' }},",
        ]
    lay = layout()
    lines += [
        "    },",
        "    caves = { " + ", ".join(f"'{n}'" for n in CAVES) + " },",
        f"    hold = '{HOLD_NAME}', resume_at = {HOLD_RESUME_AT},",
        "    layout = {",
        f"        bytes = {lay['bytes']}, mode_at = {lay['mode_at']},",
        f"        stamps_at = {lay['stamps_at']}, allowed_at = {lay['allowed_at']},",
        f"        magic_at = {lay['magic_at']}, magic = '{lay['magic']}',",
        f"        dropped_at = {lay['dropped_at']}, unmatched_at = {lay['unmatched_at']},",
        f"        held_at = {lay['held_at']}, free_at = {lay['free_at']}, unsized_at = {lay['unsized_at']},",
        f"        table_at = {lay['table_at']}, table_slots = {lay['table_slots']},",
        f"        entry_bytes = {lay['entry_bytes']}, size_at = {lay['size_at']},",
        f"        windows_at = {lay['windows_at']},",
        "        windows = { " + ", ".join(str(w) for w in lay['windows']) + " },",
        "        size_codes = { " + ", ".join(f"{s} = {c}" for s, c in
                                            sorted(lay['size_codes'].items(), key=lambda i: i[1])) + " },",
        "    },",
        f"    format = {agreement_format()},",
        f"    build = '{BUILD}',",
        f"    source_sha = '{source_sha()}',",
        "}",
    ]
    return "\n".join(lines) + "\n"


def check_site_file(mod_dir):
    """Offline (no keystone): the committed site table was generated from the
    current cave sources, sites, anchors and layout. Raises otherwise."""
    path = Path(mod_dir) / SITE_LUA
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for needle in (f"source_sha = '{source_sha()}'", f"format = {agreement_format()},"):
        if needle not in text:
            raise RuntimeError(f"[pin_cave_asm] REFUSING: {path} is missing or stale (lacks "
                               f"{needle!r}); rerun pin_cave_asm.py --write-site")
    return True


def _regex(pattern):
    return re.compile(b"".join(b"." if t == "??" else re.escape(bytes([int(t, 16)]))
                               for t in pattern.split()), re.S)


def check_exe(exe_path):
    """Offline: every cave site and every anchor matches exactly once in the
    installed exe's code, with the expected original bytes at the site.
    Returns {name: virtual address}; raises otherwise."""
    import pefile
    pe = pefile.PE(str(exe_path), fast_load=True)
    sections = [(pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress, s.get_data())
                for s in pe.sections if s.Characteristics & 0x20000000]      # executable
    found = {}
    wanted = [(n, p, at, bytes.fromhex(e.replace(" ", ""))) for n, (p, at, e, _v) in CAVES.items()]
    wanted += [(n, p, 0, b"") for n, (p, _pins) in ANCHORS.items()]
    for name, pattern, at, expect in wanted:
        rx = _regex(pattern)
        hits = [base + m.start() + at for base, data in sections for m in rx.finditer(data)
                if data[m.start() + at:m.start() + at + len(expect)] == expect]
        if len(hits) != 1:
            raise RuntimeError(f"[pin_cave_asm] REFUSING: {name} found {len(hits)} times in "
                               f"{exe_path} (a game patch moved it)")
        found[name] = hits[0]
    return found


def main(argv):
    codes = {name: assemble(name) for name in CAVES}
    failures, n = check()
    print("caves: " + ", ".join(f"{name} {len(code)} bytes" for name, code in codes.items())
          + f"; buffer {BUFFER_BYTES} bytes, {TABLE_SLOTS} entries, windows by size code 1..4 "
          f"{list(WINDOWS[:4])} ticks, unknown size {WINDOWS[4]}")
    for f in failures:
        print("FAIL", f)
    print(f"emulator: {n} checks,", "PASS" if not failures else f"{len(failures)} FAIL")
    survivors = [] if failures else negative_controls()
    for name in survivors:
        print("FAIL negative control passed every case:", name)
    if not failures:
        print(f"negative controls: {len(MUTANTS)} broken caves,",
              "each caught" if not survivors else f"{len(survivors)} NOT caught")
    bad = bool(failures or survivors)
    mod_dir = HERE.parents[1]
    if "--write-site" in argv:
        if bad:
            raise SystemExit("not writing the site table: the emulator check failed")
        (mod_dir / SITE_LUA).write_text(site_lua(codes), encoding="utf-8", newline="\n")
        print("wrote", mod_dir / SITE_LUA)
    elif not bad:
        have = (mod_dir / SITE_LUA).read_text(encoding="utf-8").replace("\r\n", "\n")
        print("site table:", "current" if have == site_lua(codes)
              else "STALE (rerun with --write-site)")
        bad = have != site_lua(codes)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
