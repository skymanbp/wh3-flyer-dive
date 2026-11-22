"""Target hit points lost in the 1, 2 and 3 s after FIRST CONTACT (impact is resolved at once; owner 2026-11-21) (the first tick the target's unary hp falls),
per lane, from each run's hp.txt ("H <ms> <lane> <target unary hp> <men>"). Same ruler for flyers and ground
cavalry. Usage: python contact_report.py <runs dir> <label prefix>... ; groups runs by label minus a _<n> suffix."""
import re
import statistics as st
import sys
from pathlib import Path

runs = Path(sys.argv[1])
out = {}
for prefix in sys.argv[2:]:
    for d in sorted(runs.glob(prefix + "*")):
        hp = d / "hp.txt"
        cmd = (d / "command.txt").read_text("utf-8", errors="replace") if (d / "command.txt").is_file() else ""
        m = re.search(r"--flyers (\S+)", cmd)
        if not hp.is_file() or not m:
            print("SKIP (no hp.txt or flyer list)", d.name)
            continue
        flyers = m.group(1).split(",")
        mt = re.search(r"--targets (\S+)", cmd)
        tg = mt.group(1).split(",") if mt else [""] * len(flyers)
        short = {"wh_main_emp_inf_swordsmen": "sword", "wh_main_emp_inf_spearmen_1": "spear", "wh_main_emp_inf_halberdiers": "halb", "": ""}
        rows = {}
        for line in hp.read_text("utf-8").splitlines():
            p = line.split()
            if len(p) >= 5 and p[0] == "H":
                rows.setdefault(int(p[2]), []).append((int(p[1]), float(p[3])))
        group = re.sub(r"_[a-z0-9]$", "", d.name)
        for lane, seq in rows.items():
            seq.sort()
            h0 = seq[0][1]
            hit = next((i for i, (_t, h) in enumerate(seq) if h < h0), None)
            if hit is None:
                out.setdefault((group, flyers[lane - 1] + ' @' + short.get(tg[lane - 1], tg[lane - 1])), []).append(None)
                continue
            t0, hb = seq[hit - 1] if hit else seq[0]

            def at(t):
                past = [h for tt, h in seq if tt <= t]
                return past[-1] if past else hb

            out.setdefault((group, flyers[lane - 1] + ' @' + short.get(tg[lane - 1], tg[lane - 1])), []).append(tuple(hb - at(t0 + w) for w in (1000, 2000, 3000)))
for (group, flyer), vals in sorted(out.items()):
    ok = [v for v in vals if v]
    if not ok:
        print(f"{group:16s} {flyer:48s} no contact in {len(vals)} run(s)")
        continue
    m = [st.mean(v[i] for v in ok) * 100 for i in range(3)]
    print(f"{group:16s} {flyer:48s} 1s {m[0]:5.1f}%  2s {m[1]:5.1f}%  3s {m[2]:5.1f}%"
          f"  runs {len(ok)}/{len(vals)}  3s each {[round(v[2] * 100, 1) for v in ok]}")
