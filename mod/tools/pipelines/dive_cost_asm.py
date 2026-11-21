"""The shipped physics-dive site table with D15 (docs/DECISIONS.md D15; d15-1118 stage 5): the eleven dive caves of
dive_cave_asm.py with the dive mark of dive_mark_asm.py, plus ``dv_cost``, the cave that judges a dive's contact
with a bracing charge-reflection soldier, and the anchor ``dv_facing`` it reads the game's facing table through.
This file writes ``script/campaign/flyer_dive/data/dive_site.lua`` (dive_cave_asm.py no longer does: its table
would drop D15). The battle script that takes the share is ``script/campaign/flyer_dive/lib/dive_cost.lua``.

What the cave reads is what the game itself uses, read from Warhammer3.exe 9.0.5 (6ae2a00b):
* the contact: the damage applier 0x14325a9c4 on a type-5 (impact, 0x143061144) or type-6 (charge collision
  attack, 0x143060e44) call whose attacker ([r12], the applier's attacker struct) is, or rides, a flying entity:
  the attacker was that flying entity in 165 / 165 and 212 / 212 such calls of the two series-4 cost runs;
* the dive: the mark of dive_mark_asm.py (armed by an air charge out of melee, stamped at the first ground hold
  of the landed dive), at most DIVE_COST_WINDOW_TICKS after the stamp; one cost per mark;
* bracing: the soldier's +0x68 bit 3, the flag the damage calculator's source->vfunc[0x50] (0x1408fc020)
  answers and the bracing update sets at 0x143090af0 (8 of 9 stamped contacts in the spear run had it);
* charge reflection: the soldier's unit attribute 0x27, the calculator's source->vfunc[0x38] (0x1430b7a44 ->
  0x1414755e0(unit + 0x36c8, 0x27)), inlined here from 0x1414755e0's own bit tests (no call is made). In game the
  calculator's gate passed 189 times against spearmen_1 (which carry charge_reflection) and 0 times against
  swordsmen (which do not; series4 d15_brace_spear / _sword);
* the front arc (air_dive_rules.DIVE_COST_FRONT_ARC): the flying entity's position (+0x88 / +0x90) within the
  game's bracing_attack_angle of the soldier's facing, as the game tests it in 0x14307c404: facing = the u16 at
  +0xb0 (vfunc +0xc8, 0x1408f84f0, of all 33 entity vtables) indexing the (x, z) table the code at 0x14307c5c6
  reads (filled at run time; the anchor's read gives its address); in front when cos >= cos(angle).
A paying contact turns the mark STAMPED -> SPENT (lock cmpxchg, one winner) and writes a ring entry for Lua. A
braced contact that fails the attribute or the arc writes an entry of its own kind and leaves the mark stamped
(a later contact of the same dive may pay). A contact past the window turns the mark EXPIRED.

[D31, brace-solver-1120] Plus ``dv_brace`` (pipelines/dive_brace_asm.py) in the pair solver's velocity block
0x1431781e9, its setting word and counter after the cost ring (BRACE_AT); MAGIC FLYDIVE5.

``dv_cost`` sits at 0x14325aa9e (``mov r14,[r12]; test r14,r14; je 0x14325ab6a; cmp byte [rcx+0x3ea9],0;
je 0x14325ab6a``, 26 bytes; nothing branches into them, site_check5 in the lane's scratch). It is reached by
types 0 / 5 / 6 with a victim unit (0x14325aa61..0x14325aa98) and is clear of the take-off cave pin_stamp
(entry, 10 bytes) and of the probe's rf_dmg (0x14325aa18, which runs first and only reads the mark). There
rsi = rdx = the victim, rcx = its unit, r12 the attacker struct, r15d the damage type. The cave keeps every
register but r14 (set by the replaced code) and the flags, and returns through push / ret (no register).

Buffer: dive_mark_asm's (the shipped layout, then the mark), then
  COST_AT +0 u32 entries written   +4 u32 front arc on (Lua writes it)   +8 F32 cos(bracing_attack_angle)
  COST_RING_AT  COST_SLOTS x 48 bytes: u64 flying entity, u64 attacker's unit, u64 victim's unit, u32 tick,
                u32 flying entity size code (+0x74), F32 cos of the angle (2.0: no direction), u32 kind
                (1 pay, 2 behind the arc, 3 no charge reflection), u32 victim +0x68, u32 seq + 1 (written last)

``python dive_cost_asm.py [--write-site]`` (keystone + unicorn): every emulator case of the eleven caves with the
mark, the mark's cases, dive_cave_asm's and dive_mark_asm's mutants on the marked caves, dv_cost's cases and
mutants; ``--write-site`` writes the shipped table.
"""
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
import rolepath  # noqa: F401,E402 -- imported because it puts the role directories on sys.path

import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import cave_site_text  # noqa: E402 -- same reason
import dive_cave_asm as base  # noqa: E402 -- same reason (pipelines/)
import dive_mark_asm as mark  # noqa: E402 -- same reason (pipelines/)
import dive_brace_asm as brace  # noqa: E402 -- same reason (pipelines/)

MAGIC = b"FLYDIVE5"                     # 4: + the mark and dv_cost (D15); 5: + dv_brace (D31)
COST_AT = mark.BYTES                    # 7296, a multiple of 64
COST_COUNT_AT, COST_ARC_ON_AT, COST_ARC_COS_AT = COST_AT, COST_AT + 4, COST_AT + 8
COST_RING_AT, COST_SLOTS, COST_ENTRY = COST_AT + 64, 64, 48
# [D31] dv_brace (dive_brace_asm.py): the setting word Lua writes (k / s* in hundredths, 0 off) and its counter
BRACE_AT = COST_RING_AT + COST_SLOTS * COST_ENTRY
BRACE_WORD_AT, BRACE_COUNT_AT = BRACE_AT, BRACE_AT + 4
BYTES = BRACE_AT + 64
K_PAY, K_ARC, K_NOATTR = 1, 2, 3
NO_DIRECTION = 2.0
# engine fields (Warhammer3.exe 9.0.5)
BRACE_FLAGS, BRACED_BIT = 0x68, 0x8
ATTRS, ATTR_ID = 0x36C8, 0x27           # the unit's attribute sets, charge reflection
ATTR_WORDS = (0x28, 0x20, 0x58, 0x38, 0x48)   # 0x1414755e0: set, [pointer], removed, set, set
FACING, SIZE = 0xB0, 0x74
SKIP_DISP = 0xB2                        # 0x14325ab6a - 0x14325aab8
FACING_PLACEHOLDER = 0x3344556677889900

