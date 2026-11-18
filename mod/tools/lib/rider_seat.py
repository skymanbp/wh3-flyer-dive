"""Rider seat on a flying mount: where the rider's pelvis sits on the mount's body,
and a levelled copy of a mount clip that keeps it there. [FLYER-SEAT-1117 2026-11-17]

WHY. A ridden flyer plays two clips at once: the mount's clip from the mount
table (``mounts_tables.animation``, the table this mod renames) and the
rider's paired clip from the rider table (``land_units.man_animation``,
which this mod does not touch). Pegasus-type riders are authored in animroot
space -- their clips carry the seat height themselves, they are not parented
to the horse (measured: the rider ``root`` bobs 2.14 / 1.43 / 2.14 m in
``fly_walk`` with the horse's 1.61 / 0.91 / 1.60 m). The flight slots pair
mount 102 / 103 / 104 / 105 with rider 1771 / 1772 / 1773 / 1774 (the clip
names say so: ``*_fly_walk`` / ``*_fly_charge`` / ``*_fly_charge_land`` /
``*_take_off`` on both sides). So when the mod changes the clip a mount slot
plays, the unchanged rider clip in the paired slot must still sit on it.
FLYER-FIX-1117 (34dfbf3) broke that: slot 103 played the bobbing level
flight clip while the rider kept the steady dive clip, and the rider's
pelvis drifted up to 1.06 m off the saddle (player report 2026-11-17,
"the character model and the mount are separated").

WHAT "SEATED" MEANS HERE. The offset rider ``root`` minus one mount bone,
both relative to their animroot (animroot translation is locomotion, which
the entity carries), on a shared clock from t = 0 with each clip looping at
its own length. In CA's own pairs that offset stays put to within 0.06-0.15 m
on the bone the rider actually sits on (``horse01``: ``spine_1``, measured
over the pegasus riders' 1771/1772/1773/1936 pairs); the seat bone per
skeleton is declared in ``SEAT`` and pinned by the tests to be CA's
best-tracking bone.
/ 骑手座位：骑手骨盆相对坐骑身体的位置；以及保持座位不动的坐骑动作水平化。
"""
from __future__ import annotations

import math

import anim_codec

# skeleton -> the mount bone the rider's pelvis sits on, and the two bones whose
# line is the body's long axis (for the body pitch)
SEAT = {"horse01": {"seat": "spine_1", "axis": ("spine_0", "neck_0")}}
# mount flight slot -> the rider table slot that plays with it
RIDER_SLOT = {102: 1771, 103: 1772, 104: 1773, 105: 1774}
# mount attack slot -> the rider table slot that plays with it: 484 MOVING_ATTACK / 1931 and 489
# JUMPING_ATTACK / 1936. The clip names say so on both sides across all 1,426 installed tables (measured
# 2026-11-17: 484 573 of 607 refs *moving_attack*, 1931 187 of 191; 489 710 of 945 *jumping_attack*, 1936
# 221 of 296, the rest plain *attack*). The mod adds 484 to a mount table from its 489 jump attack
# (air_dive.dive_entries), so the rider must then play its 1936 clip in 1931 (air_dive.rider_copies);
# leaving the rider's own 1931 moving attack under the mount's jump attack put the pegasus riders 0.99-1.17 m
# off the saddle (FLYER-SEAT-1117 second half).
RIDER_ATTACK_SLOT = {484: 1931, 489: 1936}
RIDER_PAIR = {**RIDER_SLOT, **RIDER_ATTACK_SLOT}
SAMPLE_HZ = 20.0


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def qrot(q, v):
    p = qmul(qmul(q, (v[0], v[1], v[2], 0.0)), (-q[0], -q[1], -q[2], q[3]))
    return p[:3]


def skeleton_bind(read_clip, skeleton):
    """``{bone: (t, q)}`` of the skeleton's bind pose (the installed
    ``animations/skeletons/<skeleton>.anim``), for bones a clip leaves at bind."""
    c = anim_codec.decode(read_clip(f"animations/skeletons/{skeleton}.anim"))
    return {n: c["frames"][0][i] for i, (n, _p) in enumerate(c["bones"])}


def _chain(clip, name):
    names = [n for n, _p in clip["bones"]]
    if name not in names:
        raise ValueError(f"{clip['skeleton']}: no bone {name!r}")
    i, chain = names.index(name), []
    while clip["bones"][i][1] >= 0:   # stop below animroot
        chain.append(i)
        i = clip["bones"][i][1]
    return chain[::-1]


def _pose(clip, f, i, bind):
    t, q = clip["frames"][f][i]
    name = clip["bones"][i][0]
    if t is None:
        t = bind[name][0]
    if q is None:
        q = bind[name][1]
    return t, q


def bone_pos(clip, f, name, bind):
    """Position of bone ``name`` at frame ``f`` in animroot space."""
    pos, rot = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
    for i in _chain(clip, name):
        t, q = _pose(clip, f, i, bind)
        pos = tuple(a + b for a, b in zip(pos, qrot(rot, t)))
        rot = qmul(rot, q)
    return pos


