"""[test standard, stage 6 2026-11-18] The one runner (pipelines/flyer_run.py), the one busy check
(lib/game_process.busy_refusal) and the D15 report on tonight's two real records.

* the D15 report on trimmed copies of series4 d15_brace_spear / _sword (tests/data/d15_1118, lines verbatim):
  the numbers the supervisor read by hand -- 6 cost calls; the cost's own type-2 applications 282, 153, 171, 85,
  7 + 1, 7 + 1; the control 0 calls, 7 skips, 0 errors;
* busy_refusal against stubbed process probes: free; the owner's game; another game; a Steam game folder (and
  the excepted one); the heavy-job lock; another python heavy job (and the runner's own pid); a probe that cannot
  answer is a refusal (fail-closed);
* run_one against a fake game folder and a fake driver: a busy machine is refused with nothing touched; a pack
  already in data/ is refused; a run deploys, removes what it deployed, cuts this run's part of each appended log,
  collects the probe records, runs the matching report, writes run.json and LOG.md; a finished label is not run
  again; an output folder inside the repository is refused; the heavy-job lock is held during the driver and
  released after, a held lock refuses; a pin cfg is written for the driver and removed; a driver that leaves a
  file in data/ fails the run; a killed run (inflight.json) is undone at the next start, and not while the game
  runs;
* run_list: comments skipped, quoted arguments kept, stops at the first refusal;
* the readers folded into reflect_probe_report (the supervisor's verify_d15 / read_d15_run / verify_contact):
  on the real spear record the totals the supervisor's reader printed (888 / 1943 / 631 / 947, each contact);
  on made-up records: a hit is classed by the calculator record before it on the SAME entity by clock (not the
  last record overall, not one after it), the 5 s window edge, the contact window [-2 s, +3 s] edges, and a
  timeline lane with no landing named, not dropped.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path
import flyer_run  # noqa: E402 -- because rolepath above puts pipelines/ on sys.path
import game_process  # noqa: E402 -- same reason (lib/)
import reflect_probe_report as rrep  # noqa: E402 -- same reason

DATA = TESTS_DIR / "data" / "d15_1118"


def summary(name):
    on, units, refl, dmg, hp, other = rrep.parse((DATA / f"{name}.txt").read_text("utf-8"))
    return units, dmg, other


class D15RealRecords(unittest.TestCase):
    def test_spear_run(self):
        units, dmg, other = summary("d15_brace_spear")
        out, problems = rrep.cost_summary(units, dmg, other)
        self.assertEqual(problems, [])
        self.assertEqual(sum(1 for ln in other if ln.split()[:1] == ["X"]), 6)
        text = "\n".join(out)
        for want in ("applied 282 on 1 model(s): B2F72980 (max 9424) 282 at 32800 ms",
                     "applied 153 on 1 model(s): B2E906A0 (max 5103) 153 at 52400 ms",
                     "applied 171 on 1 model(s): B3081460 (max 2858) 171 at 71700 ms",
                     "applied 85 on 1 model(s): B3081460 (max 2858) 85 at 79100 ms",
                     "applied 16 on 2 model(s): B31FCD00 (max 261) 7 at 88400 ms, B29557A0 (max 261) 1 at 88400 ms, "
                     "B31FCD00 (max 261) 7 at 88500 ms, B29557A0 (max 261) 1 at 88500 ms"):
            self.assertIn(want, text)
        own = [d["damage"] for d in dmg if rrep._own_application(d)]
        self.assertEqual(own, [282, 153, 171, 85, 7, 1, 7, 1])
        self.assertIn("outside every call's window: 0", text)
        _out, problems = rrep.dive_cost_summary(None, units, dmg, other)
        self.assertEqual([p for p in problems if "MARK" not in p], [])

    def test_sword_control(self):
        units, dmg, other = summary("d15_brace_sword")
        out, problems = rrep.cost_summary(units, dmg, other)
        self.assertEqual(problems, [])
        kinds = [ln.split()[0] for ln in other if ln.split()]
        self.assertEqual((kinds.count("X"), kinds.count("XNOATTR"), kinds.count("XERR")), (0, 7, 0))
        self.assertEqual([d for d in dmg if rrep._own_application(d)], [])
        self.assertIn("outside every call's window: 0", "\n".join(out))


class FoldedReaders(unittest.TestCase):
    def test_real_spear_record(self):
        on, units, refl, dmg, hp, other = rrep.parse((DATA / "d15_brace_spear.txt").read_text("utf-8"))
        text = "\n".join(rrep.flyer_damage_summary(units, dmg, hp, other))
        for want in ("wh2_main_hef_mon_star_dragon uid 1002 (1 models): hits 31, damage 888, first at 32800 ms, 2 ticks",
                     "feral_manticore_0 uid 1003 (1 models): hits 56, damage 1943",
                     "griffon_knights_0 uid 1004 (4 models): hits 14, damage 631",
                     "pegasus_knights uid 1005 (24 models): hits 53, damage 947",
                     "first 10 s from first damage: damage 324",
                     "CONTACT wh2_main_hef_mon_star_dragon uid 1002: first type-5/6 call as attacker at 32600 ms "
                     "(tick 325) on wh_main_emp_inf_spearmen_1; damage calls on them in [-2 s, +3 s] by type "
                     "{5: 17, 6: 2}, sum 833",
                     "by calculator record before it: not logged (no C lines)"):
            self.assertIn(want, text)

    FLY, FOOT = "AAAA0001", "BBBB0002"
    REC = "\n".join([
        "BATTLE test on: buffer 0",
        f"UNIT 1 0 dragon obj={FLY} men=1 flyer=1",
        f"UNIT 2 1 spearmen obj={FOOT} men=60 flyer=0",
        # C ms which rdi rbx ret1 ret2 x0 x6 x7 x8 thread clock [rdi+8] [rdi+10] [rbx+8] [rbx+10]
        "C 1000 2 0 0 0 00000001430AF7B4 3F800000 3F333333 40000000 0 7 100 E1 0 0 0",
        "C 1000 1 0 0 0 00000001430B0284 3F800000 3F333333 3F800000 0 7 102 E9 0 0 0",
        # D ms tick ret victim unit damage type flyer flying_entity thread clock
        f"D 1000 10 0000000143000000 E1 {FLY} 50 0 1 E1 7 101",      # after the MULT on E1 -> MULT AF7B4
        f"D 1000 10 0000000143000000 E1 {FLY} 20 0 1 E1 7 103",      # E9's GATE is a different entity -> still MULT
        f"D 1000 10 0000000143000000 E2 {FLY} 30 0 1 E2 7 104",      # nothing before it on E2 -> none
        f"D 5999 60 0000000143000000 E1 {FLY} 7 0 1 E1 7 200",       # inside the first 5 s
        f"D 6000 60 0000000143000000 E1 {FLY} 9 0 1 E1 7 201",       # first 5 s ends before 6000
        f"D 2999 30 0000000143000000 F1 {FOOT} 1 5 0 0 7 300",       # contact window edges (landing 5000)
        f"D 3000 30 0000000143000000 F1 {FOOT} 2 5 0 0 7 301",
        f"D 8000 80 0000000143000000 F1 {FOOT} 4 6 0 0 7 302",
        f"D 8001 80 0000000143000000 F1 {FOOT} 8 6 0 0 7 303",
        "U 900 1:1.0:1:0 2:1.0:60:0",
        "U 6100 1:0.99:1:1 2:0.98:60:1",
    ]) + "\n"
    TIMELINE = ("1.0s driver: 100 lane 1 flyer=dragon uid=1 x target=spearmen uid=2\n"
                "1.0s driver: 100 lane 2 flyer=dragon uid=1 x target=spearmen uid=2\n"
                "2.0s driver: 4000 track 1 y flying=true\n"
                "3.0s driver: 5000 track 1 y flying=false\n"
                "3.5s driver: 5500 track 1 y flying=false\n")

    def test_class_by_the_record_before_it_on_the_same_entity(self):
        on, units, refl, dmg, hp, other = rrep.parse(self.REC)
        text = "\n".join(rrep.flyer_damage_summary(units, dmg, hp, other))
        self.assertIn("hits 5, damage 116, first at 1000 ms; health left 0.99, pool estimate 11600", text)
        self.assertIn("MULT AF7B4: n=4 mean 21.5 min 7 max 50 sum 86", text)
        self.assertIn("none: n=1 mean 30.0 min 30 max 30 sum 30", text)
        self.assertNotIn("GATE", text.split("CONTACT")[0].split("first 5 s")[0])
        self.assertIn("first 5 s from first damage: damage 107, health 1.0 -> 1.0, "
                      "by class {'MULT AF7B4': 77, 'none': 30}", text)

    def test_lane_contact_window(self):
        on, units, refl, dmg, hp, other = rrep.parse(self.REC)
        out = rrep.timeline_contact_summary(units, dmg, other, self.TIMELINE)
        self.assertEqual(out[0], "LANE CONTACT 1 dragon: on the ground by 5000 ms; first gate None (-), first multiply "
                                 "1000, first damage on it 1000; damage calls on its target in [-2 s, +3 s] by type "
                                 "{5: 1, 6: 1}, sum 6")
        self.assertIn("LANE CONTACT 2: no UNIT line or no landing", out[1])
        self.assertEqual(rrep.timeline_contact_summary(units, dmg, other, ""), [])


class Busy(unittest.TestCase):
    def check(self, table=(), paths=None, lines=None, game=None, lock=False, stalled=None):
        paths = paths or {}
        with tempfile.TemporaryDirectory() as td:
            lock_path = os.path.join(td, "heavy.lock")
            if lock:
                Path(lock_path).write_text("x")

            def cmd_lines():
                if stalled == "python":
                    raise game_process.ProcessProbeStalled("no answer")
                return dict(lines or {})

            def ptable():
                if stalled == "table":
                    raise game_process.ProcessProbeStalled("no snapshot")
                return list(table)
            with mock.patch.object(game_process, "running_game_refusal", lambda: game), \
                    mock.patch.object(game_process, "process_table", ptable), \
                    mock.patch.object(game_process, "image_path", lambda pid: paths.get(pid)), \
                    mock.patch.object(game_process, "python_command_lines", cmd_lines), \
                    mock.patch.object(game_process, "HEAVY_LOCK", lock_path):
                return game_process.busy_refusal(own_pids=(7,))

    def test_free(self):
        self.assertIsNone(self.check([(1, "explorer.exe"), (7, "python.exe")], lines={7: "python flyer_run.py pytest"}))

    def test_each_reason(self):
        self.assertIn("Warhammer3", self.check(game="Warhammer3.exe is already running (pid 5)"))
        self.assertIn("Overwatch.exe#3 is running", self.check([(3, "Overwatch.exe")]))
        steam = r"D:\SteamLibrary\steamapps\common\Some Game\game.exe"
        self.assertIn("steam game game.exe#4", self.check([(4, "game.exe")], paths={4: steam}))
        excepted = r"D:\SteamLibrary\steamapps\common\StarSavior\StarSavior.exe"
        self.assertIsNone(self.check([(4, "StarSavior.exe")], paths={4: excepted}))
        self.assertIn("heavy-job lock", self.check(lock=True))
        self.assertIn("python heavy job is running (pid 9)",
                      self.check(lines={9: "python -m pytest mod/tools/tests", 7: "python -m pytest"}))
        self.assertIn("python heavy job", self.check(lines={9: "python build_pack.py"}))

    def test_fail_closed(self):
        self.assertIn("process table unreadable", self.check(stalled="table"))
        self.assertIn("no answer", self.check(stalled="python"))


FAKE_DRIVER = r'''
import json, sys
from pathlib import Path
args = sys.argv[1:]
out = Path(args[args.index("--out-dir") + 1])
game = Path(args[args.index("--game") + 1])
assert (game / "data" / "probe_d15.pack").read_bytes() == b"PACK", "not deployed"
with open(game / "flyer_dive.txt", "a", encoding="utf-8") as f:
    f.write("BATTLE this run\n")
(game / "reflect_probe.txt").write_text("BATTLE x on: buffer 0\n", encoding="utf-8")
lock = Path(args[args.index("--lock") + 1]) if "--lock" in args else None
assert lock is None or lock.read_text(encoding="utf-8").startswith("flyer_run "), "lock not held"
if "--want-pin" in args:
    assert (game / "pin_probe.cfg").read_text(encoding="utf-8") == "a\nb\n", "pin cfg"
if "--steal-lock" in args:        # the lock was cleared and someone else took it while the battle ran
    lock.write_text("another job", encoding="utf-8")
if "--litter" in args:
    (game / "data" / "left_behind.pack").write_bytes(b"x")
(out / "verdict.json").write_text(json.dumps({"verdict": "PASS", "standard": True, "nonstandard": []}))
print("VERDICT {}")
'''


class Runner(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        self.game, self.out = root / "game", root / "runs"
        (self.game / "data").mkdir(parents=True)
        (self.game / "data" / "vanilla.pack").write_bytes(b"v")
        (self.game / "used_mods.txt").write_text("mod x;\n")
        (self.game / "flyer_dive.txt").write_text("BATTLE an older run\n")
        (self.game / "reflect_probe.txt").write_text("stale\n")
        self.pack = root / "probe_d15.pack"
        self.pack.write_bytes(b"PACK")
        self.driver = root / "driver.py"
        self.driver.write_text(FAKE_DRIVER, encoding="utf-8")
        self.lock = root / "heavy.lock"

    def tearDown(self):
        self.td.cleanup()

    def one(self, label="r1", busy=lambda own_pids=(): None, extra=(), pin_cfg=None, game_running=lambda: None):
        return flyer_run.run_one(label, [(self.pack, "probe_d15.pack")],
                                 ["--game", str(self.game), "--lock", str(self.lock)] + list(extra),
                                 out_root=self.out, busy=busy, game_root=self.game, driver=self.driver, timeout=60,
                                 pin_cfg=pin_cfg, lock=self.lock, game_running=game_running)

    def test_lock_held_during_and_released(self):
        code, res = self.one()
        self.assertEqual(code, 0, res)
        self.assertFalse(self.lock.exists())
        self.assertFalse((self.out / "inflight.json").exists())

    def test_someone_elses_lock_is_left_alone(self):
        code, res = self.one(extra=["--steal-lock"])
        self.assertEqual(code, 0, res)
        self.assertEqual(self.lock.read_text(encoding="utf-8"), "another job")

    def test_lock_already_held_refused(self):
        self.lock.write_text("someone else")
        code, res = self.one()
        self.assertEqual(code, 6)
        self.assertIn("lock", res["refused"])
        self.assertEqual(self.lock.read_text(), "someone else")
        self.assertFalse((self.game / "data" / "probe_d15.pack").exists())

    def test_pin_cfg_written_and_removed(self):
        code, res = self.one(extra=["--want-pin"], pin_cfg="a; b")
        self.assertEqual(code, 0, res)
        self.assertFalse((self.game / "pin_probe.cfg").exists())

    def test_driver_leaving_a_file_fails(self):
        code, res = self.one(extra=["--litter"])
        self.assertEqual(code, 1)
        self.assertFalse(res["data_folder_unchanged"])
        self.assertEqual(res["data_folder_diff"], ["left_behind.pack"])

    def killed_run(self):
        """what a run killed inside its driver leaves behind"""
        (self.game / "data" / "probe_d15.pack").write_bytes(b"PACK")
        (self.game / "data" / flyer_run.HELPER_PACK).write_bytes(b"helper")
        (self.game / "pin_probe.cfg").write_text("a\n")
        (self.game / "used_mods.txt").write_text("mod probe_d15.pack;\n")
        self.lock.write_text("flyer_run dead pid 1")
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "inflight.json").write_text(json.dumps({
            "label": "dead", "lock_token": "flyer_run dead pid 1", "pin_cfg": True,
            "used_mods_hex": b"mod x;\n".hex(),
            "deployed": [{"name": "probe_d15.pack", "sha256": flyer_run.sha256(self.pack)}]}))

    def test_killed_run_recovered(self):
        self.killed_run()
        code, res = self.one()
        self.assertEqual(code, 0, res)
        self.assertEqual((self.game / "used_mods.txt").read_text(), "mod x;\n")
        self.assertEqual(sorted(os.listdir(self.game / "data")), ["vanilla.pack"])
        self.assertFalse((self.game / "pin_probe.cfg").exists())
        log = (self.out / "LOG.md").read_text("utf-8")
        self.assertIn("RECOVERED killed run **dead**: used_mods.txt restored, removed probe_d15.pack, removed "
                      "flyer_dive_autotest.pack, removed pin_probe.cfg, released its heavy-job lock", log)
        self.assertFalse(self.lock.exists())

    def test_recovery_keeps_a_pack_that_is_not_ours(self):
        self.killed_run()
        (self.game / "data" / "probe_d15.pack").write_bytes(b"someone else's build")
        self.lock.write_text("another job")
        line = flyer_run.recover(self.out, self.game, lambda: None, self.lock)
        self.assertNotIn("removed probe_d15.pack", line)
        self.assertNotIn("lock", line)
        self.assertEqual(self.lock.read_text(), "another job")
        self.assertTrue((self.game / "data" / "probe_d15.pack").exists())

    def test_no_recovery_while_the_game_runs(self):
        self.killed_run()
        with self.assertRaises(SystemExit):
            self.one(game_running=lambda: "Warhammer3.exe is already running (pid 5)")
        self.assertTrue((self.out / "inflight.json").exists())
        self.assertEqual((self.game / "used_mods.txt").read_text(), "mod probe_d15.pack;\n")

    def test_busy_refused_nothing_touched(self):
        code, res = self.one(busy=lambda own_pids=(): "Warhammer3.exe is already running")
        self.assertEqual(code, 6)
        self.assertIn("busy", res["refused"])
        self.assertFalse((self.game / "data" / "probe_d15.pack").exists())
        self.assertEqual((self.game / "reflect_probe.txt").read_text(), "stale\n")
        self.assertIn("NOT RUN", (self.out / "LOG.md").read_text("utf-8"))

    def test_pack_already_deployed_refused(self):
        (self.game / "data" / "probe_d15.pack").write_bytes(b"theirs")
        code, res = self.one()
        self.assertEqual(code, 6)
        self.assertEqual((self.game / "data" / "probe_d15.pack").read_bytes(), b"theirs")

    def test_a_run(self):
        code, res = self.one()
        self.assertEqual(code, 0, res)
        run = self.out / "r1"
        self.assertFalse((self.game / "data" / "probe_d15.pack").exists())
        self.assertEqual((run / "flyer_dive.txt").read_text(), "BATTLE this run\n")
        self.assertEqual((run / "full_flyer_dive.txt").read_text(), "BATTLE an older run\nBATTLE this run\n")
        self.assertEqual((run / "reflect_probe.txt").read_text(), "BATTLE x on: buffer 0\n")
        self.assertIn("deleted stale reflect_probe.txt", res["pre"])
        self.assertIn("reflect_probe.txt", res["reports"])
        self.assertTrue((run / "reflect_probe_report.txt").is_file())
        self.assertEqual((res["verdict"], res["standard"]), ("PASS", True))
        self.assertTrue(res["used_mods_unchanged"] and res["data_folder_unchanged"])
        self.assertEqual(json.loads((run / "run.json").read_text("utf-8"))["deployed"][0]["name"], "probe_d15.pack")
        self.assertIn("**r1** rc=0 verdict=PASS standard", (self.out / "LOG.md").read_text("utf-8"))
        # a finished label is not run again
        (self.game / "flyer_dive.txt").write_text("")
        code2, res2 = self.one()
        self.assertEqual((code2, res2["started"]), (0, res["started"]))
        self.assertEqual((self.game / "flyer_dive.txt").read_text(), "")

    def test_output_inside_the_repository_refused(self):
        # a stand-in repository, so that a broken check writes into the temp folder, never the real tree
        repo = Path(self.td.name) / "repo"
        with mock.patch.object(flyer_run, "REPO", repo), self.assertRaises(SystemExit):
            flyer_run.run_one("x", [], [], out_root=repo / "mod" / "runs", busy=lambda own_pids=(): None,
                              game_root=self.game, driver=self.driver, lock=self.lock)
        self.assertFalse((repo / "mod" / "runs").exists())
        self.assertTrue(flyer_run.inside_repo(TOOLS_DIR / "runs"))

    def test_list(self):
        jobs = Path(self.td.name) / "jobs.txt"
        jobs.write_text(f"# a comment\nA --deploy {self.pack}=probe_d15.pack -- --flyers a,b --cmd \"x=1\"\n\n"
                        f"B -- --flyers c\nC -- --flyers d\n", encoding="utf-8")
        seen = []

        def one(label, deploys, driver_args, out_root, pin_cfg):
            seen.append((label, [n for _s, n in deploys], driver_args))
            return (6 if label == "B" else 0), {}
        self.assertEqual(flyer_run.run_list(jobs, out_root=self.out, one=one), 6)
        self.assertEqual(seen, [("A", ["probe_d15.pack"], ["--flyers", "a,b", "--cmd", "x=1"]),
                                ("B", [], ["--flyers", "c"])])


if __name__ == "__main__":
    unittest.main()
