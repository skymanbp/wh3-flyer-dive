#!/usr/bin/env python3
"""The ONE way to run the flyer mod's in-game tests (test standard, stage 6 2026-11-18): one battle, or a list.

One battle (``one``):
  1. refuses while anything heavy runs (game_process.busy_refusal: the owner's Warhammer3, another game, the
     heavy-job lock, a pytest / auto_test / build_pack job) -- never waits, never touches a running game;
  2. refuses when a pack to deploy is already in the game's data folder, or a pin_probe.cfg is already there;
  3. removes the stale appended probe records (PROBE_RECORDS) left in the game folder by an earlier run;
  4. copies each ``--deploy SRC=NAME`` pack into data/ (sha256 recorded), writes ``--pin-cfg`` if given;
  5. runs pipelines/air_dive_autotest.py with the given driver arguments and ``--out-dir`` = the run's folder
     (the driver itself launches and closes the game, and writes status / hp / verdict.json there);
  6. removes what it deployed, collects the appended game logs (APPENDED_LOGS: this run's part and the whole file)
     and the probe records, checks that used_mods.txt and the data folder are as they were before;
  7. runs the matching report on every record (REPORTS) into ``<record>_report.txt``;
  8. writes run.json (what was run, exit codes, verdict, whether the setup was the standard one, the checks) and
     one line in <out root>/LOG.md.
  ``--share-machine`` (the owner's order 2026-11-22: "直接跑，不用管机器"): step 1 does not refuse for another
  heavy job or a held heavy-job lock (the game checks stay), and the lock is neither taken nor released.
  Otherwise, from step 4 to the cleanup of step 6 it holds the heavy-job lock (game_process.HEAVY_LOCK, so another lane's
  heavy job waits) and keeps <out root>/inflight.json (used_mods.txt as it was, what it deploys): a run that was
  killed is undone at the start of the next one (used_mods.txt restored, its packs, the helper pack and
  pin_probe.cfg removed, its lock released) -- never while a Warhammer3 runs.
A list (``list``): one battle per line of a jobs file, ``<label> [--deploy SRC=NAME ...] [--pin-cfg ...] --
<driver args>`` ('#' starts a comment); a label whose folder already has run.json is skipped, so a list that
stopped (a refusal, the owner's game) is resumed by running it again. The list stops at the first refusal.

Output: ``--out-root`` (default FLYER_RUNS_DIR or D:/Projects/.worktrees/wh3-flyer-dive/runs), one folder per
label; never inside this repository.

usage: python -P tools/pipelines/flyer_run.py one <label> [--deploy SRC=NAME ...] [--pin-cfg "a;b"]
           [--out-root DIR] -- <air_dive_autotest.py arguments>
       python -P tools/pipelines/flyer_run.py list <jobs file> [--out-root DIR]
"""
import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path, after the line above
import game_process  # noqa: E402 -- because rolepath above puts lib/ on sys.path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DRIVER = HERE / "air_dive_autotest.py"
GAME_ROOT = Path(os.environ.get("WH3_ROOT", r"D:\SteamLibrary\steamapps\common\Total War WARHAMMER III"))
OUT_ROOT = Path(os.environ.get("FLYER_RUNS_DIR", r"D:\Projects\.worktrees\wh3-flyer-dive\runs"))
PIN_CFG = "pin_probe.cfg"
# the battle logs the mod and its recorders APPEND to (this run's part is cut out by size)
APPENDED_LOGS = ("flyer_dive.txt", "flyer_takeoff.txt", "flyer_breath.txt", "lua_mod_log.txt", "flyer_dive_probe.txt")
# the probe records a probe pack writes (removed before a run, collected after)
PROBE_RECORDS = ("flyer_size_probe.txt", "reflect_probe.txt", "pin_probe.txt")
# the one report per record type
REPORTS = {"reflect_probe.txt": "reflect_probe_report.py", "flyer_size_probe.txt": "flyer_size_probe_report.py",
           "pin_probe.txt": "pin_probe_report.py", "flyer_dive_probe.txt": "air_dive_probe_report.py"}
