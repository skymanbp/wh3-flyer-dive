"""TEST-ONLY (AIR-DIVE-BRACE-W1 round 2): job lists on the chosen flat map.
  packed: <per> flyer types x 3 targets per battle, lanes at --offsets (one per lane), all charges at once
          (--stagger=0), no per-soldier reader unless --entity-read is given
  single: one type x 3 targets per battle at the first three --offsets, 20 s apart (the old layout)
Each type meets spear / halberd / militia once per rotation; rotations R1..R3 as batch E. Types are moved to
other ground across the rotations.
usage: python -I mkjobs.py <mode> <prefix> <pack> <per> --offsets=a,b,... [--rotations=1,2,3] [--extra="..."] <type>...
"""
import sys
from pathlib import Path

SHORT = {}
for _line in (Path(__file__).resolve().parent / "jobs_e.txt").read_text("utf-8").splitlines():
    _q = _line.split()
    if _q and not _q[0].startswith("#"):
        SHORT[_q[3].split(",")[0]] = _q[0].split("_", 1)[1]

TGT = {"spear": "wh_main_emp_inf_spearmen_1", "halb": "wh_main_emp_inf_halberdiers",
       "militia": "wh_dlc04_emp_inf_free_company_militia_0"}
ROT = {1: ("spear", "halb", "militia"), 2: ("militia", "spear", "halb"), 3: ("halb", "militia", "spear")}


def main(argv):
    opts = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    mode, prefix, pack, per, types = pos[0], pos[1], pos[2], int(pos[3]), pos[4:]
    offsets = [float(x) for x in opts["--offsets"].split(",")]
    rots = [int(x) for x in opts.get("--rotations", "1,2,3").split(",")]
    extra = opts.get("--extra", "")
    if mode == "single":
        per = 1
    n = per * 3
    if len(offsets) < n:
        raise SystemExit(f"need {n} offsets, got {len(offsets)}")
    groups = [types[i:i + per] for i in range(0, len(types), per)]
    print(f"# AIR-DIVE-BRACE-W1 {mode} jobs {prefix}: {per} type(s) x 3 targets per battle, offsets {offsets[:n]}, "
          f"extra {extra!r}, 1x")
    for r in rots:
        rot = ROT[r]
        for g, grp in enumerate(groups, 1):
            lanes = []
            for k, key in enumerate(grp):
                for j, t in enumerate(rot):
                    lanes.append(((k * 3 + j + (r - 1) * 3) % n, key, TGT[t]))
            lanes.sort()
            offs = ",".join(f"{offsets[i]:g}" for i, _, _ in lanes)
            label = f"{prefix}{r}_g{g}" if mode == "packed" else f"{prefix}{r}_{SHORT[grp[0]]}"
            # all charges at once; the per-soldier reader stays on: its pack is what loads memreader Plus
            # for a test run (QP1: without it the caves never installed)
            stag = "--stagger=0" if mode == "packed" else ""
            print(f"{label} {pack} charge {','.join(k for _, k, _ in lanes)} --lane-offsets={offs} "
                  f"--targets={','.join(t for _, _, t in lanes)} {stag} {extra.replace('--entity-read', '')}".rstrip())


if __name__ == "__main__":
    main(sys.argv[1:])
