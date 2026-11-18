"""TEST-ONLY patch script (AIR-DIVE-BRACE-W1 round 2): add the call-site cave dv_settle and give
dv_contact / dv_settle their own counters (+40 / +44). Edits dive_cave_asm.py (CRLF kept), the two
shipped Lua readers and the test docstring. Every replacement must apply exactly once."""
from pathlib import Path

LANE = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1")


def edit(rel, reps):
    p = LANE / rel
    raw = p.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    for a, b in reps:
        n = t.count(a)
        assert n == 1, f"{rel}: {n} x {a[:70]!r}"
        t = t.replace(a, b)
    p.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
    print("edited", rel, "crlf" if crlf else "lf")


ASM = "mod/tools/pipelines/dive_cave_asm.py"
edit(ASM, [
    ("ENGAGED_AT, REORDERED_AT = 32, 36            # [AIR-DIVE-RELEASE-W1] re-paths held off\n",
     "ENGAGED_AT, REORDERED_AT = 32, 36            # [AIR-DIVE-RELEASE-W1] re-paths held off\n"
     "CONTACT_AT, SETTLED_AT = 40, 44              # [AIR-DIVE-BRACE-W1] melee engages / blocked stops held off\n"),
    ("""    "dv_contact": ("48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 8B 81 24 03 00 00 48 8B F2 48 8B D9 85 C0 74 2F",
                   0, "48 89 5C 24 08 48 89 74 24 10", None),
}""", """    "dv_contact": ("48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 8B 81 24 03 00 00 48 8B F2 48 8B D9 85 C0 74 2F",
                   0, "48 89 5C 24 08 48 89 74 24 10", None),
    # [AIR-DIVE-BRACE-W1 round 2] 0x143098cc8: mov rdx,rax / xor r8d,r8d / mov rcx,rdi /
    # call 0x1431341b0 (then jmp 0x143098cdb, left in place) -- in the entity vfunc +0x490
    # 0x143098b04, the +0xb28 == 2 branch: stop at the current position (goal +0x1e0 = the snapped
    # +0x88 position, speed cap +0x180 = 0, +0x17c = 1)
    "dv_settle": ("48 8B D0 45 33 C0 48 8B CF E8 ?? ?? ?? ?? EB 03 45 8A FD 48 8B CF",
                  0, "48 8B D0 45 33 C0 48 8B CF E8", 14),
}"""),
    ("""    "dv_tick_move": {"call_at": 6, "callee": 0x14307B5B8, "entity": "qword ptr [rbx + 8]",
                     "counter": REORDERED_AT, "pre": "    movss dword ptr [rsp + 0x74], xmm3\\n"},
}""", """    "dv_tick_move": {"call_at": 6, "callee": 0x14307B5B8, "entity": "qword ptr [rbx + 8]",
                     "counter": REORDERED_AT, "pre": "    movss dword ptr [rsp + 0x74], xmm3\\n"},
    "dv_settle": {"call_at": 9, "callee": 0x1431341B0, "entity": "rdi", "counter": SETTLED_AT,
                  "pre": "    mov rdx, rax\\n    xor r8d, r8d\\n    mov rcx, rdi\\n"},
}"""),
    ("""{_fast_test("r11")}
    lock inc dword ptr [r10 + {ENGAGED_AT}]
    pop r11
    pop r10
    pop rax
    popfq
    ret""", """{_fast_test("r11")}
    lock inc dword ptr [r10 + {CONTACT_AT}]
    pop r11
    pop r10
    pop rax
    popfq
    ret"""),
    ("""    counter = {"dv_skip": SKIPPED_AT, "dv_contact": ENGAGED_AT}.get(name, KEPT_AT)""",
     """    counter = {"dv_skip": SKIPPED_AT, "dv_contact": CONTACT_AT}.get(name, KEPT_AT)"""),
    ("""            vals = {X.UC_X86_REG_RCX: ent if c["entity"] == "rcx" else order, X.UC_X86_REG_RSP: rsp,
                    X.UC_X86_REG_RDI: order,""",
     """            vals = {X.UC_X86_REG_RCX: ent if c["entity"] == "rcx" else order, X.UC_X86_REG_RSP: rsp,
                    X.UC_X86_REG_RDI: ent if c["entity"] == "rdi" else order, X.UC_X86_REG_R8: 0x8E8E,"""),
    ("""                calls.append((uc.reg_read(X.UC_X86_REG_RCX), uc.reg_read(X.UC_X86_REG_RDX),
                              uc.reg_read(X.UC_X86_REG_R9), uc.reg_read(X.UC_X86_REG_XMM2),
                              uc.reg_read(X.UC_X86_REG_RSP)))""",
     """                calls.append((uc.reg_read(X.UC_X86_REG_RCX), uc.reg_read(X.UC_X86_REG_RDX),
                              uc.reg_read(X.UC_X86_REG_R9), uc.reg_read(X.UC_X86_REG_XMM2),
                              uc.reg_read(X.UC_X86_REG_RSP), uc.reg_read(X.UC_X86_REG_R8)))"""),
    ("""                         "dv_tick_move": (order, 0xD5, 0x99, 0x1234)}[name]""",
     """                         "dv_tick_move": (order, 0xD5, 0x99, 0x1234),
                         "dv_settle": (ent, 0xFEED, 0x99, 0x1234)}[name]"""),
    ("""            if name == "dv_tick_move" and struct.unpack("<f", bytes(mu.mem_read(rsp + 0x74, 4)))[0] != 10.0:
                ok = False""",
     """            if name == "dv_tick_move" and struct.unpack("<f", bytes(mu.mem_read(rsp + 0x74, 4)))[0] != 10.0:
                ok = False
            if name == "dv_settle" and calls and calls[0][5] != 0:      # the redone xor r8d, r8d
                ok = False"""),
    ("""          "dv_contact": check_contact}""",
     """          "dv_contact": check_contact,
          "dv_settle": lambda code: check_call_skip("dv_settle", code)}"""),
    ("""    ("tick move on the order, not its entity", "dv_tick_move", "    mov r11, qword ptr [rbx + 8]\\n",
     "    mov r11, rbx\\n"),
)""", """    ("tick move on the order, not its entity", "dv_tick_move", "    mov r11, qword ptr [rbx + 8]\\n",
     "    mov r11, rbx\\n"),
    ("settle forgets the zero r8", "dv_settle", "    xor r8d, r8d\\n", ""),
    ("settle forgets the callee's entity", "dv_settle", "    mov rcx, rdi\\n", ""),
    ("settle forgets the goal", "dv_settle", "    mov rdx, rax\\n", ""),
    ("settle holds every body", "dv_settle", "    jbe pass\\n", "    nop\\n"),
    ("settle in the air too", "dv_settle", "    cmp dword ptr [r11 + 0x104], 0\\n    jne pass\\n", ""),
    ("settle for ground movers too", "dv_settle", "    cmp dword ptr [r11 + 0x710], 0\\n    je pass\\n", ""),
    ("settle misses a ridden flyer", "dv_settle", "    cmovne r11, rax\\n", ""),
    ("settle on the old counter", "dv_settle", "    lock inc dword ptr [r10 + 44]\\n", "    lock inc dword ptr [r10 + 36]\\n"),
    ("contact on the shared counter", "dv_contact", "    lock inc dword ptr [r10 + 40]\\n",
     "    lock inc dword ptr [r10 + 32]\\n"),
)"""),
    ("""            "throughs_at": THROUGHS_AT, "kept_at": KEPT_AT, "engaged_at": ENGAGED_AT,
            "reordered_at": REORDERED_AT}""",
     """            "throughs_at": THROUGHS_AT, "kept_at": KEPT_AT, "engaged_at": ENGAGED_AT,
            "reordered_at": REORDERED_AT, "contact_at": CONTACT_AT, "settled_at": SETTLED_AT}"""),
    ("""  hit have slowed the flyer below SKIP_SPEED it engages as vanilla. Counted
  on the engage counter (+32).""",
     """  hit have slowed the flyer below SKIP_SPEED it engages as vanilla. Counted
  on its own counter (+40; +32 before round 2).
* [AIR-DIVE-BRACE-W1 round 2] ``dv_settle`` (call site 0x143098cd1 in the
  entity vfunc +0x490 0x143098b04, its +0xb28 == 2 branch). With the melee
  order held, a second stop showed up on its own (batch E: wyverns x3, a
  terrorgheist): the movement goal +0x1e0 jumped to the flyer's own position
  with the charge order unchanged, then the 3.0 m/s-per-tick brake. Probe
  batch F logged the writer: stop-at-point 0x1431341b0 (+0x17c = 1, goal =
  the snapped +0x88 position, speed cap +0x180 = 0, +0x188 = 0), called from
  0x143098cd1, the vfunc being called by the entity update at 0x14308e934
  once +0xb20 is set (+0xb28 = 2; after a random delay since +0xb44 it
  settles the entity where it is). Under the ``dv_engage`` test the call is
  not made; the vfunc goes on as when its own timer has not run out, and once
  the flyer is below SKIP_SPEED the stop is vanilla again. Counted (+44)."""),
    ("""All nine only act on entities with a flight controller""", """All ten only act on entities with a flight controller"""),
    ("""+20 u32 skipped, +24 u32 throughs, +28 u32 kept, +32 u32 engage re-paths held
off, +36 u32 charge-order re-paths held off (counters for the battle log), 64
bytes.""", """+20 u32 skipped, +24 u32 throughs, +28 u32 kept, +32 u32 engage re-paths held
off, +36 u32 charge-order re-paths held off, +40 u32 melee engages held off,
+44 u32 blocked stops held off (counters for the battle log), 64 bytes."""),
])

