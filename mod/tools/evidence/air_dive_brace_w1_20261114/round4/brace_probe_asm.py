"""TEST-ONLY (AIR-DIVE-BRACE-W1): the AIR-DIVE-RELEASE-W1 repath / action-start loggers
plus a logger at the entry of the impact reflection 0x1430afae4 (braced soldier's melee
roll back at a charger; caller 0x14325bf46). Entry: rcx ctx, rdx out, r8 reflector,
r9 charger, [rsp+0x28] closing speed (float). Logged only when r8 or r9 (or its mount)
has a flight controller: u64 r8, u64 r9, u32 seq, u32 kind=3, f32 speed, u64 return,
u32 r9 +0x26c, f32 r9 vx, f32 r9 vz, u32 r9 slot, u32 r8 +0x68 (byte), u32 r8 +0x6c, f32 r8 +0xbc.

Original docstring follows.
logger cave at the entry of 0x14307b4b0 (stop flight + re-path).

AIR-DIVE-RELEASE-W1 2026-11-13. 0x14307b4b0(rcx entity, rdx, xmm2, r9d):
calls 0x14307a29c, then stop flight 0x14307e438(rcx, 0), then tail-jumps to
0x143125b54 (re-path). 22 call sites. For every call on an entity with a
flight controller (+0x128) it appends a 512-byte entry: u64 entity, u64
return address, u32 seq, u32 +0x26c, F32 vx, F32 vz, u32 +0x710, u32
+0x104, u32 r9d, u32 xmm2 bits, u64 rdx, u32 slot +0x278, pad; then the 256
bytes of stack at entry (rsp .. rsp+0x100) so the caller's caller can be
found offline. Registers and flags unchanged (Unicorn check below).
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATTERN = "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 30 48 8B 01 41 8B F9 0F 29 74 24 20 48 8B F2"
STOLEN = "48 89 5C 24 08 48 89 74 24 10"
COUNT_AT, MODE_AT, MAGIC_AT, RING_AT = 0, 4, 8, 64
MAGIC = b"LDBRPRB1"
SLOTS, ENTRY = 1024, 512
ACT_COUNT_AT, ACT_SLOTS, ACT_ENTRY = 16, 4096, 64
ACT_RING_AT = RING_AT + SLOTS * ENTRY
REFL_COUNT_AT, REFL_SLOTS, REFL_ENTRY = 20, 2048, 64
REFL_RING_AT = ACT_RING_AT + ACT_SLOTS * ACT_ENTRY
MEL_COUNT_AT, MEL_SLOTS, MEL_ENTRY = 24, 256, 512
MEL_RING_AT = REFL_RING_AT + REFL_SLOTS * REFL_ENTRY
ORD_COUNT_AT, ORD_SLOTS, ORD_ENTRY = 28, 256, 512
ORD_RING_AT = MEL_RING_AT + MEL_SLOTS * MEL_ENTRY
GSET_COUNT_AT, GSET_SLOTS, GSET_ENTRY = 32, 256, 512
GSET_RING_AT = ORD_RING_AT + ORD_SLOTS * ORD_ENTRY
STAG_COUNT_AT, STAG_SLOTS, STAG_ENTRY = 36, 256, 512
STAG_RING_AT = GSET_RING_AT + GSET_SLOTS * GSET_ENTRY
# [round 4] landing abort 0x14304cea0 (flight controller in rcx; phase +0x90 4/5 -> 6 go-around)
ABRT_COUNT_AT, ABRT_SLOTS, ABRT_ENTRY = 40, 256, 512
ABRT_RING_AT = STAG_RING_AT + STAG_SLOTS * STAG_ENTRY
ABRT_PATTERN = "40 53 48 83 EC 20 48 8B D9 48 83 C1 78 E8 66 81 FD FF"
ABRT_STOLEN = "40 53 48 83 EC 20 48 8B D9"
BYTES = ABRT_RING_AT + ABRT_SLOTS * ABRT_ENTRY
# [round 2] stop-at-point 0x1431341b0 (3 callers: 0x14308d162, 0x143098cd1, 0x1430bb1bb) and the
# vfunc 0x143098b04 that holds the 0x143098cd1 call (37 vtable refs)
GSET_PATTERN = "48 89 5C 24 08 57 48 83 EC 20 80 B9 28 02 00 00 01 48 8B F9 74 7F 33 C0"
GSET_STOLEN = "48 89 5C 24 08 57 48 83 EC 20"
STAG_PATTERN = "48 8B C4 48 89 58 10 48 89 68 18 48 89 70 20 57 41 54 41 55 41 56 41 57 48 81 EC 80 00 00 00 83"
STAG_STOLEN = "48 8B C4 48 89 58 10 48 89 68 18"
ORD_PATTERN = "48 83 EC 28 4D 8B C8 4C 8B D1 E8 39 54 E0 FF 48 8D 0D 9A 81 89 00"
ORD_STOLEN = "48 83 EC 28 4D 8B C8 4C 8B D1"
# melee order constructor 0x14305abb4 (vtable 0x143ade470), only caller 0x143075eb8 inside
# 0x143075dd8 (rcx = entity + 0x330, the inline order slot)
MEL_PATTERN = "40 53 48 83 EC 20 4D 8B D8 48 8B D9 45 8A 40 22 E8 0F 01 00 00 48 8D 05"
MEL_STOLEN = "40 53 48 83 EC 20 4D 8B D8 48 8B D9"
REFL_PATTERN = ("48 8B C4 48 89 58 08 48 89 68 10 48 89 70 18 48 89 78 20 41 56 48 81 EC 40 01 00 00 "
                "0F 29 70 E8 48 8B F9 48 8B 41 08")
REFL_STOLEN = "48 8B C4 48 89 58 08 48 89 68 10"
ACT_SITES = (
    ("rp_act1", 1, "48 89 5C 24 10 48 89 6C 24 18 48 89 74 24 20 57 48 83 EC 40 41 F6 40 0A 04 49 8B F0 0F B7 EA 48 8B F9",
     "48 89 5C 24 10 48 89 6C 24 18"),
    ("rp_act2", 2, "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 48 83 EC 20 80 7C 24 50 00 41 8A F1 41 8B E8 0F B7 FA 48 8B D9",
     "48 89 5C 24 08 48 89 6C 24 10"),
)


def act_source(kind):
    flag = "movzx eax, byte ptr [r8 + 10]" if kind == 1 else "mov eax, r8d"
    return f"""
    pushfq
    push rax
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    movzx eax, dx
    cmp eax, 484
    jb chk_fly
    cmp eax, 493
    jbe logit
