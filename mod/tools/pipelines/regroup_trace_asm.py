"""TEST-ONLY: four logger caves that say who lands a flying model and who flips its unit's stay-down flag (D23).

Never in a player's pack. Built only by ``build_pin_on_hit_probe.py --regroup-trace`` together with the
recorder ``pin_on_hit_probe.lua`` (cfg ``calls 1``), which installs them and writes the G lines.

THE QUESTION (docs/HISTORY.md REGROUP-1119): in a multi-model flyer unit that was ordered a short way off while
some models are held on the ground, the models that took off go into the landing approach (flight stage 4 / 5)
and fly back to the held ones; the unit flight controller's +8 ("stay down", 1 = stay down) flips 0 -> 1 at the
same moment. Which code does it?

STATIC READING (Warhammer3.exe 9.0.5, PE timestamp 0x6ae2a00b; this project's own read, the offsets are not
published anywhere):
* ``0x14303fab4`` ``rt_land``: the landing request (rcx = the entity's flight controller FC, rdx != 0 asks the
  approach, stage 4; rdx == 0 stage 5; at stage 2 it cancels the take-off request instead; at stage 1 it does
  nothing). Callers: 0x1430439e9 (the order "stay down", 0x1430439c0), 0x143050246 (the per-tick executor
  0x143050114, when the controller's +8 is 1), 0x143050dbc (0x143050d74: the model's target is a ground
  entity), 0x143050ecf (0x143050e44: the target unit is not flying).
* ``0x14304cea0`` ``rt_cancel``: the landing cancel (stage 1 -> 2, stage 4 / 5 -> 6). The per-tick executor calls
  it for every model every tick while the controller's +8 is 0, so only calls at stage 4 / 5 (a real cancel of
  a landing) are written to the ring; every call is counted.
* ``0x143084b10`` ``rt_target``: sets a command's target entity ([rcx+0x38] = rdx; rcx = the command, [rcx+8] its
  model); written only when the target changes. When the target is set it calls 0x143050d74 / 0x143050e44
  (return addresses 0x143084b84 / 0x143084b8e), which land the model next to a ground target.
* ``0x1430439c0`` ``rt_stay``: the order "stay down / fly" (rcx = the unit controller, rdx = an entity,
  r8b = stay down).
* ``0x143076060`` ``rt_order`` [second round]: gives one model the charge command (the only caller of the charge
  command's constructor 0x14305ade4 is 0x143076094 in this function; rcx = the model, nothing is created when
  its state +0x324 is above 1). Its only direct caller is a virtual-call stub (0x14312352e), so the entry keeps the
  next two stack qwords as well, to walk up to the code that orders the model.
* ``0x143123514`` ``rt_stub`` [third round]: the virtual method that calls 0x143076060 (rcx = the model,
  rdx = what 0x143076060 gets as its second argument); its return address ([rsp] at entry) is the unit-level code
  that gives the order, and the qword after it is kept too.
Offsets read by the caves: FC +0 = its entity (the state machine 0x14301b560 loads r10 = [FC]); FC +0x90 stage;
entity +0x104 airborne state, +0x324 state, +0x2e8 unit, +0x3e30 of the unit = its flight controller, +8 of
that = the stay-down flag; entity +0x58 -> +0x440 -> +0x98 the battle tick.

Buffer: header 64 bytes (+0 u32 mode, +8 magic, +16 u32 entries written, +24 four u32 call counters, one per
site, every call), ring at 64: SLOTS x 64-byte entries:
  +0 u64 rcx   +8 u64 entity (land / cancel: [rcx]; target: [rcx+8]; stay: rdx)   +16 u64 return address
  +24 u32 battle tick (0 when unreadable)   +28 u32 kind (1 land, 2 cancel, 3 target, 4 stay)
  +32 u64 rdx   +40 u64 aux (land / cancel: FC stage; target: the old target; stay: r8b)
  (order: +8 = rcx = the model, +16 = return address, +32 = [rsp + 8] and +40 = [rsp + 16] at entry)
  +48 u32 entity +0x104 (0xFFFFFFFF none)   +52 u32 entity +0x324 (0xFFFFFFFF none)
  +56 u32 the unit controller's +8 (0xFFFFFFFF: none)   +60 u32 seq + 1 (written last)

``python regroup_trace_asm.py [--write-site PATH]`` (keystone + unicorn + pefile) assembles the caves, checks every
pattern exactly once in the installed exe, runs the emulator cases and the mutants (each must be caught), and
writes the site table.
"""
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
import rolepath  # noqa: F401,E402 -- imported because it puts the role directories on sys.path

