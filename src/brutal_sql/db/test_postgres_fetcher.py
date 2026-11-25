"""Unit tests for the Postgres fetcher, using a fake inspector (no database)."""

from contextlib import nullcontext
from typing import Any

import pytest
from sqlalchemy import Integer, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError

from brutal_sql.db import postgres_fetcher
from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.db.postgres_fetcher import (
    create_database_engine,
    fetch_schema_tables,
    read_schema_tables,
    read_table_metadata,
)
from brutal_sql.errors import ProcessingError

SECRET_USER = "fakeuserfakeuser"
SECRET_PASSWORD = "fakepasswordfakepassword"


class FakeInspector:
    """Answers the Inspector calls the fetcher makes, from canned data."""

    dialect = postgresql.dialect()

    def __init__(self, schemas: dict[str, list[str]]) -> None:
        self.schemas = schemas

    def get_schema_names(self) -> list[str]:
        return list(self.schemas)

    def get_table_names(self, schema: str) -> list[str]:
        return self.schemas[schema]

    def get_columns(self, table_name: str, schema: str) -> list[dict[str, Any]]:
        return [
            {"name": "id", "type": Integer(), "nullable": False, "comment": None},
            {"name": "cid", "type": Text(), "nullable": True, "comment": "cookie id"},
        ]

    def get_pk_constraint(self, table_name: str, schema: str) -> dict[str, Any]:
        return {"constrained_columns": ["id"], "name": f"{table_name}_pkey"}

    def get_indexes(self, table_name: str, schema: str) -> list[dict[str, Any]]:
        return [
            {"name": "cid_idx", "column_names": ["cid"], "unique": True},
            {
                "name": "lower_cid_idx",
                "column_names": [None],
                "expressions": ["lower(cid)"],
                "unique": False,
            },
        ]

    def get_foreign_keys(self, table_name: str, schema: str, **_: Any) -> list[Any]:
        return [
            {
                "name": "orders_cid_fkey",
                "constrained_columns": ["cid"],
                "referred_schema": None,
                "referred_table": "cookies",
                "referred_columns": ["id"],
            }
        ]

    def get_table_comment(self, table_name: str, schema: str) -> dict[str, Any]:
        return {"text": None}


def make_settings() -> ConnectionSettings:
    return ConnectionSettings(
        "db.local", 5432, "shop", "public", SECRET_USER, SECRET_PASSWORD
    )


def test_read_table_metadata_reads_columns_keys_and_indexes() -> None:
    table = read_table_metadata(FakeInspector({"shop": ["orders"]}), "shop", "orders")
    assert [column.name for column in table.columns] == ["id", "cid"]
    assert table.columns[0].data_type == "INTEGER" and not table.columns[0].nullable
    assert table.columns[1].comment == "cookie id"
    assert table.primary_key == ("id",)
    assert [index.column_names for index in table.indexes] == [
        ("cid",),
        ("lower(cid)",),
    ]
    foreign_key = table.foreign_keys[0]
    assert foreign_key.referred_schema == "shop"
    assert (foreign_key.referred_table, foreign_key.column_names) == (
        "cookies",
        ("cid",),
    )


def test_read_table_metadata_rejects_unknown_table() -> None:
    class MissingTableInspector(FakeInspector):
        def get_pk_constraint(self, table_name: str, schema: str) -> dict[str, Any]:
            raise KeyError(table_name)

    with pytest.raises(KeyError):
        read_table_metadata(MissingTableInspector({"shop": []}), "shop", "ghost")


def test_read_schema_tables_sorts_tables_by_name() -> None:
    inspector = FakeInspector({"shop": ["orders", "customers"]})
    tables = read_schema_tables(inspector, "shop")  # type: ignore[arg-type]
    assert [table.name for table in tables] == ["customers", "orders"]


def test_read_schema_tables_rejects_missing_schema() -> None:
    with pytest.raises(ProcessingError, match="not found"):
        read_schema_tables(FakeInspector({"shop": ["orders"]}), "sales")


def test_read_schema_tables_rejects_empty_schema() -> None:
    with pytest.raises(ProcessingError, match="no tables"):
        read_schema_tables(FakeInspector({"shop": []}), "shop")


def test_create_database_engine_targets_psycopg() -> None:
    engine = create_database_engine(make_settings())
    assert engine.url.drivername == "postgresql+psycopg"
    engine.dispose()


def test_create_database_engine_rejects_non_settings() -> None:
    with pytest.raises(ProcessingError):
        create_database_engine("postgresql://db.local/shop")  # type: ignore[arg-type]


class FakeEngine:
    """Engine stand-in whose connections do nothing."""

    disposed = False

    def connect(self) -> Any:
        return nullcontext()

    def dispose(self) -> None:
        self.disposed = True


def failing_inspect(connection: Any) -> None:
    detail = f'password authentication failed for user "{SECRET_USER}"'
    raise OperationalError(f"connect {SECRET_PASSWORD}", {}, Exception(detail))


def test_fetch_schema_tables_masks_credentials_in_driver_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = FakeEngine()
    monkeypatch.setattr(postgres_fetcher, "create_database_engine", lambda _: engine)
    monkeypatch.setattr(postgres_fetcher, "inspect", failing_inspect)
    with pytest.raises(ProcessingError) as caught:
        fetch_schema_tables(make_settings())
    texts = [str(caught.value), str(caught.value.__cause__), repr(caught.value)]
    leaked = any(SECRET_USER in t or SECRET_PASSWORD in t for t in texts)
    assert not leaked, "error text leaks a username or password"
    assert "db.local:5432/shop" in str(caught.value)
    assert engine.disposed
