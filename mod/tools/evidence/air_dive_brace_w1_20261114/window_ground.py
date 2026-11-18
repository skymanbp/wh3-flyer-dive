from pathlib import Path
p = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools/pipelines/dive_cave_asm.py")
t = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
a = '''    hold. Every register and xmm0 / xmm1 come back unchanged."""
    d2 = struct.unpack("<I", struct.pack("<f", SLIDE_RELEASE_M * SLIDE_RELEASE_M))[0]
    return f"""
    push rax'''
b = '''    hold. Every register and xmm0 / xmm1 come back unchanged. A hold IN THE AIR (+0x104 not 0: dv_keep and
    dv_skip also hold a state-30 flyer on its way down) holds without touching the table, so the window
    starts where the flyer was first held on the ground (an airborne first hold would start it up to a
    dive-length before touchdown). Flags are not kept (every caller sets them again)."""
    d2 = struct.unpack("<I", struct.pack("<f", SLIDE_RELEASE_M * SLIDE_RELEASE_M))[0]
    return f"""
    cmp dword ptr [{ent} + {LAYER_OFF:#x}], 0
    jne wair
    push rax'''
assert t.count(a) == 1, "doc"
t = t.replace(a, b)
a = '''whold:
    movdqu xmm0, xmmword ptr [rsp]
    movdqu xmm1, xmmword ptr [rsp + 16]
    lea rsp, [rsp + 32]
    pop r9
    pop r8
    pop rdx
    pop rcx
    pop rbx
    pop rax
"""'''
b = a[:-3] + 'wair:\n"""'
assert t.count(a) == 1, "whold"
t = t.replace(a, b)
a = '''    # a full table (no empty slot, no tombstone): a new flyer passes, uncounted'''
b = '''    # an airborne hold (state 30, layer 2) holds and leaves the table alone; the window starts on the ground
    c = 0x505000
    _mover(mu, c, True, 30, FAST, layer=2)
    n += 1
    got = hold(c, 500.0, 500.0)
    if got != "held" or c in [k & ~1 for k in _slot_keys(mu, buf)]:
        fails.append(f"window airborne hold: {got}, in the table {c in [k & ~1 for k in _slot_keys(mu, buf)]}")
    mu.mem_write(c + LAYER_OFF, struct.pack("<i", 0))
    for label, x, want, rel in (("c lands 30 m on", 530.0, "held", 2), ("c 15 m on the ground", 545.0, "held", 2),
                                ("c 21 m on the ground", 551.0, "passed", 3)):
        n += 1
        got = hold(c, x, 500.0)
        if got != want or _released(mu, buf) != rel:
            fails.append(f"window {label}: {got} released {_released(mu, buf)} (want {want}, {rel})")
    # a full table (no empty slot, no tombstone): a new flyer passes, uncounted'''
assert t.count(a) == 1, "check"
t = t.replace(a, b)
a = '''    ("window never releases", "dv_keep", "    jb whold\\n", "    jmp whold\\n"),'''
b = a + '''
    ("window starts in the air", "dv_keep", "    jne wair\\n", "    nop\\n"),'''
assert t.count(a) == 1, "mutant"
t = t.replace(a, b)
p.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
print("ok")
