"""AIR-DIVE-W1 measurement: codec proofs + root motion of every flight clip.

1. every installed battle bin decodes and re-encodes byte-identical
   (lib/anim_table_bin.py);
2. every clip a flying table names in slots 102-105 decodes to EOF
   (lib/anim_codec.py; v5 clips are counted, not read), and its v7
   re-encoding decodes back to the same values (translation 1e-6,
   quaternion 1e-4);
3. per clip, the animroot (bone 0) displacement first -> last frame and the
   descent window (frame 0 .. touchdown) -- the numbers the dive rule in
   pipelines/air_dive.py is derived from.
Writes flight_clips.json next to this script.
/ 实测：编解码往返证明与全部飞行槽位动作的根骨位移。
"""
import json
import struct
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent.parent
sys.path.insert(0, str(TOOLS))
# role bootstrap first: the flat module names below resolve through it
import rolepath

import air_dive
import anim_codec
import anim_table_bin

SLOTS = {102: "FLY_CHARGE_AIR_TO_AIR", 103: "FLY_CHARGE_AIR_TO_GROUND",
         104: "FLY_CHARGE_LAND", 105: "FLY_TAKEOFF"}


def _close(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return max(abs(x - y) for x, y in zip(a, b)) <= tol


def main():
    bins, read_clip = air_dive.load_installed()
    bin_ok = bin_refused = 0
    slot_of = {}
    for ip in sorted(bins):
        try:
            t = anim_table_bin.parse(bins[ip])
        except anim_table_bin.BinFormatError:
            bin_refused += 1
            continue
        if anim_table_bin.write(t) != bins[ip]:
            raise SystemExit(f"bin does not round-trip: {ip}")
        bin_ok += 1
        if not any(e["slot"] in (103, 104) for e in t["entries"]):
            continue
        for e in t["entries"]:
            if e["slot"] in SLOTS:
                for r in e["refs"]:
                    slot_of.setdefault(r[0].lower(), set()).add(SLOTS[e["slot"]])
    versions, clips = Counter(), []
    for path in sorted(slot_of):
        blob = read_clip(path)
        ver = struct.unpack_from("<I", blob, 0)[0]
        versions[ver] += 1
        rec = {"clip": path, "version": ver, "slots": sorted(slot_of[path])}
        if ver in (7, 8):
            c = anim_codec.decode(blob)
            back = anim_codec.decode(anim_codec.encode_v7(c))
            for f1, f2 in zip(c["frames"], back["frames"]):
                for (t1, q1), (t2, q2) in zip(f1, f2):
                    if not (_close(t1, t2, 1e-6) and _close(q1, q2, 1e-4)):
                        raise SystemExit(f"v7 re-encoding changed values: {path}")
            rec.update(duration_s=round(c["duration"], 3), fps=c["fps"],
                       frames=len(c["frames"]))
            track = air_dive._root_track(c)
            if track is not None:
                rec["animroot_delta_xyz"] = [round(b - a, 3) for a, b in
                                             zip(track[0], track[-1])]
                d, fwd, t = air_dive._descent(c)
                rec["descent"] = {"drop_m": round(d, 3), "forward_m": round(fwd, 3),
                                  "seconds": round(t, 3)}
                rec["bone1_cancels_animroot"] = air_dive._counter_rooted(c)
        clips.append(rec)
    out = {"battle_bins_round_trip": bin_ok, "bins_refused_not_v4": bin_refused,
           "flight_clips": len(clips), "versions": dict(versions), "clips": clips}
    (HERE / "flight_clips.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print({k: v for k, v in out.items() if k != "clips"})


if __name__ == "__main__":
    main()
