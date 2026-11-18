"""TEST-ONLY: add the melee-order constructor logger (bp_mel) to brace_probe_asm.py."""
from pathlib import Path

p = Path(__file__).resolve().parent / "brace_probe_asm.py"
s = p.read_text("utf-8")
assert "mel_source" not in s

s = s.replace('''BYTES = REFL_RING_AT + REFL_SLOTS * REFL_ENTRY''', '''MEL_COUNT_AT, MEL_SLOTS, MEL_ENTRY = 24, 256, 512
MEL_RING_AT = REFL_RING_AT + REFL_SLOTS * REFL_ENTRY
BYTES = MEL_RING_AT + MEL_SLOTS * MEL_ENTRY
# melee order constructor 0x14305abb4 (vtable 0x143ade470), only caller 0x143075eb8 inside
# 0x143075dd8 (rcx = entity + 0x330, the inline order slot)
MEL_PATTERN = "40 53 48 83 EC 20 4D 8B D8 48 8B D9 45 8A 40 22 E8 0F 01 00 00 48 8D 05"
MEL_STOLEN = "40 53 48 83 EC 20 4D 8B D8 48 8B D9"''')

MEL = r'''def mel_source():
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
                                     (0, True, False, False)):
        mu = Uc(UC_ARCH_X86, UC_MODE_64)
        mu.mem_map(CODE, 0x2000)
        mu.mem_map(B, (BYTES + 0xfff) & ~0xfff)
        mu.mem_map(STACK, 0x10000)
        mu.mem_map(OBJ, 0x10000)
        mu.mem_write(CODE, code.replace(struct.pack("<Q", BUF), struct.pack("<Q", B)))
        ent, par, prm = OBJ + 0x1000, OBJ + 0x6000, OBJ + 0x8000
        mu.mem_write(ent + 0x128, struct.pack("<Q", 0x77 if flyer else 0))
        mu.mem_write(ent + 0x2e0, struct.pack("<Q", par if mount else 0))
        mu.mem_write(par + 0x128, struct.pack("<Q", 0x55))
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


def refl_source():'''
s = s.replace("def refl_source():", MEL, 1)
s = s.replace('''    fails += check_refl(refl)''', '''    fails += check_refl(refl)
    mel = assemble(mel_source())
    fails += check_mel(mel)''')
s = s.replace('''            bytes = '{template(refl)}' }}, }},''', '''            bytes = '{template(refl)}' }},
        {{ name = 'bp_mel', feature = 'brace_probe', kind = 'cave', pattern = '{MEL_PATTERN}', at = 0, expect = '{MEL_STOLEN}',
            bytes = '{template(mel)}' }}, }},''')
s = s.replace('''refl_slots = {REFL_SLOTS}, refl_entry = {REFL_ENTRY} }},''', '''refl_slots = {REFL_SLOTS}, refl_entry = {REFL_ENTRY},
        mel_count_at = {MEL_COUNT_AT}, mel_ring_at = {MEL_RING_AT}, mel_slots = {MEL_SLOTS}, mel_entry = {MEL_ENTRY} }},''')
s = s.replace('''print(f"caves {len(code)} / {len(refl)} B''', '''print(f"caves {len(code)} / {len(refl)} / {len(mel)} B''')
for needle in ("bp_mel", "check_mel(mel)", "mel_ring_at", "len(mel)"):
    assert needle in s, needle
p.write_text(s, "utf-8")
print("patched")
