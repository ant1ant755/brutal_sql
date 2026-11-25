"""Database access: connection settings, credential masking, schema fetching."""

from brutal_sql.db.connection_settings import (
    ConnectionSettings,
    connection_settings_from_url,
)
from brutal_sql.db.credential_masking import mask_credentials
from brutal_sql.db.postgres_fetcher import (
    create_database_engine,
    fetch_schema_tables,
    read_schema_tables,
    read_table_metadata,
)
from brutal_sql.db.table_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    IndexMetadata,
    TableMetadata,
)

__all__ = [
    "ColumnMetadata",
    "ConnectionSettings",
    "ForeignKeyMetadata",
    "IndexMetadata",
    "TableMetadata",
    "connection_settings_from_url",
    "create_database_engine",
    "fetch_schema_tables",
    "mask_credentials",
    "read_schema_tables",
    "read_table_metadata",
]
