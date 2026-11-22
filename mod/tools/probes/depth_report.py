"""Penetration from flyer_dive_probe_report.txt: per (flyer, target), the touchdown anchor's advance into the target
(m, + = deeper), speed at touchdown and whether it stopped. Multi-model units are centroid values (marked *).
Usage: python depth_report.py <runs dir> <run>..."""
import sys
from pathlib import Path

MULTI = ("griffon_knights", "hippogryph_knights", "pegasus_knights", "longma_riders", "doom_knights", "furies")
SHORT = {"wh_main_emp_inf_swordsmen": "sword", "wh_main_emp_inf_spearmen_1": "spear", "wh_main_emp_inf_halberdiers": "halb"}
runs = Path(sys.argv[1])
for name in sys.argv[2:]:
    rep = runs / name / "flyer_dive_probe_report.txt"
    if not rep.is_file():
        print(name, "NO REPORT")
        continue
    print("==", name)
    for line in rep.read_text("utf-8").splitlines():
        p = [x.strip() for x in line.split("|")]
        if len(p) < 12 or p[0] != "FLY" or p[2] != "touchdown":
            continue
        key, v_in, travel, t_stop, adv, tgt = p[1], p[4], p[5], p[6], p[9], p[11]
        star = "*" if any(m in key for m in MULTI) else " "
        print(f"  {key:50s}{star} @{SHORT.get(tgt, tgt):6s} advance {adv:>7s} m  v_in {v_in:>6s}  travel {travel:>6s}  t_stop {t_stop}")
