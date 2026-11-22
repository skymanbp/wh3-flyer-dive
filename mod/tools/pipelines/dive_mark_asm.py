"""The physics-dive caves plus the dive mark (d15-1118; SHIPPED since stage 5 through dive_cost_asm.py, which
writes the shipped site table with these marked caves and dv_cost).

The dive rule itself is unchanged: ``check`` runs dive_cave_asm's whole emulator check (every case of every
cave) against these caves, then the mark's own cases; dive_cost_asm.py adds dive_cave_asm's mutants on the
marked sources and this file's mutants (``negative_controls``).

THE MARK (docs/DECISIONS.md D15; design: the d15-1118 lane report). Per flying entity (the mover: the
entity itself, or the entity it rides; the same key as the slide table), one entry with a state:
  ARMED (1)   dv_through, for a charge order IN THE AIR and NOT IN MELEE: exactly where the shipped cave
              opens a new slide window (_window_clear's ``wclr_go``). A ground charge (+0x104 0) and a
              re-charge out of melee (+0x324 1) never get here. Arming an entry that is already armed only
              refreshes its tick (no event).
  STAMPED (2) the first hold ON THE GROUND (_window_test's ``whold``, reached only with +0x104 0) of an
              ARMED mover that is still in flight movement (+0x710 not 0: the landed dive, the shipped
              caves' own test for it). The tick of the stamp is the touchdown tick. _window_test never
              creates an entry: it only stamps one dv_through armed.
  SPENT (3)   written by dv_cost (dive_cost_asm.py): a type-5 / type-6 damage call whose attacker's flying
              entity is STAMPED, at most DIVE_COST_WINDOW_TICKS after the stamp, on a braced soldier of a
              unit with charge reflection, in front of it. One cost, then the mark is spent.
  EXPIRED (4) also dv_cost: the same call more than the window after the stamp.
Every change of state is an event in a ring (dv_cost writes its two kinds into the same ring).

Buffer: the shipped layout (dive_cave_asm.BUFFER_BYTES), then
  MARK_AT +0  u32 events written (the next seq)   +4 u32 entries not found room for (table full)
  MARK_TABLE_AT  MARK_SLOTS x 16 bytes: u64 mover (0 empty), u32 state, u32 tick of the last arm / stamp
  MARK_RING_AT   MARK_RING x 32 bytes: u64 entity, u64 its unit (+0x2e8), u32 battle tick, u32 kind
                 (1 arm, 2 stamp, 3 spent, 4 expired), u32 extra (arm: the state it replaced; stamp:
                 ticks since the arm; spent / expired: ticks since the stamp), u32 seq + 1 (written last)
The whole buffer stays below 8 KiB so dive_cave_asm's own emulator rigs (8 KiB buffers) hold it.
The shipped table's MAGIC and the cost area after this layout are dive_cost_asm.py's.
"""
import struct
import sys
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
import rolepath  # noqa: F401,E402 -- imported because it puts the role directories on sys.path

import dive_cave_asm as base  # noqa: E402 -- because rolepath above puts pipelines/ on sys.path

MAGIC = b"FLYDIVM3"                          # this layout alone; the shipped table uses dive_cost_asm.MAGIC
MARK_AT = base.BUFFER_BYTES                  # 5248 since D66 (4160 before), a multiple of 64
MARK_COUNT_AT, MARK_FULL_AT = MARK_AT, MARK_AT + 4
MARK_TABLE_AT, MARK_SLOTS = MARK_AT + 64, 128
MARK_RING_AT, MARK_RING, MARK_ENTRY = MARK_TABLE_AT + MARK_SLOTS * 16, 32, 32
BYTES = MARK_RING_AT + MARK_RING * MARK_ENTRY
ARMED, STAMPED, SPENT, EXPIRED = 1, 2, 3, 4
EV_ARM, EV_STAMP, EV_SPENT, EV_EXPIRED = 1, 2, 3, 4
BATTLE_OFF, TICKS_OFF, TICK_OFF = 0x58, 0x440, 0x98
SITE_PATH = "script/campaign/flyer_dive/data/dive_site.lua"
assert BYTES <= base.RIG_BUF, BYTES           # dive_cave_asm's rigs map RIG_BUF bytes (16 KiB since D66)


