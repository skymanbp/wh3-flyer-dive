"""AIR-DIVE-W1 coverage census: which flying units (vanilla and ours) play a
dive clip after this lane, and which do not and why. [2026-11-09]

Inputs: RPFM TSV exports of the installed db.pack (land_units, mounts,
battle_entities; exported with rpfm_cli into --tsv-dir) and the committed
assets/air_dive/air_dive_manifest.json. Our units and characters come from
unit_catalog / db_writer (source_key -> the vanilla unit they inherit).
A unit flies when its man_entity or its mount's entity has fly_speed > 0;
its flight table is the mount's animation when mounted, else man_animation.

usage: python -P flyer_coverage.py --tsv-dir <dir with db/<table>/data__.tsv>
writes flyer_coverage.json next to this script.
/ 覆盖普查：哪些飞行单位（原版与我方）会播放俯冲动作，哪些不会、为什么。
"""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent.parent
sys.path.insert(0, str(TOOLS))
# role bootstrap first: the flat module names below resolve through it
import rolepath

import unit_catalog
import db_writer
import air_dive_rules

_FLOAT_COLS = ("fly_speed", "flying_charge_speed", "acceleration",
               "charge_distance_commence_run", "charge_distance_adopt_charge_pose",
               "charge_distance_pick_target")


def _tsv(path):
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[2:]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tsv-dir", required=True)
    args = ap.parse_args()
    db = Path(args.tsv_dir) / "db"
    land = {r["key"]: r for r in _tsv(db / "land_units_tables" / "data__.tsv")}
    mounts = {r["key"]: r for r in _tsv(db / "mounts_tables" / "data__.tsv")}
    ents = {r["key"]: r for r in _tsv(db / "battle_entities_tables" / "data__.tsv")}
    manifest = json.loads((TOOLS.parent / "assets" / "air_dive" /
                           "air_dive_manifest.json").read_text("utf-8"))
    dived = {b["bin"].rsplit("/", 1)[1][:-4] for b in manifest["tables_overridden"]}
    skipped_tables = {}
    for s in manifest["skipped"]:
        for t in s["tables"]:
            skipped_tables[t.rsplit("/", 1)[1][:-4]] = s["reason"]

    def classify(unit_key):
        lu = land.get(unit_key)
        if lu is None:
            return None
        mount = mounts.get(lu.get("mount") or "")
        if mount:
            ent, table = mount["entity"], mount["animation"]
        else:
            ent, table = lu["man_entity"], lu["man_animation"]
        row = ents.get(ent)
        if row is None or float(row["fly_speed"]) <= 0:
            return None
        typed = {k: (float(v) if k in _FLOAT_COLS else v) for k, v in row.items()}
        if table in dived:
            status = "dive"
        elif table in skipped_tables:
            status = "kept: " + skipped_tables[table]
        else:
            status = "kept: table has no FLY_CHARGE_LAND slot"
        return {"entity": ent, "table": table, "dive": status,
                "data_cells": sorted(air_dive_rules.tuned_cells(typed))}

    vanilla = {k: c for k in sorted(land) if (c := classify(k))}
    ours = {}
    for rec in unit_catalog.UNIT_RECORDS:
        c = classify(rec.get("source_key") or "")
        if c:
            ours[rec["new_key"]] = dict(c, source=rec["source_key"])
    for spec in db_writer.iter_lore_disaster_character_specs():
        c = classify(spec.get("source_key") or "")
        if c:
            ours[spec["key"]] = dict(c, source=spec["source_key"])
    summary = {
        "vanilla_flying_units": len(vanilla),
        "vanilla_dive": sum(1 for c in vanilla.values() if c["dive"] == "dive"),
        "our_flying_units": len(ours),
        "our_dive": sum(1 for c in ours.values() if c["dive"] == "dive"),
    }
    out = {"summary": summary, "ours": ours, "vanilla": vanilla}
    (HERE / "flyer_coverage.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
        newline="\n")
    print(json.dumps(summary))
    for k, c in sorted(ours.items()):
        print(f"  {k:48s} {c['table']:34s} {c['dive']}")


if __name__ == "__main__":
    main()