COST_SITE = ("4D 8B 34 24 4D 85 F6 0F 84 BF 00 00 00 80 B9 A9 3E 00 00 00 0F 84 B2 00 00 00 "
             "48 81 C1 C8 36 00 00 BA 2A 00 00 00 E8")
COST_STOLEN, COST_RESUME = "4D 8B 34 24 4D 85 F6", 26
FACING_ANCHOR = "0F 57 DB 0F 2E FB 0F B7 08 48 8D 05 ?? ?? ?? ?? F3 0F 10 64 C8 04 F3 0F 10 0C C8"
FACING_READ_AT, FACING_READ_AFTER = 12, 16
EXE_SITES = {"dv_cost": 0x14325AA9E, "dv_facing": 0x14307C5BD, "dv_brace": brace.EXE_SITE}
DB_PACK = base.EXE.parent / "data" / "db.pack"


def arc_angle(db_pack=DB_PACK):
    """bracing_attack_angle from the installed game's kv rules (a missing value is an error)."""
    import unit_attributes
    return unit_attributes.kv_rules(db_pack)["bracing_attack_angle"]


def arc_cos(angle):
    return struct.unpack("<f", struct.pack("<f", math.cos(angle * math.pi / 180.0)))[0]


def attr_test(unit, tag):
    """Flags after: 'jnz <tag>_yes' when the unit carries attribute ATTR_ID (0x1414755e0's tests, inlined);
    rax / r8 scratch."""
    w0, wp, wrm, w1, w2 = (ATTRS + o for o in ATTR_WORDS)
    word, bit = ATTR_ID >> 6, 1 << (ATTR_ID & 63)
    return f"""
    movabs rax, {bit:#x}
    test qword ptr [{unit} + {w0 + 8 * word:#x}], rax
    jnz {tag}_yes
    mov r8, qword ptr [{unit} + {wp:#x}]
    test r8, r8
    jz {tag}_noptr
    test qword ptr [r8 + {8 * word:#x}], rax
    jnz {tag}_yes
{tag}_noptr:
    test qword ptr [{unit} + {wrm + 8 * word:#x}], rax
    jnz {tag}_no
    test qword ptr [{unit} + {w1 + 8 * word:#x}], rax
    jnz {tag}_yes
    test qword ptr [{unit} + {w2 + 8 * word:#x}], rax
    jnz {tag}_yes
{tag}_no:
    xor eax, eax
    jmp {tag}_out
{tag}_yes:
    mov eax, 1
{tag}_out:
    test eax, eax
"""


XMM_SAVED = 6


def cost_source():
    save = "".join(f"    movdqu xmmword ptr [rsp + {16 * i}], xmm{i}\n" for i in range(XMM_SAVED))
    load = "".join(f"    movdqu xmm{i}, xmmword ptr [rsp + {16 * i}]\n" for i in range(XMM_SAVED))
    return f"""
    push rax
    push rbx
    push rcx
    push rdx
    push r8
    push r9
    push r10
    push r11
    lea rsp, [rsp - {16 * XMM_SAVED}]
{save}    mov r10, {base.BUF_PLACEHOLDER:#x}
    cmp dword ptr [r10 + {base.MODE_AT}], 1
    jne co_out
    cmp r15d, 5
    je co_type
    cmp r15d, 6
    jne co_out
co_type:
    test rsi, rsi
    jz co_out
    mov r11, rcx
    test r11, r11
    jz co_out
    mov r9, qword ptr [r12]
    test r9, r9
    jz co_out
    mov r8d, 4
co_chain:
    cmp qword ptr [r9 + {base.FC_OFF:#x}], 0
    jne co_fly
    mov r9, qword ptr [r9 + {base.PARENT_OFF:#x}]
    test r9, r9
    jz co_out
    dec r8d
    jnz co_chain
    jmp co_out
co_fly:
{mark.find("r10", "r9", False, "co")}    test rdx, rdx
    jz co_out
    cmp dword ptr [rdx + 8], {mark.STAMPED}
    jne co_out
{mark.tick("rsi", "ebx", "rax", "co")}    mov ecx, ebx
    sub ecx, dword ptr [rdx + 12]
    cmp ecx, {air_dive_rules.DIVE_COST_WINDOW_TICKS}
    jbe co_fresh
    mov eax, {mark.STAMPED}
    mov r8d, {mark.EXPIRED}
    lock cmpxchg dword ptr [rdx + 8], r8d
    jne co_out
    mov edx, ecx
{mark.event("r10", "r9", mark.EV_EXPIRED, "coe")}    jmp co_out
co_fresh:
    test byte ptr [rsi + {BRACE_FLAGS:#x}], {BRACED_BIT}
    jz co_out
{attr_test("r11", "ca")}    mov r8d, {K_PAY}
    jnz co_angle
    mov r8d, {K_NOATTR}
co_angle:
    movzx eax, word ptr [rsi + {FACING:#x}]
    mov rcx, {FACING_PLACEHOLDER:#x}
    lea rcx, [rcx + rax * 8]
    movss xmm0, dword ptr [rcx]
    movss xmm1, dword ptr [rcx + 4]
    movss xmm2, dword ptr [r9 + {base.POS_OFF:#x}]
    subss xmm2, dword ptr [rsi + {base.POS_OFF:#x}]
    movss xmm3, dword ptr [r9 + {base.POS_OFF + 8:#x}]
    subss xmm3, dword ptr [rsi + {base.POS_OFF + 8:#x}]
    movaps xmm4, xmm0
    mulss xmm4, xmm2
    movaps xmm5, xmm1
    mulss xmm5, xmm3
    addss xmm4, xmm5
    mulss xmm2, xmm2
    mulss xmm3, xmm3
    addss xmm2, xmm3
    mulss xmm0, xmm0
    mulss xmm1, xmm1
    addss xmm0, xmm1
    mulss xmm0, xmm2
    xorps xmm1, xmm1
    comiss xmm0, xmm1
    jbe co_nodir
    sqrtss xmm0, xmm0
    divss xmm4, xmm0
    jmp co_cos
co_nodir:
    mov eax, {struct.unpack("<I", struct.pack("<f", NO_DIRECTION))[0]:#x}
    movd xmm4, eax
co_cos:
    cmp r8d, {K_PAY}
    jne co_log
    cmp dword ptr [r10 + {COST_ARC_ON_AT}], 0
    je co_pay
    comiss xmm4, dword ptr [r10 + {COST_ARC_COS_AT}]
    jae co_pay
    mov r8d, {K_ARC}
    jmp co_log
co_pay:
    mov eax, {mark.STAMPED}
    mov ecx, {mark.SPENT}
    lock cmpxchg dword ptr [rdx + 8], ecx
    jne co_out
    mov ecx, ebx
    sub ecx, dword ptr [rdx + 12]
    mov edx, ecx
{mark.event("r10", "r9", mark.EV_SPENT, "cop")}co_log:
    mov eax, 1
    lock xadd dword ptr [r10 + {COST_COUNT_AT}], eax
    mov ecx, eax
    and ecx, {COST_SLOTS - 1}
    imul ecx, ecx, {COST_ENTRY}
    lea rcx, [r10 + rcx + {COST_RING_AT}]
    inc eax
    mov dword ptr [rcx + 44], 0
    mov qword ptr [rcx], r9
    mov rdx, qword ptr [r12]
    mov rdx, qword ptr [rdx + {base.UNIT_OFF:#x}]
    test rdx, rdx
    jnz co_unit
    mov rdx, qword ptr [r9 + {base.UNIT_OFF:#x}]
co_unit:
    mov qword ptr [rcx + 8], rdx
    mov qword ptr [rcx + 16], r11
    mov dword ptr [rcx + 24], ebx
    mov edx, dword ptr [r9 + {SIZE:#x}]
    mov dword ptr [rcx + 28], edx
    movss dword ptr [rcx + 32], xmm4
    mov dword ptr [rcx + 36], r8d
    movzx edx, byte ptr [rsi + {BRACE_FLAGS:#x}]
    mov dword ptr [rcx + 40], edx
    mov dword ptr [rcx + 44], eax
co_out:
{load}    lea rsp, [rsp + {16 * XMM_SAVED}]
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdx
    pop rcx
    pop rbx
    pop rax
    mov r14, qword ptr [r12]
    push rax
    movabs rax, {base.RESUME_PLACEHOLDER:#x}
    test r14, r14
    je co_skip
    cmp byte ptr [rcx + 0x3ea9], 0
    je co_skip
    xchg qword ptr [rsp], rax
    ret
co_skip:
    add rax, {SKIP_DISP:#x}
    xchg qword ptr [rsp], rax
    ret
"""


