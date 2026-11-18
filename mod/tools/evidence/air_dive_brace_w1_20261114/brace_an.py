"""TEST-ONLY (AIR-DIVE-BRACE-W1): read runs/<label>/ld_brace_probe_slice.txt and classify every lane.

Per lane (single-model flyers; multi-model units are reported with the lead model, marked multi):
  touchdown = first T sample with +0x104 2 -> 0; early stop = within STOP_WINDOW s of touchdown the
  planar speed falls from > 5 m/s to < 1 m/s within 0.5 s.
For each early stop it prints the brake tick +-4 samples (state, slot, speed, +0x1c8, goal, order
vtable, order target, +0xab0), the N neighbour summary, every A / R / F event within 1.5 s, and which
dwords of the D dump changed at the brake tick that had been constant over the 5 ticks before it.

usage: python -I brace_an.py <label>... [--detail]    (labels under runs/)
       python -I brace_an.py --table <label>...       (one line per lane)
"""
import json
import math
import struct
import sys
from collections import defaultdict
from pathlib import Path

H = Path(__file__).resolve().parent
STOP_WINDOW = 8.0
CHARGE_VT, MELEE_VT = "43ADE800", "43ADE470"
TYPES = {"wh_main_emp_inf_spearmen_1": "spear", "wh_main_emp_inf_halberdiers": "halb",
         "wh_dlc04_emp_inf_free_company_militia_0": "militia", "wh_main_emp_inf_swordsmen": "sword"}


def job_targets():
    out = {}
    for f in H.glob("jobs_*.txt"):
        for line in f.read_text("utf-8").splitlines():
            q = line.split()
            if not q or q[0].startswith("#"):
                continue
            for a in q[4:]:
                if a.startswith("--targets="):
                    out[q[0]] = a.split("=", 1)[1].split(",")
    return out


JOBS = job_targets()
BAD_DUMPS = {}


def load(lab):
    d = H / "runs" / lab
    v = json.loads((d / "verdict.json").read_text("utf-8")) if (d / "verdict.json").exists() else {"lanes": []}
    T, N, D, EV = defaultdict(list), defaultdict(dict), defaultdict(dict), []
    for raw in (d / "ld_brace_probe_slice.txt").read_text("utf-8", errors="replace").splitlines():
        p = raw.split()
        if not p:
            continue
        k = p[0]
        if k == "T" and "|" in p:
            i = p.index("|")
            a, b = p[:i], p[i + 1:]
            T[a[2]].append(dict(t=int(a[1]) / 1000, ent=a[3], st=int(a[4]), slot=int(a[5]) & 0xffff, tick=int(a[6]),
                                vx=float(a[7]), vz=float(a[8]), fm=int(a[9]), lay=int(a[10]), x=float(a[11]), z=float(a[12]),
                                mst=int(a[13]), mslot=int(a[14]), s1c8=float(b[0]), s238=float(b[1]), s23c=float(b[2]),
                                gx=float(b[3]), gz=float(b[4]), g7x=float(b[5]), g7z=float(b[6]), vt=b[7], otgt=b[8],
                                ab0=float(b[9]), r324=int(b[10]), mass=float(b[11]), bc=float(b[12]), f68=int(b[13]), f6c=b[14]))
        elif k == "N":
            N[p[2]][int(p[1])] = dict(n10=int(p[3]), n6=int(p[4]), nfront=int(p[5]), braced=int(p[6]), immov=int(p[7]),
                                      bcs=float(p[8]), bcm=float(p[9]), react=int(p[10]), nearest=float(p[11]),
                                      tsp=float(p[12]), fbr=int(p[13]), frc=int(p[14]))
        elif k == "D":
            try:
                D[p[2]][int(p[1])] = bytes.fromhex(p[3])
            except (ValueError, IndexError):   # a dump line cut short in the log: skip it, keep the run
                BAD_DUMPS[lab] = BAD_DUMPS.get(lab, 0) + 1
        elif k in ("A", "R", "F", "M", "O", "G", "K"):
            EV.append((int(p[1]) / 1000, k, p))
    return v, T, N, D, EV


def speed(s):
    return math.hypot(s["vx"], s["vz"])


def lanes(lab):
    v, T, N, D, EV = load(lab)
    out = []
    for ln in v["lanes"]:
        uid = ln["flyer_uid"]
        s = T.get(uid, [])
        rec = dict(lab=lab, lane=ln["lane"], uid=uid, flyer=ln["flyer"], target=TYPES.get((JOBS.get(lab) or ["?"] * 9)[ln["lane"] - 1], "?"),
                   men=ln.get("flyer_men"), touchdown=None, stop=None, travel=None, s=s, N=N.get(uid, {}), D=D.get(uid, {}),
                   EV=[e for e in EV if uid in e[2][2:7]], verdict_travel=ln.get("travel_after_touchdown_m"))
        td = next((i for i in range(1, len(s)) if s[i - 1]["lay"] == 2 and s[i]["lay"] == 0), None)
        if td is not None:
            rec["touchdown"] = td
            for i in range(td + 1, len(s) - 4):
                if s[i]["t"] > s[td]["t"] + STOP_WINDOW:
                    break
                if speed(s[i - 1]) > 5 and any(speed(s[j]) < 1 for j in range(i, min(i + 5, len(s)))) \
                        and speed(s[i]) < speed(s[i - 1]) - 1.0:
                    rec["stop"] = i
                    rec["travel"] = math.hypot(s[i + 3]["x"] - s[td]["x"], s[i + 3]["z"] - s[td]["z"])
                    # [round 2] farthest the flyer got from its touchdown point before this stop: a flyer that
                    # slid out and came back stops near its touchdown point too (QS1_dragon lane 2: 50 m out,
                    # back to 13 m), and that is not an early stop
                    rec["maxd"] = max(math.hypot(q["x"] - s[td]["x"], q["z"] - s[td]["z"]) for q in s[td:i + 4])
                    break
        out.append(rec)
    return out


