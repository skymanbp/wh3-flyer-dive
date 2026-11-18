"""TEST-ONLY: check candidate unit keys against the installed db.pack (land_units / main_units / mounts / battle_entities)."""
import sys
sys.path.insert(0, r"D:/Projects/.worktrees/lore_disaster/air-dive-brace-w1/mod/tools")
import rolepath  # noqa
from pathlib import Path
import installed_db_table as idb
DB = Path(r"D:/SteamLibrary/steamapps/common/Total War WARHAMMER III/data/db.pack")
lu = {r["key"]: r for r in idb.decode_round_trip(DB, "land_units_tables", "probe")[0]}
mu = {r["unit"]: r for r in idb.decode_round_trip(DB, "main_units_tables", "probe")[0]}
mo = {r["key"]: r for r in idb.decode_round_trip(DB, "mounts_tables", "probe")[0]}
be = {r["key"]: r for r in idb.decode_round_trip(DB, "battle_entities_tables", "probe")[0]}
pat = sys.argv[1:] or []
for k in pat:
    hits = [k] if k in lu else [x for x in lu if k in x][:12]
    for h in hits:
        r = lu[h]; m = mu.get(h, {}); mt = r.get("mount") or ""
        ent = be.get(mo[mt]["entity"]) if mt in mo else be.get(r["man_entity"])
        print(f"{h:52s} men={m.get('num_men')} cat={m.get('caste')} mount={mt[:28]:28s} anim={(mo[mt]['animation'] if mt in mo else r['man_animation'])[:30]:30s} fly={ent and ent.get('fly_speed')} mass={ent and ent.get('mass')} size={ent and ent.get('size')} rad={ent and ent.get('radius')}")