DRIVER_TIMEOUT_S = 1200
HELPER_PACK = "flyer_dive_autotest.pack"      # air_dive_autotest.HELPER_PACK: left in data/ by a killed driver


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside_repo(path):
    try:
        Path(path).resolve().relative_to(REPO)
        return True
    except ValueError:
        return False


def parse_deploys(items):
    out = []
    for item in items:
        src, sep, name = item.partition("=")
        if not sep or not name or "/" in name or "\\" in name:
            raise SystemExit(f"[flyer_run] REFUSING: --deploy wants SRC=NAME (a file name in data/), got {item!r}")
        if not Path(src).is_file():
            raise SystemExit(f"[flyer_run] REFUSING: {src} does not exist")
        out.append((Path(src), name))
    return out


def _log(out_root, line):
    Path(out_root).mkdir(parents=True, exist_ok=True)
    with open(Path(out_root) / "LOG.md", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def recover(out_root, game_root, game_running=game_process.running_game_refusal, lock=None):
    """Undo what a killed run left (inflight.json). Returns a log line, or None when there was nothing to undo;
    raises SystemExit when the game runs (the folder is not touched then)."""
    inflight = Path(out_root) / "inflight.json"
    if not inflight.is_file():
        return None
    why = game_running()
    if why:
        raise SystemExit(f"[flyer_run] STOP: a killed run left {inflight} but {why}; not touching the game folder")
    rec = json.loads(inflight.read_text("utf-8"))
    game_root, done = Path(game_root), []
    if rec.get("used_mods_hex") is not None:
        (game_root / "used_mods.txt").write_bytes(bytes.fromhex(rec["used_mods_hex"]))
        done.append("used_mods.txt restored")
    for d in rec.get("deployed", []):
        p = game_root / "data" / d["name"]
        if p.is_file() and sha256(p) == d["sha256"]:
            p.unlink()
            done.append(f"removed {d['name']}")
    if (game_root / "data" / HELPER_PACK).is_file():
        (game_root / "data" / HELPER_PACK).unlink()
        done.append(f"removed {HELPER_PACK}")
    if rec.get("pin_cfg") and (game_root / PIN_CFG).is_file():
        (game_root / PIN_CFG).unlink()
        done.append(f"removed {PIN_CFG}")
    lock = Path(lock or game_process.HEAVY_LOCK)
    if lock.is_file() and lock.read_text("utf-8", errors="replace").strip() == rec.get("lock_token"):
        lock.unlink()
        done.append("released its heavy-job lock")
    inflight.unlink()
    line = f"- {time.strftime('%F %T')} RECOVERED killed run **{rec.get('label')}**: {', '.join(done) or 'nothing'}"
    _log(out_root, line)
    return line


def take_lock(lock, token):
    """Create the heavy-job lock (exclusive); False when someone holds it."""
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token)
    return True


def release_lock(lock, token):
    lock = Path(lock)
    if lock.is_file() and lock.read_text("utf-8", errors="replace").strip() == token:
        lock.unlink()


