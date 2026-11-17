"""The DB-table primitives the flyer mini-mod build needs, in one file, so this repository builds the
Workshop pack on its own. [FLYER-FIX-1117 2026-11-17]

User ruling 2026-11-17: the flyer mod is developed in this repository and the Lore Disasters mod no longer
carries it, so the build may not import the main mod's DB writer (``db_writer`` loads the whole unit
catalogue and validator chain). Copied verbatim from Lore Disasters at 09ec5528c:

* ``FieldType``, ``encode_field``, ``_require_bytes``, ``_decode_string_u8``, ``decode_field``,
  ``DBTableWriter``, ``_decode_db_table_bytes`` and ``DB_FRAGMENT_GUID_NAMESPACE`` from
  ``tools/generators/dbw_binary.py``;
* ``installed_bytes``, ``_lossy_cells``, ``decode_round_trip``, ``decode_round_trip_with_replay`` from
  ``tools/lib/installed_db_table.py`` (``db_writer.X`` read as this module's X).

``SCHEMAS`` is not code here but data: ``data/flyer_db_schemas.json``, the writer schema of each of the 11
tables the build reads or writes, recorded from that same main build (``db_writer.SCHEMAS``, its runtime
derivations from RPFM's schema included) -- the build that reproduced the published pack 6382b46d... byte
for byte. Every installed table the build reads is still proved by re-encoding it byte-identical under its
installed GUID (``decode_round_trip_with_replay``), so a game patch that changes a table is refused here as
it was there. A table with no recorded schema is refused (``DBTableWriter`` / ``_decode_db_table_bytes``).
/ 建包所需的 DB 表读写原语（自主仓库照搬），表结构为记录下来的数据。
"""
import json
import struct
import uuid
from collections import OrderedDict
from pathlib import Path

from packfile import DBTableReader, PackFile

# [C12.63] Project-owned namespace: generated DB fragment GUIDs must remain
# stable across machines and rebuilds (uuid5 of table identity, not uuid4).
DB_FRAGMENT_GUID_NAMESPACE = uuid.UUID("b377aec4-f06b-5ce7-90b2-7fe1d8d86f31")
SCHEMA_FILE = Path(__file__).resolve().parent.parent / "data" / "flyer_db_schemas.json"


class FieldType:
    """DB table field type definitions — matches RPFM schema types."""
    STRING = "StringU8"          # uint16 byte-length + UTF-8 bytes
    BOOL = "Boolean"             # 1 byte (0x00/0x01)
    INT32 = "I32"                # 4 bytes LE signed
    INT64 = "I64"                # 8 bytes LE signed
    FLOAT32 = "F32"              # 4 bytes LE float
    FLOAT64 = "F64"              # 8 bytes LE double (unit_special_abilities v74)
    KEY = "StringU8_Key"         # Same encoding as STRING, marks a key field
    OPTIONAL_STRING = "OptionalStringU8"  # 1 byte presence flag + string if present


def encode_field(value, field_type):
    """Encode a single field value to binary.
    WH3 DB tables use UTF-8 strings with uint16 byte-length prefix."""
    if field_type in (FieldType.STRING, FieldType.KEY):
        if value is None:
            value = ""
        s = str(value)
        encoded = s.encode('utf-8')
        return struct.pack('<H', len(encoded)) + encoded

    elif field_type == FieldType.OPTIONAL_STRING:
        if value is None or value == "":
            return b'\x00'
        s = str(value)
        encoded = s.encode('utf-8')
        return b'\x01' + struct.pack('<H', len(encoded)) + encoded

    elif field_type == FieldType.BOOL:
        return struct.pack('B', 1 if value else 0)

    elif field_type == FieldType.INT32:
        return struct.pack('<i', int(value) if value is not None else 0)

    elif field_type == FieldType.INT64:
        return struct.pack('<q', int(value) if value is not None else 0)

    elif field_type == FieldType.FLOAT32:
        return struct.pack('<f', float(value) if value is not None else 0.0)

    elif field_type == FieldType.FLOAT64:
        return struct.pack('<d', float(value) if value is not None else 0.0)

    else:
        raise ValueError(f"Unknown field type: {field_type}")


