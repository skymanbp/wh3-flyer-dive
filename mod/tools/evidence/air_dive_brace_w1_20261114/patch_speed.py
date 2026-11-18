"""TEST-ONLY: opt-in battle speed for later batches (user reminder 2026-11-14: battle tests may run
fast-forward via CA's bm:modify_battle_speed(speed), lib_battle_manager.lua:1874).

series.py: a job flag --speed=N (never passed on to the autotest) writes N to ld_brace_speed.txt in
the game folder for that run; the file is removed in `finally` and listed in inflight.json so the
killed-run recovery removes it too. brace_probe.lua: on Deployed it reads that file and, when N > 1,
calls bm:modify_battle_speed(N, true) and logs `SPEED N`. Every recorder (this probe, the entity
reader, the driver) schedules with bm:repeat_callback, i.e. battle time -- to be PROVEN by a 1x / Nx
pair before any batch uses it."""
from pathlib import Path

H = Path(__file__).resolve().parent
s = (H / "series.py").read_text("utf-8")
assert "ld_brace_speed.txt" not in s
s = s.replace('''HELPER_PACKS = ("ld_air_dive_autotest.pack", "ld_entity_read.pack")''',
              '''HELPER_PACKS = ("ld_air_dive_autotest.pack", "ld_entity_read.pack")
SPEED_FILE = GAME / "ld_brace_speed.txt"''')
s = s.replace('''    gone = [n for n in rec["packs"] + list(HELPER_PACKS) if (DATA / n).exists() and _unlink_retry(DATA / n)]''',
              '''    gone = [n for n in rec["packs"] + list(HELPER_PACKS) if (DATA / n).exists() and _unlink_retry(DATA / n)]
    if SPEED_FILE.exists() and _unlink_retry(SPEED_FILE):
        gone.append(SPEED_FILE.name)''')
s = s.replace('''    for label, pack, scenario, flyers, *extra in jobs:''',
              '''    for label, pack, scenario, flyers, *extra in jobs:
        speed = [a.split("=", 1)[1] for a in extra if a.startswith("--speed=")]
        extra = [a for a in extra if not a.startswith("--speed=")]''')
s = s.replace('''        try:
            shutil.copyfile(SCR / "packs" / f"{pack}.pack", dst)''',
              '''        try:
            if speed:
                SPEED_FILE.write_text(str(float(speed[0])), encoding="utf-8")
            shutil.copyfile(SCR / "packs" / f"{pack}.pack", dst)''')
s = s.replace('''        finally:
            _unlink_retry(dst)''',
              '''        finally:
            _unlink_retry(dst)
            _unlink_retry(SPEED_FILE)''')
for n in ("SPEED_FILE.write_text", "_unlink_retry(SPEED_FILE)", 'a.startswith("--speed=")', "gone.append(SPEED_FILE.name)"):
    assert n in s, n
(H / "series.py").write_text(s, "utf-8")

t = (H / "brace_probe.lua").read_text("utf-8")
assert "ld_brace_speed.txt" not in t
old = '''bm:register_phase_change_callback("Deployed", function()
    mr.write(buf, l.mode_at, mr.uint32(1))'''
new = '''bm:register_phase_change_callback("Deployed", function()
    mr.write(buf, l.mode_at, mr.uint32(1))
    -- [opt-in] battle speed for this run (series.py --speed=N writes the file; absent = 1x)
    local sf = io.open("ld_brace_speed.txt", "r")
    if sf then
        local n = tonumber(sf:read("*l") or "")
        sf:close()
        if n and n > 1 then
            local sok, serr = pcall(function() bm:modify_battle_speed(n, true) end)
            record(("SPEED %s %s"):format(tostring(n), sok and "set" or ("failed " .. tostring(serr))))
        end
    end'''
assert t.count(old) == 1
t = t.replace(old, new)
(H / "brace_probe.lua").write_text(t, "utf-8", newline="\n")
print("patched")
