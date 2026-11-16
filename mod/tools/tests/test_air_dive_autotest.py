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
        self.assertIn(adt.CATCHMENT, text)

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


if __name__ == "__main__":
    unittest.main()
