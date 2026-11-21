"""TEST-ONLY: the take-off caves with a trace, for the run that explains the take-off gap (D11).

Never in a player's pack. ``build_pin_on_hit_probe.py --trace-from <built pack>`` swaps the shipped
take-off site table for the one generated here (``TRACE_SITE``) and adds the recorder; the pack is
deployed INSTEAD of the shipped one (same scripts, same rule, one more cave and a trace ring).

THE QUESTION (docs/STATUS.md, series 3 run 3): a manticore whose take-off countdown had long run out was
hit for the first time at tick 204, ordered away at 205 and airborne at 206 -- earlier than its window.
Two explanations: (1) the engine does not ask the take-off check when the countdown is already 0, or
(2) the check is asked less often than once per tick. The trace answers it per entity and per tick.

STATIC READING (Warhammer3.exe 9.0.5, 6ae2a00b):
* the per-tick executor 0x143050114 walks the unit's living flight entities (unit +0x184 / +0x188) and,
  for each one, may call the take-off request 0x14304cea0 (call at 0x143050250; phase FC+0x90 1 -> 2) and
  then ALWAYS calls the per-model flight update 0x143053bd4 (call at 0x14305026c);
* the update first runs the state machine 0x14301b534 (call at 0x143053c44), whose phase-2 branch
  0x14301b8d4 lifts the model off (phase 3) when the countdown FC+0x44 is 0;
* only afterwards comes the gate in front of the take-off check (0x143053ce3): the check (the hold
  cave's site, 0x143053cfb) is asked when the countdown is above 0, or when the phase is 1; with the
  countdown at 0 in any other phase it is skipped (jne 0x143053d8b), and so is the re-arm.
So a hit that lands after the model's update in tick T, followed by a request that sets phase 2 before
the update of tick T+1, is never seen by the check. That is explanation (1); the trace shows whether the
game does it.

THREE CAVES, one buffer (the shipped layout, then a trace header and ring):
  pin_stamp  the shipped stamp cave + one trace entry per recorded melee hit (kind 5; kind 6 when the
             shipped D11 raise set its 0 countdown to 1 -- the entry keeps the countdown from before);
  pin_hold   the shipped hold cave + one trace entry per call: kind 2 answered free, 3 answered held,
             4 passed through to the game's own check (mode != 1);
  pin_tick   NEW, at 0x143053c19 in the update (after its first call, before the state machine; stolen
             ``xor r12d,r12d; lea rsi,[rbx+0x78]``, 7 bytes, nothing relative): one entry per update call
             (kind 1), with the countdown and the phase BEFORE the state machine ran.
The rule's answers and counters are the shipped caves' own: ``check`` runs pin_cave_asm's whole emulator
check against the traced caves, once with the trace off and once with it on.

Trace (at TRACE_AT = the shipped buffer's end): +0 u32 on, +4 u32 entries written (the next seq);
ring at TRACE_RING_AT, TRACE_SLOTS x 32 bytes:
  +0 u64 key: the flight controller (kinds 1-4) or the flying entity (kind 5)
  +8 u32 battle tick (0xFFFFFFFF: not readable)     +12 u32 countdown FC+0x44
  +16 u32 phase FC+0x90                             +20 u32 kind
  +24 u32 extra: kind 1 = byte FC+0x64 | 0x100 when FC+8 (the "stay down" field) is set;
               kinds 2/3 = the window used (0xFFFFFFFF: no model / unit / tick / list;
               0xFFFFFFFE: no living entity carries this FC); kind 4 = 0; kinds 5/6 = the entry's hit count
  +28 u32 seq + 1 (written last)

``python takeoff_trace_asm.py [--write-site]`` (keystone + unicorn) assembles, runs the checks and the
mutants, checks the installed exe, and writes TRACE_SITE; offline (no keystone) ``check_site_file`` says
whether the committed table was generated from the current sources.
"""
import hashlib
import json
import struct
import sys
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
import rolepath  # noqa: F401,E402 -- imported because it puts the role directories on sys.path

import cave_site_text  # noqa: E402 -- because rolepath above puts lib/ on sys.path
import pin_cave_asm as base  # noqa: E402 -- same reason (pipelines/)