def assemble_cost(source=None):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_64
    code, _ = Ks(KS_ARCH_X86, KS_MODE_64).asm(source or cost_source(), 0x1000)
    code = bytes(code)
    for ph, n in ((base.BUF_PLACEHOLDER, 1), (base.RESUME_PLACEHOLDER, 1), (FACING_PLACEHOLDER, 1)):
        if code.count(struct.pack("<Q", ph)) != n:
            raise SystemExit(f"[dive_cost_asm] REFUSING: placeholder {ph:#x} not in dv_cost {n} times")
    return code


# --- emulator: dv_cost ------------------------------------------------------------------------------------
CODE, RESUME, BUF, STACK, OBJ, TABLE = 0x100000, 0x120000, 0x200000, 0x400000, 0x500000, 0x600000
VICTIM, VUNIT, ATT, MOUNT, ATT_STRUCT = OBJ + 0x1000, OBJ + 0x3000, OBJ + 0x8000, OBJ + 0xA000, OBJ + 0xE000
ATTR_PTR = OBJ + 0xF000
BATTLE, TICKS = OBJ + 0xC000, OBJ + 0xC800
COST_STEPS = 6000


class CostRig:
    """One machine: the cave, the buffer (mark table seeded by the caller), a soldier and its unit, a flying
    attacker (optionally ridden), the facing table. call() runs the cave once and returns where it left."""

    def __init__(self, code):
        from unicorn import UC_HOOK_CODE
        from unicorn import x86_const as X
        self.X = X
        mu = self.mu = base._uc()
        for at, size in ((CODE, 0x2000), (RESUME, 0x1000), (BUF, 0x4000), (STACK, 0x10000), (OBJ, 0x10000),
                         (TABLE, 0x80000)):
            mu.mem_map(at, size)
        code = base._fill(code, BUF, RESUME).replace(struct.pack("<Q", FACING_PLACEHOLDER), struct.pack("<Q", TABLE))
        mu.mem_write(CODE, code)
        mu.mem_write(RESUME, b"\x90" * 0x100)
        mu.mem_write(BUF + base.MODE_AT, struct.pack("<I", 1))
        self.stop = {}

        def on_code(uc, addr, _size, _data):
            self.stop["at"] = addr
            uc.emu_stop()
        for at in (RESUME, RESUME + SKIP_DISP):
            mu.hook_add(UC_HOOK_CODE, on_code, begin=at, end=at)
        # the battle tick, read through every entity's +0x58 -> +0x440 -> +0x98
        mu.mem_write(BATTLE + mark.TICKS_OFF, struct.pack("<Q", TICKS))
        for ent in (VICTIM, ATT, MOUNT):
            mu.mem_write(ent + mark.BATTLE_OFF, struct.pack("<Q", BATTLE))
        mu.mem_write(VICTIM + base.UNIT_OFF, struct.pack("<Q", VUNIT))
        mu.mem_write(ATT + base.UNIT_OFF, struct.pack("<Q", 0xAA0000))
        mu.mem_write(MOUNT + base.UNIT_OFF, struct.pack("<Q", 0xBB0000))
        mu.mem_write(ATT_STRUCT, struct.pack("<Q", ATT))
        mu.mem_write(VUNIT + 0x3EA9, b"\x01")
        self.facing(0, 1.0, 0.0)

    # --- world -------------------------------------------------------------------------------------------
    def tick(self, t):
        self.mu.mem_write(TICKS + mark.TICK_OFF, struct.pack("<I", t))

    def facing(self, index, fx, fz):
        self.mu.mem_write(VICTIM + FACING, struct.pack("<H", index))
        self.mu.mem_write(TABLE + index * 8, struct.pack("<ff", fx, fz))

    def place(self, ent, x, z):
        self.mu.mem_write(ent + base.POS_OFF, struct.pack("<f", x))
        self.mu.mem_write(ent + base.POS_OFF + 8, struct.pack("<f", z))

    def flyer(self, ent, flyer=True, parent=0, size=4):
        self.mu.mem_write(ent + base.FC_OFF, struct.pack("<Q", 0x77 if flyer else 0))
        self.mu.mem_write(ent + base.PARENT_OFF, struct.pack("<Q", parent))
        self.mu.mem_write(ent + SIZE, struct.pack("<I", size))

    def braced(self, flags):
        self.mu.mem_write(VICTIM + BRACE_FLAGS, bytes([flags]))

    def attr(self, word=None, pointer=False, removed=False):
        """the victim unit's attribute sets: ATTR_ID in set ``word`` (0x28 / 0x38 / 0x48), in the pointed set,
        and / or in the removed mask"""
        bit = struct.pack("<Q", 1 << ATTR_ID)
        zero = struct.pack("<Q", 0)
        for off in (0x28, 0x38, 0x48, 0x58):
            self.mu.mem_write(VUNIT + ATTRS + off, bit if off in (word, 0x58 if removed else None) else zero)
        self.mu.mem_write(VUNIT + ATTRS + 0x20, struct.pack("<Q", ATTR_PTR if pointer else 0))
        self.mu.mem_write(ATTR_PTR, bit if pointer else zero)

    def arc(self, on, cos):
        self.mu.mem_write(BUF + COST_ARC_ON_AT, struct.pack("<If", 1 if on else 0, cos))

    def seed(self, key, state, tick):
        """a mark table entry for ``key`` in its home slot"""
        slot = (key >> 4) & (mark.MARK_SLOTS - 1)
        self.mu.mem_write(BUF + mark.MARK_TABLE_AT + slot * 16, struct.pack("<QII", key, state, tick))

    def entry(self, key):
        raw = bytes(self.mu.mem_read(BUF + mark.MARK_TABLE_AT, mark.MARK_SLOTS * 16))
        for i in range(mark.MARK_SLOTS):
            k, st, tk = struct.unpack_from("<QII", raw, i * 16)
            if k == key:
                return st, tk
        return None

    def costs(self):
        n = struct.unpack("<I", bytes(self.mu.mem_read(BUF + COST_COUNT_AT, 4)))[0]
        out = []
        for s in range(max(0, n - COST_SLOTS), n):
            e = bytes(self.mu.mem_read(BUF + COST_RING_AT + (s % COST_SLOTS) * COST_ENTRY, COST_ENTRY))
            fly, aunit, vunit, tk, size, cos, kind, v68, seq = struct.unpack("<QQQIIfIII", e)
            out.append({"fly": fly, "aunit": aunit, "vunit": vunit, "tick": tk, "size": size,
                        "cos": round(cos, 4), "kind": kind, "v68": v68, "seq_ok": seq == s + 1})
        return out

    def marks(self):
        return mark._events(self.mu, BUF)

    # --- one call -------------------------------------------------------------------------------------------
    def call(self, dtype=5, victim=VICTIM, vunit=VUNIT, att_struct=ATT_STRUCT):
        from unicorn import UcError
        X = self.X
        keep = {X.UC_X86_REG_RAX: 0x1001, X.UC_X86_REG_RBX: 0x1002, X.UC_X86_REG_RCX: vunit,
                X.UC_X86_REG_RDX: victim, X.UC_X86_REG_RSI: victim, X.UC_X86_REG_RDI: 0x1006,
                X.UC_X86_REG_RBP: 0x1007, X.UC_X86_REG_R8: 0x1008, X.UC_X86_REG_R9: 0x1009,
                X.UC_X86_REG_R10: 0x100A, X.UC_X86_REG_R11: 0x100B, X.UC_X86_REG_R12: att_struct,
                X.UC_X86_REG_R13: 0x100D, X.UC_X86_REG_R15: dtype,
                X.UC_X86_REG_XMM0: 0x1111_2222_3333_4444_5555_6666_7777_8888,
                X.UC_X86_REG_XMM1: 0x9999_AAAA_BBBB_CCCC_DDDD_EEEE_FFFF_0000,
                X.UC_X86_REG_XMM2: 0x0102_0304_0506_0708_090A_0B0C_0D0E_0F10,
                X.UC_X86_REG_XMM3: 0x1112_1314_1516_1718_191A_1B1C_1D1E_1F20,
                X.UC_X86_REG_XMM4: 0x2122_2324_2526_2728_292A_2B2C_2D2E_2F30,
                X.UC_X86_REG_XMM5: 0x3132_3334_3536_3738_393A_3B3C_3D3E_3F40}
        for r, v in keep.items():
            self.mu.reg_write(r, v)
        rsp = STACK + 0x8000
        self.mu.reg_write(X.UC_X86_REG_RSP, rsp)
        self.mu.reg_write(X.UC_X86_REG_R14, 0xDEAD)
        self.stop.clear()
        try:
            self.mu.emu_start(CODE, 0, count=COST_STEPS)
        except UcError as exc:        # a fault is a failing case, reported by the caller
            return f"fault {exc}"
        bad = [r for r, v in keep.items() if self.mu.reg_read(r) != v]
        if bad:
            return f"registers changed {bad}"
        if self.mu.reg_read(X.UC_X86_REG_RSP) != rsp:
            return "stack not balanced"
        att = struct.unpack("<Q", bytes(self.mu.mem_read(att_struct, 8)))[0] if att_struct else None
        if self.mu.reg_read(X.UC_X86_REG_R14) != att:
            return f"r14 {self.mu.reg_read(X.UC_X86_REG_R14):#x} is not [r12]"
        where = self.stop.get("at")
        if where == RESUME:
            return "resume"
        if where == RESUME + SKIP_DISP:
            return "skip"
        return f"stopped at {where}"


