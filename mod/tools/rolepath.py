"""Role-directory import bootstrap (RESTRUCT-W1, ARCHITECTURE §A12.2).

The toolchain imports by FLAT module name (`import unit_catalog`) from
~250 call sites. Classifying the 159 remaining top-level files into the
role subdirectories the Filetree_Standard gate names
(catalogs / generators / gates / pipelines / lib) would break every one of
those imports, because a subdirectory is not on sys.path.

This module puts each role directory on sys.path, so the module namespace
stays flat while the FILES are classified. Import it once, early:

    import rolepath  # noqa: F401 — registers the role dirs on sys.path

Consumers that already do `sys.path.insert(0, TOOLS_DIR)` keep working
unchanged: this file lives in TOOLS_DIR, so it is importable the moment
that line runs, and `conftest.py` imports it for the whole test suite.

Why a path bootstrap and not a package: making tools a package would
require rewriting every `import X` to `from tools.role import X` across
~250 sites in one irreversible step. The path bootstrap reaches the same
directory classification with a change that is verifiable file by file.
/ 角色目录上 sys.path：文件按角色分类，模块名保持扁平，避免一次性重写
~250 处 import。
"""
from __future__ import annotations

import pathlib
import sys

TOOLS_DIR = pathlib.Path(__file__).resolve().parent

# The role vocabulary the Filetree_Standard gate already names. Directories
# that do not exist yet are skipped, so this file is safe to land before the
# migration and stays correct during it.
ROLE_DIRS = (
    "catalogs",     # single-source content data modules
    "generators",   # build-time emitters
    "gates",        # permanent validation + shared gate libs
    "pipelines",    # asset production pipelines
    "lib",          # shared primitives
    "console",      # dev-platform web console (§A13)
)
# `console` was missing here until 2026-08-16 while validate_mod's
# Filetree_Standard gate (`role_dirs`, §A12.5) already listed it — two
# spellings of one vocabulary, which is the drift RESTRUCT-W1 exists to
# close. The cost was concrete: resolve("build_polish_console.py") could
# not find a file the gate happily counted as classified.


def register() -> list[str]:
    """Put every existing role directory on sys.path; return what was added."""
    added = []
    for name in ROLE_DIRS:
        path = TOOLS_DIR / name
        if not path.is_dir():
            continue
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
            added.append(text)
    tools = str(TOOLS_DIR)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    return added


def resolve(name: str) -> pathlib.Path:
    """Absolute path of a tool file by name, wherever it is classified.

    Code that reads a tool's SOURCE (AST parses, spec_from_file_location,
    text scans) cannot go through the import system, so it used to join
    TOOLS_DIR with a bare file name. Those joins stop resolving the moment
    the file is filed into a role directory — and inside a fail-closed
    gate a missing path reads as a defect in the CONTENT, not as a stale
    path. Every such site must ask here instead.

    Falls back to the top-level path when the file is not classified (or
    does not exist), so the caller always gets a reportable path.
    / 按文件名解析工具源文件的真实位置，替代硬拼顶层路径。
    """
    if not name.endswith(".py"):
        name = f"{name}.py"
    direct = TOOLS_DIR / name
    if direct.is_file():
        return direct
    for role in ROLE_DIRS:
        candidate = TOOLS_DIR / role / name
        if candidate.is_file():
            return candidate
    return direct


DATA_DIRS = (
    "data",         # our own hand-maintained registries and manifests
    "vanilla",      # caches/indexes extracted from the shipped game
    "gen",          # generated products
    "baselines",    # frozen comparison baselines
)


def data(name: str) -> pathlib.Path:
    """Absolute path of a tool DATA file by name, wherever it is filed.

    Same hazard as resolve(), one level worse: data readers commonly treat a
    missing file as "no override / nothing to check" and carry on, so a path
    that stops resolving does not raise - it silently changes the answer.
    (Witnessed: the ward-budget gate anchored the override JSON on the
    imported catalog module's __file__; once catalogs were filed one level
    down, the overrides vanished and three characters "went over budget".)
    Callers that need the file MUST check .is_file() and fail loudly.
    / 数据文件按名解析：静默跳过会把路径断裂变成错误答案。
    """
    direct = TOOLS_DIR / name
    if direct.is_file():
        return direct
    for role in DATA_DIRS:
        candidate = TOOLS_DIR / role / name
        if candidate.is_file():
            return candidate
    return direct


#: Directory names under `tools/` that are NOT live tool source.
#: `evidence/` is the machine evidence tree (ARCHITECTURE A12): audit snapshots,
#: lanes' one-off scripts and temp roots, and FROZEN COPIES of files this repo
#: ships elsewhere. `__pycache__` is build output.
NON_SOURCE_DIRS = ("evidence", "__pycache__")


def is_tool_source(path) -> bool:
    """True when `path` is live tool source -- a file a tools-wide SOURCE
    discipline (a census, a single-source ratchet, an accessor-parity or
    path-resolution pin) may judge.

    Such a scanner means the live toolchain, not everything that happens to sit
    under `mod/tools`. The evidence tree breaks that assumption by construction:
    a frozen copy of a SHIPPED file parked there drags that file's own
    legitimate definitions into a census that never covered it. Witnessed three
    times on 2026-09-13 -- vm_docs (fixture tree under evidence/), vm_localization
    (a lane's temp clone), and the ARCH-W1f-2 seam census, which read the shipped
    framework's three real seam bodies as new carriers after L1/L3 froze
    `lore_disasters.lua` under `evidence/`.

    Paths outside TOOLS_DIR are accepted unchanged: a caller that mixes trees is
    asking about its own population, and silently dropping those files would be
    the fail-quiet this predicate exists to replace.
    / 工具树的源码纪律只管活工具源：证据树里有发货文件的冻结副本，扫到它等于把
    别处的正当定义算成本树的违规。
    """
    resolved = pathlib.Path(path).resolve()
    try:
        parts = resolved.relative_to(TOOLS_DIR).parts
    except ValueError:
        return True
    return not any(part in NON_SOURCE_DIRS for part in parts)


REGISTERED = register()
