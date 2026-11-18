"""Lane edit (AIR-DIVE-BRACE-W1, batch C evidence): dv_contact moves to the melee-engage function
itself, 0x143075dd8 (rcx = the engaging entity, rdx = the engage parameters).

Measured (batch C, CONTENT_LEDGER §C11 AIR-DIVE-BRACE-W1): with the cave at 0x143123338 the melee
order was still installed on landed, fast flyers in flight movement (27 of 36 logged orders in the
early stops; dive counter 'engage re-paths held off' 1 for a whole run). Every logged stack goes
0x143075ebd (inside 0x143075dd8) straight to 0x14305ddde, the return of `call [rax+0x4b0]` in the
contact-engage 0x14305dcac -- no 0x14312337d (the return into 0x143123338). The exe holds
0x143075dd8 as a qword 33 times (the default vtable slot +0x4b0) and 0x143123338 once (one
class's override, which calls 0x143075dd8 at 0x143123378). So 0x143075dd8 is the sink of every
contact path and every entity class."""
from pathlib import Path

p = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools/pipelines/dive_cave_asm.py")
s = p.read_bytes().decode("utf-8")
CRLF = chr(13) + chr(10) in s
s = s.replace(chr(13) + chr(10), chr(10))

old = '''    # [AIR-DIVE-BRACE-W1] 0x143123338 entry: the entity's melee-engage vfunc +0x4b0 (rcx = the
    # entity that engages); both contact paths call it -- the pairwise collision's contact-engage
    # 0x14305dcac (via 0x14305ddd8) and the per-model update's own copy 0x143090e3c (0x1430912de)
    "dv_contact": ("48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 48 8B F9 4C 8B D2 48 8B 89 E8 02 00 00",
                   0, "48 89 5C 24 08 48 89 74 24 10", None),'''
new = '''    # [AIR-DIVE-BRACE-W1] 0x143075dd8 entry: melee-engage (rcx = the entity that engages, rdx = the
    # parameters), the default vtable slot +0x4b0 (33 vtables; one class overrides it with
    # 0x143123338, which calls this). Both contact paths reach it: the pairwise collision's
    # contact-engage 0x14305dcac (call at 0x14305ddd8) and the per-model update's copy 0x143090e3c
    # (0x1430912de)
    "dv_contact": ("48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 8B 81 24 03 00 00 48 8B F2 48 8B D9 85 C0 74 2F",
                   0, "48 89 5C 24 08 48 89 74 24 10", None),'''
assert old in s
s = s.replace(old, new)

old = '''* [AIR-DIVE-BRACE-W1 2026-11-14] ``dv_contact`` (the entity's melee-engage
  vfunc +0x4b0, 0x143123338 entry). A landed flyer that touched upright'''
new = '''* [AIR-DIVE-BRACE-W1 2026-11-14] ``dv_contact`` (melee-engage 0x143075dd8
  entry, the default vtable slot +0x4b0 -- 33 vtables; batch C showed the
  one override 0x143123338 is not the flyers'). A landed flyer that touched upright'''
assert old in s
s = s.replace(old, new)
p.write_bytes((s.replace(chr(10), chr(13) + chr(10)) if CRLF else s).encode("utf-8"))
print("patched")
