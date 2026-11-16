"""[AIR-DIVE-TAKEOFF-W1 2026-11-12] TEST-ONLY: how long each step of a flyer's
take-off took, from the "FL" lines of ld_entity_read.txt (format and the static
source of every field: pipelines/entity_read.lua header).

The take-off sequence (9.0.5, static read + measured 2026-11-12, run eV1):
  1. the order clears controller +8 (1 = stay down, 0 = fly);
  2. the per-tick executor 0x143050114 asks each entity to take off
     (0x14304cea0, FC phase 1 -> 2) once its +0x324 is 0 and FC +8 is clear;
  3. in phase 2 the per-FC update 0x143053bd4 re-arms FC +0x44 to 30 ticks
     (round(1000 / 100 ms) x 3.0) every tick the engaged check 0x143026588
     says busy, and counts it down by 1 otherwise;
  4. at FC +0x44 == 0, 0x14301b8d4 sets entity +0x104 = 2 and phase 3.
Per flyer unit, from --from-s (default its first FL tick) it prints when each
of these happened, per entity, and the hold = step 3's start minus step 2.

Fails (exit 1) on: no FLSITE ok line, a STOP/FAIL line, no FL lines.

usage: python -P tools/pipelines/takeoff_gate_report.py <ld_entity_read.txt slice> [--from-s S]
"""
import sys

FULL_HOLD = 30   # ticks: the re-armed value of FC +0x44 seen in game (3.0 s)


def parse(text):
    site, notes, t, units = None, [], None, {}
    for raw in (text or "").splitlines():
        p = raw.split(" ")
        if p[0] == "FLSITE":
            site = raw
        elif p[0] in ("STOP", "FAIL"):
            notes.append(raw)
        elif p[0] == "T" and len(p) == 2:
            t = int(float(p[1])) / 1000.0
        elif p[0] == "FL" and t is not None:
            kv = dict(x.split("=", 1) for x in p[2:6])
            ents = []
            for cell in p[6:]:
                f = cell.split(",")
                e = {"v104": int(f[1]), "s324": int(f[2])}
                if len(f) == 13:
                    e.update(k=int(f[5]), ph=int(f[6]), f44=int(f[7]), fc8=int(f[11]))
                ents.append(e)
            units.setdefault(p[1], []).append({
                "t": t, "c8": int(kv["c"].split(",")[0]), "melee": int(kv["mel"]), "ents": ents})
    return site, notes, units


def first(rows, pred):
    return next((r["t"] for r in rows if pred(r)), None)


def report(units, from_s=None):
    res = {}
    for uid, rows in units.items():
        if from_s is not None:
            rows = [r for r in rows if r["t"] >= from_s]
        if not rows:
            continue
        order = first(rows, lambda r: r["c8"] == 0)
        after = [r for r in rows if order is not None and r["t"] >= order]
        ents = []
        for i in range(len(rows[0]["ents"])):
            def e(r, i=i):
                return r["ents"][i] if i < len(r["ents"]) else {}
            asked = first(after, lambda r: e(r).get("ph") == 2)
            count = first(after, lambda r: e(r).get("ph") == 2 and e(r).get("f44", FULL_HOLD) < FULL_HOLD)
            up = first(after, lambda r: e(r).get("v104") == 2)
            ents.append({"asked": asked, "countdown": count, "airborne": up,
                         "hold": None if asked is None or count is None else round(count - asked, 1)})
        last_melee = max((r["t"] for r in after if r["melee"] > 0), default=None)
        res[uid] = {"order": order, "ents": ents, "last_melee": last_melee}
    return res


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    from_s = float(argv[argv.index("--from-s") + 1]) if "--from-s" in argv else None
    with open(argv[1], encoding="utf-8", errors="replace") as f:
        site, notes, units = parse(f.read())
    bad = []
    if not site or not site.startswith("FLSITE ok"):
        bad.append("no 'FLSITE ok' line: " + str(site))
    bad += notes
    if not units:
        bad.append("no FL lines")
    fmt = lambda v: "-" if v is None else f"{v:.1f}"
    for uid, r in sorted(report(units, from_s).items()):
        print(f"unit {uid}: order (C+8 -> 0) {fmt(r['order'])}s, unit +0x34b8 last > 0 at {fmt(r['last_melee'])}s")
        for i, e in enumerate(r["ents"]):
            print(f"   entity {i}: asked (phase 2) {fmt(e['asked'])}s, hold {fmt(e['hold'])}s, "
                  f"countdown from {fmt(e['countdown'])}s, airborne (+0x104 = 2) {fmt(e['airborne'])}s")
    for b in bad:
        print("FAIL:", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
