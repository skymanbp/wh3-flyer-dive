"""air_dive_autotest: the battle xml and the verdict, offline. [AIR-DIVE-AUTOTEST 2026-11-10]

The live run needs the game; what can be checked without it is that the
battle definition names every lane, and that the judge never turns an empty
or partial record into a PASS (CLAUDE.md 判决不得退化).
/ 离线部分：战斗定义每条跑道齐全；空记录、缺一条跑道一律判失败。
"""
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import rolepath  # noqa: F401 -- because it puts the role directories on sys.path

import air_dive_autotest as adt


def _sample(t_ms, uid, x, z, y, spd, flying, melee, near, near_d, nx, nz):
    return (f"S {t_ms} {uid} {x:.2f} {y:.2f} {z:.2f} {spd:.2f} 0.0 "
            f"{flying} 1 1 {melee} 1 {near} {near_d:.2f} {nx:.2f} {nz:.2f} 0.0")


def _probe(lanes):
    """A recorder log: each flyer descends, touches down 10 m short, stops."""
    out = ["BATTLE 2026-11-10 00:00:00 variant=test tick_ms=100 gate_m=80"]
    for f_uid, t_uid, key in lanes:
        out.append(f"UNIT {f_uid} 1 {key} fly=1 men=1 class=x")
        out.append(f"UNIT {t_uid} 2 {adt.TARGET} fly=0 men=120 class=x")
    for f_uid, t_uid, _ in lanes:
        z = -60.0
        for k in range(40):
            flying = 1 if k < 25 else 0
            spd = 20.0 if k < 25 else 0.0
            if k < 25:
                z += 2.0
            out.append(_sample(1000 + k * 100, f_uid, 0.0, z, 5.0 if flying else 0.0,
                               spd, flying, 0 if k < 26 else 1, t_uid, abs(z), 0.0, 0.0))
    return "\n".join(out) + "\n"


def _hp(lanes, loss_at_touchdown=0.05):
    """[AIR-DIVE-W14] the driver's hp file: each target loses
    loss_at_touchdown right after the touchdown at 3.5 s (_probe: k=25)."""
    out = []
    for i in range(1, len(lanes) + 1):
        for k in range(0, 120):
            t_ms = 1000 + k * 100
            hp = 1.0 if t_ms <= 3500 else 1.0 - loss_at_touchdown
            out.append(f"H {t_ms} {i} {hp:.5f} {120 if hp == 1.0 else 114}")
    return "\n".join(out) + "\n"


def _status(lanes, done=True):
    st = ["real1 harness_loaded dist=250", "10 phase Deployed"]
    for i, (f_uid, t_uid, key) in enumerate(lanes, 1):
        st.append(f"20 lane {i} flyer={key} uid={f_uid} at=0,0 "
                  f"target={adt.TARGET} uid={t_uid} at=0,0")
        st.append(f"30 charge {i} ordered uid={f_uid} dist=250.0")
    if done:
        st.append("90 DONE")
    return st


LANES = [("101", "201", adt.FLYERS[0]), ("102", "202", adt.FLYERS[1]),
         ("103", "203", adt.FLYERS[2])]
N = len(LANES)


class BattleXml(unittest.TestCase):
    def test_every_lane_has_a_flyer_and_a_target(self):
        text = adt.battle_xml().decode("utf-16")
        for i, key in enumerate(adt.FLYERS, 1):
            self.assertIn(f'script_name="flyer_{i}"', text)
            self.assertIn(f'script_name="target_{i}"', text)
            self.assertIn(f'type="{key}"', text)
        self.assertIn(adt.MAP_NAME, text)
        # [test standard] no catchment area: the element is left out
        self.assertNotIn("catchment_area", text)

    def test_helper_pack_paths(self):
        paths = [p for p, _ in adt.helper_entries()]
        self.assertEqual(paths, [adt.XML_PACK_PATH, adt.DRIVER_PACK_PATH])
        self.assertNotIn("\\", adt.DRIVER_PACK_PATH)   # Lua paths: forward slashes


