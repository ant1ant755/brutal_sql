"""Name a foreign key and tell whether it can be NULL, for its graph edges."""

from brutal_sql.db.table_metadata import ForeignKeyMetadata, TableMetadata
from brutal_sql.errors import ProcessingError


def edge_id_for(table: TableMetadata, foreign_key: ForeignKeyMetadata) -> str:
    """Return the foreign key's constraint name, or a stable id if it has none.

    The fallback is built from table and column names, e.g.
    orders(billing_address_id)->address(id).
    """
    if foreign_key.name and foreign_key.name.strip():
        return foreign_key.name.strip()
    source_columns = ",".join(foreign_key.column_names)
    target_columns = ",".join(foreign_key.referred_column_names)
    return (
        f"{table.name}({source_columns})"
        f"->{foreign_key.referred_table}({target_columns})"
    )


def is_foreign_key_nullable(
    table: TableMetadata, foreign_key: ForeignKeyMetadata
) -> bool:
    """True when any foreign key column of table can be NULL.

    Raises ProcessingError if a foreign key column is not a column of table.
    """
    nullable_by_name = {column.name: column.nullable for column in table.columns}
    missing = [
        name for name in foreign_key.column_names if name not in nullable_by_name
    ]
    if missing:
        raise ProcessingError(
            f"foreign key columns {missing!r} are not columns of table {table.name!r}"
        )
    return any(nullable_by_name[name] for name in foreign_key.column_names)
