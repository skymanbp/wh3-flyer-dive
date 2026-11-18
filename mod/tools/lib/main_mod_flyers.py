"""The recorded snapshot of the main mod's flying bodies and donor flyers (``data/main_mod_flyers.json``).

Owner's order 2026-11-17: this repository builds, re-derives and tests on its own and never reads the
Lore Disasters checkout. The rows the air dive used to read from that checkout's staged donor closures
(``mod/assets/vendored_chars/<closure>/tsv/db/...``) are kept here as a snapshot, labelled as input for
the future main-mod adapter pack (a separate pack for the main mod's own bodies). The flyer pack ships
none of these bodies; ``pipelines/air_dive.py`` still counts them so the staged tables stay the ones the
main mod's units ride (``census_riders``: one renamed copy per plough speed among a table's riders).

What the file holds, per donor closure and source table (the source path, its sha256 and row count are
recorded; the snapshot's own header names the other repository's commit and the date):

* ``battle_entities_tables``: the rows that fly (``air_dive_rules.is_flyer``), every column, with the
  source's column header and ``#table;version`` marker, so :func:`entities_tsv_texts` rebuilds a TSV in
  the source's own format;
* ``land_units_tables`` / ``mounts_tables``: ``(unit key, animation table, battle entity)`` for the rows
  whose animation table is a flight table (slot 104) of the installed game when the snapshot was taken.

A missing or malformed snapshot is a refusal (:class:`SnapshotError`): the census would otherwise lose
riders silently and the staged tables would change.
/ 主模组飞兽与捐赠方飞兽的数据快照（供将来的主模组适配包用），本仓库不再读另一个仓库。
"""
import json
import re
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parent.parent / "data" / "main_mod_flyers.json"
ENTITY_TABLE = "battle_entities_tables"
RIDER_TABLES = {
    "land_units_tables": ("key", "man_animation", "man_entity"),
    "mounts_tables": ("key", "animation", "entity"),
}
ENTITY_COLUMNS = ("key", "size", "fly_speed", "type")
_SHA = re.compile(r"[0-9a-f]{64}")

_CACHE = {}


class SnapshotError(RuntimeError):
    """The snapshot is missing or does not have the recorded shape."""


def _need(cond, what, path):
    if not cond:
        raise SnapshotError(f"[main_mod_flyers] REFUSING: {path}: {what}")


def load(path=SNAPSHOT):
    """The validated snapshot (cached per path)."""
    path = Path(path)
    key = str(path.resolve())
    if key in _CACHE:
        return _CACHE[key]
    _need(path.is_file(), "snapshot file missing", path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SnapshotError(f"[main_mod_flyers] REFUSING: {path}: not JSON ({exc})") from exc
    _need(isinstance(data, dict), "top level is not an object", path)
    for field in ("about", "taken_from", "closures"):
        _need(field in data, f"no {field!r}", path)
    taken = data["taken_from"]
    _need(isinstance(taken, dict) and all(taken.get(k) for k in ("repository", "commit", "date")),
          "taken_from lacks repository / commit / date", path)
    closures = data["closures"]
    _need(isinstance(closures, dict) and closures, "no closures", path)
    counts = {ENTITY_TABLE: 0, **{t: 0 for t in RIDER_TABLES}}
    for name, tables in closures.items():
        _need(isinstance(tables, dict) and tables, f"closure {name!r} holds no table", path)
        for table, rec in tables.items():
            where = f"{name}/{table}"
            _need(table in counts, f"{where}: unknown table", path)
            _need(isinstance(rec, dict) and isinstance(rec.get("source"), str) and rec["source"],
                  f"{where}: no source", path)
            _need(isinstance(rec.get("sha256"), str) and _SHA.fullmatch(rec["sha256"]),
                  f"{where}: no sha256", path)
            rows = rec.get("rows")
            _need(isinstance(rows, list) and rows, f"{where}: no rows", path)
            if table == ENTITY_TABLE:
                header = rec.get("header")
                _need(isinstance(header, list) and all(c in header for c in ENTITY_COLUMNS),
                      f"{where}: header lacks one of {ENTITY_COLUMNS}", path)
                _need(isinstance(rec.get("marker"), str) and rec["marker"].startswith("#"),
                      f"{where}: no #table;version marker", path)
                width = len(header)
            else:
                _need(tuple(rec.get("columns", ())) == RIDER_TABLES[table],
                      f"{where}: columns are not {RIDER_TABLES[table]}", path)
                width = 3
            for row in rows:
                _need(isinstance(row, list) and len(row) == width
                      and all(isinstance(c, str) for c in row), f"{where}: malformed row {row!r}", path)
            counts[table] += len(rows)
    for table, n in counts.items():
        _need(n, f"no {table} rows in any closure", path)
    _CACHE[key] = data
    return data


def entity_rows(path=SNAPSHOT):
    """``[(source, row dict)]``: every recorded flying battle_entities row, cells as the TSV text."""
    out = []
    for _name, tables in sorted(load(path)["closures"].items()):
        rec = tables.get(ENTITY_TABLE)
        if rec:
            out += [(rec["source"], dict(zip(rec["header"], row))) for row in rec["rows"]]
    return out


def rider_pairs(table, path=SNAPSHOT):
    """``[(animation table, battle entity)]`` of one rider table (``land_units_tables`` /
    ``mounts_tables``) over every closure."""
    if table not in RIDER_TABLES:
        raise SnapshotError(f"[main_mod_flyers] REFUSING: {table!r} is not a rider table")
    out = []
    for _name, tables in sorted(load(path)["closures"].items()):
        rec = tables.get(table)
        if rec:
            out += [(row[1], row[2]) for row in rec["rows"]]
    return out


def entities_tsv_texts(path=SNAPSHOT):
    """``{source: TSV text}``: each closure's recorded flying rows in the source's RPFM format (column
    header, ``#table;version`` marker, one row per line, LF), as ``air_dive_rules.
    rewrite_vendored_entities_tsv`` reads a staged TSV."""
    out = {}
    for _name, tables in sorted(load(path)["closures"].items()):
        rec = tables.get(ENTITY_TABLE)
        if rec:
            lines = ["\t".join(rec["header"]), rec["marker"], *("\t".join(r) for r in rec["rows"])]
            out[rec["source"]] = "\n".join(lines) + "\n"
    return out
