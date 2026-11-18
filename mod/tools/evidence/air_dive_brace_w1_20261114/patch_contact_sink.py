"""Lane edit (AIR-DIVE-BRACE-W1, batch B evidence): move dv_contact from the contact-engage function
0x14305dcac (rdx = engaging body) to the sink both contact paths call, the entity's melee-engage
vfunc +0x4b0 = 0x143123338 (rcx = the engaging entity), which installs the melee order through
0x143075dd8 (its only caller) and then repeats for the entity's sub-entities (+0xb64).

Measured (batch B, runs B*_*, CONTENT_LEDGER §C11 AIR-DIVE-BRACE-W1): with the cave at 0x14305dcac
the contact path disappeared from the logged stacks and the melee order came instead from the
per-model update's own copy of the same test (0x143090e3c: enemy within the summed radii,
0x1430985e4 / vfunc +0x618 / 0x14306287c / 0x143098648, then vfunc +0x4b0 at 0x1430912de, stack
0x1430912e4 <- 0x14308ea3f in the model update 0x14308e448). Single-model early stops by
contact-engage were 13 in batch A and 28 in batch B. Both paths end in vfunc +0x4b0."""
from pathlib import Path

p = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools/pipelines/dive_cave_asm.py")
s = p.read_bytes().decode("utf-8")
CRLF = chr(13) + chr(10) in s
s = s.replace(chr(13) + chr(10), chr(10))
assert "0x143123338" not in s.split('"dv_contact": (')[1][:400]

old = '''    # [AIR-DIVE-BRACE-W1] 0x14305dcac entry: contact-engage (rdx = the body that engages, r8 = the
    # enemy it touched), called twice per enemy pair by the pairwise collision 0x1430731c8
    "dv_contact": ("48 89 5C 24 08 48 89 74 24 10 57 48 81 EC 80 00 00 00 48 8B 8A E8 02 00 00 49 8B F8 48 8B DA",
                   0, "48 89 5C 24 08 48 89 74 24 10", None),'''
new = '''    # [AIR-DIVE-BRACE-W1] 0x143123338 entry: the entity's melee-engage vfunc +0x4b0 (rcx = the
    # entity that engages); both contact paths call it -- the pairwise collision's contact-engage
    # 0x14305dcac (via 0x14305ddd8) and the per-model update's own copy 0x143090e3c (0x1430912de)
    "dv_contact": ("48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 48 8B F9 4C 8B D2 48 8B 89 E8 02 00 00",
                   0, "48 89 5C 24 08 48 89 74 24 10", None),'''
assert old in s
s = s.replace(old, new)

old = '''    jne pass
    mov r11, rdx
    test r11, r11
    je pass'''
new = '''    jne pass
    mov r11, rcx
    test r11, r11
    je pass'''
assert s.count(old) == 1
s = s.replace(old, new)

old = '''            X.UC_X86_REG_R15: 0xC4, X.UC_X86_REG_R8: 0x8E8E, X.UC_X86_REG_RDX: rcx if contact else 0xD5,'''
new = '''            X.UC_X86_REG_R15: 0xC4, X.UC_X86_REG_R8: 0x8E8E, X.UC_X86_REG_RDX: 0xD5D5 if contact else 0xD5,'''
assert old in s
s = s.replace(old, new)
old = '''    vals = {X.UC_X86_REG_RCX: 0xC0C0 if contact else rcx, X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_RBX: 0xB1,'''
new = '''    vals = {X.UC_X86_REG_RCX: rcx, X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_RBX: 0xB1,'''
assert old in s
s = s.replace(old, new)

old = '''    ("contact on the touched enemy", "dv_contact", "    mov r11, rdx\\n", "    mov r11, r8\\n"),'''
new = '''    ("contact on the wrong register", "dv_contact", "    mov r11, rcx\\n", "    mov r11, rdx\\n"),'''
assert old in s
s = s.replace(old, new)

old = '''* [AIR-DIVE-BRACE-W1 2026-11-14] ``dv_contact`` (contact-engage 0x14305dcac
  entry). A landed flyer that touched upright enemies (braced infantry are
  not knocked over, so they stay valid) was given the melee order (vtable
  0x143ade470, +0x324 = 1) whose movement goal is its own position, and
  braked to a stop 5-14 m in (run A1_wyvern lane 1, CONTENT_LEDGER §C11
  AIR-DIVE-BRACE-W1: issuer stack pair solver 0x143176c6c -> pairwise
  collision 0x1430731c8 -> 0x14305dcac -> vfunc +0x4b0 -> 0x143075dd8). Under
  the ``dv_engage`` test (landed, still in flight movement, fast) the cave
  returns at once, as when one of the function's own checks fails; the
  collision itself (push, knock, collision attack) is untouched, and once
  the bodies hit have slowed the flyer the contact engages as vanilla.
  Counted on the engage counter (+32).'''
new = '''* [AIR-DIVE-BRACE-W1 2026-11-14] ``dv_contact`` (the entity's melee-engage
  vfunc +0x4b0, 0x143123338 entry). A landed flyer that touched upright
  enemies (braced infantry are not knocked over, so they stay valid) was
  given the melee order (vtable 0x143ade470, +0x324 = 1) and stopped 1-14 m
  in (batch A, CONTENT_LEDGER §C11 AIR-DIVE-BRACE-W1). Two contact paths
  issue it, both through this vfunc: the pairwise collision's contact-engage
  0x14305dcac (stack: pair solver 0x143176c6c -> 0x1430731c8 -> 0x14305dcac)
  and the per-model update's own copy of the same test 0x143090e3c (seen
  once the first was held, batch B). Under the ``dv_engage`` test (landed,
  still in flight movement, fast) the cave returns at once; the collision
  itself (push, knock, collision attack) is untouched, and once the bodies
  hit have slowed the flyer below SKIP_SPEED it engages as vanilla. Counted
  on the engage counter (+32).'''
assert old in s
s = s.replace(old, new)

p.write_bytes((s.replace(chr(10), chr(13) + chr(10)) if CRLF else s).encode("utf-8"))
print("patched")
