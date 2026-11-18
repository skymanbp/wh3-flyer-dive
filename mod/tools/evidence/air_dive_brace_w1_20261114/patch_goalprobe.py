"""TEST-ONLY (AIR-DIVE-BRACE-W1, round 2): add two flyer loggers to the brace probe.
  bp_gset  entry of 0x1431341b0  (stop-at-point: +0x17c=1, goal +0x1e0 = [rdx], cap +0x180 = 0, +0x188 = r8d)
  bp_stag  entry of 0x143098b04  (vfunc; first thing it does is clear +0x6c/+0x70 bit 0x20, then may call
                                  0x1431341b0 with goal = snapped +0x88 position at 0x143098cd1)
Same 512-byte entry shape as bp_log (entity, return, seq, +0x26c, vx, vz, +0x710, +0x104, two u32 extras,
u64 extra, slot, 48 stack qwords). The goal-collapse tick in batch E matched both functions' writes
(gdiff.py); the probe decides which caller path runs."""
from pathlib import Path

H = Path(__file__).resolve().parent
P = H / "brace_probe_asm.py"
s = P.read_text("utf-8")
assert "GSET_PATTERN" not in s

s = s.replace('BYTES = ORD_RING_AT + ORD_SLOTS * ORD_ENTRY\n', '''GSET_COUNT_AT, GSET_SLOTS, GSET_ENTRY = 32, 256, 512
GSET_RING_AT = ORD_RING_AT + ORD_SLOTS * ORD_ENTRY
STAG_COUNT_AT, STAG_SLOTS, STAG_ENTRY = 36, 256, 512
STAG_RING_AT = GSET_RING_AT + GSET_SLOTS * GSET_ENTRY
BYTES = STAG_RING_AT + STAG_SLOTS * STAG_ENTRY
# [round 2] stop-at-point 0x1431341b0 (3 callers: 0x14308d162, 0x143098cd1, 0x1430bb1bb) and the
# vfunc 0x143098b04 that holds the 0x143098cd1 call (37 vtable refs)
GSET_PATTERN = "48 89 5C 24 08 57 48 83 EC 20 80 B9 28 02 00 00 01 48 8B F9 74 7F 33 C0"
GSET_STOLEN = "48 89 5C 24 08 57 48 83 EC 20"
STAG_PATTERN = "48 8B C4 48 89 58 10 48 89 68 18 48 89 70 20 57 41 54 41 55 41 56 41 57 48 81 EC 80 00 00 00 83"
STAG_STOLEN = "48 8B C4 48 89 58 10 48 89 68 18"
''', 1)

s = s.replace('''def assemble(src=None):''', '''def ent_source(count_at, slots, ring_at, extras):
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
            want_extra = (161.0, -141.0, 0x1234) if kind == "gset" else \\
                (2, 0x0c, struct.unpack("<Q", struct.pack("<ff", 160.5, 2270.25))[0])
            if cnt != 1 or head != (ent, 0x143098CD6, slots + 2, 30, 2.0, -11.0, 4, 0) or extra != want_extra \\
                    or struct.unpack_from("<I", e, 56)[0] != 1 or e[64:72] != struct.pack("<Q", 0x143098CD6) \\
                    or e[72:80] != bytes(range(8, 16)):
                fails.append(f"{kind} {mode, flyer, mount}: entry {head} {extra} count {cnt}")
        elif cnt or any(e):
            fails.append(f"{kind} {mode, flyer, mount}: wrote")
    return fails


def assemble(src=None):''', 1)

s = s.replace('''    if fails:
        raise SystemExit("FAILED " + "; ".join(fails))
    names =''', '''    gsc = assemble(gset_source())
    fails += check_ent(gsc, GSET_COUNT_AT, GSET_SLOTS, GSET_RING_AT, "gset")
    stc = assemble(stag_source())
    fails += check_ent(stc, STAG_COUNT_AT, STAG_SLOTS, STAG_RING_AT, "stag")
    # broken variants the checks must catch: wrong ring, wrong extra, no flyer filter
    for kind, src, args in (("gset", gset_source().replace("mov eax, dword ptr [rdx + 8]", "mov eax, dword ptr [rdx + 4]"),
                             (GSET_COUNT_AT, GSET_SLOTS, GSET_RING_AT)),
                            ("stag", stag_source().replace("[rcx + 0xb28]", "[rcx + 0xb2c]"), (STAG_COUNT_AT, STAG_SLOTS, STAG_RING_AT)),
                            ("gset", gset_source().replace(f"[r10 + {GSET_COUNT_AT}]", f"[r10 + {STAG_COUNT_AT}]"),
                             (GSET_COUNT_AT, GSET_SLOTS, GSET_RING_AT)),
                            ("stag", stag_source().replace("    je done\\nlogit:", "    jmp logit\\nlogit:").replace(
                                "    test rax, rax\\n    je done\\n    mov rax, qword ptr [rax + 0x128]",
                                "    test rax, rax\\n    jmp logit\\n    mov rax, qword ptr [rax + 0x128]"),
                             (STAG_COUNT_AT, STAG_SLOTS, STAG_RING_AT))):
        try:
            bad = assemble(src)
        except AssertionError:
            continue
        if not check_ent(bad, *args, kind):
            fails.append(f"mutant of {kind} not caught")
    if fails:
        raise SystemExit("FAILED " + "; ".join(fails))
    names =''', 1)