EXE = Path(r"D:/SteamLibrary/steamapps/common/Total War WARHAMMER III/Warhammer3.exe")
OWNER, FEATURE = "regroup_trace", "regroup_trace"
SITE_REQUIRE = "script/regroup_trace/regroup_trace_site"
MAGIC = b"RGTRACE1"
MODE_AT, MAGIC_AT, COUNT_AT, CALLS_AT = 0, 8, 16, 24
RING_AT, SLOTS, ENTRY = 64, 16384, 64
BYTES = RING_AT + SLOTS * ENTRY
BUF = 0x1122334455667788
FC_ENTITY, FC_STAGE = 0, 0x90
E_AIR, E_STATE, E_UNIT, E_BATTLE, B_TICKS, T_TICK = 0x104, 0x324, 0x2E8, 0x58, 0x440, 0x98
U_CTL, CTL_STAY = 0x3E30, 8
CMD_MODEL, CMD_TARGET = 8, 0x38
NONE32 = 0xFFFFFFFF
PUSHES = 7                     # flags rax rcx rdx r9 r10 r11 -> the return address is at [rsp + 56]

# name: (pattern, at, stolen bytes (whole instructions, no relative operand), exe address of the site)
SITES = {
    "rt_land": ("40 53 48 83 EC 20 8B 81 90 00 00 00 48 8B D9 83 F8 01", 0,
                "40 53 48 83 EC 20 8B 81 90 00 00 00", 0x14303FAB4),
    "rt_cancel": ("40 53 48 83 EC 20 48 8B D9 48 83 C1 78 E8 ?? ?? ?? ?? 84 C0", 0,
                  "40 53 48 83 EC 20 48 8B D9 48 83 C1 78", 0x14304CEA0),
    "rt_target": ("40 53 48 83 EC 20 48 8B 41 38 48 8B D9 48 3B C2", 0,
                  "40 53 48 83 EC 20 48 8B 41 38", 0x143084B10),
    "rt_stay": ("48 89 5C 24 08 57 48 83 EC 20 80 79 10 00 48 8B F9", 0,
                "48 89 5C 24 08 57 48 83 EC 20", 0x1430439C0),
    "rt_order": ("48 89 5C 24 08 57 48 83 EC 20 83 B9 24 03 00 00 01 48 8B FA", 0,
                 "48 89 5C 24 08 57 48 83 EC 20", 0x143076060),
    "rt_stub": ("48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18 57 48 83 EC 20 48 8B EA 48 8B D9 E8 ?? ?? ?? ?? "
                "8B 83 64 0B 00 00", 0,
                "48 89 5C 24 08 48 89 6C 24 10 48 89 74 24 18", 0x143123514),
}
KIND = {"rt_land": 1, "rt_cancel": 2, "rt_target": 3, "rt_stay": 4, "rt_order": 5, "rt_stub": 6}


