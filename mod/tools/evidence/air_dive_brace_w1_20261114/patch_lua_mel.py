from pathlib import Path
p = Path(__file__).resolve().parent / "brace_probe.lua"
s = p.read_text("utf-8")
assert "drain_mel" not in s
s = s.replace('''--   D <ms> <uid>''', '''--   M <ms> <seq> <uid> <ent8> <ret> <+0x26c> <vx> <vz> <+0x710> <+0x104> <[r8]> <[r8+4]> <slot> <stack hex>   (melee order ctor)
--   D <ms> <uid>''', 1)
s = s.replace('''for _, n in ipairs({ "bp_log", "bp_act1", "bp_act2", "bp_refl" }) do''',
              '''for _, n in ipairs({ "bp_log", "bp_act1", "bp_act2", "bp_refl", "bp_mel" }) do''')
s = s.replace('''bp_act2 = { buf = buf }, bp_refl = { buf = buf } })''',
              '''bp_act2 = { buf = buf }, bp_refl = { buf = buf }, bp_mel = { buf = buf } })''')
s = s.replace('''mr.write(buf, l.refl_count_at, mr.uint32(0))''',
              '''mr.write(buf, l.refl_count_at, mr.uint32(0))
mr.write(buf, l.mel_count_at, mr.uint32(0))''')
s = s.replace('''local seen = 0
local function tick()''', '''local mel_seen = 0
local function drain_mel(ms)
    local count = u32(mr.read(buf, l.mel_count_at, 4), 0)
    if count - mel_seen > l.mel_slots then
        record(("LOSTM %d"):format(count - mel_seen - l.mel_slots))
        mel_seen = count - l.mel_slots
    end
    while mel_seen < count do
        local at = l.mel_ring_at + (mel_seen % l.mel_slots) * l.mel_entry
        local e = mr.read(buf, at, 64)
        local ent = sub(hex(sub(e, 1, 8)), -8)
        record(("M %d %d %s %s %s %d %.2f %.2f %d %d %d %d %d %s"):format(ms, u32(e, 16), tostring(owner_of[ent] or "?"),
            ent, hex(sub(e, 9, 16)), mr.read_int32(buf, at + 20), mr.read_float(buf, at + 24),
            mr.read_float(buf, at + 28), mr.read_int32(buf, at + 32), mr.read_int32(buf, at + 36),
            mr.read_int32(buf, at + 40), mr.read_int32(buf, at + 44), e:byte(57) + e:byte(58) * 256,
            hexfwd(mr.read(buf, at + 64, 384))))
        mel_seen = mel_seen + 1
    end
end

local seen = 0
local function tick()''')
s = s.replace('''    pcall(drain_refl, ms)
''', '''    pcall(drain_refl, ms)
    pcall(drain_mel, ms)
''')
for n in ("drain_mel, ms", "bp_mel = { buf", "mel_count_at, mr.uint32(0)", '"bp_refl", "bp_mel"'):
    assert n in s, n
p.write_text(s, "utf-8", newline="\n")
print("ok")