s = s.replace("""            bytes = '{template(orc)}' }}, }},""", """            bytes = '{template(orc)}' }},
        {{ name = 'bp_gset', feature = 'brace_probe', kind = 'cave', pattern = '{GSET_PATTERN}', at = 0, expect = '{GSET_STOLEN}',
            bytes = '{template(gsc)}' }},
        {{ name = 'bp_stag', feature = 'brace_probe', kind = 'cave', pattern = '{STAG_PATTERN}', at = 0, expect = '{STAG_STOLEN}',
            bytes = '{template(stc)}' }}, }},""", 1)
s = s.replace("""        ord_count_at = {ORD_COUNT_AT}, ord_ring_at = {ORD_RING_AT}, ord_slots = {ORD_SLOTS}, ord_entry = {ORD_ENTRY} }},""",
              """        ord_count_at = {ORD_COUNT_AT}, ord_ring_at = {ORD_RING_AT}, ord_slots = {ORD_SLOTS}, ord_entry = {ORD_ENTRY},
        gset_count_at = {GSET_COUNT_AT}, gset_ring_at = {GSET_RING_AT}, gset_slots = {GSET_SLOTS}, gset_entry = {GSET_ENTRY},
        stag_count_at = {STAG_COUNT_AT}, stag_ring_at = {STAG_RING_AT}, stag_slots = {STAG_SLOTS}, stag_entry = {STAG_ENTRY} }},""", 1)
assert s.count("bp_gset") == 1 and s.count("gset_count_at = ") == 1
P.write_text(s, "utf-8", newline=chr(10))

L = H / "brace_probe.lua"
t = L.read_text("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
t = t.replace("\r\n", "\n")
rep = [
    ('for _, n in ipairs({ "bp_log", "bp_act1", "bp_act2", "bp_refl", "bp_mel", "bp_ord" }) do',
     'for _, n in ipairs({ "bp_log", "bp_act1", "bp_act2", "bp_refl", "bp_mel", "bp_ord", "bp_gset", "bp_stag" }) do'),
    ("bp_act2 = { buf = buf }, bp_refl = { buf = buf }, bp_mel = { buf = buf }, bp_ord = { buf = buf } })",
     "bp_act2 = { buf = buf }, bp_refl = { buf = buf }, bp_mel = { buf = buf }, bp_ord = { buf = buf },\n        bp_gset = { buf = buf }, bp_stag = { buf = buf } })"),
    ("mr.write(buf, l.ord_count_at, mr.uint32(0))\n",
     "mr.write(buf, l.ord_count_at, mr.uint32(0))\nmr.write(buf, l.gset_count_at, mr.uint32(0))\nmr.write(buf, l.stag_count_at, mr.uint32(0))\n"),
    ("local seen = 0\nlocal function tick()", '''-- [round 2] G = stop-at-point 0x1431341b0 (goal x z, r8), K = vfunc 0x143098b04 (+0xb28, +0xb11, +0x88 x z)
local function drain_ent(ms, tag, count_at, ring_at, slots, entry, seen_ref)
    local count = u32(mr.read(buf, count_at, 4), 0)
    if count - seen_ref[1] > slots then
        record(("LOST%s %d"):format(tag, count - seen_ref[1] - slots))
        seen_ref[1] = count - slots
    end
    while seen_ref[1] < count do
        local at = ring_at + (seen_ref[1] % slots) * entry
        local e = mr.read(buf, at, 64)
        local ent = sub(hex(sub(e, 1, 8)), -8)
        local x1, x2
        if tag == "G" then
            x1 = ("%.2f %.2f %d"):format(mr.read_float(buf, at + 40), mr.read_float(buf, at + 44), mr.read_int32(buf, at + 48))
        else
            x1 = ("%d %d %.2f %.2f"):format(mr.read_int32(buf, at + 40), mr.read_int32(buf, at + 44),
                mr.read_float(buf, at + 48), mr.read_float(buf, at + 52))
        end
        record(("%s %d %d %s %s %s %d %.2f %.2f %d %d %s %d %s"):format(tag, ms, u32(e, 16), tostring(owner_of[ent] or "?"),
            ent, hex(sub(e, 9, 16)), mr.read_int32(buf, at + 20), mr.read_float(buf, at + 24),
            mr.read_float(buf, at + 28), mr.read_int32(buf, at + 32), mr.read_int32(buf, at + 36), x1,
            e:byte(57) + e:byte(58) * 256, hexfwd(mr.read(buf, at + 64, 384))))
        seen_ref[1] = seen_ref[1] + 1
    end
end
local gset_seen, stag_seen = { 0 }, { 0 }

local seen = 0
local function tick()'''),
    ("    pcall(drain_ord, ms)\n",
     "    pcall(drain_ord, ms)\n    pcall(drain_ent, ms, \"G\", l.gset_count_at, l.gset_ring_at, l.gset_slots, l.gset_entry, gset_seen)\n"
     "    pcall(drain_ent, ms, \"K\", l.stag_count_at, l.stag_ring_at, l.stag_slots, l.stag_entry, stag_seen)\n"),
]
for a, b in rep:
    assert t.count(a) == 1, a
    t = t.replace(a, b)
L.write_text(t.replace("\n", nl), "utf-8", newline="")
print("patched")