def tick(ent, out32, scratch, tag):
    """battle tick of entity ``ent`` into ``out32``; 0 when a link is null. ``scratch`` a 64-bit register."""
    return f"""
    xor {out32}, {out32}
    test {ent}, {ent}
    jz tk_{tag}
    mov {scratch}, qword ptr [{ent} + {BATTLE_OFF:#x}]
    test {scratch}, {scratch}
    jz tk_{tag}
    mov {scratch}, qword ptr [{scratch} + {TICKS_OFF:#x}]
    test {scratch}, {scratch}
    jz tk_{tag}
    mov {out32}, dword ptr [{scratch} + {TICK_OFF:#x}]
tk_{tag}:
"""


def find(buf, key, claim, tag):
    """The table entry of ``key`` -> rdx (0: none; with ``claim`` an empty slot is taken with lock cmpxchg,
    a full table is counted at MARK_FULL_AT). Uses rax, rcx, r8; ``buf`` / ``key`` must be none of them."""
    if {buf, key} & {"rax", "rcx", "r8", "rdx"}:
        raise ValueError("find: buf / key collide with the scratch registers")
    take = f"""
    mov rcx, rax
    xor eax, eax
    lock cmpxchg qword ptr [rdx], {key}
    xchg rax, rcx
    je fd_hit_{tag}
    cmp rcx, {key}
    je fd_hit_{tag}
    jmp fd_next_{tag}
""" if claim else f"""
    jmp fd_miss_{tag}
"""
    full = f"    lock inc dword ptr [{buf} + {MARK_FULL_AT}]\n" if claim else ""
    return f"""
    mov rax, {key}
    shr rax, 4
    and eax, {MARK_SLOTS - 1}
    mov r8d, {MARK_SLOTS}
fd_probe_{tag}:
    mov edx, eax
    shl rdx, 4
    lea rdx, [{buf} + rdx + {MARK_TABLE_AT}]
    mov rcx, qword ptr [rdx]
    cmp rcx, {key}
    je fd_hit_{tag}
    test rcx, rcx
    jnz fd_next_{tag}
{take}fd_next_{tag}:
    inc eax
    and eax, {MARK_SLOTS - 1}
    dec r8d
    jnz fd_probe_{tag}
{full}fd_miss_{tag}:
    xor edx, edx
fd_hit_{tag}:
"""


def event(buf, ent, kind, tag):
    """One ring entry: entity ``ent``, tick in ebx, ``kind``, extra in edx. Keeps every register but flags
    (rax, rcx, r8 saved); ``buf`` / ``ent`` must not be rax / rcx / r8 / rbx / rdx."""
    if {buf, ent} & {"rax", "rcx", "r8", "rbx", "rdx"}:
        raise ValueError("event: buf / ent collide with the registers it uses")
    return f"""
    push rax
    push rcx
    push r8
    mov r8d, 1
    lock xadd dword ptr [{buf} + {MARK_COUNT_AT}], r8d
    mov ecx, r8d
    and ecx, {MARK_RING - 1}
    shl ecx, 5
    lea rcx, [{buf} + rcx + {MARK_RING_AT}]
    inc r8d
    mov dword ptr [rcx + 28], 0
    mov qword ptr [rcx], {ent}
    xor eax, eax
    test {ent}, {ent}
    jz ev_nounit_{tag}
    mov rax, qword ptr [{ent} + {base.UNIT_OFF:#x}]
ev_nounit_{tag}:
    mov qword ptr [rcx + 8], rax
    mov dword ptr [rcx + 16], ebx
    mov dword ptr [rcx + 20], {kind}
    mov dword ptr [rcx + 24], edx
    mov dword ptr [rcx + 28], r8d
    pop r8
    pop rcx
    pop rax
"""