def _require_bytes(data, pos, size, field_type):
    """Fail with a stable error instead of letting struct/unicode read past EOF."""
    if pos < 0:
        raise ValueError(f"Negative position {pos} while decoding {field_type}")
    end = pos + size
    if end > len(data):
        available = max(0, len(data) - pos)
        raise ValueError(
            f"Truncated {field_type} at offset {pos}: need {size} bytes, "
            f"have {available}"
        )
    return end


def _decode_string_u8(data, pos, field_type):
    length_end = _require_bytes(data, pos, 2, field_type)
    byte_len = struct.unpack('<H', data[pos:length_end])[0]
    payload_end = _require_bytes(data, length_end, byte_len, field_type)
    try:
        value = data[length_end:payload_end].decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"Invalid UTF-8 in {field_type} at offset {length_end}: {exc}"
        ) from exc
    return value, payload_end


def decode_field(data, pos, field_type):
    """Decode one WH3 schema field and return ``(value, new_pos)``.

    StringU8 lengths count encoded bytes, not Unicode characters. Every branch
    validates bounds so this function can be used as an independent artifact
    checker rather than accepting truncated data accidentally.
    """
    if field_type in (FieldType.STRING, FieldType.KEY):
        return _decode_string_u8(data, pos, field_type)

    if field_type == FieldType.OPTIONAL_STRING:
        marker_end = _require_bytes(data, pos, 1, field_type)
        present = data[pos]
        if present == 0:
            return None, marker_end
        if present != 1:
            raise ValueError(
                f"Invalid OptionalStringU8 presence marker 0x{present:02X} "
                f"at offset {pos}"
            )
        return _decode_string_u8(data, marker_end, field_type)

    if field_type == FieldType.BOOL:
        end = _require_bytes(data, pos, 1, field_type)
        raw = data[pos]
        if raw not in (0, 1):
            raise ValueError(f"Invalid Boolean value 0x{raw:02X} at offset {pos}")
        return bool(raw), end

    if field_type == FieldType.INT32:
        end = _require_bytes(data, pos, 4, field_type)
        return struct.unpack('<i', data[pos:end])[0], end

    if field_type == FieldType.INT64:
        end = _require_bytes(data, pos, 8, field_type)
        return struct.unpack('<q', data[pos:end])[0], end

    if field_type == FieldType.FLOAT32:
        end = _require_bytes(data, pos, 4, field_type)
        value = struct.unpack('<f', data[pos:end])[0]
        return round(value, 6), end

    if field_type == FieldType.FLOAT64:
        end = _require_bytes(data, pos, 8, field_type)
        return struct.unpack('<d', data[pos:end])[0], end

    raise ValueError(f"Unknown field type: {field_type}")




