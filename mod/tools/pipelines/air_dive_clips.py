"""Air dive plough clips -- the from-scratch slot-489 dive charge. [AIR-DIVE-W9 2026-11-10]

User 2026-11-09 (CONTENT_LEDGER §C8-45 item 3): a charging flyer must
descend while it charges and carry on INTO the enemy. W8 shipped half of
that: the renamed flight tables without slot 104 FLY_CHARGE_LAND and
``jump_attack_chance`` 100 on every flyer, so right after touchdown the
engine plays the table's slot 489 JUMPING_ATTACK and applies that clip's
animroot translation to the entity (canary 13: 24.3 m after touchdown).
Vanilla 489 clips are short pounces; this module authors, per skeleton, a
NEW clip for slot 489 that ploughs through the line (canary 15, lane
air-dive-clips, user eyeballing in game 2026-11-10).

EVIDENCE THIS RESTS ON
- After touchdown with slot 104 removed and jump_attack_chance 100, the engine
  plays the table's slot 489 and applies the clip's animroot translation to
  the entity (probe: star dragon 21.5 / 21.8 m at is_moving=0, bearing-aligned;
  canary 11 authored 17.3 m -> 19.9 m; canary 13 vanilla 20.1 m -> 24.3 m
  twice). Touchdown zeroes flyer speed, so this clip is the only forward
  momentum. Observed displacement peaks at 20.0 m/s even where the clip root
  reaches 27 m/s: treat 20 m/s as an engine cap.
- Meta points (IMPACT_POS, SPLASH_ATTACK start/end) are clip-space: dr1 jump
  meta capsules sit at z 7-23 m on a clip whose root ends at z 20.1.

WHAT ONE CLIP IS (new, not a copy)
- animroot: our own speed profile -- [AIR-DIVE-CONTINUOUS-W1 2026-11-12,
  §C8-59] it STARTS at the speed (the flyer's arrival speed,
  ``air_dive_rules.plough_speed``), holds it, then a linear stop; at least
  MIN_HOLD_S of hold, a short travel shortens the stop instead. W9-W13 eased
  in from 0 over 0.25 s, which with the approach braking before touchdown
  read as "brake, then a second forward lunge". [AIR-DIVE-W12 2026-11-11] The peak is the flyer's own charge
  speed (``air_dive_rules.FLYER_CHARGE_SPEEDS``; momentum = speed x mass,
  user 2026-11-11) and the travel follows from the size class's timing
  (``air_dive_rules.plough_profile``: large 22 m per 20 m/s, medium 16 per
  18, small 11 per 14; ``PLOUGH_SKELETON_CLASS`` maps the skeleton). W9-W11
  used the class peak for every flyer of the class.
- body: per-bone local poses BLENDED on our timeline from the skeleton's own
  vanilla poses: the touchdown frame of its land clip (slot 104), its charge
  stride (slot 135, else run 53) cycled at the rate our root speed implies, the
  impact frame of its jump attack (489, else 484, else attack 454) layered on
  the upper body over the strike window, and its combat idle (439, else stand
  1) at the end. The body-root bone keeps the stride's horizontal offset so a
  source clip that carries its motion in that bone (counter-rooted) cannot
  drag the body.
- meta: built fresh -- one IMPACT_POS at first contact (head reach measured from
  the source jump attack), SPLASH_ATTACK knock-back capsules every
  SPLASH_EVERY s along the plough (capsule geometry and the four tail floats
  copied from the source's own nearest-to-impact splash, positions re-placed
  ahead of our root), CAMERA_SHAKE kept at impact, every other source event
  (EFFECT, FACE_POSE, SPLICE, DOCK_*, ANIMATED_PROP, ...) re-timed by mapping the
  source impact time onto ours. An event with no rule is a refusal.

STRIKE SOURCE (``pick_strike``): the first decodable ref among slots 489,
484, 454 whose meta carries an IMPACT_POS. ``bi1b_carrion`` (bird01b): its
slot-489 ``bi1b_jump_attack_01`` and its stand / combat idle (slots 1, 439)
are anim version 5, which ``anim_codec`` does not decode (measured
2026-11-10), so the strike falls back to its slot-454 ``bi1b_attack_06``
pose (version 8); that meta has no SPLASH_ATTACK, so the knock-back
capsules come from DONOR_SPLASH_META (the bird01 eagle's jump attack) at
fixed offsets, and the clip ends without an idle blend (``missing_poses:
idle`` in the manifest). Every other skeleton uses its own poses.

``pipelines/air_dive.py`` calls :func:`author` once per distinct (skeleton,
strike ref, speed) and puts the clip in slot 489 of each renamed table
(``air_dive.dive_entries``); the clips ship from ``mod/assets/air_dive``
under ``animations/battle/flyer_dive/plough/`` with the manifest's sha256.
Deterministic: ``air_dive.py --check`` re-authors and compares bytes.
/ 俯冲冲锋：按骨架从零生成 489 号跳击动作（落地后冲进敌阵）。
"""
import math
import struct