def arm_block():
    """Inserted in _window_clear after ``cmovne rcx, rax`` (rcx = the mover, r10 = the buffer); every
    register comes back (rcx too: the shipped code goes on with it)."""
    return f"""
    push rax
    push rbx
    push rcx
    push rdx
    push r8
    push r11
    mov r11, rcx
{tick("r11", "ebx", "rax", "arm")}{find("r10", "r11", True, "arm")}    test rdx, rdx
    jz arm_out
    mov eax, dword ptr [rdx + 8]
    mov dword ptr [rdx + 12], ebx
    cmp eax, {ARMED}
    je arm_out
    mov dword ptr [rdx + 8], {ARMED}
    mov edx, eax
{event("r10", "r11", EV_ARM, "arm")}arm_out:
    pop r11
    pop r8
    pop rdx
    pop rcx
    pop rbx
    pop rax
"""


def stamp_block():
    """Inserted in _window_test right after ``whold:`` (r9 = the mover, r10 = the buffer; rax rbx rcx rdx
    r8 are saved by _window_test there and restored after it)."""
    return f"""
    cmp dword ptr [r9 + {base.FLYMODE_OFF:#x}], 0
    je st_out
{find("r10", "r9", False, "st")}    test rdx, rdx
    jz st_out
    cmp dword ptr [rdx + 8], {ARMED}
    jne st_out
{tick("r9", "ebx", "rax", "st")}    mov eax, ebx
    sub eax, dword ptr [rdx + 12]
    mov dword ptr [rdx + 12], ebx
    mov dword ptr [rdx + 8], {STAMPED}
    mov edx, eax
{event("r10", "r9", EV_STAMP, "st")}st_out:
"""


ARM_ANCHOR = "    cmovne rcx, rax\n    mov rax, rcx\n    shr rax, 4\n"
STAMP_ANCHOR = "whold:\n"


def _edit(text, old, new, what):
    if text.count(old) != 1:
        raise SystemExit(f"[dive_mark] REFUSING: {what}: {old!r} found {text.count(old)} times in the shipped "
                         "source (dive_cave_asm changed?)")
    return text.replace(old, new)


_SHIPPED_SOURCE = base.cave_source


def cave_source(name):
    """The shipped cave's source with the mark added: dv_through arms, every cave that runs _window_test
    stamps; the rest are the shipped source unchanged."""
    s = _SHIPPED_SOURCE(name)
    if name == "dv_through":
        s = _edit(s, ARM_ANCHOR, "    cmovne rcx, rax\n" + arm_block() + "    mov rax, rcx\n    shr rax, 4\n",
                  "dv_through: arm")
    if STAMP_ANCHOR in s:
        s = _edit(s, STAMP_ANCHOR, STAMP_ANCHOR + stamp_block(), f"{name}: stamp")
    return s


@contextmanager
def _marked():
    """dive_cave_asm's checks assemble partner caves by name (base.assemble -> base.cave_source): inside
    this block they get the marked sources, and their rigs a larger instruction budget (the mark's probe
    loops run more instructions per call; an endless loop still stops the emulator)."""
    base.cave_source, base.STEP_FACTOR = cave_source, 8
    try:
        yield
    finally:
        base.cave_source, base.STEP_FACTOR = _SHIPPED_SOURCE, 1


def assemble(name, source=None):
    with _marked():
        return base.assemble(name, source or cave_source(name))


# --- emulator: the mark's own cases ----------------------------------------------
def _mark_rig(through_code, hold_code):
    """dive_cave_asm's window rig (one machine, one buffer, a hold cave + dv_through), with a battle tick
    readable from every entity: -> (mu, hold, through, buf, set_tick)."""
    mu, hold, through, buf = base._window_rig(hold_code, through_code)
    battle, ticks = 0x500000 + 0xE000, 0x500000 + 0xE800
    mu.mem_write(battle + TICKS_OFF, struct.pack("<Q", ticks))

    def set_tick(t):
        mu.mem_write(ticks + TICK_OFF, struct.pack("<I", t))

    def wire(ent, unit):
        mu.mem_write(ent + BATTLE_OFF, struct.pack("<Q", battle))
        mu.mem_write(ent + base.UNIT_OFF, struct.pack("<Q", unit))
    return mu, hold, through, buf, set_tick, wire


