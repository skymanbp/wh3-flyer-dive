"""TEST-ONLY: logger caves that say who lands a flying model and who flips its unit's stay-down flag (D23).

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
* ``0x142f7f706`` ``rt_task1`` / ``0x142f8ffc4`` ``rt_task2`` [fourth round, D23-RUNS-1120]: inside the two
  per-model task handlers 0x142f7f600 / 0x142f8ff54 (slots 1 and 2 of the vtable 0x143ad9690; one qword reference
  each), just before they hand the model the charge command through [vtable + 0x4f8] (the calls that return to
  0x142f7f71c / 0x142f8ffda, the rt_stub return addresses). Both start ``push rbx; sub rsp, 0x60`` and keep the
  task in rbx from ``mov rbx, rcx`` (0x142f7f60a / 0x142f8ff61); nothing between that and the site writes rbx
  (checked by decoding, ``decode_check``). Stolen: ``mov rdx,[rbx+0x10]; mov rcx,[rdx+8]; lea rdx,[rsp+0x20]``.
  Task layout (constructor 0x142f6b770 over the base 0x14325875c, read): +0 vtable, +8 u32 serial (the battle's
  counter +0x440 -> +0x9c, the same counter that numbers the unit's orders), +0x10 the model's task slot
  (entity +0x490; slot +8 = the model), +0x18 [slot +0x10], +0x40..+0x77 a copy of the 0x38-byte parameters
  (0x142da511c), so +0x58 = parameter +0x18 (the target entity, ref-counted at +0xa60), +0x68 = parameter +0x28,
  +0x74 = parameter +0x34 (flags: 4 = act at once, 8 = skip the distance test), +0x80 u8 done, +0x84 f32 due time.
* ``0x143077c68`` ``rt_mktask`` [fourth round]: the only direct caller of that constructor (0x143077c9b) sits in
  this entity method (rcx = the model, rdx = the parameters; it builds the task at entity +0x4a8 = slot + 0x18).
  It is a slot of many entity vtables, so its return address is the code that creates the task.
Offsets read by the caves: FC +0 = its entity (the state machine 0x14301b560 loads r10 = [FC]); FC +0x90 stage;
entity +0x104 airborne state, +0x324 state, +0x2e8 unit, +0x3e30 of the unit = its flight controller, +8 of
that = the stay-down flag; entity +0x58 -> +0x440 -> +0x98 the battle tick.

Buffer: header 64 bytes (+0 u32 mode, +8 magic, +16 u32 entries written, +24 nine u32 call counters, one per
site, every call), ring at 64: SLOTS x 128-byte entries:
  +0 u64 rcx   +8 u64 entity (land / cancel: [rcx]; target: [rcx+8]; stay: rdx)   +16 u64 return address
  +24 u32 battle tick (0 when unreadable)   +28 u32 kind (1 land, 2 cancel, 3 target, 4 stay, 5 order, 6 stub,
  7 task1, 8 task2, 9 mktask)
  +32 u64 rdx   +40 u64 aux (land / cancel: FC stage; target: the old target; stay: r8b)
  (order: +8 = rcx = the model, +16 = return address, +32 = [rsp + 8] and +40 = [rsp + 16] at entry)
  +48 u32 entity +0x104 (0xFFFFFFFF none)   +52 u32 entity +0x324 (0xFFFFFFFF none)
  +56 u32 the unit controller's +8 (0xFFFFFFFF: none)   +60 u32 seq + 1 (written last)
  task1 / task2: +0 = the task (rbx), +8 = the model [[task+0x10]+8], +16 = the handler's return address
  ([rsp + 0x68] at the site), +32 = [task+0x10], +40 = [task] (vtable); +64 [task+0x18], +72 [task+0x58],
  +80 [task+0x68], +88 u32 [task+0x74], +92 u32 [task+0x80], +96 u32 [task+0x84], +100 u32 [task+8]
  mktask: +0 = +8 = the model (rcx), +16 = return address, +32 = the parameters (rdx), +40 = [rdx+0x18];
  +64..+119 the parameters' seven qwords [rdx] .. [rdx+0x30] (none when rdx is null)
  every other kind: +64..+127 zero

``python regroup_trace_asm.py [--write-site PATH]`` (keystone + unicorn + pefile + capstone) assembles the caves,
checks every pattern exactly once in the installed exe, decodes the sites (``decode_check``), runs the emulator
cases and the mutants (each must be caught), and writes the site table.
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
RING_AT, SLOTS, ENTRY = 64, 16384, 128
BYTES = RING_AT + SLOTS * ENTRY
BUF = 0x1122334455667788
FC_ENTITY, FC_STAGE = 0, 0x90
E_AIR, E_STATE, E_UNIT, E_BATTLE, B_TICKS, T_TICK = 0x104, 0x324, 0x2E8, 0x58, 0x440, 0x98
U_CTL, CTL_STAY = 0x3E30, 8
CMD_MODEL, CMD_TARGET = 8, 0x38
NONE32 = 0xFFFFFFFF
PUSHES = 7                     # flags rax rcx rdx r9 r10 r11 -> the return address is at [rsp + 56]
# [fourth round] the task (rt_task1 / rt_task2) and its creator (rt_mktask)
T_SLOT, SLOT_ENT, T_SERIAL = 0x10, 8, 8
T_Q = (0x18, 0x58, 0x68)              # qwords -> ext +64, +72, +80
T_D = (0x74, 0x80, 0x84)              # dwords -> ext +88, +92, +96 (then the serial at +100)
HANDLER_RET = 0x68                    # push rbx; sub rsp, 0x60 -> the handler's return address at [rsp + 0x68]
P_QWORDS, P_TARGET = 7, 0x18          # the 0x38-byte parameters (copied by 0x142da511c); +0x18 = target entity
EXT = 64
TASK_VT = 0x143AD9690
TASK_KINDS = (7, 8)
# [D42, ORDER-DROP-1121] rt_pop: the order queue's only pop 0x142f5c180 (static read, order-drop-1121 lane). Entry:
# rcx = the ring at unit+0x288 (the stolen ``mov eax, [rcx+0x2d04]`` reads the head = unit+0x2f8c), the unit at
# [rcx-0x10] (the queue manager unit+0x278 holds it), the order being popped at rcx + head*0x120 + 0x18 (its vtable
# first; +0x39 a flag), 40 slots; the unit's override stack: count unit+0x3310 (at most 2), entries unit+0x3300,
# each override's state machine state at +0x88. Entry: +0 ring, +8 order +0x39, +16 the caller, +32 the order's
# vtable (0: head out of range), +40 unit, +48 override count, +52 top override vtable (low 32), +56 its state.
POP_UNIT, POP_HEAD, POP_STRIDE, POP_ORDER, POP_FLAG, POP_SLOTS = 0x10, 0x2D04, 0x120, 0x18, 0x39, 40
U_OV_ARRAY, U_OV_COUNT, U_OV_MAX, OV_STATE = 0x3300, 0x3310, 2, 0x88
POP_KIND = 10

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
    "rt_task1": ("48 8D 53 40 48 8D 4C 24 20 E8 ?? ?? ?? ?? 48 8B 53 10 48 8B 4A 08 48 8D 54 24 20 48 8B 01 "
                 "FF 90 F8 04 00 00 C6 83 80 00 00 00 01 48 83 C4 60 5B C3", 14,
                 "48 8B 53 10 48 8B 4A 08 48 8D 54 24 20", 0x142F7F706),
    "rt_task2": ("48 8D 51 40 48 8D 4C 24 20 E8 ?? ?? ?? ?? 48 8B 53 10 48 8B 4A 08 48 8D 54 24 20 48 8B 01 "
                 "FF 90 F8 04 00 00 C6 83 80 00 00 00 01 48 8B 4B 18", 14,
                 "48 8B 53 10 48 8B 4A 08 48 8D 54 24 20", 0x142F8FFC4),
    "rt_mktask": ("48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 48 8D B1 90 04 00 00 48 8B D9 48 8B CE 48 8B FA "
                  "E8 ?? ?? ?? ?? 48 8D 4E 18 48 85 C9 74 0B 4C 8B C7 48 8B D6 E8 ?? ?? ?? ?? F6 47 34 04", 0,
                  "48 89 5C 24 08 48 89 74 24 10", 0x143077C68),
    "rt_pop": ("40 53 48 83 EC 20 8B 81 04 2D 00 00 48 8B D9", 0,
               "40 53 48 83 EC 20 8B 81 04 2D 00 00", 0x142F5C180),
}
KIND = {"rt_land": 1, "rt_cancel": 2, "rt_target": 3, "rt_stay": 4, "rt_order": 5, "rt_stub": 6,
        "rt_task1": 7, "rt_task2": 8, "rt_mktask": 9, "rt_pop": POP_KIND}
# decode_check: per task site, (handler start, the "mov rbx, rcx", the return address of the charge-command call)
TASK_SITES = {"rt_task1": (0x142F7F600, 0x142F7F60A, 0x142F7F71C),
              "rt_task2": (0x142F8FF54, 0x142F8FF61, 0x142F8FFDA)}
TASK_CTOR, TASK_CTOR_CALL, TASK_HANDLERS = 0x142F6B770, 0x143077C9B, (0x142F7F600, 0x142F8FF54)


def _task_aux():
    """task1 / task2: the task's fields into +32, +40 and the extension (rbx = the task, checked non-null)."""
    s = [f"mov rax, qword ptr [rbx + {T_SLOT:#x}]", "mov qword ptr [r11 + 32], rax",
         "mov rax, qword ptr [rbx]", "mov qword ptr [r11 + 40], rax"]
    for i, off in enumerate(T_Q):
        s += [f"mov rax, qword ptr [rbx + {off:#x}]", f"mov qword ptr [r11 + {EXT + 8 * i}], rax"]
    for i, off in enumerate(T_D + (T_SERIAL,)):
        s += [f"mov eax, dword ptr [rbx + {off:#x}]", f"mov dword ptr [r11 + {EXT + 24 + 4 * i}], eax"]
    return "\n    ".join(s)


