"""TEST-ONLY: add bp_ord, a logger at the entry of 0x143255718 (constructor of the order with vtable
0x143aed8c8, which replaces the charge order 0x143ade800 at the brake tick; callers 0x143076ebb,
0x143077337; rcx = entity + 0x330). Same 512-byte entry as bp_mel, own ring."""
from pathlib import Path

p = Path(__file__).resolve().parent / "brace_probe_asm.py"
s = p.read_text("utf-8")
assert "ORD_PATTERN" not in s
s = s.replace('''BYTES = MEL_RING_AT + MEL_SLOTS * MEL_ENTRY''', '''ORD_COUNT_AT, ORD_SLOTS, ORD_ENTRY = 28, 256, 512
ORD_RING_AT = MEL_RING_AT + MEL_SLOTS * MEL_ENTRY
BYTES = ORD_RING_AT + ORD_SLOTS * ORD_ENTRY
ORD_PATTERN = "48 83 EC 28 4D 8B C8 4C 8B D1 E8 39 54 E0 FF 48 8D 0D 9A 81 89 00"
ORD_STOLEN = "48 83 EC 28 4D 8B C8 4C 8B D1"''')
s = s.replace('''def mel_source():''', '''def ord_source():
    return mel_source().replace(f"[r10 + {MEL_COUNT_AT}]", f"[r10 + {ORD_COUNT_AT}]") \\
        .replace(f"and r11d, {MEL_SLOTS - 1}", f"and r11d, {ORD_SLOTS - 1}") \\
        .replace(f"add r11, {MEL_RING_AT}", f"add r11, {ORD_RING_AT}")


def check_ord(code):
    g = globals()
    saved = (g["MEL_COUNT_AT"], g["MEL_SLOTS"], g["MEL_RING_AT"])
    g["MEL_COUNT_AT"], g["MEL_SLOTS"], g["MEL_RING_AT"] = ORD_COUNT_AT, ORD_SLOTS, ORD_RING_AT
    try:
        return check_mel(code)
    finally:
        g["MEL_COUNT_AT"], g["MEL_SLOTS"], g["MEL_RING_AT"] = saved


def mel_source():''', 1)
s = s.replace('''    fails += check_mel(mel)''', '''    fails += check_mel(mel)
    osrc = ord_source()
    assert f"[r10 + {ORD_COUNT_AT}]" in osrc and f"add r11, {ORD_RING_AT}" in osrc
    orc = assemble(osrc)
    fails += check_ord(orc)''')
s = s.replace('''            bytes = '{template(mel)}' }}, }},''', '''            bytes = '{template(mel)}' }},
        {{ name = 'bp_ord', feature = 'brace_probe', kind = 'cave', pattern = '{ORD_PATTERN}', at = 0, expect = '{ORD_STOLEN}',
            bytes = '{template(orc)}' }}, }},''')
s = s.replace('''mel_slots = {MEL_SLOTS}, mel_entry = {MEL_ENTRY} }},''', '''mel_slots = {MEL_SLOTS}, mel_entry = {MEL_ENTRY},
        ord_count_at = {ORD_COUNT_AT}, ord_ring_at = {ORD_RING_AT}, ord_slots = {ORD_SLOTS}, ord_entry = {ORD_ENTRY} }},''')
for n in ("bp_ord", "check_ord(orc)", "ord_ring_at"):
    assert n in s, n
p.write_text(s, "utf-8")

q = Path(__file__).resolve().parent / "brace_probe.lua"
t = q.read_text("utf-8")
assert "drain_ord" not in t
t = t.replace('''"bp_refl", "bp_mel" }) do''', '''"bp_refl", "bp_mel", "bp_ord" }) do''')
t = t.replace('''bp_mel = { buf = buf } })''', '''bp_mel = { buf = buf }, bp_ord = { buf = buf } })''')
t = t.replace('''mr.write(buf, l.mel_count_at, mr.uint32(0))''', '''mr.write(buf, l.mel_count_at, mr.uint32(0))
mr.write(buf, l.ord_count_at, mr.uint32(0))''')
start = t.index("local mel_seen = 0")
end = t.index("local seen = 0")
block = t[start:end]
ordb = (block.replace("mel_seen", "ord_seen").replace("drain_mel", "drain_ord").replace("l.mel_", "l.ord_")
        .replace('"LOSTM %d"', '"LOSTO %d"').replace('("M %d', '("O %d'))
t = t[:end] + ordb + t[end:]
t = t.replace('''    pcall(drain_mel, ms)
''', '''    pcall(drain_mel, ms)
    pcall(drain_ord, ms)
''')
t = t.replace('''--   D <ms> <uid>''', '''--   O <ms> ... same as M, for the 0x143aed8c8 order constructor 0x143255718
--   D <ms> <uid>''', 1)
for n in ("drain_ord, ms", "bp_ord = { buf", "l.ord_ring_at", '("O %d'):
    assert n in t, n
q.write_text(t, "utf-8", newline="\n")
print("patched")
