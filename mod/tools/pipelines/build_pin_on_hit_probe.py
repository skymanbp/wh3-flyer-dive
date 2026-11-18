"""TEST-ONLY packs for the flyer take-off comparisons.

[AIR-DIVE-TAKEOFF-W1 2026-11-12] Nothing here ships: ld_air_dive.pack is
built by build_air_dive_minimod.py and is not touched. Each pack carries the air-dive
movement recorder plus:

  --base probe   recorder only (vanilla flight data)
  --base full    the stand-alone air-dive content (flight tables, impact
                 stage) WITHOUT its take-off scripts, plus the balance
                 submod's breath flags (taken from the balance entries; the
                 balance pack's mass cut is not included, so a full base is
                 the main pack's flyer rows, uncut) [balance split 2026-11-17]
  --rule         + the shipped take-off scripts (battle entry, rule module,
                 generated site table: build_air_dive_minimod.takeoff_entries)
  --record       (with --rule) + pin_on_hit_probe.lua, which writes what the
                 caves recorded and answered to ld_pin_probe.txt and reads
                 ld_pin_probe.cfg ("window <ticks>", "mode <1|2>"; mode 2 =
                 hits recorded, the game's own engaged check answers: the
                 vanilla arm with the record)

Without --rule the pack leaves the game's take-off as it is (pure vanilla).

usage: build_pin_on_hit_probe.py --out X.pack --base probe|full
       [--rule [--record]] [--impact-stage B]
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import rolepath

import air_dive_rules
import build_air_dive_minimod as mini
from packfile import PACK_TYPE_MOD, write_pack_file

assert rolepath          # imported for its side effect: the role directories on sys.path
PROBE_SOURCE = HERE / "pin_on_hit_probe.lua"
PROBE_PACK_PATH = "script/battle/mod/ld_pin_on_hit_probe.lua"


def record_entry():
    return (PROBE_PACK_PATH, PROBE_SOURCE.read_text("utf-8").replace("\r\n", "\n").encode("utf-8"))


def full_entries():
    anims, _manifest = mini.anim_entries()
    dbs, _n_ent, _n_loco = mini.db_entries(mini.GAME_DIR / "db.pack")
    impact, repoint, _report = mini.impact_entries(mini.GAME_DIR / "db.pack")
    renamed, _counts = mini.rename_entries(mini.GAME_DIR / "db.pack", repoint)
    balance, _report = mini.balance_entries(mini.GAME_DIR / "db.pack", dbs)
    usage_path = f"db\\{air_dive_rules.USAGE_FLAGS_TABLE}\\{air_dive_rules.USAGE_FLAGS_FRAGMENT}"
    usage = [(p, d) for p, d in balance if p == usage_path]
    if len(usage) != 1:
        raise SystemExit(f"[pin_probe] REFUSING: the balance entries carry {len(usage)} {usage_path}")
    return anims + dbs + impact + renamed + usage


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", choices=("probe", "full"), required=True)
    ap.add_argument("--rule", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--impact-stage", choices=air_dive_rules.IMPACT_STAGES,
                    default=air_dive_rules.IMPACT_STAGE)
    args = ap.parse_args(argv)
    if args.record and not args.rule:
        raise SystemExit("[pin_probe] REFUSING: --record reads the caves' buffer, it needs --rule")
    air_dive_rules.IMPACT_STAGE = args.impact_stage
    entries = [mini.probe_entry("probe_only" if args.base == "probe" else "with_dive")]
    if args.base == "full":
        entries += full_entries()
    if args.rule:
        entries += mini.takeoff_entries()
    if args.record:
        entries.append(record_entry())
    size = write_pack_file(args.out, entries, PACK_TYPE_MOD)
    print(f"wrote {args.out} ({size} bytes): base {args.base}"
          + (f" impact {args.impact_stage}" if args.base == "full" else "")
          + (" + take-off rule scripts" if args.rule else "")
          + (" + take-off recorder" if args.record else ""))


if __name__ == "__main__":
    main()
