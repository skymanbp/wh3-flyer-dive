#!/usr/bin/env python3
"""TEST-ONLY: a built pack plus the update-1117 in-game probes, written as a new pack.

Nothing here ships. The base is a pack this repository built (normally the main pack built with
``build_air_dive_minimod.py --probe``, so it carries the movement recorder the autotest requires);
the output adds:

  --size-read   pipelines/flyer_size_probe.lua (part B: reads engine entity +0x74 of every flying
                model; memory read-only)
  --reflect     pipelines/reflect_probe.lua and the site table reflect_probe_asm.py generates
                (part C: two logger caves, needs keystone + unicorn to assemble and to pass its
                emulator check and negative controls before anything is written)
  --dive-mark   [d15-1118, D15] with --reflect: the base's dive site table is swapped for the one
                dive_mark_asm.py generates (the shipped dive caves plus a log-only dive mark; their
                emulator check, the shipped cases included, and the mark's mutants run first). The
                pack replaces the shipped one in the run; reflect_probe.lua hands the marks to rf_dmg.

The output name may not be the shipped pack's (flyer_dive_takeoff.pack).

usage: python -P tools/pipelines/build_probe_pack.py --base <built pack> --out <name>.pack
       [--size-read] [--reflect [--dive-mark]]
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path

import argparse
from pathlib import Path

from packfile import PACK_TYPE_MOD, PackFile, write_pack_file

HERE = Path(__file__).resolve().parent
SHIPPED = ("flyer_dive_takeoff.pack",)
SIZE_PROBE = ("script/battle/mod/flyer_size_probe.lua", HERE / "flyer_size_probe.lua")
REFLECT_PROBE = ("script/battle/mod/reflect_probe.lua", HERE / "reflect_probe.lua")
REFLECT_SITE = "script/reflect_probe/reflect_probe_site.lua"
DIVE_SITE = "script/campaign/flyer_dive/data/dive_site.lua"     # [d15-1118] swapped by --dive-mark


def swap_dive_site(entries):
    """[d15-1118] ``entries`` with the one dive site table replaced by the marked one; refuses unless the base
    carries exactly one."""
    import dive_mark_asm
    norm = [p.replace("\\", "/").lower() for p, _d in entries]
    at = [i for i, p in enumerate(norm) if p == DIVE_SITE]
    if len(at) != 1:
        raise SystemExit(f"[probe pack] REFUSING: the base carries {len(at)} {DIVE_SITE}, want 1")
    text, report = dive_mark_asm.build_site()
    print("[probe pack] dive mark:", report)
    out = list(entries)
    out[at[0]] = (out[at[0]][0], text.encode("utf-8"))
    return out


def _lua(path):
    return path.read_bytes().replace(b"\r\n", b"\n")


def probe_entries(size_read=False, reflect=False):
    out = []
    if size_read:
        out.append((SIZE_PROBE[0], _lua(SIZE_PROBE[1])))
    if reflect:
        import reflect_probe_asm
        text, report = reflect_probe_asm.build_site()
        print("[probe pack] reflect probe:", report)
        out += [(REFLECT_PROBE[0], _lua(REFLECT_PROBE[1])), (REFLECT_SITE, text.encode("utf-8"))]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size-read", action="store_true")
    ap.add_argument("--reflect", action="store_true")
    ap.add_argument("--dive-mark", action="store_true", help="[D15] with --reflect: the marked dive caves")
    args = ap.parse_args(argv)
    if args.dive_mark and not args.reflect:
        raise SystemExit("[probe pack] REFUSING: --dive-mark is read by the reflect probe; it needs --reflect")
    if Path(args.out).name.lower() in SHIPPED:
        raise SystemExit(f"[probe pack] REFUSING: {args.out} is a shipped pack's name")
    extra = probe_entries(args.size_read, args.reflect)
    if not extra:
        raise SystemExit("[probe pack] REFUSING: no probe chosen (--size-read / --reflect)")
    with PackFile.open(args.base) as base:
        entries = [(e.path, base.read_file(e)) for e in base.entries]
    if args.dive_mark:
        entries = swap_dive_site(entries)
    clash = {p for p, _d in entries} & {p for p, _d in extra}
    if clash:
        raise SystemExit(f"[probe pack] REFUSING: the base already ships {sorted(clash)}")
    size = write_pack_file(args.out, entries + extra, PACK_TYPE_MOD)
    print(f"wrote {args.out} ({size} bytes): {len(entries)} base files + {[p for p, _d in extra]}")


if __name__ == "__main__":
    main()
