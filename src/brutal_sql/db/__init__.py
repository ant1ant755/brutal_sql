"""Database utilities: fetch a Postgres schema's details and model them as JSON."""

from brutal_sql.db.schema_fetcher import (
    DatabaseConnectionError,
    SchemaFetchError,
    SchemaNotFoundError,
    fetch_and_save_schema,
    fetch_schema_details,
)
from brutal_sql.db.schema_model import InvalidSchemaFileError, PostgresSchemaObject
from brutal_sql.db.snapshot_file import save_schema_snapshot

__all__ = [
    "DatabaseConnectionError",
    "InvalidSchemaFileError",
    "PostgresSchemaObject",
    "SchemaFetchError",
    "SchemaNotFoundError",
    "fetch_and_save_schema",
    "fetch_schema_details",
    "save_schema_snapshot",
]
