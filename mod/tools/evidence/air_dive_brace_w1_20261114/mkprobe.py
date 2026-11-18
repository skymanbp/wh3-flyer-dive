"""TEST-ONLY (AIR-DIVE-BRACE-W1): base pack + brace probe -> out pack. usage: mkprobe.py base out"""
import sys
sys.path.insert(0, r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools")
import rolepath  # noqa
from packfile import PACK_TYPE_MOD, PackFile, write_pack_file
from pathlib import Path
H = Path(__file__).resolve().parent
base, out = sys.argv[1:3]
extra = [("script/battle/mod/ld_brace_probe.lua", (H / "brace_probe.lua").read_bytes().replace(b"\r\n", b"\n")),
         ("script/ld_brace_probe/brace_probe_site.lua", (H / "brace_probe_site.lua").read_bytes())]
with PackFile.open(base) as p:
    ents = [(e.path, p.read_file(e)) for e in p.entries]
assert not any(path.startswith("script/ld_brace_probe") or path.endswith("ld_brace_probe.lua") for path, _ in ents)
assert Path(out).name.lower() not in ("ld_mod.pack", "ld_air_dive.pack")
print(write_pack_file(out, ents + extra, PACK_TYPE_MOD), len(ents) + 2)