import air_dive_rules
import anim_codec
import anim_meta

FPS = 20.0
SLOT_LAND, SLOT_CHARGE, SLOT_RUN, SLOT_CIDLE, SLOT_STAND = 104, 135, 53, 439, 1
SLOT_ATTACK, SLOT_JUMP, SLOT_MOVING = 454, 489, 484

T_DECEL = 0.70
T_SETTLE = 0.40
T_IMPACT = 0.35     # the impact event's time in the clip (unchanged since W9)
MIN_HOLD_S = 0.15   # [AIR-DIVE-CONTINUOUS-W1] the clip holds its entry speed at least this long
SPLASH_EVERY = 0.20
LEG_KEYS = ("leg", "foot", "toe", "ankle", "knee", "hips", "thigh", "calf", "heel")
WING_KEYS = ("wing", "feather")
POINT_EVENTS = {("IMPACT_POS", 10), ("SPLASH_ATTACK", 10), ("CAMERA_SHAKE_POS", 10)}
KEEP_EVENTS = {"EFFECT", "FACE_POSE", "RHAND_POSE", "SPLICE", "SPLICE_OVERRIDE",
               "DOCK_EQPT_RHAND", "DOCK_EQPT_LHAND", "DOCK_EQPT_LHAND_2",
               "DOCK_EQPT_RHAND_2", "ANIMATED_PROP", "DISABLE_PERSISTENT",
               "DISABLE_PERSISTENT_ID", "DISABLE_HEAD_TRACKING",
               "SHADER_PARAMETER", "CAMERA_SHAKE_SCALE", "IMPACT_SPEED"}
DONOR_SPLASH_META = "animations/battle/bird01/attacks/bi1_jump_attack_01.anm.meta"


class Refused(SystemExit):
    pass


def profile_for(skeleton, charge_speed):
    try:
        cls, v, d = air_dive_rules.plough_profile(skeleton, charge_speed)
    except RuntimeError as exc:
        raise Refused(f"[air_dive_clips] {exc}") from None
    # [AIR-DIVE-CONTINUOUS-W1] no ramp: hold v from t = 0, then stop in t_dec
    t_dec = T_DECEL
    hold = (d - v * t_dec / 2.0) / v
    if hold < MIN_HOLD_S:
        hold = MIN_HOLD_S
        t_dec = 2.0 * (d - v * hold) / v
        if t_dec < 0.2:
            raise Refused(f"[air_dive_clips] REFUSING: class {cls} travel {d} too short for {v} m/s")
    t_stop = hold + t_dec
    return {"class": cls, "v": v, "d": d, "t_hold_end": hold, "t_stop": t_stop,
            "t_dec": t_dec, "duration": round((t_stop + T_SETTLE) * FPS) / FPS,
            "t_impact": T_IMPACT}


def speed(p, t):
    v = p["v"]
    if t <= p["t_hold_end"]:
        return v
    if t <= p["t_stop"]:
        return v * (1 - (t - p["t_hold_end"]) / p["t_dec"])
    return 0.0


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def nlerp_q(a, b, w):
    if sum(x * y for x, y in zip(a, b)) < 0:
        b = tuple(-x for x in b)
    q = tuple(x + (y - x) * w for x, y in zip(a, b))
    n = math.sqrt(sum(x * x for x in q)) or 1.0
    return tuple(x / n for x in q)


def lerp_t(a, b, w):
    return tuple(x + (y - x) * w for x, y in zip(a, b))


def sample(clip, t, bind):
    fr = clip["frames"]
    f = max(0.0, min(t * clip["fps"], len(fr) - 1))
    i = int(f); j = min(i + 1, len(fr) - 1); u = f - i
    out = []
    for bi in range(len(clip["bones"])):
        ta, qa = fr[i][bi]
        tb, qb = fr[j][bi]
        ta = ta if ta is not None else bind[bi][0]
        tb = tb if tb is not None else bind[bi][0]
        qa = qa if qa is not None else bind[bi][1]
        qb = qb if qb is not None else bind[bi][1]
        out.append((lerp_t(ta, tb, u), nlerp_q(qa, qb, u)))
    return out


