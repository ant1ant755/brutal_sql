"""In-memory model of a Postgres schema snapshot saved as JSON.

A snapshot file holds one ``PostgresSchemaObject``: the tables (with their columns,
keys and indexes) and the enums of a single database schema. Downstream code loads
a snapshot with ``PostgresSchemaObject.load_from_file(path)``.
"""

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

SNAPSHOT_FORMAT_VERSION = 1


class InvalidSchemaFileError(ValueError):
    """Raised when JSON text or a dict does not describe a valid schema snapshot."""


def _build_record[RecordType](record_class: type[RecordType], data: Any) -> RecordType:
    """Build a flat record class from a dict, or raise ``InvalidSchemaFileError``."""
    if not isinstance(data, dict):
        raise InvalidSchemaFileError(
            f"{record_class.__name__} must be a JSON object, got {type(data).__name__}"
        )
    try:
        return record_class(**data)
    except TypeError as error:
        raise InvalidSchemaFileError(
            f"Invalid {record_class.__name__}: {error}"
        ) from error


def _build_records[RecordType](
    record_class: type[RecordType], items: Any
) -> list[RecordType]:
    """Build a list of flat records from a list of dicts."""
    if not isinstance(items, list):
        raise InvalidSchemaFileError(
            f"Expected a list of {record_class.__name__}, got {type(items).__name__}"
        )
    return [_build_record(record_class, item) for item in items]


def _require_key(data: dict[str, Any], key: str, owner: str) -> Any:
    """Return ``data[key]``, or raise ``InvalidSchemaFileError`` naming the owner."""
    if key not in data:
        raise InvalidSchemaFileError(f"{owner} is missing the key '{key}'")
    return data[key]


@dataclass(frozen=True)
class ColumnDetails:
    """One column of a table."""

    name: str
    data_type: str
    is_nullable: bool
    default: str | None


@dataclass(frozen=True)
class PrimaryKeyDetails:
    """The primary key constraint of a table."""

    name: str | None
    column_names: list[str]


@dataclass(frozen=True)
class ForeignKeyDetails:
    """A foreign key from some columns of a table to columns of another table."""

    name: str | None
    column_names: list[str]
    referred_schema: str | None
    referred_table: str
    referred_column_names: list[str]
    on_delete: str | None
    on_update: str | None


@dataclass(frozen=True)
class UniqueConstraintDetails:
    """A unique constraint over one or more columns."""

    name: str | None
    column_names: list[str]


@dataclass(frozen=True)
class IndexDetails:
    """An index; ``column_names`` holds expressions for expression indexes."""

    name: str
    column_names: list[str]
    is_unique: bool


@dataclass(frozen=True)
class EnumDetails:
    """A Postgres enum type and its allowed values, in declaration order."""

    name: str
    values: list[str]


@dataclass(frozen=True)
class TableDetails:
    """A table with its columns, keys and indexes."""

    name: str
    columns: list[ColumnDetails]
    primary_key: PrimaryKeyDetails | None
    foreign_keys: list[ForeignKeyDetails]
    unique_constraints: list[UniqueConstraintDetails]
    indexes: list[IndexDetails]

    @classmethod
    def from_dict(cls, data: Any) -> Self:
        """Build a table from its JSON dict, or raise ``InvalidSchemaFileError``."""
        if not isinstance(data, dict):
            raise InvalidSchemaFileError("TableDetails must be a JSON object")
        owner = f"Table '{data.get('name')}'"
        primary_key = _require_key(data, "primary_key", owner)
        return cls(
            name=_require_key(data, "name", owner),
            columns=_build_records(ColumnDetails, _require_key(data, "columns", owner)),
            primary_key=(
                None
                if primary_key is None
                else _build_record(PrimaryKeyDetails, primary_key)
            ),
            foreign_keys=_build_records(
                ForeignKeyDetails, _require_key(data, "foreign_keys", owner)
            ),
            unique_constraints=_build_records(
                UniqueConstraintDetails, _require_key(data, "unique_constraints", owner)
            ),
            indexes=_build_records(IndexDetails, _require_key(data, "indexes", owner)),
        )


@dataclass(frozen=True)
class PostgresSchemaObject:
    """A snapshot of one Postgres schema: its tables and enums.

    ``fetched_at`` is the UTC time of the snapshot in ISO 8601 format.
    """

    database_name: str
    schema_name: str
    fetched_at: str
    tables: list[TableDetails]
    enums: list[EnumDetails]
    format_version: int = SNAPSHOT_FORMAT_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return the snapshot as plain dicts and lists, ready for ``json.dumps``."""
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        """Return the snapshot as indented JSON text."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Any) -> Self:
        """Build a snapshot from a dict, or raise ``InvalidSchemaFileError``."""
        if not isinstance(data, dict):
            raise InvalidSchemaFileError("A schema snapshot must be a JSON object")
        owner = "Schema snapshot"
        format_version = _require_key(data, "format_version", owner)
        if format_version != SNAPSHOT_FORMAT_VERSION:
            raise InvalidSchemaFileError(
                f"Unsupported snapshot format version: {format_version!r}"
            )
        tables = _require_key(data, "tables", owner)
        if not isinstance(tables, list):
            raise InvalidSchemaFileError("'tables' must be a list")
        return cls(
            database_name=_require_key(data, "database_name", owner),
            schema_name=_require_key(data, "schema_name", owner),
            fetched_at=_require_key(data, "fetched_at", owner),
            tables=[TableDetails.from_dict(table) for table in tables],
            enums=_build_records(EnumDetails, _require_key(data, "enums", owner)),
            format_version=format_version,
        )

    @classmethod
    def from_json(cls, text: str) -> Self:
        """Build a snapshot from JSON text, or raise ``InvalidSchemaFileError``."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise InvalidSchemaFileError(f"Not valid JSON: {error}") from error
        return cls.from_dict(data)

    @classmethod
    def load_from_file(cls, path: Path) -> Self:
        """Read a snapshot JSON file. Raises ``FileNotFoundError`` if it is missing."""
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    def find_table(self, table_name: str) -> TableDetails:
        """Return the table with this name, or raise ``KeyError``."""
        for table in self.tables:
            if table.name == table_name:
                return table
        raise KeyError(f"No table named '{table_name}' in schema '{self.schema_name}'")

    def find_enum(self, enum_name: str) -> EnumDetails:
        """Return the enum with this name, or raise ``KeyError``."""
        for enum in self.enums:
            if enum.name == enum_name:
                return enum
        raise KeyError(f"No enum named '{enum_name}' in schema '{self.schema_name}'")