def run_one(label, deploys, driver_args, out_root=OUT_ROOT, pin_cfg=None, busy=game_process.busy_refusal,
            game_root=GAME_ROOT, driver=DRIVER, timeout=DRIVER_TIMEOUT_S, lock=None,
            game_running=game_process.running_game_refusal, share_machine=False):
    """One battle; returns (exit code, run.json dict). 6 = refused, nothing touched; a finished label (run.json
    present) is not run again."""
    if inside_repo(out_root):
        raise SystemExit(f"[flyer_run] REFUSING: output {out_root} is inside the repository")
    game_root = Path(game_root)
    out = Path(out_root) / label
    if (out / "run.json").is_file():
        return 0, json.loads((out / "run.json").read_text("utf-8"))
    data = game_root / "data"
    lock = Path(lock or game_process.HEAVY_LOCK)
    recovered = recover(out_root, game_root, game_running, lock)
    if recovered:
        print(f"[flyer_run] {recovered}")
    why = busy(own_pids=(os.getpid(),), games_only=True) if share_machine else busy(own_pids=(os.getpid(),))
    refusal = None
    if why:
        refusal = f"busy: {why}"
    elif any((data / n).exists() for _s, n in deploys):
        refusal = "a pack to deploy is already in data/: " + ", ".join(n for _s, n in deploys if (data / n).exists())
    elif (game_root / PIN_CFG).exists():
        refusal = f"a {PIN_CFG} is already in the game folder"
    token = f"flyer_run {label} pid {os.getpid()} {time.strftime('%F %T')}"
    if not refusal and not share_machine and not take_lock(lock, token):
        refusal = f"heavy-job lock {lock} was taken just now"
    if refusal:
        _log(out_root, f"- {time.strftime('%F %T')} **{label}** NOT RUN: {refusal}")
        print(f"[flyer_run] {label}: NOT RUN: {refusal}")
        return 6, {"label": label, "refused": refusal}
    out.mkdir(parents=True, exist_ok=True)
    pre = []
    for f in PROBE_RECORDS:
        if (game_root / f).exists():
            (game_root / f).unlink()
            pre.append(f"deleted stale {f}")
    used_mods = game_root / "used_mods.txt"
    um_before = sha256(used_mods) if used_mods.is_file() else None
    listing_before = sorted(os.listdir(data))
    deployed, wrote_cfg = [], False
    sizes = {f: (game_root / f).stat().st_size if (game_root / f).is_file() else 0 for f in APPENDED_LOGS}
    cmd = [sys.executable, "-P", str(driver)] + list(driver_args) + ["--out-dir", str(out)]
    rc, started = None, time.strftime("%F %T")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    inflight = Path(out_root) / "inflight.json"
    inflight.write_text(json.dumps({"label": label, "lock_token": token, "pin_cfg": bool(pin_cfg),
                                    "used_mods_hex": used_mods.read_bytes().hex() if used_mods.is_file() else None,
                                    "deployed": [{"name": n, "sha256": sha256(s)} for s, n in deploys]}),
                        encoding="utf-8")
    try:
        for src, name in deploys:
            shutil.copyfile(src, data / name)
            deployed.append({"name": name, "source": str(src), "sha256": sha256(data / name)})
        if pin_cfg:
            (game_root / PIN_CFG).write_text("\n".join(x.strip() for x in pin_cfg.split(";")) + "\n",
                                             encoding="utf-8")
            wrote_cfg = True
        (out / "command.txt").write_text(shlex.join(cmd) + "\n", encoding="utf-8")
        with open(out / "stdout.txt", "w", encoding="utf-8") as so:
            try:
                rc = subprocess.run(cmd, stdout=so, stderr=subprocess.STDOUT, timeout=timeout, env=env,
                                    cwd=str(REPO / "mod")).returncode
            except subprocess.TimeoutExpired:
                rc = "timeout"
    finally:
        for d in deployed:
            (data / d["name"]).unlink(missing_ok=True)
        if wrote_cfg:
            (game_root / PIN_CFG).unlink(missing_ok=True)
        if not share_machine:
            release_lock(lock, token)
        inflight.unlink(missing_ok=True)
    collected = {}
    for f, before in sizes.items():
        p = game_root / f
        if p.is_file():
            whole = p.read_bytes()
            (out / f"full_{f}").write_bytes(whole)
            (out / f).write_bytes(whole[before:])
            collected[f] = len(whole) - before
        else:
            collected[f] = None
    for f in PROBE_RECORDS:
        if (game_root / f).is_file():
            shutil.copyfile(game_root / f, out / f)
            collected[f] = (game_root / f).stat().st_size
    reports = {}
    for f, tool in REPORTS.items():
        if (out / f).is_file() and (out / f).stat().st_size:
            with open(out / f"{Path(f).stem}_report.txt", "w", encoding="utf-8") as rep:
                reports[f] = subprocess.run([sys.executable, "-P", str(HERE / tool), str(out / f)], stdout=rep,
                                            stderr=subprocess.STDOUT, cwd=str(REPO / "mod"), env=env).returncode
    verdict = json.loads((out / "verdict.json").read_text("utf-8")) if (out / "verdict.json").is_file() else {}
    um_after = sha256(used_mods) if used_mods.is_file() else None
    listing_after = sorted(os.listdir(data))
    try:
        games_after = game_process.game_pids()
    except game_process.ProcessProbeStalled as exc:
        games_after = f"unknown ({exc})"
    result = {"label": label, "started": started, "ended": time.strftime("%F %T"), "command": cmd,
              "pre": pre, "deployed": deployed, "pin_cfg": pin_cfg, "driver_exit": rc,
              "verdict": verdict.get("verdict"), "standard": verdict.get("standard"),
              "nonstandard": verdict.get("nonstandard"), "collected": collected, "reports": reports,
              "used_mods_unchanged": um_before == um_after,
              "data_folder_unchanged": listing_before == listing_after,
              "data_folder_diff": sorted(set(listing_after) ^ set(listing_before)),
              "warhammer3_after": games_after, "shared_machine": share_machine}
    (out / "run.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    flag = "standard" if result["standard"] else f"NONSTANDARD {result['nonstandard']}"
    _log(out_root, f"- {started} -> {result['ended']} **{label}** rc={rc} verdict={result['verdict']} {flag} "
                   f"reports={reports} used_mods {'OK' if result['used_mods_unchanged'] else 'CHANGED'} "
                   f"data {'OK' if result['data_folder_unchanged'] else 'DIFFERS'} Warhammer3 after: {games_after}")
    code = rc if isinstance(rc, int) else 1
    if not (result["data_folder_unchanged"] and result["used_mods_unchanged"]):
        code = code or 1
    return code, result


def parse_job(line):
    """(label, deploys, pin_cfg, driver args) from one jobs-file line"""
    words = shlex.split(line, posix=False)
    if "--" in words:
        cut = words.index("--")
        mine, driver_args = words[:cut], words[cut + 1:]
    else:
        mine, driver_args = words, []
    ap = argparse.ArgumentParser(prog="job")
    ap.add_argument("label")
    ap.add_argument("--deploy", action="append", default=[])
    ap.add_argument("--pin-cfg")
    a = ap.parse_args(mine)
    strip = lambda s: s[1:-1] if len(s) > 1 and s[0] == s[-1] == '"' else s  # noqa: E731 -- because the quotes of a non-posix split are the line's own
    return a.label, [strip(d) for d in a.deploy], a.pin_cfg and strip(a.pin_cfg), [strip(w) for w in driver_args]


def run_list(jobs_file, out_root=OUT_ROOT, one=run_one):
    """every job of the file in order; stops at the first refusal. Returns the exit code of the list."""
    worst = 0
    for raw in Path(jobs_file).read_text("utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        label, deploys, pin_cfg, driver_args = parse_job(line)
        code, _res = one(label, parse_deploys(deploys), driver_args, out_root=out_root, pin_cfg=pin_cfg)
        if code == 6:
            print(f"[flyer_run] list stopped at {label} (refused); run the list again to resume")
            return 6
        worst = worst or code
    return worst


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    driver_args = []
    if "--" in argv:
        cut = argv.index("--")
        argv, driver_args = argv[:cut], argv[cut + 1:]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    one = sub.add_parser("one")
    one.add_argument("label")
    one.add_argument("--deploy", action="append", default=[], metavar="SRC=NAME")
    one.add_argument("--pin-cfg")
    one.add_argument("--out-root", default=str(OUT_ROOT))
    one.add_argument("--share-machine", action="store_true",
                     help="run while another heavy job runs (the owner's say-so); the game checks stay")
    lst = sub.add_parser("list")
    lst.add_argument("jobs")
    lst.add_argument("--out-root", default=str(OUT_ROOT))
    args = ap.parse_args(argv)
    if args.mode == "one":
        code, _res = run_one(args.label, parse_deploys(args.deploy), driver_args, out_root=Path(args.out_root),
                             pin_cfg=args.pin_cfg, share_machine=args.share_machine)
        return code
    return run_list(args.jobs, out_root=Path(args.out_root))


if __name__ == "__main__":
    sys.exit(main())
