"""The `.animpack` container codec: one reader and one writer.

An animpack is a flat list of named blobs: ``<u32 count>`` followed, per entry,
by ``<u16 path length><ascii path><u32 size><bytes>``. Here it reads CA's
animpacks and writes ``ld_air_dive_tables.animpack`` (``pipelines/air_dive.py``).
/ animpack 容器编解码的唯一实现。
"""
from __future__ import annotations

import struct


def animpack_iter(data):
    """Yield ``(inner path, blob)`` for every entry of an animpack blob."""
    n = struct.unpack_from("<I", data, 0)[0]
    off = 4
    for _ in range(n):
        plen = struct.unpack_from("<H", data, off)[0]
        off += 2
        path = data[off:off + plen].decode("ascii", "replace")
        off += plen
        size = struct.unpack_from("<I", data, off)[0]
        off += 4
        yield path, data[off:off + size]
        off += size


def animpack_build(entries):
    """Serialise ``(inner path, blob)`` pairs into an animpack blob."""
    out = bytearray(struct.pack("<I", len(entries)))
    for path, blob in entries:
        p = path.encode("ascii")
        out += struct.pack("<H", len(p)) + p
        out += struct.pack("<I", len(blob)) + blob
    return bytes(out)


def bin_table_name(blob):
    """The battle-animation table a ``.bin`` declares, or None if unreadable.

    The name sits at offset 8 as ``<u16 length><ascii>``. Moved here from
    ``gates/vendor_anim_closure.py`` (§C8-26 R-1 续 2026-10-15) because the
    polish-review animation census now needs the same answer: a vendored kit's
    table can be declared inside ANOTHER kit's shared container, so "does this
    kit ship an animation file named after it" is the wrong question.
    / 动作表名在 bin 偏移 8 处；普查与闭包门共用这一份。
    """
    try:
        length = struct.unpack_from("<H", blob, 8)[0]
        return blob[10:10 + length].decode("ascii", "replace")
    except struct.error:
        return None


_ANIM_REF_SUFFIXES = (b".anim", b".frg")


def bin_anim_refs(blob):
    """Every animation file a battle ``.bin`` names, as the bin spells them.

    Strings inside a bin are ``<u16 length><ascii>``, so a reference is read
    by its own length prefix: find each ``animations`` (any case), read the
    u16 just before it, and take exactly that many bytes. Accepted when the
    string is printable ASCII and ends ``.anim`` / ``.frg``.

    [cw-vendor-c 2026-10-22] Replaces a regex in ``gates/vendor_anim_closure``
    whose path character class was letters, digits, underscore, slashes and
    dot -- no space, no hyphen. CA names files with both
    (``..._matched combat_01.anim``, ``.../nan-gau/...``; a Kislev folder is
    literally ``pistol_axe_and _shield``), so the regex stopped at the first
    such byte and the closure never saw the file. Measured on vanilla
    ``anim.pack`` (4,404 bins): this reader finds 1,762 references the regex
    missed (1,540 with a space, 222 with a hyphen); the regex found 4 this
    reader does not, and all 4 were false positives -- the ``.anim`` prefix of
    a ``.anim.meta`` string (the metadata file is not the animation).
    / 按长度前缀读 bin 内字符串；旧正则不含空格与连字符，这类路径整条看不见。
    """
    out = []
    low = blob.lower()
    p = low.find(b"animations")
    while p >= 0:
        if p >= 2:
            length = struct.unpack_from("<H", blob, p - 2)[0]
            s = blob[p:p + length]
            if (len(s) == length and s.lower().endswith(_ANIM_REF_SUFFIXES)
                    and all(32 <= c < 127 for c in s)):
                out.append(s.decode("ascii"))
        p = low.find(b"animations", p + 1)
    return out