chk_fly:
    cmp eax, 102
    jb done
    cmp eax, 105
    ja done
    mov rax, qword ptr [rcx + 0x128]
    test rax, rax
    jne logit
    mov rax, qword ptr [rcx + 0x2e0]
    test rax, rax
    je done
    mov rax, qword ptr [rax + 0x128]
    test rax, rax
    je done
logit:
    mov eax, 1
    lock xadd dword ptr [r10 + {ACT_COUNT_AT}], eax
    mov r11d, eax
    and r11d, {ACT_SLOTS - 1}
    shl r11, 6
    lea r11, [r10 + r11 + {ACT_RING_AT}]
    mov qword ptr [r11], rcx
    mov dword ptr [r11 + 16], eax
    mov rax, qword ptr [rsp + 32]
    mov qword ptr [r11 + 8], rax
    mov dword ptr [r11 + 20], {kind}
    movzx eax, dx
    mov dword ptr [r11 + 24], eax
    mov eax, dword ptr [rcx + 0x26c]
    mov dword ptr [r11 + 28], eax
    mov eax, dword ptr [rcx + 0xe0]
    mov dword ptr [r11 + 32], eax
    mov eax, dword ptr [rcx + 0xe8]
    mov dword ptr [r11 + 36], eax
    mov rax, qword ptr [rcx + 0x128]
    mov dword ptr [r11 + 40], eax
    {flag}
    mov dword ptr [r11 + 44], eax
    mov eax, dword ptr [rcx + 0x278]
    mov dword ptr [r11 + 48], eax
    mov eax, dword ptr [rcx + 0x104]
    mov dword ptr [r11 + 52], eax
    mov rax, qword ptr [rcx + 0x2e0]
    mov qword ptr [r11 + 56], rax
done:
    pop r11
    pop r10
    pop rax
    popfq
"""
BUF = 0x1122334455667788


def ord_source():
    return mel_source().replace(f"[r10 + {MEL_COUNT_AT}]", f"[r10 + {ORD_COUNT_AT}]") \
        .replace(f"and r11d, {MEL_SLOTS - 1}", f"and r11d, {ORD_SLOTS - 1}") \
        .replace(f"add r11, {MEL_RING_AT}", f"add r11, {ORD_RING_AT}")


def check_ord(code):
    g = globals()
    saved = (g["MEL_COUNT_AT"], g["MEL_SLOTS"], g["MEL_RING_AT"])
    g["MEL_COUNT_AT"], g["MEL_SLOTS"], g["MEL_RING_AT"] = ORD_COUNT_AT, ORD_SLOTS, ORD_RING_AT
    try:
        return check_mel(code)
    finally:
        g["MEL_COUNT_AT"], g["MEL_SLOTS"], g["MEL_RING_AT"] = saved


def mel_source():
    """Same entry shape as the repath logger (512 B: entity, return, seq, +0x26c, vx, vz, +0x710,
    +0x104, u32 [r8], u32 [r8+4], u64 r8, u32 slot, pad, 48 stack qwords); entity = rcx - 0x330."""
    stack = "\n".join(f"    mov rax, qword ptr [rsp + {32 + 8 * i}]\n    mov qword ptr [r11 + {64 + 8 * i}], rax"
                      for i in range(48))
    return f"""
    pushfq
    push rax
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    mov r11, rcx
    sub r11, 0x330
    mov rax, qword ptr [r11 + 0x128]
    test rax, rax
    jne logit
    mov rax, qword ptr [r11 + 0x2e0]
    test rax, rax
    je done
    mov rax, qword ptr [rax + 0x128]
    test rax, rax
    je done
logit:
    mov eax, 1
    lock xadd dword ptr [r10 + {MEL_COUNT_AT}], eax
    mov r11d, eax
    and r11d, {MEL_SLOTS - 1}
    shl r11, 9
    add r11, r10
    add r11, {MEL_RING_AT}
    mov dword ptr [r11 + 16], eax
    lea rax, [rcx - 0x330]
    mov qword ptr [r11], rax
    mov rax, qword ptr [rsp + 32]
    mov qword ptr [r11 + 8], rax
    mov eax, dword ptr [rcx - 0x330 + 0x26c]
    mov dword ptr [r11 + 20], eax
    mov eax, dword ptr [rcx - 0x330 + 0xe0]
    mov dword ptr [r11 + 24], eax
    mov eax, dword ptr [rcx - 0x330 + 0xe8]
    mov dword ptr [r11 + 28], eax
    mov eax, dword ptr [rcx - 0x330 + 0x710]
    mov dword ptr [r11 + 32], eax
    mov eax, dword ptr [rcx - 0x330 + 0x104]
    mov dword ptr [r11 + 36], eax
    mov eax, dword ptr [r8]
    mov dword ptr [r11 + 40], eax
    mov eax, dword ptr [r8 + 4]
    mov dword ptr [r11 + 44], eax
    mov qword ptr [r11 + 48], r8
    mov eax, dword ptr [rcx - 0x330 + 0x278]
    mov dword ptr [r11 + 56], eax
{stack}
done:
    pop r11
    pop r10
    pop rax
    popfq