def track(clip, name, bind):
    return [bone_pos(clip, f, name, bind) for f in range(len(clip["frames"]))]


def _at(points, fps, duration, t):
    if len(points) == 1 or duration <= 0:
        return points[0]
    x = (t % duration) * fps
    i = min(int(x), len(points) - 1)
    j = min(i + 1, len(points) - 1)
    u = x - i
    return tuple(a + (b - a) * u for a, b in zip(points[i], points[j]))


def offsets(mount, rider, seat, mount_bind, rider_bind, loops=3):
    """Rider ``root`` minus mount ``seat`` bone, sampled at SAMPLE_HZ from t = 0
    over ``loops`` times the longer clip, each clip looping at its own length."""
    m, r = track(mount, seat, mount_bind), track(rider, "root", rider_bind)
    span = loops * max(mount["duration"], rider["duration"])
    out = []
    for k in range(int(span * SAMPLE_HZ) + 1):
        t = k / SAMPLE_HZ
        a = _at(r, rider["fps"], rider["duration"], t)
        b = _at(m, mount["fps"], mount["duration"], t)
        out.append(tuple(x - y for x, y in zip(a, b)))
    return out


def pair_error(mount, rider, authored_mount, authored_rider, seat, mount_bind, rider_bind):
    """Largest distance (m) between the rider's seat offset in the pair (``mount``, ``rider``) and in the
    pair CA authored (``authored_mount``, ``authored_rider``), same clock, each clip looping at its own length."""
    a = offsets(mount, rider, seat, mount_bind, rider_bind)
    b = offsets(authored_mount, authored_rider, seat, mount_bind, rider_bind)
    return max(math.dist(x, y) for x, y in zip(a, b))


def seat_error(mount, authored_mount, rider, seat, mount_bind, rider_bind):
    """Largest distance (m) between the rider's seat offset on ``mount`` and
    on ``authored_mount`` (the clip CA paired the rider clip with), same clock."""
    return pair_error(mount, rider, authored_mount, rider, seat, mount_bind, rider_bind)


def seat_spread(mount, rider, bone, mount_bind, rider_bind):
    """How far (m) the rider's offset to ``bone`` strays from its mean over the pair."""
    o = offsets(mount, rider, bone, mount_bind, rider_bind)
    mean = [sum(v[k] for v in o) / len(o) for k in range(3)]
    return max(math.dist(v, mean) for v in o)


def body_pitch(clip, f, axis, bind):
    """Degrees the body's long axis rises above horizontal (+ = nose up)."""
    a, b = bone_pos(clip, f, axis[0], bind), bone_pos(clip, f, axis[1], bind)
    d = [y - x for x, y in zip(a, b)]
    return math.degrees(math.atan2(d[1], math.hypot(d[0], d[2])))


def mean_pitch(clip, axis, bind):
    n = len(clip["frames"])
    return sum(body_pitch(clip, f, axis, bind) for f in range(n)) / n


def level_about_seat(clip, bind, target_pitch):
    """A copy of mount ``clip`` whose whole body is turned about the lateral
    (x) axis through the seat bone, frame by frame, so its mean body pitch is
    ``target_pitch``: the seat bone keeps its exact position (the rider's
    paired clip still sits on it) and only the mount's attitude changes.

    The turn is applied to the skeleton's ``root`` (the one child of animroot
    every other body bone hangs from); animroot itself is untouched, so the
    clip's locomotion is CA's. Refuses a clip whose animroot rotates (the
    lateral axis would not be the clip's x axis) or whose body does not hang
    from ``root``."""
    spec = SEAT[clip["skeleton"]]
    names = [n for n, _p in clip["bones"]]
    if names[0] != "animroot" or names[1] != "root" or clip["bones"][1][1] != 0:
        raise ValueError(f"{clip['skeleton']}: bone 1 is not root under animroot")
    for fr in clip["frames"]:
        q = fr[0][1]
        if q is not None and abs(abs(q[3]) - 1.0) > 1e-4:
            raise ValueError(f"{clip['skeleton']}: animroot rotates; refusing to level")
    theta = math.radians(mean_pitch(clip, spec["axis"], bind) - target_pitch)
    rot = (math.sin(theta / 2), 0.0, 0.0, math.cos(theta / 2))   # + theta lowers the nose
    frames = []
    for f, fr in enumerate(clip["frames"]):
        s = bone_pos(clip, f, spec["seat"], bind)
        t, q = _pose(clip, f, 1, bind)
        rel = tuple(a - b for a, b in zip(t, s))
        t2 = tuple(a + b for a, b in zip(s, qrot(rot, rel)))
        q2 = qmul(rot, q)
        new = list(fr)
        new[1] = (t2, q2)
        frames.append(new)
    out = dict(clip)
    out["frames"] = frames
    return out