class Judge(unittest.TestCase):
    def test_complete_record_passes(self):
        res = adt.judge(_status(LANES), _probe(LANES), _hp(LANES), N)
        self.assertEqual(res["verdict"], "PASS", res["reasons"])
        self.assertEqual([ln["status"] for ln in res["lanes"]], ["OK"] * 3)
        for ln in res["lanes"]:
            self.assertGreater(ln["touchdown_speed_mps"], 0)
            self.assertTrue(ln["plough"])
            self.assertAlmostEqual(ln["target_hp_loss_1_5s"], 0.05)

    def test_no_hp_loss_is_not_a_plough(self):
        res = adt.judge(_status(LANES), _probe(LANES), _hp(LANES, 0.0), N)
        self.assertEqual(res["verdict"], "PASS", res["reasons"])
        self.assertEqual([ln["plough"] for ln in res["lanes"]], [False] * 3)

    def test_missing_hp_record_fails(self):
        res = adt.judge(_status(LANES), _probe(LANES), "", N)
        self.assertEqual(res["verdict"], "FAIL")

    def test_multi_model_flyer_drops_centre_numbers(self):
        probe = _probe(LANES).replace(
            f"UNIT 102 1 {adt.FLYERS[1]} fly=1 men=1",
            f"UNIT 102 1 {adt.FLYERS[1]} fly=1 men=8")
        res = adt.judge(_status(LANES), probe, _hp(LANES), N)
        lane = res["lanes"][1]
        self.assertEqual(lane["flyer_men"], 8)
        for k in adt.CENTRE_ONLY_FIELDS:
            self.assertIsNone(lane[k], k)
        self.assertTrue(lane["plough"])
        self.assertIsNotNone(res["lanes"][0]["depth_into_target_m"])

    def test_empty_record_fails(self):
        res = adt.judge(_status(LANES), "", _hp(LANES), N)
        self.assertEqual(res["verdict"], "FAIL")

    def test_missing_lane_in_record_fails(self):
        res = adt.judge(_status(LANES), _probe(LANES[:2]), _hp(LANES), N)
        self.assertEqual(res["verdict"], "FAIL")
        self.assertEqual(res["lanes"][2]["status"], "FAIL")

    def test_no_done_fails(self):
        res = adt.judge(_status(LANES, done=False), _probe(LANES), _hp(LANES), N)
        self.assertEqual(res["verdict"], "FAIL")

    def test_driver_fail_line_fails(self):
        st = _status(LANES) + ["40 FAIL charge 2 order: boom"]
        res = adt.judge(st, _probe(LANES), _hp(LANES), N)
        self.assertEqual(res["verdict"], "FAIL")