"""


def check_mel(code):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
    from unicorn import x86_const as X
    CODE, B, STACK, OBJ = 0x100000, 0x200000, 0x400000, 0x500000
    fails = []
    for mode, flyer, mount, want in ((1, True, False, True), (1, False, True, True), (1, False, False, False),
                                     (0, True, False, False), (1, False, "nofc", False)):
        mu = Uc(UC_ARCH_X86, UC_MODE_64)
        mu.mem_map(CODE, 0x2000)
        mu.mem_map(B, (BYTES + 0xfff) & ~0xfff)
        mu.mem_map(STACK, 0x10000)
        mu.mem_map(OBJ, 0x10000)
        mu.mem_write(CODE, code.replace(struct.pack("<Q", BUF), struct.pack("<Q", B)))
        ent, par, prm = OBJ + 0x1000, OBJ + 0x6000, OBJ + 0x8000
        mu.mem_write(ent + 0x128, struct.pack("<Q", 0x77 if flyer else 0))
        mu.mem_write(ent + 0x2e0, struct.pack("<Q", par if mount else 0))
        mu.mem_write(par + 0x128, struct.pack("<Q", 0 if mount == "nofc" else 0x55))
        mu.mem_write(ent + 0x26c, struct.pack("<i", 33))
        mu.mem_write(ent + 0xe0, struct.pack("<fff", 1.0, 0.0, -9.0))
        mu.mem_write(ent + 0x710, struct.pack("<i", 4))
        mu.mem_write(ent + 0x278, struct.pack("<I", 1))
        mu.mem_write(prm, struct.pack("<II", 7, 9))
        mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
        mu.mem_write(B + MEL_COUNT_AT, struct.pack("<I", MEL_SLOTS + 2))
        rsp = STACK + 0x4000
        mu.mem_write(rsp, struct.pack("<Q", 0x143075EBD) + bytes(range(8, 256)) + bytes(256))
        vals = {X.UC_X86_REG_RAX: 0xAAAA, X.UC_X86_REG_RCX: ent + 0x330, X.UC_X86_REG_RDX: ent + 0x328,
                X.UC_X86_REG_R8: prm, X.UC_X86_REG_R10: 0x1010, X.UC_X86_REG_R11: 0x1111,
                X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_EFLAGS: 0x246}
        for r, v in vals.items():
            mu.reg_write(r, v)
        mu.emu_start(CODE, CODE + len(code))
        changed = [r for r in vals if mu.reg_read(r) != vals[r]]
        cnt = struct.unpack("<I", bytes(mu.mem_read(B + MEL_COUNT_AT, 4)))[0] - (MEL_SLOTS + 2)
        e = bytes(mu.mem_read(B + MEL_RING_AT + 2 * MEL_ENTRY, MEL_ENTRY))
        if changed:
            fails.append(f"mel {mode, flyer, mount}: changed {changed}")
        if want:
            got = struct.unpack_from("<QQIiffiiIIQI", e, 0)
            if cnt != 1 or got != (ent, 0x143075EBD, MEL_SLOTS + 2, 33, 1.0, -9.0, 4, 0, 7, 9, prm, 1) \
                    or e[64:72] != struct.pack("<Q", 0x143075EBD) or e[72:80] != bytes(range(8, 16)):
                fails.append(f"mel {mode, flyer, mount}: entry {got} count {cnt}")
        elif cnt or any(e):
            fails.append(f"mel {mode, flyer, mount}: wrote")
    return fails


def refl_source():
    return f"""
    pushfq
    push rax
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    test r9, r9
    je chk_r8
    mov rax, qword ptr [r9 + 0x128]
    test rax, rax
    jne logit
    mov rax, qword ptr [r9 + 0x2e0]
    test rax, rax
    je chk_r8
    mov rax, qword ptr [rax + 0x128]
    test rax, rax
    jne logit
chk_r8:
    test r8, r8
    je done
    mov rax, qword ptr [r8 + 0x128]
    test rax, rax
    jne logit
    mov rax, qword ptr [r8 + 0x2e0]
    test rax, rax
    je done
    mov rax, qword ptr [rax + 0x128]
    test rax, rax
    je done
logit:
    mov eax, 1
    lock xadd dword ptr [r10 + {REFL_COUNT_AT}], eax
    mov r11d, eax
    and r11d, {REFL_SLOTS - 1}
    shl r11, 6
    add r11, r10
    add r11, {REFL_RING_AT}
    mov dword ptr [r11 + 16], eax
    mov qword ptr [r11], r8
    mov qword ptr [r11 + 8], r9
    mov dword ptr [r11 + 20], 3
    mov eax, dword ptr [rsp + 32 + 0x28]
    mov dword ptr [r11 + 24], eax
    mov rax, qword ptr [rsp + 32]
    mov qword ptr [r11 + 28], rax
    test r9, r9
    je skip9
    mov eax, dword ptr [r9 + 0x26c]
    mov dword ptr [r11 + 36], eax
    mov eax, dword ptr [r9 + 0xe0]
    mov dword ptr [r11 + 40], eax
    mov eax, dword ptr [r9 + 0xe8]
    mov dword ptr [r11 + 44], eax
    mov eax, dword ptr [r9 + 0x278]
    mov dword ptr [r11 + 48], eax
skip9:
    test r8, r8
    je done
    movzx eax, byte ptr [r8 + 0x68]
    mov dword ptr [r11 + 52], eax
    mov eax, dword ptr [r8 + 0x6c]
    mov dword ptr [r11 + 56], eax
    mov eax, dword ptr [r8 + 0xbc]
    mov dword ptr [r11 + 60], eax
