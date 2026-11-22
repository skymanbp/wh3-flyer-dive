"""Copy a built test pack with the lane's load probe added as script/battle/mod/smallflyer_load.lua."""
import sys
from pathlib import Path

REPO, SRC, DST, LUA = (Path(a) for a in sys.argv[1:5])
sys.path[:0] = [str(REPO / "mod" / "tools")]
from packfile import PackFile, PACK_TYPE_MOD, write_pack_file

pk = PackFile.open(str(SRC))
entries = [(e.path, pk.read_file(e)) for e in pk.entries]
pk.close()
entries.append(("script/battle/mod/" + LUA.stem + ".lua", LUA.read_bytes().replace(b"\r\n", b"\n")))
DST.parent.mkdir(parents=True, exist_ok=True)
print(DST, write_pack_file(str(DST), entries, PACK_TYPE_MOD), "bytes,", len(entries), "entries")