def check_cost(code):
    """dv_cost on synthetic contacts -> (fails, cases)."""
    fails, n = [], 0
    win = air_dive_rules.DIVE_COST_WINDOW_TICKS
    cos80 = arc_cos(80.0)

    def fresh(arc_on=True):
        rig = CostRig(code)
        rig.flyer(ATT)
        rig.flyer(VICTIM, flyer=False)
        rig.braced(0x6B)
        rig.attr(word=0x28)
        rig.arc(arc_on, cos80)
        rig.tick(110)
        rig.seed(ATT, mark.STAMPED, 100)
        rig.place(VICTIM, 0.0, 0.0)
        rig.place(ATT, 3.0, 0.0)            # straight ahead of a soldier facing +x
        return rig

    def expect(label, got, want):
        nonlocal n
        n += 1
        if got != want:
            fails.append(f"dv_cost {label}: {got!r} != {want!r}")

    # 1. the paying contact: one cost entry, the mark spent with one event, the code goes on as vanilla
    rig = fresh()
    expect("pay: exit", rig.call(5), "resume")
    expect("pay: mark", rig.entry(ATT), (mark.SPENT, 100))
    expect("pay: cost", rig.costs(), [{"fly": ATT, "aunit": 0xAA0000, "vunit": VUNIT, "tick": 110, "size": 4,
                                       "cos": 1.0, "kind": K_PAY, "v68": 0x6B, "seq_ok": True}])
    expect("pay: mark event", [e[:5] for e in rig.marks()], [(mark.EV_SPENT, ATT, 0xAA0000, 110, 10)])
    # 2. the same dive again: nothing (one cost per mark)
    expect("again: exit", rig.call(6), "resume")
    expect("again: costs", len(rig.costs()), 1)
    # 3. type 6 pays too; type 0 / 4 never
    rig = fresh()
    expect("type 6", (rig.call(6), len(rig.costs())), ("resume", 1))
    for t in (0, 2, 4):
        rig = fresh()
        expect(f"type {t}", (rig.call(t), rig.costs(), rig.entry(ATT)), ("resume", [], (mark.STAMPED, 100)))
    # 4. mode 0: vanilla, nothing written
    rig = fresh()
    rig.mu.mem_write(BUF + base.MODE_AT, struct.pack("<I", 0))
    expect("mode 0", (rig.call(5), rig.costs(), rig.entry(ATT)), ("resume", [], (mark.STAMPED, 100)))
    # 5. not braced (bit 3 clear, other bits set): nothing, the mark stays for a later contact
    rig = fresh()
    rig.braced(0x61)
    expect("not braced", (rig.call(5), rig.costs(), rig.entry(ATT)), ("resume", [], (mark.STAMPED, 100)))
    # 6. charge reflection through each of 0x1414755e0's sets; the removed mask wins over the later two
    for label, kw, want in (("set +0x28", {"word": 0x28}, K_PAY), ("pointed set", {"pointer": True}, K_PAY),
                            ("set +0x38", {"word": 0x38}, K_PAY), ("set +0x48", {"word": 0x48}, K_PAY),
                            ("removed, set +0x38", {"word": 0x38, "removed": True}, K_NOATTR),
                            ("set +0x28 beats removed", {"word": 0x28, "removed": True}, K_PAY),
                            ("none", {}, K_NOATTR)):
        rig = fresh()
        rig.attr(**kw)
        rig.call(5)
        c = rig.costs()
        expect(f"attribute {label}", ([x["kind"] for x in c], rig.entry(ATT)[0]),
               ([want], mark.SPENT if want == K_PAY else mark.STAMPED))
    # attribute bit of another id does not count
    rig = fresh()
    rig.attr()
    rig.mu.mem_write(VUNIT + ATTRS + 0x28, struct.pack("<Q", 1 << (ATTR_ID + 1)))
    rig.call(5)
    expect("another attribute", [x["kind"] for x in rig.costs()], [K_NOATTR])
    # 7. the front arc: behind / to the side (cos 0 < cos 80) does not pay with the arc on; pays with it off
    rig = fresh()
    rig.place(ATT, -3.0, 0.0)
    rig.call(5)
    expect("behind, arc on", ([(x["kind"], x["cos"]) for x in rig.costs()], rig.entry(ATT)[0]),
           ([(K_ARC, -1.0)], mark.STAMPED))
    rig = fresh()
    rig.place(ATT, 0.0, 3.0)
    rig.call(5)
    expect("side, arc on", [(x["kind"], x["cos"]) for x in rig.costs()], [(K_ARC, 0.0)])
    rig = fresh()
    rig.place(ATT, 3.0, 4.0)                    # cos = 0.6, inside 80 degrees
    rig.call(5)
    expect("front-left, arc on", [(x["kind"], x["cos"]) for x in rig.costs()], [(K_PAY, 0.6)])
    rig = fresh(arc_on=False)
    rig.place(ATT, -3.0, 0.0)
    rig.call(5)
    expect("behind, arc off", [(x["kind"], x["cos"]) for x in rig.costs()], [(K_PAY, -1.0)])
    rig = fresh()
    rig.place(ATT, 0.0, 0.0)                    # no direction: counts as in front
    rig.call(5)
    expect("same point", [(x["kind"], x["cos"]) for x in rig.costs()], [(K_PAY, NO_DIRECTION)])
    rig = fresh()
    rig.facing(4096, 0.0, -1.0)                 # facing index read from +0xb0
    rig.place(ATT, 0.0, -2.0)
    rig.call(5)
    expect("facing index", [(x["kind"], x["cos"]) for x in rig.costs()], [(K_PAY, 1.0)])
    # 8. past the window: the mark expires (one event), no cost
    rig = fresh()
    rig.tick(100 + win + 1)
    rig.call(5)
    expect("expired", (rig.costs(), rig.entry(ATT), [e[:5] for e in rig.marks()]),
           ([], (mark.EXPIRED, 100), [(mark.EV_EXPIRED, ATT, 0xAA0000, 100 + win + 1, win + 1)]))
    rig = fresh()
    rig.tick(100 + win)
    rig.call(5)
    expect("last tick of the window", [x["kind"] for x in rig.costs()], [K_PAY])
    # 9. armed only, spent, no entry: nothing
    for st in (mark.ARMED, mark.SPENT, mark.EXPIRED):
        rig = fresh()
        rig.seed(ATT, st, 100)
        expect(f"state {st}", (rig.call(5), rig.costs(), rig.entry(ATT)), ("resume", [], (st, 100)))
    rig = fresh()                               # an armed mark logs nothing either (no touchdown yet)
    rig.seed(ATT, mark.ARMED, 100)
    rig.attr()
    expect("armed, no attribute", (rig.call(5), rig.costs()), ("resume", []))
    rig = fresh()
    rig.seed(ATT, 0, 0)
    rig.mu.mem_write(BUF + mark.MARK_TABLE_AT + ((ATT >> 4) & (mark.MARK_SLOTS - 1)) * 16, b"\0" * 16)
    expect("no entry", (rig.call(5), rig.costs()), ("resume", []))
    # 10. a rider: the mark of the mount pays; the cost names the rider's unit (the unit that pays)
    rig = fresh()
    rig.flyer(ATT, flyer=False, parent=MOUNT)
    rig.flyer(MOUNT, size=3)
    rig.place(MOUNT, 2.0, 0.0)
    rig.mu.mem_write(BUF + mark.MARK_TABLE_AT, b"\0" * mark.MARK_SLOTS * 16)
    rig.seed(MOUNT, mark.STAMPED, 100)
    rig.call(5)
    expect("rider", [(x["fly"], x["aunit"], x["size"], x["kind"]) for x in rig.costs()],
           [(MOUNT, 0xAA0000, 3, K_PAY)])
    rig = fresh()
    rig.flyer(ATT, flyer=False, parent=0)
    expect("ground attacker", (rig.call(5), rig.costs()), ("resume", []))
    # 11. the replaced code: no attacker / a unit with +0x3ea9 clear go to 0x14325ab6a, else 0x14325aab8
    rig = fresh()
    rig.mu.mem_write(ATT_STRUCT + 0x100, struct.pack("<Q", 0))
    expect("no attacker", (rig.call(5, att_struct=ATT_STRUCT + 0x100), rig.costs()), ("skip", []))
    rig = fresh()
    rig.mu.mem_write(VUNIT + 0x3EA9, b"\x00")
    expect("unit flag clear", rig.call(5), "skip")
    rig = fresh()
    rig.mu.mem_write(BUF + base.MODE_AT, struct.pack("<I", 0))
    rig.mu.mem_write(VUNIT + 0x3EA9, b"\x00")
    expect("unit flag clear, mode 0", rig.call(5), "skip")
    # 12. the ring wraps: entries past COST_SLOTS keep their seq
    rig = fresh()
    rig.attr()
    for i in range(COST_SLOTS + 3):
        rig.call(5)
    c = rig.costs()
    expect("ring wraps", (len(c), all(x["seq_ok"] for x in c), {x["kind"] for x in c}),
           (COST_SLOTS, True, {K_NOATTR}))
    return fails, n