done:
    pop r11
    pop r10
    pop rax
    popfq
"""


def source():
    stack = "\n".join(f"    mov rax, qword ptr [rsp + {32 + 8 * i}]\n    mov qword ptr [r11 + {64 + 8 * i}], rax"
                      for i in range(48))
    return f"""
    pushfq
    push rax
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    mov rax, qword ptr [rcx + 0x128]
    test rax, rax
    jne logit
    mov rax, qword ptr [rcx + 0x2e0]
    test rax, rax
    je done
    mov rax, qword ptr [rax + 0x128]
    test rax, rax
    je done
logit:
    mov eax, 1
    lock xadd dword ptr [r10 + {COUNT_AT}], eax
    mov r11d, eax
    and r11d, {SLOTS - 1}
    shl r11, 9
    lea r11, [r10 + r11 + {RING_AT}]
    mov qword ptr [r11], rcx
    mov dword ptr [r11 + 16], eax
    mov rax, qword ptr [rsp + 32]
    mov qword ptr [r11 + 8], rax
    mov eax, dword ptr [rcx + 0x26c]
    mov dword ptr [r11 + 20], eax
    mov eax, dword ptr [rcx + 0xe0]
    mov dword ptr [r11 + 24], eax
    mov eax, dword ptr [rcx + 0xe8]
    mov dword ptr [r11 + 28], eax
    mov eax, dword ptr [rcx + 0x710]
    mov dword ptr [r11 + 32], eax
    mov eax, dword ptr [rcx + 0x104]
    mov dword ptr [r11 + 36], eax
    mov dword ptr [r11 + 40], r9d
    movd eax, xmm2
    mov dword ptr [r11 + 44], eax
    mov qword ptr [r11 + 48], rdx
    mov eax, dword ptr [rcx + 0x278]
    mov dword ptr [r11 + 56], eax
{stack}
done:
    pop r11
    pop r10
    pop rax
    popfq
"""


def ent_source(count_at, slots, ring_at, extras):
    """bp_log's body with its own ring and its own three extra fields (+40, +44, +48)."""
    body = source()
    old_extras = """    mov dword ptr [r11 + 40], r9d
    movd eax, xmm2
    mov dword ptr [r11 + 44], eax
    mov qword ptr [r11 + 48], rdx
"""
    assert body.count(old_extras) == 1
    body = body.replace(old_extras, extras)
    for a, b in ((f"[r10 + {COUNT_AT}]", f"[r10 + {count_at}]"), (f"and r11d, {SLOTS - 1}", f"and r11d, {slots - 1}"),
                 (f"lea r11, [r10 + r11 + {RING_AT}]", f"lea r11, [r10 + r11 + {ring_at}]")):
        assert body.count(a) == 1, a
        body = body.replace(a, b)
    return body


GSET_EXTRAS = """    mov eax, dword ptr [rdx]
    mov dword ptr [r11 + 40], eax
    mov eax, dword ptr [rdx + 8]
    mov dword ptr [r11 + 44], eax
    mov qword ptr [r11 + 48], r8
"""
STAG_EXTRAS = """    mov eax, dword ptr [rcx + 0xb28]
    mov dword ptr [r11 + 40], eax
    movzx eax, byte ptr [rcx + 0xb11]
    mov dword ptr [r11 + 44], eax
    mov rax, qword ptr [rcx + 0x88]
    mov qword ptr [r11 + 48], rax
"""


def abrt_source():
    """[round 4] entry of 0x14304cea0: rcx = flight controller, [rcx] its entity. Entry (512 bytes): +0 entity,
    +8 return address, +16 seq, +20 phase (fc +0x90), +24 rate (fc +0x38), +28 height (entity +0x8c),
    +32 entity +0x710, +36 entity +0x104, +40 fc +0x3c, +44 entity +0x26c, +48 fc +0x10 / +0x18 (landing
    point x, z), +56 entity +0x278, +64.. 48 stack slots. Every register and the flags come back."""
    stack = "\n".join(f"    mov rax, qword ptr [rsp + {32 + 8 * i}]\n    mov qword ptr [r11 + {64 + 8 * i}], rax"
                      for i in range(48))
    return f"""
    pushfq
    push rax
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    mov rax, qword ptr [rcx]
    test rax, rax
    je done
    mov eax, 1
    lock xadd dword ptr [r10 + {ABRT_COUNT_AT}], eax
    mov r11d, eax
    and r11d, {ABRT_SLOTS - 1}
    shl r11, 9
    lea r11, [r10 + r11 + {ABRT_RING_AT}]
    mov dword ptr [r11 + 16], eax
    mov rax, qword ptr [rcx]
    mov qword ptr [r11], rax
    mov rax, qword ptr [rsp + 32]
    mov qword ptr [r11 + 8], rax
    mov eax, dword ptr [rcx + 0x90]
    mov dword ptr [r11 + 20], eax
    mov eax, dword ptr [rcx + 0x38]
    mov dword ptr [r11 + 24], eax
    mov eax, dword ptr [rcx + 0x3c]
    mov dword ptr [r11 + 40], eax
    mov eax, dword ptr [rcx + 0x10]
    mov dword ptr [r11 + 48], eax
    mov eax, dword ptr [rcx + 0x18]
    mov dword ptr [r11 + 52], eax
    mov r10, qword ptr [rcx]
    mov eax, dword ptr [r10 + 0x8c]
    mov dword ptr [r11 + 28], eax
    mov eax, dword ptr [r10 + 0x710]
    mov dword ptr [r11 + 32], eax
    mov eax, dword ptr [r10 + 0x104]
    mov dword ptr [r11 + 36], eax
    mov eax, dword ptr [r10 + 0x26c]
    mov dword ptr [r11 + 44], eax
    mov eax, dword ptr [r10 + 0x278]
    mov dword ptr [r11 + 56], eax
{stack}
done:
    pop r11
    pop r10
    pop rax
    popfq
"""


