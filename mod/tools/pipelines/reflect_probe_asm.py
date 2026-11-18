"""TEST-ONLY: two logger caves for the impact-damage probe (update-1117 part C, user ruling D4).

Never in a player's pack: built only by pipelines/build_pin_on_hit_probe.py --reflect, together
with pipelines/reflect_probe.lua. Question: does a diving flyer that runs head-on into braced
``charge_reflection`` infantry get the engine's impact reflection, and how much damage does it
take per hit -- with a positive control (ground cavalry into the same braced spearmen), because
the earlier logger recorded only flyer participants, so its "0 reflections" was never shown to
mean "no reflection" (design.md section 1).

Exe 9.0.5, PE timestamp 0x6ae2a00b (both sites are checked against the installed exe by
``check_exe``; the site loader needs each pattern exactly once).

``rf_refl`` at the ENTRY of the impact reflection 0x1430afae4 (only caller 0x14325bf46 in
0x14325bbec). Entry: rcx ctx, rdx out ({u32 knock kind, i32 damage}, read back by the caller at
0x14325bf4b / 0x14325bf78), r8 the braced reflector, r9 the charger, [rsp+0x28] closing speed
(F32; the caller stores xmm7 at its [rsp+0x20] at 0x14325bf2d). EVERY call is logged (no flyer
filter: the positive control's charger is a ground unit). 64-byte entry:
  +0 u64 reflector   +8 u64 charger   +16 u64 return address   +24 f32 closing speed
  +28 u32 battle tick (charger, else reflector)   +32 u64 reflector unit [+0x2e8]
  +40 u64 charger unit [+0x2e8] (else its mount's)   +48 u32 charger is / rides a flyer (FC +0x128)
  +52 f32 reflector +0xbc (bracing multiplier, static read)   +56 u32 reflector +0x6c
  +60 u32 seq + 1 (written last)
``rf_dmg`` inside the damage applier 0x14325a9c4, at +0x54 (0x14325aa18: ``mov r15d,[rbp+0x6f];
mov r14d,eax; mov r13b,[rbp+0x67]; mov [rbp+0x57],eax``), i.e. after the applier scaled the damage
(eax, the applier's own rounding call 0x1405a1d2c touches only rax / xmm0) and before it uses it.
There rdx = the victim ([ctx+8], loaded at 0x14325a9e6 and still read at 0x14325aa41), rbp = entry
rsp - 0x3f, so [rbp+0x3f] = the return address and [rbp+0x6f] = the damage type (entry [rsp+0x30]).
Not at the entry: the shipped take-off cave pin_stamp owns the entry's first 10 bytes; this
site's pattern starts after them (0x14325a9ce), so it matches with or without pin_stamp. The
probe installs at Deployed, after the take-off battle entry installed pin_stamp at chunk scope
(pin_stamp's own pattern spans this site; installed the other way round, the take-off rule
would be off for that battle -- its BATTLE line says so). EVERY call is logged:
  +0 u64 return address   +8 u64 victim   +16 u64 victim unit [+0x2e8] (else its mount's)
  +24 i32 damage (scaled)   +28 u32 damage type   +32 u32 battle tick
  +36 u32 victim is / rides a flyer   +40 u64 the flying entity (0: none)   +60 u32 seq + 1
The reflection's own damage call is the applier call at 0x14325bf8b (type 0, damage = the
reflection's out +4), so its entries carry return address 0x14325bf90.

``python reflect_probe_asm.py [--write-site PATH]`` (keystone + unicorn) assembles both caves,
runs them in Unicorn against synthetic objects, runs mutated sources that must each fail, and
writes the site table to PATH (default: print only).
"""
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWNER, FEATURE = "reflect_probe", "reflect_probe"
SITE_REQUIRE = "script/reflect_probe/reflect_probe_site"     # Lua require name of the site table
REFL_PATTERN = ("48 8B C4 48 89 58 08 48 89 68 10 48 89 70 18 48 89 78 20 41 56 48 81 EC 40 01 00 00 "
                "0F 29 70 E8 48 8B F9 48 8B 41 08")
