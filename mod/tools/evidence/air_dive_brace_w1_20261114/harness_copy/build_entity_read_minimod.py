#!/usr/bin/env python3
"""Per-soldier battle reader -- the TEST-ONLY mini-mod pack. [ENGINE-ENTITY-READ-W1 2026-11-11]

User 2026-11-11: a minimod that reads each soldier's position, hit points and
knock state in battle, for the automated battle tests only. It is never part
of ld_mod.pack and never shipped to players. Read-only: the recorder reads
game memory through memreader Plus and writes none.

The pack holds:

* ``script/battle/mod/ld_entity_read.lua`` -- ``pipelines/entity_read.lua``
  (offsets and checks documented in its header; writes ld_entity_read.txt
  next to Warhammer3.exe, read by ``pipelines/entity_read_report.py``);
* memreader Plus 0_15_2, the same sha256-pinned files ld_mod.pack carries
  (``build_pack.collect_vendored_script_files``): a test enables only its own
  packs, so the reader cannot lean on ld_mod.pack being on;
* ``script/ld_entity_read/LICENSE_derpy_third_person.txt`` -- the MIT text of
  Derpy's Third-Person Battles (DerpyNewb), whose per-model offsets the
  recorder uses (credit: docs/CONTENT_LEDGER.md §C6).

Usage:  python -P tools/pipelines/build_entity_read_minimod.py --out <path.pack> [--dump]
        --dump: [AIR-DIVE-CONTINUOUS-W1] also write the raw entity dump of every
        single-model unit (D lines, see entity_read.lua); off by default
        (deliberately no default: this pack is not part of the mod build)
/ 测试专用小模组：逐兵模读位置、血量、击倒状态；不进主包、不发给玩家。
"""
import os as _ld_os, sys as _ld_sys
_ld_sys.path.insert(0, r"D:\Projects\.worktrees\lore_disaster\air-dive-continuous-w1\mod\tools")  # [BRACE-W1 scratch copy]
import rolepath

import argparse
from pathlib import Path

from packfile import PACK_TYPE_MOD, write_pack_file

MOD_DIR = Path(rolepath.__file__).resolve().parent.parent
RECORDER_SOURCE = Path(__file__).resolve().parent / "entity_read.lua"
RECORDER_PACK_PATH = "script/battle/mod/ld_entity_read.lua"   # Lua: forward slashes
LICENSE_SOURCE = MOD_DIR / "assets" / "entity_read" / "LICENSE_derpy_third_person.txt"
LICENSE_PACK_PATH = "script/ld_entity_read/LICENSE_derpy_third_person.txt"
MEMREADER_ROOT = "script/_lib/mod/!memreader_plus_boot.lua"


def memreader_entries():
    """The vendored memreader Plus files, verified by build_pack (fail-closed)."""
    _ld_sys.path.insert(0, str(MOD_DIR))
    import build_pack  # noqa: E402  -- needs MOD_DIR on sys.path first
    out = []
    for disk, pack_path in build_pack.collect_vendored_script_files():
        out.append((pack_path, Path(disk).read_bytes()))
    if not any(p.replace("\\", "/").lower() == MEMREADER_ROOT.lower() for p, _ in out):
        raise SystemExit("[entity_read_minimod] REFUSING: the vendored scripts carry "
                         f"no {MEMREADER_ROOT}")
    return out


DUMP_OFF, DUMP_ON = b"local DUMP_ON = false\n", b"local DUMP_ON = true\n"


def recorder_entries(dump=False):
    text = RECORDER_SOURCE.read_bytes()
    if dump:
        text = text.replace(b"\r\n", b"\n")
        if text.count(DUMP_OFF) != 1:
            raise SystemExit("[entity_read_minimod] REFUSING: entity_read.lua must carry "
                             "exactly one 'local DUMP_ON = false' line")
        text = text.replace(DUMP_OFF, DUMP_ON)
    if b"ld_entity_read.txt" not in text or b"mr.write" in text:
        raise SystemExit("[entity_read_minimod] REFUSING: entity_read.lua must name "
                         "ld_entity_read.txt and never call mr.write (read-only)")
    lic = LICENSE_SOURCE.read_bytes()
    if b"MIT License" not in lic or b"DerpyNewb" not in lic:
        raise SystemExit(f"[entity_read_minimod] REFUSING: {LICENSE_SOURCE} is not "
                         "Derpy's MIT text")
    return [(RECORDER_PACK_PATH, text), (LICENSE_PACK_PATH, lic)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--dump", action="store_true",
                    help="also dump each single-model unit's entity bytes (D lines)")
    args = ap.parse_args(argv)
    entries = recorder_entries(args.dump) + memreader_entries()
    size = write_pack_file(args.out, entries, PACK_TYPE_MOD)
    print(f"wrote {args.out} ({size} bytes): entity reader + "
          f"{len(entries) - 2} memreader Plus files")


if __name__ == "__main__":
    main()