def check_abrt(code):
    """logs entity / return / phase / landing point for mode 1, nothing for mode 0 or a null entity;
    registers and flags kept."""
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
    from unicorn import x86_const as X
    CODE, B, STACK, OBJ = 0x100000, 0x200000, 0x400000, 0x500000
    fails = []
    for mode, has_ent, want in ((1, True, True), (0, True, False), (1, False, False)):
        mu = Uc(UC_ARCH_X86, UC_MODE_64)
        mu.mem_map(CODE, 0x2000)
        mu.mem_map(B, (BYTES + 0xfff) & ~0xfff)
        mu.mem_map(STACK, 0x10000)
        mu.mem_map(OBJ, 0x10000)
        mu.mem_write(CODE, code.replace(struct.pack("<Q", BUF), struct.pack("<Q", B)))
        fc, ent = OBJ + 0x1000, OBJ + 0x4000
        mu.mem_write(fc, struct.pack("<Q", ent if has_ent else 0))
        mu.mem_write(fc + 0x10, struct.pack("<fff", 718.0, 577.0, -160.0))
        mu.mem_write(fc + 0x38, struct.pack("<f", -0.225))
        mu.mem_write(fc + 0x3c, struct.pack("<I", 2))
        mu.mem_write(fc + 0x90, struct.pack("<I", 5))
        mu.mem_write(ent + 0x8c, struct.pack("<f", 579.0))
        mu.mem_write(ent + 0x104, struct.pack("<i", 2))
        mu.mem_write(ent + 0x710, struct.pack("<i", 4))
        mu.mem_write(ent + 0x26c, struct.pack("<i", 30))
        mu.mem_write(ent + 0x278, struct.pack("<I", 1))
        mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
        rsp = STACK + 0x4000
        mu.mem_write(rsp, struct.pack("<Q", 0x143050255) + bytes(range(8, 256)) + bytes(256))
        vals = {X.UC_X86_REG_RAX: 0xAAAA, X.UC_X86_REG_RCX: fc, X.UC_X86_REG_RDX: 0xD5, X.UC_X86_REG_R10: 0x1010,
                X.UC_X86_REG_R11: 0x1111, X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_EFLAGS: 0x246}
        for r, v in vals.items():
            mu.reg_write(r, v)
        from unicorn import UcError
        try:
            mu.emu_start(CODE, CODE + len(code))
        except UcError as exc:        # a fault is a failing case (the null-entity mutant reads address 0)
            fails.append(f"abrt {mode, has_ent}: fault {exc}")
            continue
        changed = [r for r in vals if mu.reg_read(r) != vals[r]]
        cnt = struct.unpack("<I", bytes(mu.mem_read(B + ABRT_COUNT_AT, 4)))[0]
        e = bytes(mu.mem_read(B + ABRT_RING_AT, 512))
        if changed:
            fails.append(f"abrt {mode, has_ent}: changed {changed}")
        if want:
            got = struct.unpack_from("<QQIIffiiIiffI", e, 0)
            exp = (ent, 0x143050255, 0, 5, struct.unpack("<f", struct.pack("<f", -0.225))[0], 579.0, 4, 2, 2, 30,
                   718.0, -160.0, 1)
            if cnt != 1 or got != exp or e[64:72] != struct.pack("<Q", 0x143050255):
                fails.append(f"abrt {mode, has_ent}: entry {got} count {cnt}")
        elif cnt or any(e):
            fails.append(f"abrt {mode, has_ent}: wrote")
    return fails


def gset_source():
    return ent_source(GSET_COUNT_AT, GSET_SLOTS, GSET_RING_AT, GSET_EXTRAS)


def stag_source():
    return ent_source(STAG_COUNT_AT, STAG_SLOTS, STAG_RING_AT, STAG_EXTRAS)


