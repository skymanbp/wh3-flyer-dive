"""Battle ``.anim`` clip codec: read v7 and v8, write v7. [AIR-DIVE-W1 2026-11-09]

Layout measured on the installed game's anim packs (every flight-slot clip
the 75 vanilla flying animation tables name: 29 v7 + 135 v8, each consumed
to the last byte; evidence ``evidence/air_dive_w1_20261109/``). The skeleton
bind files that ``skeleton_anim.py`` reads are the same family (v8, one part,
raw codes) -- that parser stays as it is.

Common header (v7 and v8)::

    u32 version | u32 1 | f32 fps | str skeleton | u32 0 | f32 duration_s
    u32 bone_count | bone_count * (str name, i32 parent)
    (str = u16 length + ascii)

v7 body::

    i32 trans_map[bone_count] | i32 rot_map[bone_count]
        -1 = bind pose, n < 10000 = dynamic track n, 10000+n = static track n
    static : u32 tc | u32 rc | tc * 3f | rc * 4 i16
    dynamic: u32 tc | u32 rc | u32 frames | frames * (tc * 3f + rc * 4 i16)
    (quaternion component = i16 / 32767)

v8 body::

    u32 6 | u32 parts
    per part:
      i8 tcode[bone_count] | i8 rcode[bone_count]
          0 = bind pose; > 0 dynamic, < 0 static; |code| = bytes per value:
          translation 12 = 3 f32, 3 = 3 s8 quantized
          rotation    8 = 4 i16/32767,  4 = 4 s8 quantized
      u32 t_ranges | u32 r_ranges          (0 or bone_count each)
      t_ranges * (3f scale, 3f centre) | r_ranges * (4f scale, 4f centre)
          quantized value = centre + scale * s8 / 127
          (measured: 15,093 code-4 rotations decode to |q| = 1, median error
          0.0000, p90 0.0004; the min/max reading gives median 0.50)
      u32 tc | u32 rc | static values (bone order, translations first)
      u32 tc | u32 rc | u32 frames | frames * (dyn translations, dyn rotations)

A decoded clip is plain data: ``frames[f][bone] = (t, q)`` where ``t`` is a
3-tuple or ``None`` (bind pose) and ``q`` a 4-tuple (x, y, z, w) or ``None``.
Writing always produces v7 -- uncompressed, which vanilla itself ships
(``dr1_fly_charge_01.anim`` is v7), so an edited clip loses no precision.
/ 战斗动画读写：读 v7/v8，写 v7。布局逐字节实测，见证据目录。
"""
from __future__ import annotations

import struct


class AnimFormatError(ValueError):
    """The bytes are not a clip this codec can read."""


def read_ascii16(b, o):
    """(string, next offset) of a u16-length-prefixed ascii string at `o`.

    [TEST-REPAIR-1113] One home: anim_table_bin.py and skeleton_anim.py read
    and write the same string form and import these two."""
    n = struct.unpack_from("<H", b, o)[0]
    return b[o + 2:o + 2 + n].decode("ascii"), o + 2 + n


def write_ascii16(s):
    """The u16-length-prefixed ascii bytes of `s`."""
    e = s.encode("ascii")
    return struct.pack("<H", len(e)) + e


_rs, _ws = read_ascii16, write_ascii16


def _header(b):
    o = 0
    ver, one, fps = struct.unpack_from("<IIf", b, o)
    o += 12
    skel, o = _rs(b, o)
    flag, dur = struct.unpack_from("<If", b, o)
    o += 8
    bc = struct.unpack_from("<I", b, o)[0]
    o += 4
    bones = []
    for _ in range(bc):
        name, o = _rs(b, o)
        parent = struct.unpack_from("<i", b, o)[0]
        o += 4
        bones.append((name, parent))
    return {"version": ver, "one": one, "fps": fps, "skeleton": skel,
            "flag": flag, "duration": dur, "bones": bones}, o


def _q16(raw):
    return tuple(v / 32767.0 for v in raw)


def _decode_v7(b, o, bc):
    tmap = struct.unpack_from(f"<{bc}i", b, o)
    o += 4 * bc
    rmap = struct.unpack_from(f"<{bc}i", b, o)
    o += 4 * bc
    stc, src = struct.unpack_from("<II", b, o)
    o += 8
    st = [struct.unpack_from("<3f", b, o + 12 * i) for i in range(stc)]
    o += 12 * stc
    sr = [_q16(struct.unpack_from("<4h", b, o + 8 * i)) for i in range(src)]
    o += 8 * src
    dtc, drc, nf = struct.unpack_from("<III", b, o)
    o += 12
    frames = []
    for _ in range(nf):
        dt = [struct.unpack_from("<3f", b, o + 12 * i) for i in range(dtc)]
        o += 12 * dtc
        dr = [_q16(struct.unpack_from("<4h", b, o + 8 * i)) for i in range(drc)]
        o += 8 * drc
        fr = []
        for bi in range(bc):
            t = None if tmap[bi] < 0 else (st[tmap[bi] - 10000] if tmap[bi] >= 10000 else dt[tmap[bi]])
            q = None if rmap[bi] < 0 else (sr[rmap[bi] - 10000] if rmap[bi] >= 10000 else dr[rmap[bi]])
            fr.append((t, q))
        frames.append(fr)
    return frames, o


def _deq(raw, scale, centre):
    return tuple(c + s * (v / 127.0) for v, s, c in zip(raw, scale, centre))


