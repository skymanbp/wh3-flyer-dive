"""[d15-1118 stage 5] The probe report's COST section (reflect_probe_report.cost_summary) on synthetic records.
[D51] The shipped cost module it observed (lib/dive_cost.lua) is removed with D15's cost, and so are its LuaJIT
cases; the report keeps reading old records (its stage-5 defects: tests/test_d15_stage5.py).
"""
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TESTS_DIR.parent
MOD_DIR = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path
import reflect_probe_report as rrep  # noqa: E402 -- because rolepath above puts pipelines/ on sys.path


def _x(kind, ms, tick, p, before, uid="1005", key="wh2_main_hef_mon_star_dragon", n=1, init=1):
    return f"{kind} {ms} {tick} {uid} {key} {n} {p:.6f} {p:.6f} {before:.6f} 1 {init}"


def _d(ms, verdict, vunit="F0000001", victim="A1000020", dmg=0, att_unit="F0000001"):
    h = lambda v: f"{v & 0xFFFFFFFF:08X}"  # noqa: E731 -- because a one-line formatter reads clearer inline
    return (f"D {ms} 1 0000000143061966 {victim} {vunit} {dmg} 5 1 {victim} 7 {ms} 00000069 {h(verdict)} "
            f"A1000020 A1000020 {h(9400)} {h(9100)} {h(9400)} {h(9100)} 00000002 00000001 {att_unit} 00000004")


BASE = ["BATTLE x on: buffer 0", "UNIT 1005 1 wh2_main_hef_mon_star_dragon obj=F0000001 men=1 flyer=1",
        "COST shipped: lib/dive_cost.lua, observed"]
PAY = "XPAY 33000 330 1007 wh_main_emp_inf_spearmen_1 F0000001 A1000020 0.9000 6B"


class CostReport(unittest.TestCase):
    def _summary(self, lines, keys=None):
        on, units, refl, dmg, hp, other = rrep.parse("\n".join(BASE + lines) + "\n")
        return rrep.cost_summary(units, dmg, other, keys)

    def test_call_with_effect(self):
        out, probs = self._summary([_d(33000, 1), PAY, _x("X", 33000, 330, 0.03, 0.9),
                                    "XA 33100 1005 1 0.870000 1", "XA 33200 1005 2 0.870000 1"],
                                   {"wh_main_emp_inf_spearmen_1"})
        self.assertEqual(probs, [])
        text = "\n".join(out)
        self.assertIn("COST wh2_main_hef_mon_star_dragon uid 1005: calls 1, p requested 0.0300, measured drop 0.0300",
                      text)
        self.assertIn("dv_cost entries: paid 1 (cos [0.9]), behind the arc 0 (cos []), no charge reflection 0", text)

    def test_call_without_effect_fails(self):
        _out, probs = self._summary([_d(33000, 1), PAY, _x("X", 33000, 330, 0.03, 0.9),
                                     "XA 33100 1005 1 0.900000 1", "XA 33200 1005 2 0.900000 1"])
        self.assertTrue(any("no health change" in p for p in probs), probs)

    def test_verdicts_without_call_fail(self):
        _out, probs = self._summary([_d(33000, 1)])
        self.assertTrue(any("verdicts but no cost line" in p for p in probs), probs)

    def test_a_contact_behind_the_arc_is_not_a_missing_call(self):
        _out, probs = self._summary([_d(33000, 1), PAY.replace("XPAY", "XARC").replace("0.9000", "-0.5000")])
        self.assertEqual(probs, [])

    def test_ordinary_damage_is_subtracted(self):
        out, probs = self._summary([_d(33000, 1), PAY, _x("X", 33000, 330, 0.03, 0.9), _d(33050, 0, dmg=94),
                                    "XA 33100 1005 1 0.860000 1"])
        self.assertEqual(probs, [])
        self.assertIn("ordinary damage in the windows 94 (0.0100 of the unit), attributable 0.0300",
                      "\n".join(out))

    def test_cross_checks(self):
        # the cave paid a soldier the game data says lacks charge reflection, or skipped one that has it
        _out, probs = self._summary([PAY, _x("X", 33000, 330, 0.03, 0.9), "XA 33100 1005 1 0.870000 1"], set())
        self.assertTrue(any("XPAY on wh_main_emp_inf_spearmen_1, which the game data says lacks" in p for p in probs),
                        probs)
        _out, probs = self._summary(["XNOATTR 33000 330 1007 wh_main_emp_inf_spearmen_1 F0000001 A1000020"],
                                    {"wh_main_emp_inf_spearmen_1"})
        self.assertTrue(any("XNOATTR on wh_main_emp_inf_spearmen_1, which the game data says has" in p
                            for p in probs), probs)
        # paying entries the calls do not account for
        _out, probs = self._summary([PAY, PAY, _x("X", 33000, 330, 0.03, 0.9), "XA 33100 1005 1 0.870000 1"])
        self.assertTrue(any("2 paying entries but calls for 1 models" in p for p in probs), probs)

    def test_errors_fail(self):
        _out, probs = self._summary([_d(33000, 1), "XERR 33000 330 DEAD0001 no unit object: x"])
        self.assertTrue(any("XERR" in p for p in probs), probs)


if __name__ == "__main__":
    unittest.main()
