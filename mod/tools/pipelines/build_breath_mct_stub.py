#!/usr/bin/env python3
"""TEST-ONLY: a pack holding a stand-in for the Mod Configuration Tool with one breath setting (D10).

The in-game check of the breath-while-engaged switch needs both settings without clicking through MCT. This
writes ``pipelines/breath_mct_stub.lua`` with ``@VALUE@`` filled in as
``script/_lib/mod/zz_flyer_breath_mct_stub.lua`` and nothing else. Load it after the main pack
(``air_dive_autotest.py --pack-after``); with the real MCT loaded the stub does nothing.

usage: python -P tools/pipelines/build_breath_mct_stub.py --value on|off --out <dir>/breath_mct_<value>.pack
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path

import argparse
from pathlib import Path

from packfile import PACK_TYPE_MOD, write_pack_file

SOURCE = Path(__file__).resolve().parent / "breath_mct_stub.lua"
PACK_PATH = "script/_lib/mod/zz_flyer_breath_mct_stub.lua"
SHIPPED = ("flyer_dive_takeoff.pack",)


def stub_entry(value):
    """The stub script with its value filled in (fail-closed)."""
    if value not in ("on", "off"):
        raise SystemExit(f"[breath stub] REFUSING: value {value!r} is not on / off")
    text = SOURCE.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
    if text.count("@VALUE@") != 2:
        raise SystemExit("[breath stub] REFUSING: breath_mct_stub.lua must carry @VALUE@ exactly twice")
    return PACK_PATH, text.replace("@VALUE@", value).encode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--value", required=True, choices=("on", "off"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if Path(args.out).name.lower() in SHIPPED:
        raise SystemExit(f"[breath stub] REFUSING: {args.out} is a shipped pack's name")
    size = write_pack_file(args.out, [stub_entry(args.value)], PACK_TYPE_MOD)
    print(f"wrote {args.out} ({size} bytes): MCT stand-in, breath while engaged = {args.value}")


if __name__ == "__main__":
    main()
