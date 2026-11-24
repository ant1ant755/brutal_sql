"""Fetch the tables, keys, indexes and enums of a Postgres schema and save them as JSON.

The main entry point is ``fetch_and_save_schema``. It connects with the given URL and
credentials, reads the schema with SQLAlchemy's inspector, writes a timestamped
snapshot file into the staging folder and returns that file's path.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, inspect, make_url
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import (
    ArgumentError,
    InterfaceError,
    NoSuchModuleError,
    OperationalError,
    SQLAlchemyError,
)

from brutal_sql.db.schema_model import (
    ColumnDetails,
    EnumDetails,
    ForeignKeyDetails,
    IndexDetails,
    PostgresSchemaObject,
    PrimaryKeyDetails,
    TableDetails,
    UniqueConstraintDetails,
)
from brutal_sql.db.snapshot_file import save_schema_snapshot

CONNECT_TIMEOUT_SECONDS = 10


class SchemaFetchError(Exception):
    """Raised when the details of a schema cannot be fetched."""


class DatabaseConnectionError(SchemaFetchError):
    """Raised for a bad database URL, wrong credentials or an unreachable server."""


class SchemaNotFoundError(SchemaFetchError):
    """Raised when the target schema does not exist in the database."""


def fetch_and_save_schema(
    database_url: str,
    username: str,
    password: str,
    schema_name: str,
    staging_folder: Path,
) -> Path:
    """Fetch a schema's details, save them as JSON in the staging folder.

    ``database_url`` has no credentials, e.g. ``postgresql+psycopg://host:5432/db``;
    ``username`` and ``password`` override any that it does contain.
    Returns the path of the new snapshot file. Raises ``SchemaFetchError``
    (or a subclass) if the details cannot be fetched.
    """
    engine = _build_engine(database_url, username, password)
    try:
        schema_object = fetch_schema_details(engine, schema_name)
    finally:
        engine.dispose()
    return save_schema_snapshot(schema_object, Path(staging_folder))


def fetch_schema_details(engine: Engine, schema_name: str) -> PostgresSchemaObject:
    """Read the tables and enums of ``schema_name`` into a ``PostgresSchemaObject``."""
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            _ensure_schema_exists(inspector, schema_name)
            table_names = sorted(inspector.get_table_names(schema=schema_name))
            return PostgresSchemaObject(
                database_name=engine.url.database or "",
                schema_name=schema_name,
                fetched_at=datetime.now(UTC).isoformat(),
                tables=[
                    _read_table(inspector, schema_name, table_name)
                    for table_name in table_names
                ],
                enums=_read_enums(inspector, schema_name),
            )
    except SQLAlchemyError as error:
        raise _as_fetch_error(error, engine) from None


def _build_engine(database_url: str, username: str, password: str) -> Engine:
    """Create a Postgres engine with the credentials set on the URL."""
    try:
        url = make_url(database_url).set(username=username, password=password)
    except (ArgumentError, ValueError, TypeError):
        raise DatabaseConnectionError("Could not parse the database URL") from None
    if url.get_backend_name() != "postgresql":
        raise DatabaseConnectionError("Only postgresql:// database URLs are supported")
    try:
        return create_engine(
            url, connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS}
        )
    except (ArgumentError, NoSuchModuleError) as error:
        raise DatabaseConnectionError(f"Unusable database URL: {error}") from None


def _as_fetch_error(error: SQLAlchemyError, engine: Engine) -> SchemaFetchError:
    """Turn a SQLAlchemy error into a fetch error whose message hides the password."""
    safe_url = engine.url.render_as_string(hide_password=True)
    reason = str(getattr(error, "orig", None) or error).strip()
    if engine.url.password:
        reason = reason.replace(engine.url.password, "***")
    is_connection_failure = isinstance(error, (OperationalError, InterfaceError))
    error_class = DatabaseConnectionError if is_connection_failure else SchemaFetchError
    return error_class(f"Could not fetch schema from {safe_url}: {reason}")


def _ensure_schema_exists(inspector: Inspector, schema_name: str) -> None:
    """Raise ``SchemaNotFoundError`` if the schema is not in the database."""
    if not inspector.has_schema(schema_name):
        raise SchemaNotFoundError(f"Schema '{schema_name}' does not exist")


def _read_table(
    inspector: Inspector, schema_name: str, table_name: str
) -> TableDetails:
    """Read the columns, keys and indexes of one table."""
    unique_constraints = inspector.get_unique_constraints(table_name, schema_name)
    return TableDetails(
        name=table_name,
        columns=_read_columns(inspector, schema_name, table_name),
        primary_key=_read_primary_key(inspector, schema_name, table_name),
        foreign_keys=_read_foreign_keys(inspector, schema_name, table_name),
        unique_constraints=[
            UniqueConstraintDetails(
                name=constraint["name"], column_names=constraint["column_names"]
            )
            for constraint in unique_constraints
        ],
        indexes=_read_indexes(inspector, schema_name, table_name),
    )


def _read_columns(
    inspector: Inspector, schema_name: str, table_name: str
) -> list[ColumnDetails]:
    """Read the columns of one table, in table order."""
    return [
        ColumnDetails(
            name=column["name"],
            data_type=_describe_type(column["type"], inspector),
            is_nullable=column["nullable"],
            default=column.get("default"),
        )
        for column in inspector.get_columns(table_name, schema_name)
    ]


def _describe_type(column_type: Any, inspector: Inspector) -> str:
    """Render a column type the way Postgres spells it, e.g. ``VARCHAR(100)``."""
    try:
        return str(column_type.compile(dialect=inspector.dialect))
    except SQLAlchemyError:
        return str(column_type)


def _read_primary_key(
    inspector: Inspector, schema_name: str, table_name: str
) -> PrimaryKeyDetails | None:
    """Read the primary key of one table, or None if it has none."""
    constraint = inspector.get_pk_constraint(table_name, schema_name)
    if not constraint.get("constrained_columns"):
        return None
    return PrimaryKeyDetails(
        name=constraint.get("name"), column_names=constraint["constrained_columns"]
    )


def _read_foreign_keys(
    inspector: Inspector, schema_name: str, table_name: str
) -> list[ForeignKeyDetails]:
    """Read the foreign keys of one table."""
    return [
        ForeignKeyDetails(
            name=key.get("name"),
            column_names=key["constrained_columns"],
            referred_schema=key.get("referred_schema"),
            referred_table=key["referred_table"],
            referred_column_names=key["referred_columns"],
            on_delete=key.get("options", {}).get("ondelete"),
            on_update=key.get("options", {}).get("onupdate"),
        )
        for key in inspector.get_foreign_keys(table_name, schema_name)
    ]


def _read_indexes(
    inspector: Inspector, schema_name: str, table_name: str
) -> list[IndexDetails]:
    """Read the indexes of one table (not the primary key's own index)."""
    return [
        IndexDetails(
            name=index["name"],
            column_names=[
                column or expression
                for column, expression in zip(
                    index["column_names"],
                    index.get("expressions") or index["column_names"],
                )
            ],
            is_unique=index["unique"],
        )
        for index in inspector.get_indexes(table_name, schema_name)
    ]


def _read_enums(inspector: Inspector, schema_name: str) -> list[EnumDetails]:
    """Read the enum types defined in the schema."""
    enums = inspector.get_enums(schema=schema_name)
    return [
        EnumDetails(name=enum["name"], values=list(enum["labels"]))
        for enum in sorted(enums, key=lambda enum: enum["name"])
    ]
