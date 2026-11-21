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
{_flyer("fa")}{_part(0, 0xFFFF)}    mulss xmm1, xmm0
{_part(16, 0xFF)}    maxss xmm12, xmm0
    lock inc dword ptr [rdx + COUNT]
fa_no:
br_a:
    test r12b, r12b
    je br_out
    lea rcx, [rbx - {BODY_OFF:#x}]
{_flyer("fb")}{_part(0, 0xFFFF)}    mulss xmm2, xmm0
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
    return s.replace("+ WORD]", f"+ {word_at:#x}]").replace("+ COUNT]", f"+ {count_at:#x}]")


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
BUF_SIZE = 0x4000
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
         want={"XMM1": scaled_b, "XMM12": f32(0.8)})
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
         want={"XMM1": scaled_b, "XMM12": f32(0.8)})
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
    return fails, n


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
    ("not counted", "    lock inc dword ptr [rdx + ", "    inc dword ptr [rdx + 4 + "),
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