def changed_dwords(D, ms_list, i):
    """dword offsets that were constant over ms_list[i-5:i] and differ at ms_list[i]."""
    if i < 5 or any(m not in D for m in ms_list[i - 5:i + 1]):
        return []
    base = D[ms_list[i - 1]]
    stable = [o for o in range(0, len(base) - 3, 4)
              if all(D[ms_list[j]][o:o + 4] == base[o:o + 4] for j in range(i - 5, i))]
    now = D[ms_list[i]]
    res = []
    for o in stable:
        if now[o:o + 4] != base[o:o + 4]:
            a, b = struct.unpack_from("<I", base, o)[0], struct.unpack_from("<I", now, o)[0]
            fa, fb = struct.unpack_from("<f", base, o)[0], struct.unpack_from("<f", now, o)[0]
            res.append(f"+0x{o:x}: {a:08x}->{b:08x} ({fa:.3g}->{fb:.3g})")
    return res


def detail(rec):
    s, i = rec["s"], rec["stop"]
    td = rec["touchdown"]
    print(f"== {rec['lab']} lane {rec['lane']} {rec['flyer']} -> {rec['target']}  touchdown {s[td]['t']:.1f}s"
          f"  brake {s[i]['t']:.1f}s (+{s[i]['t'] - s[td]['t']:.1f})  travel {rec['travel']:.1f} m")
    for j in range(max(td - 1, i - 6), min(len(s), i + 8)):
        r = s[j]
        ms = int(round(r["t"] * 1000))
        n = rec["N"].get(ms)
        gd = math.hypot(r["gx"] - r["x"], r["gz"] - r["z"])
        g7 = math.hypot(r["g7x"] - r["x"], r["g7z"] - r["z"])
        nb = (f" N n6 {n['n6']} front {n['nfront']} braced {n['braced']}/{n['n10']} immov {n['immov']} bcmax {n['bcm']:.1f}"
              f" react {n['react']} near {n['nearest']:.1f}") if n else ""
        mark = "<-" if j == i else "  "
        vt = {CHARGE_VT: "CHG", MELEE_VT: "MEL"}.get(r["vt"], r["vt"])
        print(f" {mark}{r['t']:6.1f} st{r['st']:3d} sl{r['slot']:4d} tk{r['tick']:3d} v{speed(r):6.2f} 1c8 {r['s1c8']:6.2f} "
              f"238 {r['s238']:6.2f} 23c {r['s23c']:6.2f} fm{r['fm']} goal {gd:5.1f}m g7 {g7:5.1f}m order {vt} tgt {r['otgt']} "
              f"ab0 {r['ab0']:.0f} 324 {r['r324']}{nb}")
    t0 = s[i]["t"]
    for t, k, p in rec["EV"]:
        if t0 - 1.5 <= t <= t0 + 1.5:
            print(f"   {k} {' '.join(p[1:16])[:200]}")
    ms_list = sorted(rec["D"])
    msi = int(round(s[i]["t"] * 1000))
    if msi in rec["D"]:
        k = ms_list.index(msi)
        for row in changed_dwords(rec["D"], ms_list, k)[:60]:
            print("   D", row)


def cause(rec):
    s, i = rec["s"], rec["stop"]
    t0 = s[i]["t"]
    ent = s[i]["ent"]
    evs = [(t, k) for t, k, p in rec["EV"] if t0 - 1.0 <= t <= t0 + 0.05 and len(p) > 4 and p[4] == ent]
    if any(k == "M" for t, k in evs):
        return "contact-engage"
    win = [r for r in s if t0 - 1.0 <= r["t"] <= t0]
    if any(k == "O" for t, k in evs) or any(r["vt"] == "43AED8C8" for r in win):
        return "re-order"
    if any(a["fm"] != 0 and b["fm"] == 0 and b["lay"] == 0 for a, b in zip(win, win[1:])):
        return "flight-ended"
    return f"other({s[i - 1]['vt']}->{s[i]['vt']} st {s[i - 1]['st']}->{s[i]['st']})"


def main(argv):
    table = "--table" in argv
    labs = [a for a in argv if not a.startswith("--")]
    for lab in labs:
        for rec in lanes(lab):
            s = rec["s"]
            if rec["touchdown"] is None:
                print(f"{lab:14s} lane {rec['lane']} {rec['target']:7s} no touchdown")
                continue
            if rec["stop"] is None:
                if table:
                    print(f"{lab:14s} lane {rec['lane']} {rec['target']:7s} men {rec['men']} no early stop "
                          f"(verdict travel {rec['verdict_travel']})")
                continue
            r0 = s[rec["stop"]]
            if table:
                early = "EARLY" if rec["travel"] < 15 and rec.get("maxd", 0) < 15 else "late "
                print(f"{lab:14s} lane {rec['lane']} {rec['target']:7s} men {rec['men']} STOP {early} +{r0['t'] - s[rec['touchdown']]['t']:.1f}s "
                      f"travel {rec['travel']:.1f} m st/slot {s[rec['stop'] - 1]['st']}/{s[rec['stop'] - 1]['slot']} "
                      f"cause {cause(rec)}")
            else:
                detail(rec)


if __name__ == "__main__":
    main(sys.argv[1:])