def _mktask_aux():
    """mktask: rdx = the parameters (may be null): [rdx+0x18] into +40, the seven qwords into the extension."""
    s = ["test rdx, rdx", "jz noparams", f"mov rax, qword ptr [rdx + {P_TARGET:#x}]", "mov qword ptr [r11 + 40], rax"]
    for i in range(P_QWORDS):
        s += [f"mov rax, qword ptr [rdx + {8 * i:#x}]", f"mov qword ptr [r11 + {EXT + 8 * i}], rax"]
    return "\n    ".join(s) + "\nnoparams:"


def _pop_aux():
    """[D42] rt_pop's fields (rcx = the ring); rax rcx rdx only (r9 = the serial, r10 / r11 = buffer / entry)."""
    return f"""mov qword ptr [r11 + 32], 0
    mov rdx, qword ptr [rcx - {POP_UNIT:#x}]
    mov qword ptr [r11 + 40], rdx
    mov eax, dword ptr [rcx + {POP_HEAD:#x}]
    cmp eax, {POP_SLOTS}
    jae pop_noorder
    imul eax, eax, {POP_STRIDE:#x}
    add rax, rcx
    mov rcx, qword ptr [rax + {POP_ORDER:#x}]
    mov qword ptr [r11 + 32], rcx
    movzx ecx, byte ptr [rax + {POP_ORDER + POP_FLAG:#x}]
    mov qword ptr [r11 + 8], rcx
pop_noorder:
    test rdx, rdx
    jz pop_end
    mov eax, dword ptr [rdx + {U_OV_COUNT:#x}]
    mov dword ptr [r11 + 48], eax
    dec eax
    cmp eax, {U_OV_MAX - 1}
    ja pop_end
    mov rax, qword ptr [rdx + rax*8 + {U_OV_ARRAY:#x}]
    test rax, rax
    jz pop_end
    mov rcx, qword ptr [rax]
    mov dword ptr [r11 + 52], ecx
    mov ecx, dword ptr [rax + {OV_STATE:#x}]
    mov dword ptr [r11 + 56], ecx
pop_end:"""