def blend(a, b, weights):
    return [((lerp_t(ta, tb, w), nlerp_q(qa, qb, w)) if w > 0 else (ta, qa))
            for (ta, qa), (tb, qb), w in zip(a, b, weights)]


def _horiz_root(clip):
    tr = anim_meta.root_track(clip)
    if tr is None:
        return 0.0
    return math.hypot(tr[-1][0] - tr[0][0], tr[-1][2] - tr[0][2])


def _event_point(blob, e, k=0):
    pre, _n = anim_meta.META_POINTS.get((e["name"], e["version"]), (6, 1))
    return struct.unpack_from("<fff", blob, e["body"] + pre + 12 * k)


def _root_at(clip, t):
    tr = anim_meta.root_track(clip)
    if tr is None:
        return (0.0, 0.0, 0.0)
    return anim_meta.root_at(tr, clip["fps"], t)


def pick_strike(read, table):
    """First decodable ref among slots 489, 484, 454 with an IMPACT_POS meta."""
    tried = []
    for slot in (SLOT_JUMP, SLOT_MOVING, SLOT_ATTACK):
        for e in table["entries"]:
            if e["slot"] != slot:
                continue
            for r in e["refs"]:
                try:
                    anim_codec.decode(read(r[0]))
                    evs = anim_meta.meta_events(read(r[1])) if r[1] else []
                except (anim_codec.AnimFormatError, SystemExit) as exc:
                    tried.append((slot, r[0], str(exc)[:50])); continue
                if any(x["name"] == "IMPACT_POS" for x in evs):
                    return r, slot, tried
                tried.append((slot, r[0], "no IMPACT_POS"))
    raise Refused(f"[air_dive_clips] REFUSING: {table['name']} has no usable strike ref: {tried}")


