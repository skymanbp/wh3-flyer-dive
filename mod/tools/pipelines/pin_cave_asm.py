"""Machine code of the pin-on-hit take-off caves, their emulator check and the
generated site table.

[AIR-DIVE-TAKEOFF-W1 2026-11-12, user rulings 2026-11-12, CONTENT_LEDGER
§C8-58] RULE: a flying unit is held on the ground (its models' take-off
countdown re-armed) only while MORE THAN HALF of its living models were struck
in melee within the last ``air_dive_rules.TAKEOFF_PIN_WINDOW_TICKS`` battle
ticks (15 = 1.5 s). A single-model unit (one living model): its one model,
struck within the last ``TAKEOFF_PIN_WINDOW_SINGLE_TICKS`` (30 = 3.0 s; user
ruling 2026-11-16, CONTENT_LEDGER §C8-78). Contact without hits,
ranged and explosion hits, and a charge's collision damage do not hold it.
Replaces the first take-off patch (the countdown always ran, so a flyer left
3.0 s after the order whatever was hitting it).

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
= unit; unit +0x184 (count) / +0x188 (array of pointers) = its living flight
entities (the engine's own loop over them: 0x14305018b; the list shrinks when
a model dies). Mode 1: the cave counts the living entities whose table entry
is younger than the window, answers al = 1 (hold) when struck x 2 > living,
else al = 0 -- when exactly one entity is living, its entry is judged against
the single-model window (+40) instead [§C8-78], and jumps to the instruction after the call (``test al,al``),
skipping the engaged check. Any other mode: the cave does nothing and the
original check runs. The entity pointers are only compared, never followed.
Registers a call may clobber change (rax rcx rdx r8-r11, flags); rbx rsi rdi
rbp r12-r15 rsp come back unchanged (rsi rdi r12 r13 are saved around the loop).

Buffer (game_alloc, little endian), 64-byte header then the table:
  +0  u32 window in ticks        +4  u32 mode: 0 off, 1 the rule, 2 record
  +8  u32 stamps (hits recorded)     only (stamps kept, stock hold; tests)
  +12 u32 allowed (Lua only: the campaign's agreement said yes)
  +16 8 bytes MAGIC              +24 u32 dropped (no free entry in reach)
  +32 u32 "hold" answers         +36 u32 "free" answers (mode 1)
  +40 u32 single-model window in ticks (§C8-78)
  +64 TABLE_SLOTS x 16 bytes: u64 flying entity, u32 tick, u32 hits
Entry of pointer p: slot ((p>>4) ^ (p>>17) ^ (p>>30)) & (TABLE_SLOTS-1), then
linear probing, at most PROBES entries. Entries are never freed inside a
battle; the Lua side clears the table when a battle loads. A hit that finds
no entry in reach is dropped (counted), so a full table errs towards "free".

The site table also carries ANCHORS: pieces of the engine's own code that use
the same fields (the flight-entity list, the unit back-reference, the battle
tick, the parent link) and the callers that pass a non-melee damage type
(charge 6, impact 5, ranged 1..4); the stamp site's own pattern pins the
applier's victim, damage and damage-type reads. The site loader needs every
one exactly once, so a game update that moves a field turns the feature off
instead of letting the caves read the wrong memory.

``python pin_cave_asm.py`` (needs keystone + unicorn) assembles the caves,
runs them in Unicorn against synthetic objects (see ``check``), then runs the
same cases against mutated sources that must each fail (``MUTANTS``).
``--write-site`` writes the site table when everything passed. Importing the
module needs neither package: ``check_site_file`` / ``check_exe`` are what
build_pack.py and build_air_dive_minimod.py call.
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
WINDOW_TICKS = air_dive_rules.TAKEOFF_PIN_WINDOW_TICKS

# --- buffer layout ----------------------------------------------------------
WINDOW_AT, MODE_AT, STAMPS_AT, ALLOWED_AT, MAGIC_AT = 0, 4, 8, 12, 16
DROPPED_AT, HELD_AT, FREE_AT, WINDOW_SINGLE_AT = 24, 32, 36, 40
WINDOW_SINGLE_TICKS = air_dive_rules.TAKEOFF_PIN_WINDOW_SINGLE_TICKS
TABLE_AT, ENTRY_BYTES = 64, 16
TABLE_SLOTS = 8192                  # power of two
PROBES = 64
BUFFER_BYTES = TABLE_AT + TABLE_SLOTS * ENTRY_BYTES
MAGIC = b"LDFLYPN2"                  # 2: +40 single-model window (§C8-78)
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
        push rsi
        push rdi
        push r12
        push r13
        xor r10d, r10d
        xor r12d, r12d
        xor r13d, r13d
    each:
        mov rsi, [rdx]
        test rsi, rsi
        jz skip
        dec r10d
        inc r12d
        {_hash("rsi", "rax", "rdi")}
        mov r11d, {PROBES}
    look:
        mov edi, eax
        shl rdi, 4
        lea rdi, [r9 + rdi + {TABLE_AT}]
        cmp [rdi], rsi
        je hit
        cmp qword ptr [rdi], 0
        je skip
        inc eax
        and eax, {TABLE_SLOTS - 1}
        dec r11d
        jnz look
        jmp skip
    hit:
        mov eax, r8d
        sub eax, dword ptr [rdi + 8]
        cmp eax, dword ptr [r9 + {WINDOW_SINGLE_AT}]
        jae short_window
        inc r13d
    short_window:
        cmp eax, dword ptr [r9 + {WINDOW_AT}]
        jae skip
        add r10d, 2
    skip:
        add rdx, 8
        dec ecx
        jnz each
        cmp r12d, 1
        jne several
        mov r10d, r13d
    several:
        pop r13
        pop r12
        pop rdi
        pop rsi
        test r10d, r10d
        jle free
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
    return {"bytes": BUFFER_BYTES, "window_at": WINDOW_AT, "mode_at": MODE_AT,
            "stamps_at": STAMPS_AT, "allowed_at": ALLOWED_AT, "magic_at": MAGIC_AT,
            "magic": MAGIC.decode(), "dropped_at": DROPPED_AT, "held_at": HELD_AT,
            "free_at": FREE_AT, "table_at": TABLE_AT, "table_slots": TABLE_SLOTS,
            "entry_bytes": ENTRY_BYTES, "window": WINDOW_TICKS,
            "window_single_at": WINDOW_SINGLE_AT, "window_single": WINDOW_SINGLE_TICKS}


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
BATTLE, TICKS, FCB, ARRAY = WORLD, WORLD + 0x10000, BLOCK + 0x8000, UNIT + 0x10000
FLAGS = 0x0247


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
        uc.mem_write(RESUME, b"\xf4")
        self.code = {}
        for i, name in enumerate(CAVES):
            code = filled(_assembled(name, tuple(mutate)), BUF, RESUME)
            self.code[name] = (CODE + 0x1000 * i, len(code))
            uc.mem_write(CODE + 0x1000 * i, code)
        self.reset()

    # -- the battle's memory
    def reset(self, window=WINDOW_TICKS, mode=1, single=WINDOW_SINGLE_TICKS):
        self.uc.mem_write(BUF, bytes(BUFFER_BYTES))
        self.uc.mem_write(BUF, struct.pack("<II", window, mode))
        self.uc.mem_write(BUF + WINDOW_SINGLE_AT, struct.pack("<I", single))
        self.uc.mem_write(BUF + MAGIC_AT, MAGIC)
        self.uc.mem_write(OBJ, bytes(0x40000))
        self.models = set()
        self.now(0)

    def now(self, tick, battle=True, ticks=True):
        self._battle = BATTLE if battle else 0
        self.uc.mem_write(BATTLE + TICKS_OFF, struct.pack("<Q", TICKS if ticks else 0))
        self.uc.mem_write(TICKS + TICK_OFF, struct.pack("<I", tick & 0xFFFFFFFF))
        for at in self.models:
            self.uc.mem_write(at + BATTLE_OFF, struct.pack("<Q", self._battle))

    def model(self, index, fc=True, parent=None, unit=UNIT, at=None):
        """A synthetic entity: with or without a flight controller, riding
        ``parent`` (a model index) or nothing. ``at`` = an address instead of
        an index."""
        at = model_at(index) if at is None else at
        self.models.add(at)
        self.uc.mem_write(at + FC_OFF, struct.pack("<Q", FCB + 0x100 if fc else 0))
        self.uc.mem_write(at + PARENT_OFF,
                          struct.pack("<Q", model_at(parent) if parent is not None else 0))
        self.uc.mem_write(at + UNIT_OFF, struct.pack("<Q", unit))
        self.uc.mem_write(at + BATTLE_OFF, struct.pack("<Q", self._battle))
        return at

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

    def stamp(self, kind, damage, victim, site="pin_stamp"):
        """One damage-applier call through the stamp cave: ``kind`` = the damage
        type, ``victim`` = an entity address or 0 (in the context rcx points at)."""
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
        uc.emu_start(begin, begin + size, count=100_000)
        return {"ran to the end": uc.reg_read(x.UC_X86_REG_RIP) == begin + size,
                "registers": all(uc.reg_read(r) == v for r, v in before.items()),
                "rsp": uc.reg_read(x.UC_X86_REG_RSP) == STACK + 0x8000,
                "flags": (uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFF) == FLAGS}

    def hold(self, living, count=None, fc_model=True, unit=True, array=True):
        """The hold cave for one model of a unit whose living flight entities
        are ``living`` (addresses; ``count`` overrides the list length)."""
        from unicorn import UC_HOOK_CODE
        x, uc = self.x, self.uc
        begin, size = self.code[HOLD_NAME]
        self._registers()
        asker = self.model(0x3F)
        uc.mem_write(FCB, struct.pack("<Q", asker if fc_model else 0))
        uc.mem_write(asker + UNIT_OFF, struct.pack("<Q", UNIT if unit else 0))
        n = len(living) if count is None else count
        uc.mem_write(UNIT + LIST_COUNT_OFF, struct.pack("<I", n & 0xFFFFFFFF))
        uc.mem_write(UNIT + LIST_OFF, struct.pack("<Q", ARRAY if array else 0))
        uc.mem_write(ARRAY, bytes(0x4000))
        uc.mem_write(ARRAY, b"".join(struct.pack("<Q", e) for e in living))
        uc.reg_write(x.UC_X86_REG_RBX, FCB)
        before = {r: uc.reg_read(r) for r in self.callee_saved}
        counters = (self.head(STAMPS_AT), self.head(DROPPED_AT), self.head(HELD_AT),
                    self.head(FREE_AT))
        landed = []

        def at_resume(mu, address, _size, _data):
            landed.append(address)
            mu.emu_stop()
        hook = uc.hook_add(UC_HOOK_CODE, at_resume, begin=RESUME, end=RESUME)
        uc.emu_start(begin, begin + size, count=2_000_000)
        uc.hook_del(hook)
        rip = uc.reg_read(x.UC_X86_REG_RIP)
        after = (self.head(STAMPS_AT), self.head(DROPPED_AT), self.head(HELD_AT),
                 self.head(FREE_AT))
        return {"where": "resume" if landed else ("through" if rip == begin + size else hex(rip)),
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

    # ---- hold cave ----------------------------------------------------------
    def hold_case(name, living, struck, now, want, window=WINDOW_TICKS, mode=1, extra=(),
                  single=WINDOW_SINGLE_TICKS, **kw):
        """``struck`` = {entity: tick}; ``want`` = 1 hold / 0 free / None pass-through."""
        m.reset(window=window, mode=mode, single=single)
        m.now(now, battle=kw.pop("battle", True), ticks=kw.pop("ticks", True))
        for entity, tick in list(struck.items()) + list(extra):
            m.put(entity, tick)
        r = m.hold(living, **kw)
        expect(f"hold {name}: where", r["where"], "through" if want is None else "resume")
        expect(f"hold {name}: callee-saved registers", r["callee-saved"], True)
        expect(f"hold {name}: rsp", r["rsp"], True)
        if want is None:
            expect(f"hold {name}: counters", r["counters"], (0, 0, 0, 0))
        else:
            expect(f"hold {name}: al", r["al"], want)
            expect(f"hold {name}: counters", r["counters"], (0, 0, want, 1 - want))

    e8 = _keys(8)
    fresh = lambda keys, tick=995: {k: tick for k in keys}
    hold_case("mode 0 passes through", e8, fresh(e8), 1000, None, mode=0)
    hold_case("mode 2 passes through", e8, fresh(e8), 1000, None, mode=2)
    hold_case("0 of 8 struck", e8, {}, 1000, 0)
    hold_case("1 of 8 struck", e8, fresh(e8[:1]), 1000, 0)
    hold_case("3 of 8 struck", e8, fresh(e8[:3]), 1000, 0)
    hold_case("4 of 8 struck (exactly half)", e8, fresh(e8[:4]), 1000, 0)
    hold_case("5 of 8 struck", e8, fresh(e8[:5]), 1000, 1)
    hold_case("5 of 8 struck, the last five", e8, fresh(e8[3:]), 1000, 1)
    hold_case("8 of 8 struck", e8, fresh(e8), 1000, 1)
    hold_case("5 of 8 struck 20 ticks ago (stale)", e8, fresh(e8[:5], 980), 1000, 0)
    hold_case("8 of 8 struck long ago", e8, fresh(e8, 12), 100000, 0)
    hold_case("4 fresh + 4 stale of 8", e8, {**fresh(e8[:4]), **fresh(e8[4:], 900)}, 1000, 0)
    hold_case("5 fresh + 3 stale of 8", e8, {**fresh(e8[:5]), **fresh(e8[5:], 900)}, 1000, 1)
    hold_case("5 of 8 struck 14 ticks ago", e8, fresh(e8[:5], 986), 1000, 1)
    hold_case("5 of 8 struck 15 ticks ago", e8, fresh(e8[:5], 985), 1000, 0)
    hold_case("5 of 8, four at 14 ticks and one at 15", e8,
              {**fresh(e8[:4], 986), e8[4]: 985}, 1000, 0)
    hold_case("window 5: struck 4 ticks ago", e8, fresh(e8[:5], 996), 1000, 1, window=5)
    hold_case("window 5: struck 5 ticks ago", e8, fresh(e8[:5], 995), 1000, 0, window=5)
    hold_case("window 0: never held", e8, fresh(e8, 1000), 1000, 0, window=0)
    hold_case("struck this very tick", e8, fresh(e8[:5], 1000), 1000, 1)
    # single-model unit
    hold_case("single model, struck", e8[:1], fresh(e8[:1]), 1000, 1)
    # [§C8-78] one living model: 3.0 s (30 ticks); 2.9 s held, 3.0 and 3.1 s free
    hold_case("single model, struck 15 ticks ago", e8[:1], fresh(e8[:1], 985), 1000, 1)
    hold_case("single model, struck 29 ticks ago (2.9 s)", e8[:1], fresh(e8[:1], 971), 1000, 1)
    hold_case("single model, struck 30 ticks ago (3.0 s)", e8[:1], fresh(e8[:1], 970), 1000, 0)
    hold_case("single model, struck 31 ticks ago (3.1 s)", e8[:1], fresh(e8[:1], 969), 1000, 0)
    hold_case("single model, single window 10: struck 9 ago", e8[:1], fresh(e8[:1], 991), 1000, 1,
              single=10)
    hold_case("single model, single window 10: struck 10 ago", e8[:1], fresh(e8[:1], 990), 1000, 0,
              single=10)
    hold_case("single model held by the single window, not the multi one", e8[:1],
              fresh(e8[:1], 980), 1000, 1, window=0)
    hold_case("one living model left of eight (dead gone from the list): 3.0 s", e8[4:5],
              fresh(e8[:5], 980), 1000, 1)
    hold_case("one living model and a null entry: 3.0 s", [e8[0], 0], fresh(e8[:1], 980), 1000, 1)
    hold_case("two living, both struck 20 ticks ago: multi window", e8[:2], fresh(e8[:2], 980),
              1000, 0)
    hold_case("eight living, all struck 20 ticks ago: multi window", e8, fresh(e8, 980), 1000, 0)
    hold_case("eight living, five struck 14 ticks ago, single window 0", e8, fresh(e8[:5], 986),
              1000, 1, single=0)
    hold_case("single model, never struck", e8[:1], {}, 1000, 0)
    hold_case("single model, only others struck", e8[:1], fresh(e8[1:]), 1000, 0)
    # two and three models
    hold_case("1 of 2 struck", e8[:2], fresh(e8[:1]), 1000, 0)
    hold_case("2 of 2 struck", e8[:2], fresh(e8[:2]), 1000, 1)
    hold_case("2 of 3 struck", e8[:3], fresh(e8[:2]), 1000, 1)
    # dead models: gone from the living list, their entries stay in the table
    hold_case("5 struck, four of them dead: 1 of 4 living", e8[4:], fresh(e8[:5]), 1000, 0)
    hold_case("3 of 8 struck, three unstruck dead: 3 of 5 living", e8[:5], fresh(e8[:3]), 1000, 1)
    hold_case("all struck models dead", e8[5:], fresh(e8[:5]), 1000, 0)
    # another unit's models
    others = _keys(8, base=0x2A1B3C4D0)
    hold_case("eight of another unit struck", e8, fresh(others), 1000, 0)
    hold_case("5 of 8 struck among another unit's entries", e8, fresh(e8[:5]), 1000, 1,
              extra=list(fresh(others).items()))
    # broken links, odd counts
    hold_case("null FC model", e8, fresh(e8), 1000, 0, fc_model=False)
    hold_case("null unit", e8, fresh(e8), 1000, 0, unit=False)
    hold_case("null battle", e8, fresh(e8), 1000, 0, battle=False)
    hold_case("null tick block", e8, fresh(e8), 1000, 0, ticks=False)
    hold_case("null entity array", e8, fresh(e8), 1000, 0, array=False)
    hold_case("count 0", e8, fresh(e8), 1000, 0, count=0)
    hold_case("count -1", e8, fresh(e8), 1000, 0, count=-1)
    hold_case(f"count {MAX_MODELS + 1}", e8, fresh(e8), 1000, 0, count=MAX_MODELS + 1)
    big = _keys(MAX_MODELS, base=0x3000000000, stride=0x9C0)
    hold_case(f"{MAX_MODELS // 2} of {MAX_MODELS} struck", big, fresh(big[:MAX_MODELS // 2]),
              1000, 0)
    hold_case(f"{MAX_MODELS // 2 + 1} of {MAX_MODELS} struck", big,
              fresh(big[:MAX_MODELS // 2 + 1]), 1000, 1)
    hold_case("null entry in the list: 1 of 2 living struck", [e8[0], 0, e8[2]],
              fresh(e8[:1]), 1000, 0)
    hold_case("null entry in the list: 1 of 1 living struck", [e8[0], 0], fresh(e8[:1]), 1000, 1)
    hold_case("only null entries", [0, 0, 0], {}, 1000, 0)
    # tick arithmetic
    hold_case("tick wrap", e8[:1], {e8[0]: 0xFFFFFFFE}, 3, 1)
    hold_case("stamp ahead of now", e8[:1], {e8[0]: 1001}, 1000, 0)
    hold_case("first tick of a battle, empty table", e8, {}, 0, 0)
    # entries away from home
    for far, want in ((3, 1), (PROBES - 1, 1), (PROBES, 0)):
        m.reset(); m.now(1000)
        home = slot_of(e8[0])
        for k in range(far):
            m.put(0x7000000000 + k, 5, slot=(home + k) % TABLE_SLOTS)
        m.put(e8[0], 995, slot=(home + far) % TABLE_SLOTS)
        r = m.hold(e8[:1])
        expect(f"hold entry {far} past home: al", (r["where"], r["al"]), ("resume", want))
    m.reset(); m.now(1000)
    m.put(0x7000000000, 5, slot=TABLE_SLOTS - 1)
    m.put(EDGE_MODEL, 995, slot=0)
    r = m.hold([EDGE_MODEL])
    expect("hold entry wrapped to slot 0: al", (r["where"], r["al"]), ("resume", 1))
    m.reset(); m.now(1000)
    m.put(e8[0], 995, slot=slot_of(e8[0]) + 1)             # home empty: not searched further
    r = m.hold(e8[:1])
    expect("hold entry behind an empty home is not found: al", (r["where"], r["al"]), ("resume", 0))

    # ---- stamp -> hold, the two caves on one table -------------------------
    def unit_of(indices, riders=False):
        """Flight entities (models with an FC); with ``riders`` each is ridden
        by model index + 0x20 and the riders are the victims."""
        ents, victims = [], []
        for i in indices:
            ents.append(m.model(i))
            victims.append(m.model(i + 0x20, fc=False, parent=i) if riders else ents[-1])
        return ents, victims

    for riders in (False, True):
        who = "riders" if riders else "flyers"
        m.reset(); m.now(2000)
        ents, victims = unit_of(range(1, 9), riders)
        for v in victims[:4]:
            m.stamp(MELEE, 30, v)
        expect(f"round trip {who}: 4 of 8 struck", m.hold(ents)["al"], 0)
        m.stamp(6, 30, victims[4])                          # a charge's collision attack
        m.stamp(1, 30, victims[4])                          # a ranged hit
        expect(f"round trip {who}: non-melee damage on the fifth does not hold", m.hold(ents)["al"], 0)
        m.stamp(MELEE, 30, victims[4])
        expect(f"round trip {who}: 5 of 8 struck", m.hold(ents)["al"], 1)
        expect(f"round trip {who}: stamps", m.head(STAMPS_AT), 5)
        m.now(2014)
        expect(f"round trip {who}: 14 ticks later", m.hold(ents)["al"], 1)
        m.now(2015)
        expect(f"round trip {who}: 15 ticks later", m.hold(ents)["al"], 0)
        m.stamp(MELEE, 30, victims[0])
        m.stamp(MELEE, 30, victims[0])                      # one model struck twice
        expect(f"round trip {who}: one model struck twice is one model", m.hold(ents)["al"], 0)
        m.now(2100)
        for v in victims[:5]:
            m.stamp(MELEE, 30, v)
        expect(f"round trip {who}: 5 of 8 again", m.hold(ents)["al"], 1)
        expect(f"round trip {who}: three struck die, 2 of 5 living", m.hold(ents[3:])["al"], 0)
        expect(f"round trip {who}: three unstruck die, 5 of 5 living", m.hold(ents[:5])["al"], 1)
        m.reset(); m.now(3000)
        ents, victims = unit_of([1], riders)
        expect(f"round trip {who}: single model, not struck", m.hold(ents)["al"], 0)
        m.stamp(MELEE, 30, victims[0])
        expect(f"round trip {who}: single model, struck", m.hold(ents)["al"], 1)
        m.now(3015)
        expect(f"round trip {who}: single model, 15 ticks later", m.hold(ents)["al"], 1)
        m.now(3029)
        expect(f"round trip {who}: single model, 29 ticks later", m.hold(ents)["al"], 1)
        m.now(3031)
        expect(f"round trip {who}: single model, 31 ticks later", m.hold(ents)["al"], 0)
        m.reset(mode=2); m.now(3000)
        ents, victims = unit_of(range(1, 9), riders)
        for v in victims:
            m.stamp(MELEE, 30, v)
        expect(f"round trip {who}: mode 2 records", m.head(STAMPS_AT), 8)
        expect(f"round trip {who}: mode 2 leaves the stock check", m.hold(ents)["where"], "through")
    return failures, count[0]


# Source edits that break the rule: the cases above must catch each one.
MUTANTS = (
    ("exactly half holds", "hold", "jle free", "jl free"),
    ("the window's last tick counts", "hold", "jae skip", "ja skip"),
    ("living models not counted", "hold", "dec r10d", "nop"),
    ("a struck model counts once, not twice", "hold", "add r10d, 2", "add r10d, 1"),
    ("mode 2 answers", "hold", "jne passthrough", "je passthrough"),
    ("no probe limit on the lookup", "hold", "jnz look\n        jmp skip",
     "jmp look\n        jmp skip"),
    ("the two caves hash differently", "hold", "shr rdi, 17", "shr rdi, 16"),
    ("one living model judged on the multi-model window", "hold", "jne several", "jmp several"),
    ("several living models judged on the single-model window", "hold", "jne several",
     "je several"),
    ("the single-model window's last tick counts", "hold", "jae short_window", "ja short_window"),
    ("the single-model window read from the multi-model slot", "hold",
     f"[r9 + {WINDOW_SINGLE_AT}]", f"[r9 + {WINDOW_AT}]"),
    ("living models not counted for the single-model test", "hold", "inc r12d\n", "nop\n"),
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
)


def negative_controls():
    """[mutant name] whose broken cave passed every case (must be empty)."""
    survivors = []
    for name, kind, old, new in MUTANTS:
        failures, _n = check(((kind, old, new),))
        if not failures:
            survivors.append(name)
    return survivors


# --- site table -------------------------------------------------------------
def site_lua(codes):
    """The generated Lua data module. ``codes`` = {cave name: assembled bytes}."""
    lines = [
        "-- ld_flyer_takeoff_site.lua -- GENERATED by tools/pipelines/pin_cave_asm.py",
        "-- (--write-site); do not edit, rerun the generator. Pure data.",
        "-- [AIR-DIVE-TAKEOFF-W1 2026-11-12] Flyers are held on the ground only while",
        "-- more than half of their living models were struck in melee in the last",
        "-- `layout.window` battle ticks (one living model: `layout.window_single`,",
        "-- §C8-78): two code caves (one records every melee",
        "-- hit at the damage applier, one answers the take-off countdown) and the",
        "-- anchors that pin the engine fields and damage types they rely on, as",
        "-- memreader Plus site-loader entries (handle:sites), plus the buffer",
        "-- layout lib/ld_flyer_takeoff.lua writes.",
        "-- / 飞兽只在过半存活模型近 1.5 秒内近战挨打时才被按在地上：两个代码洞与",
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
        f"        bytes = {lay['bytes']}, window_at = {lay['window_at']}, mode_at = {lay['mode_at']},",
        f"        stamps_at = {lay['stamps_at']}, allowed_at = {lay['allowed_at']},",
        f"        magic_at = {lay['magic_at']}, magic = '{lay['magic']}',",
        f"        dropped_at = {lay['dropped_at']}, held_at = {lay['held_at']}, free_at = {lay['free_at']},",
        f"        table_at = {lay['table_at']}, table_slots = {lay['table_slots']},",
        f"        entry_bytes = {lay['entry_bytes']}, window = {lay['window']},",
        f"        window_single_at = {lay['window_single_at']}, window_single = {lay['window_single']},",
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
          + f"; buffer {BUFFER_BYTES} bytes, {TABLE_SLOTS} entries, window {WINDOW_TICKS} ticks"
          f" (single model {WINDOW_SINGLE_TICKS})")
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