COST_MUTANTS = (
    ("pays without bracing", "    test byte ptr [rsi + 0x68], 8\n    jz co_out\n", "    nop\n"),
    ("bracing from the wrong bit", "    test byte ptr [rsi + 0x68], 8\n", "    test byte ptr [rsi + 0x68], 4\n"),
    ("ignores the attribute", f"    mov r8d, {K_PAY}\n    jnz co_angle\n", f"    mov r8d, {K_PAY}\n    jmp co_angle\n"),
    ("removed mask ignored", "    jnz ca_no\n", "    nop\n"),
    ("pointed set ignored", "    jz ca_noptr\n", "    jmp ca_noptr\n"),
    ("ignores the arc", f"    mov r8d, {K_ARC}\n", f"    mov r8d, {K_PAY}\n"),
    ("arc compare reversed", "    jae co_pay\n", "    jb co_pay\n"),
    ("window not checked", f"    cmp ecx, {air_dive_rules.DIVE_COST_WINDOW_TICKS}\n    jbe co_fresh\n",
     "    jmp co_fresh\n"),
    ("pays on any type", "    cmp r15d, 6\n    jne co_out\n", "    nop\n"),
    ("does not spend", f"    mov ecx, {mark.SPENT}\n", f"    mov ecx, {mark.STAMPED}\n"),
    ("pays an armed mark", f"    cmp dword ptr [rdx + 8], {mark.STAMPED}\n    jne co_out\n", "    nop\n"),
    ("keys on the rider", "    jne co_fly\n", "    jmp co_fly\n"),
    ("seq not written", "    mov dword ptr [rcx + 44], eax\n", "    nop\n"),
    ("facing table index not scaled", "    lea rcx, [rcx + rax * 8]\n", "    lea rcx, [rcx + rax * 4]\n"),
    ("unit flag test dropped", "    cmp byte ptr [rcx + 0x3ea9], 0\n    je co_skip\n", "    nop\n"),
    ("mode not checked", f"    cmp dword ptr [r10 + {base.MODE_AT}], 1\n    jne co_out\n", "    nop\n"),
    ("size from the wrong field", f"    mov edx, dword ptr [r9 + {SIZE:#x}]\n", "    mov edx, dword ptr [r9 + 0x70]\n"),
    ("victim unit not saved", "    mov qword ptr [rcx + 16], r11\n", "    mov qword ptr [rcx + 16], rsi\n"),
    ("xmm5 not restored", "    movdqu xmm5, xmmword ptr [rsp + 80]\n", "    nop\n"),
)


