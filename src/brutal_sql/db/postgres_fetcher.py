"""Read tables, columns, keys and indexes of one Postgres schema."""

import logging
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine, Inspector
from sqlalchemy.exc import SQLAlchemyError

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.db.credential_masking import mask_credentials
from brutal_sql.db.table_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    IndexMetadata,
    TableMetadata,
)
from brutal_sql.errors import ProcessingError, SanitizedDriverError

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 5


def create_database_engine(settings: ConnectionSettings) -> Engine:
    """Create an engine for the settings. Its repr names the user: never log it."""
    if not isinstance(settings, ConnectionSettings):
        raise ProcessingError("settings must be ConnectionSettings")
    return create_engine(
        settings.to_sqlalchemy_url(),
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def fetch_schema_tables(settings: ConnectionSettings) -> list[TableMetadata]:
    """Connect, read every table of settings.schema_name, then close the engine."""
    engine = create_database_engine(settings)
    logger.info(
        "Reading schema %r on %s", settings.schema_name, settings.describe_database()
    )
    try:
        with engine.connect() as connection:
            return read_schema_tables(inspect(connection), settings.schema_name)
    except SQLAlchemyError as error:
        detail = mask_credentials(str(error), settings)
        message = f"reading {settings.describe_database()} failed: {detail}"
        cause = SanitizedDriverError(f"{type(error).__name__}: {detail}")
        raise ProcessingError(message) from cause
    finally:
        engine.dispose()


def read_schema_tables(inspector: Inspector, schema_name: str) -> list[TableMetadata]:
    """Return metadata for every table in the schema, sorted by table name."""
    if schema_name not in inspector.get_schema_names():
        raise ProcessingError(f"schema {schema_name!r} not found in the database")
    table_names = sorted(inspector.get_table_names(schema=schema_name))
    if not table_names:
        raise ProcessingError(f"schema {schema_name!r} has no tables")
    return [read_table_metadata(inspector, schema_name, name) for name in table_names]


def read_table_metadata(
    inspector: Inspector, schema_name: str, table_name: str
) -> TableMetadata:
    """Return the columns, primary key, indexes and foreign keys of one table."""
    primary_key = inspector.get_pk_constraint(table_name, schema=schema_name)
    return TableMetadata(
        name=table_name,
        columns=_read_columns(inspector, schema_name, table_name),
        primary_key=tuple(primary_key.get("constrained_columns") or ()),
        indexes=_read_indexes(inspector, schema_name, table_name),
        foreign_keys=_read_foreign_keys(inspector, schema_name, table_name),
        comment=inspector.get_table_comment(table_name, schema=schema_name)["text"],
    )


def _read_columns(
    inspector: Inspector, schema_name: str, table_name: str
) -> tuple[ColumnMetadata, ...]:
    """Read each column's name, compiled Postgres type, nullability and comment."""
    return tuple(
        ColumnMetadata(
            name=column["name"],
            data_type=column["type"].compile(dialect=inspector.dialect),
            nullable=bool(column["nullable"]),
            comment=column.get("comment"),
        )
        for column in inspector.get_columns(table_name, schema=schema_name)
    )


def _read_indexes(
    inspector: Inspector, schema_name: str, table_name: str
) -> tuple[IndexMetadata, ...]:
    """Read indexes; expression indexes list their expressions as columns."""
    return tuple(
        IndexMetadata(
            name=index["name"],
            column_names=_index_columns(index),
            unique=bool(index["unique"]),
        )
        for index in inspector.get_indexes(table_name, schema=schema_name)
    )


def _index_columns(index: Any) -> tuple[str, ...]:
    """Prefer 'expressions' (set for expression indexes) over column names."""
    names = index.get("expressions") or index["column_names"]
    return tuple(name for name in names if name is not None)


def _read_foreign_keys(
    inspector: Inspector, schema_name: str, table_name: str
) -> tuple[ForeignKeyMetadata, ...]:
    """Read foreign keys with the referred schema always spelled out."""
    foreign_keys = inspector.get_foreign_keys(
        table_name, schema=schema_name, postgresql_ignore_search_path=True
    )
    return tuple(
        ForeignKeyMetadata(
            column_names=tuple(key["constrained_columns"]),
            referred_schema=key.get("referred_schema") or schema_name,
            referred_table=key["referred_table"],
            referred_column_names=tuple(key["referred_columns"]),
            name=key.get("name"),
        )
        for key in foreign_keys
    )
