"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 4): test pack + the bob probe -> out pack. usage: mkbob.py base out"""
import sys
sys.path.insert(0, r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools")
import rolepath  # noqa: F401 -- because it puts the role dirs on sys.path
from packfile import PACK_TYPE_MOD, PackFile, write_pack_file
from pathlib import Path
H = Path(__file__).resolve().parent
base, out = sys.argv[1:3]
extra = [("script/battle/mod/ld_bob_probe.lua", (H / "bob_probe.lua").read_bytes().replace(b"\r\n", b"\n"))]
with PackFile.open(base) as p:
    ents = [(e.path, p.read_file(e)) for e in p.entries]
assert not any(path.endswith("ld_bob_probe.lua") for path, _ in ents)
assert Path(out).name.lower() not in ("ld_mod.pack", "ld_air_dive.pack")
print(write_pack_file(out, ents + extra, PACK_TYPE_MOD), len(ents) + 1)