REFL_STOLEN = "48 8B C4 48 89 58 08 48 89 68 10"
# from 0x14325a9ce (after pin_stamp's 10 stolen bytes) to 0x14325aa26; the cave sits at +0x4a
DMG_PATTERN = ("41 55 41 56 41 57 48 8D 6C 24 F9 48 81 EC A0 00 00 00 0F 57 C0 48 8B DA 48 8B 51 08 "
               "4D 8B E1 48 8B F9 48 8B 42 58 4C 8B 90 40 04 00 00 41 8B C0 4D 8B 9A A8 00 00 00 "
               "F3 48 0F 2A C0 F3 41 0F 59 83 C0 02 00 00 E8 ?? ?? ?? ?? "
               "44 8B 7D 6F 44 8B F0 44 8A 6D 67 89 45 57 41 83 FF 02")
DMG_AT = 0x4A
DMG_STOLEN = "44 8B 7D 6F 44 8B F0 44 8A 6D 67 89 45 57"
REFLECT_DAMAGE_RETURN = 0x14325BF90      # the reflection's own applier call returns here
EXE_SITES = {"rf_refl": 0x1430AFAE4, "rf_dmg": 0x14325AA18}   # build 6ae2a00b

MODE_AT, MAGIC_AT, REFL_COUNT_AT, DMG_COUNT_AT = 0, 8, 16, 20
MAGIC = b"RFPROBE1"
REFL_RING_AT, REFL_SLOTS = 64, 4096
DMG_RING_AT, DMG_SLOTS = REFL_RING_AT + REFL_SLOTS * 64, 32768
ENTRY = 64
BYTES = DMG_RING_AT + DMG_SLOTS * ENTRY
BUF = 0x1122334455667788
FC, PARENT, UNIT, BATTLE, TICKS, TICK = 0x128, 0x2E0, 0x2E8, 0x58, 0x440, 0x98
BRACE_MULT, IMMOVABLE = 0xBC, 0x6C


def _tick(reg, out, tag):
    """battle tick of entity ``reg`` into ``out`` (32-bit), 0 when a link is null; rax scratch."""
    return f"""
    xor {out}, {out}
    test {reg}, {reg}
    jz tick_{tag}
    mov rax, qword ptr [{reg} + {BATTLE:#x}]
    test rax, rax
    jz tick_{tag}
    mov rax, qword ptr [rax + {TICKS:#x}]
    test rax, rax
    jz tick_{tag}
    mov {out}, dword ptr [rax + {TICK:#x}]
tick_{tag}:
"""


REFL_PUSHES = 6


def refl_source(mutate=None):
    s = f"""
    pushfq
    push rax
    push rcx
    push rdx
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    mov edx, 1
    lock xadd dword ptr [r10 + {REFL_COUNT_AT}], edx
    mov r11d, edx
    and r11d, {REFL_SLOTS - 1}
    shl r11, 6
    lea r11, [r10 + r11 + {REFL_RING_AT}]
    inc edx
    mov dword ptr [r11 + 60], 0
    push rdx
    mov qword ptr [r11], r8
    mov qword ptr [r11 + 8], r9
    mov rax, qword ptr [rsp + {8 * (REFL_PUSHES + 1)}]
    mov qword ptr [r11 + 16], rax
    mov eax, dword ptr [rsp + {8 * (REFL_PUSHES + 1) + 0x28}]
    mov dword ptr [r11 + 24], eax
    {_tick("r9", "ecx", "charger")}
    test ecx, ecx
    jnz have_tick
    {_tick("r8", "ecx", "reflector")}
have_tick:
    mov dword ptr [r11 + 28], ecx
    xor eax, eax
    xor ecx, ecx
    mov dword ptr [r11 + 52], ecx
    mov dword ptr [r11 + 56], ecx
    test r8, r8
    jz no_r8
    mov rax, qword ptr [r8 + {UNIT:#x}]
    mov ecx, dword ptr [r8 + {BRACE_MULT:#x}]
    mov dword ptr [r11 + 52], ecx
    mov ecx, dword ptr [r8 + {IMMOVABLE:#x}]
    mov dword ptr [r11 + 56], ecx
no_r8:
    mov qword ptr [r11 + 32], rax
    xor eax, eax
    xor ecx, ecx
    test r9, r9
    jz no_r9
    mov rax, qword ptr [r9 + {UNIT:#x}]
    cmp qword ptr [r9 + {FC:#x}], 0
    setne cl
    mov rdx, qword ptr [r9 + {PARENT:#x}]
    test rdx, rdx
    jz no_r9
    test rax, rax
    jnz parent_fc
    mov rax, qword ptr [rdx + {UNIT:#x}]
parent_fc:
    cmp qword ptr [rdx + {FC:#x}], 0
    je no_r9
    mov ecx, 1
no_r9:
    mov qword ptr [r11 + 40], rax
    mov dword ptr [r11 + 48], ecx
    pop rdx
    mov dword ptr [r11 + 60], edx
done:
    pop r11
    pop r10
    pop rdx
    pop rcx
    pop rax
    popfq
"""
    return _mutate(s, mutate)


