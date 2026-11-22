"""[D25 / D29 / D31, brace-solver-1120] ``dv_brace``: a braced line against a dive, inside the engine's own pair
solver. Shipped through dive_cost_asm.py, which writes the dive site table with this cave in it (same feature,
same buffer, layout offsets passed in from there).

What the cave reads is what the engine itself uses, read from Warhammer3.exe 9.0.5 (6ae2a00b):
* the site: the velocity block of the neighbour-collision pair solver 0x14317768c (its only caller 0x143177490,
  call at 0x14317762f; docs/HISTORY.md PAIR-SOLVER-1120). The 26 bytes 0x1431781e9..0x143178202 replaced here:
      test r12b, r12b / je +6 / mulss xmm2, [r14 + 0x54] / movss xmm1, [rbx + 0x4c] /
      test r13b, r13b / je +5 / mulss xmm1, [rbx + 0x54]
  r14 = body A, rbx = body B (a body is its entity + 0x68: +0x4c the entity's mass +0xb4, +0x54 its brace
  multiplier +0xbc); xmm2 already holds A's mass (0x1431781da); r12b / r13b are set by the solver at 0x143177e69 /
  0x143177f13 only for a braced body (byte [body] bit 3) with the other in its front cone, the bodies passed the
  solver's own masks and unit-attribute rules (0x14317790c..0x143177a80, their entities' vfunc +0x78), and the pair
  is marked for this step ([rbp + 0x78] == 1). After the bytes: xmm2 = M_A, xmm1 = M_B (braced where counted),
  and the block at 0x143178203.. computes the velocity target with them and moves each body's momentum toward it
  by its size-tier share (xmm12 for A, xmm6 for B, set at 0x143178025..0x143178087; 0.8 / 0.2 / 0.1 / 0 for the
  larger body at tier gaps 1-4). The position push before the block (0x14317808b..0x143178156) has already used
  the shares; xmm6 / xmm12 are callee-saved and restored at the solver's common exit 0x143177817.
  PAIR-PROBE-1120 read in game: M = mass x 5.43 for braced Empire spearmen, e 0.3, shares 0.8 / 0.2 / 0.1, and the
  correction reached the landed flyers' velocity every time.
* the flyer: the other body's entity (body - 0x68) or the entity it rides (+0x2e0, at most 4 links) carries a
  flight controller (+0x128 not 0), and that flight entity is in a landed dive (+0x104 0, +0x710 not 0): the dive
  caves' own tests (dive_cave_asm.py). INFERRED, not read: every body in this solver is a battle entity of the
  class those offsets belong to (the outer loop takes the bodies from the battle's spatial grid as entity + 0x68,
  and the solver calls both entities' vfunc +0x78 for their units before it can set r12b / r13b).

The cave: does exactly what the 26 bytes do; then, when mode is 1 and the setting word is not 0, for each body
the engine counted as braced (r13b: B, r12b: A) whose OTHER body is a flyer in a landed dive: the braced mass
x k (xmm1 for B, xmm2 for A) and the flyer's share = max(share, s*) (xmm12 when the flyer is A, xmm6 when it is
B), counted (lock inc). k = (word & 0xffff) / 100, s* = ((word >> 16) & 0xff) / 100; a word whose k part is 0
counts as off. It ends with the replaced code's last flag-setter (test r13b, r13b), so every register, every
other xmm register and the flags are what the replaced bytes leave; it returns through push / ret (no register).

[D64 2026-11-22] Once per soldier. The solver runs every step while a pair touches, and a braced soldier is set back
in its place by its formation, so a scaling applied on every step is a brake that never runs out (the landed star
dragon crawled about 1 m/s into braced spearmen, HISTORY BRACE-ONCE-1122). A collision costs one exchange per
soldier hit: the cave scales a braced body against a given landed flyer only the first time it meets it in this
dive; on its later steps the pair is the engine's own (its mass, its brace, its size-tier share). The memory is
per flyer and per dive: the flyer's slide entry (dive_cave_asm's table at SLIDE_AT, claimed at its first hold on
the ground) names the dive by its first-hold point, and the hit slot of the same index (HIT_REL from the setting
word, HIT_BYTES each) keeps that point as its tag, a count, and the last HIT_RING braced bodies met. A slot whose
tag is not the entry's point belongs to an earlier dive: emptied first. Counted: first meetings at the word's
counter (+4), later steps left to the engine at REPEAT_REL, a flyer with no slide entry yet (scaled, not
remembered) at NOSLOT_REL.

``python dive_brace_asm.py`` (keystone + unicorn) assembles and runs the emulator check against the replaced bytes
themselves and the mutants; dive_cost_asm.py runs the same from its run_checks.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
import rolepath  # noqa: F401,E402 -- imported because it puts the role directories on sys.path

import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import dive_cave_asm as base  # noqa: E402 -- same reason (pipelines/)

NAME = "dv_brace"
SITE = ("45 84 E4 74 06 F3 41 0F 59 56 54 F3 0F 10 4B 4C 45 84 ED 74 05 F3 0F 59 4B 54 "
        "F3 41 0F 10 6E 70 0F 28 C1 8A 55 78")
STOLEN, RESUME_OFF = "45 84 E4 74 06", 26
REPLACED = bytes.fromhex("4584E47406F3410F595654F30F104B4C4584ED7405F30F594B54")
EXE_SITE = 0x1431781E9
BODY_OFF = 0x68                      # body = entity + 0x68
MASS, BRACE = 0x4C, 0x54             # in the body
CHAIN = 4                            # links followed through +0x2e0 (dv_cost's depth)
HUNDRED = 0x42C80000                 # 100.0f
# [D64] the once-per-soldier memory, relative to the setting word (dive_cost_asm's BRACE block): +16 u32 later
# steps left to the engine, +20 u32 flyers scaled with no slide entry yet; the hit slots from +64, one per slide
# slot: +0 the dive's first-hold point (the slide entry's +8, 8 bytes), +8 u32 braced bodies met, +16 the last
# HIT_RING of them (body pointers)
REPEAT_REL, NOSLOT_REL, HIT_REL = 16, 20, 64
HIT_RING = 16
HIT_BYTES = 16 + 8 * HIT_RING
assert HIT_RING & (HIT_RING - 1) == 0
assert len(REPLACED) == RESUME_OFF and SITE.replace(" ", "").lower().startswith(REPLACED.hex())


def _flyer(tag):
    """rcx = an entity: falls through when it, or the entity it rides, is a flyer in a landed dive, else
    'jmp <tag>_no'. Uses rax; rcx is left on the flight entity."""
    return f"""
    mov eax, {CHAIN}
{tag}_chain:
    cmp qword ptr [rcx + {base.FC_OFF:#x}], 0
    jne {tag}_fly
    mov rcx, qword ptr [rcx + {base.PARENT_OFF:#x}]
    test rcx, rcx
    jz {tag}_no
    dec eax
    jnz {tag}_chain
    jmp {tag}_no
{tag}_fly:
    cmp dword ptr [rcx + {base.LAYER_OFF:#x}], 0
    jne {tag}_no
    cmp dword ptr [rcx + {base.FLYMODE_OFF:#x}], 0
    je {tag}_no
"""


def _once(tag, braced):
    """[D64] rcx = the flight entity (after _flyer), rdx = the buffer, ``braced`` = the braced body's register:
    'jmp <tag>_no' when this body already met this flyer in this dive (counted at REPEAT); else falls through,
    the body remembered in the flyer's hit slot (or counted at NOSLOT when the flyer has no slide entry). The
    slide table is probed as dive_cave_asm's _window_test does (key >> 4, open addressing; key | 1 = released
    is the same flyer; an empty slot ends the probe). Uses rax, rcx; r8 / r9 saved."""
    return f"""
    push r8
    push r9
    mov r8, rcx
    mov rax, rcx
    shr rax, 4
    and eax, {base.SLIDE_SLOTS - 1}
    mov r9d, {base.SLIDE_SLOTS}
{tag}_sp:
    mov rcx, rax
    shl rcx, 4
    mov rcx, qword ptr [rdx + rcx + {base.SLIDE_AT}]
    test rcx, rcx
    je {tag}_none
    and rcx, -2
    cmp rcx, r8
    je {tag}_found
    inc eax
    and eax, {base.SLIDE_SLOTS - 1}
    dec r9d
    jne {tag}_sp
{tag}_none:
    lock inc dword ptr [rdx + NOSLOT]
    jmp {tag}_go
{tag}_found:
    mov rcx, rax
    shl rcx, 4
    mov r9, qword ptr [rdx + rcx + {base.SLIDE_AT + 8}]
    imul eax, eax, {HIT_BYTES}
    lea r8, [rdx + rax + HIT]
    cmp qword ptr [r8], r9
    je {tag}_same
    mov dword ptr [r8 + 8], 0
    mov qword ptr [r8], r9
{tag}_same:
    mov ecx, dword ptr [r8 + 8]
    cmp ecx, {HIT_RING}
    jbe {tag}_scan
    mov ecx, {HIT_RING}
{tag}_scan:
    test ecx, ecx
    je {tag}_new
    dec ecx
    cmp qword ptr [r8 + rcx*8 + 16], {braced}
    jne {tag}_scan
    lock inc dword ptr [rdx + REPEAT]
    pop r9
    pop r8
    jmp {tag}_no
{tag}_new:
    mov eax, 1
    lock xadd dword ptr [r8 + 8], eax
    and eax, {HIT_RING - 1}
    mov qword ptr [r8 + rax*8 + 16], {braced}
{tag}_go:
    pop r9
    pop r8
"""


def _part(shift, mask):
    """xmm0 = ((word >> shift) & mask) / 100 (the word at [rdx + WORD], re-read); rax scratch."""
    return f"""
    mov eax, dword ptr [rdx + WORD]
    shr eax, {shift}
    and eax, {mask:#x}
    cvtsi2ss xmm0, eax
    push {HUNDRED:#x}
    divss xmm0, dword ptr [rsp]
    lea rsp, [rsp + 8]
"""


def source(word_at, count_at):
    s = f"""
    push rax
    push rcx
    push rdx
    lea rsp, [rsp - 16]
    movdqu xmmword ptr [rsp], xmm0
    test r12b, r12b
    je br_o1
    mulss xmm2, dword ptr [r14 + {BRACE:#x}]
br_o1:
    movss xmm1, dword ptr [rbx + {MASS:#x}]
    test r13b, r13b
    je br_o2
    mulss xmm1, dword ptr [rbx + {BRACE:#x}]
br_o2:
    mov rdx, {base.BUF_PLACEHOLDER:#x}
    cmp dword ptr [rdx + {base.MODE_AT}], 1
    jne br_out
    test word ptr [rdx + WORD], 0xffff
    je br_out
    test r13b, r13b
    je br_a
    lea rcx, [r14 - {BODY_OFF:#x}]
{_flyer("fa")}{_once("fa", "rbx")}{_part(0, 0xFFFF)}    mulss xmm1, xmm0
{_part(16, 0xFF)}    maxss xmm12, xmm0
    lock inc dword ptr [rdx + COUNT]
fa_no:
br_a:
    test r12b, r12b
    je br_out
    lea rcx, [rbx - {BODY_OFF:#x}]
{_flyer("fb")}{_once("fb", "r14")}{_part(0, 0xFFFF)}    mulss xmm2, xmm0
{_part(16, 0xFF)}    maxss xmm6, xmm0
    lock inc dword ptr [rdx + COUNT]
fb_no:
br_out:
    movdqu xmm0, xmmword ptr [rsp]
    lea rsp, [rsp + 16]
    pop rdx
    pop rcx
    pop rax
    test r13b, r13b
    push rax
    movabs rax, {base.RESUME_PLACEHOLDER:#x}
    xchg qword ptr [rsp], rax
    ret
"""
    return (s.replace("+ WORD]", f"+ {word_at:#x}]").replace("+ COUNT]", f"+ {count_at:#x}]")
            .replace("+ REPEAT]", f"+ {word_at + REPEAT_REL:#x}]").replace("+ NOSLOT]", f"+ {word_at + NOSLOT_REL:#x}]")
            .replace("+ HIT]", f"+ {word_at + HIT_REL:#x}]"))


def assemble(word_at, count_at, src=None):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_64
    code, _ = Ks(KS_ARCH_X86, KS_MODE_64).asm(src or source(word_at, count_at), 0x1000)
    code = bytes(code)
    for ph in (base.BUF_PLACEHOLDER, base.RESUME_PLACEHOLDER):
        if code.count(struct.pack("<Q", ph)) != 1:
            raise SystemExit(f"[dive_brace_asm] REFUSING: placeholder {ph:#x} not in {NAME} exactly once")
    return code


# --- emulator: the cave against the replaced bytes themselves ----------------------------------------------
CODE, REF, RESUME, BUF, STACK, OBJ = 0x100000, 0x110000, 0x120000, 0x200000, 0x400000, 0x500000
EA, EB, EM, EM2, EM3, EM4, EM5 = (OBJ + 0x1000 * i for i in range(1, 8))
BUF_SIZE = 0x10000                  # [D64] the hit slots reach past 0x4000
GPRS = ("RAX", "RBX", "RCX", "RDX", "RSI", "RDI", "RBP", "RSP", "R8", "R9", "R10", "R11", "R12", "R13", "R14",
        "R15", "EFLAGS")
STEPS = 2000


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def fbits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def lane(value, low):
    """the 128-bit value with its low 32 bits replaced by the float ``low``"""
    return (value & ~0xFFFFFFFF) | fbits(low)


class Rig:
    """One machine with the cave at CODE and the replaced bytes at REF, both returning to RESUME; the same world
    (bodies, entities, buffer) for both. run(at) runs from CODE or REF and returns the end state."""

    def __init__(self, code, word_at, count_at):
        from unicorn import UC_HOOK_CODE
        from unicorn import x86_const as X
        self.X, self.word_at, self.count_at = X, word_at, count_at
        mu = self.mu = base._uc()
        for at, size in ((CODE, 0x2000), (REF, 0x1000), (RESUME, 0x1000), (BUF, BUF_SIZE), (STACK, 0x10000),
                         (OBJ, 0x10000)):
            mu.mem_map(at, size)
        mu.mem_write(CODE, base._fill(code, BUF, RESUME))
        mu.mem_write(REF, REPLACED + b"\xE9" + struct.pack("<i", RESUME - (REF + RESUME_OFF + 5)))
        mu.mem_write(RESUME, b"\x90" * 16)
        self.stop = {}

        def on_code(uc, addr, _size, _data):
            self.stop["at"] = addr
            uc.emu_stop()
        mu.hook_add(UC_HOOK_CODE, on_code, begin=RESUME, end=RESUME)

    def word(self, value):
        self.mu.mem_write(BUF + self.word_at, struct.pack("<I", value))

    def mode(self, value):
        self.mu.mem_write(BUF + base.MODE_AT, struct.pack("<I", value))

    def count(self):
        return struct.unpack("<I", bytes(self.mu.mem_read(BUF + self.count_at, 4)))[0]

    def entity(self, ent, mass, brace, fc=0, parent=0, layer=0, flymode=0):
        mu = self.mu
        mu.mem_write(ent + BODY_OFF + MASS, struct.pack("<f", mass))
        mu.mem_write(ent + BODY_OFF + BRACE, struct.pack("<f", brace))
        mu.mem_write(ent + base.FC_OFF, struct.pack("<Q", fc))
        mu.mem_write(ent + base.PARENT_OFF, struct.pack("<Q", parent))
        mu.mem_write(ent + base.LAYER_OFF, struct.pack("<I", layer))
        mu.mem_write(ent + base.FLYMODE_OFF, struct.pack("<I", flymode))

    def regs(self, r12b, r13b, xmm2, share_a, share_b, flags):
        X = self.X
        vals = {"RAX": 0x1111, "RBX": EB + BODY_OFF, "RCX": 0x3333, "RDX": 0x4444, "RSI": 0x5501, "RDI": 0x8000,
                "RBP": 0x7777, "R8": 0x20000, "R9": 0x9999, "R10": 0xAAAA, "R11": 0xBBBB,
                "R12": 0xC0C0C000 | r12b, "R13": 0xD0D0D000 | r13b, "R14": EA + BODY_OFF, "R15": 0xF0F0F001}
        for name, v in vals.items():
            self.mu.reg_write(getattr(X, f"UC_X86_REG_{name}"), v)
        self.mu.reg_write(X.UC_X86_REG_RSP, STACK + 0x8000)
        self.mu.reg_write(X.UC_X86_REG_EFLAGS, flags)
        for i in range(16):
            self.mu.reg_write(getattr(X, f"UC_X86_REG_XMM{i}"),
                              (0x0102030405060708_090A0B0C << 32) * (i + 1) & ((1 << 128) - 1) | fbits(1.5 + i))
        self.mu.reg_write(X.UC_X86_REG_XMM2, (0xAB << 64) | fbits(xmm2))
        self.mu.reg_write(X.UC_X86_REG_XMM12, (0xCD << 64) | fbits(share_a))
        self.mu.reg_write(X.UC_X86_REG_XMM6, (0xEF << 64) | fbits(share_b))

    def run(self, at):
        from unicorn import UcError
        X = self.X
        self.stop.clear()
        try:
            self.mu.emu_start(at, 0, count=STEPS)
        except UcError as exc:
            return f"fault {exc}"
        if self.stop.get("at") != RESUME:
            return f"stopped at {self.stop.get('at')}"
        state = {n: self.mu.reg_read(getattr(X, f"UC_X86_REG_{n}")) for n in GPRS}
        state.update({f"XMM{i}": self.mu.reg_read(getattr(X, f"UC_X86_REG_XMM{i}")) for i in range(16)})
        state["stack"] = bytes(self.mu.mem_read(STACK + 0x8000, 64))
        return state


# body A = EA, body B = EB; EM.. flight mounts / chain links
SPEAR, PEG, DRAGON = (100.0, 5.43), 1300.0, 4425.0


def check(code, word_at, count_at):
    """dv_brace on synthetic pairs against the replaced bytes -> (fails, cases). Every case runs the reference
    (the 26 bytes) and the cave from the same state; the cave's end state must equal the reference's except, in
    the cases that scale, the braced mass and the flyer's share, which must equal the expected values."""
    k_def, s_def = air_dive_rules.BRACE_MASS_K, air_dive_rules.BRACE_SHARE_MIN
    word_def = air_dive_rules.brace_word(k_def, s_def)
    fails, n = [], 0

    def case(label, world, r12b, r13b, share_a, share_b, word=word_def, mode=1, want=None, flags=0x202,
             counted=None):
        """``want``: {register: low float} the cave changes from the reference (None: nothing)."""
        nonlocal n
        n += 1
        rig = Rig(code, word_at, count_at)
        rig.mode(mode)
        rig.word(word)
        world(rig)
        xmm2 = struct.unpack("<f", bytes(rig.mu.mem_read(EA + BODY_OFF + MASS, 4)))[0]   # A's mass (0x1431781da)
        rig.regs(r12b, r13b, xmm2, share_a, share_b, flags)
        ref = rig.run(REF)
        rig.regs(r12b, r13b, xmm2, share_a, share_b, flags)
        got = rig.run(CODE)
        if isinstance(ref, str) or isinstance(got, str):
            fails.append(f"{NAME} {label}: ref {ref if isinstance(ref, str) else 'ok'} / cave "
                         f"{got if isinstance(got, str) else 'ok'}")
            return
        expect = dict(ref)
        for reg, low in (want or {}).items():
            expect[reg] = lane(ref[reg], low)
        bad = {r: (hex(got[r]) if isinstance(got[r], int) else got[r], hex(expect[r]) if isinstance(expect[r], int)
                   else expect[r]) for r in expect if got[r] != expect[r]}
        if bad:
            fails.append(f"{NAME} {label}: {bad}")
        want_count = (len(want or {}) // 2) if counted is None else counted
        if rig.count() != want_count:
            fails.append(f"{NAME} {label}: count {rig.count()} != {want_count}")

    def braced_b_flyer_a(flyer_mass=DRAGON, layer=0, flymode=4, fc=0x77, parent=0):
        def world(rig):
            rig.entity(EA, flyer_mass, 1.0, fc=fc, parent=parent, layer=layer, flymode=flymode)
            rig.entity(EB, *SPEAR)
        return world

    def mass_b(k):
        return f32(f32(f32(SPEAR[0]) * f32(SPEAR[1])) * f32(k))

    k_cave = f32(f32(round(k_def * 100)) / f32(100.0))
    s_cave = f32(f32(round(s_def * 100)) / f32(100.0))
    scaled_b = f32(mass_b(1.0) * k_cave)

    # 1. the flyer A against braced B (r13b): B's mass x k, A's share raised; counted once
    case("A flyer, B braced", braced_b_flyer_a(), 0, 1, 0.1, 1.0,
         want={"XMM1": scaled_b, "XMM12": max(f32(0.1), s_cave)})
    case("A flyer (pegasus, its own share 0.8), B braced", braced_b_flyer_a(PEG), 0, 1, 0.8, 1.0,
         want={"XMM1": scaled_b, "XMM12": max(f32(0.8), s_cave)})
    case("A flyer, share 1.0 above s*", braced_b_flyer_a(), 0, 1, 1.0, 1.0,
         want={"XMM1": scaled_b, "XMM12": f32(1.0)})
    # 2. mirrored: the flyer B against braced A (r12b): A's mass (xmm2) x k, B's share raised
    def flyer_b(rig):
        rig.entity(EA, *SPEAR)
        rig.entity(EB, DRAGON, 1.0, fc=0x77, flymode=4)
    case("B flyer, A braced", flyer_b, 1, 0, 1.0, 0.1,
         want={"XMM2": f32(f32(f32(SPEAR[0]) * f32(SPEAR[1])) * k_cave), "XMM6": max(f32(0.1), s_cave)})
    # 3. the engine did not count the brace (unbraced, side-on, not this step): vanilla exactly
    case("A flyer, brace not counted", braced_b_flyer_a(), 0, 0, 0.1, 1.0)
    case("B flyer, brace not counted", flyer_b, 0, 0, 1.0, 0.1)
    # the braced body is the flyer's own side of the test: B braced but B is the flyer, A ground -> nothing
    def b_flyer_braced(rig):
        rig.entity(EA, *SPEAR)
        rig.entity(EB, DRAGON, 2.0, fc=0x77, flymode=4)
    case("B braced flyer, A ground", b_flyer_braced, 0, 1, 1.0, 0.1)
    # 4. the other body is not a flyer in a landed dive: vanilla exactly
    case("A in the air", braced_b_flyer_a(layer=2), 0, 1, 0.1, 1.0)
    case("A landed, flight movement ended", braced_b_flyer_a(flymode=0), 0, 1, 0.1, 1.0)
    case("A ground charger (no flight controller, no mount)", braced_b_flyer_a(fc=0), 0, 1, 0.1, 1.0)
    # 5. a rider: its mount carries the flight controller and the dive state
    def rider(mount_layer, mount_flymode, mount_fc=0x77):
        def world(rig):
            rig.entity(EA, 100.0, 1.0, parent=EM)
            rig.entity(EM, PEG, 1.0, fc=mount_fc, layer=mount_layer, flymode=mount_flymode)
            rig.entity(EB, *SPEAR)
        return world
    case("A rider on a landed diving mount", rider(0, 4), 0, 1, 0.8, 1.0,
         want={"XMM1": scaled_b, "XMM12": max(f32(0.8), s_cave)})
    case("A rider on a mount in the air", rider(2, 4), 0, 1, 0.8, 1.0)
    case("A rider on a ground mount", rider(0, 4, mount_fc=0), 0, 1, 0.8, 1.0)
    # the chain: 4 links reach a flyer, a 5th does not
    def chain(links):
        def world(rig):
            ents = [EA, EM, EM2, EM3, EM4, EM5][:links + 1]
            for here, up in zip(ents, ents[1:]):
                rig.entity(here, 100.0, 1.0, parent=up)
            rig.entity(ents[-1], DRAGON, 1.0, fc=0x77, flymode=4)
            rig.entity(EB, *SPEAR)
        return world
    case("flyer 3 links up", chain(3), 0, 1, 0.1, 1.0, want={"XMM1": scaled_b, "XMM12": s_cave})
    case("flyer 4 links up (past the chain)", chain(4), 0, 1, 0.1, 1.0)
    # 6. both bodies counted, both flyers in a landed dive: each braced mass scaled, each share raised
    def both(rig):
        rig.entity(EA, DRAGON, 2.0, fc=0x77, flymode=4)
        rig.entity(EB, PEG, 3.0, fc=0x77, flymode=4)
    case("both braced, both flyers", both, 1, 1, 0.1, 1.0,
         want={"XMM2": f32(f32(f32(DRAGON) * f32(2.0)) * k_cave), "XMM12": s_cave,
               "XMM1": f32(f32(f32(PEG) * f32(3.0)) * k_cave), "XMM6": f32(1.0)})
    # 7. the switch: mode 0, word 0, a word with k = 0 -> vanilla exactly
    case("mode 0", braced_b_flyer_a(), 0, 1, 0.1, 1.0, mode=0)
    case("word 0 (switch off)", braced_b_flyer_a(), 0, 1, 0.1, 1.0, word=0)
    case("k part 0", braced_b_flyer_a(), 0, 1, 0.1, 1.0, word=80 << 16)
    # neutral settings (k 1.00, s* 0.00) give the vanilla numbers (counted, nothing else changes)
    case("k 1.00, s* 0.00", braced_b_flyer_a(), 0, 1, 0.1, 1.0, word=air_dive_rules.brace_word(1.0, 0.0),
         counted=1)
    # other settings decode: k 10.00, s* 1.00; k 1.25, s* 0.35
    for k, s in ((10.0, 1.0), (1.25, 0.35)):
        kc = f32(f32(round(k * 100)) / f32(100.0))
        sc = f32(f32(round(s * 100)) / f32(100.0))
        case(f"k {k}, s* {s}", braced_b_flyer_a(), 0, 1, 0.1, 1.0, word=air_dive_rules.brace_word(k, s),
             want={"XMM1": f32(mass_b(1.0) * kc), "XMM12": max(f32(0.1), sc)})
    # 8. the flags the replaced code leaves, whatever came in (ZF / SF / CF / OF / PF set on entry)
    for flags in (0x202, 0x8D7, 0xAC3):
        case(f"entry flags {flags:#x}, scaled", braced_b_flyer_a(), 0, 1, 0.1, 1.0, flags=flags,
             want={"XMM1": scaled_b, "XMM12": s_cave})
        case(f"entry flags {flags:#x}, not counted", braced_b_flyer_a(), 0, 0, 0.1, 1.0, flags=flags)
    # 9. [D64] once per soldier: the flyer's slide entry names the dive, its hit slot remembers the bodies met
    once_n, once_fails = once_cases(code, word_at, count_at, word_def, scaled_b, s_cave)
    n += once_n
    fails += once_fails
    return fails, n


def once_cases(code, word_at, count_at, word, scaled_b, s_cave):
    """[D64] the cave run more than once on one world (a pair touching for several steps): the first meeting of a
    braced body with a landed flyer is scaled, its later steps are the replaced bytes' result exactly."""
    fails, n = [], 0
    slot_of = lambda key: (key >> 4) & (base.SLIDE_SLOTS - 1)  # noqa: E731 -- because the cave hashes the same way
    hit_base = BUF + word_at + HIT_REL

    def u32(rig, at):
        return struct.unpack("<I", bytes(rig.mu.mem_read(at, 4)))[0]

    def u64(rig, at):
        return struct.unpack("<Q", bytes(rig.mu.mem_read(at, 8)))[0]

    def slide(rig, slot, key, x=12.5, z=-40.25):
        rig.mu.mem_write(BUF + base.SLIDE_AT + slot * 16, struct.pack("<Qff", key, x, z))

    def hit(rig, slot, tag, count, ring):
        at = hit_base + slot * HIT_BYTES
        rig.mu.mem_write(at, struct.pack("<QI", tag, count))
        for i, ptr in enumerate(ring):
            rig.mu.mem_write(at + 16 + 8 * i, struct.pack("<Q", ptr))

    def tag_of(x=12.5, z=-40.25):
        return struct.unpack("<Q", struct.pack("<ff", x, z))[0]

    def scenario(label, world, steps, flyer_is_a=True, after=None):
        """``steps``: per run, True = scaled, False = the reference exactly. ``after(rig)`` -> problems."""
        nonlocal n
        n += 1
        rig = Rig(code, word_at, count_at)
        rig.mode(1)
        rig.word(word)
        world(rig)
        xmm2 = struct.unpack("<f", bytes(rig.mu.mem_read(EA + BODY_OFF + MASS, 4)))[0]
        r12b, r13b, sa, sb = (0, 1, 0.1, 1.0) if flyer_is_a else (1, 0, 1.0, 0.1)
        for i, scaled in enumerate(steps):
            rig.regs(r12b, r13b, xmm2, sa, sb, 0x202)
            ref = rig.run(REF)
            rig.regs(r12b, r13b, xmm2, sa, sb, 0x202)
            got = rig.run(CODE)
            if isinstance(ref, str) or isinstance(got, str):
                fails.append(f"{NAME} once {label} step {i}: {ref if isinstance(ref, str) else got}")
                return
            expect = dict(ref)
            if scaled and flyer_is_a:
                expect["XMM1"], expect["XMM12"] = lane(ref["XMM1"], scaled_b), lane(ref["XMM12"], max(f32(0.1), s_cave))
            elif scaled:
                expect["XMM2"] = lane(ref["XMM2"], f32(f32(f32(SPEAR[0]) * f32(SPEAR[1])) * f32(1.0)))
                expect["XMM6"] = lane(ref["XMM6"], max(f32(0.1), s_cave))
            bad = [r for r in expect if got[r] != expect[r]]
            if bad:
                fails.append(f"{NAME} once {label} step {i}: {'scaled' if scaled else 'vanilla'} expected, {bad} differ")
        want = sum(steps)
        if rig.count() != want:
            fails.append(f"{NAME} once {label}: count {rig.count()} != {want}")
        for problem in (after(rig) if after else ()):
            fails.append(f"{NAME} once {label}: {problem}")

    def dragon_a(rig):
        rig.entity(EA, DRAGON, 1.0, fc=0x77, flymode=4)
        rig.entity(EB, *SPEAR)

    sa = slot_of(EA)
    body_b, body_a = EB + BODY_OFF, EA + BODY_OFF

    def remembered(rig):
        at = hit_base + sa * HIT_BYTES
        out = []
        if u64(rig, at) != tag_of():
            out.append(f"tag {u64(rig, at):#x} != the entry's point {tag_of():#x}")
        if u32(rig, at + 8) != 1 or u64(rig, at + 16) != body_b:
            out.append(f"count {u32(rig, at + 8)}, ring[0] {u64(rig, at + 16):#x} (want 1, {body_b:#x})")
        if u32(rig, BUF + word_at + REPEAT_REL) != 0:
            out.append("a repeat counted on a first meeting")
        return out

    def with_entry(key=EA):
        def world(rig):
            dragon_a(rig)
            slide(rig, sa, key)
        return world

    scenario("first meeting scaled and remembered", with_entry(), [True], after=remembered)
    scenario("later steps of the same pair are vanilla", with_entry(), [True, False, False],
             after=lambda rig: [] if u32(rig, BUF + word_at + REPEAT_REL) == 2 else
             [f"repeats {u32(rig, BUF + word_at + REPEAT_REL)} != 2"])
    scenario("a released entry (key | 1) is the same flyer", with_entry(EA | 1), [True, False])

    def old_dive(rig):
        with_entry()(rig)
        hit(rig, sa, tag_of(99.0, 99.0), 1, [body_b])
    scenario("a new dive (another first-hold point) forgets the last one's bodies", old_dive, [True, False],
             after=lambda rig: [] if u32(rig, hit_base + sa * HIT_BYTES + 8) == 1 else
             [f"count after reset {u32(rig, hit_base + sa * HIT_BYTES + 8)} != 1"])

    others = [0x7000_0000 + 0x100 * i for i in range(HIT_RING)]

    def full_ring(rig):
        with_entry()(rig)
        hit(rig, sa, tag_of(), HIT_RING + 4, others)
    scenario("a full ring without the body: scaled, written over the oldest", full_ring, [True, False],
             after=lambda rig: [] if u64(rig, hit_base + sa * HIT_BYTES + 16 + 8 * 4) == body_b else
             [f"ring[4] {u64(rig, hit_base + sa * HIT_BYTES + 16 + 8 * 4):#x} != {body_b:#x}"])

    def full_ring_has(rig):
        with_entry()(rig)
        hit(rig, sa, tag_of(), HIT_RING + 4, others[:7] + [body_b] + others[8:])
    scenario("a full ring holding the body: vanilla", full_ring_has, [False])

    def probed(rig):
        dragon_a(rig)
        slide(rig, sa, 2)                                   # a tombstone at the home slot
        slide(rig, (sa + 1) % base.SLIDE_SLOTS, 0x7123_4560)    # another flyer
        slide(rig, (sa + 2) % base.SLIDE_SLOTS, EA)
    scenario("the entry found past a tombstone and another flyer", probed, [True, False],
             after=lambda rig: [] if u64(rig, hit_base + ((sa + 2) % base.SLIDE_SLOTS) * HIT_BYTES + 16) == body_b
             else ["the body was not remembered in the entry's own hit slot"])
    scenario("no slide entry yet: scaled every step, counted as unremembered", dragon_a, [True, True],
             after=lambda rig: [] if u32(rig, BUF + word_at + NOSLOT_REL) == 2 else
             [f"unremembered {u32(rig, BUF + word_at + NOSLOT_REL)} != 2"])

    def other_body_first(rig):
        with_entry()(rig)
        hit(rig, sa, tag_of(), 1, [0x7AAA_0000])
    scenario("another body met before: this one is still new", other_body_first, [True, False])

    sb_ = slot_of(EB)

    def dragon_b(rig):
        rig.entity(EA, *SPEAR)
        rig.entity(EB, DRAGON, 1.0, fc=0x77, flymode=4)
        slide(rig, sb_, EB)
    scenario("mirrored: the flyer is B, the braced body A", dragon_b, [True, False], flyer_is_a=False,
             after=lambda rig: [] if u64(rig, hit_base + sb_ * HIT_BYTES + 16) == body_a else
             ["A's body was not remembered"])
    return n, fails


MUTANTS = (
    ("mode not checked", f"    cmp dword ptr [rdx + {base.MODE_AT}], 1\n    jne br_out\n", "    nop\n"),
    ("switch word not checked", "    je br_out\n    test r13b, r13b\n", "    nop\n    test r13b, r13b\n"),
    ("scales without the engine's brace (r13b)", "    test r13b, r13b\n    je br_a\n", "    nop\n"),
    ("scales without the engine's brace (r12b)", "    test r12b, r12b\n    je br_out\n", "    nop\n"),
    ("tests the braced body instead of the other", f"    lea rcx, [r14 - {BODY_OFF:#x}]\n",
     f"    lea rcx, [rbx - {BODY_OFF:#x}]\n"),
    ("landed test dropped", f"    cmp dword ptr [rcx + {base.LAYER_OFF:#x}], 0\n    jne fa_no\n", "    nop\n"),
    ("flight-movement test dropped", f"    cmp dword ptr [rcx + {base.FLYMODE_OFF:#x}], 0\n    je fa_no\n",
     "    nop\n"),
    ("mount not followed", f"    mov rcx, qword ptr [rcx + {base.PARENT_OFF:#x}]\n    test rcx, rcx\n    jz fa_no\n",
     "    jmp fa_no\n"),
    ("chain unbounded", "    dec eax\n    jnz fa_chain\n    jmp fa_no\n", "    jmp fa_chain\n"),
    ("share in the wrong register", "    maxss xmm12, xmm0\n", "    maxss xmm6, xmm0\n"),
    ("share lowered (min)", "    maxss xmm12, xmm0\n", "    minss xmm12, xmm0\n"),
    ("k in tenths", f"    push {HUNDRED:#x}\n", "    push 0x41200000\n"),
    ("s* from the k bits", "    shr eax, 16\n    and eax, 0xff\n", "    shr eax, 0\n    and eax, 0xff\n"),
    ("vanilla brace of A dropped", f"    mulss xmm2, dword ptr [r14 + {BRACE:#x}]\n", "    nop\n"),
    ("vanilla brace of B dropped", f"    mulss xmm1, dword ptr [rbx + {BRACE:#x}]\n", "    nop\n"),
    ("xmm0 not restored", "    movdqu xmm0, xmmword ptr [rsp]\n", "    nop\n"),
    ("rcx not restored", "    pop rdx\n    pop rcx\n    pop rax\n", "    pop rdx\n    pop rax\n    pop rax\n"),
    ("flags left by the cave", "    pop rax\n    test r13b, r13b\n", "    pop rax\n    nop\n"),
    ("not counted", "maxss xmm12, xmm0\n    lock inc dword ptr [rdx + ",
     "maxss xmm12, xmm0\n    inc dword ptr [rdx + 4 + "),
    # [D64] once per soldier
    ("never remembers (every step scaled)", "    jne fa_scan\n", "    jmp fa_scan\n"),
    ("an old dive's bodies kept", "    je fa_same\n", "    jmp fa_same\n"),
    ("a released entry not matched", "    and rcx, -2\n", "    nop\n"),
    ("ring index not wrapped", f"    and eax, {HIT_RING - 1}\n", f"    and eax, {2 * HIT_RING - 1}\n"),
    ("body not written to the ring", "    mov qword ptr [r8 + rax*8 + 16], rbx\n", "    nop\n"),
    ("unremembered not counted", "fa_none:\n    lock inc", "fa_none:\n    jmp fa_go\n    lock inc"),
    ("repeat not counted", "    jne fa_scan\n    lock inc dword ptr [rdx + ", "    jne fa_scan\n    inc dword ptr [rdx + 0x100 + "),
    ("mirrored path never remembers", "    jne fb_scan\n", "    jmp fb_scan\n"),
    ("probe stops at a tombstone", "    test rcx, rcx\n    je fa_none\n    and rcx, -2\n",
     "    cmp rcx, 2\n    je fa_none\n    test rcx, rcx\n    je fa_none\n    and rcx, -2\n"),
)


def negative_controls(word_at, count_at):
    survivors = []
    src = source(word_at, count_at)
    for label, old, new in MUTANTS:
        if src.count(old) < 1:
            raise SystemExit(f"[dive_brace_asm] REFUSING: mutant {label!r} does not apply")
        f, _n = check(assemble(word_at, count_at, src.replace(old, new, 1)), word_at, count_at)
        if not f:
            survivors.append(label)
    return survivors


def main():
    import dive_cost_asm
    w, c = dive_cost_asm.BRACE_WORD_AT, dive_cost_asm.BRACE_COUNT_AT
    code = assemble(w, c)
    fails, n = check(code, w, c)
    if fails:
        raise SystemExit("[dive_brace_asm] emulator check FAILED:\n  " + "\n  ".join(fails[:40]))
    survivors = negative_controls(w, c)
    if survivors:
        raise SystemExit(f"[dive_brace_asm] REFUSING: mutants passed every case: {survivors}")
    print(f"[dive_brace_asm] {NAME} {len(code)} B; {n} emulator cases against the replaced bytes; "
          f"{len(MUTANTS)} mutants each caught")


if __name__ == "__main__":
    main()