def check_ent(code, count_at, slots, ring_at, kind):
    """flyer / mount-of-flyer logged with the right extras, non-flyer and mode 0 not; registers kept."""
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
    from unicorn import x86_const as X
    CODE, B, STACK, OBJ = 0x100000, 0x200000, 0x400000, 0x500000
    fails = []
    for mode, flyer, mount, want in ((1, True, False, True), (1, False, True, True), (1, False, False, False),
                                     (0, True, False, False), (1, False, "nofc", False)):
        mu = Uc(UC_ARCH_X86, UC_MODE_64)
        mu.mem_map(CODE, 0x2000)
        mu.mem_map(B, (BYTES + 0xfff) & ~0xfff)
        mu.mem_map(STACK, 0x10000)
        mu.mem_map(OBJ, 0x10000)
        mu.mem_write(CODE, code.replace(struct.pack("<Q", BUF), struct.pack("<Q", B)))
        ent, par, vec = OBJ + 0x1000, OBJ + 0x6000, OBJ + 0x8000
        mu.mem_write(ent + 0x128, struct.pack("<Q", 0x77 if flyer else 0))
        mu.mem_write(ent + 0x2e0, struct.pack("<Q", par if mount else 0))
        mu.mem_write(par + 0x128, struct.pack("<Q", 0 if mount == "nofc" else 0x55))
        mu.mem_write(ent + 0x26c, struct.pack("<i", 30))
        mu.mem_write(ent + 0xe0, struct.pack("<fff", 2.0, 0.0, -11.0))
        mu.mem_write(ent + 0x710, struct.pack("<i", 4))
        mu.mem_write(ent + 0x278, struct.pack("<I", 1))
        mu.mem_write(ent + 0x88, struct.pack("<ff", 160.5, 2270.25))
        mu.mem_write(ent + 0xb28, struct.pack("<I", 2))
        mu.mem_write(ent + 0xb11, bytes([0x0c]))
        mu.mem_write(vec, struct.pack("<fff", 161.0, 0.0, -141.0))
        mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
        mu.mem_write(B + count_at, struct.pack("<I", slots + 2))
        rsp = STACK + 0x4000
        mu.mem_write(rsp, struct.pack("<Q", 0x143098CD6) + bytes(range(8, 256)) + bytes(256))
        vals = {X.UC_X86_REG_RAX: 0xAAAA, X.UC_X86_REG_RCX: ent, X.UC_X86_REG_RDX: vec,
                X.UC_X86_REG_R8: 0x1234, X.UC_X86_REG_R9: 0x99, X.UC_X86_REG_R10: 0x1010, X.UC_X86_REG_R11: 0x1111,
                X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_EFLAGS: 0x246}
        for r, v in vals.items():
            mu.reg_write(r, v)
        mu.emu_start(CODE, CODE + len(code))
        changed = [r for r in vals if mu.reg_read(r) != vals[r]]
        cnt = struct.unpack("<I", bytes(mu.mem_read(B + count_at, 4)))[0] - (slots + 2)
        e = bytes(mu.mem_read(B + ring_at + 2 * 512, 512))
        if changed:
            fails.append(f"{kind} {mode, flyer, mount}: changed {changed}")
        if want:
            head = struct.unpack_from("<QQIiffii", e, 0)
            extra = struct.unpack_from("<ffQ", e, 40) if kind == "gset" else struct.unpack_from("<IIQ", e, 40)
            want_extra = (161.0, -141.0, 0x1234) if kind == "gset" else \
                (2, 0x0c, struct.unpack("<Q", struct.pack("<ff", 160.5, 2270.25))[0])
            if cnt != 1 or head != (ent, 0x143098CD6, slots + 2, 30, 2.0, -11.0, 4, 0) or extra != want_extra \
                    or struct.unpack_from("<I", e, 56)[0] != 1 or e[64:72] != struct.pack("<Q", 0x143098CD6) \
                    or e[72:80] != bytes(range(8, 16)):
                fails.append(f"{kind} {mode, flyer, mount}: entry {head} {extra} count {cnt}")
        elif cnt or any(e):
            fails.append(f"{kind} {mode, flyer, mount}: wrote")
    return fails


def assemble(src=None):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_64
    code = bytes(Ks(KS_ARCH_X86, KS_MODE_64).asm(src or source(), 0x1000)[0])
    assert code.count(struct.pack("<Q", BUF)) == 1
    return code


def check(code):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
    from unicorn import x86_const as X
    CODE, B, STACK, OBJ = 0x100000, 0x200000, 0x400000, 0x500000
    fails = []
    for mode, flyer, want in ((1, True, True), (1, False, False), (0, True, False)):
        mu = Uc(UC_ARCH_X86, UC_MODE_64)
        mu.mem_map(CODE, 0x2000)
        mu.mem_map(B, (BYTES + 0xfff) & ~0xfff)
        mu.mem_map(STACK, 0x10000)
        mu.mem_map(OBJ, 0x10000)
        mu.mem_write(CODE, code.replace(struct.pack("<Q", BUF), struct.pack("<Q", B)))
        ent = OBJ + 0x1000
        mu.mem_write(ent + 0x128, struct.pack("<Q", 0x77 if flyer else 0))
        mu.mem_write(ent + 0x26c, struct.pack("<i", 30))
        mu.mem_write(ent + 0xe0, struct.pack("<fff", 1.0, 0.0, -12.0))
        mu.mem_write(ent + 0x710, struct.pack("<i", 4))
        mu.mem_write(ent + 0x278, struct.pack("<I", 489))
        mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
        mu.mem_write(B + COUNT_AT, struct.pack("<I", SLOTS + 3))
        rsp = STACK + 0x4000
        mu.mem_write(rsp, struct.pack("<Q", 0x14307B6FB) + bytes(range(8, 256)) + bytes(128))
        vals = {X.UC_X86_REG_RAX: 0xAAAA, X.UC_X86_REG_RCX: ent, X.UC_X86_REG_RDX: 0xD0D0,
                X.UC_X86_REG_R9: 0x99, X.UC_X86_REG_R10: 0x1010, X.UC_X86_REG_R11: 0x1111,
                X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_EFLAGS: 0x246, X.UC_X86_REG_XMM2: 0x40400000}
        for r, v in vals.items():
            mu.reg_write(r, v)
        mu.emu_start(CODE, CODE + len(code))
        changed = [r for r in vals if mu.reg_read(r) != vals[r]]
        cnt = struct.unpack("<I", bytes(mu.mem_read(B + COUNT_AT, 4)))[0] - (SLOTS + 3)
        e = bytes(mu.mem_read(B + RING_AT + 3 * ENTRY, ENTRY))
        if changed:
            fails.append(f"mode {mode} flyer {flyer}: changed {changed}")
        if want:
            got = struct.unpack("<QQIiffiiIIQI", e[:60])
            if cnt != 1 or got != (ent, 0x14307B6FB, SLOTS + 3, 30, 1.0, -12.0, 4, 0, 0x99, 0x40400000, 0xD0D0, 489) \
                    or e[64:72] != struct.pack("<Q", 0x14307B6FB) or e[72:80] != bytes(range(8, 16)):
                fails.append(f"entry {got} count {cnt}")
        elif cnt or any(e):
            fails.append(f"mode {mode} flyer {flyer} wrote")
    return fails


