"""TEST-ONLY series runner for AIR-DIVE-BRACE-W1 (copied from AIR-DIVE-RELEASE-W1; uses the MAIN repo's
heavy_lock.py so the lock file is the one every lane shares, and waits for heavy.lock to be free).
usage: python -I series.py jobs.txt   (lines: label pack scenario flyers [extra...])
Each run: waits for no game / no GAME_LOCK, takes GAME_LOCK, copies packs/<pack>.pack
into data/, runs air_dive_autotest (continuous-w1 checkout: has --targets) THROUGH
heavy_lock.py, collects the probe log slices, removes the pack, checks used_mods.txt
is byte-identical to before, releases the lock."""
import os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, r"D:/Projects/.worktrees/lore_disaster/air-dive-continuous-w1_scratch")
from run_series import busy as _busy  # warhammer3 / blender / other games (psutil); fails closed

# USER RULING 2026-11-13 ~19:5x ("没事，你直接开始测，我在玩的游戏不吃资源的"): these named
# processes, and only these, no longer block a run. Opt-in via LD_SERIES_ALLOW (comma list);
# every other game / heavy process still blocks, and a failed snapshot still blocks.
RULING_ALLOW = {"starsavior.exe", "unitycrashhandler64.exe"}
ALLOW = {n.strip().lower() for n in os.environ.get("LD_SERIES_ALLOW", "").split(",") if n.strip()}
if ALLOW - RULING_ALLOW:
    raise SystemExit(f"LD_SERIES_ALLOW names {sorted(ALLOW - RULING_ALLOW)}, not covered by the ruling")
_allowed_seen = set()


def busy():
    why = _busy()
    names = [n.strip() for n in why.split(",") if n.strip()]
    if not names or any(" " in n for n in names):   # "process snapshot failed" etc.: block as before
        return why
    kept = [n for n in names if n.lower() not in ALLOW]
    hit = {n.lower() for n in names} & ALLOW
    if hit - _allowed_seen:
        _allowed_seen.update(hit)
        print(time.strftime("%H:%M:%S"), "proceeding with", ", ".join(sorted(hit)),
              "running, under the user ruling of 2026-11-13 19:5x (light game, allowed by name)", flush=True)
    return ", ".join(kept)

LANE = "air-dive-brace-w1"
ROOT = Path(r"D:/Projects/.worktrees/lore_disaster")
LOCK = ROOT / "GAME_LOCK"
GAME = Path(r"D:/SteamLibrary/steamapps/common/Total War WARHAMMER III")
DATA = GAME / "data"
SCR = ROOT / "air-dive-brace-w1_scratch"
HEAVY = Path(r"D:/Projects/lore_disaster/mod/tools/evidence/sprint72_20260913/heavy_lock.py")
HEAVY_FILE = HEAVY.parent / "heavy.lock"
# [round 2] the scratch copy of the continuous-w1 harness (patch_harness.py: target setup, map choice, survey);
# it runs from the continuous-w1 checkout like before
AUTOTEST = SCR / "harness" / "air_dive_autotest.py"
WINDOW = os.environ.get("LD_SERIES_WINDOW", "").strip()
if WINDOW not in ("", "behind", "normal"):
    raise SystemExit(f"LD_SERIES_WINDOW must be behind or normal, not {WINDOW!r}")
HARNESS_CWD = ROOT / "air-dive-continuous-w1"
LOGS = ("ld_brace_probe.txt", "ld_flyer_dive.txt", "ld_flyer_takeoff.txt", "ld_bob_probe.txt")   # [round 4] + bob probe


def steam_up():
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True).stdout.lower()
    return '"steam.exe"' in out


