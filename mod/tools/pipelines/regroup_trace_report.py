#!/usr/bin/env python3
"""Who gave a model the charge command, and what was its unit doing? [D23-RUNS-1120, TEST-ONLY]

Reads the recorder's file (``pin_probe.txt``, format in the header of ``pin_on_hit_probe.lua``), recorded with
``track 1;calls 1`` and a pack built with ``build_pin_on_hit_probe.py --record --regroup-trace`` (caves in
``regroup_trace_asm.py``), and for the last battle in it joins, for every charge command a per-model task handler
gave (G kind 6 returning to 0x142f7f71c / 0x142f8ffda):

* the task line written just before it in the handler (G kind 7 / 8, same model, same battle tick): the task's vtable,
  serial, flags +0x74, done +0x80, due time +0x84, target +0x58, +0x18, +0x68;
* the newest creation of a task on that model before it (G kind 9): who created it (its return address) and the
  parameters' target (+0x18; equal to the task's +0x58 when it is the same task);
* the unit's order at that sample (the O line): vtable, serial, +0x3c, queue length;
* whether a landing request for that model from 0x143050dc1 follows in the same battle tick (the pull-back chain,
  docs/HISTORY.md D23-RUNS-1120).

Then a census over (airborne, handler, creator, order vtable, order +0x3c, task flags). That census is what should
separate the engine's own re-attack of airborne models from an attack order the player gave.

Every way of having no measurement is a problem (exit 1): no BATTLE line with ``track=1`` and ``calls=1``, no
``CALLS on`` line or a FAIL line, a Q line without its O line, an O line whose memory reading disagrees with the
script's ``is_idle`` (the order-queue offsets are then wrong) or no readable ``is_idle`` at all, a task / creator
line without its fields, a GC line without the task counters, a handler's charge command without its task line
(then rbx was not the task at the cave), a task whose vtable is not 0x143ad9690, and no joined charge command at all.

usage: python -P tools/pipelines/regroup_trace_report.py <pin_probe.txt>
"""
import collections
import struct
import sys
from pathlib import Path

TASK_VT = 0x143AD9690
HANDLER_RET = {0x142F7F71C: 7, 0x142F8FFDA: 8}         # the stub's return address -> the task line's kind
LAND_FROM_TARGET = 0x143050DC1
TASK_KEYS = ("t18", "t58", "t68", "f74", "f80", "t84", "sn")
MK_KEYS = tuple(f"p{8 * i:02x}" for i in range(7))
GC_KEYS = ("land", "cancel", "target", "stay", "order", "stub", "task1", "task2", "mktask", "lost")


def last_battle(text):
    """the lines of the last battle: from after the END before its BATTLE line to its END (or the file's end)"""
    lines = text.splitlines()
    b = max((i for i, ln in enumerate(lines) if ln.startswith("BATTLE ")), default=None)
    if b is None:
        return None
    start = max((i + 1 for i, ln in enumerate(lines[:b]) if ln == "END"), default=0)
    end = next((i for i in range(b, len(lines)) if lines[i] == "END"), len(lines))
    return [(i + 1, lines[i]) for i in range(start, end)]


def _kv(tokens):
    return dict(t.split("=", 1) for t in tokens if "=" in t)


def parse(text):
    """(record, problems)"""
    rows = last_battle(text)
    if rows is None:
        return None, ["no BATTLE line"]
    rec = dict(battle=None, calls_on=False, fails=[], q=set(), o={}, g=[], gc=None)
    for no, ln in rows:
        f = ln.split(" ")
        t = f[0]
        if t == "BATTLE":
            rec["battle"] = ln
        elif ln.startswith("CALLS on"):
            rec["calls_on"] = True
        elif t == "FAIL":
            rec["fails"].append(f"line {no}: {ln}")
        elif t == "Q" and len(f) > 4 and f[4] != "FAIL":
            rec["q"].add((int(f[1]), f[3]))
        elif t == "O":
            rec["o"][(int(f[1]), f[3])] = dict(_kv(f[4:]), line=no)
        elif t == "G" and len(f) >= 13:
            rec["g"].append(dict(no=no, ms=int(f[1]), tick=f[2], kind=int(f[3]), uid=f[4], ent=f[5],
                                 ret=int(f[6], 16), rdx=int(f[7], 16), aux=int(f[8], 16), air=int(f[9], 16),
                                 state=f[10], stay=f[11], rcx=f[12], ext=_kv(f[13:])))
        elif t == "GC":
            rec["gc"] = _kv(f[2:])
    problems = []
    b = rec["battle"] or ""
    if " track=1" not in b or " calls=1" not in b:
        problems.append(f"the battle was not recorded with track 1 and calls 1: {b!r}")
    if not rec["calls_on"]:
        problems.append("no 'CALLS on' line: the call tracer was not installed")
    problems += rec["fails"]
    return rec, problems


def _f32(hex8):
    return struct.unpack("<f", struct.pack("<I", int(hex8, 16)))[0]


