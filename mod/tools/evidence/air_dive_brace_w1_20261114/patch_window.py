"""TEST-ONLY patch script (AIR-DIVE-BRACE-W1 round 3, bounded slide): every hold cave keeps a landed flyer's
momentum only within SLIDE_RELEASE_M of the point where it was first held; past that the hold ends for good
(sticky until the flyer charges again in the air: dv_through clears it) and the engine's own engage / stop /
re-path take over. Edits dive_cave_asm.py (CRLF kept) and the two shipped Lua readers. Each replacement must
apply exactly once."""
from pathlib import Path

LANE = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1")


def edit(rel, reps):
    p = LANE / rel
    raw = p.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    for a, b in reps:
        n = t.count(a)
        assert n == 1, f"{rel}: {n} x {a[:80]!r}"
        t = t.replace(a, b)
    p.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
    print("edited", rel)


ASM = "mod/tools/pipelines/dive_cave_asm.py"
WINDOW_FN = '''

def _window_test(ent):
    """[AIR-DIVE-BRACE-W1 round 3] After a passed _fast_test: hold only within SLIDE_RELEASE_M of where this
    mover was first held since it last charged in the air. Table at SLIDE_AT, SLIDE_SLOTS x 16 bytes
    (qword key: 0 empty, 2 tombstone, the mover, the mover | 1 = released; dword x, dword z of the first
    hold), open addressing on key >> 4. First sight: claimed with one lock cmpxchg16b (key and point
    together, so no reader sees a key without its point), held. Past the radius: key | 1 (lock or), counted
    at RELEASED_AT, and 'jmp pass'. A released key, or a full table, passes at once. Falls through to the
    hold. Every register and xmm0 / xmm1 come back unchanged."""
    d2 = struct.unpack("<I", struct.pack("<f", SLIDE_RELEASE_M * SLIDE_RELEASE_M))[0]
    return f"""
    push rax
    push rbx
    push rcx
    push rdx
    push r8
    push r9
    mov r9, {ent}
    lea rsp, [rsp - 32]
    movdqu xmmword ptr [rsp], xmm0
    movdqu xmmword ptr [rsp + 16], xmm1
    mov rax, r9
    shr rax, 4
    and eax, {SLIDE_SLOTS - 1}
    mov r8d, {SLIDE_SLOTS}
    xor ecx, ecx
wprobe:
    mov rdx, rax
    shl rdx, 4
    lea rbx, [r10 + rdx + {SLIDE_AT}]
    mov rdx, qword ptr [rbx]
    cmp rdx, r9
    je wfound
    xor rdx, 1
    cmp rdx, r9
    je wpass_out
    xor rdx, 1
    cmp rdx, 2
    jne wnot_tomb
    test rcx, rcx
    jne wnext
    mov rcx, rbx
    jmp wnext
wnot_tomb:
    test rdx, rdx
    jne wnext
    test rcx, rcx
    jne winsert
    mov rcx, rbx
    jmp winsert
wnext:
    inc eax
    and eax, {SLIDE_SLOTS - 1}
    dec r8d
    jne wprobe
    test rcx, rcx
    je wpass_out
winsert:
    mov r8, rcx
    mov rax, qword ptr [r8]
    mov rdx, qword ptr [r8 + 8]
    mov ecx, dword ptr [r9 + {POS_OFF + 8:#x}]
    shl rcx, 32
    mov ebx, dword ptr [r9 + {POS_OFF:#x}]
    or rcx, rbx
    mov rbx, r9
    lock cmpxchg16b xmmword ptr [r8]
    jmp whold
wfound:
    movss xmm0, dword ptr [r9 + {POS_OFF:#x}]
    subss xmm0, dword ptr [rbx + 8]
    mulss xmm0, xmm0
    movss xmm1, dword ptr [r9 + {POS_OFF + 8:#x}]
    subss xmm1, dword ptr [rbx + 12]
    mulss xmm1, xmm1
    addss xmm0, xmm1
    mov eax, {d2:#x}
    movd xmm1, eax
    comiss xmm0, xmm1
    jb whold
    lock or qword ptr [rbx], 1
    lock inc dword ptr [r10 + {RELEASED_AT}]
wpass_out:
    movdqu xmm0, xmmword ptr [rsp]
    movdqu xmm1, xmmword ptr [rsp + 16]
    lea rsp, [rsp + 32]
    pop r9
    pop r8
    pop rdx
    pop rcx
    pop rbx
    pop rax
    jmp pass
whold:
    movdqu xmm0, xmmword ptr [rsp]
    movdqu xmm1, xmmword ptr [rsp + 16]
    lea rsp, [rsp + 32]
    pop r9
    pop r8
    pop rdx
    pop rcx
    pop rbx
    pop rax
"""


def _window_clear(ent):
    """[AIR-DIVE-BRACE-W1 round 3] dv_through, for a flyer charging IN THE AIR (+0x104 not 0): tombstone the
    mover's slide entry (the mover is its mount when it rides one), so its next landing gets a new window."""
    return f"""
    cmp dword ptr [{ent} + {LAYER_OFF:#x}], 0
    je wclr_done
    push rax
    push rcx
    push rdx
    push r8
    mov rcx, {ent}
    mov rax, qword ptr [rcx + {PARENT_OFF:#x}]
    test rax, rax
    cmovne rcx, rax
    mov rax, rcx
    shr rax, 4
    and eax, {SLIDE_SLOTS - 1}
    mov r8d, {SLIDE_SLOTS}
wclr_probe:
    mov rdx, rax
    shl rdx, 4
    mov rdx, qword ptr [r10 + rdx + {SLIDE_AT}]
    test rdx, rdx
    je wclr_out
    and rdx, -2
    cmp rdx, rcx
    jne wclr_next
    mov rdx, rax
    shl rdx, 4
    mov qword ptr [r10 + rdx + {SLIDE_AT}], 2
    jmp wclr_out
wclr_next:
    inc eax
    and eax, {SLIDE_SLOTS - 1}
    dec r8d
    jne wclr_probe
wclr_out:
    pop r8
    pop rdx
    pop rcx
    pop rax
wclr_done:
"""
'''