def source(name, mutate=None):
    kind = KIND[name]
    task = kind in TASK_KINDS
    ent = {1: "mov rax, qword ptr [rcx]", 2: "mov rax, qword ptr [rcx]",
           3: f"mov rax, qword ptr [rcx + {CMD_MODEL:#x}]", 4: "mov rax, rdx", 5: "mov rax, rcx",
           6: "mov rax, rcx", 9: "mov rax, rcx", POP_KIND: "xor eax, eax"}.get(kind) or (
        f"mov rax, qword ptr [rbx + {T_SLOT:#x}]\n    test rax, rax\n    jz noent\n"
        f"    mov rax, qword ptr [rax + {SLOT_ENT}]")
    guard = "test rcx, rcx\n    jz noent" if kind in (1, 2, 3, 5, 6, 9, POP_KIND) else (
        "test rbx, rbx\n    jz noent" if task else "nop")
    aux = {1: f"mov eax, dword ptr [rcx + {FC_STAGE:#x}]\n    mov qword ptr [r11 + 40], rax",
           2: f"mov eax, dword ptr [rcx + {FC_STAGE:#x}]\n    mov qword ptr [r11 + 40], rax",
           3: f"mov rax, qword ptr [rcx + {CMD_TARGET:#x}]\n    mov qword ptr [r11 + 40], rax",
           4: "movzx eax, r8b\n    mov qword ptr [r11 + 40], rax",
           5: f"mov rax, qword ptr [rsp + {PUSHES * 8 + 8}]\n    mov qword ptr [r11 + 32], rax\n"
              f"    mov rax, qword ptr [rsp + {PUSHES * 8 + 16}]\n    mov qword ptr [r11 + 40], rax",
           6: f"mov rax, qword ptr [rsp + {PUSHES * 8 + 8}]\n    mov qword ptr [r11 + 40], rax",
           7: _task_aux(), 8: _task_aux(), 9: _mktask_aux(), POP_KIND: _pop_aux()}[kind]
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
    pre = "test rcx, rcx\n    jz done" if kind in (2, 3, 5, 6, 9, POP_KIND) else ("test rbx, rbx\n    jz done" if task else "nop")
    zero = "".join(f"    mov qword ptr [r11 + {o}], rax\n" for o in range(0, ENTRY, 8))
    me = "rbx" if task else "rcx"                                     # +0: the task itself at the task sites
    ret = PUSHES * 8 + (HANDLER_RET if task else 0)                   # mid-function: the handler's return address
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
    shl r11, {ENTRY.bit_length() - 1}
    mov rax, {RING_AT}
    add r11, rax
    add r11, r10
    inc r9d
    xor eax, eax
{zero}    mov dword ptr [r11 + 28], {kind}
    mov qword ptr [r11], {me}
    mov qword ptr [r11 + 32], rdx
    mov rax, qword ptr [rsp + {ret}]
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
RET_H = 0x142F6B847                        # the task handler's own return address, at [rsp + 0x68] of the site
STK1, STK2 = 0x143123533, 0x1430ABCDE      # the next two stack qwords of the emulated entry (rt_order logs them)
TICK = 4321
T_VALS = (0x1818181818, None, 0x6868686868)   # [task+0x18], [task+0x58] (= the target), [task+0x68]
D_VALS = (0x4, 0x1, 0x41200000, 0x3344)        # [task+0x74], [task+0x80], [task+0x84], [task+8]
P_VALS = tuple(0x7000 + 0x111 * i for i in range(P_QWORDS))   # the parameters' qwords ([+0x18] = the target)


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


