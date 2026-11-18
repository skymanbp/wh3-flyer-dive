"""pin_probe_report: per-model take-off delay after the last melee hit, judged against the window by body size.

Synthetic records in the recorder's own format (header of pipelines/pin_on_hit_probe.lua). The failure the tool
exists for is a model leaving EARLIER than its window; every way of having no measurement must also fail.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines"))
import pin_probe_report as rep

import air_dive_rules

LARGE = air_dive_rules.TAKEOFF_SIZE_CODES["large"]
WINDOW = air_dive_rules.TAKEOFF_PIN_WINDOWS["large"]

HEAD = ["BATTLE 2026-11-18 05:00:00 window=0 mode=1 table=4096 sample=100 entities=1",
        "UNIT 7 1 wh2_dlc10_def_mon_feral_manticore_0 obj=AAAA0000 flyer=1",
        "UNIT 9 2 wh_main_emp_inf_swordsmen obj=BBBB0000 flyer=0"]


def record(airborne_tick, hit_tick=1000, sized=True, head=None):
    lines = list(head or HEAD)
    if sized:
        lines.append(f"Z 100 7 E1:{LARGE}")
    lines.append("E 100 990 7 E1:0:1:0")
    if hit_tick is not None:
        lines.append(f"H 1000 {hit_tick} E1:{hit_tick}:1")
    lines.append("E 2000 1010 7 E1:0:2:30")
    lines.append(f"E 9000 {airborne_tick} 7 E1:2:3:0")
    return "\n".join(lines) + "\n"


class Judge(unittest.TestCase):
    def test_takeoff_after_window_and_engine_timer_passes(self):
        rows, problems = rep.judge(rep.parse(record(1000 + WINDOW + rep.ENGINE_TIMER_TICKS + 1)))
        self.assertEqual(problems, [])
        self.assertEqual(len(rows), 1)                      # only the flyer
        self.assertEqual(rows[0]["size"], "large")
        self.assertEqual(rows[0]["window"], WINDOW)
        self.assertEqual(rows[0]["delays"], [WINDOW + rep.ENGINE_TIMER_TICKS + 1])
        self.assertEqual(rows[0]["early"], 0)

    def test_takeoff_before_the_window_fails(self):
        rows, problems = rep.judge(rep.parse(record(1000 + WINDOW - 5)))
        self.assertEqual(rows[0]["early"], 1)
        self.assertTrue(any("earlier than its window" in p for p in problems), problems)

    def test_one_sampling_period_of_slack_only(self):
        # the record is sampled every 100 ms = 1 tick: one tick short of the window is not called early,
        # two ticks short is
        self.assertEqual(rep.judge(rep.parse(record(1000 + WINDOW - 1)))[0][0]["early"], 0)
        self.assertEqual(rep.judge(rep.parse(record(1000 + WINDOW - 2)))[0][0]["early"], 1)

    def test_never_hit_is_counted_not_judged(self):
        rows, problems = rep.judge(rep.parse(record(1005, hit_tick=None)))
        self.assertEqual(problems, [])
        self.assertEqual((rows[0]["takeoffs"], rows[0]["never_hit"], rows[0]["delays"]), (1, 1, []))

    def test_the_last_battle_of_the_file_is_read(self):
        text = record(1000 + WINDOW - 20) + record(1000 + WINDOW + 40)
        rows, problems = rep.judge(rep.parse(text))
        self.assertEqual(problems, [])
        self.assertEqual(rows[0]["delays"], [WINDOW + 40])


class NoMeasurement(unittest.TestCase):
    def test_empty_file(self):
        self.assertEqual(rep.judge(rep.parse("")), ([], ["no BATTLE line in the record"]))

    def test_recorded_without_entity_lines(self):
        head = [HEAD[0].replace("entities=1", "entities=0")] + HEAD[1:]
        text = "\n".join(head) + "\n"
        _rows, problems = rep.judge(rep.parse(text))
        self.assertTrue(any("entities 1" in p for p in problems), problems)
        self.assertTrue(any("no E line" in p for p in problems), problems)

    def test_old_header_without_the_keys(self):
        head = ["BATTLE 2026-11-18 02:42:16 window=0 mode=1 table=4096"] + HEAD[1:]
        _rows, problems = rep.judge(rep.parse("\n".join(head) + "\n"))
        self.assertTrue(any("entities 1" in p for p in problems), problems)

    def test_missing_size_line(self):
        _rows, problems = rep.judge(rep.parse(record(1100, sized=False)))
        self.assertTrue(any("no Z line" in p for p in problems), problems)

    def test_fail_line(self):
        _rows, problems = rep.judge(rep.parse(record(1100) + "FAIL tick something broke\n"))
        self.assertIn("FAIL tick something broke", problems)

    def test_main_exit_codes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            good, bad = Path(td) / "good.txt", Path(td) / "bad.txt"
            good.write_text(record(1000 + WINDOW + 31), encoding="utf-8")
            bad.write_text(record(1000 + WINDOW - 9), encoding="utf-8")
            self.assertEqual(rep.main([str(good), "--json"]), 0)
            self.assertEqual(rep.main([str(bad), "--json"]), 1)


if __name__ == "__main__":
    unittest.main()