def _load_schemas(path=SCHEMA_FILE):
    """``{table: schema}`` from the recorded JSON; field order kept, every type a known FieldType."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    known = {v for k, v in vars(FieldType).items() if not k.startswith("_")}
    out = {}
    for table, s in raw.items():
        fields = OrderedDict((name, ftype) for name, ftype in s["fields"])
        bad = sorted({t for t in fields.values() if t not in known})
        if bad:
            raise RuntimeError(f"{path}: {table} has unknown field types {bad}")
        schema = {"version": s["version"], "version_marker": s["version_marker"], "fields": fields}
        for k in ("guid", "field_defaults"):
            if k in s:
                schema[k] = s[k]
        out[table] = schema
    return out


SCHEMAS = _load_schemas()


class DBTableWriter:
    """
    Write binary DB tables in WH3 format.

    Usage:
        writer = DBTableWriter("main_units_tables")
        writer.add_row({
            "unit": "ld_custom_emp_inf_reiksguard_foot",
            "caste": "Infantry",
            "land_unit": "ld_custom_emp_inf_reiksguard_foot",
            "num_men": 80,
            ...
        })
        data = writer.build()
    """

    def __init__(self, table_name, schema=None):
        self.table_name = table_name
        if schema is None:
            if table_name not in SCHEMAS:
                raise ValueError(f"No schema for table: {table_name}. "
                               f"Available: {list(SCHEMAS.keys())}")
            schema = SCHEMAS[table_name]

        self.version = schema["version"]
        # Some tables ship WITHOUT the FC FD FE FF version-marker block in
        # both vanilla and community packs (character_skill_node_sets /
        # _set_items — skill-tree spike 2026-07-16); emit the same shape.
        self.version_marker = schema.get("version_marker", True)
        # [C12.63] Deterministic fragment GUIDs: uuid4 made every rebuild churn
        # all DB binaries (and pack hashes), defeating reproducible builds.
        # Schema-hardcoded vanilla GUIDs still take precedence.
        fragment_identity = f"{table_name}:version={self.version}"
        self.guid = schema.get("guid") or str(
            uuid.uuid5(DB_FRAGMENT_GUID_NAMESPACE, fragment_identity)
        )
        self.fields = schema["fields"]
        self.field_defaults = dict(schema.get("field_defaults", {}))
        unknown_defaults = set(self.field_defaults) - set(self.fields)
        if unknown_defaults:
            raise ValueError(
                f"{table_name}: field_defaults name field(s) not in schema: "
                f"{sorted(unknown_defaults)}")
        self.rows = []
        self.raw_fields = []

    def add_row(self, data, raw_fields=None):
        """Add a row normalized to the schema's complete field order.

        ``raw_fields`` is an opt-in byte-passthrough for rows decoded from an
        installed table. It is intentionally unused by ordinary generators:
        callers explicitly name every field whose original wire encoding must
        be emitted verbatim.
        """
        # [C12.63] Fail loud on unknown keys: a misspelled field previously
        # vanished silently while the real column got a default.
        unknown = set(data) - set(self.fields)
        if unknown:
            raise ValueError(
                f"{self.table_name}: unknown field(s): {sorted(unknown)}"
            )
        raw_fields = dict(raw_fields or {})
        unknown_raw = set(raw_fields) - set(self.fields)
        if unknown_raw:
            raise ValueError(
                f"{self.table_name}: raw field(s) not in schema: "
                f"{sorted(unknown_raw)}"
            )
        for field_name, raw in raw_fields.items():
            if not isinstance(raw, bytes):
                raise TypeError(
                    f"{self.table_name}.{field_name}: raw field must be bytes")
        row = OrderedDict()
        for field_name, field_type in self.fields.items():
            if field_name in data:
                row[field_name] = data[field_name]
            elif field_name in self.field_defaults:
                # [DLC-W1 2026-10-12] A column whose vanilla convention is not
                # the type's zero value (the 9.0 `culture` column is "*" on
                # 9,673 of 9,693 rows, never "") is declared on the schema
                # once, so no producer can forget it and ship "".
                # / 原版惯例不是类型零值的列在表格定义上声明一次。
                row[field_name] = self.field_defaults[field_name]
            else:
                if field_type in (FieldType.STRING, FieldType.KEY):
                    row[field_name] = ""
                elif field_type == FieldType.BOOL:
                    row[field_name] = False
                elif field_type in (FieldType.INT32, FieldType.INT64):
                    row[field_name] = 0
                elif field_type in (FieldType.FLOAT32, FieldType.FLOAT64):
                    row[field_name] = 0.0
                elif field_type == FieldType.OPTIONAL_STRING:
                    row[field_name] = None
                else:
                    raise ValueError(
                        f"No default for field type {field_type}: "
                        f"{self.table_name}.{field_name}"
                    )
        self.rows.append(row)
        self.raw_fields.append(raw_fields)

    def catalog_entry(self, pack_path=None):
        """Return normalized expectations without re-decoding generated bytes."""
        return {
            "pack_path": pack_path or self.get_pack_path(),
            "table_name": self.table_name,
            "version": self.version,
            "version_marker": self.version_marker,
            # [REDS-W6 2026-09-21] The field map travels WITH the entry.
            # Consumers used to take `table_name` and look the schema back up
            # in SCHEMAS, which silently assumes every generator declares its
            # schema there -- and dbw_recruitment derives ten of its tables at
            # runtime from RPFM's .ron (seven landmark building chains, three
            # retinue/mercenary), so that lookup returned None and aborted
            # Localization_Contract's whole generated-row scan: 99 of 117
            # fragments went unscanned. This writer knows its own fields either
            # (`self.fields` is set from the schema in __init__, whichever path
            # supplied it), so it says so instead of making the reader guess.
            # / 字段表随条目走：读的人不必再回头去猜它是哪来的。
            "fields": OrderedDict(self.fields),
            "row_count": len(self.rows),
            "rows": [OrderedDict(row) for row in self.rows],
        }

    def build(self):
        """Build the binary DB table data."""
        result = bytearray()

        # GUID header — WH3 format: FD FE FC FF + UTF-16LE GUID + FC FD FE FF + version
        result.extend(b'\xFD\xFE\xFC\xFF')
        guid_utf16 = self.guid.encode('utf-16-le')
        result.extend(struct.pack('<H', len(self.guid)))  # char count (not byte count)
        result.extend(guid_utf16)

        # Version marker — WH3 format: FC FD FE FF + uint32 version + bool(01) + uint32 count
        if self.version_marker:
            result.extend(b'\xFC\xFD\xFE\xFF')
            result.extend(struct.pack('<I', self.version))
        result.append(0x01)  # Mystery bool — always 1 in all observed WH3 DB tables

        # Entry count
        result.extend(struct.pack('<I', len(self.rows)))

        # Row data
        for row, raw_fields in zip(self.rows, self.raw_fields):
            for field_name, field_type in self.fields.items():
                raw = raw_fields.get(field_name)
                if raw is not None:
                    result.extend(raw)
                else:
                    value = row.get(field_name)
                    result.extend(encode_field(value, field_type))

        return bytes(result)

    def get_pack_path(self):
        """Get the pack-internal path for this table."""
        return f"db/{self.table_name}/lore_disasters"


def _decode_db_table_bytes(data, table_name, source, capture_raw=False):
    """Decode one complete DB table fragment against the local writer schema.

    Raw field bytes are returned only when explicitly requested. The shared
    value decoder, including its historical float rounding, is unchanged.
    """
    schema = SCHEMAS.get(table_name)
    if schema is None:
        raise RuntimeError(f"no local schema for required {table_name}")
    try:
        header = DBTableReader.parse_binary_header(data)
    except Exception as exc:
        raise RuntimeError(f"{source}: cannot decode DB header: {exc}") from exc
    # [TEST-REPAIR-1113 2026-11-13] A markerless fragment serializes no
    # version, so the header's 0 means "absent"; for a schema that is itself
    # markerless (effects_tables v3, character_skill_node_sets_tables v2 --
    # vanilla ships both markerless) the logical version cannot be read from
    # the bytes and the exact-to-EOF decode below is the proof. Comparing the
    # absent 0 against the logical version left every such fragment
    # "undecodable" (4 of ours, then the Fellblade's effects a 5th). A marker
    # present on either side still has to agree exactly.
    # / 无标记片段不带版本号；双方都无标记时以解码到 EOF 为证。
    markerless_pair = (not header.get("version_marker")
                       and not schema.get("version_marker", True))
    if header["version"] != schema["version"] and not markerless_pair:
        raise RuntimeError(
            f"{source}: {table_name} version {header['version']} != "
            f"schema version {schema['version']}")
    if header["entry_count"] <= 0:
        raise RuntimeError(f"{source}: {table_name} has no rows")
    pos = header["data_start"]
    rows = []
    raw_rows = []
    for row_index in range(header["entry_count"]):
        row = {}
        raw_row = {}
        try:
            for field, field_type in schema["fields"].items():
                field_start = pos
                row[field], pos = decode_field(data, pos, field_type)
                if capture_raw:
                    raw_row[field] = data[field_start:pos]
        except Exception as exc:
            raise RuntimeError(
                f"{source}: cannot decode {table_name} row "
                f"{row_index}: {exc}") from exc
        rows.append(row)
        if capture_raw:
            raw_rows.append(raw_row)
    if pos != len(data):
        raise RuntimeError(
            f"{source}: decoded {pos} of {len(data)} bytes; "
            "schema/table drift")
    if capture_raw:
        return rows, raw_rows
    return rows


# ---- from tools/lib/installed_db_table.py
def installed_bytes(db_pack, table, tag):
    """The one `db/<table>/data__` fragment carried by `db_pack`, as bytes.

    Exactly one is the contract: zero means the table name is wrong or this
    pack is not the installed game, and more than one means the fragment to
    trust is ambiguous. Both are refusals, never a "pick the first".
    """
    pack = PackFile.open(str(db_pack))
    try:
        wanted = f"db\\{table}\\data__".lower()
        matches = [e for e in pack.entries
                   if e.path.replace("/", "\\").lower() == wanted]
        if len(matches) != 1:
            raise SystemExit(
                f"[{tag}] REFUSING: {db_pack} carries {len(matches)} "
                f"entries for {table}, expected exactly 1")
        return pack.read_file(matches[0])
    finally:
        pack.close()


# The only field types whose bytes our own decoder is allowed to fail to
# reproduce. `decode_field` rounds F32 to six decimals, so a float CA wrote as
# 0x3f666665 re-encodes as 0x3f666666 and a CORRECT schema is refused for a
# rounding artefact of ours. Nothing else gets that latitude.
_ROUNDING_TYPES = (FieldType.FLOAT32, FieldType.FLOAT64)


def _lossy_cells(table, tag, row, raw_row, fields):
    """The cells to replay verbatim: the ones our encoder cannot reproduce.

    [KITWEAP-W1 2026-09-21] This is PER CELL on purpose, and the first draft
    was not -- it handed the writer every field's original bytes, which makes
    the byte-identity test below **vacuous**: a schema wrong in a compensating
    way would replay the whole fragment and pass. That is the
    judgement-degradation shape §A14.4 forbids, and it would have silently
    weakened the two caches that were already relying on this proof.
    / 全字段回放会让「逐字节相等」变成永远成立，那就不是证明了。

    So every cell must be reproduced by `encode_field` from the decoded value,
    and a cell that is not is a REFUSAL unless its type is one whose decode is
    known lossy. Measured over every table this helper is used on: melee
    weapons 5 of 24,100 cells, all in one F32 column, and the garrison, skill
    and attribute tables (8 tables, 555,000+ cells) **0**. The exact-to-EOF
    walk and byte identity for all the other cells are what the proof rests on.
    """
    lossy = {}
    for field, field_type in fields.items():
        original = raw_row[field]
        if encode_field(row[field], field_type) == original:
            continue
        if field_type not in _ROUNDING_TYPES:
            raise SystemExit(
                f"[{tag}] REFUSING: {table}.{field} decodes to "
                f"{row[field]!r} but re-encodes to different bytes than the "
                f"installed table holds ({original!r}) -- that is a schema "
                "error, not a rounding artefact, and replaying the original "
                "bytes would hide it")
        lossy[field] = original
    return lossy or None


def decode_round_trip(db_pack, table, tag, remedy="before caching from it"):
    """`(rows, header)` of `table`, decoded with our schema and re-encoded.

    Returns the parsed header too because the garrison cache reads the
    version out of it; a caller that only wants rows drops it.
    """
    rows, header, _replay = decode_round_trip_with_replay(
        db_pack, table, tag, remedy)
    return rows, header


def decode_round_trip_with_replay(db_pack, table, tag,
                                  remedy="before caching from it"):
    """`(rows, header, replay)`: as `decode_round_trip`, plus per row the
    cells our encoder cannot reproduce (`_lossy_cells`, F32 rounding only).

    An emitter that re-ships an installed row whole (DB merge is whole-row
    replacement) passes `replay[i]` as `raw_fields`, so the cells it does not
    mean to change go out byte-identical to the game's. / 整行覆盖原版时，
    不改的格子按原字节发。
    """
    data = installed_bytes(db_pack, table, tag)
    name = Path(db_pack).name
    rows, raw = _decode_db_table_bytes(
        data, table, f"{name}:db/{table}/data__", capture_raw=True)
    header = DBTableReader.parse_binary_header(data)
    schema = dict(SCHEMAS[table])
    schema["guid"] = header["guid"]
    writer = DBTableWriter(table, schema=schema)
    fields = schema["fields"]
    replay = []
    for row, raw_row in zip(rows, raw):
        replay.append(_lossy_cells(table, tag, row, raw_row, fields))
        writer.add_row(row, raw_fields=replay[-1])
    rebuilt = writer.build()
    if rebuilt != data:
        first = next((i for i, (a, b) in enumerate(zip(rebuilt, data))
                      if a != b), min(len(rebuilt), len(data)))
        raise SystemExit(
            f"[{tag}] REFUSING: {table} does not round-trip — re-encoded "
            f"{len(rebuilt)} bytes vs installed {len(data)}, first "
            f"difference at byte {first}. The writer schema does not "
            f"describe what the engine reads; fix SCHEMAS "
            f"{remedy}.")
    return rows, header, replay