def _world(mu, ctl8=1, air=2, state=5, stage=4, tick=TICK, unit=True, ctl=True, battle=True, slot=True):
    """entity E (with an FC, a unit, a controller, a battle), a task on it and the parameters of a new task;
    returns {fc, ent, cmd, tgt, ctl, unit, task, slot, params}."""
    fc, ent, cmd, tgt, unit_o, ctl_o = (OBJ + 0x10000 * i for i in range(1, 7))
    battle_o, ticks_o = OBJ + 0x70000, OBJ + 0x78000
    task, slot_o, params = OBJ + 0x80000, OBJ + 0x88000, OBJ + 0x90000
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
    _put(mu, task, "<Q", TASK_VT)
    _put(mu, task + T_SLOT, "<Q", slot_o if slot else 0)
    _put(mu, slot_o + SLOT_ENT, "<Q", ent)
    for off, v in zip(T_Q, T_VALS):
        _put(mu, task + off, "<Q", tgt if v is None else v)
    for off, v in zip(T_D + (T_SERIAL,), D_VALS):
        _put(mu, task + off, "<I", v)
    for i, v in enumerate(P_VALS):
        _put(mu, params + 8 * i, "<Q", tgt if 8 * i == P_TARGET else v)
    return dict(fc=fc, ent=ent, cmd=cmd, tgt=tgt, ctl=ctl_o, unit=unit_o, task=task, slot=slot_o, params=params)


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
        mu.mem_write(rsp + HANDLER_RET, struct.pack("<Q", RET_H))
        r = regs(objs)
        r["rsp"] = rsp
        changed = _run(mu, code, r, flags)
        entry = bytes(mu.mem_read(B + RING_AT + (seq0 % SLOTS) * ENTRY, ENTRY))
        out.append((changed, entry, _u32(mu, B + COUNT_AT) - seq0, _u32(mu, B + CALLS_AT + 4 * (KIND[name] - 1)),
                    objs))
    return out


def _regs_for(name):
    def regs(o):
        if name == "rt_land":
            return {"rcx": o["fc"], "rdx": 0x77}
        if name == "rt_cancel":
            return {"rcx": o["fc"], "rdx": 0x66}
        if name == "rt_target":
            return {"rcx": o["cmd"], "rdx": o["tgt"]}
        if name == "rt_order":
            return {"rcx": o["ent"], "rdx": 0x55}
        if name == "rt_stub":
            return {"rcx": o["ent"], "rdx": 0x56}
        if name in ("rt_task1", "rt_task2"):     # rcx / rdx hold whatever the handler left there
            return {"rbx": o["task"], "rcx": 0x9999, "rdx": 0x8888}
        if name == "rt_mktask":
            return {"rcx": o["ent"], "rdx": o["params"]}
        return {"rcx": o["ctl"], "rdx": o["ent"], "r8": 0x1}
    return regs


def _expect(name, o, wk, regs):
    """the whole 128-byte entry the cave must write for this call"""
    kind = KIND[name]
    ent = o["ent"]
    if kind in TASK_KINDS and not wk.get("slot", True):
        ent = 0
    rcx = {"rt_land": o["fc"], "rt_cancel": o["fc"], "rt_target": o["cmd"], "rt_stay": o["ctl"], "rt_order": ent,
           "rt_stub": ent, "rt_task1": o["task"], "rt_task2": o["task"], "rt_mktask": o["ent"]}[name]
    params = regs.get("rdx", 0) if name == "rt_mktask" else 0
    rdx = {"rt_land": 0x77, "rt_cancel": 0x66, "rt_target": o["tgt"], "rt_stay": o["ent"], "rt_order": STK1,
           "rt_stub": 0x56, "rt_task1": o["slot"] if wk.get("slot", True) else 0,
           "rt_mktask": params}
    rdx["rt_task2"] = rdx["rt_task1"]
    aux = {"rt_land": wk.get("stage", 4), "rt_cancel": wk.get("stage", 4), "rt_target": 0, "rt_stay": 1,
           "rt_order": STK2, "rt_stub": STK1, "rt_task1": TASK_VT, "rt_task2": TASK_VT,
           "rt_mktask": o["tgt"] if params else 0}[name]
    unit_ok = wk.get("unit", True) and wk.get("ctl", True)
    if ent:
        tail = (0 if not wk.get("battle", True) else TICK, kind, rdx[name], aux, 2, 5,
                wk.get("ctl8", 1) if unit_ok else NONE32, 7 + 1)
    else:
        tail = (0, kind, rdx[name], aux, NONE32, NONE32, NONE32, 7 + 1)
    head = struct.pack("<QQQIIQQIIII", rcx, ent, RET_H if kind in TASK_KINDS else RET, *tail)
    if kind in TASK_KINDS:
        q = [o["tgt"] if v is None else v for v in T_VALS]
        ext = struct.pack("<QQQIIII", *q, *D_VALS)
    elif kind == 9 and params:
        ext = struct.pack("<7Q", *[o["tgt"] if 8 * i == P_TARGET else v for i, v in enumerate(P_VALS)])
    else:
        ext = b""
    return head + ext + bytes(ENTRY - len(head) - len(ext))