def source(name, mutate=None):
    kind = KIND[name]
    ent = {1: "mov rax, qword ptr [rcx]", 2: "mov rax, qword ptr [rcx]",
           3: f"mov rax, qword ptr [rcx + {CMD_MODEL:#x}]", 4: "mov rax, rdx", 5: "mov rax, rcx",
           6: "mov rax, rcx"}[kind]
    guard = "test rcx, rcx\n    jz noent" if kind in (1, 2, 3, 5, 6) else "nop"
    aux = {1: f"mov eax, dword ptr [rcx + {FC_STAGE:#x}]\n    mov qword ptr [r11 + 40], rax",
           2: f"mov eax, dword ptr [rcx + {FC_STAGE:#x}]\n    mov qword ptr [r11 + 40], rax",
           3: f"mov rax, qword ptr [rcx + {CMD_TARGET:#x}]\n    mov qword ptr [r11 + 40], rax",
           4: "movzx eax, r8b\n    mov qword ptr [r11 + 40], rax",
           5: f"mov rax, qword ptr [rsp + {PUSHES * 8 + 8}]\n    mov qword ptr [r11 + 32], rax\n"
              f"    mov rax, qword ptr [rsp + {PUSHES * 8 + 16}]\n    mov qword ptr [r11 + 40], rax",
           6: f"mov rax, qword ptr [rsp + {PUSHES * 8 + 8}]\n    mov qword ptr [r11 + 40], rax"}[kind]
    filt = "nop"
    if kind == 2:       # only a real landing cancel (stage 4 or 5) goes to the ring
        filt = f"""mov eax, dword ptr [rcx + {FC_STAGE:#x}]
    sub eax, 4
    cmp eax, 1
    ja done"""
    elif kind == 3:     # only a change of target
        filt = f"""mov rax, qword ptr [rcx + {CMD_TARGET:#x}]
    cmp rax, rdx
    je done"""
    pre = "test rcx, rcx\n    jz done" if kind in (2, 3, 5, 6) else "nop"
    zero = "".join(f"    mov qword ptr [r11 + {o}], rax\n" for o in range(0, ENTRY, 8))
    s = f"""
    pushfq
    push rax
    push rcx
    push rdx
    push r9
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    lock inc dword ptr [r10 + {CALLS_AT + 4 * (kind - 1)}]
    {pre}
    {filt}
    mov r9d, 1
    lock xadd dword ptr [r10 + {COUNT_AT}], r9d
    mov r11d, r9d
    and r11d, {SLOTS - 1}
    shl r11, 6
    mov rax, {RING_AT}
    add r11, rax
    add r11, r10
    inc r9d
    xor eax, eax
{zero}    mov dword ptr [r11 + 28], {kind}
    mov qword ptr [r11], rcx
    mov qword ptr [r11 + 32], rdx
    mov rax, qword ptr [rsp + {PUSHES * 8}]
    mov qword ptr [r11 + 16], rax
    mov dword ptr [r11 + 48], {NONE32:#x}
    mov dword ptr [r11 + 52], {NONE32:#x}
    mov dword ptr [r11 + 56], {NONE32:#x}
    {guard}
    {aux}
    {ent}
    test rax, rax
    jz noent
    mov qword ptr [r11 + 8], rax
    mov ecx, dword ptr [rax + {E_AIR:#x}]
    mov dword ptr [r11 + 48], ecx
    mov ecx, dword ptr [rax + {E_STATE:#x}]
    mov dword ptr [r11 + 52], ecx
    mov rdx, qword ptr [rax + {E_UNIT:#x}]
    test rdx, rdx
    jz notick_unit
    mov rdx, qword ptr [rdx + {U_CTL:#x}]
    test rdx, rdx
    jz notick_unit
    mov ecx, dword ptr [rdx + {CTL_STAY}]
    mov dword ptr [r11 + 56], ecx
notick_unit:
    mov rdx, qword ptr [rax + {E_BATTLE:#x}]
    test rdx, rdx
    jz noent
    mov rdx, qword ptr [rdx + {B_TICKS:#x}]
    test rdx, rdx
    jz noent
    mov ecx, dword ptr [rdx + {T_TICK:#x}]
    mov dword ptr [r11 + 24], ecx
noent:
    mov dword ptr [r11 + 60], r9d
done:
    pop r11
    pop r10
    pop r9
    pop rdx
    pop rcx
    pop rax
    popfq
"""
    return _mutate(s, mutate)


