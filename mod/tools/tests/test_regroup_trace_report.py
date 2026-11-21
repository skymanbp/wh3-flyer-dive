"""regroup_trace_report: the charge commands of the per-model task handlers joined with their task, its creator and
the unit's order (D23-RUNS-1120).

Synthetic records in the recorder's own format (header of pipelines/pin_on_hit_probe.lua). Every way of having no
measurement must fail: an old recorder (no O lines, no task fields, no task counters), offsets the script's is_idle
contradicts, a handler's charge command without its task line, a foreign vtable, nothing to join.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines"))
import regroup_trace_report as rep

TASK = ("t18=0000000011112222 t58=00000000c0ffee00 t68=00000000a0a0a0a0 f74=00000000 f80=00000000 "
        "t84=41200000 sn=00001234")
MK = ("p00=0000000000000001 p08=0000000000000002 p10=0000000000000003 p18=00000000c0ffee00 p20=0000000000000005 "
      "p28=00000000a0a0a0a0 p30=0000000000000000")
G = "G {ms} {tick} {kind} 1004 B3AC45D0 {ret:016x} {rdx:016x} {aux:016x} 00000002 00000000 00000001 {rcx}"


def g(kind, ret, ms=48600, tick=486, aux=0, rdx=0, rcx="B3AC45D0", ext=""):
    return G.format(ms=ms, tick=tick, kind=kind, ret=ret, rdx=rdx, aux=aux, rcx=rcx) + (" " + ext if ext else "")


def record(o_idle="0", o_n="1", busy="00", task_ext=TASK, vt=rep.TASK_VT, with_task=True, with_o=True,
           calls=True, gc="land=3 cancel=0 target=1 stay=0 order=1 stub=1 task1=1 task2=0 mktask=1 lost=0"):
    lines = ["SITE ok", "CALLS on: caves installed" if calls else "",
             f"BATTLE 2026-11-20 18:00:00 window=0 mode=1 table=4096 sample=100 entities=1 track=1"
             + (" calls=1" if calls else ""),
             "UNIT 1004 1 wh2_dlc15_hef_inf_mistwalkers_griffon_knights_0 obj=AAAA0000 flyer=1",
             "Q 48600 486 1004 1.0 2.0 3.0 mv=0 melee=1 fly=0 men=4"]
    if with_o:
        lines.append(f"O 48600 486 1004 n={o_n} head=3 vt=00000001439193c0 sn=000004d2 a3c=00000002 busy={busy} "
                     f"idle={o_idle}")
    lines.append(g(9, 0x143123456, ms=44000, tick=440, rdx=0x7000, aux=0xC0FFEE00, ext=MK))
    if with_task:
        lines.append(g(7, 0x142F6B847, rdx=0x5000, aux=vt, rcx="77770000", ext=task_ext))
    lines += [g(6, 0x142F7F71C, rdx=0x7FF4DFE6FB10), g(5, 0x143123533), g(3, 0x14305B144),
              g(1, 0x143050DC1, rdx=0xB1756130), f"GC 50000 {gc}", "END"]
    return "\n".join(ln for ln in lines if ln) + "\n"


def judge(text):
    rec, problems = rep.parse(text)
    if rec is None:
        return [], None, problems
    joined, census, more = rep.judge(rec)
    return joined, census, problems + more


class Report(unittest.TestCase):
    def test_joins_task_creator_order_and_landing(self):
        joined, census, problems = judge(record())
        self.assertEqual(problems, [])
        self.assertEqual(len(joined), 1)
        j = joined[0]
        self.assertEqual((j["handler"], j["task_sn"], j["due"], j["t58"]), (7, "00001234", 10.0, "00000000c0ffee00"))
        self.assertEqual((j["creator"], j["creator_ms"], j["creator_same_target"]), ("0x143123456", 44000, True))
        self.assertEqual((j["order_vt"], j["order_sn"], j["order_a3c"], j["order_n"]),
                         ("00000001439193c0", "000004d2", "00000002", "1"))
        self.assertTrue(j["lands"])
        self.assertEqual(sum(census.values()), 1)

    def test_main_exit_codes(self):
        with tempfile.TemporaryDirectory() as td:
            good, bad = Path(td) / "good.txt", Path(td) / "bad.txt"
            good.write_text(record(), encoding="utf-8")
            bad.write_text(record(with_task=False), encoding="utf-8")
            self.assertEqual(rep.main([str(good)]), 0)
            self.assertEqual(rep.main([str(bad)]), 1)
            self.assertEqual(rep.main([str(Path(td) / "missing.txt")]), 1)

    def test_stub_without_task_line_fails(self):
        self.assertTrue(any("without its task line" in p for p in judge(record(with_task=False))[2]))

    def test_task_line_of_another_tick_does_not_count(self):
        text = record().replace(g(7, 0x142F6B847, rdx=0x5000, aux=rep.TASK_VT, rcx="77770000", ext=TASK),
                                g(7, 0x142F6B847, tick=485, rdx=0x5000, aux=rep.TASK_VT, rcx="77770000", ext=TASK))
        self.assertTrue(any("without its task line" in p for p in judge(text)[2]))

    def test_foreign_vtable_fails(self):
        self.assertTrue(any("task vtable" in p for p in judge(record(vt=0x143AD9588))[2]))

    def test_task_fields_missing_fails(self):
        self.assertTrue(any("without" in p and "sn" in p for p in judge(record(task_ext=TASK.rsplit(" ", 1)[0]))[2]))

    def test_missing_o_line_fails(self):
        self.assertTrue(any("without an O line" in p for p in judge(record(with_o=False))[2]))

    def test_is_idle_disagreement_fails(self):
        # memory says idle (no order, busy 0) but the script says not idle
        self.assertTrue(any("disagree" in p for p in judge(record(o_n="0", o_idle="0"))[2]))
        self.assertTrue(any("disagree" in p for p in judge(record(o_n="1", o_idle="1"))[2]))
        self.assertEqual(judge(record(o_n="0", o_idle="1"))[2], [])

    def test_unreadable_is_idle_fails(self):
        self.assertTrue(any("unchecked" in p for p in judge(record(o_idle="?"))[2]))

    def test_old_recorder_fails(self):
        problems = judge(record(calls=False, gc="land=3 cancel=0 target=1 stay=0 lost=0"))[2]
        self.assertTrue(any("calls 1" in p for p in problems), problems)
        self.assertTrue(any("CALLS on" in p for p in problems), problems)
        self.assertTrue(any("GC line" in p for p in problems), problems)

    def test_nothing_to_join_fails(self):
        text = record().replace(g(6, 0x142F7F71C, rdx=0x7FF4DFE6FB10), g(6, 0x142F00000, rdx=0x7FF4DFE6FB10))
        self.assertTrue(any("nothing to compare" in p for p in judge(text)[2]))

    def test_no_battle_fails(self):
        self.assertEqual(judge("UNIT 1 1 x obj=0 flyer=1\n")[2], ["no BATTLE line"])


if __name__ == "__main__":
    unittest.main()