def _check_one(name, code):
    fails = []
    kind = KIND[name]
    regs = _regs_for(name)
    cases = [("normal", 1, {}), ("off", 0, {}), ("no ctl", 1, {"ctl": False}), ("no unit", 1, {"unit": False}),
             ("no battle", 1, {"battle": False}), ("stay0", 1, {"ctl8": 0})]
    if name == "rt_cancel":
        cases += [("stage 5", 1, {"stage": 5}), ("stage 3 filtered", 1, {"stage": 3}),
                  ("stage 6 filtered", 1, {"stage": 6}), ("stage 0 filtered", 1, {"stage": 0})]
    if kind in TASK_KINDS:
        cases += [("no slot", 1, {"slot": False})]
    variants = [(label, mode, wk, regs) for label, mode, wk in cases]
    if name == "rt_mktask":          # no parameters: the entry without them
        variants.append(("no params", 1, {}, lambda o: {"rcx": o["ent"], "rdx": 0}))
    for label, mode, wk, rg in variants:
        for (changed, entry, written, calls, objs) in _call(name, code, mode, rg, wk):
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
            exp = _expect(name, objs, wk, rg(objs))
            if entry != exp:
                fails.append(f"{name} {label}: entry {entry.hex()} want {exp.hex()}")
    if name == "rt_target":      # the same target again: counted, not written
        for (changed, entry, written, calls, objs) in _call(name, code, 1, lambda o: {"rcx": o["cmd"], "rdx": 0}):
            if written or calls != 1 or any(entry):
                fails.append(f"rt_target unchanged target: written {written} calls {calls}")
    if name in ("rt_target", "rt_cancel", "rt_land", "rt_order", "rt_stub", "rt_mktask"):   # a null rcx: no crash
        for (changed, entry, written, calls, objs) in _call(name, code, 1, lambda o: {"rcx": 0, "rdx": 0}):
            want = 1 if name == "rt_land" else 0
            if changed or written != want:
                fails.append(f"{name} null rcx: written {written} (want {want}) changed {changed}")
    if kind in TASK_KINDS:      # a null rbx: counted, nothing written, no crash
        for (changed, entry, written, calls, objs) in _call(name, code, 1, lambda o: {"rbx": 0}):
            if changed or written or calls != 1:
                fails.append(f"{name} null rbx: written {written} calls {calls} changed {changed}")
    return fails


