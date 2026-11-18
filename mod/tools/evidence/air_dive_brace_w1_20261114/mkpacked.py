"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 2): packed job lists -- several flyer types per battle.
Each battle has len(OFFSETS) lanes; each flyer type gets three lanes (spear / halberd / militia) and the
target rotation R1..R3 is the same as batch E (R1 spear/halb/militia, R2 militia/spear/halb, R3 halb/militia/spear).
Types are spread so that no type keeps the same ground across the three rotations.

usage: python -I mkpacked.py <prefix> <pack> <types-per-battle> <type>... > jobs.txt
"""
import sys

OFFSETS = (-430, -340, -250, -160, -70, 160, 250, 340, 430)
TGT = {"spear": "wh_main_emp_inf_spearmen_1", "halb": "wh_main_emp_inf_halberdiers",
       "militia": "wh_dlc04_emp_inf_free_company_militia_0"}
ROT = (("spear", "halb", "militia"), ("militia", "spear", "halb"), ("halb", "militia", "spear"))


def main(prefix, pack, per, types):
    per = int(per)
    assert 1 <= per <= len(OFFSETS) // 3
    n = per * 3
    print(f"# AIR-DIVE-BRACE-W1 packed jobs {prefix}: {per} flyer types x 3 targets per battle, offsets {OFFSETS[:n]}, 1x")
    groups = [types[i:i + per] for i in range(0, len(types), per)]
    for r, rot in enumerate(ROT, 1):
        for g, grp in enumerate(groups, 1):
            lanes = []                                  # (offset index, flyer key, target)
            for k, key in enumerate(grp):
                for j, t in enumerate(rot):
                    lanes.append(((k * 3 + j + (r - 1) * 3) % n, key, TGT[t]))
            lanes.sort()
            offs = ",".join(str(OFFSETS[i]) for i, _, _ in lanes)
            print(f"{prefix}{r}_g{g} {pack} charge {','.join(k for _, k, _ in lanes)} --lane-offsets={offs} "
                  f"--targets={','.join(t for _, _, t in lanes)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