def dmg_source(mutate=None):
    s = f"""
    pushfq
    push rax
    push rcx
    push r9
    push r10
    push r11
    mov r10, {BUF:#x}
    cmp dword ptr [r10 + {MODE_AT}], 0
    je done
    mov r9d, 1
    lock xadd dword ptr [r10 + {DMG_COUNT_AT}], r9d
    mov r11d, r9d
    and r11d, {DMG_SLOTS - 1}
    shl r11, 6
    mov rcx, {DMG_RING_AT}
    add r11, rcx
    add r11, r10
    mov dword ptr [r11 + 60], 0
    mov dword ptr [r11 + 36], 0
    mov qword ptr [r11 + 40], 0
    mov rcx, qword ptr [rbp + 0x3f]
    mov qword ptr [r11], rcx
    mov qword ptr [r11 + 8], rdx
    mov ecx, dword ptr [rsp + 32]
    mov dword ptr [r11 + 24], ecx
    mov ecx, dword ptr [rbp + 0x6f]
    mov dword ptr [r11 + 28], ecx
    {_tick("rdx", "ecx", "victim")}
    mov dword ptr [r11 + 32], ecx
    xor eax, eax
    xor ecx, ecx
    test rdx, rdx
    jz no_victim
    mov rax, qword ptr [rdx + {UNIT:#x}]
    mov rcx, rdx
    cmp qword ptr [rdx + {FC:#x}], 0
    jne flyer
    mov rcx, qword ptr [rdx + {PARENT:#x}]
    test rcx, rcx
    jz no_flyer
    test rax, rax
    jnz parent_fc
    mov rax, qword ptr [rcx + {UNIT:#x}]
parent_fc:
    cmp qword ptr [rcx + {FC:#x}], 0
    jne flyer
no_flyer:
    jmp unit_out
flyer:
    mov qword ptr [r11 + 40], rcx
    mov dword ptr [r11 + 36], 1
unit_out:
no_victim:
    mov qword ptr [r11 + 16], rax
    inc r9d
    mov dword ptr [r11 + 60], r9d
done:
    pop r11
    pop r10
    pop r9
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


SOURCES = {"rf_refl": refl_source, "rf_dmg": dmg_source}


def assemble(name, mutate=None):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_64
    code = bytes(Ks(KS_ARCH_X86, KS_MODE_64).asm(SOURCES[name](mutate), 0x1000)[0])
    if code.count(struct.pack("<Q", BUF)) != 1:
        raise SystemExit(f"{name}: the buffer placeholder must appear exactly once")
    return code


# --- emulator ---------------------------------------------------------------
CODE, B, STACK, OBJ = 0x100000, 0x200000, 0x2000000, 0x3000000
RET, SPEED = 0x14325BF4B, 9.25


def _machine(code):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
    mu = Uc(UC_ARCH_X86, UC_MODE_64)
    mu.mem_map(CODE, 0x10000)
    mu.mem_map(B, ((BYTES + 0xFFFF) // 0x10000) * 0x10000)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(OBJ, 0x100000)
    mu.mem_write(CODE, code.replace(struct.pack("<Q", BUF), struct.pack("<Q", B)))
    return mu


def _entities(mu, tick=4321):
    """six synthetic entities sharing one battle; each its own synthetic unit."""
    e = [OBJ + 0x10000 * (i + 1) for i in range(6)]
    battle, ticks = OBJ + 0x90000, OBJ + 0x98000
    for x in e:
        mu.mem_write(x + BATTLE, struct.pack("<Q", battle))
        mu.mem_write(x + UNIT, struct.pack("<Q", 0xAA0000 + x))
    mu.mem_write(battle + TICKS, struct.pack("<Q", ticks))
    mu.mem_write(ticks + TICK, struct.pack("<I", tick))
    return e


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


def check(mutate=None, which=None):
    """[failure] of the caves (``which`` one built from the ``mutate`` (old, new) edit) on synthetic calls."""
    fails = []
    if which in (None, "rf_refl"):
        code = assemble("rf_refl", mutate if which == "rf_refl" else None)
        for name, mode, kind, want in (("ground charger", 1, "ground", 0), ("flying charger", 1, "flyer", 1),
                                       ("rider of a flyer", 1, "rider", 1), ("off", 0, "ground", None),
                                       ("null reflector", 1, "null8", 0), ("null charger", 1, "null9", 0)):
            for flags in (0x202, 0x8D7):
                mu = _machine(code)
                e = _entities(mu)
                r8, r9 = e[0], e[1]
                mu.mem_write(r8 + BRACE_MULT, struct.pack("<f", 5.5))
                mu.mem_write(r8 + IMMOVABLE, struct.pack("<I", 0x10))
                if kind == "flyer":
                    mu.mem_write(r9 + FC, struct.pack("<Q", 0x77))
                elif kind == "rider":
                    mu.mem_write(r9 + PARENT, struct.pack("<Q", e[2]))
                    mu.mem_write(e[2] + FC, struct.pack("<Q", 0x77))
                if kind == "null8":
                    r8 = 0
                if kind == "null9":
                    r9 = 0
                mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
                mu.mem_write(B + REFL_COUNT_AT, struct.pack("<I", REFL_SLOTS + 7))
                rsp = STACK + 0x4000
                mu.mem_write(rsp, struct.pack("<Q", RET) + bytes(0x20) + struct.pack("<f", SPEED) + bytes(12))
                changed = _run(mu, code, {"rcx": 0x9999, "rdx": 0x8888, "r8": r8, "r9": r9, "rsp": rsp}, flags)
                if changed:
                    fails.append(f"rf_refl {name}/{flags:#x}: registers changed {changed}")
                cnt = _u32(mu, B + REFL_COUNT_AT) - (REFL_SLOTS + 7)
                ent = bytes(mu.mem_read(B + REFL_RING_AT + 7 * ENTRY, ENTRY))
                if want is None:
                    if cnt or any(ent):
                        fails.append(f"rf_refl {name}: logged in mode 0")
                    continue
                got = struct.unpack_from("<QQQfIQQIfII", ent, 0)
                exp = (r8, r9, RET, SPEED, 4321 if (r8 or r9) else 0,
                       (0xAA0000 + r8) if r8 else 0, (0xAA0000 + r9) if r9 else 0, want,
                       5.5 if r8 else 0.0, 0x10 if r8 else 0, REFL_SLOTS + 8)
                if (cnt, got) != (1, exp):
                    fails.append(f"rf_refl {name}: count {cnt} entry {got} want {exp}")
    if which in (None, "rf_dmg"):
        code = assemble("rf_dmg", mutate if which == "rf_dmg" else None)
        for name, mode, kind, want_flyer in (("ground victim", 1, "ground", 0), ("flying victim", 1, "flyer", 1),
                                             ("rider of a flyer", 1, "rider", 1), ("null victim", 1, "null", 0),
                                             ("off", 0, "ground", None),
                                             ("rider without unit: the mount's unit", 1, "rider_nounit", 1)):
            for flags in (0x202, 0x8D7):
                mu = _machine(code)
                e = _entities(mu, tick=777)
                victim, flyer, unit = e[0], 0, 0xAA0000 + e[0]
                if kind == "flyer":
                    mu.mem_write(victim + FC, struct.pack("<Q", 0x77))
                    flyer = victim
                elif kind in ("rider", "rider_nounit"):
                    mu.mem_write(victim + PARENT, struct.pack("<Q", e[2]))
                    mu.mem_write(e[2] + FC, struct.pack("<Q", 0x77))
                    flyer = e[2]
                    if kind == "rider_nounit":
                        mu.mem_write(victim + UNIT, struct.pack("<Q", 0))
                        unit = 0xAA0000 + e[2]
                elif kind == "null":
                    victim, unit = 0, 0
                mu.mem_write(B + MODE_AT, struct.pack("<I", mode))
                mu.mem_write(B + DMG_COUNT_AT, struct.pack("<I", DMG_SLOTS + 3))
                frame = STACK + 0x6000                   # rbp = entry rsp - 0x3f
                mu.mem_write(frame + 0x3F, struct.pack("<Q", REFLECT_DAMAGE_RETURN))
                mu.mem_write(frame + 0x6F, struct.pack("<I", 5))
                rsp = STACK + 0x4000
                # the ring slot holds junk: a reused slot must not keep stale fields
                mu.mem_write(B + DMG_RING_AT + 3 * ENTRY, b"\xEE" * ENTRY)
                changed = _run(mu, code, {"rdx": victim, "rax": 0xFFFFFFFF00000033, "rbp": frame,
                                          "rsp": rsp}, flags)
                if changed:
                    fails.append(f"rf_dmg {name}/{flags:#x}: registers changed {changed}")
                cnt = _u32(mu, B + DMG_COUNT_AT) - (DMG_SLOTS + 3)
                ent = bytes(mu.mem_read(B + DMG_RING_AT + 3 * ENTRY, ENTRY))
                if want_flyer is None:
                    if cnt or ent != b"\xEE" * ENTRY:
                        fails.append(f"rf_dmg {name}: logged in mode 0")
                    continue
                got = struct.unpack_from("<QQQiIIIQ", ent, 0) + struct.unpack_from("<I", ent, 60)
                exp = (REFLECT_DAMAGE_RETURN, victim, unit, 0x33, 5, 777 if victim else 0, want_flyer,
                       flyer, DMG_SLOTS + 4)
                if (cnt, got) != (1, exp):
                    fails.append(f"rf_dmg {name}: count {cnt} entry {got} want {exp}")
    return fails


MUTANTS = (
    ("rf_refl", "mov qword ptr [r11 + 8], r9", "mov qword ptr [r11 + 8], r8"),
    ("rf_refl", f"[rsp + {8 * (REFL_PUSHES + 1) + 0x28}]", f"[rsp + {8 * (REFL_PUSHES + 1) + 0x20}]"),
    ("rf_refl", f"mov rax, qword ptr [rsp + {8 * (REFL_PUSHES + 1)}]",
     f"mov rax, qword ptr [rsp + {8 * REFL_PUSHES}]"),
    ("rf_refl", "    mov ecx, 1\nno_r9:", "    nop\nno_r9:"),
    ("rf_refl", "    pop rdx\n    mov dword ptr [r11 + 60], edx", "    pop rdx\n    mov dword ptr [r11 + 60], 0"),
    ("rf_dmg", "mov rcx, qword ptr [rbp + 0x3f]", "mov rcx, qword ptr [rbp + 0x37]"),
    ("rf_dmg", "mov ecx, dword ptr [rbp + 0x6f]", "mov ecx, dword ptr [rbp + 0x67]"),
    ("rf_dmg", "mov ecx, dword ptr [rsp + 32]", "mov ecx, dword ptr [rsp + 24]"),
    ("rf_dmg", "    mov dword ptr [r11 + 36], 0\n", "    nop\n"),
    ("rf_dmg", "    pop r9\n", "    pop rax\n"),
)


def negative_controls():
    """[mutant] whose broken cave passed every case (must be empty)."""
    return [m for m in MUTANTS if not check(m[1:], which=m[0])]


def _regex(pattern):
    return re.compile(b"".join(b"." if t == "??" else re.escape(bytes([int(t, 16)]))
                               for t in pattern.split()), re.S)


SITES = {"rf_refl": (REFL_PATTERN, 0, REFL_STOLEN), "rf_dmg": (DMG_PATTERN, DMG_AT, DMG_STOLEN)}


def check_exe(exe_path):
    """{cave: virtual address}: each pattern exactly once in the exe's code with the stolen bytes
    at the site, and at the address of the static read (EXE_SITES); refuses otherwise."""
    import pefile
    pe = pefile.PE(str(exe_path), fast_load=True)
    code = [(pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress, s.get_data())
            for s in pe.sections if s.Characteristics & 0x20000000]
    found = {}
    for name, (pattern, at, stolen) in SITES.items():
        want = bytes.fromhex(stolen.replace(" ", ""))
        hits = [va + m.start() + at for va, data in code for m in _regex(pattern).finditer(data)
                if data[m.start() + at:m.start() + at + len(want)] == want]
        if hits != [EXE_SITES[name]]:
            raise SystemExit(f"[reflect_probe] REFUSING: {name} found at {[hex(h) for h in hits]}, "
                             f"want {EXE_SITES[name]:#x} (another build?)")
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
    lines = ["-- TEST-ONLY, generated by tools/pipelines/reflect_probe_asm.py; never in a player's pack",
             "return {", f"    owner = '{OWNER}', feature = '{FEATURE}',", "    entries = {"]
    for n in SOURCES:
        pattern, at, stolen = SITES[n]
        lines += [f"        {{ name = '{n}', feature = '{FEATURE}', kind = 'cave',",
                  f"          pattern = '{pattern}', at = {at}, expect = '{stolen}',",
                  f"          bytes = '{_template(codes[n])}' }},"]
    lines += ["    },", "    caves = { 'rf_refl', 'rf_dmg' },",
              f"    layout = {{ bytes = {BYTES}, mode_at = {MODE_AT}, magic_at = {MAGIC_AT}, "
              f"magic = '{MAGIC.decode()}',",
              f"        refl_count_at = {REFL_COUNT_AT}, refl_ring_at = {REFL_RING_AT}, "
              f"refl_slots = {REFL_SLOTS},",
              f"        dmg_count_at = {DMG_COUNT_AT}, dmg_ring_at = {DMG_RING_AT}, dmg_slots = {DMG_SLOTS},",
              f"        entry = {ENTRY} }},", "}"]
    return "\n".join(lines) + "\n"


def build_site():
    """(site Lua text, report): assemble, emulator check, negative controls; refuses on any failure."""
    codes = {n: assemble(n) for n in SOURCES}
    fails = check()
    survivors = [] if fails else negative_controls()
    if fails or survivors:
        raise SystemExit("[reflect_probe] REFUSING: "
                         + "; ".join(fails + [f"mutant not caught: {m}" for m in survivors]))
    return site_lua(codes), (f"caves {', '.join(f'{n} {len(c)} B' for n, c in codes.items())}; "
                             f"emulator PASS; {len(MUTANTS)} mutants, each caught")


def main(argv):
    exe = Path(r"D:/SteamLibrary/steamapps/common/Total War WARHAMMER III/Warhammer3.exe")
    found = check_exe(exe)
    text, report = build_site()
    print(report + "; exe sites " + ", ".join(f"{k} {v:#x}" for k, v in found.items()))
    if "--write-site" in argv:
        out = Path(argv[argv.index("--write-site") + 1])
        out.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
