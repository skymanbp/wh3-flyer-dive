"""AIR-DIVE-W1: prove the shipped animpack changes nothing but slot 104.

For every bin in assets/air_dive/@ld_air_dive.animpack: same entry count and
order as the installed bin of the same path, the only differing cells are the
anim path of FLY_CHARGE_LAND (104) refs, and every clip any ref names exists
(installed anim packs, or our dive clips) -- except refs left exactly as
CA ships them, whose missing clips are CA's own and are only listed. Prints the counts; exits non-zero
on any violation. / 证明覆盖动画表只改了 104 号槽位的动作路径，且引用的动作都存在。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent.parent
sys.path.insert(0, str(TOOLS))
# role bootstrap first: the flat module names below resolve through it
import rolepath

import air_dive
import anim_table_bin
from animpack_codec import animpack_iter


def main():
    asset = TOOLS.parent / "assets" / "air_dive"
    manifest = json.loads((asset / "air_dive_manifest.json").read_text("utf-8"))
    ours = {f["pack_path"].replace(chr(92), "/").lower() for f in manifest["files"]}
    installed, read_clip = air_dive.load_installed()
    bad, inherited, refs, swapped, tables = [], set(), 0, 0, 0
    for ip, blob in animpack_iter((asset / air_dive.ANIMPACK_NAME).read_bytes()):
        tables += 1
        mine, van = anim_table_bin.parse(blob), anim_table_bin.parse(installed[ip])
        head = {k: v for k, v in mine.items() if k != "entries"}
        if head != {k: v for k, v in van.items() if k != "entries"}:
            bad.append(f"{ip}: header differs")
        if len(mine["entries"]) != len(van["entries"]):
            bad.append(f"{ip}: entry count differs")
            continue
        for a, b in zip(mine["entries"], van["entries"]):
            if {k: v for k, v in a.items() if k != "refs"} != \
                    {k: v for k, v in b.items() if k != "refs"}:
                bad.append(f"{ip}: slot {a['slot']} entry fields differ")
            for ra, rb in zip(a["refs"], b["refs"]):
                refs += 1
                if ra != rb:
                    if a["slot"] != air_dive.SLOT_LAND or ra[1:] != rb[1:]:
                        bad.append(f"{ip}: slot {a['slot']} ref {rb} -> {ra}")
                    swapped += 1
                clip = ra[0].lower()
                if clip in ours:
                    continue
                try:
                    read_clip(clip)
                except SystemExit:
                    if ra == rb:   # CA's own bin names it too: not ours
                        inherited.add(clip)
                    else:
                        bad.append(f"{ip}: names missing clip {clip}")
    print(f"tables {tables}, refs {refs}, slot-104 swaps {swapped}, problems {len(bad)}; "
          f"clips CA's own installed bins already name but no installed pack "
          f"carries (unchanged by us): {sorted(inherited)}")
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
