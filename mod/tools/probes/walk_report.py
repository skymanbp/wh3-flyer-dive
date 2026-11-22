"""Which entity / unit offset holds battle_entities.walk_speed (D64)? For every unit in walk_probe.txt, its body entity
in the installed db (the mount's entity when the unit has a mount, else its man_entity, as mass_lookup.py) gives
walk_speed, run_speed, charge_speed; an offset is a candidate when every unit's value there equals that number.
Units whose number is the same as another field's are kept (the check is over all units at once).
Usage: python -P walk_report.py <repo> <walk_probe.txt>"""
import sys
from pathlib import Path

REPO, PROBE = Path(sys.argv[1]), Path(sys.argv[2])
sys.path[:0] = [str(REPO / "mod" / "tools"), str(REPO / "mod" / "tools" / "lib"), str(REPO / "mod" / "tools" / "pipelines")]
import flyer_db
import build_air_dive_minimod as main_build

DB = main_build.GAME_DIR / "db.pack"
ents = {r["key"]: r for r in flyer_db.decode_round_trip(DB, "battle_entities_tables", "walk_report")[0]}
mounts = {r["key"]: r for r in flyer_db.decode_round_trip(DB, "mounts_tables", "walk_report")[0]}
units = {r["key"]: r for r in flyer_db.decode_round_trip(DB, "land_units_tables", "walk_report")[0]}
if not ents or not units:
    sys.exit("REFUSING: no db rows read")


def body(key):
    u = units[key]
    m = mounts.get(u.get("mount") or "", {})
    return ents.get(m.get("entity", ""), {}) or ents[u["man_entity"]]


rows = {"E": [], "U": []}
key_of = {}
for line in PROBE.read_text("utf-8").splitlines():
    p = line.split()
    if p and p[0] == "FAIL":
        sys.exit("REFUSING: " + line)
    if p and p[0] == "E":
        key_of[p[1]] = p[3]
        rows["E"].append((p[3], {int(o, 16): float(v) for o, v in (c.split(":") for c in p[4:])}))
    elif p and p[0] == "U" and p[1] in key_of:
        rows["U"].append((key_of[p[1]], {int(o, 16): float(v) for o, v in (c.split(":") for c in p[2:])}))
if not rows["E"]:
    sys.exit("REFUSING: no E lines")
keys = sorted({k for k, _ in rows["E"]})
for k in keys:
    b = body(k)
    print(f"{k:55s} body {b['key']:40s} walk {b['walk_speed']} run {b['run_speed']} charge {b['charge_speed']}")
for kind in ("E", "U"):
    for field in ("walk_speed", "run_speed", "charge_speed"):
        offs = None
        for k, vals in rows[kind]:
            want = body(k)[field]
            hit = {o for o, v in vals.items() if abs(v - want) < 1e-3}
            offs = hit if offs is None else offs & hit
        print(f"{kind} {field}: {len(rows[kind])} units, offsets equal in every one: "
              f"{', '.join(hex(o) for o in sorted(offs or ()))}")
