"""Lane edit (AIR-DIVE-BRACE-W1): dv_contact, the root fix for the brace stop.

Measured (run A1_wyvern lane 1, wyvern vs braced spearmen, CONTENT_LEDGER §C11 AIR-DIVE-BRACE-W1):
0.3 s after touchdown, still at 11.2 m/s, the engine gave the wyvern the melee order (vtable
0x143ade470, +0x324 = 1) and set its movement goal on itself; it braked at its deceleration to 0 in
0.5 s, 5.7 m in. The logged stack names the issuer: neighbour pair solver 0x143176c6c -> pairwise
collision 0x1430731c8 (enemy pair, at 0x1430732ff) -> contact-engage 0x14305dcac(rdx = the body that
engages, r8 = the enemy it touched) -> its vfunc +0x4b0 (0x143123338) -> 0x143075dd8, which installs
the melee order. So the stop is a state change (contact -> engage in melee -> stand), not the
collision's momentum. The cave makes 0x14305dcac return at once for a landed flyer still in flight
movement and fast (the dv_engage test): the collision itself (push, knock, collision attack) runs as
before; once the bodies it hits have slowed it below SKIP_SPEED the contact engages as vanilla.
Counted on ENGAGED_AT (the engage family; no new buffer field, no Lua change)."""
from pathlib import Path

p = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools/pipelines/dive_cave_asm.py")
s = p.read_bytes().decode("utf-8")
CRLF = chr(13) + chr(10) in s
s = s.replace(chr(13) + chr(10), chr(10))
assert "dv_contact" not in s

# 1. the site
old = '''    "dv_tick_move": ("F3 0F 11 5C 24 74 E8 ?? ?? ?? ?? 0F 28 74 24 50 0F 28 7C 24 40",
                     0, "F3 0F 11 5C 24 74 E8", 11),
}'''
new = '''    "dv_tick_move": ("F3 0F 11 5C 24 74 E8 ?? ?? ?? ?? 0F 28 74 24 50 0F 28 7C 24 40",
                     0, "F3 0F 11 5C 24 74 E8", 11),
    # [AIR-DIVE-BRACE-W1] 0x14305dcac entry: contact-engage (rdx = the body that engages, r8 = the
    # enemy it touched), called twice per enemy pair by the pairwise collision 0x1430731c8
    "dv_contact": ("48 89 5C 24 08 48 89 74 24 10 57 48 81 EC 80 00 00 00 48 8B 8A E8 02 00 00 49 8B F8 48 8B DA",
                   0, "48 89 5C 24 08 48 89 74 24 10", None),
}'''
assert old in s
s = s.replace(old, new)

# 2. the source
old = '''    if name == "dv_keep":
        return f"""'''
new = '''    if name == "dv_contact":
        return f"""
    pushfq
    push rax
    push r10
    push r11
    mov r10, {BUF_PLACEHOLDER:#x}
    cmp dword ptr [r10 + {MODE_AT}], 1
    jne pass
    mov r11, rdx
    test r11, r11
    je pass
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
    lock inc dword ptr [r10 + {ENGAGED_AT}]
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
    if name == "dv_keep":
        return f"""'''
assert s.count(old) == 1
s = s.replace(old, new)

# 3. the emulator helper: dv_contact takes its body in rdx and counts on ENGAGED_AT
old = '''    vals = {X.UC_X86_REG_RCX: rcx, X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_RBX: 0xB1, X.UC_X86_REG_RBP: 0xB2,
            X.UC_X86_REG_RSI: 0xB3, X.UC_X86_REG_RDI: 0xB4, X.UC_X86_REG_R12: 0xC1, X.UC_X86_REG_R15: 0xC4,
            X.UC_X86_REG_RDX: 0xD5, X.UC_X86_REG_EFLAGS: 0x202,'''
new = '''    contact = name == "dv_contact"
    vals = {X.UC_X86_REG_RCX: 0xC0C0 if contact else rcx, X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_RBX: 0xB1,
            X.UC_X86_REG_RBP: 0xB2, X.UC_X86_REG_RSI: 0xB3, X.UC_X86_REG_RDI: 0xB4, X.UC_X86_REG_R12: 0xC1,
            X.UC_X86_REG_R15: 0xC4, X.UC_X86_REG_R8: 0x8E8E, X.UC_X86_REG_RDX: rcx if contact else 0xD5,
            X.UC_X86_REG_EFLAGS: 0x202,'''
assert old in s
s = s.replace(old, new)
old = '''    if name == "dv_keep":
        vals.update({X.UC_X86_REG_RAX: 0xAAAA, X.UC_X86_REG_R10: 0x1010, X.UC_X86_REG_R11: 0x1111})'''
new = '''    if name in ("dv_keep", "dv_contact"):
        vals.update({X.UC_X86_REG_RAX: 0xAAAA, X.UC_X86_REG_R10: 0x1010, X.UC_X86_REG_R11: 0x1111})'''
assert old in s
s = s.replace(old, new)
old = '''    counter = SKIPPED_AT if name == "dv_skip" else KEPT_AT'''
new = '''    counter = {"dv_skip": SKIPPED_AT, "dv_contact": ENGAGED_AT}.get(name, KEPT_AT)'''
assert old in s
s = s.replace(old, new)

# 4. the check
old = '''def check_call_skip(name, code):'''
new = '''def check_contact(code):
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


def check_call_skip(name, code):'''
assert s.count(old) == 1
s = s.replace(old, new)
old = '''          "dv_tick_move": lambda code: check_call_skip("dv_tick_move", code)}'''
new = '''          "dv_tick_move": lambda code: check_call_skip("dv_tick_move", code),
          "dv_contact": check_contact}'''
assert old in s
s = s.replace(old, new)

# 5. mutants
old = '''    ("tick move forgets the store", "dv_tick_move",'''
new = '''    ("contact holds every body", "dv_contact", "    jbe pass\\n", "    nop\\n"),
    ("contact misses a ridden flyer", "dv_contact", "    cmovne r11, rax\\n", ""),
    ("contact in the air too", "dv_contact", "    cmp dword ptr [r11 + 0x104], 0\\n    jne pass\\n    cmp dword ptr [r11 + 0x710]",
     "    cmp dword ptr [r11 + 0x710]"),
    ("contact for ground movers too", "dv_contact", "    cmp dword ptr [r11 + 0x710], 0\\n    je pass\\n", ""),
    ("contact for ground units too", "dv_contact", "    mov rax, qword ptr [r11 + 0x128]\\n    test rax, rax\\n    je pass\\n",
     "    mov rax, qword ptr [r11 + 0x128]\\n    test rax, rax\\n    nop\\n"),
    ("contact on the touched enemy", "dv_contact", "    mov r11, rdx\\n", "    mov r11, r8\\n"),
    ("contact forgets rax", "dv_contact", "    pop rax\\n    popfq\\n    ret\\n", "    pop r11\\n    popfq\\n    ret\\n"),
    ("tick move forgets the store", "dv_tick_move",'''
assert s.count(old) == 1
s = s.replace(old, new)

p.write_bytes((s.replace(chr(10), chr(13) + chr(10)) if CRLF else s).encode("utf-8"))
print("patched")