edit("mod/script/campaign/lore_disasters/lib/ld_flyer_dive.lua", [
    ("    for _, at in ipairs({ l.skipped_at, l.throughs_at, l.kept_at, l.engaged_at, l.reordered_at }) do",
     "    for _, at in ipairs({ l.skipped_at, l.throughs_at, l.kept_at, l.engaged_at, l.reordered_at,\n"
     "            l.contact_at, l.settled_at }) do"),
    ("""-- {mode, skipped, throughs, kept, engaged, reordered}: contact attacks not
-- started for a fast landed flyer, flyer charges aimed through, flight stops
-- held off, engage-approach and charge-order re-paths held off.""",
     """-- {mode, skipped, throughs, kept, engaged, reordered, contact, settled}: contact
-- attacks not started for a fast landed flyer, flyer charges aimed through,
-- flight stops held off, engage-approach and charge-order re-paths held off,
-- melee engages held off, blocked stops held off (AIR-DIVE-BRACE-W1)."""),
    ("""        engaged = u32(buf, l.engaged_at), reordered = u32(buf, l.reordered_at) }""",
     """        engaged = u32(buf, l.engaged_at), reordered = u32(buf, l.reordered_at),
        contact = u32(buf, l.contact_at), settled = u32(buf, l.settled_at) }"""),
])

edit("mod/script/battle/mod/ld_flyer_dive.lua", [
    ("""    .. "engage re-paths held off %d, charge-order re-paths held off %d\"""",
     """    .. "engage re-paths held off %d, charge-order re-paths held off %d, melee engages held off %d, "
    .. "blocked stops held off %d\""""),
    ("""            local line = COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered)""",
     """            local line = COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered, c.contact, c.settled)"""),
    ("""        record("END " .. COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered))""",
     """        record("END " .. COUNTS:format(c.throughs, c.skipped, c.kept, c.engaged, c.reordered, c.contact, c.settled))"""),
])