class PackOrder(unittest.TestCase):
    """[d3-1118] The pack-order experiment: used_mods.txt lists --pack-before packs ahead of the test
    pack and --pack-after packs after the helper pack, in the order given."""

    def test_used_mods_order(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saved = adt.USED_MODS
            adt.USED_MODS = Path(tmp) / "used_mods.txt"
            try:
                adt.write_startup("argv", "flyer_dive_takeoff.pack", adt.Restore(), ("probe_size.pack",),
                                  False, before_packs=("before_probe.pack",))
                lines = adt.USED_MODS.read_text("utf-8").splitlines()
            finally:
                adt.USED_MODS = saved
        self.assertEqual(lines[:4], ['mod "before_probe.pack";', 'mod "flyer_dive_takeoff.pack";',
                                     f'mod "{adt.HELPER_PACK}";', 'mod "probe_size.pack";'])
        self.assertTrue(lines[-1].startswith("game_startup_mode battle "))

class StandardSetup(unittest.TestCase):
    """[test standard, owner 2026-11-14] The one setup is the default, and every departure from it is named."""

    def args(self, **kw):
        import types
        base = dict(spacing=adt.STANDARD["lane_spacing_m"], offset=0.0, stagger=0.0, scenario="charge",
                    dist=250.0, window="normal", cmd=None)
        base.update(kw)
        return types.SimpleNamespace(**base)

    def test_the_numbers(self):
        self.assertEqual(adt.MAP_NAME, "terrain/battles/mp_crossroads_flat/")
        self.assertEqual(adt.CATCHMENT, "")
        self.assertEqual(adt.ENVIRONMENT, "weather\\battle\\wh_day_desert_02.environment_group")
        self.assertEqual(adt.standard_offsets(9), (-700.0, -525.0, -350.0, -175.0, 0.0, 175.0, 350.0, 525.0, 700.0))
        self.assertEqual(adt.standard_offsets(3), (-175.0, 0.0, 175.0))
        self.assertEqual(adt.standard_offsets(4), (-262.5, -87.5, 87.5, 262.5))
        with self.assertRaises(SystemExit):
            adt.standard_offsets(10)
        self.assertEqual(adt.resolve_lane_offsets(None, 3), (-175.0, 0.0, 175.0))
        self.assertEqual(len(set(adt.FLYERS)), len(adt.FLYERS))      # no duplicated (uphill) lane

    def test_deviations_are_named(self):
        self.assertEqual(adt.nonstandard(self.args(), adt.standard_offsets(4)), [])
        self.assertEqual(adt.nonstandard(self.args(stagger=20.0), adt.standard_offsets(4)), ["stagger 20 s"])
        self.assertEqual(adt.nonstandard(self.args(dist=300.0), adt.standard_offsets(4)), ["dist 300 m"])
        self.assertEqual(adt.nonstandard(self.args(window="behind"), adt.standard_offsets(4)), ["window behind"])
        # [ingame-1119] extra control lines are a deviation, named with the lines themselves
        self.assertEqual(adt.nonstandard(self.args(cmd="target_turn_2=90"), adt.standard_offsets(4)),
                         ["extra control lines target_turn_2=90"])
        self.assertEqual(adt.nonstandard(self.args(cmd="  "), adt.standard_offsets(4)), [])
        self.assertEqual(adt.nonstandard(self.args(), (-250.0, -160.0, 160.0, 80.0)),
                         ["lane offsets -250,-160,160,80"])
        self.assertEqual(adt.nonstandard(self.args(), ()), ["lanes by --spacing 175.0 / --offset 0.0"])
        self.assertEqual(adt.nonstandard(self.args(scenario="engage", dist=40.0), adt.standard_offsets(4)), [])
        saved = adt.MAP_NAME, adt.CATCHMENT
        adt.MAP_NAME, adt.CATCHMENT = "terrain/battles/ult_plains_infield_a/", "catchment_01"
        try:
            self.assertEqual(adt.nonstandard(self.args(), adt.standard_offsets(4)),
                             ["map terrain/battles/ult_plains_infield_a/", "catchment catchment_01"])
        finally:
            adt.MAP_NAME, adt.CATCHMENT = saved

    def test_targets_per_lane(self):
        text = adt.battle_xml(("a", "b"), ("t1", "t2")).decode("utf-16").replace("\r\n", "\n")
        self.assertIn('<unit script_name="target_1">\n\t\t\t\t<unit_type type="t1"/>', text)
        self.assertIn('<unit script_name="target_2">\n\t\t\t\t<unit_type type="t2"/>', text)
        with self.assertRaises(SystemExit):
            adt.battle_xml(("a", "b"), ("t1",))

    def test_driver_lua_sets_up_targets_and_says_which_setup(self):
        lua = adt.DRIVER_SOURCE.read_text("utf-8")
        for needle in ('status(fmt("lane %d target_setup skirmish_off=%s fire_at_will_off=%s melee_on=%s %s"',
                       'local r1, e1 = pcall(function() uc:change_behaviour_active("skirmish", false, false) end)',
                       'local r2, e2 = pcall(function() uc:change_behaviour_active("fire_at_will", false, false) end)',
                       'status(fmt("TT %d %d %.2f %.2f %.2f %s"',
                       'status(cfg.nonstandard and ("NONSTANDARD setup: " .. cfg.nonstandard) or "SETUP standard")'):
            self.assertIn(needle, lua)
        # the target setup runs on the targets (lane.target.uc), after the flyers' own
        at = lua.index("target_setup skirmish_off")
        self.assertIn("local uc = lane.target.uc", lua[at - 600:at])



class MctPageKeys(unittest.TestCase):
    """[ingame-1119] the driver's keys that open the real MCT's settings page: off by default, inert when off,
    and every MCT call sits inside a protected call (a missing MCT gives a status line, not an error)."""

    def setUp(self):
        text = (TOOLS / "pipelines" / "air_dive_autotest.lua").read_text("utf-8")
        self.text = text
        start = text.index("if cfg.mct_open_ms >= 0 then")
        self.block = text[start:text.index('if cfg.scenario == "cycle" then', start)]

    def test_off_by_default(self):
        self.assertIn("cfg.mct_open_ms, cfg.mct_close_ms, cfg.mct_set = -1, 15000, -1", self.text)
        self.assertEqual(self.text.count("if cfg.mct_open_ms >= 0 then"), 1)
        self.assertEqual(self.block.count("if cfg.mct_set >= 0 then"), 1)
        self.assertIn("cfg.mct_settings_ms = 6000", self.text)

    def test_calls_are_guarded(self):
        self.assertIn('if type(get_mct) ~= "function" then', self.block)
        self.assertIn('status("mct page: no MCT")', self.block)
        # MCT's own calls: each once, each after the opening of a protected call that reports its failure
        for call, fail in (("ui:open_frame()", "FAIL mct page: "), ("ui:set_selected_mod(", "FAIL mct page: "),
                           ("option:set_selected_setting(want)", "FAIL mct set: "),
                           ("mct:finalize()", "FAIL mct set: "), ("get_ui():close_frame()", "mct page closed ok="),
                           ("mod:get_default_settings_page())", "FAIL mct settings page: ")):
            self.assertEqual(self.block.count(call), 1, call)
            at = self.block.index(call)
            self.assertIn("pcall(function()", self.block[:at], call)
            self.assertIn(fail, self.block[at:], call)

    def test_keys_come_from_the_mod(self):
        self.assertIn('require("script/campaign/flyer_dive/data/breath_rows")', self.block)
        self.assertIn("rows.mct_mod", self.block)
        self.assertIn("rows.mct_option", self.block)


if __name__ == "__main__":
    unittest.main()
