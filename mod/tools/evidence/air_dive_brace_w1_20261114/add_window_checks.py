from pathlib import Path
p = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools/pipelines/dive_cave_asm.py")
t = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
NEW = r'''
def _window_rig(hold_code, through_code):
    """[AIR-DIVE-BRACE-W1 round 3] One machine, one buffer, both caves: the slide table must persist from
    call to call. -> (mu, hold(ent, x, z) -> 'held' / 'passed' / why, through(ent, layer), buffer)."""
    from unicorn import UC_HOOK_CODE, UcError
    from unicorn import x86_const as X
    HOLD, THR, RESUME, BUF, STACK, OBJ, RET = 0x100000, 0x110000, 0x120000, 0x200000, 0x400000, 0x500000, 0x130000
    mu = _uc()
    for base, size in ((HOLD, 0x1000), (THR, 0x1000), (RESUME, 0x1000), (BUF, 0x2000), (STACK, 0x10000),
                       (OBJ, 0x10000), (RET, 0x1000)):
        mu.mem_map(base, size)
    mu.mem_write(HOLD, _fill(hold_code, BUF) + b"\x90")
    mu.mem_write(THR, _fill(through_code, BUF, RESUME) + b"\x90")
    mu.mem_write(RET, b"\x90")
    mu.mem_write(RESUME, b"\x90")
    mu.mem_write(BUF + MODE_AT, struct.pack("<I", 1))
    mu.mem_write(BUF + SKIP_SPEED_AT, struct.pack("<f", SKIP_SPEED))
    end = HOLD + len(hold_code)
    stop = {}

    def on_code(uc, addr, _size, _data):
        stop["at"] = addr
        uc.emu_stop()
    for at in (RET, end, RESUME):
        mu.hook_add(UC_HOOK_CODE, on_code, begin=at, end=at)
    keep = (X.UC_X86_REG_RAX, X.UC_X86_REG_RBX, X.UC_X86_REG_RCX, X.UC_X86_REG_RDX, X.UC_X86_REG_RSI,
            X.UC_X86_REG_RDI, X.UC_X86_REG_RBP, X.UC_X86_REG_R8, X.UC_X86_REG_R9, X.UC_X86_REG_R10,
            X.UC_X86_REG_R11, X.UC_X86_REG_R12, X.UC_X86_REG_R15, X.UC_X86_REG_XMM0, X.UC_X86_REG_XMM1)

    def hold(ent, x, z):
        mu.mem_write(ent + POS_OFF, struct.pack("<f", x))
        mu.mem_write(ent + POS_OFF + 8, struct.pack("<f", z))
        rsp = STACK + 0x8000
        mu.mem_write(rsp, struct.pack("<Q", RET))
        vals = {r: 0x1000 + i for i, r in enumerate(keep)}
        vals[X.UC_X86_REG_RCX] = ent
        vals[X.UC_X86_REG_XMM0] = 0x1111_2222_3333_4444_5555_6666_7777_8888
        vals[X.UC_X86_REG_XMM1] = 0x9999_AAAA_BBBB_CCCC_DDDD_EEEE_FFFF_0000
        for r, v in vals.items():
            mu.reg_write(r, v)
        mu.reg_write(X.UC_X86_REG_RSP, rsp)
        mu.reg_write(X.UC_X86_REG_EFLAGS, 0x202)
        stop.clear()
        try:
            mu.emu_start(HOLD, 0, count=600)
        except UcError as exc:        # a fault is a failing case, reported by the caller
            return f"fault {exc}"
        bad = [r for r in vals if mu.reg_read(r) != vals[r]]
        if bad:
            return f"changed {bad}"
        if stop.get("at") == RET and mu.reg_read(X.UC_X86_REG_RSP) == rsp + 8:
            return "held"
        if stop.get("at") == end and mu.reg_read(X.UC_X86_REG_RSP) == rsp:
            return "passed"
        return f"stopped at {stop.get('at')} rsp {mu.reg_read(X.UC_X86_REG_RSP) - rsp:+d}"

    def through(ent, layer):
        mu.mem_write(ent + LAYER_OFF, struct.pack("<i", layer))
        for r, v in ((X.UC_X86_REG_R9, ent), (X.UC_X86_REG_RDI, OBJ + 0x9000), (X.UC_X86_REG_RBX, 0x5A),
                     (X.UC_X86_REG_RSP, STACK + 0x8000)):
            mu.reg_write(r, v)
        stop.clear()
        try:
            mu.emu_start(THR, 0, count=4000)
        except UcError:               # a fault is a failing case: the caller sees False
            return False
        mu.mem_write(ent + LAYER_OFF, struct.pack("<i", 0))
        return stop.get("at") == RESUME
    return mu, hold, through, BUF


def _released(mu, buf):
    return struct.unpack("<I", bytes(mu.mem_read(buf + RELEASED_AT, 4)))[0]


def _slot_keys(mu, buf):
    raw = bytes(mu.mem_read(buf + SLIDE_AT, SLIDE_SLOTS * 16))
    return [struct.unpack_from("<Q", raw, i * 16)[0] for i in range(SLIDE_SLOTS)]


def check_window(hold_code, through_code):
    """[AIR-DIVE-BRACE-W1 round 3] The slide window, through dv_keep (rcx = the flyer): held within
    SLIDE_RELEASE_M of the first hold, released for good past it (counted once), a fresh window after an
    airborne charge (dv_through on the same flyer, not a ground one), flyers independent, a full table
    passes uncounted, and every register comes back on both exits."""
    fails, n = [], 0
    mu, hold, through, buf = _window_rig(hold_code, through_code)
    a, b = 0x501000, 0x503000
    for ent in (a, b):
        _mover(mu, ent, True, 30, FAST)
    r = SLIDE_RELEASE_M
    steps = [("a first hold", a, 3.0, 4.0, "held", 0), ("a 14 m out", a, 13.0, 14.0, "held", 0),
             ("b first hold far away", b, 300.0, 300.0, "held", 0),
             ("a just inside", a, 3.0 + r * 0.99, 4.0, "held", 0),
             ("a just past", a, 3.0 + r * 0.6, 4.0 + r * 0.81, "passed", 1),
             ("a back near the start: released for good", a, 3.0, 4.0, "passed", 1),
             ("b still inside its own window", b, 310.0, 300.0, "held", 1)]
    for label, ent, x, z, want, rel in steps:
        n += 1
        got = hold(ent, x, z)
        if got != want or _released(mu, buf) != rel:
            fails.append(f"window {label}: {got} released {_released(mu, buf)} (want {want}, {rel})")
    n += 1
    if not through(a, 0) or a not in [k & ~1 for k in _slot_keys(mu, buf)]:
        fails.append("window: a ground charge (layer 0) must not clear the entry")
    n += 1
    if not through(a, 2) or a in [k & ~1 for k in _slot_keys(mu, buf)] or 2 not in _slot_keys(mu, buf):
        fails.append("window: an airborne charge must tombstone the flyer's entry")
    for label, ent, x, z, want, rel in (("a new window after the air charge", a, 100.0, 100.0, "held", 1),
                                        ("a 15 m into the new window", a, 115.0, 100.0, "held", 1),
                                        ("a past the new window", a, 125.0, 100.0, "passed", 2)):
        n += 1
        got = hold(ent, x, z)
        if got != want or _released(mu, buf) != rel:
            fails.append(f"window {label}: {got} released {_released(mu, buf)} (want {want}, {rel})")
    # a full table (no empty slot, no tombstone): a new flyer passes, uncounted
    mu2, hold2, _thr2, buf2 = _window_rig(hold_code, through_code)
    mu2.mem_write(buf2 + SLIDE_AT, b"".join(struct.pack("<QQ", 0x7000_0000 + 0x10 * (i + 1), 0)
                                            for i in range(SLIDE_SLOTS)))
    _mover(mu2, a, True, 30, FAST)
    n += 1
    got = hold2(a, 0.0, 0.0)
    if got != "passed" or _released(mu2, buf2) != 0:
        fails.append(f"window full table: {got} released {_released(mu2, buf2)} (want passed, 0)")
    return fails, n


def check_window_ridden(contact_code, through_code):
    """[AIR-DIVE-BRACE-W1 round 3] A rider (dv_contact, rcx = the rider): the window is keyed on the
    mount; released past the radius; and an airborne charge of the rider (dv_through) clears the mount's
    entry."""
    fails, n = [], 0
    mu, hold, through, buf = _window_rig(contact_code, through_code)
    rider, mount = 0x501000, 0x503000
    mu.mem_write(rider + PARENT_OFF, struct.pack("<Q", mount))
    _mover(mu, mount, True, 30, FAST)
    mu.mem_write(mount + FLYMODE_OFF, struct.pack("<i", 4))

    def at(x, z):
        mu.mem_write(mount + POS_OFF, struct.pack("<f", x))
        mu.mem_write(mount + POS_OFF + 8, struct.pack("<f", z))
        return hold(rider, 0.0, 0.0)          # the rider's own position must not matter
    n += 1
    got = at(0.0, 0.0)
    keys = [k & ~1 for k in _slot_keys(mu, buf)]
    if got != "held" or mount not in keys or rider in keys:
        fails.append(f"window ridden: {got}, keyed on the mount {mount in keys}, on the rider {rider in keys}")
    for label, x, want, rel in (("mount 15 m", 15.0, "held", 0), ("mount past", 25.0, "passed", 1),
                                ("mount back: released", 1.0, "passed", 1)):
        n += 1
        got = at(x, 0.0)
        if got != want or _released(mu, buf) != rel:
            fails.append(f"window ridden {label}: {got} released {_released(mu, buf)} (want {want}, {rel})")
    n += 1
    if not through(rider, 2) or mount in [k & ~1 for k in _slot_keys(mu, buf)]:
        fails.append("window ridden: the rider's airborne charge must clear the mount's entry")
    n += 1
    got = at(1.0, 0.0)
    if got != "held":
        fails.append(f"window ridden after the air charge: {got} (want held)")
    return fails, n


def _keep_and_window(code):
    f1, n1 = check_keep(code)
    f2, n2 = check_window(code, assemble("dv_through"))
    return f1 + f2, n1 + n2


def _through_and_window(code):
    f1, n1 = check_through(code)
    f2, n2 = check_window(assemble("dv_keep"), code)
    f3, n3 = check_window_ridden(assemble("dv_contact"), code)
    return f1 + f2 + f3, n1 + n2 + n3


def _contact_and_window(code):
    f1, n1 = check_contact(code)
    f2, n2 = check_window_ridden(code, assemble("dv_through"))
    return f1 + f2, n1 + n2


CHECKS = {"dv_through": _through_and_window, "dv_skip": check_skip, "dv_keep": _keep_and_window,'''
old = '\nCHECKS = {"dv_through": check_through, "dv_skip": check_skip, "dv_keep": check_keep,'
assert t.count(old) == 1
t = t.replace(old, NEW)
old = '          "dv_contact": check_contact,'
assert t.count(old) == 1
t = t.replace(old, '          "dv_contact": _contact_and_window,')
MUT = '''    ("contact on the shared counter", "dv_contact", "    lock inc dword ptr [r10 + 40]\\n",
     "    lock inc dword ptr [r10 + 32]\\n"),
'''
assert t.count(MUT) == 1, t.count(MUT)
t = t.replace(MUT, MUT + '''    # [AIR-DIVE-BRACE-W1 round 3] the slide window
    ("window never releases", "dv_keep", "    jb whold\\n", "    jmp whold\\n"),
    ("window releases at once", "dv_keep", "    jb whold\\n", "    nop\\n"),
    ("window not sticky", "dv_keep", "    lock or qword ptr [rbx], 1\\n", ""),
    ("window release uncounted", "dv_keep", "    lock inc dword ptr [r10 + 48]\\n", ""),
    ("window on x only", "dv_keep", "    addss xmm0, xmm1\\n    mov eax", "    mov eax"),
    ("window forgets xmm1 on release", "dv_keep",
     "    movdqu xmm1, xmmword ptr [rsp + 16]\\n    lea rsp, [rsp + 32]\\n    pop r9\\n",
     "    lea rsp, [rsp + 32]\\n    pop r9\\n"),
    ("window full table holds", "dv_keep", "    test rcx, rcx\\n    je wpass_out\\n",
     "    test rcx, rcx\\n    je whold\\n"),
    ("window ignores a released key", "dv_contact", "    xor rdx, 1\\n    cmp rdx, r9\\n    je wpass_out\\n",
     "    xor rdx, 1\\n    cmp rdx, r9\\n    nop\\n"),
    ("through never clears", "dv_through", "    mov qword ptr [r10 + rdx + 64], 2\\n", ""),
    ("through clears on a ground charge", "dv_through", "    je wclr_done\\n", "    nop\\n"),
    ("through clears the rider, not the mount", "dv_through", "    cmovne rcx, rax\\n", ""),
''')
p.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
print("ok")