TRACE_SITE = HERE / "takeoff_trace_site.lua"
MAGIC = b"FLYPIT10"                 # a shipped table never adopts a traced buffer (cave_common.installed); 5: D11 raise
# 6: followed the shipped marker 6 (D23); the traced table carries the stamp and hold caves only, not the regroup ones
# 7: follows the shipped FLYPINS7 (D37, windows one second longer)
# 8: follows the shipped FLYPINS8 (D39, the unit table and the unit rule)
# 9: follows the shipped FLYPINS9 (D44, pin_repick)
# 10: follows the shipped FLYPIN10 (REPICK-EXIT-1121, pin_repick at the picker's exit)
TRACE_AT = base.BUFFER_BYTES        # 147584 since D39, a multiple of 64
TRACE_ON_AT, TRACE_COUNT_AT = TRACE_AT, TRACE_AT + 4
TRACE_RING_AT, TRACE_ENTRY, TRACE_SLOTS = TRACE_AT + 64, 32, 32768
BYTES = TRACE_RING_AT + TRACE_ENTRY * TRACE_SLOTS
KIND_UPDATE, KIND_FREE, KIND_HELD, KIND_PASS, KIND_HIT, KIND_HIT_RAISED = 1, 2, 3, 4, 5, 6
NO_TICK, NO_MODEL, UNMATCHED = 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFE
COUNT_OFF, PHASE_OFF, FORCE_OFF, STAY_OFF = base.COUNT_OFF, base.PHASE_OFF, 0x64, 0x08

TICK_NAME = "pin_tick"
# 0x143053c14 call 0x143051e78 | 0x143053c19 xor r12d,r12d; lea rsi,[rbx+0x78]; mov ebp,1;
# cmp byte [rbx+0x64],r12b; je; mov edx,ebp; mov [rbx+0x38],r12d -- the first lines of the update
TICK_PATTERN = "E8 ?? ?? ?? ?? 45 33 E4 48 8D 73 78 BD 01 00 00 00 44 38 63 64 74 0E 8B D5 44 89 63 38"
TICK_AT, TICK_STOLEN = 5, "45 33 E4 48 8D 73 78"
TICK_EXE_SITE = 0x143053C19
CAVES = ("pin_stamp", "pin_hold", TICK_NAME)
R = TRACE_RING_AT


def _edit(text, old, new, what):
    if text.count(old) != 1:
        raise SystemExit(f"[takeoff_trace] REFUSING: {what}: {old!r} found {text.count(old)} times in the "
                         "shipped source (pin_cave_asm changed?)")
    return text.replace(old, new)


def _log(buf, kind, extra32, tag):
    """One trace entry keyed by rbx (the FC), tick in r8d; uses r11 (slot), edx (seq), ecx; keeps eax."""
    return f"""
        cmp dword ptr [{buf} + {TRACE_ON_AT}], 0
        je skip_{tag}
        mov edx, 1
        lock xadd dword ptr [{buf} + {TRACE_COUNT_AT}], edx
        mov r11d, edx
        and r11d, {TRACE_SLOTS - 1}
        shl r11, 5
        add r11, {buf}
        inc edx
        mov dword ptr [r11 + {R + 28}], 0
        mov qword ptr [r11 + {R}], rbx
        mov dword ptr [r11 + {R + 8}], r8d
        mov ecx, dword ptr [rbx + {COUNT_OFF:#x}]
        mov dword ptr [r11 + {R + 12}], ecx
        mov ecx, dword ptr [rbx + {PHASE_OFF:#x}]
        mov dword ptr [r11 + {R + 16}], ecx
        {kind}
        mov dword ptr [r11 + {R + 20}], ecx
        mov dword ptr [r11 + {R + 24}], {extra32}
        mov dword ptr [r11 + {R + 28}], edx
    skip_{tag}:
"""


def hold_source(mutate=None):
    s = base.hold_source()
    s = _edit(s, "        jne passthrough\n",
              "        jne passthrough\n        mov r8d, -1\n        mov r10d, -1\n", "hold: preset")
    s = _edit(s, f"        lock inc dword ptr [r9 + {base.UNMATCHED_AT}]\n        jmp free\n",
              f"        lock inc dword ptr [r9 + {base.UNMATCHED_AT}]\n        mov r10d, {UNMATCHED - 2**32}\n"
              "        jmp free\n", "hold: unmatched marker")
    # [D39] two held paths (the model's own window, the unit rule): both traced
    if s.count("        mov eax, 1\n        jmp resume\n") != 2:
        raise SystemExit("[takeoff_trace] REFUSING: hold: want the two held paths of the shipped source")
    s = s.replace("        mov eax, 1\n        jmp resume\n", "        mov eax, 1\n        jmp traced\n")
    s = _edit(s, "    resume:\n",
              "    traced:\n" + _log("r9", f"lea ecx, [rax + {KIND_FREE}]", "r10d", "answer") + "    resume:\n",
              "hold: answer entry")
    s = _edit(s, "    passthrough:\n",
              "    passthrough:\n        mov r8d, -1\n        mov rcx, [rbx]\n        test rcx, rcx\n"
              "        jz pt_tick\n" + base._tick("rcx", "r8d", "pt_tick") + "    pt_tick:\n"
              + _log("r9", f"mov ecx, {KIND_PASS}", "0", "pass"), "hold: pass entry")
    return _mutate(s, mutate)


