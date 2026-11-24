"""Unit tests for the schema snapshot model. No database needed."""

import json
from pathlib import Path

import pytest

from brutal_sql.db.schema_model import (
    SNAPSHOT_FORMAT_VERSION,
    ColumnDetails,
    EnumDetails,
    ForeignKeyDetails,
    IndexDetails,
    InvalidSchemaFileError,
    PostgresSchemaObject,
    PrimaryKeyDetails,
    TableDetails,
    UniqueConstraintDetails,
)


def build_customers_table() -> TableDetails:
    """A table with a primary key, a unique constraint and an index."""
    return TableDetails(
        name="customers",
        columns=[
            ColumnDetails("id", "INTEGER", False, "nextval('customers_id_seq')"),
            ColumnDetails("email", "VARCHAR(200)", False, None),
        ],
        primary_key=PrimaryKeyDetails("customers_pkey", ["id"]),
        foreign_keys=[],
        unique_constraints=[UniqueConstraintDetails("customers_email_key", ["email"])],
        indexes=[IndexDetails("customers_email_key", ["email"], True)],
    )


def build_orders_table() -> TableDetails:
    """A table with a foreign key to customers and no unique constraints."""
    return TableDetails(
        name="orders",
        columns=[ColumnDetails("customer_id", "INTEGER", False, None)],
        primary_key=None,
        foreign_keys=[
            ForeignKeyDetails(
                "orders_customer_id_fkey",
                ["customer_id"],
                "shop",
                "customers",
                ["id"],
                "CASCADE",
                None,
            )
        ],
        unique_constraints=[],
        indexes=[],
    )


@pytest.fixture
def snapshot() -> PostgresSchemaObject:
    """A small two-table snapshot with one enum."""
    return PostgresSchemaObject(
        database_name="test",
        schema_name="shop",
        fetched_at="2026-11-24T10:00:00+00:00",
        tables=[build_customers_table(), build_orders_table()],
        enums=[EnumDetails("order_status", ["pending", "shipped", "delivered"])],
    )


# Positive tests


def test_dict_round_trip_gives_equal_object(snapshot: PostgresSchemaObject) -> None:
    assert PostgresSchemaObject.from_dict(snapshot.to_dict()) == snapshot


def test_json_round_trip_gives_equal_object(snapshot: PostgresSchemaObject) -> None:
    assert PostgresSchemaObject.from_json(snapshot.to_json()) == snapshot


def test_to_dict_is_plain_json_data(snapshot: PostgresSchemaObject) -> None:
    data = snapshot.to_dict()
    assert json.loads(json.dumps(data)) == data
    assert data["format_version"] == SNAPSHOT_FORMAT_VERSION
    assert data["tables"][0]["primary_key"] == {
        "name": "customers_pkey",
        "column_names": ["id"],
    }


def test_load_from_file_reads_saved_json(
    snapshot: PostgresSchemaObject, tmp_path: Path
) -> None:
    file_path = tmp_path / "snapshot.json"
    file_path.write_text(snapshot.to_json(), encoding="utf-8")
    assert PostgresSchemaObject.load_from_file(file_path) == snapshot


def test_find_table_returns_matching_table(snapshot: PostgresSchemaObject) -> None:
    orders = snapshot.find_table("orders")
    assert orders.foreign_keys[0].referred_table == "customers"
    assert orders.foreign_keys[0].on_delete == "CASCADE"
    assert orders.primary_key is None


def test_find_enum_keeps_value_order(snapshot: PostgresSchemaObject) -> None:
    assert snapshot.find_enum("order_status").values == [
        "pending",
        "shipped",
        "delivered",
    ]


def test_empty_schema_round_trips() -> None:
    empty = PostgresSchemaObject("test", "empty", "2026-11-24T10:00:00+00:00", [], [])
    assert PostgresSchemaObject.from_json(empty.to_json()) == empty


# Negative tests


def test_from_json_rejects_malformed_json() -> None:
    with pytest.raises(InvalidSchemaFileError, match="Not valid JSON"):
        PostgresSchemaObject.from_json("{not json")


def test_from_json_rejects_non_object() -> None:
    with pytest.raises(InvalidSchemaFileError, match="must be a JSON object"):
        PostgresSchemaObject.from_json("[1, 2, 3]")


def test_from_dict_rejects_missing_top_level_key(
    snapshot: PostgresSchemaObject,
) -> None:
    data = snapshot.to_dict()
    del data["schema_name"]
    with pytest.raises(InvalidSchemaFileError, match="schema_name"):
        PostgresSchemaObject.from_dict(data)


def test_from_dict_rejects_missing_table_key(snapshot: PostgresSchemaObject) -> None:
    data = snapshot.to_dict()
    del data["tables"][0]["indexes"]
    with pytest.raises(InvalidSchemaFileError, match="indexes"):
        PostgresSchemaObject.from_dict(data)


def test_from_dict_rejects_unknown_column_field(
    snapshot: PostgresSchemaObject,
) -> None:
    data = snapshot.to_dict()
    data["tables"][0]["columns"][0]["colour"] = "red"
    with pytest.raises(InvalidSchemaFileError, match="ColumnDetails"):
        PostgresSchemaObject.from_dict(data)


def test_from_dict_rejects_tables_that_are_not_a_list(
    snapshot: PostgresSchemaObject,
) -> None:
    data = snapshot.to_dict()
    data["tables"] = {"customers": {}}
    with pytest.raises(InvalidSchemaFileError, match="'tables' must be a list"):
        PostgresSchemaObject.from_dict(data)


def test_from_dict_rejects_unknown_format_version(
    snapshot: PostgresSchemaObject,
) -> None:
    data = snapshot.to_dict()
    data["format_version"] = 999
    with pytest.raises(InvalidSchemaFileError, match="format version"):
        PostgresSchemaObject.from_dict(data)


def test_find_table_raises_for_unknown_table(snapshot: PostgresSchemaObject) -> None:
    with pytest.raises(KeyError, match="invoices"):
        snapshot.find_table("invoices")


def test_find_enum_raises_for_unknown_enum(snapshot: PostgresSchemaObject) -> None:
    with pytest.raises(KeyError, match="colour"):
        snapshot.find_enum("colour")


def test_load_from_file_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        PostgresSchemaObject.load_from_file(tmp_path / "missing.json")