def author(read, table, strike_ref, charge_speed):
    """(clip_bytes, meta_bytes, report) for one vanilla table, the jump/attack
    ref whose impact frame and meta layout seed the strike, and the flyer
    charge speed the plough peaks at. ``table`` is the installed vanilla
    table (parsed)."""
    skel = table["skeleton"]
    p = profile_for(skel, charge_speed)
    def try_dec(path):
        try:
            return anim_codec.decode(read(path))
        except (anim_codec.AnimFormatError, SystemExit):
            return None

    def first_dec(*slots):
        for slot in slots:
            for e in table["entries"]:
                if e["slot"] == slot:
                    for r in e["refs"]:
                        c = try_dec(r[0])
                        if c is not None:
                            return c, r[0]
        return None, None

    run, run_path = first_dec(SLOT_CHARGE, SLOT_RUN)
    if run is None:
        raise Refused(f"[air_dive_clips] REFUSING: {table['name']} has no decodable charge/run clip")
    names = [b[0] for b in run["bones"]]
    sk = try_dec(f"animations/skeletons/{skel}.anim")
    if sk is None or [b[0] for b in sk["bones"]] != names:
        raise Refused(f"[air_dive_clips] REFUSING: {skel} skeleton bones differ from {run_path}")
    bind = [(t if t is not None else (0.0, 0.0, 0.0), q if q is not None else (0.0, 0.0, 0.0, 1.0))
            for t, q in sk["frames"][0]]
    used = {"run": run_path}

    def pose_src(label, *slots):
        c, path = first_dec(*slots)
        if c is not None and [b[0] for b in c["bones"]] == names:
            used[label] = path
            return c
        return None

    land = pose_src("land", SLOT_LAND)
    idle = pose_src("idle", SLOT_CIDLE, SLOT_STAND)
    strike = try_dec(strike_ref[0])
    if strike is None:
        raise Refused(f"[air_dive_clips] REFUSING: strike ref {strike_ref[0]} undecodable")
    strike_ok = [b[0] for b in strike["bones"]] == names
    if strike_ok:
        used["strike"] = strike_ref[0]
    land_ok, idle_ok = land is not None, idle is not None

    # body root: bone named root/pelvis directly under animroot, else bone 1
    body = next((i for i, (n, par) in enumerate(run["bones"]) if par == 0 and n in ("root", "pelvis")), None)
    if body is None:
        body = next((i for i, (n, par) in enumerate(run["bones"]) if par == 0 and not n.startswith("be_prop")), 1)
    leg_w = [0.3 if any(k in n.lower() for k in LEG_KEYS) else 1.0 for n in names]
    wing = [any(k in n.lower() for k in WING_KEYS) for n in names]
    has_t = [any(c["frames"][0][bi][0] is not None for c in (land, run, strike, idle)
                 if c is not None and [b[0] for b in c["bones"]] == names) for bi in range(len(names))]

    # touchdown frame of the land clip
    ltr = anim_meta.root_track(land) if land_ok else None
    land_td = (anim_meta.touchdown_frame(ltr) / land["fps"]) if ltr else 0.7 * land["duration"]
    # strike time = the source jump/attack impact
    meta_blob = read(strike_ref[1]) if strike_ref[1] else None
    evs = anim_meta.meta_events(meta_blob) if meta_blob else []
    imp = next((e for e in evs if e["name"] == "IMPACT_POS"), None)
    strike_t = imp["start"] if imp else 0.5 * strike["duration"]
    p_land = sample(land, land_td, bind) if land_ok else None
    p_strike = sample(strike, strike_t, bind) if strike_ok else None
    p_idle = sample(idle, 0.0, bind) if idle_ok else None
    run_mps = _horiz_root(run) / run["duration"] if run["duration"] else 0.0
    run_len = run["duration"]

    n = int(round(p["duration"] * FPS)) + 1
    dt = 1.0 / FPS
    ti = p["t_impact"]
    z, phase = 0.0, 0.0
    frames, root_z = [], []
    for f in range(n):
        t = f * dt
        if f:
            z += 0.5 * (speed(p, t - dt) + speed(p, t)) * dt
            rate = (speed(p, t) / run_mps) if run_mps > 0.5 else 1.0
            phase = (phase + max(0.8, min(2.2, rate)) * dt) % run_len
        root_z.append(z)
        base = sample(run, phase, bind)
        pose = base
        if p_land:
            # wings keep the descent flare and fold by 0.75 s; body leaves the crouch in 0.2 s
            pose = blend(pose, p_land, [1.0 - smooth((t - 0.35) / 0.40) if w else 0.0 for w in wing])
            pose = blend(pose, p_land, [1.0 - smooth(t / 0.20)] * len(names))
        if p_strike:
            w = smooth((t - (ti - 0.25)) / 0.25) * (1.0 - smooth((t - (p["t_hold_end"] - 0.05)) / 0.35))
            pose = blend(pose, p_strike, [w * lw for lw in leg_w])
        if p_idle:
            pose = blend(pose, p_idle, [smooth((t - (p["t_stop"] - 0.2)) / (T_SETTLE + 0.2))] * len(names))
        fr = []
        for bi, (tt, qq) in enumerate(pose):
            if bi == 0:
                fr.append(((0.0, 0.0, z), run["frames"][0][0][1] or (0.0, 0.0, 0.0, 1.0)))
                continue
            if bi == body:
                tt = (base[bi][0][0], tt[1], base[bi][0][2])
            fr.append((tt if has_t[bi] else None, qq))
        frames.append(fr)
    # animroot rotation must be one kind of track: force it
    clip = {"version": 7, "one": 1, "fps": FPS, "skeleton": run["skeleton"], "flag": run.get("flag", 0),
            "duration": (n - 1) / FPS, "bones": run["bones"], "frames": frames}
    blob = anim_codec.encode_v7(clip)
    back = anim_codec.decode(blob)
    if len(back["frames"]) != n or abs(anim_meta.root_track(back)[-1][2] - z) > 1e-3:
        raise Refused("[air_dive_clips] REFUSING: encoded clip does not decode to what was authored")

    meta, meta_report = build_meta(read, meta_blob, evs, strike, strike_t, p, root_z)
    peak = max((root_z[k + 1] - root_z[k]) * FPS for k in range(n - 1))
    report = {"table": table["name"], "skeleton": skel, "class": p["class"],
              "duration_s": round((n - 1) / FPS, 2), "travel_m": round(z, 2),
              "peak_mps": round(peak, 2), "impact_t": round(ti, 2),
              "poses": used, "missing_poses": [k for k in ("land", "strike", "idle") if k not in used],
              "meta": meta_report}
    return blob, meta, report


def _event_blob(blob, e):
    return bytearray(blob[e["offset"]:e["limit"]])


def _set_times(eb, e, s, en):
    struct.pack_into("<ff", eb, e["body"] - e["offset"] - 8, s, en)


