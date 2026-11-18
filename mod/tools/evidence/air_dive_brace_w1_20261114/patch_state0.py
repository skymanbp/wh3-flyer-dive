"""Lane edit (AIR-DIVE-BRACE-W1): dive caves treat a LANDED flyer in state 0 as moving.

Measured (runs A1_storm, CONTENT_LEDGER §C11 AIR-DIVE-BRACE-W1): the storm dragon (dr04,
cathay_dragon_entity) shows +0x26c == 0 on its touchdown tick on all three lanes, where every
other flyer shows 33; on lane 3 its flight movement (+0x710 4 -> 0) ended on that tick and it
braked from 12.5 m/s at 30 m/s2 to a stop 1.7 m on. The fast-mover test only knew 30 / 33."""
from pathlib import Path

p = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools/pipelines/dive_cave_asm.py")
s = p.read_bytes().decode("utf-8")
CRLF = chr(13) + chr(10) in s
s = s.replace(chr(13) + chr(10), chr(10))
assert "LANDED_IDLE_STATE" not in s

s = s.replace('''MOVING_STATES = (30, 33)
''', '''MOVING_STATES = (30, 33)
# [AIR-DIVE-BRACE-W1 2026-11-14] state 0 counts as moving only on the ground (+0x104 0): the storm
# dragon's touchdown tick (runs A1_storm, CONTENT_LEDGER §C11 AIR-DIVE-BRACE-W1)
LANDED_IDLE_STATE = 0
''')

old = '''def _fast_test(ent):
    """Flags after: 'jbe pass' skips unless ent is in a moving state and its
    planar velocity is above the skip speed (r10 = buffer; xmm0/1 saved)."""
    return f"""
    cmp dword ptr [{ent} + {STATE_OFF:#x}], {MOVING_STATES[0]}
    je moving
    cmp dword ptr [{ent} + {STATE_OFF:#x}], {MOVING_STATES[1]}
    jne pass
moving:'''
new = '''def _fast_test(ent):
    """Flags after: 'jbe pass' skips unless ent is in a moving state and its
    planar velocity is above the skip speed (r10 = buffer; xmm0/1 saved).
    [AIR-DIVE-BRACE-W1] A moving state is 30, 33, or LANDED_IDLE_STATE (0)
    on the ground (+0x104 0) -- the storm dragon's touchdown tick."""
    return f"""
    cmp dword ptr [{ent} + {STATE_OFF:#x}], {MOVING_STATES[0]}
    je moving
    cmp dword ptr [{ent} + {STATE_OFF:#x}], {MOVING_STATES[1]}
    je moving
    cmp dword ptr [{ent} + {STATE_OFF:#x}], {LANDED_IDLE_STATE}
    jne pass
    cmp dword ptr [{ent} + {LAYER_OFF:#x}], 0
    jne pass
moving:'''
assert old in s
s = s.replace(old, new)

old = '''def _mover(mu, ent, flyer, state, vel):
    mu.mem_write(ent + FC_OFF, struct.pack("<Q", 0x77 if flyer else 0))
    mu.mem_write(ent + STATE_OFF, struct.pack("<i", state))
    mu.mem_write(ent + VEL_OFF, struct.pack("<fff", vel[0], 0.0, vel[1]))'''
new = '''def _mover(mu, ent, flyer, state, vel, layer=0):
    mu.mem_write(ent + FC_OFF, struct.pack("<Q", 0x77 if flyer else 0))
    mu.mem_write(ent + STATE_OFF, struct.pack("<i", state))
    mu.mem_write(ent + VEL_OFF, struct.pack("<fff", vel[0], 0.0, vel[1]))
    mu.mem_write(ent + LAYER_OFF, struct.pack("<i", layer))'''
assert old in s
s = s.replace(old, new)

old = '''              (1, True, 30, (NAN, 3.0), False))
'''
new = '''              (1, True, 30, (NAN, 3.0), False),
              # [AIR-DIVE-BRACE-W1] the storm dragon's touchdown tick (state 0, 12.5 m/s, on the ground)
              (1, True, 0, (-0.38, -12.48), True), (1, True, 0, (0.0, 0.0), False))
# [AIR-DIVE-BRACE-W1] (case, layer): state 0 in the air is not the landing tick
KEEP_LAYER_CASES = (((1, True, 0, (-0.38, -12.48), False), 2), ((1, True, 0, (-0.38, -12.48), False), 1),
                    ((1, True, 30, FAST, True), 2), ((1, True, 0, (-0.38, -12.48), True), 0))
'''
assert old in s
s = s.replace(old, new)

old = '''def check_keep(code):
    fails, n = [], 0
    for mode, flyer, state, vel, want in FAST_CASES:
        n += 1

        def build(mu, obj, buf):
            ent = obj + 0x1000
            mu.mem_write(buf + MODE_AT, struct.pack("<I", mode))
            _mover(mu, ent, flyer, state, vel)
            return ent, mode'''
new = '''def check_keep(code):
    fails, n = [], 0
    for (mode, flyer, state, vel, want), layer in [(c, 0) for c in FAST_CASES] + list(KEEP_LAYER_CASES):
        n += 1

        def build(mu, obj, buf):
            ent = obj + 0x1000
            mu.mem_write(buf + MODE_AT, struct.pack("<I", mode))
            _mover(mu, ent, flyer, state, vel, layer)
            return ent, mode'''
assert old in s
s = s.replace(old, new)
s = s.replace('''            fails.append(f"keep mode {mode} flyer {flyer} state {state} vel {vel}: {why}")''',
              '''            fails.append(f"keep mode {mode} flyer {flyer} state {state} vel {vel} layer {layer}: {why}")''')

old = '''    ("keep forgets xmm0", "dv_keep", "    movdqu xmm0, xmmword ptr [rsp]\\n", ""),'''
new = '''    ("keep forgets xmm0", "dv_keep", "    movdqu xmm0, xmmword ptr [rsp]\\n", ""),
    ("keep forgets the landed state 0", "dv_keep", "    cmp dword ptr [rcx + 0x26c], 0\\n    jne pass\\n",
     "    jmp pass\\n"),
    ("keep holds state 0 in the air too", "dv_keep", "    cmp dword ptr [rcx + 0x104], 0\\n    jne pass\\nmoving:",
     "moving:"),
    ("engage forgets the landed state 0", "dv_engage", "    cmp dword ptr [r11 + 0x26c], 0\\n    jne pass\\n",
     "    jmp pass\\n"),'''
assert old in s, "mutant anchor"
s = s.replace(old, new)
p.write_bytes((s.replace(chr(10), chr(13) + chr(10)) if CRLF else s).encode("utf-8"))
print("patched")