def check_refl(code):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
    from unicorn import x86_const as X
    CODE, B, STACK, OBJ = 0x100000, 0x200000, 0x400000, 0x500000
    fails = []
    # (mode, r9 flyer?, r9 mount flyer?, r8 flyer?, r9 null?, want log)
    cases = ((1, True, False, False, False, True), (1, False, True, False, False, True),
             (1, False, False, True, False, True), (1, False, False, False, False, False),
             (0, True, False, False, False, False), (1, False, False, True, True, True),
             (1, False, False, False, True, False))
    for mode, f9, m9, f8, null9, want in cases:
        mu = Uc(UC_ARCH_X86, UC_MODE_64)
        mu.mem_map(CODE, 0x2000)
        mu.mem_map(B, (BYTES + 0xfff) & ~0xfff)
        mu.mem_map(STACK, 0x10000)
        mu.mem_map(OBJ, 0x10000)
        mu.mem_write(CODE, code.replace(struct.pack("<Q", BUF), struct.pack("<Q", B)))
        e9, e8, mount = OBJ + 0x1000, OBJ + 0x4000, OBJ + 0x8000
        mu.mem_write(e9 + 0x128, struct.pack("<Q", 0x77 if f9 else 0))
        mu.mem_write(e9 + 0x2e0, struct.pack("<Q", mount if m9 else 0))
        mu.mem_write(mount + 0x128, struct.pack("<Q", 0x55))
        mu.mem_write(e9 + 0x26c, struct.pack("<i", 33))
        mu.mem_write(e9 + 0xe0, struct.pack("<fff", 2.0, 0.0, -11.0))
        mu.mem_write(e9 + 0x278, struct.pack("<I", 1))
        mu.mem_write(e8 + 0x128, struct.pack("<Q", 0x66 if f8 else 0))
        mu.mem_write(e8 + 0x68, bytes([0x0c]))
        mu.mem_write(e8 + 0x6c, struct.pack("<I", 0x10000))
        mu.mem_write(e8 + 0xbc, struct.pack("<f", 6.5))
        mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
        mu.mem_write(B + REFL_COUNT_AT, struct.pack("<I", REFL_SLOTS + 5))
        rsp = STACK + 0x4000
        mu.mem_write(rsp, struct.pack("<Q", 0x14325BF4B) + bytes(0x20) + struct.pack("<f", 9.25) + bytes(64))
        vals = {X.UC_X86_REG_RAX: 0xAAAA, X.UC_X86_REG_RCX: 0xC0C0, X.UC_X86_REG_RDX: 0xD0D0,
                X.UC_X86_REG_R8: e8, X.UC_X86_REG_R9: 0 if null9 else e9, X.UC_X86_REG_R10: 0x1010,
                X.UC_X86_REG_R11: 0x1111, X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_EFLAGS: 0x246}
        for r, v in vals.items():
            mu.reg_write(r, v)
        mu.emu_start(CODE, CODE + len(code))
        changed = [r for r in vals if mu.reg_read(r) != vals[r]]
        cnt = struct.unpack("<I", bytes(mu.mem_read(B + REFL_COUNT_AT, 4)))[0] - (REFL_SLOTS + 5)
        e = bytes(mu.mem_read(B + REFL_RING_AT + 5 * REFL_ENTRY, REFL_ENTRY))
        if changed:
            fails.append(f"refl case {mode, f9, m9, f8, null9}: changed {changed}")
        if want:
            r8v, r9v, seq, kind, spd, ret = struct.unpack_from("<QQIIfQ", e, 0)
            st, vx, vz, slot, f68, f6c, bc = struct.unpack_from("<iffIIIf", e, 36)
            exp9 = 0 if null9 else e9
            good = (cnt == 1 and r8v == e8 and r9v == exp9 and seq == REFL_SLOTS + 5 and kind == 3 and spd == 9.25
                    and ret == 0x14325BF4B and f68 == 0x0c and f6c == 0x10000 and bc == 6.5
                    and ((st, vx, vz, slot) == (33, 2.0, -11.0, 1) if not null9 else (st, vx, vz, slot) == (0, 0.0, 0.0, 0)))
            if not good:
                fails.append(f"refl case {mode, f9, m9, f8, null9}: entry {r8v:x} {r9v:x} {seq} {kind} {spd} {ret:x} {st} {vx} {vz} {slot} {f68:x} {f6c:x} {bc} cnt {cnt}")
        elif cnt or any(e):
            fails.append(f"refl case {mode, f9, m9, f8, null9}: wrote")
    return fails


def template(code):
    out, i, mark = [], 0, struct.pack("<Q", BUF)
    while i < len(code):
        if code[i:i + 8] == mark:
            out.append("{buf:8}")
            i += 8
        else:
            out.append(f"{code[i]:02X}")
            i += 1
    return " ".join(out)


