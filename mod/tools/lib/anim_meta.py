"""Clip-space helpers for battle clips: ``.anm.meta`` event headers and the
animroot track. [AIR-DIVE-W9 2026-11-10]

The air dive's from-scratch plough clips (``pipelines/air_dive_clips.py``)
read a vanilla jump attack's meta (where its IMPACT_POS and SPLASH_ATTACK
capsules sit) and re-place those events on a new timeline, and sample the
animroot of vanilla clips (touchdown frame of a land clip, root position at
an event time). ``pipelines/air_dive.py`` uses :func:`root_track` to judge
which land clips carry a clip-driven descent. These are the helpers W1-W3
had inside ``air_dive.py`` (removed at W8 with the dive clips, restored here
as one module; only the ones still used).

``.anm.meta`` layout (version 2, measured on the installed anim packs at
W1): ``u32 version, u32 count`` then ``count`` events, each a u16 name
length, the ASCII name, ``u32 event_version, f32 start, f32 end`` and a body
whose layout depends on (name, version). :data:`META_POINTS` gives, for the
two point-carrying events the dive moves, the byte offset of the first
xyz point inside the body and how many points follow.
/ 战斗动作的 meta 事件头与 animroot 轨迹工具。
"""
from __future__ import annotations

import math
import re
import struct

_META_HEAD = re.compile(rb"([\x01-\x40])\x00([A-Z][A-Z0-9_]+)")
# (event name, event version) -> (byte offset of the first point in the
# body, number of xyz points)
META_POINTS = {("IMPACT_POS", 10): (6, 1), ("SPLASH_ATTACK", 10): (10, 2)}


def meta_events(blob):
    """Event headers of an ``.anm.meta``: name, version, start, end, offsets
    (``offset`` of the header, ``body`` after start/end, ``limit`` = next
    header). Fail-closed: a meta whose declared count is not the number of
    headers found is refused, never half-read."""
    ver, count = struct.unpack_from("<II", blob, 0)
    if ver != 2:
        raise SystemExit(f"[anim_meta] REFUSING: meta version {ver}")
    out = []
    for m in _META_HEAD.finditer(blob, 8):
        if m.group(1)[0] != len(m.group(2)) or m.end() + 12 > len(blob):
            continue
        ev, start, end = struct.unpack_from("<Iff", blob, m.end())
        if not 9 <= ev <= 20:
            continue
        out.append({"offset": m.start(), "body": m.end() + 12,
                    "name": m.group(2).decode("ascii"), "version": ev,
                    "start": start, "end": end})
    if len(out) != count:
        raise SystemExit(f"[anim_meta] REFUSING: meta says {count} events, "
                         f"{len(out)} headers found")
    for i, e in enumerate(out):
        e["limit"] = out[i + 1]["offset"] if i + 1 < len(out) else len(blob)
    return out


def root_track(clip):
    """animroot translation per frame, or None when bone 0 is not an
    animated animroot."""
    name, parent = clip["bones"][0]
    if name != "animroot" or parent != -1:
        return None
    track = [fr[0][0] for fr in clip["frames"]]
    if any(t is None for t in track):
        return None
    return track


def root_at(track, fps, t):
    """The animroot translation at time ``t``, linearly interpolated."""
    f = max(0.0, min(t * fps, len(track) - 1))
    i = int(math.floor(f))
    j = min(i + 1, len(track) - 1)
    u = f - i
    return tuple(a + (b - a) * u for a, b in zip(track[i], track[j]))


def touchdown_frame(track):
    """First frame at which the animroot has finished its descent (within 2%
    of the clip's own drop)."""
    y0 = track[0][1]
    lowest = min(t[1] for t in track)
    slack = 0.02 * (y0 - lowest)
    for f, t in enumerate(track):
        if t[1] - lowest <= slack:
            return f
    return len(track) - 1
