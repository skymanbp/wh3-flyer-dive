#!/usr/bin/env python3
"""TEST-ONLY: a pack holding a stand-in for the Mod Configuration Tool with the mod's settings (D10, D31).

The in-game checks of the breath-while-engaged switch and of the braced-line settings need set values without
clicking through MCT. This writes ``pipelines/breath_mct_stub.lua`` with its tags filled in as
``script/_lib/mod/zz_flyer_breath_mct_stub.lua`` and nothing else. Load it after the main pack
(``air_dive_autotest.py --pack-after``); with the real MCT loaded the stub does nothing.
[D31 / D51] ``--brace on|off`` with ``--k`` / ``--share`` / ``--reflect`` gives the braced-line options those values (the
omitted ones: the defaults of tools/lib/air_dive_rules.py); without ``--brace`` the stand-in holds none of them and
the battle uses the defaults.

usage: python -P tools/pipelines/build_breath_mct_stub.py --value on|off [--brace on|off [--k K] [--share S]
           [--reflect F]] --out <dir>/<name>.pack
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import rolepath  # noqa: E402,F401 -- because it puts the role dirs on sys.path

import argparse
from pathlib import Path

import air_dive_rules  # noqa: E402 -- because rolepath above puts lib/ on sys.path
from packfile import PACK_TYPE_MOD, write_pack_file

SOURCE = Path(__file__).resolve().parent / "breath_mct_stub.lua"
PACK_PATH = "script/_lib/mod/zz_flyer_breath_mct_stub.lua"
SHIPPED = ("flyer_dive_takeoff.pack",)
TAGS = {"@VALUE@": 2, "@BREATH_KEY@": 1, "@OTHER@": 1, "@SUMMARY@": 1}


def brace_values(on, k=None, share=None, reflect=None):
    """[D31 / D51] {MCT option key: value} for the braced-line options; refuses values outside the sliders' ranges."""
    r = air_dive_rules
    k = r.BRACE_MASS_K if k is None else k
    share = r.BRACE_SHARE_MIN if share is None else share
    reflect = r.REFLECT_FLYER_FACTOR if reflect is None else reflect
    r.brace_word(k, share)                                  # the range checks
    r.reflect_word(reflect)
    o = r.BRACE_MCT_OPTIONS
    return {o["on"]: bool(on), o["k"]: float(k), o["share"]: float(share), o["reflect"]: float(reflect)}


def _lua(values):
    def lit(v):
        return ("true" if v else "false") if isinstance(v, bool) else repr(v)
    return "{ " + ", ".join(f'["{k}"] = {lit(v)}' for k, v in sorted(values.items())) + " }"


def stub_entry(value, brace=None):
    """The stub script with its tags filled in (fail-closed). ``brace``: brace_values(...) or None."""
    if value not in ("on", "off"):
        raise SystemExit(f"[breath stub] REFUSING: value {value!r} is not on / off")
    text = SOURCE.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
    for tag, n in TAGS.items():
        if text.count(tag) != n:
            raise SystemExit(f"[breath stub] REFUSING: breath_mct_stub.lua must carry {tag} exactly {n} time(s)")
    summary = ("defaults (not held)" if not brace
               else ", ".join(f"{k}={v}" for k, v in sorted(brace.items())))
    text = (text.replace("@VALUE@", value).replace("@BREATH_KEY@", air_dive_rules.BREATH_SWITCH_MCT_OPTION)
            .replace("@OTHER@", _lua(brace or {})).replace("@SUMMARY@", summary))
    return PACK_PATH, text.encode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--value", required=True, choices=("on", "off"))
    ap.add_argument("--brace", choices=("on", "off"))
    ap.add_argument("--k", type=float)
    ap.add_argument("--share", type=float)
    ap.add_argument("--reflect", type=float)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if Path(args.out).name.lower() in SHIPPED:
        raise SystemExit(f"[breath stub] REFUSING: {args.out} is a shipped pack's name")
    if args.brace is None and (args.k is not None or args.share is not None or args.reflect is not None):
        raise SystemExit("[breath stub] REFUSING: --k / --share / --reflect need --brace on|off")
    brace = None if args.brace is None else brace_values(args.brace == "on", args.k, args.share, args.reflect)
    path, data = stub_entry(args.value, brace)
    size = write_pack_file(args.out, [(path, data)], PACK_TYPE_MOD)
    print(f"wrote {args.out} ({size} bytes): MCT stand-in, breath while engaged = {args.value}, braced line "
          f"{brace if brace else 'defaults (not held)'}")


if __name__ == "__main__":
    main()