def judge(rec):
    """(joined charge commands, census, problems)"""
    problems = []
    if not rec["q"]:
        problems.append("no Q lines")
    missing_o = sorted(k for k in rec["q"] if k not in rec["o"])
    if missing_o:
        problems.append(f"{len(missing_o)} Q lines without an O line, first {missing_o[0]}")
    checked = bad = 0
    for k, o in rec["o"].items():
        if o.get("idle") not in ("0", "1"):
            continue
        checked += 1
        mem_idle = o.get("n") == "0" and o.get("busy") == "00"
        if mem_idle != (o["idle"] == "1"):
            bad += 1
    if rec["o"] and not checked:
        problems.append("no O line carries the script's is_idle: the order-queue offsets are unchecked")
    if bad:
        problems.append(f"{bad} of {checked} O lines disagree with the script's is_idle: the order-queue offsets "
                        "are wrong")
    gc = rec["gc"]
    if gc is None or any(k not in gc for k in GC_KEYS):
        problems.append(f"no GC line with the counters {', '.join(GC_KEYS)}: {gc}")
    for g in rec["g"]:
        want = TASK_KEYS if g["kind"] in (7, 8) else MK_KEYS if g["kind"] == 9 else ()
        lack = [k for k in want if k not in g["ext"]]
        if lack:
            problems.append(f"line {g['no']}: G kind {g['kind']} without {', '.join(lack)}")
    joined = []
    g = rec["g"]
    for i, s in enumerate(g):
        if s["kind"] != 6 or s["ret"] not in HANDLER_RET:
            continue
        want = HANDLER_RET[s["ret"]]
        # same model, same battle tick (the caves' own tick: a drain may fall between the two entries)
        task = next((t for t in reversed(g[max(0, i - 50):i]) if t["kind"] == want and t["ent"] == s["ent"]
                     and t["tick"] == s["tick"]), None)
        if task is None:
            problems.append(f"line {s['no']}: a charge command from the handler (ret {s['ret']:#x}) without its task "
                            f"line (kind {want}) for model {s['ent']}")
            continue
        if task["aux"] != TASK_VT:
            problems.append(f"line {task['no']}: task vtable {task['aux']:#x}, want {TASK_VT:#x}")
        mk = next((c for c in reversed(g[:i]) if c["kind"] == 9 and c["ent"] == s["ent"]), None)
        lands = any(x["kind"] == 1 and x["ret"] == LAND_FROM_TARGET and x["ent"] == s["ent"] and x["tick"] == s["tick"]
                    for x in g[i + 1:i + 40])
        o = rec["o"].get((s["ms"], s["uid"]), {})
        e = task["ext"]
        joined.append(dict(
            ms=s["ms"], line=s["no"], task_line=task["no"], uid=s["uid"], ent=s["ent"], air=s["air"], handler=want,
            task_sn=e.get("sn"), f74=e.get("f74"), f80=e.get("f80"),
            due=round(_f32(e["t84"]), 2) if "t84" in e else None, t58=e.get("t58"), t18=e.get("t18"),
            t68=e.get("t68"), creator=f"{mk['ret']:#x}" if mk else "-", creator_ms=mk["ms"] if mk else None,
            creator_same_target=(mk["ext"].get("p18") == e.get("t58")) if mk else None,
            order_vt=o.get("vt", "?"), order_sn=o.get("sn", "?"), order_a3c=o.get("a3c", "?"), order_n=o.get("n", "?"),
            lands=lands))
    if not joined:
        problems.append("no charge command from a task handler with its task line: nothing to compare")
    census = collections.Counter((j["air"], j["handler"], j["creator"], j["order_vt"], j["order_a3c"], j["f74"],
                                  j["lands"]) for j in joined)
    return joined, census, problems


def render(joined, census, problems, gc):
    out = ["== charge commands from the task handlers (ms line uid model air handler | task sn f74 f80 due t58 | "
           "creator @ms same-target | order vt sn a3c n | lands)"]
    for j in joined:
        out.append(f"{j['ms']:>6} L{j['line']} {j['uid']} {j['ent']} air={j['air']} h{j['handler']} | "
                   f"sn={j['task_sn']} f74={j['f74']} f80={j['f80']} due={j['due']} t58={j['t58']} | "
                   f"{j['creator']} @{j['creator_ms']} {j['creator_same_target']} | "
                   f"{j['order_vt']} {j['order_sn']} {j['order_a3c']} n={j['order_n']} | lands={int(j['lands'])}")
    out.append("== census (air handler creator order_vt order_a3c task_f74 lands): n")
    for k, n in sorted(census.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        out.append(f"   {' '.join(str(x) for x in k)}: {n}")
    out.append(f"== GC {gc}")
    out += [f"PROBLEM {p}" for p in problems] or ["PASS"]
    return "\n".join(out)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(__doc__)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"PROBLEM no record at {path}")
        return 1
    rec, problems = parse(path.read_text(encoding="utf-8", errors="replace"))
    if rec is None:
        print("\n".join(f"PROBLEM {p}" for p in problems))
        return 1
    joined, census, more = judge(rec)
    problems += more
    print(render(joined, census, problems, rec["gc"]))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
