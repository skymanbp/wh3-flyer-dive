"""TEST-ONLY offline probe of series.recover() against a temp game folder (no game, no lock)."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import series as s

with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    g = t / "game"
    d = g / "data"
    d.mkdir(parents=True)
    s.GAME, s.DATA, s.INFLIGHT = g, d, t / "inflight.json"
    for n in ("ld_adb_A.pack", "ld_air_dive_autotest.pack", "ld_entity_read.pack", "keep_me.pack"):
        (d / n).write_bytes(b"x")
    (g / "used_mods.txt").write_bytes(b"TEST STATE\n")
    s.INFLIGHT.write_text(json.dumps({"label": "X", "used_mods_hex": b"orig\n".hex(), "packs": ["ld_adb_A.pack"]}))
    s.busy = lambda: "warhammer3.exe"
    try:
        s.recover()
        print("FAIL: ran while game up")
    except SystemExit as e:
        print("refuses with game up:", "Warhammer3" in str(e) and (g / "used_mods.txt").read_bytes() == b"TEST STATE\n")
    s.busy = lambda: ""
    s.recover()
    print("restored:", (g / "used_mods.txt").read_bytes() == b"orig\n",
          sorted(p.name for p in d.iterdir()) == ["keep_me.pack"], not s.INFLIGHT.exists())
    s.recover()
    print("no-op without journal: ok")
