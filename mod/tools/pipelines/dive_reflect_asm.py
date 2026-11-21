"""[D51] ``dv_reflect``: Charge Reflection hits a flyer harder, inside the engine's own reflection multiply.
Shipped through dive_cost_asm.py, which writes the dive site table with this cave in it (same feature, same buffer,
layout offsets passed in from there). It replaces D15's dive cost (``dv_cost``, removed by D51).

What the cave reads is what the engine itself uses, read from Warhammer3.exe 9.0.5 (6ae2a00b):
* the site: the melee damage calculator 0x142e5fcb0, the block 0x142e6004c..0x142e600af
  (docs/research/2026-11-20-brace-collision-reading.md section E). xmm7 = kv charge_reflect_damage_multiplier
  ([r12 + 0x6670], 2.0); the block reaches the multiply only when every engine gate held: target->vfunc[0x48],
  the striker's charge_reflection attribute (source->vfunc[0x38]), target->vfunc[+8] non-null, the striker braced
  (source->vfunc[0x50], else it jumps to 0x142e600b4, past the multiply), and the target entity's charge factor
  (0x143065f3c) at least kv charge_reflect_min_charge_factor_threshold (0.7, else 0x142e6028a). Then
  ``mulss xmm8, xmm7`` (F3 44 0F 59 C7) at 0x142e600af; the next instruction ``test bpl, bpl`` sets the flags
  itself. Nothing branches to 0x142e600b0..0x142e600b3 (the function's disassembly, d_fn_142e5fcb0_damage.txt).
* the target: rdi, the participant being hit (the charger; HISTORY 1993 matched it in game by pointer), still live
  there (callee-saved). Its entity is what rdi->vfunc[+8] returns, the getter the engine itself calls on rdi three
  times in this block; for the participant vtable 0x143ae0278 it is 0x1408d9b70 ``mov rax, [rcx + 8]; ret``. The
  cave calls the getter rather than reading [rdi + 8], so a participant of another class is read its own way.
* the flyer: that entity, or the entity it rides (+0x2e0, at most 4 links: dv_brace's chain), carries a flight
  controller (+0x128 not 0). No dive state is tested (D51: flyers only, landed dive or not).

The cave: does what the 5 bytes do (``mulss xmm8, xmm7``); then, when mode is 1 and the factor word is not 0 and
the target is a flyer: xmm8 x (word / 100), counted (lock inc). Every register but xmm8, every other xmm register
and the flags are what the replaced bytes leave; the getter is called with a 16-byte aligned stack and 32 bytes of
shadow space, with rax / rcx / rdx / r8-r11 and xmm0-xmm5 (the volatile ones) saved around it. It returns through
push / ret (no register).

``python dive_reflect_asm.py`` (keystone + unicorn) assembles and runs the emulator check against the replaced bytes
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
from dive_brace_asm import f32, fbits, lane  # noqa: E402 -- same reason (pipelines/)

NAME = "dv_reflect"
SITE = "E8 ?? ?? ?? ?? 0F 2F C6 0F 82 ?? ?? ?? ?? F3 44 0F 59 C7 40 84 ED 74 12"
AT = 14
STOLEN = "F3 44 0F 59 C7"
REPLACED = bytes.fromhex("F3440F59C7")
EXE_SITE = 0x142E600AF
CHAIN = 4                            # links followed through +0x2e0 (dv_brace's depth)
HUNDRED = 0x42C80000                 # 100.0f
XMM_SAVED = 6                        # xmm0..xmm5, the volatile ones the getter may change
FRAME = 32 + 16 * XMM_SAVED          # shadow space + the saved xmm registers
assert len(REPLACED) == len(bytes.fromhex(STOLEN.replace(" ", "")))
assert SITE.replace(" ", "")[2 * AT:].upper().startswith(STOLEN.replace(" ", ""))


def source(word_at, count_at):
    save = "".join(f"    movdqa xmmword ptr [rsp + {32 + 16 * i}], xmm{i}\n" for i in range(XMM_SAVED))
    load = "".join(f"    movdqa xmm{i}, xmmword ptr [rsp + {32 + 16 * i}]\n" for i in range(XMM_SAVED))
    s = f"""
    mulss xmm8, xmm7
    pushfq
    push rax
    push rcx
    push rdx
    push r8
    push r9
    push r10
    push r11
    push rbx
    mov rdx, {base.BUF_PLACEHOLDER:#x}
    cmp dword ptr [rdx + {base.MODE_AT}], 1
    jne rf_out
    cmp dword ptr [rdx + WORD], 0
    je rf_out
    test rdi, rdi
    jz rf_out
    mov rbx, rsp
    and rsp, -16
    sub rsp, {FRAME}
{save}    mov rcx, rdi
    mov rax, qword ptr [rdi]
    call qword ptr [rax + 8]
{load}    mov rsp, rbx
    mov rdx, {base.BUF_PLACEHOLDER:#x}
    test rax, rax
    jz rf_out
    mov ecx, {CHAIN}
rf_chain:
    cmp qword ptr [rax + {base.FC_OFF:#x}], 0
    jne rf_fly
    mov rax, qword ptr [rax + {base.PARENT_OFF:#x}]
    test rax, rax
    jz rf_out
    dec ecx
    jnz rf_chain
    jmp rf_out
rf_fly:
    lea rsp, [rsp - 16]
    movdqu xmmword ptr [rsp], xmm0
    mov eax, dword ptr [rdx + WORD]
    cvtsi2ss xmm0, eax
    push {HUNDRED:#x}
    divss xmm0, dword ptr [rsp]
    lea rsp, [rsp + 8]
    mulss xmm8, xmm0
    movdqu xmm0, xmmword ptr [rsp]
    lea rsp, [rsp + 16]
    lock inc dword ptr [rdx + COUNT]
rf_out:
    pop rbx
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdx
    pop rcx
    pop rax
    popfq
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
    if code.count(struct.pack("<Q", base.RESUME_PLACEHOLDER)) != 1:
        raise SystemExit(f"[dive_reflect_asm] REFUSING: the resume placeholder is not in {NAME} exactly once")
    if code.count(struct.pack("<Q", base.BUF_PLACEHOLDER)) < 1:
        raise SystemExit(f"[dive_reflect_asm] REFUSING: the buffer placeholder is not in {NAME}")
    return code


# --- emulator: the cave against the replaced bytes themselves ----------------------------------------------
CODE, REF, RESUME, BUF, STACK, OBJ, FN = 0x100000, 0x110000, 0x120000, 0x200000, 0x400000, 0x500000, 0x600000
PART, VTBL = OBJ + 0x100, OBJ + 0x200
EA, EM, EM2, EM3, EM4, EM5 = (OBJ + 0x1000 * i for i in range(1, 7))
BUF_SIZE = 0x4000
GPRS = ("RAX", "RBX", "RCX", "RDX", "RSI", "RDI", "RBP", "RSP", "R8", "R9", "R10", "R11", "R12", "R13", "R14",
        "R15", "EFLAGS")
STEPS = 4000
# getters the vtable's +8 can point at
GET_PLAIN = bytes.fromhex("488B4108C3")                         # mov rax, [rcx + 8]; ret (0x1408d9b70)
# the same after trashing every volatile register, and faulting (ud2) when entered with a misaligned stack
GET_HARSH = bytes.fromhex(
    "4889E0"            # mov rax, rsp
    "83E00F"            # and eax, 0xf
    "83F808"            # cmp eax, 8
    "7402"              # je +2
    "0F0B"              # ud2
    "4C8B4108"          # mov r8, [rcx + 8]
    "48C7C2EFBEADDE"    # mov rdx, 0xffffffffdeadbeef
    "49C7C1EFBEADDE"    # mov r9, ...
    "49C7C2EFBEADDE"    # mov r10, ...
    "49C7C3EFBEADDE"    # mov r11, ...
    "48C7C1EFBEADDE"    # mov rcx, ...
    "4889542408"        # mov [rsp + 8], rdx: the callee's own shadow space, written as a callee may
    "4889542410"        # mov [rsp + 16], rdx
    "4889542418"        # mov [rsp + 24], rdx
    "4889542420"        # mov [rsp + 32], rdx
    + "".join(f"660F6E{0xC2 + 8 * i:02X}" for i in range(6))     # movd xmm0..xmm5, edx
    + "4C89C0"          # mov rax, r8
    "4885C0"            # test rax, rax (flags changed too)
    "C3")               # ret
GET_NULL = bytes.fromhex("31C0C3")                              # xor eax, eax; ret
GETTERS = {"plain": FN, "harsh": FN + 0x100, "null": FN + 0x200}


class Rig:
    """One machine with the cave at CODE and the replaced bytes at REF, both returning to RESUME; the same world
    (participant, its vtable and getter, entities, buffer) for both. run(at) runs from CODE or REF."""

    def __init__(self, code, word_at, count_at):
        from unicorn import UC_HOOK_CODE
        from unicorn import x86_const as X
        self.X, self.word_at, self.count_at = X, word_at, count_at
        mu = self.mu = base._uc()
        for at, size in ((CODE, 0x2000), (REF, 0x1000), (RESUME, 0x1000), (BUF, BUF_SIZE), (STACK, 0x10000),
                         (OBJ, 0x10000), (FN, 0x1000)):
            mu.mem_map(at, size)
        mu.mem_write(CODE, base._fill(code, BUF, RESUME))
        mu.mem_write(REF, REPLACED + b"\xE9" + struct.pack("<i", RESUME - (REF + len(REPLACED) + 5)))
        mu.mem_write(RESUME, b"\x90" * 16)
        for name, at in GETTERS.items():
            mu.mem_write(at, {"plain": GET_PLAIN, "harsh": GET_HARSH, "null": GET_NULL}[name])
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

    def participant(self, entity, getter="plain"):
        self.mu.mem_write(PART, struct.pack("<QQ", VTBL, entity))
        self.mu.mem_write(VTBL, struct.pack("<QQ", 0, GETTERS[getter]))

    def entity(self, ent, fc=0, parent=0):
        self.mu.mem_write(ent + base.FC_OFF, struct.pack("<Q", fc))
        self.mu.mem_write(ent + base.PARENT_OFF, struct.pack("<Q", parent))

    def regs(self, xmm8, mult, flags, rsp_low, rdi=PART):
        X = self.X
        vals = {"RAX": 0x1111, "RBX": 0x2222, "RCX": 0x3333, "RDX": 0x4444, "RSI": 0x5501, "RDI": rdi,
                "RBP": 0x7701, "R8": 0x20000, "R9": 0x9999, "R10": 0xAAAA, "R11": 0xBBBB, "R12": 0xC0C0,
                "R13": 0xD0D0, "R14": 0xE0E0, "R15": 0xF0F0F001}
        for name, v in vals.items():
            self.mu.reg_write(getattr(X, f"UC_X86_REG_{name}"), v)
        self.mu.reg_write(X.UC_X86_REG_RSP, STACK + 0x8000 + rsp_low)
        self.mu.reg_write(X.UC_X86_REG_EFLAGS, flags)
        for i in range(16):
            self.mu.reg_write(getattr(X, f"UC_X86_REG_XMM{i}"),
                              (0x0102030405060708_090A0B0C << 32) * (i + 1) & ((1 << 128) - 1) | fbits(1.5 + i))
        self.mu.reg_write(X.UC_X86_REG_XMM8, (0xAB << 64) | fbits(xmm8))
        self.mu.reg_write(X.UC_X86_REG_XMM7, (0xCD << 64) | fbits(mult))

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
        rsp = state["RSP"]
        state["stack"] = bytes(self.mu.mem_read(rsp, 64))
        return state


def check(code, word_at, count_at):
    """dv_reflect on synthetic calls against the replaced bytes -> (fails, cases). Every case runs the reference
    (the 5 bytes) and the cave from the same state; the cave's end state must equal the reference's except, in the
    cases that scale, xmm8, which must equal the reference's xmm8 x (word / 100) as float32 arithmetic does it."""
    word_def = air_dive_rules.reflect_word(air_dive_rules.REFLECT_FLYER_FACTOR)
    fails, n = [], 0

    def case(label, world, word=word_def, mode=1, scaled=False, flags=0x202, getter="plain", rsp_low=0,
             xmm8=37.5, mult=2.0, rdi=PART):
        nonlocal n
        n += 1
        rig = Rig(code, word_at, count_at)
        rig.mode(mode)
        rig.word(word)
        ent = world(rig)
        rig.participant(ent, getter)
        rig.regs(xmm8, mult, flags, rsp_low, rdi)
        ref = rig.run(REF)
        rig.regs(xmm8, mult, flags, rsp_low, rdi)
        got = rig.run(CODE)
        if isinstance(ref, str) or isinstance(got, str):
            fails.append(f"{NAME} {label}: ref {ref if isinstance(ref, str) else 'ok'} / cave "
                         f"{got if isinstance(got, str) else 'ok'}")
            return
        expect = dict(ref)
        if scaled:
            factor = f32(f32(float(word)) / f32(100.0))
            ref_low = struct.unpack("<f", struct.pack("<I", ref["XMM8"] & 0xFFFFFFFF))[0]
            expect["XMM8"] = lane(ref["XMM8"], f32(ref_low * factor))
        bad = {r: (hex(got[r]) if isinstance(got[r], int) else got[r], hex(expect[r]) if isinstance(expect[r], int)
                   else expect[r]) for r in expect if got[r] != expect[r]}
        if bad:
            fails.append(f"{NAME} {label}: {bad}")
        if rig.count() != (1 if scaled else 0):
            fails.append(f"{NAME} {label}: count {rig.count()} != {1 if scaled else 0}")

    def flyer(rig):
        rig.entity(EA, fc=0x77)
        return EA

    def ground(rig):
        rig.entity(EA)
        return EA

    def rider(mount_fc):
        def world(rig):
            rig.entity(EA, parent=EM)
            rig.entity(EM, fc=mount_fc)
            return EA
        return world

    def chain(links):
        def world(rig):
            ents = [EA, EM, EM2, EM3, EM4, EM5][:links + 1]
            for here, up in zip(ents, ents[1:]):
                rig.entity(here, parent=up)
            rig.entity(ents[-1], fc=0x77)
            return EA
        return world

    # 1. a flyer charger hit by Charge Reflection: the engine's x2, then x factor; counted once
    case("flyer", flyer, scaled=True)
    case("flyer, other damage factor", flyer, scaled=True, xmm8=0.8125, mult=2.0)
    case("flyer, kv multiplier 3", flyer, scaled=True, mult=3.0)
    # 2. riders: the mount carries the flight controller
    case("rider on a flying mount", rider(0x77), scaled=True)
    case("rider on a ground mount", rider(0))
    case("flyer 3 links up", chain(3), scaled=True)
    case("flyer 4 links up (past the chain)", chain(4))
    # 3. not a flyer, or no entity: the engine's result exactly
    case("ground charger", ground)
    case("getter returns 0", flyer, getter="null")
    case("participant 0", flyer, rdi=0)
    # 4. the switch: mode 0, word 0 -> vanilla
    case("mode 0", flyer, mode=0)
    case("mode 2", flyer, mode=2)
    case("word 0 (switch off)", flyer, word=0)
    # neutral factor 1.00: counted, the value the engine's own
    case("factor 1.00", flyer, word=air_dive_rules.reflect_word(1.0), scaled=True)
    for factor in (1.25, 2.5, 4.0):
        case(f"factor {factor}", flyer, word=air_dive_rules.reflect_word(factor), scaled=True)
    # 5. the getter's world: it trashes every volatile register and faults on a misaligned stack; the cave's
    #    result is the same from any entry alignment
    for low in (0, 8):
        case(f"harsh getter, flyer, rsp low {low}", flyer, getter="harsh", rsp_low=low, scaled=True)
        case(f"harsh getter, ground, rsp low {low}", ground, getter="harsh", rsp_low=low)
    # 6. the flags the replaced code leaves (it changes none), whatever came in
    for flags in (0x202, 0x8D7, 0xAC3):
        case(f"entry flags {flags:#x}, scaled", flyer, flags=flags, scaled=True)
        case(f"entry flags {flags:#x}, ground", ground, flags=flags)
        case(f"entry flags {flags:#x}, harsh getter", flyer, flags=flags, getter="harsh", scaled=True)
    return fails, n


MUTANTS = (
    ("engine multiply dropped", "    mulss xmm8, xmm7\n    pushfq\n", "    pushfq\n"),
    ("mode not checked", f"    cmp dword ptr [rdx + {base.MODE_AT}], 1\n    jne rf_out\n", "    nop\n"),
    ("switch word not checked", "    je rf_out\n    test rdi, rdi\n", "    nop\n    test rdi, rdi\n"),
    ("participant not null-checked", "    test rdi, rdi\n    jz rf_out\n", "    nop\n"),
    ("stack not aligned", "    and rsp, -16\n", "    nop\n"),
    ("no shadow space kept", f"    sub rsp, {FRAME}\n", f"    sub rsp, {FRAME - 32}\n"),
    ("getter result not null-checked", "    test rax, rax\n    jz rf_out\n    mov ecx", "    nop\n    mov ecx"),
    ("reads [rdi + 8] without the getter", "    mov rax, qword ptr [rdi]\n    call qword ptr [rax + 8]\n",
     "    mov rax, qword ptr [rdi + 8]\n    nop\n"),
    ("mount not followed", f"    mov rax, qword ptr [rax + {base.PARENT_OFF:#x}]\n    test rax, rax\n    jz rf_out\n",
     "    jmp rf_out\n"),
    ("chain unbounded", "    dec ecx\n    jnz rf_chain\n    jmp rf_out\n", "    jmp rf_chain\n"),
    ("flight controller not tested", f"    cmp qword ptr [rax + {base.FC_OFF:#x}], 0\n    jne rf_fly\n",
     "    jmp rf_fly\n"),
    ("factor in tenths", f"    push {HUNDRED:#x}\n", "    push 0x41200000\n"),
    ("factor added, not multiplied", "    mulss xmm8, xmm0\n", "    addss xmm8, xmm0\n"),
    ("xmm0 not restored after the factor", "    movdqu xmm0, xmmword ptr [rsp]\n", "    nop\n"),
    ("xmm3 not restored after the call", "    movdqa xmm3, xmmword ptr [rsp + 80]\n", "    nop\n"),
    ("buffer pointer not reloaded after the call",
     f"    mov rsp, rbx\n    mov rdx, {base.BUF_PLACEHOLDER:#x}\n", "    mov rsp, rbx\n    nop\n"),
    ("rbx not restored", "    pop rbx\n    pop r11\n", "    pop r11\n    pop r11\n"),
    ("flags not restored", "    pop rax\n    popfq\n", "    pop rax\n    add rsp, 8\n"),
    ("not counted", "    lock inc dword ptr [rdx + ", "    inc dword ptr [rdx + 4 + "),
)


def negative_controls(word_at, count_at):
    survivors = []
    src = source(word_at, count_at)
    for label, old, new in MUTANTS:
        if src.count(old) < 1:
            raise SystemExit(f"[dive_reflect_asm] REFUSING: mutant {label!r} does not apply")
        f, _n = check(assemble(word_at, count_at, src.replace(old, new, 1)), word_at, count_at)
        if not f:
            survivors.append(label)
    return survivors


def main():
    import dive_cost_asm
    w, c = dive_cost_asm.REFLECT_WORD_AT, dive_cost_asm.REFLECT_COUNT_AT
    code = assemble(w, c)
    fails, n = check(code, w, c)
    if fails:
        raise SystemExit("[dive_reflect_asm] emulator check FAILED:\n  " + "\n  ".join(fails[:40]))
    survivors = negative_controls(w, c)
    if survivors:
        raise SystemExit(f"[dive_reflect_asm] REFUSING: mutants passed every case: {survivors}")
    print(f"[dive_reflect_asm] {NAME} {len(code)} B; {n} emulator cases against the replaced bytes; "
          f"{len(MUTANTS)} mutants each caught")


if __name__ == "__main__":
    main()