def main():
    code = assemble()
    fails = check(code)
    refl = assemble(refl_source())
    fails += check_refl(refl)
    mel = assemble(mel_source())
    fails += check_mel(mel)
    osrc = ord_source()
    assert f"[r10 + {ORD_COUNT_AT}]" in osrc and f"add r11, {ORD_RING_AT}" in osrc
    orc = assemble(osrc)
    fails += check_ord(orc)
    gsc = assemble(gset_source())
    fails += check_ent(gsc, GSET_COUNT_AT, GSET_SLOTS, GSET_RING_AT, "gset")
    stc = assemble(stag_source())
    fails += check_ent(stc, STAG_COUNT_AT, STAG_SLOTS, STAG_RING_AT, "stag")
    abc = assemble(abrt_source())
    fails += check_abrt(abc)
    for bad_src in (abrt_source().replace("mov eax, dword ptr [rcx + 0x90]", "mov eax, dword ptr [rcx + 0x94]"),
                    abrt_source().replace("    je done\n    mov eax, 1", "    nop\n    mov eax, 1")):
        if not check_abrt(assemble(bad_src)):
            fails.append("mutant of abrt not caught")
    # broken variants the checks must catch: wrong ring, wrong extra, no flyer filter
    for kind, src, args in (("gset", gset_source().replace("mov eax, dword ptr [rdx + 8]", "mov eax, dword ptr [rdx + 4]"),
                             (GSET_COUNT_AT, GSET_SLOTS, GSET_RING_AT)),
                            ("stag", stag_source().replace("[rcx + 0xb28]", "[rcx + 0xb2c]"), (STAG_COUNT_AT, STAG_SLOTS, STAG_RING_AT)),
                            ("gset", gset_source().replace(f"[r10 + {GSET_COUNT_AT}]", f"[r10 + {STAG_COUNT_AT}]"),
                             (GSET_COUNT_AT, GSET_SLOTS, GSET_RING_AT)),
                            ("stag", stag_source().replace("    je done\nlogit:", "    jmp logit\nlogit:").replace(
                                "    test rax, rax\n    je done\n    mov rax, qword ptr [rax + 0x128]",
                                "    test rax, rax\n    jmp logit\n    mov rax, qword ptr [rax + 0x128]"),
                             (STAG_COUNT_AT, STAG_SLOTS, STAG_RING_AT))):
        try:
            bad = assemble(src)
        except AssertionError:
            continue
        if not check_ent(bad, *args, kind):
            fails.append(f"mutant of {kind} not caught")
    if fails:
        raise SystemExit("FAILED " + "; ".join(fails))
    names = {"rp_act1": "bp_act1", "rp_act2": "bp_act2"}
    acts = chr(10).join(f"""        {{ name = '{names[n]}', feature = 'brace_probe', kind = 'cave', pattern = '{pat}', at = 0, expect = '{st}',
            bytes = '{template(assemble(act_source(k)))}' }},""" for n, k, pat, st in ACT_SITES)
    lua = f"""-- TEST-ONLY generated by brace_probe_asm.py (AIR-DIVE-BRACE-W1)
return {{
    owner = 'ld_brace_probe', feature = 'brace_probe',
    entries = {{ {{ name = 'bp_log', feature = 'brace_probe', kind = 'cave',
        pattern = '{PATTERN}', at = 0, expect = '{STOLEN}',
        bytes = '{template(code)}' }},
{acts}
        {{ name = 'bp_refl', feature = 'brace_probe', kind = 'cave', pattern = '{REFL_PATTERN}', at = 0, expect = '{REFL_STOLEN}',
            bytes = '{template(refl)}' }},
        {{ name = 'bp_mel', feature = 'brace_probe', kind = 'cave', pattern = '{MEL_PATTERN}', at = 0, expect = '{MEL_STOLEN}',
            bytes = '{template(mel)}' }},
        {{ name = 'bp_ord', feature = 'brace_probe', kind = 'cave', pattern = '{ORD_PATTERN}', at = 0, expect = '{ORD_STOLEN}',
            bytes = '{template(orc)}' }},
        {{ name = 'bp_gset', feature = 'brace_probe', kind = 'cave', pattern = '{GSET_PATTERN}', at = 0, expect = '{GSET_STOLEN}',
            bytes = '{template(gsc)}' }},
        {{ name = 'bp_stag', feature = 'brace_probe', kind = 'cave', pattern = '{STAG_PATTERN}', at = 0, expect = '{STAG_STOLEN}',
            bytes = '{template(stc)}' }},
        {{ name = 'bp_abrt', feature = 'brace_probe', kind = 'cave', pattern = '{ABRT_PATTERN}', at = 0, expect = '{ABRT_STOLEN}',
            bytes = '{template(abc)}' }}, }},
    layout = {{ bytes = {BYTES}, count_at = {COUNT_AT}, mode_at = {MODE_AT}, magic_at = {MAGIC_AT},
        magic = '{MAGIC.decode()}', ring_at = {RING_AT}, slots = {SLOTS}, entry = {ENTRY},
        act_count_at = {ACT_COUNT_AT}, act_ring_at = {ACT_RING_AT}, act_slots = {ACT_SLOTS}, act_entry = {ACT_ENTRY},
        refl_count_at = {REFL_COUNT_AT}, refl_ring_at = {REFL_RING_AT}, refl_slots = {REFL_SLOTS}, refl_entry = {REFL_ENTRY},
        mel_count_at = {MEL_COUNT_AT}, mel_ring_at = {MEL_RING_AT}, mel_slots = {MEL_SLOTS}, mel_entry = {MEL_ENTRY},
        ord_count_at = {ORD_COUNT_AT}, ord_ring_at = {ORD_RING_AT}, ord_slots = {ORD_SLOTS}, ord_entry = {ORD_ENTRY},
        gset_count_at = {GSET_COUNT_AT}, gset_ring_at = {GSET_RING_AT}, gset_slots = {GSET_SLOTS}, gset_entry = {GSET_ENTRY},
        stag_count_at = {STAG_COUNT_AT}, stag_ring_at = {STAG_RING_AT}, stag_slots = {STAG_SLOTS}, stag_entry = {STAG_ENTRY},
        abrt_count_at = {ABRT_COUNT_AT}, abrt_ring_at = {ABRT_RING_AT}, abrt_slots = {ABRT_SLOTS}, abrt_entry = {ABRT_ENTRY} }},
}}
"""
    (HERE / "brace_probe_site.lua").write_text(lua, encoding="utf-8", newline=chr(10))
    print(f"caves {len(code)} / {len(refl)} / {len(mel)} B, emulator OK, site written")


if __name__ == "__main__":
    main()
