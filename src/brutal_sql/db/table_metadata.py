"""Plain records of a table's columns, keys and indexes, as read from Postgres."""

from dataclasses import dataclass


def _require_name(value: object, field_name: str) -> None:
    """Raise ValueError unless value is a string with non-blank text."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-blank string, got {value!r}")


@dataclass(frozen=True)
class ColumnMetadata:
    """A column: name, SQL type, nullability and optional comment."""

    name: str
    data_type: str
    nullable: bool = True
    comment: str | None = None

    def __post_init__(self) -> None:
        _require_name(self.name, "column name")
        _require_name(self.data_type, "data_type")


@dataclass(frozen=True)
class IndexMetadata:
    """An index: its name, the columns or expressions it covers, and uniqueness."""

    name: str
    column_names: tuple[str, ...]
    unique: bool = False

    def __post_init__(self) -> None:
        _require_name(self.name, "index name")
        if not self.column_names:
            raise ValueError(f"index {self.name!r} needs at least one column")


@dataclass(frozen=True)
class ForeignKeyMetadata:
    """A foreign key from column_names to referred_column_names of another table."""

    column_names: tuple[str, ...]
    referred_schema: str
    referred_table: str
    referred_column_names: tuple[str, ...]
    name: str | None = None

    def __post_init__(self) -> None:
        _require_name(self.referred_schema, "referred_schema")
        _require_name(self.referred_table, "referred_table")
        if not self.column_names:
            raise ValueError("foreign key needs at least one column")
        if len(self.column_names) != len(self.referred_column_names):
            raise ValueError("foreign key column counts do not match")

    @property
    def is_composite(self) -> bool:
        """True when the key spans more than one column."""
        return len(self.column_names) > 1


@dataclass(frozen=True)
class TableMetadata:
    """A table with its columns, primary key, indexes and foreign keys."""

    name: str
    columns: tuple[ColumnMetadata, ...]
    primary_key: tuple[str, ...] = ()
    indexes: tuple[IndexMetadata, ...] = ()
    foreign_keys: tuple[ForeignKeyMetadata, ...] = ()
    comment: str | None = None

    def __post_init__(self) -> None:
        _require_name(self.name, "table name")
        if not self.columns:
            raise ValueError(f"table {self.name!r} needs at least one column")