def _entry(mu, buf, key):
    raw = bytes(mu.mem_read(buf + MARK_TABLE_AT, MARK_SLOTS * 16))
    for i in range(MARK_SLOTS):
        k, st, tk = struct.unpack_from("<QII", raw, i * 16)
        if k == key:
            return st, tk
    return None


def _events(mu, buf):
    n = struct.unpack("<I", bytes(mu.mem_read(buf + MARK_COUNT_AT, 4)))[0]
    out = []
    for s in range(max(0, n - MARK_RING), n):
        e = bytes(mu.mem_read(buf + MARK_RING_AT + (s % MARK_RING) * MARK_ENTRY, MARK_ENTRY))
        ent, unit, tk, kind, extra, seq = struct.unpack("<QQIIiI", e)
        out.append((kind, ent, unit, tk, extra, seq == s + 1))
    return out


def check_mark(through_code, keep_code, contact_code):
    """The mark on synthetic flyers: armed only by an air charge out of melee, stamped only by a ground hold
    of an armed mover still in flight movement, never created by a hold, keyed on the mount of a rider,
    re-armed by a new air charge, one event per change, a full table counted. -> (fails, cases)."""
    fails, n = [], 0
    mu, hold, through, buf, set_tick, wire = _mark_rig(through_code, keep_code)
    a, g = 0x501000, 0x503000
    for ent in (a, g):
        base._mover(mu, ent, True, 30, base.FAST)
        mu.mem_write(ent + base.FLYMODE_OFF, struct.pack("<i", 4))
        wire(ent, 0xCC0000 + ent)
    # 1. a ground hold without an air charge: no entry (a hold never creates a mark)
    set_tick(100)
    n += 1
    got = hold(g, 0.0, 0.0)
    if got != "held" or _entry(mu, buf, g) is not None or _events(mu, buf):
        fails.append(f"mark: a ground hold with no air charge: {got}, entry {_entry(mu, buf, g)}")
    # 2. a ground charge (layer 0): no mark
    n += 1
    if not through(g, 0) or _entry(mu, buf, g) is not None:
        fails.append(f"mark: a ground charge armed {_entry(mu, buf, g)}")
    # 3. an air charge arms (one event, extra = old state 0); a second air charge only refreshes the tick
    set_tick(110)
    n += 1
    if not through(a, 2) or _entry(mu, buf, a) != (ARMED, 110) or [e[:5] for e in _events(mu, buf)] != [
            (EV_ARM, a, 0xCC0000 + a, 110, 0)]:
        fails.append(f"mark: air charge: entry {_entry(mu, buf, a)} events {_events(mu, buf)}")
    set_tick(115)
    n += 1
    if not through(a, 1) or _entry(mu, buf, a) != (ARMED, 115) or len(_events(mu, buf)) != 1:
        fails.append(f"mark: re-arm while armed: entry {_entry(mu, buf, a)} events {len(_events(mu, buf))}")
    # 4. an airborne hold does not stamp
    mu.mem_write(a + base.LAYER_OFF, struct.pack("<i", 2))
    n += 1
    got = hold(a, 0.0, 0.0)
    mu.mem_write(a + base.LAYER_OFF, struct.pack("<i", 0))
    if got != "held" or _entry(mu, buf, a) != (ARMED, 115):
        fails.append(f"mark: airborne hold stamped: {got} {_entry(mu, buf, a)}")
    # 5. a ground hold out of flight movement (+0x710 0) does not stamp
    mu.mem_write(a + base.FLYMODE_OFF, struct.pack("<i", 0))
    n += 1
    got = hold(a, 0.0, 0.0)
    mu.mem_write(a + base.FLYMODE_OFF, struct.pack("<i", 4))
    if _entry(mu, buf, a) != (ARMED, 115):
        fails.append(f"mark: a walking flyer's hold stamped: {got} {_entry(mu, buf, a)}")
    # 6. the landed dive's first ground hold stamps (tick, extra = ticks since the arm); later holds do not
    set_tick(140)
    n += 1
    got = hold(a, 1.0, 1.0)
    ev = _events(mu, buf)
    if got != "held" or _entry(mu, buf, a) != (STAMPED, 140) or [e[:5] for e in ev[1:]] != [
            (EV_STAMP, a, 0xCC0000 + a, 140, 25)] or not all(e[5] for e in ev):
        fails.append(f"mark: first ground hold: {got} {_entry(mu, buf, a)} events {ev}")
    set_tick(145)
    n += 1
    hold(a, 2.0, 2.0)
    if _entry(mu, buf, a) != (STAMPED, 140) or len(_events(mu, buf)) != 2:
        fails.append(f"mark: a second hold re-stamped: {_entry(mu, buf, a)}")
    # 7. a re-charge out of melee (+0x324 1) does not re-arm
    mu.mem_write(a + base.MELEE_OFF, struct.pack("<i", 1))
    n += 1
    through(a, 2)
    mu.mem_write(a + base.MELEE_OFF, struct.pack("<i", 0))
    if _entry(mu, buf, a) != (STAMPED, 140) or len(_events(mu, buf)) != 2:
        fails.append(f"mark: an engaged re-charge re-armed: {_entry(mu, buf, a)}")
    # 8. a new air charge re-arms a stamped mark (extra = the replaced state)
    set_tick(300)
    n += 1
    through(a, 2)
    if _entry(mu, buf, a) != (ARMED, 300) or _events(mu, buf)[-1][:5] != (EV_ARM, a, 0xCC0000 + a, 300, STAMPED):
        fails.append(f"mark: re-arm after a dive: {_entry(mu, buf, a)} {_events(mu, buf)[-1]}")
    # 9. a rider: the mark is keyed on the mount, through dv_through (r9 = rider) and dv_contact (rcx = rider)
    mu2, hold2, through2, buf2, set_tick2, wire2 = _mark_rig(through_code, contact_code)
    rider, mount = 0x501000, 0x503000
    mu2.mem_write(rider + base.PARENT_OFF, struct.pack("<Q", mount))
    base._mover(mu2, mount, True, 30, base.FAST)
    mu2.mem_write(mount + base.FLYMODE_OFF, struct.pack("<i", 4))
    wire2(mount, 0xDD0000)
    wire2(rider, 0xEE0000)
    set_tick2(50)
    n += 1
    through2(rider, 2)
    if _entry(mu2, buf2, mount) != (ARMED, 50) or _entry(mu2, buf2, rider) is not None:
        fails.append(f"mark ridden: armed mount {_entry(mu2, buf2, mount)} rider {_entry(mu2, buf2, rider)}")
    set_tick2(58)
    n += 1
    got = hold2(rider, 0.0, 0.0)
    ev = _events(mu2, buf2)
    if got != "held" or _entry(mu2, buf2, mount) != (STAMPED, 58) or ev[-1][:4] != (EV_STAMP, mount, 0xDD0000, 58):
        fails.append(f"mark ridden: contact hold {got} {_entry(mu2, buf2, mount)} {ev}")
    # 10. a full table: an air charge of a new flyer is counted, nothing written
    mu3, _hold3, through3, buf3, set_tick3, wire3 = _mark_rig(through_code, keep_code)
    mu3.mem_write(buf3 + MARK_TABLE_AT, b"".join(struct.pack("<QII", 0x7100_0000 + 0x10 * (i + 1), ARMED, 1)
                                                 for i in range(MARK_SLOTS)))
    base._mover(mu3, a, True, 30, base.FAST)
    n += 1
    through3(a, 2)
    full = struct.unpack("<I", bytes(mu3.mem_read(buf3 + MARK_FULL_AT, 4)))[0]
    if full != 1 or _events(mu3, buf3):
        fails.append(f"mark: full table: counted {full}, events {_events(mu3, buf3)}")
    return fails, n