def _read_t(b, o, code, rng):
    size = abs(code)
    if size == 12:
        return struct.unpack_from("<3f", b, o), o + 12
    if size == 3:
        if rng is None:
            raise AnimFormatError("quantized translation without a range")
        return _deq(struct.unpack_from("<3b", b, o), rng[:3], rng[3:]), o + 3
    raise AnimFormatError(f"translation code {code}")


def _read_q(b, o, code, rng):
    size = abs(code)
    if size == 8:
        return _q16(struct.unpack_from("<4h", b, o)), o + 8
    if size == 4:
        if rng is None:
            raise AnimFormatError("quantized rotation without a range")
        return _deq(struct.unpack_from("<4b", b, o), rng[:4], rng[4:]), o + 4
    raise AnimFormatError(f"rotation code {code}")


def _decode_v8(b, o, bc):
    _six, parts = struct.unpack_from("<II", b, o)
    o += 8
    frames = []
    for _p in range(parts):
        tcode = struct.unpack_from(f"<{bc}b", b, o)
        o += bc
        rcode = struct.unpack_from(f"<{bc}b", b, o)
        o += bc
        trn, rrn = struct.unpack_from("<II", b, o)
        o += 8
        if trn not in (0, bc) or rrn not in (0, bc):
            raise AnimFormatError(f"range counts {trn}/{rrn} for {bc} bones")
        tr = [struct.unpack_from("<6f", b, o + 24 * i) for i in range(trn)]
        o += 24 * trn
        rr = [struct.unpack_from("<8f", b, o + 32 * i) for i in range(rrn)]
        o += 32 * rrn
        o += 8  # static counts, implied by the codes
        st, sr = {}, {}
        for bi, c in enumerate(tcode):
            if c < 0:
                st[bi], o = _read_t(b, o, c, tr[bi] if tr else None)
        for bi, c in enumerate(rcode):
            if c < 0:
                sr[bi], o = _read_q(b, o, c, rr[bi] if rr else None)
        _tc, _rc, nf = struct.unpack_from("<III", b, o)
        o += 12
        for _f in range(nf):
            dt, dr = {}, {}
            for bi, c in enumerate(tcode):
                if c > 0:
                    dt[bi], o = _read_t(b, o, c, tr[bi] if tr else None)
            for bi, c in enumerate(rcode):
                if c > 0:
                    dr[bi], o = _read_q(b, o, c, rr[bi] if rr else None)
            frames.append([(dt.get(bi, st.get(bi)), dr.get(bi, sr.get(bi)))
                           for bi in range(bc)])
    return frames, o


def decode(blob):
    """Decode a v7 or v8 clip into ``{header fields..., frames}``."""
    ver = struct.unpack_from("<I", blob, 0)[0]
    if ver not in (7, 8):
        raise AnimFormatError(f"unsupported .anim version {ver}")
    head, o = _header(blob)
    bc = len(head["bones"])
    frames, o = (_decode_v7 if ver == 7 else _decode_v8)(blob, o, bc)
    if o != len(blob):
        raise AnimFormatError(f"consumed {o} of {len(blob)} bytes")
    head["frames"] = frames
    return head


def _track_kind(frames, bi, k):
    """'bind' / 'static' / 'dynamic' for one bone's translation (k=0) or rotation (k=1)."""
    vals = [fr[bi][k] for fr in frames]
    if all(v is None for v in vals):
        return "bind"
    if any(v is None for v in vals):
        raise AnimFormatError(f"bone {bi} track mixes bind pose and values")
    return "static" if all(v == vals[0] for v in vals) else "dynamic"


def _i16(v):
    return max(-32767, min(32767, int(round(v * 32767.0))))


def encode_v7(clip):
    """Write a decoded clip as an uncompressed v7 ``.anim``."""
    bones = clip["bones"]
    bc = len(bones)
    frames = clip["frames"]
    if not frames:
        raise AnimFormatError("clip has no frames")
    out = bytearray(struct.pack("<IIf", 7, clip.get("one", 1), clip["fps"]))
    out += _ws(clip["skeleton"])
    out += struct.pack("<If", clip.get("flag", 0), clip["duration"])
    out += struct.pack("<I", bc)
    for name, parent in bones:
        out += _ws(name) + struct.pack("<i", parent)
    tmap, rmap = [], []
    st, sr, dti, dri = [], [], [], []
    for bi in range(bc):
        kind = _track_kind(frames, bi, 0)
        if kind == "bind":
            tmap.append(-1)
        elif kind == "static":
            tmap.append(10000 + len(st)); st.append(frames[0][bi][0])
        else:
            tmap.append(len(dti)); dti.append(bi)
    for bi in range(bc):
        kind = _track_kind(frames, bi, 1)
        if kind == "bind":
            rmap.append(-1)
        elif kind == "static":
            rmap.append(10000 + len(sr)); sr.append(frames[0][bi][1])
        else:
            rmap.append(len(dri)); dri.append(bi)
    out += struct.pack(f"<{bc}i", *tmap) + struct.pack(f"<{bc}i", *rmap)
    out += struct.pack("<II", len(st), len(sr))
    for t in st:
        out += struct.pack("<3f", *t)
    for q in sr:
        out += struct.pack("<4h", *(_i16(v) for v in q))
    out += struct.pack("<III", len(dti), len(dri), len(frames))
    for fr in frames:
        for bi in dti:
            out += struct.pack("<3f", *fr[bi][0])
        for bi in dri:
            out += struct.pack("<4h", *(_i16(v) for v in fr[bi][1]))
    return bytes(out)
