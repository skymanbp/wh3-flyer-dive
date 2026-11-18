"""Lane edit: dive_cave_asm.py module docstring bullets for dv_contact and the landed state 0."""
from pathlib import Path

p = Path(r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools/pipelines/dive_cave_asm.py")
s = p.read_bytes().decode("utf-8")
CRLF = chr(13) + chr(10) in s
s = s.replace(chr(13) + chr(10), chr(10))
old = "All eight only act on entities with a flight controller,"
assert s.count(old) == 1 and "``dv_contact`` (contact-engage" not in s
new = """* [AIR-DIVE-BRACE-W1 2026-11-14] ``dv_contact`` (contact-engage 0x14305dcac
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
  Counted on the engage counter (+32).
* [AIR-DIVE-BRACE-W1] a moving state is 30, 33, or 0 on the ground (+0x104
  0): the storm dragon passes through state 0 on its touchdown tick.

All nine only act on entities with a flight controller,"""
s = s.replace(old, new)
p.write_bytes((s.replace(chr(10), chr(13) + chr(10)) if CRLF else s).encode("utf-8"))
print("patched")
