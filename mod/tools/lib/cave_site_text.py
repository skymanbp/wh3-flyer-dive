"""cave_site_text.py — text the memreader Plus cave generators share.

[TEST-REPAIR-1113 2026-11-13] pipelines/pin_cave_asm.py (flyer take-off) and
pipelines/dive_cave_asm.py (flyer physics dive) each carried a copy of the
cave template writer and of the Lua lines one cave entry takes in the
generated site table (`Py_Dup_Census` measured the pair). One home; each
generator passes its own placeholders and fields, so the generated
data/ld_flyer_*_site.lua bytes are unchanged.
/ 两个代码洞生成器共用的模板文本与位点表条目行。
"""
import struct


def bytes_template(code, buffer_placeholder, resume_placeholder, extra=None):
    """The site loader's cave template: hex bytes with {buf:8} / {resume:8}
    where the 8-byte placeholders sit; ``extra`` maps further placeholders to
    their tags (AIR-DIVE-RELEASE-W1: {orig:8}, the callee the loader reads)."""
    marks = {struct.pack("<Q", buffer_placeholder): "{buf:8}",
             struct.pack("<Q", resume_placeholder): "{resume:8}"}
    for placeholder, tag in (extra or {}).items():
        marks[struct.pack("<Q", placeholder)] = tag
    out, i = [], 0
    while i < len(code):
        tag = marks.get(code[i:i + 8])
        if tag:
            out.append(tag)
            i += 8
        else:
            out.append(f"{code[i]:02X}")
            i += 1
    return " ".join(out)


def cave_entry_lines(name, feature, pattern, at, expect, template, call_read_at=None):
    """The Lua lines of one `kind = 'cave'` site-loader entry; ``call_read_at``
    adds the loader read of the original call's target at that offset."""
    lines = ["        {",
             f"            name = '{name}', feature = '{feature}', kind = 'cave',",
             f"            pattern = '{pattern}',",
             f"            at = {at}, expect = '{expect}',"]
    if call_read_at is not None:
        lines.append(f"            reads = {{ orig = {{ type = 'call', at = {call_read_at} }} }},")
    return lines + [f"            bytes = '{template}',",
                    "        },"]