def cost_negative_controls():
    survivors = []
    src = cost_source()
    for label, old, new in COST_MUTANTS:
        if src.count(old) < 1:
            raise SystemExit(f"[dive_cost_asm] REFUSING: mutant {label!r} does not apply")
        f, _n = check_cost(assemble_cost(src.replace(old, new, 1)))
        if not f:
            survivors.append(label)
    return survivors


def run_checks():
    """(codes, fails, counts, survivors): the marked caves under every shipped case and the mark's cases,
    dive_cave_asm's mutants on the marked sources, dive_mark_asm's mutants, dv_cost's cases and mutants."""
    codes, fails, counts = mark.check()
    survivors = []
    with mark._marked():
        for label, name, old, new in base.MUTANTS:
            src = mark.cave_source(name)
            if src.count(old) < 1:
                raise SystemExit(f"[dive_cost_asm] REFUSING: dive_cave_asm mutant {label!r} does not apply to the "
                                 "marked source")
            f, _n = base.CHECKS[name](base.assemble(name, src.replace(old, new, 1)))
            if not f:
                survivors.append(f"dive_cave_asm: {label}")
    survivors += [f"dive_mark_asm: {m}" for m in mark.negative_controls()]
    codes["dv_cost"] = assemble_cost()
    f, n = check_cost(codes["dv_cost"])
    fails += f
    counts["dv_cost"] = n
    survivors += [f"dv_cost: {m}" for m in cost_negative_controls()]
    codes["dv_brace"] = brace.assemble(BRACE_WORD_AT, BRACE_COUNT_AT)
    f, n = brace.check(codes["dv_brace"], BRACE_WORD_AT, BRACE_COUNT_AT)
    fails += f
    counts["dv_brace"] = n
    survivors += [f"dv_brace: {m}" for m in brace.negative_controls(BRACE_WORD_AT, BRACE_COUNT_AT)]
    return codes, fails, counts, survivors