def _mutate(s, mutate):
    if mutate:
        old, new = mutate
        if s.count(old) != 1:
            raise SystemExit(f"mutant: {old!r} found {s.count(old)} times")
        s = s.replace(old, new)
    return s


def assemble(name, mutate=None):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_64
    code = bytes(Ks(KS_ARCH_X86, KS_MODE_64).asm(source(name, mutate), 0x1000)[0])
    if code.count(struct.pack("<Q", BUF)) != 1:
        raise SystemExit(f"{name}: the buffer placeholder must appear exactly once")
    return code


# --- emulator ----------------------------------------------------------------
CODE, B, STACK, OBJ = 0x100000, 0x200000, 0x2000000, 0x3000000
RET = 0x143050246
STK1, STK2 = 0x143123533, 0x1430ABCDE      # the next two stack qwords of the emulated entry (rt_order logs them)
TICK = 4321


def _machine(code):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
    mu = Uc(UC_ARCH_X86, UC_MODE_64)
    mu.mem_map(CODE, 0x10000)
    mu.mem_map(B, ((BYTES + 0xFFFF) // 0x10000) * 0x10000)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(OBJ, 0x100000)
    mu.mem_write(CODE, code.replace(struct.pack("<Q", BUF), struct.pack("<Q", B)))
    return mu


def _put(mu, at, fmt, value):
    mu.mem_write(at, struct.pack(fmt, value))


def _world(mu, ctl8=1, air=2, state=5, stage=4, tick=TICK, unit=True, ctl=True, battle=True):
    """entity E (with an FC, a unit, a controller, a battle); returns (fc, entity, command, target, ctl)."""
    fc, ent, cmd, tgt, unit_o, ctl_o = (OBJ + 0x10000 * i for i in range(1, 7))
    battle_o, ticks_o = OBJ + 0x70000, OBJ + 0x78000
    _put(mu, fc + FC_ENTITY, "<Q", ent)
    _put(mu, fc + FC_STAGE, "<I", stage)
    _put(mu, ent + E_AIR, "<I", air)
    _put(mu, ent + E_STATE, "<I", state)
    _put(mu, ent + E_UNIT, "<Q", unit_o if unit else 0)
    _put(mu, unit_o + U_CTL, "<Q", ctl_o if ctl else 0)
    _put(mu, ctl_o + CTL_STAY, "<I", ctl8)
    _put(mu, ent + E_BATTLE, "<Q", battle_o if battle else 0)
    _put(mu, battle_o + B_TICKS, "<Q", ticks_o)
    _put(mu, ticks_o + T_TICK, "<I", tick)
    _put(mu, cmd + CMD_MODEL, "<Q", ent)
    _put(mu, cmd + CMD_TARGET, "<Q", 0)
    return fc, ent, cmd, tgt, ctl_o


def _run(mu, code, regs_in, flags):
    from unicorn import x86_const as X
    names = ("rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "r8", "r9", "r10", "r11",
             "r12", "r13", "r14", "r15", "rsp", "eflags")
    vals = {n: 0x5150 + i for i, n in enumerate(names)}
    vals["eflags"] = flags
    vals.update(regs_in)
    for n, v in vals.items():
        mu.reg_write(getattr(X, "UC_X86_REG_" + n.upper()), v)
    mu.emu_start(CODE, CODE + len(code), count=10_000)
    return [n for n, v in vals.items() if mu.reg_read(getattr(X, "UC_X86_REG_" + n.upper())) != v]


def _u32(mu, at):
    return struct.unpack("<I", bytes(mu.mem_read(at, 4)))[0]


def _call(name, code, mode, regs, world_kw=None, seq0=7):
    """per flags value: (changed registers, ring entry bytes, entries written, this site's call counter, objects)"""
    out = []
    for flags in (0x202, 0x8D7):
        mu = _machine(code)
        objs = _world(mu, **(world_kw or {}))
        mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
        mu.mem_write(B + COUNT_AT, struct.pack("<I", seq0))
        rsp = STACK + 0x4000
        mu.mem_write(rsp, struct.pack("<QQQ", RET, STK1, STK2))
        r = regs(*objs)
        r["rsp"] = rsp
        changed = _run(mu, code, r, flags)
        entry = bytes(mu.mem_read(B + RING_AT + (seq0 % SLOTS) * ENTRY, ENTRY))
        out.append((changed, entry, _u32(mu, B + COUNT_AT) - seq0, _u32(mu, B + CALLS_AT + 4 * (KIND[name] - 1)),
                    objs))
    return out


def _regs_for(name):
    def regs(fc, ent, cmd, tgt, ctl):
        if name == "rt_land":
            return {"rcx": fc, "rdx": 0x77}
        if name == "rt_cancel":
            return {"rcx": fc, "rdx": 0x66}
        if name == "rt_target":
            return {"rcx": cmd, "rdx": tgt}
        if name == "rt_order":
            return {"rcx": ent, "rdx": 0x55}
        if name == "rt_stub":
            return {"rcx": ent, "rdx": 0x56}
        return {"rcx": ctl, "rdx": ent, "r8": 0x1}
    return regs


def _check_one(name, code):
    fails = []
    kind = KIND[name]
    regs = _regs_for(name)
    cases = [("normal", 1, {}), ("off", 0, {}), ("no ctl", 1, {"ctl": False}), ("no unit", 1, {"unit": False}),
             ("no battle", 1, {"battle": False}), ("stay0", 1, {"ctl8": 0})]
    if name == "rt_cancel":
        cases += [("stage 5", 1, {"stage": 5}), ("stage 3 filtered", 1, {"stage": 3}),
                  ("stage 6 filtered", 1, {"stage": 6}), ("stage 0 filtered", 1, {"stage": 0})]
    for label, mode, wk in cases:
        for (changed, entry, written, calls, objs) in _call(name, code, mode, regs, wk):
            fc, ent, cmd, tgt, ctl = objs
            if changed:
                fails.append(f"{name} {label}: registers changed {changed}")
            filtered = name == "rt_cancel" and wk.get("stage", 4) not in (4, 5)
            if mode == 0:
                if written or calls or any(entry):
                    fails.append(f"{name} {label}: logged in mode 0")
                continue
            if calls != 1:
                fails.append(f"{name} {label}: call counter {calls}, want 1")
            if filtered:
                if written or any(entry):
                    fails.append(f"{name} {label}: a filtered call was written")
                continue
            if written != 1:
                fails.append(f"{name} {label}: {written} entries written, want 1")
                continue
            got = struct.unpack_from("<QQQIIQQIIII", entry, 0)
            rcx = {"rt_land": fc, "rt_cancel": fc, "rt_target": cmd, "rt_stay": ctl, "rt_order": ent,
                   "rt_stub": ent}[name]
            rdx = {"rt_land": 0x77, "rt_cancel": 0x66, "rt_target": tgt, "rt_stay": ent, "rt_order": STK1,
                   "rt_stub": 0x56}[name]
            aux = {"rt_land": wk.get("stage", 4), "rt_cancel": wk.get("stage", 4), "rt_target": 0, "rt_stay": 1,
                   "rt_order": STK2, "rt_stub": STK1}[name]
            unit_ok = wk.get("unit", True) and wk.get("ctl", True)
            exp = (rcx, ent, RET, 0 if not wk.get("battle", True) else TICK, kind, rdx, aux, 2, 5,
                   wk.get("ctl8", 1) if unit_ok else NONE32, 7 + 1)
            if got != exp:
                fails.append(f"{name} {label}: entry {got} want {exp}")
    if name == "rt_target":      # the same target again: counted, not written
        for (changed, entry, written, calls, objs) in _call(
                name, code, 1, lambda fc, ent, cmd, tgt, ctl: {"rcx": cmd, "rdx": 0}):
            if written or calls != 1 or any(entry):
                fails.append(f"rt_target unchanged target: written {written} calls {calls}")
    if name in ("rt_target", "rt_cancel", "rt_land", "rt_order", "rt_stub"):   # a null rcx must not crash
        for (changed, entry, written, calls, objs) in _call(
                name, code, 1, lambda fc, ent, cmd, tgt, ctl: {"rcx": 0, "rdx": 0}):
            want = 1 if name == "rt_land" else 0
            if changed or written != want:
                fails.append(f"{name} null rcx: written {written} (want {want}) changed {changed}")
    return fails


def check(mutate=None, which=None):
    """[failure] of the caves on synthetic calls (``which`` is built from the ``mutate`` (old, new) edit)."""
    fails = []
    for name in SITES:
        if which not in (None, name):
            continue
        try:
            fails += _check_one(name, assemble(name, mutate if which == name else None))
        except Exception as err:     # a broken cave that faults in the emulator is a caught cave
            fails.append(f"{name}: the emulator faulted: {err}")
    return fails


MUTANTS = (
    ("rt_land", "mov dword ptr [r11 + 28], 1", "mov dword ptr [r11 + 28], 2"),
    ("rt_land", "mov rax, qword ptr [rcx]", "mov rax, qword ptr [rcx + 8]"),
    ("rt_land", "mov rax, qword ptr [rsp + 56]", "mov rax, qword ptr [rsp + 48]"),
    ("rt_land", "mov dword ptr [r11 + 56], ecx\nnotick_unit:", "mov dword ptr [r11 + 52], ecx\nnotick_unit:"),
    ("rt_land", "pop r11\n    pop r10\n    pop r9", "pop r11\n    pop r9\n    pop r10"),
    ("rt_land", "lock inc dword ptr [r10 + 24]", "lock inc dword ptr [r10 + 28]"),
    ("rt_land", "mov ecx, dword ptr [rax + 0x104]", "mov ecx, dword ptr [rax + 0x324]"),
    ("rt_cancel", "sub eax, 4\n    cmp eax, 1\n    ja done", "sub eax, 3\n    cmp eax, 1\n    ja done"),
    ("rt_cancel", "sub eax, 4\n    cmp eax, 1\n    ja done", "sub eax, 4\n    cmp eax, 2\n    ja done"),
    ("rt_cancel", "mov dword ptr [r11 + 28], 2", "mov dword ptr [r11 + 28], 1"),
    ("rt_target", "cmp rax, rdx\n    je done", "cmp rax, rdx\n    jne done"),
    ("rt_target", "mov rax, qword ptr [rcx + 0x8]", "mov rax, qword ptr [rcx]"),
    ("rt_target", "mov rax, qword ptr [rcx + 0x38]\n    mov qword ptr [r11 + 40], rax",
     "mov rax, rdx\n    mov qword ptr [r11 + 40], rax"),
    ("rt_stay", "movzx eax, r8b", "mov eax, 0"),
    ("rt_stay", "mov rax, rdx\n    test rax, rax", "mov rax, rcx\n    test rax, rax"),
    ("rt_stay", "mov dword ptr [r11 + 60], r9d", "mov dword ptr [r11 + 60], 0"),
    ("rt_order", "mov rax, qword ptr [rsp + 64]", "mov rax, qword ptr [rsp + 56]"),
    ("rt_order", "mov rax, qword ptr [rsp + 72]", "mov rax, qword ptr [rsp + 64]"),
    ("rt_order", "mov rax, rcx\n    test rax, rax", "mov rax, rdx\n    test rax, rax"),
    ("rt_order", "mov dword ptr [r11 + 28], 5", "mov dword ptr [r11 + 28], 4"),
    ("rt_stub", "mov dword ptr [r11 + 28], 6", "mov dword ptr [r11 + 28], 5"),
    ("rt_stub", "mov rax, qword ptr [rsp + 64]\n    mov qword ptr [r11 + 40], rax",
     "mov rax, qword ptr [rsp + 72]\n    mov qword ptr [r11 + 40], rax"),
    ("rt_stub", "mov rax, rcx\n    test rax, rax", "mov rax, rdx\n    test rax, rax"),
)


def negative_controls():
    """[mutant] whose broken cave passed every case (must be empty)."""
    return [m for m in MUTANTS if not check(m[1:], which=m[0])]


def _regex(pattern):
    return re.compile(b"".join(b"." if t == "??" else re.escape(bytes([int(t, 16)]))
                               for t in pattern.split()), re.S)


def check_exe(exe_path):
    """{cave: virtual address}: each pattern exactly once in the exe's code with the stolen bytes at the
    site and at the address of the static read; refuses otherwise."""
    import pefile
    pe = pefile.PE(str(exe_path), fast_load=True)
    code = [(pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress, s.get_data())
            for s in pe.sections if s.Characteristics & 0x20000000]
    found = {}
    for name, (pattern, at, stolen, want_va) in SITES.items():
        want = bytes.fromhex(stolen.replace(" ", ""))
        hits = [va + m.start() + at for va, data in code for m in _regex(pattern).finditer(data)
                if data[m.start() + at:m.start() + at + len(want)] == want]
        if hits != [want_va]:
            raise SystemExit(f"[regroup_trace] REFUSING: {name} found at {[hex(h) for h in hits]}, "
                             f"want {want_va:#x} (another build?)")
        found[name] = hits[0]
    return found


def _template(code):
    out, i, mark = [], 0, struct.pack("<Q", BUF)
    while i < len(code):
        if code[i:i + 8] == mark:
            out.append("{buf:8}")
            i += 8
        else:
            out.append(f"{code[i]:02X}")
            i += 1
    return " ".join(out)


def site_lua(codes):
    lines = ["-- TEST-ONLY, generated by tools/pipelines/regroup_trace_asm.py; never in a player's pack",
             "return {", f"    owner = '{OWNER}', feature = '{FEATURE}',", "    entries = {"]
    for n in SITES:
        pattern, at, stolen, _va = SITES[n]
        lines += [f"        {{ name = '{n}', feature = '{FEATURE}', kind = 'cave',",
                  f"          pattern = '{pattern}', at = {at}, expect = '{stolen}',",
                  f"          bytes = '{_template(codes[n])}' }},"]
    lines += ["    },", "    caves = { " + ", ".join(f"'{n}'" for n in SITES) + " },",
              f"    layout = {{ bytes = {BYTES}, mode_at = {MODE_AT}, magic_at = {MAGIC_AT}, magic = '{MAGIC.decode()}',",
              f"        count_at = {COUNT_AT}, calls_at = {CALLS_AT}, ring_at = {RING_AT}, slots = {SLOTS}, "
              f"entry = {ENTRY} }},", "}"]
    return "\n".join(lines) + "\n"


def build_site():
    """(site Lua text, report): assemble, emulator check, negative controls; refuses on any failure."""
    codes = {n: assemble(n) for n in SITES}
    fails = check()
    survivors = [] if fails else negative_controls()
    if fails or survivors:
        raise SystemExit("[regroup_trace] REFUSING: " + "; ".join(fails + [f"mutant not caught: {m}" for m in survivors]))
    return site_lua(codes), (f"caves {', '.join(f'{n} {len(c)} B' for n, c in codes.items())}; "
                             f"emulator PASS; {len(MUTANTS)} mutants, each caught")


def main(argv):
    found = check_exe(EXE)
    text, report = build_site()
    print(report + "; exe sites " + ", ".join(f"{k} {v:#x}" for k, v in found.items()))
    if "--write-site" in argv:
        out = Path(argv[argv.index("--write-site") + 1])
        out.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