def take_lock():
    while True:
        if HEAVY_FILE.exists():
            print(time.strftime("%H:%M:%S"), "waiting: heavy.lock", HEAVY_FILE.read_text("utf-8", errors="replace").strip(), flush=True)
            time.sleep(60)
            continue
        why = busy()
        if not why and not LOCK.exists():
            LOCK.write_text(LANE, encoding="utf-8")
            time.sleep(2)
            if LOCK.read_text(encoding="utf-8").strip() == LANE and not busy():
                return
            if LOCK.exists() and LOCK.read_text(encoding="utf-8").strip() == LANE:
                LOCK.unlink()
        holder = LOCK.read_text(encoding="utf-8").strip() if LOCK.exists() else "-"
        print(time.strftime("%H:%M:%S"), "waiting:", why or "-", "lock:", holder, flush=True)
        time.sleep(120)


def release():
    if LOCK.exists() and LOCK.read_text(encoding="utf-8").strip() == LANE:
        LOCK.unlink()


INFLIGHT = SCR / "inflight.json"
HELPER_PACKS = ("ld_air_dive_autotest.pack", "ld_entity_read.pack")
SPEED_FILE = GAME / "ld_brace_speed.txt"


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
    if SPEED_FILE.exists() and _unlink_retry(SPEED_FILE):
        gone.append(SPEED_FILE.name)
    print(time.strftime("%H:%M:%S"), "RECOVERED killed run", rec.get("label"), ": used_mods.txt restored,",
          "removed", gone or "nothing", flush=True)
    INFLIGHT.unlink()


def main(jobfile):
    recover()
    jobs = [l.split() for l in Path(jobfile).read_text("utf-8").splitlines() if l.strip() and not l.startswith("#")]
    for label, pack, scenario, flyers, *extra in jobs:
        speed = [a.split("=", 1)[1] for a in extra if a.startswith("--speed=")]
        entity_read = [] if "--no-entity-read" in extra else ["--entity-read"]
        extra = [a for a in extra if a != "--no-entity-read"]
        extra = [a for a in extra if not a.startswith("--speed=")]
        out = SCR / "runs" / label
        if (out / "verdict.json").is_file():
            print("skip", label, flush=True)
            continue
        if not steam_up():
            print("STOP: Steam is not running; not starting it", flush=True)
            return 2
        take_lock()
        print(time.strftime("%H:%M:%S"), "lock taken; run", label, flush=True)
        used_before = (GAME / "used_mods.txt").read_bytes()
        dst = DATA / f"{pack}.pack"
        import json
        INFLIGHT.write_text(json.dumps({"label": label, "used_mods_hex": used_before.hex(),
                                        "packs": [dst.name]}), encoding="utf-8")
        try:
            if speed:
                SPEED_FILE.write_text(str(float(speed[0])), encoding="utf-8")
            shutil.copyfile(SCR / "packs" / f"{pack}.pack", dst)
            out.mkdir(parents=True, exist_ok=True)
            offs = {n: ((GAME / n).stat().st_size if (GAME / n).exists() else 0) for n in LOGS}
            cmd = [sys.executable, "-P", str(HEAVY), LANE + ":" + label, "--wait", "900",
                   "--log", str(out / "autotest.log"), "--cwd", str(HARNESS_CWD), "--",
                   sys.executable, "-P", str(AUTOTEST), "--scenario", scenario, "--test-pack", dst.name,
                   "--flyers", flyers, *entity_read, "--out-dir", str(out)] + extra
            # [2026-11-15] LD_SERIES_WINDOW=behind|normal for every run (a job's own --window wins)
            if WINDOW and not any(e.startswith("--window") for e in extra):
                cmd.append(f"--window={WINDOW}")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5400)
            (out / "stdout.txt").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
            for n, o in offs.items():
                p = GAME / n
                if p.exists():
                    with open(p, "rb") as fh:
                        fh.seek(o)
                        (out / (n[:-4] + "_slice.txt")).write_bytes(fh.read())
            print("\n".join(l for l in r.stdout.splitlines()[-12:] if not l.startswith("VERDICT")), flush=True)
            print("exit", r.returncode, flush=True)
        finally:
            _unlink_retry(dst)
            _unlink_retry(SPEED_FILE)
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
            release()
            print(time.strftime("%H:%M:%S"), "lock released", flush=True)
        time.sleep(20)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]) or 0)