# --- site table ------------------------------------------------------------------------------------------
CAVES = tuple(base.CAVES) + ("dv_cost", "dv_brace")


def layout():
    lay = dict(mark.layout())
    lay.update({"bytes": BYTES, "magic": MAGIC.decode(), "cost_count_at": COST_COUNT_AT,
                "cost_arc_on_at": COST_ARC_ON_AT, "cost_arc_cos_at": COST_ARC_COS_AT,
                "cost_ring_at": COST_RING_AT, "cost_slots": COST_SLOTS, "cost_entry": COST_ENTRY,
                "brace_word_at": BRACE_WORD_AT, "brace_count_at": BRACE_COUNT_AT})
    return lay


def cost_rules(angle):
    """the numbers the battle script needs, all from air_dive_rules (and the game's angle)"""
    codes = air_dive_rules.TAKEOFF_SIZE_CODES
    return {"share_by_code": [air_dive_rules.DIVE_COST_SHARE[s] for s in sorted(codes, key=codes.get)],
            "max_call": air_dive_rules.DIVE_COST_MAX_CALL, "keep": air_dive_rules.DIVE_COST_KEEP_UNARY,
            "window": air_dive_rules.DIVE_COST_WINDOW_TICKS, "follow": air_dive_rules.DIVE_COST_FOLLOW_TICKS,
            "front_arc": air_dive_rules.DIVE_COST_FRONT_ARC, "angle": angle, "arc_cos": arc_cos(angle)}


def brace_rules():
    """[D31] the numbers the battle script and the MCT page need for dv_brace and the cost setting, all from
    air_dive_rules"""
    r = air_dive_rules
    return {"default_on": r.BRACE_LINE_DEFAULT_ON, "k": r.BRACE_MASS_K, "k_min": r.BRACE_MASS_K_RANGE[0],
            "k_max": r.BRACE_MASS_K_RANGE[1], "k_step": r.BRACE_MASS_K_STEP, "share": r.BRACE_SHARE_MIN,
            "share_min": r.BRACE_SHARE_MIN_RANGE[0], "share_max": r.BRACE_SHARE_MIN_RANGE[1],
            "share_step": r.BRACE_SHARE_MIN_STEP, "scale": r.BRACE_WORD_SCALE,
            "cost": r.DIVE_COST_PERCENT_DEFAULT, "cost_min": r.DIVE_COST_PERCENT_RANGE[0],
            "cost_max": r.DIVE_COST_PERCENT_RANGE[1], "mct_mod": r.BREATH_SWITCH_MCT_MOD,
            "mct_on": r.BRACE_MCT_OPTIONS["on"], "mct_k": r.BRACE_MCT_OPTIONS["k"],
            "mct_share": r.BRACE_MCT_OPTIONS["share"], "mct_cost": r.BRACE_MCT_OPTIONS["cost"],
            "default_word": r.brace_word(r.BRACE_MASS_K, r.BRACE_SHARE_MIN)}