def _check_pop(code, mutated=False):
    """[D42] rt_pop on a synthetic unit: ring at unit+0x288 (unit at [ring-0x10]), head, the popped order (vtable,
    flag), the override stack; plus head out of range, no override, override count out of range, a null unit,
    mode 0, a null rcx. Every register and the flags back; the whole entry checked."""
    fails = []
    unit = OBJ + 0x20000
    ring = unit + 0x288
    ov = OBJ + 0x60000
    order_vt, ov_vt, state = 0x14391A670, 0x14391AF10, 0x43D2B2C0

    def world(mu, head=3, ovn=1, null_unit=False, ov_ptr=True):
        _put(mu, ring - POP_UNIT, "<Q", 0 if null_unit else unit)
        _put(mu, ring + POP_HEAD, "<I", head)
        # written for an out-of-range head too: the cave must not read past the 40 slots (the bound is tested)
        at = ring + head * POP_STRIDE + POP_ORDER
        _put(mu, at, "<Q", order_vt)
        _put(mu, at + POP_FLAG, "<B", 1)
        _put(mu, unit + U_OV_COUNT, "<I", ovn)
        for i in range(U_OV_MAX):
            _put(mu, unit + U_OV_ARRAY + 8 * i, "<Q", (ov if ov_ptr else 0) if i == ovn - 1 else 0x9191)
        _put(mu, ov, "<Q", ov_vt)
        _put(mu, ov + OV_STATE, "<Q", state)

    cases = [("normal", 1, {}, dict(flag=1, vt=order_vt, unit=unit, n=1, ovvt=ov_vt, st=state)),
             ("head 39", 1, {"head": 39}, dict(flag=1, vt=order_vt, unit=unit, n=1, ovvt=ov_vt, st=state)),
             ("head 40", 1, {"head": 40}, dict(flag=0, vt=0, unit=unit, n=1, ovvt=ov_vt, st=state)),
             ("two overrides", 1, {"ovn": 2}, dict(flag=1, vt=order_vt, unit=unit, n=2, ovvt=ov_vt, st=state)),
             ("no override", 1, {"ovn": 0}, dict(flag=1, vt=order_vt, unit=unit, n=0, ovvt=NONE32, st=NONE32)),
             ("override count 3", 1, {"ovn": 3}, dict(flag=1, vt=order_vt, unit=unit, n=3, ovvt=NONE32, st=NONE32)),
             ("null override", 1, {"ov_ptr": False}, dict(flag=1, vt=order_vt, unit=unit, n=1, ovvt=NONE32,
                                                            st=NONE32)),
             ("null unit", 1, {"null_unit": True}, dict(flag=1, vt=order_vt, unit=0, n=NONE32, ovvt=NONE32,
                                                         st=NONE32)),
             ("off", 0, {}, None)]
    for label, mode, wk, want in cases:
        for flags in (0x202, 0x8D7):
            mu = _machine(code)
            world(mu, **wk)
            mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
            mu.mem_write(B + COUNT_AT, struct.pack("<I", 7))
            rsp = STACK + 0x4000
            mu.mem_write(rsp, struct.pack("<Q", RET))
            try:
                changed = _run(mu, code, {"rcx": ring, "rdx": 0x4242, "rsp": rsp}, flags)
            except Exception as err:      # a fault is a failed case
                fails.append(f"rt_pop {label}: faulted {err}")
                continue
            entry = bytes(mu.mem_read(B + RING_AT + 7 * ENTRY, ENTRY))
            written = _u32(mu, B + COUNT_AT) - 7
            calls = _u32(mu, B + CALLS_AT + 4 * (POP_KIND - 1))
            if changed:
                fails.append(f"rt_pop {label}: registers changed {changed}")
            if want is None:
                if written or calls or any(entry):
                    fails.append(f"rt_pop {label}: logged in mode 0")
                continue
            exp = struct.pack("<QQQIIQQIIII", ring, want["flag"], RET, 0, POP_KIND, want["vt"], want["unit"],
                              want["n"], want["ovvt"] & 0xFFFFFFFF, want["st"], 8)   # the cave keeps the low 32 bits
            exp += bytes(ENTRY - len(exp))
            if written != 1 or calls != 1 or entry != exp:
                fails.append(f"rt_pop {label}: written {written} calls {calls} entry {entry.hex()} want {exp.hex()}")
    for flags in (0x202,):            # a null rcx: counted, nothing written, no crash
        mu = _machine(code)
        mu.mem_write(B + MODE_AT, struct.pack("<I", 1))
        mu.mem_write(B + COUNT_AT, struct.pack("<I", 7))
        rsp = STACK + 0x4000
        mu.mem_write(rsp, struct.pack("<Q", RET))
        changed = _run(mu, code, {"rcx": 0, "rsp": rsp}, flags)
        if changed or _u32(mu, B + COUNT_AT) != 7:
            fails.append(f"rt_pop null rcx: changed {changed}")
    return fails


def check(mutate=None, which=None):
    """[failure] of the caves on synthetic calls (``which`` is built from the ``mutate`` (old, new) edit)."""
    fails = []
    for name in SITES:
        if which not in (None, name):
            continue
        try:
            code = assemble(name, mutate if which == name else None)
            fails += _check_pop(code) if name == "rt_pop" else _check_one(name, code)
        except Exception as err:     # a broken cave that faults in the emulator is a caught cave
            fails.append(f"{name}: the emulator faulted: {err}")
    return fails