edit(ASM, [
    ("""CONTACT_AT, SETTLED_AT = 40, 44              # [AIR-DIVE-BRACE-W1] melee engages / blocked stops held off
""", """CONTACT_AT, SETTLED_AT = 40, 44              # [AIR-DIVE-BRACE-W1] melee engages / blocked stops held off
# [AIR-DIVE-BRACE-W1 round 3, bounded slide] the hold window (_window_test): slides ended at RELEASED_AT, the
# table at SLIDE_AT (16-byte aligned: lock cmpxchg16b), SLIDE_SLOTS entries of 16 bytes
RELEASED_AT, SLIDE_AT, SLIDE_SLOTS = 48, 64, 256
POS_OFF = 0x88                                 # entity position x (+0x88), z (+0x90)
# A landed flyer keeps its speed only within this distance of where it was first held: the target's depth
# (6.5-8.1 m) plus its touchdown distance from the target's centre (5.6-7.8 m) is about 10-12 m (packed
# A/B batch, mp_crossroads_flat, 2026-11-14), so 20 m carries every flyer through the line and a body length
# out the far side; past it the engine's engage / stop / re-path take over and its own deceleration brakes.
SLIDE_RELEASE_M = 20.0
"""),
    ("""BUFFER_BYTES = 64
""", """BUFFER_BYTES = 64 + 256 * 16                  # [AIR-DIVE-BRACE-W1 round 3] + the slide table
"""),
    ('''

def call_skip_source(name):''', WINDOW_FN + '''

def call_skip_source(name):'''),
])

# insert the window after every hold-side _fast_test, and the clear into dv_through
p = LANE / ASM
raw = p.read_bytes().decode("utf-8")
t = raw.replace("\r\n", "\n")
n_r11 = t.count('{_fast_test("r11")}\n')
n_rcx = t.count('{_fast_test("rcx")}\n')
assert (n_r11, n_rcx) == (3, 1), (n_r11, n_rcx)
t = t.replace('{_fast_test("r11")}\n', '{_fast_test("r11")}\n{_window_test("r11")}')
t = t.replace('{_fast_test("rcx")}\n', '{_fast_test("rcx")}\n{_window_test("rcx")}')
a = """flyer:
    lock inc dword ptr [r10 + {THROUGHS_AT}]"""
assert t.count(a) == 1
t = t.replace(a, """flyer:
{_window_clear("r9")}    lock inc dword ptr [r10 + {THROUGHS_AT}]""")
for old in ("(BUF, 0x1000)",):
    t = t.replace(old, "(BUF, 0x2000)")
a = """            "reordered_at": REORDERED_AT, "contact_at": CONTACT_AT, "settled_at": SETTLED_AT}"""
assert t.count(a) == 1
t = t.replace(a, """            "reordered_at": REORDERED_AT, "contact_at": CONTACT_AT, "settled_at": SETTLED_AT,
            "released_at": RELEASED_AT, "slide_at": SLIDE_AT, "slide_slots": SLIDE_SLOTS}""")
p.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
print("window inserted", n_r11 + n_rcx, "times; clear in dv_through")

edit("mod/script/campaign/lore_disasters/lib/ld_flyer_dive.lua", [
    ("""            if not have then return nil, "game_alloc failed" end
""", """            if not have then return nil, "game_alloc failed" end
            -- [AIR-DIVE-BRACE-W1 round 3] the slide table is claimed with lock cmpxchg16b: 16-byte aligned
            if sub(mr.tostring(have), -1) ~= "0" then return nil, "buffer not 16-byte aligned" end
"""),
    ("""    for _, at in ipairs({ l.skipped_at, l.throughs_at, l.kept_at, l.engaged_at, l.reordered_at,
            l.contact_at, l.settled_at }) do
        put_u32(buf, at, 0)
    end""", """    for _, at in ipairs({ l.skipped_at, l.throughs_at, l.kept_at, l.engaged_at, l.reordered_at,
            l.contact_at, l.settled_at, l.released_at }) do
        put_u32(buf, at, 0)
    end
    -- [AIR-DIVE-BRACE-W1 round 3] the slide table holds entity pointers of the last battle: cleared
    local zeros = string.rep("\\0", l.slide_slots * 16)
    mr_().write(buf, l.slide_at, zeros)"""),
    ("""        contact = u32(buf, l.contact_at), settled = u32(buf, l.settled_at) }""",
     """        contact = u32(buf, l.contact_at), settled = u32(buf, l.settled_at),
        released = u32(buf, l.released_at) }"""),
])
edit("mod/script/battle/mod/ld_flyer_dive.lua", [
    ("""    .. "blocked stops held off %d\"""", """    .. "blocked stops held off %d, slides ended %d\""""),
    ("""            local line = COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered, c.contact, c.settled)""",
     """            local line = COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered, c.contact, c.settled,
                c.released)"""),
    ("""        record("END " .. COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered, c.contact, c.settled))""",
     """        record("END " .. COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered, c.contact, c.settled,
            c.released))"""),
])