def source_sha(angle):
    norm = lambda s: "\n".join(line.strip() for line in s.splitlines() if line.strip())  # noqa: E731 -- because base.source_sha uses the same one-liner
    with mark._marked():
        marked = {n: norm(mark.cave_source(n)) for n in base.CAVES}
    blob = json.dumps({"base": base.source_sha(), "marked": marked, "dv_cost": norm(cost_source()),
                       "site": [COST_SITE, COST_STOLEN, COST_RESUME, FACING_ANCHOR, FACING_READ_AT,
                                FACING_READ_AFTER], "layout": layout(), "rules": cost_rules(angle),
                       "dv_brace": norm(brace.source(BRACE_WORD_AT, BRACE_COUNT_AT)),
                       "brace_site": [brace.SITE, brace.STOLEN, brace.RESUME_OFF], "brace": brace_rules()},
                      sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def agreement_format(angle):
    """whole and exact in a float32: players whose caves or numbers differ are told they run another version"""
    return 2 + int(source_sha(angle)[:5], 16)


def _lua_bytes(raw):
    return "'" + "".join(f"\\{b}" for b in raw) + "'"


def template(code):
    return cave_site_text.bytes_template(code, base.BUF_PLACEHOLDER, base.RESUME_PLACEHOLDER,
                                         {base.ORIG_PLACEHOLDER: "{orig:8}", FACING_PLACEHOLDER: "{facing:8}"})


def site_lua(codes, angle):
    rules = cost_rules(angle)
    skip_bits = struct.unpack("<I", struct.pack("<f", base.SKIP_SPEED))[0]
    lines = [
        "-- dive_site.lua -- GENERATED by tools/pipelines/dive_cost_asm.py",
        "-- (--write-site); do not edit, rerun the generator. Pure data.",
        "-- [AIR-DIVE-MP-DIVE-W1 2026-11-12, §C8-61] The physics dive: eleven code caves (dive_cave_asm.py),",
        "-- [D15, d15-1118 stage 5] with the dive mark (dive_mark_asm.py) and dv_cost, the braced-spear cost of a",
        "-- dive (judged in the cave, taken by lib/dive_cost.lua), as memreader Plus site-loader entries, plus the",
        "-- buffer layout and the cost numbers (tools/lib/air_dive_rules.py; the angle is the game's own).",
        "-- / 物理俯冲与俯冲撞枪阵代价：代码洞的位点表、缓冲区布局与数值（生成物）。",
        "return {",
        f"    owner = '{base.OWNER}',",
        f"    feature = '{base.FEATURE}',",
        "    entries = {",
    ]
    for name, (pattern, at, stolen, _resume) in base.CAVES.items():
        lines += cave_site_text.cave_entry_lines(
            name, base.FEATURE, pattern, at, stolen, template(codes[name]),
            base.CALL_SITES[name]["call_at"] if name in base.CALL_SITES else None)
    lines += ["        {",
              f"            name = 'dv_facing', feature = '{base.FEATURE}', kind = 'anchor',",
              f"            pattern = '{FACING_ANCHOR}',",
              f"            reads = {{ facing = {{ at = {FACING_READ_AT}, after = {FACING_READ_AFTER} }} }},",
              "        },",
              "        {",
              f"            name = 'dv_cost', feature = '{base.FEATURE}', kind = 'cave',",
              f"            pattern = '{COST_SITE}',",
              f"            at = 0, expect = '{COST_STOLEN}',",
              "            reads = { facing = { from = 'dv_facing' } },",
              f"            bytes = '{template(codes['dv_cost'])}',",
              "        },"]
    lines += cave_site_text.cave_entry_lines("dv_brace", base.FEATURE, brace.SITE, 0, brace.STOLEN,
                                             template(codes["dv_brace"]))
    resume = {n: base.CAVES[n][3] for n in base.CAVES if base.CAVES[n][3]}
    resume["dv_cost"] = COST_RESUME
    resume["dv_brace"] = brace.RESUME_OFF
    b = brace_rules()
    lines += [
        "    },",
        "    caves = { " + ", ".join(f"'{n}'" for n in CAVES) + " },",
        "    resume_at = { " + ", ".join(f"{n} = {v}" for n, v in resume.items()) + " },",
        "    layout = {",
        "        " + ", ".join(f"{k} = {v!r}".replace('"', "'") for k, v in layout().items()) + ",",
        "    },",
        f"    skip_speed = {base.SKIP_SPEED}, skip_speed_bits = {skip_bits},",
        "    cost = {",
        "        share_by_code = { " + ", ".join(repr(s) for s in rules["share_by_code"]) + " },",
        f"        max_call = {rules['max_call']!r}, keep = {rules['keep']!r}, window = {rules['window']}, "
        f"follow = {rules['follow']},",
        f"        front_arc = {'true' if rules['front_arc'] else 'false'}, angle = {rules['angle']!r}, "
        f"arc_cos = {rules['arc_cos']!r},",
        f"        arc_cos_bytes = {_lua_bytes(struct.pack('<f', rules['arc_cos']))},",
        f"        kinds = {{ pay = {K_PAY}, arc = {K_ARC}, no_attribute = {K_NOATTR} }},",
        "    },",
        "    -- [D31] dv_brace and the MCT settings of the braced-line work (lib/brace_rule.lua, the MCT page)",
        "    brace = {",
        f"        default_on = {'true' if b['default_on'] else 'false'}, k = {b['k']!r}, k_min = {b['k_min']!r}, "
        f"k_max = {b['k_max']!r}, k_step = {b['k_step']!r},",
        f"        share = {b['share']!r}, share_min = {b['share_min']!r}, share_max = {b['share_max']!r}, "
        f"share_step = {b['share_step']!r}, scale = {b['scale']},",
        f"        cost = {b['cost']}, cost_min = {b['cost_min']}, cost_max = {b['cost_max']}, "
        f"default_word = {b['default_word']},",
        f"        mct_mod = '{b['mct_mod']}', mct_on = '{b['mct_on']}', mct_k = '{b['mct_k']}', "
        f"mct_share = '{b['mct_share']}', mct_cost = '{b['mct_cost']}',",
        "    },",
        f"    format = {agreement_format(angle)},",
        f"    build = '{base.BUILD}',",
        f"    source_sha = '{source_sha(angle)}',",
        "}",
    ]
    return "\n".join(lines) + "\n"


def check_site_file(mod_dir=base.MOD_DIR, db_pack=DB_PACK):
    """Offline (no keystone; reads the game's bracing_attack_angle): the committed site table matches these
    sources, numbers and the installed game's angle."""
    angle = arc_angle(db_pack)
    path = Path(mod_dir) / base.SITE_LUA
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for needle in (f"source_sha = '{source_sha(angle)}'", f"format = {agreement_format(angle)},"):
        if needle not in text:
            raise RuntimeError(f"[dive_cost_asm] REFUSING: {path} is missing or stale (lacks {needle!r}); "
                               "rerun dive_cost_asm.py --write-site")
    return True


def check_exe(exe_path=base.EXE):
    """The eleven dive sites (dive_cave_asm.check_exe), dv_cost's site with its replaced bytes and the facing
    anchor, each exactly once. Returns {name: virtual address}."""
    import pefile
    found = base.check_exe(exe_path)
    pe = pefile.PE(str(exe_path), fast_load=True)
    image = pe.OPTIONAL_HEADER.ImageBase
    code = [(image + s.VirtualAddress, s.get_data()) for s in pe.sections if s.Characteristics & 0x20000000]
    for name, pattern, want in (("dv_cost", COST_SITE, COST_STOLEN), ("dv_facing", FACING_ANCHOR, None),
                                ("dv_brace", brace.SITE, brace.STOLEN)):
        rx = re.compile(b"".join(b"." if t == "??" else re.escape(bytes([int(t, 16)])) for t in pattern.split()),
                        re.S)
        hits = [va + m.start() for va, data in code for m in rx.finditer(data)]
        if len(hits) != 1:
            raise RuntimeError(f"[dive_cost_asm] REFUSING: {name} matches {len(hits)} times in {exe_path}")
        if want and not pattern.startswith(want):
            raise RuntimeError(f"[dive_cost_asm] REFUSING: {name} pattern does not start with its replaced bytes")
        found[name] = hits[0]
    return found


def main(argv):
    if "--check-exe" in argv:
        print("[dive_cost_asm] exe sites:", {k: hex(v) for k, v in check_exe().items()})
    codes, fails, counts, survivors = run_checks()
    if fails:
        raise SystemExit("[dive_cost_asm] emulator check FAILED:\n  " + "\n  ".join(fails[:40]))
    if survivors:
        raise SystemExit(f"[dive_cost_asm] REFUSING: mutants passed every case: {survivors}")
    n_mut = len(base.MUTANTS) + len(mark.MUTANTS) + len(COST_MUTANTS) + len(brace.MUTANTS)
    print(f"[dive_cost_asm] caves {', '.join(f'{n} {len(codes[n])} B' for n in codes)}; emulator cases {counts}; "
          f"{n_mut} mutants each caught ({len(base.MUTANTS)} dive, {len(mark.MUTANTS)} mark, "
          f"{len(COST_MUTANTS)} cost, {len(brace.MUTANTS)} brace)")
    if "--write-site" in argv:
        angle = arc_angle()
        out = base.MOD_DIR / base.SITE_LUA
        out.write_text(site_lua(codes, angle), encoding="utf-8", newline="\n")
        print(f"[dive_cost_asm] wrote {out} (bracing_attack_angle {angle}, cos {arc_cos(angle)!r})")


if __name__ == "__main__":
    main(sys.argv[1:])