MUTANTS = (
    ("rt_pop", "mov rdx, qword ptr [rcx - 0x10]", "mov rdx, qword ptr [rcx - 0x8]"),
    ("rt_pop", "cmp eax, 40\n    jae pop_noorder", "cmp eax, 41\n    jae pop_noorder"),
    ("rt_pop", "imul eax, eax, 0x120", "imul eax, eax, 0x118"),
    ("rt_pop", "movzx ecx, byte ptr [rax + 0x51]", "movzx ecx, byte ptr [rax + 0x50]"),
    ("rt_pop", "mov eax, dword ptr [rdx + 0x3310]", "mov eax, dword ptr [rdx + 0x3314]"),
    ("rt_pop", "cmp eax, 1\n    ja pop_end", "cmp eax, 2\n    ja pop_end"),
    ("rt_pop", "mov ecx, dword ptr [rax + 0x88]", "mov ecx, dword ptr [rax + 0x80]"),
    ("rt_pop", "mov dword ptr [r11 + 28], 10", "mov dword ptr [r11 + 28], 9"),
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
    ("rt_land", "shl r11, 7", "shl r11, 6"),
    ("rt_task1", "mov rax, qword ptr [rsp + 160]", "mov rax, qword ptr [rsp + 56]"),
    ("rt_task1", "mov qword ptr [r11], rbx", "mov qword ptr [r11], rcx"),
    ("rt_task1", "mov rax, qword ptr [rax + 8]", "mov rax, qword ptr [rax + 0x10]"),
    ("rt_task1", "mov rax, qword ptr [rbx + 0x58]", "mov rax, qword ptr [rbx + 0x50]"),
    ("rt_task1", "mov rax, qword ptr [rbx]\n", "mov rax, qword ptr [rbx + 8]\n"),
    ("rt_task1", "test rbx, rbx\n    jz done", "test rbx, rbx\n    jz noent"),
    ("rt_task2", "mov eax, dword ptr [rbx + 0x84]", "mov eax, dword ptr [rbx + 0x80]"),
    ("rt_task2", "mov eax, dword ptr [rbx + 0x8]", "mov eax, dword ptr [rbx + 0xc]"),
    ("rt_task2", "mov dword ptr [r11 + 28], 8", "mov dword ptr [r11 + 28], 7"),
    ("rt_task2", "mov rax, qword ptr [rbx + 0x68]", "mov rax, qword ptr [rbx + 0x60]"),
    ("rt_mktask", "mov rax, qword ptr [rdx + 0x18]\n    mov qword ptr [r11 + 40], rax",
     "mov rax, qword ptr [rdx + 0x10]\n    mov qword ptr [r11 + 40], rax"),
    ("rt_mktask", "mov rax, qword ptr [rdx + 0x30]", "mov rax, qword ptr [rdx + 0x28]"),
    ("rt_mktask", "jz noparams", "jz done"),
    ("rt_mktask", "mov rax, qword ptr [rsp + 56]", "mov rax, qword ptr [rsp + 64]"),
    ("rt_mktask", "mov dword ptr [r11 + 28], 9", "mov dword ptr [r11 + 28], 6"),
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


def decode_check(exe_path):
    """[problem] from decoding the installed exe with capstone (empty = the static reading holds):
    * every site's stolen bytes are whole instructions with no RIP-relative operand and no branch;
    * no branch of the function that holds a site lands inside its stolen bytes;
    * task sites: the handler starts ``push rbx; sub rsp, 0x60`` (its return address at [rsp + 0x68]),
      ``mov rbx, rcx`` is at the stated address, and from there to the site nothing writes rbx or moves rsp;
      the stolen bytes are followed by ``mov rax, [rcx]; call [rax + 0x4f8]`` whose return address is the one
      rt_stub logged (0x142f7f71c / 0x142f8ffda);
    * the task: the constructor installs the vtable TASK_VT, whose slots 1 and 2 are the two handlers, it has
      exactly one direct caller (TASK_CTOR_CALL, inside rt_mktask's function) and no qword reference."""
    import capstone
    import pefile
    from capstone import x86 as X
    pe = pefile.PE(str(exe_path), fast_load=True)
    base, img = pe.OPTIONAL_HEADER.ImageBase, pe.get_memory_mapped_image()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    probs = []

    def insns(va, end):
        return list(md.disasm(img[va - base:end - base], va))

    def to_ret(va):           # linear decode up to and including the first ret
        out = []
        for i in md.disasm(img[va - base:va - base + 0x400], va):
            out.append(i)
            if i.mnemonic == "ret":
                return out
        probs.append(f"no ret within 0x400 bytes of {va:#x}")
        return out

    def branch_target(i):
        if i.group(X.X86_GRP_JUMP) or i.group(X.X86_GRP_CALL):
            op = i.operands[0] if i.operands else None
            if op is not None and op.type == X.X86_OP_IMM:
                return op.imm
        return None

    def writes(i, regs):
        _r, w = i.regs_access()
        return any(i.reg_name(r) in regs for r in w)

    q = lambda va: struct.unpack_from("<Q", img, va - base)[0]
    for name, (_pattern, _at, stolen, va) in SITES.items():
        n = len(stolen.split())
        got = insns(va, va + n)
        if sum(i.size for i in got) != n:
            probs.append(f"{name}: the stolen bytes are not whole instructions")
        for i in got:
            if any(op.type == X.X86_OP_MEM and op.mem.base == X.X86_REG_RIP for op in i.operands):
                probs.append(f"{name}: RIP-relative operand at {i.address:#x}")
            if branch_target(i) is not None or i.group(X.X86_GRP_JUMP) or i.group(X.X86_GRP_CALL):
                probs.append(f"{name}: a branch in the stolen bytes at {i.address:#x}")
    for name, (start, movrbx, after) in TASK_SITES.items():
        va = SITES[name][3]
        n = len(SITES[name][2].split())
        body = to_ret(start)
        if [(i.mnemonic, i.op_str) for i in body[:2]] != [("push", "rbx"), ("sub", f"rsp, {HANDLER_RET - 8:#x}")]:
            probs.append(f"{name}: the handler {start:#x} does not start push rbx; sub rsp, {HANDLER_RET - 8:#x}")
        mv = [i for i in body if i.address == movrbx]
        if not mv or (mv[0].mnemonic, mv[0].op_str) != ("mov", "rbx, rcx"):
            probs.append(f"{name}: no mov rbx, rcx at {movrbx:#x}")
        for i in body:
            if movrbx < i.address < va and writes(i, ("rbx", "ebx", "bx", "bl")):
                probs.append(f"{name}: rbx written at {i.address:#x} before the site")
            if body[1].address < i.address < va and (i.mnemonic in ("push", "pop") or writes(i, ("rsp",))
                                                    and not i.group(X.X86_GRP_CALL)):
                probs.append(f"{name}: rsp moved at {i.address:#x} before the site")
            t = branch_target(i)
            if t is not None and va < t < va + n:
                probs.append(f"{name}: a branch at {i.address:#x} lands inside the stolen bytes")
        nxt = [i for i in body if va + n <= i.address < after]
        if [(i.mnemonic, i.op_str) for i in nxt] != [("mov", "rax, qword ptr [rcx]"), ("call", "qword ptr [rax + 0x4f8]")]:
            probs.append(f"{name}: the stolen bytes are not followed by the charge-command call returning to {after:#x}")
    ctor = to_ret(TASK_CTOR)
    vts = [i.operands[1].mem.disp + i.address + i.size for i in ctor
           if i.mnemonic == "lea" and i.operands[1].type == X.X86_OP_MEM and i.operands[1].mem.base == X.X86_REG_RIP]
    if vts != [TASK_VT]:
        probs.append(f"the constructor {TASK_CTOR:#x} installs {[hex(v) for v in vts]}, want [{TASK_VT:#x}]")
    if (q(TASK_VT + 8), q(TASK_VT + 16)) != TASK_HANDLERS:
        probs.append(f"vtable {TASK_VT:#x} slots 1 / 2 are {q(TASK_VT + 8):#x} / {q(TASK_VT + 16):#x}")
    callers = []
    for s in pe.sections:
        if s.Characteristics & 0x20000000:
            data, va0 = s.get_data(), base + s.VirtualAddress
            for m in re.finditer(b"\xe8", data):
                i = m.start()
                if i + 5 <= len(data) and va0 + i + 5 + struct.unpack_from("<i", data, i + 1)[0] == TASK_CTOR:
                    callers.append(va0 + i)
    mk = SITES["rt_mktask"][3]
    if callers != [TASK_CTOR_CALL] or not mk < TASK_CTOR_CALL < mk + 0x40:
        probs.append(f"direct calls of the constructor: {[hex(c) for c in callers]}, want [{TASK_CTOR_CALL:#x}] "
                     f"inside rt_mktask's function")
    if img.find(struct.pack("<Q", TASK_CTOR)) != -1:
        probs.append(f"the constructor {TASK_CTOR:#x} also has a qword reference (an indirect caller)")
    return probs


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
    """The site table of the caves in ``codes`` (every site, or those build_site was not told to leave out)."""
    lines = ["-- TEST-ONLY, generated by tools/pipelines/regroup_trace_asm.py; never in a player's pack",
             "return {", f"    owner = '{OWNER}', feature = '{FEATURE}',", "    entries = {"]
    for n in codes:
        pattern, at, stolen, _va = SITES[n]
        lines += [f"        {{ name = '{n}', feature = '{FEATURE}', kind = 'cave',",
                  f"          pattern = '{pattern}', at = {at}, expect = '{stolen}',",
                  f"          bytes = '{_template(codes[n])}' }},"]
    lines += ["    },", "    caves = { " + ", ".join(f"'{n}'" for n in codes) + " },",
              f"    layout = {{ bytes = {BYTES}, mode_at = {MODE_AT}, magic_at = {MAGIC_AT}, magic = '{MAGIC.decode()}',",
              f"        count_at = {COUNT_AT}, calls_at = {CALLS_AT}, ring_at = {RING_AT}, slots = {SLOTS}, "
              f"entry = {ENTRY} }},", "}"]
    return "\n".join(lines) + "\n"


def build_site(exe_path=EXE, exclude=()):
    """(site Lua text, report): the sites in the installed exe (patterns, decoding), assemble, emulator check,
    negative controls; refuses on any failure. ``exclude``: sites left out of the table [REGROUP-FIX-1120: the
    task sites, where the shipped take-off caves' regroup part now sits; two caves cannot share a site]."""
    if set(exclude) - set(SITES):
        raise SystemExit(f"[regroup_trace] REFUSING: unknown sites to leave out {sorted(set(exclude) - set(SITES))}")
    check_exe(exe_path)
    decoded = decode_check(exe_path)
    if decoded:
        raise SystemExit("[regroup_trace] REFUSING: " + "; ".join(decoded))
    codes = {n: assemble(n) for n in SITES if n not in exclude}
    fails = check()
    survivors = [] if fails else negative_controls()
    if fails or survivors:
        raise SystemExit("[regroup_trace] REFUSING: " + "; ".join(fails + [f"mutant not caught: {m}" for m in survivors]))
    return site_lua(codes), (f"caves {', '.join(f'{n} {len(c)} B' for n, c in codes.items())}"
                             + (f" (left out: {', '.join(exclude)})" if exclude else "") + "; "
                             f"exe patterns and decoding PASS; emulator PASS; {len(MUTANTS)} mutants, each caught")


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