def check():
    """(fails, report): dive_cave_asm's whole check on the marked caves, then the mark's own."""
    codes = {name: assemble(name) for name in base.CAVES}
    fails, counts = [], {}
    with _marked():
        for name in base.CAVES:
            f, cnt = base.CHECKS[name](codes[name])
            fails += [f"shipped case on the marked {name}: {x}" for x in f]
            counts[name] = cnt
    f, cnt = check_mark(codes["dv_through"], codes["dv_keep"], codes["dv_contact"])
    fails += f
    counts["mark"] = cnt
    return codes, fails, counts


# each must fail at least one mark case: (label, cave, old, new) applied to the marked source
MUTANTS = (
    ("arms on a ground charge too", "dv_through", "    cmp dword ptr [r9 + 0x104], 0\n    je wclr_done\n",
     "    cmp dword ptr [r9 + 0x104], 0\n    nop\n"),
    ("arms the rider, not the mount", "dv_through", "    mov r11, rcx\n", "    mov r11, r9\n"),
    ("arms out of melee too", "dv_through", "    jne wclr_go\n", "    jmp wclr_go\n"),
    ("re-arm logs every time", "dv_through", f"    cmp eax, {ARMED}\n    je arm_out\n", "    nop\n"),
    ("stamps a walking flyer", "dv_keep", "    cmp dword ptr [r9 + 0x710], 0\n    je st_out\n", "    nop\n"),
    ("stamps without an arm", "dv_keep", f"    cmp dword ptr [rdx + 8], {ARMED}\n    jne st_out\n", "    nop\n"),
    ("a hold creates a mark", "dv_keep", "    jmp fd_miss_st\n", "    mov rcx, rax\n    xor eax, eax\n"
     "    lock cmpxchg qword ptr [rdx], r9\n    xchg rax, rcx\n    jmp fd_hit_st\n"),
    ("stamp keeps the arm tick", "dv_keep", "    mov dword ptr [rdx + 12], ebx\n    mov dword ptr [rdx + 8], 2\n",
     "    mov dword ptr [rdx + 8], 2\n"),
    ("stamp without event", "dv_keep", "    mov dword ptr [rcx + 20], 2\n", "    mov dword ptr [rcx + 20], 1\n"),
    ("event seq not written", "dv_through", "    mov dword ptr [rcx + 28], r8d\n", "    nop\n"),
    ("full table not counted", "dv_through", f"    lock inc dword ptr [r10 + {MARK_FULL_AT}]\n", "    nop\n"),
    ("tick from the wrong field", "dv_through", f"    mov ebx, dword ptr [rax + {TICK_OFF:#x}]\n",
     "    mov ebx, dword ptr [rax + 0x9c]\n"),
)


def negative_controls():
    survivors = []
    for label, name, old, new in MUTANTS:
        src = cave_source(name)
        if src.count(old) < 1:
            raise SystemExit(f"[dive_mark] REFUSING: mutant {label!r} does not apply")
        mutated = assemble(name, src.replace(old, new, 1))
        codes = {k: assemble(k) for k in ("dv_through", "dv_keep", "dv_contact")}
        codes[name] = mutated
        f, _n = check_mark(codes["dv_through"], codes["dv_keep"], codes["dv_contact"])
        if not f:
            survivors.append(label)
    return survivors


def layout():
    lay = dict(base.layout())
    lay.update({"bytes": BYTES, "magic": MAGIC.decode(), "mark_count_at": MARK_COUNT_AT,
                "mark_full_at": MARK_FULL_AT, "mark_table_at": MARK_TABLE_AT, "mark_slots": MARK_SLOTS,
                "mark_ring_at": MARK_RING_AT, "mark_ring": MARK_RING, "mark_entry": MARK_ENTRY})
    return lay