def stamp_source(mutate=None):
    """The shipped stamp cave; after it wrote the entry (rcx = flying entity, rdx = its table entry,
    r8d = tick, r10 = buffer), one trace entry. rax r9 r11 are free there (pushed, popped at done).
    [D11] The entry is filled BEFORE the shipped raise (so it holds the countdown as it was) and closed
    (seq written) after it; a raise rewrites its kind to KIND_HIT_RAISED first. The raise uses rax rdx
    r8 r9 and keeps r11 (this entry, 0 with the trace off); r9 (the seq) is pushed around it."""
    s = base.stamp_source()
    s = _edit(s, "    write:\n        mov dword ptr [rdx + 8], r8d\n        lock inc dword ptr [rdx + 12]\n",
              f"""    write:
        mov dword ptr [rdx + 8], r8d
        lock inc dword ptr [rdx + 12]
        xor r11d, r11d
        cmp dword ptr [r10 + {TRACE_ON_AT}], 0
        je skip_hit
        mov r9d, 1
        lock xadd dword ptr [r10 + {TRACE_COUNT_AT}], r9d
        mov r11d, r9d
        and r11d, {TRACE_SLOTS - 1}
        shl r11, 5
        add r11, r10
        inc r9d
        mov dword ptr [r11 + {R + 28}], 0
        mov qword ptr [r11 + {R}], rcx
        mov dword ptr [r11 + {R + 8}], r8d
        mov eax, dword ptr [rdx + 12]
        mov dword ptr [r11 + {R + 24}], eax
        mov rax, qword ptr [rcx + {base.FC_OFF:#x}]
        mov edx, dword ptr [rax + {COUNT_OFF:#x}]
        mov dword ptr [r11 + {R + 12}], edx
        mov edx, dword ptr [rax + {PHASE_OFF:#x}]
        mov dword ptr [r11 + {R + 16}], edx
        mov dword ptr [r11 + {R + 20}], {KIND_HIT}
    skip_hit:
        push r9
""", "stamp: hit entry")
    s = _edit(s, f"        lock cmpxchg dword ptr [r8 + {base.COUNT_OFF:#x}], edx\n",
              f"""        lock cmpxchg dword ptr [r8 + {base.COUNT_OFF:#x}], edx
        jne raise_done
        test r11, r11
        jz raise_done
        mov dword ptr [r11 + {R + 20}], {KIND_HIT_RAISED}
""", "stamp: raise mark")
    s = _edit(s, "    raise_done:\n", f"""    raise_done:
        pop r9
        test r11, r11
        jz skip_seq
        mov dword ptr [r11 + {R + 28}], r9d
    skip_seq:
""", "stamp: hit entry closed")
    return _mutate(s, mutate)


