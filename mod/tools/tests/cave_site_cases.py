"""cave_site_cases.py — what the two cave site-table suites share (not collected).

[TEST-REPAIR-1113 2026-11-13] test_flyer_takeoff_site.py and
test_flyer_dive_site.py each carried a copy of the site-table reader and of
the vendored memreader Plus loader's pattern limit (`Py_Dup_Census` measured
the pair). One home; each suite passes its own site file.
/ 两个代码洞位点表测试共用的读取与模式长度上限。
"""
import re
from pathlib import Path

MOD_DIR = Path(__file__).resolve().parents[2]
LOADER = (MOD_DIR / "assets" / "vendored_scripts" / "memreader_plus" / "script"
          / "memreader_plus" / "0_15_2" / "sites.lua")


def read_site_text(site_file):
    """The committed site table, LF line ends; a missing table is refused."""
    if not site_file.is_file():
        raise RuntimeError(f"required site table missing: {site_file}")
    return site_file.read_text(encoding="utf-8").replace("\r\n", "\n")


def loader_pattern_limit():
    """MAX_PATTERN_BYTES of the vendored loader; refused when it moved."""
    if not LOADER.is_file():
        raise RuntimeError(f"required vendored loader missing: {LOADER}")
    m = re.search(r"^local MAX_PATTERN_BYTES = (\d+)$", LOADER.read_text(encoding="utf-8"), re.M)
    if not m:
        raise RuntimeError(f"{LOADER}: MAX_PATTERN_BYTES not found (the loader changed)")
    return int(m.group(1))
