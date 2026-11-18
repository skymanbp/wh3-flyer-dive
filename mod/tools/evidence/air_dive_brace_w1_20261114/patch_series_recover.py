"""TEST-ONLY: make series.py recover from a killed run (Windows TerminateProcess skips `finally`).
Before each run it writes inflight.json (the used_mods.txt bytes it found and the packs it puts in
data/); at the end of the run's `finally` it deletes it. At series start, an inflight.json left by a
killed run is acted on first: used_mods.txt restored, the run's test pack and the autotest helper
packs removed from data/ -- only when no Warhammer3.exe is running."""
from pathlib import Path

p = Path(__file__).resolve().parent / "series.py"
s = p.read_text("utf-8")
assert "inflight.json" not in s

s = s.replace('''def main(jobfile):
    jobs =''', '''INFLIGHT = SCR / "inflight.json"
HELPER_PACKS = ("ld_air_dive_autotest.pack", "ld_entity_read.pack")


def _unlink_retry(path):
    for _ in range(60):
        try:
            if path.exists():
                path.unlink()
            return True
        except OSError:
            time.sleep(5)
    return False


def recover():
    """Undo what a killed run left in the game folder (inflight.json written before the run)."""
    if not INFLIGHT.exists():
        return
    import json
    names = [n.strip() for n in busy().split(",") if n.strip()]
    if any(n.lower() == "warhammer3.exe" for n in names):
        raise SystemExit("STOP: inflight.json from a killed run but Warhammer3.exe is running; not touching the game folder")
    rec = json.loads(INFLIGHT.read_text("utf-8"))
    (GAME / "used_mods.txt").write_bytes(bytes.fromhex(rec["used_mods_hex"]))
    gone = [n for n in rec["packs"] + list(HELPER_PACKS) if (DATA / n).exists() and _unlink_retry(DATA / n)]
    print(time.strftime("%H:%M:%S"), "RECOVERED killed run", rec.get("label"), ": used_mods.txt restored,",
          "removed", gone or "nothing", flush=True)
    INFLIGHT.unlink()


def main(jobfile):
    recover()
    jobs =''')
s = s.replace('''        used_before = (GAME / "used_mods.txt").read_bytes()
        dst = DATA / f"{pack}.pack"
        try:''', '''        used_before = (GAME / "used_mods.txt").read_bytes()
        dst = DATA / f"{pack}.pack"
        import json
        INFLIGHT.write_text(json.dumps({"label": label, "used_mods_hex": used_before.hex(),
                                        "packs": [dst.name]}), encoding="utf-8")
        try:''')
s = s.replace('''        finally:
            for _ in range(60):
                try:
                    if dst.exists():
                        dst.unlink()
                    break
                except OSError:
                    time.sleep(5)
            after = (GAME / "used_mods.txt").read_bytes()
            if after != used_before:
                (GAME / "used_mods.txt").write_bytes(used_before)
                print("WARNING used_mods.txt differed after the run; restored", flush=True)
            release()''', '''        finally:
            _unlink_retry(dst)
            after = (GAME / "used_mods.txt").read_bytes()
            if after != used_before:
                (GAME / "used_mods.txt").write_bytes(used_before)
                print("WARNING used_mods.txt differed after the run; restored", flush=True)
            left = [n for n in HELPER_PACKS if (DATA / n).exists()]
            if left:
                print("WARNING helper packs left after the run, removing:", left, flush=True)
                for n in left:
                    _unlink_retry(DATA / n)
            if not dst.exists() and (GAME / "used_mods.txt").read_bytes() == used_before:
                INFLIGHT.unlink(missing_ok=True)
            release()''')
for n in ("def recover", "recover()\n    jobs", "INFLIGHT.write_text", "INFLIGHT.unlink(missing_ok=True)"):
    assert n in s, n
p.write_text(s, "utf-8")
print("patched")