def tick_source(mutate=None):
    s = f"""
        pushfq
        push rax
        push rcx
        push rdx
        push r8
        push r10
        push r11
        mov r10, {base.BUFFER_PLACEHOLDER:#x}
        mov r8d, -1
        mov rcx, [rbx]
        test rcx, rcx
        jz have_tick
{base._tick("rcx", "r8d", "have_tick")}
    have_tick:
        movzx eax, byte ptr [rbx + {FORCE_OFF:#x}]
        cmp qword ptr [rbx + {STAY_OFF:#x}], 0
        je no_stay
        or eax, 0x100
    no_stay:
{_log("r10", f"mov ecx, {KIND_UPDATE}", "eax", "tick")}
        pop r11
        pop r10
        pop r8
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


SOURCES = {"pin_stamp": stamp_source, "pin_hold": hold_source, TICK_NAME: tick_source}


def assemble(name, mutate=None):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_64
    code = bytes(Ks(KS_ARCH_X86, KS_MODE_64).asm(SOURCES[name](mutate), 0x1000)[0])
    if code.count(struct.pack("<Q", base.BUFFER_PLACEHOLDER)) != 1:
        raise SystemExit(f"{name}: the buffer placeholder must appear exactly once")
    return code


def layout():
    lay = dict(base.layout())
    lay.update(bytes=BYTES, magic=MAGIC.decode(), trace_on_at=TRACE_ON_AT, trace_count_at=TRACE_COUNT_AT,
               trace_ring_at=TRACE_RING_AT, trace_entry=TRACE_ENTRY, trace_slots=TRACE_SLOTS)
    return lay


def source_sha():
    """sha256 over the three traced sources, the shipped caves' own sha, the pin_tick site and the layout."""
    norm = lambda s: "\n".join(line.strip() for line in s.splitlines() if line.strip())
    blob = json.dumps({"caves": {n: norm(SOURCES[n]()) for n in CAVES}, "shipped": base.source_sha(),
                       "tick": [TICK_PATTERN, TICK_AT, TICK_STOLEN], "layout": layout()}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --- emulator ---------------------------------------------------------------
_ORIGINAL_MACHINE = base.Machine
TICK_CODE = base.CODE + 0x1000 * len(base.CAVES)


class TraceMachine(_ORIGINAL_MACHINE):
    """pin_cave_asm's machine with the traced caves in place of the shipped ones, the trace region
    mapped, and pin_tick loaded. ``trace_on`` is written by every reset."""
    trace_on = 1

    def __init__(self, mutate=(), tmutate=None):
        self._ready = False
        super().__init__(mutate)
        mapped = 0x10000 * ((base.BUFFER_BYTES + 0xFFFF) // 0x10000)
        self.uc.mem_map(base.BUF + mapped, 0x10000 * ((BYTES - mapped + 0xFFFF) // 0x10000))
        for i, name in enumerate(CAVES):
            mut = tmutate[1:] if tmutate and tmutate[0] == name else None
            code = base.filled(assemble(name, mut), base.BUF, base.RESUME)
            at = TICK_CODE if name == TICK_NAME else base.CODE + 0x1000 * list(base.CAVES).index(name)
            self.code[name] = (at, len(code))
            self.uc.mem_write(at, code)
        self._ready = True
        self.reset()

    def reset(self, windows=base.WINDOWS, mode=1, unit_window=base.UNIT_WINDOW):
        super().reset(windows, mode, unit_window)
        if self._ready:
            self.uc.mem_write(base.BUF + TRACE_AT, struct.pack("<II", self.trace_on, 0))

    def preset_count(self, n):
        self.uc.mem_write(base.BUF + TRACE_COUNT_AT, struct.pack("<I", n))

    def written(self):
        return struct.unpack("<I", self.uc.mem_read(base.BUF + TRACE_COUNT_AT, 4))[0]

    def entry(self, seq):
        raw = bytes(self.uc.mem_read(base.BUF + R + TRACE_ENTRY * (seq % TRACE_SLOTS), TRACE_ENTRY))
        key, tick, count, phase, kind, extra, seq1 = struct.unpack("<QIIIIII", raw)
        return {"key": key, "tick": tick, "count": count, "phase": phase, "kind": kind, "extra": extra,
                "seq1": seq1}

    def update(self, fc):
        """One pass of pin_tick with rbx = ``fc``: every register and the flags must come back."""
        x, uc = self.x, self.uc
        begin, size = self.code[TICK_NAME]
        self._registers()
        uc.reg_write(x.UC_X86_REG_RBX, fc)
        before = {r: uc.reg_read(r) for r in self.all}
        uc.emu_start(begin, begin + size, count=10_000)
        return {"ran to the end": uc.reg_read(x.UC_X86_REG_RIP) == begin + size,
                "registers": all(uc.reg_read(r) == v for r, v in before.items()),
                "rsp": uc.reg_read(x.UC_X86_REG_RSP) == base.STACK + 0x8000,
                "flags": (uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFF) == base.FLAGS}


@contextmanager
def _shipped_check_on_traced_caves(trace_on):
    """pin_cave_asm.check() builds ``Machine(...)``: make that the traced machine for the duration."""
    TraceMachine.trace_on = trace_on
    base.Machine = TraceMachine
    try:
        yield
    finally:
        base.Machine = _ORIGINAL_MACHINE
        TraceMachine.trace_on = 1


def check_trace(tmutate=None):
    """([failure], checks) of the trace entries themselves."""
    fails, n = [], [0]
    m = TraceMachine(tmutate=tmutate)

    def expect(name, got, want):
        n[0] += 1
        if got != want:
            fails.append(f"{name}: got {got!r}, want {want!r}")

    def clean(name, r, keys=("ran to the end", "registers", "rsp", "flags")):
        for k in keys:
            expect(f"{name}: {k}", r[k], True)

    def one(name, before, want):
        expect(name + ": entries written", m.written() - before, 1 if want else 0)
        if want:
            got = m.entry(before)
            expect(name + ": entry", {k: got[k] for k in want}, want)
            expect(name + ": seq last", got["seq1"], (before + 1) & 0xFFFFFFFF)

    # pin_tick: the update's state before the state machine
    for name, count, phase, force, stay, tick, model in (
            ("update, phase 1, countdown 0", 0, 1, 0, 0, 204, True),
            ("update, phase 2, countdown 0", 0, 2, 0, 0, 205, True),
            ("update, phase 2, countdown 30, +0x64 set", 30, 2, 1, 0, 9, True),
            ("update, stay-down field set", 100, 1, 0, 1, 77, True),
            ("update, FC without model", 12, 1, 0, 0, 5, False)):
        m.reset(); m.now(tick)
        ent = m.model(1)
        fc = m.fc_state(ent, count, phase, force, stay)
        if not model:
            m.uc.mem_write(fc, struct.pack("<Q", 0))
        m.preset_count(TRACE_SLOTS + 3)                 # the ring wraps
        clean(name, m.update(fc))
        one(name, TRACE_SLOTS + 3, {"key": fc, "tick": tick if model else NO_TICK, "count": count,
                                    "phase": phase, "kind": KIND_UPDATE,
                                    "extra": force | (0x100 if stay else 0)})
    m.trace_on = 0
    m.reset(); m.now(3)
    ent = m.model(1)
    clean("update, trace off", m.update(m.fc_state(ent, 5, 1)))
    one("update, trace off", 0, None)
    m.trace_on = 1

    # pin_hold: one entry per answer, the rule's answer unchanged
    w = base.WINDOW_OF["large"]
    for name, hit_at, now, want_al in (("held: hit 1 tick ago", 203, 204, 1), ("held: same tick", 204, 204, 1),
                                       ("free: window run out", 100, 204, 0)):
        m.reset(); m.now(now)
        ent = m.model(1, size="large")
        fc = m.fc_state(ent, 7, 2)
        m.put(ent, hit_at)
        r = m.hold([ent], ent)
        expect(name + ": answer", (r["where"], r["al"]), ("resume", want_al))
        clean(name, r, ("callee-saved", "rsp"))
        one(name, 0, {"key": fc, "tick": now, "count": 7, "phase": 2,
                      "kind": KIND_HELD if want_al else KIND_FREE, "extra": w})
    m.reset(); m.now(50)
    ent, other = m.model(1), m.model(2)
    fc = m.fc_state(ent, 0, 1)
    r = m.hold([other], ent)
    expect("unmatched: answer", (r["where"], r["al"]), ("resume", 0))
    one("unmatched", 0, {"key": fc, "tick": 50, "kind": KIND_FREE, "extra": UNMATCHED})
    m.reset(); m.now(50)
    ent = m.model(1)
    fc = m.fc_state(ent, 3, 1)
    r = m.hold([ent], ent, fc_model=False)
    expect("no model: answer", (r["where"], r["al"]), ("resume", 0))
    one("no model", 0, {"key": fc, "tick": NO_TICK, "kind": KIND_FREE, "extra": NO_MODEL})
    m.reset(mode=2); m.now(61)
    ent = m.model(1)
    fc = m.fc_state(ent, 30, 2)
    r = m.hold([ent], ent)
    expect("mode 2: passes through", r["where"], "through")
    one("mode 2", 0, {"key": fc, "tick": 61, "count": 30, "phase": 2, "kind": KIND_PASS, "extra": 0})
    m.trace_on = 0
    m.reset(); m.now(50)
    ent = m.model(1)
    m.fc_state(ent, 3, 1)
    m.hold([ent], ent)
    one("hold, trace off", 0, None)
    m.trace_on = 1

    # pin_stamp: a recorded melee hit, with its FC's countdown and phase at that moment
    m.reset(); m.now(204)
    ent = m.model(1)
    m.fc_state(ent, 0, 1)
    m.put(ent, 100, hits=4)
    clean("hit", m.stamp(base.MELEE, 40, ent))
    one("hit", 0, {"key": ent, "tick": 204, "count": 0, "phase": 1, "kind": KIND_HIT, "extra": 5})
    m.reset(); m.now(204)
    mount = m.model(2)
    m.fc_state(mount, 9, 2)
    rider = m.model(3, fc=False, parent=2)
    clean("hit on a rider", m.stamp(base.MELEE, 40, rider))
    one("hit on a rider", 0, {"key": mount, "tick": 204, "count": 9, "phase": 2, "kind": KIND_HIT, "extra": 1})
    m.reset(); m.now(204)
    ent = m.model(1)
    m.fc_state(ent, 0, 1)
    clean("impact, not recorded", m.stamp(5, 40, ent))
    one("impact, not recorded", 0, None)
    # [D11] the raise: kind 6 with the countdown from BEFORE it; the FC's countdown is 1 afterwards
    for name, count, phase, living, mode, raised in (
            ("raised, phase 1", 0, 1, True, 1, True), ("raised, phase 2", 0, 2, True, 1, True),
            ("not raised, countdown 5", 5, 2, True, 1, False), ("not raised, phase 3", 0, 3, True, 1, False),
            ("not raised, not living", 0, 2, False, 1, False), ("not raised, mode 2", 0, 2, True, 2, False)):
        m.reset(mode=mode); m.now(300)
        ent = m.model(1)
        m.living([ent] if living else [m.model(2)])
        m.fc_state(ent, count, phase)
        m.preset_count(TRACE_SLOTS - 1)                 # the ring wraps right here
        clean("hit " + name, m.stamp(base.MELEE, 40, ent))
        one("hit " + name, TRACE_SLOTS - 1, {"key": ent, "tick": 300, "count": count, "phase": phase,
                                             "kind": KIND_HIT_RAISED if raised else KIND_HIT, "extra": 1})
        expect("hit " + name + ": countdown after", m.countdown(ent), base.RAISE_TO if raised else count)
    m.trace_on = 0
    m.reset(); m.now(300)
    ent = m.model(1)
    m.living([ent])
    m.fc_state(ent, 0, 2)
    clean("hit raised, trace off", m.stamp(base.MELEE, 40, ent))
    one("hit raised, trace off", 0, None)
    expect("hit raised, trace off: countdown after", m.countdown(ent), base.RAISE_TO)
    m.trace_on = 1
    return fails, n[0]


def check():
    """([failure], checks): the shipped emulator check on the traced caves (trace off, then on), then the
    trace entries."""
    fails, total = [], 0
    for on in (0, 1):
        with _shipped_check_on_traced_caves(on):
            f, k = base.check()
        fails += [f"shipped check, trace {'on' if on else 'off'}: {x}" for x in f]
        total += k
    f, k = check_trace()
    return fails + f, total + k


MUTANTS = (
    ("held logged as free", "pin_hold", f"lea ecx, [rax + {KIND_FREE}]", f"mov ecx, {KIND_FREE}"),
    ("hold entry without seq", "pin_hold", f"mov dword ptr [r11 + {R + 28}], edx\n    skip_answer",
     "nop\n    skip_answer"),
    ("unmatched not marked", "pin_hold", f"mov r10d, {UNMATCHED - 2**32}\n", "nop\n"),
    ("passthrough not logged", "pin_hold", "je skip_pass", "jmp skip_pass"),
    ("hold logs the window as the tick", "pin_hold",
     f"mov dword ptr [r11 + {R + 8}], r8d\n        mov ecx, dword ptr [rbx + {COUNT_OFF:#x}]\n"
     f"        mov dword ptr [r11 + {R + 12}], ecx\n        mov ecx, dword ptr [rbx + {PHASE_OFF:#x}]\n"
     f"        mov dword ptr [r11 + {R + 16}], ecx\n        lea",
     f"mov dword ptr [r11 + {R + 8}], r10d\n        mov ecx, dword ptr [rbx + {COUNT_OFF:#x}]\n"
     f"        mov dword ptr [r11 + {R + 12}], ecx\n        mov ecx, dword ptr [rbx + {PHASE_OFF:#x}]\n"
     f"        mov dword ptr [r11 + {R + 16}], ecx\n        lea"),
    ("trace-on flag ignored by the hold entry", "pin_hold", "je skip_answer", "nop"),
    ("update: countdown read from the phase field", TICK_NAME,
     f"mov ecx, dword ptr [rbx + {COUNT_OFF:#x}]", f"mov ecx, dword ptr [rbx + {PHASE_OFF:#x}]"),
    ("update: stay-down field not read", TICK_NAME, "or eax, 0x100", "nop"),
    ("update: a register lost", TICK_NAME, "        pop r8\n", "        pop rax\n"),
    ("update: ring not wrapped", TICK_NAME, f"and r11d, {TRACE_SLOTS - 1}", f"and r11d, {2 * TRACE_SLOTS - 1}"),
    ("update: model read from the FC's second field", TICK_NAME, "mov rcx, [rbx]\n", "mov rcx, [rbx + 8]\n"),
    ("hit: countdown of the entity, not of its FC", "pin_stamp",
     f"mov edx, dword ptr [rax + {COUNT_OFF:#x}]", f"mov edx, dword ptr [rcx + {COUNT_OFF:#x}]"),
    ("hit: tick not written", "pin_stamp", f"mov dword ptr [r11 + {R + 8}], r8d", f"mov dword ptr [r11 + {R + 8}], 0"),
    ("hit: raise not marked", "pin_stamp", f"mov dword ptr [r11 + {R + 20}], {KIND_HIT_RAISED}", "nop"),
    ("hit: entry never closed", "pin_stamp", f"mov dword ptr [r11 + {R + 28}], r9d\n    skip_seq:",
     "nop\n    skip_seq:"),
    ("hit: no entry pointer reset with the trace off", "pin_stamp", "        xor r11d, r11d\n", ""),
    ("hit: seq not kept over the raise", "pin_stamp", "        pop r9\n        test r11, r11\n        jz skip_seq",
     "        pop r9\n        xor r9d, r9d\n        test r11, r11\n        jz skip_seq"),
)


def negative_controls():
    """[mutant name] whose broken cave passed every trace case (must be empty)."""
    out = []
    for name, cave, old, new in MUTANTS:
        try:
            fails, _n = check_trace((cave, old, new))
        except Exception as exc:                  # because an emulator fault on a broken cave is a catch too
            fails = [repr(exc)]
        if not fails:
            out.append(name)
    return out


# --- site table -------------------------------------------------------------
def site_lua(codes):
    lines = [
        "-- takeoff_trace_site.lua -- GENERATED by tools/pipelines/takeoff_trace_asm.py (--write-site).",
        "-- TEST-ONLY: never in a player's pack. The shipped take-off caves with a trace, plus pin_tick; built",
        "-- into a test pack by build_pin_on_hit_probe.py --trace-from in place of data/takeoff_site.lua.",
        "return {",
        f"    owner = '{base.OWNER}',",
        f"    feature = '{base.FEATURE}',",
        "    entries = {",
    ]
    for name in CAVES:
        if name == TICK_NAME:
            pattern, at, expect = TICK_PATTERN, TICK_AT, TICK_STOLEN
        else:
            pattern, at, expect, _role = base.CAVES[name]
        lines += cave_site_text.cave_entry_lines(name, base.FEATURE, pattern, at, expect,
                                                 base.bytes_template(codes[name]))
    for name, (pattern, pins) in base.ANCHORS.items():
        lines += [f"        -- {pins}",
                  f"        {{ name = '{name}', feature = '{base.FEATURE}', kind = 'anchor',",
                  f"          pattern = '{pattern}' }},"]
    lay = layout()
    lines += [
        "    },",
        "    caves = { " + ", ".join(f"'{n}'" for n in CAVES) + " },",
        f"    hold = '{base.HOLD_NAME}', resume_at = {base.HOLD_RESUME_AT},",
        "    layout = {",
        f"        bytes = {lay['bytes']}, mode_at = {lay['mode_at']},",
        f"        stamps_at = {lay['stamps_at']}, allowed_at = {lay['allowed_at']},",
        f"        magic_at = {lay['magic_at']}, magic = '{lay['magic']}',",
        f"        dropped_at = {lay['dropped_at']}, unmatched_at = {lay['unmatched_at']},",
        f"        held_at = {lay['held_at']}, free_at = {lay['free_at']}, unsized_at = {lay['unsized_at']},",
        f"        table_at = {lay['table_at']}, table_slots = {lay['table_slots']},",
        f"        entry_bytes = {lay['entry_bytes']}, size_at = {lay['size_at']},",
        f"        windows_at = {lay['windows_at']},",
        "        windows = { " + ", ".join(str(w) for w in lay['windows']) + " },",
        "        size_codes = { " + ", ".join(f"{s} = {c}" for s, c in
                                            sorted(lay['size_codes'].items(), key=lambda i: i[1])) + " },",
        # [D39] the unit rule's ticks, counters and table: lib/takeoff.lua writes the ticks and clears the table
        f"        unit_ticks_at = {lay['unit_ticks_at']}, unit_ticks = {lay['unit_ticks']},",
        f"        unit_held_at = {lay['unit_held_at']}, unit_stamps_at = {lay['unit_stamps_at']},",
        f"        unit_dropped_at = {lay['unit_dropped_at']},",
        f"        unit_table_at = {lay['unit_table_at']}, unit_slots = {lay['unit_slots']},",
        f"        trace_on_at = {TRACE_ON_AT}, trace_count_at = {TRACE_COUNT_AT},",
        f"        trace_ring_at = {TRACE_RING_AT}, trace_entry = {TRACE_ENTRY}, trace_slots = {TRACE_SLOTS},",
        "    },",
        f"    format = {2 + int(source_sha()[:5], 16)},",
        f"    build = '{base.BUILD}',",
        f"    source_sha = '{source_sha()}',",
        "    trace = true,",
        "}",
    ]
    return "\n".join(lines) + "\n"


def check_site_file(path=TRACE_SITE):
    """Offline (no keystone): the committed trace table was generated from the current sources (the
    shipped caves included). Returns its text; raises otherwise."""
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    needle = f"source_sha = '{source_sha()}'"
    if needle not in text:
        raise RuntimeError(f"[takeoff_trace] REFUSING: {path} is missing or stale (lacks {needle!r}); "
                           "rerun takeoff_trace_asm.py --write-site")
    return text


def check_exe(exe_path):
    """The shipped sites and anchors (pin_cave_asm.check_exe) and pin_tick, each exactly once, pin_tick at
    the address of the static read. Returns {name: address}; raises otherwise."""
    import pefile
    found = base.check_exe(exe_path)
    pe = pefile.PE(str(exe_path), fast_load=True)
    want = bytes.fromhex(TICK_STOLEN.replace(" ", ""))
    hits = []
    for sec in pe.sections:
        if not sec.Characteristics & 0x20000000:
            continue
        data, va = sec.get_data(), pe.OPTIONAL_HEADER.ImageBase + sec.VirtualAddress
        hits += [va + m.start() + TICK_AT for m in base._regex(TICK_PATTERN).finditer(data)
                 if data[m.start() + TICK_AT:m.start() + TICK_AT + len(want)] == want]
    if hits != [TICK_EXE_SITE]:
        raise RuntimeError(f"[takeoff_trace] REFUSING: {TICK_NAME} found at {[hex(h) for h in hits]}, "
                           f"want {TICK_EXE_SITE:#x} (another build?)")
    found[TICK_NAME] = hits[0]
    return found


def main(argv):
    exe = Path(r"D:/SteamLibrary/steamapps/common/Total War WARHAMMER III/Warhammer3.exe")
    found = check_exe(exe)
    codes = {name: assemble(name) for name in CAVES}
    fails, n = check()
    for f in fails:
        print("FAIL", f)
    print("caves: " + ", ".join(f"{k} {len(c)} bytes" for k, c in codes.items())
          + f"; emulator: {n} checks, " + ("PASS" if not fails else f"{len(fails)} FAIL"))
    survivors = [] if fails else negative_controls()
    for name in survivors:
        print("FAIL negative control passed every case:", name)
    if not fails:
        print(f"negative controls: {len(MUTANTS)} broken caves,",
              "each caught" if not survivors else f"{len(survivors)} NOT caught")
    print("exe sites: " + ", ".join(f"{k} {v:#x}" for k, v in found.items() if k in CAVES))
    bad = bool(fails or survivors)
    if "--write-site" in argv:
        if bad:
            raise SystemExit("not writing the trace site table: the checks failed")
        TRACE_SITE.write_text(site_lua(codes), encoding="utf-8", newline="\n")
        print("wrote", TRACE_SITE)
    elif not bad:
        have = TRACE_SITE.read_text(encoding="utf-8").replace("\r\n", "\n") if TRACE_SITE.is_file() else ""
        print("trace site table:", "current" if have == site_lua(codes) else "STALE (rerun with --write-site)")
        bad = have != site_lua(codes)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