def build_meta(read, meta_blob, evs, strike, strike_t, p, root_z):
    dur = (len(root_z) - 1) / FPS
    ti = p["t_impact"]
    src_dur = strike["duration"]

    def zt(t):
        return root_z[min(len(root_z) - 1, max(0, int(round(t * FPS))))]

    def remap(t):
        if t <= strike_t:
            v = t * ti / strike_t if strike_t > 0 else ti
        else:
            span = max(1e-3, src_dur - strike_t)
            v = ti + (t - strike_t) * (dur - ti) / span
        return max(0.0, min(dur, v))

    out_events = []
    report = []
    # IMPACT_POS
    imp = next((e for e in evs if e["name"] == "IMPACT_POS"), None)
    if imp is None:
        raise Refused("[air_dive_clips] REFUSING: source meta has no IMPACT_POS")
    sr = _root_at(strike, imp["start"])
    ip = _event_point(meta_blob, imp)
    reach = tuple(a - b for a, b in zip(ip, sr))
    eb = _event_blob(meta_blob, imp)
    _set_times(eb, imp, ti, ti)
    pt = (reach[0], reach[1], zt(ti) + reach[2])
    struct.pack_into("<fff", eb, imp["body"] - imp["offset"] + 6, *pt)
    out_events.append(eb)
    report.append(("IMPACT_POS", round(ti, 2), [round(v, 2) for v in pt]))
    # SPLASH_ATTACK knock-back capsules along the plough
    splashes = [e for e in evs if e["name"] == "SPLASH_ATTACK"]
    src_blob = meta_blob
    if not splashes:
        src_blob = read(DONOR_SPLASH_META)
        splashes = [e for e in anim_meta.meta_events(src_blob) if e["name"] == "SPLASH_ATTACK"]
        donor = True
    else:
        donor = False
    main = min(splashes, key=lambda e: abs(e["start"] - imp["start"]))
    if donor:
        off_s = (0.0, 0.0, 3.0); off_e = (0.0, 0.0, 9.0)
    else:
        mr = _root_at(strike, main["start"])
        s0 = _event_point(src_blob, main, 0); e0 = _event_point(src_blob, main, 1)
        off_s = tuple(a - b for a, b in zip(s0, mr)); off_e = tuple(a - b for a, b in zip(e0, mr))
    t = ti
    while t <= p["t_hold_end"] + 0.15 + 1e-6:
        eb = _event_blob(src_blob, main)
        _set_times(eb, main, t, t)
        a = (off_s[0], off_s[1], zt(t) + off_s[2]); b = (off_e[0], off_e[1], zt(t) + off_e[2])
        base = main["body"] - main["offset"] + 10
        struct.pack_into("<fff", eb, base, *a)
        struct.pack_into("<fff", eb, base + 12, *b)
        out_events.append(eb)
        report.append(("SPLASH_ATTACK", round(t, 2), [round(v, 2) for v in a], [round(v, 2) for v in b]))
        t += SPLASH_EVERY
    # everything else
    for e in evs:
        if e["name"] in ("IMPACT_POS", "SPLASH_ATTACK"):
            continue
        key = (e["name"], e["version"])
        if e["name"] == "CAMERA_SHAKE_POS":
            eb = _event_blob(meta_blob, e)
            _set_times(eb, e, ti, ti)
            v = _event_point(meta_blob, e)
            if v != (0.0, 0.0, 0.0):
                v = (v[0], v[1], v[2] - _root_at(strike, e["start"])[2] + zt(ti))
                struct.pack_into("<fff", eb, e["body"] - e["offset"] + 6, *v)
            out_events.append(eb)
            report.append((e["name"], round(ti, 2)))
            continue
        if key in POINT_EVENTS or e["name"] not in KEEP_EVENTS:
            raise Refused(f"[air_dive_clips] REFUSING: meta event {key} has no rule")
        eb = _event_blob(meta_blob, e)
        s, en = remap(e["start"]), remap(e["end"])
        if e["start"] <= 0.0 and e["end"] >= src_dur - 1e-3:
            s, en = e["start"], dur  # whole-clip events stay whole-clip
        _set_times(eb, e, s, max(s, en))
        out_events.append(eb)
        report.append((e["name"], round(s, 2), round(en, 2)))
    blob = struct.pack("<II", 2, len(out_events)) + b"".join(bytes(x) for x in out_events)
    check = anim_meta.meta_events(blob)
    if len(check) != len(out_events):
        raise Refused("[air_dive_clips] REFUSING: rebuilt meta does not re-parse")
    return blob, {"events": len(out_events), "splash_donor": donor, "list": report}
