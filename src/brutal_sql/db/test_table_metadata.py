"""Tests for the table metadata records."""

import pytest

from brutal_sql.db.table_metadata import (
    ColumnMetadata,
    ForeignKeyMetadata,
    IndexMetadata,
    TableMetadata,
)


def test_column_keeps_its_fields() -> None:
    column = ColumnMetadata("cid", "INTEGER", nullable=False, comment="cookie id")
    assert (column.name, column.data_type, column.nullable, column.comment) == (
        "cid",
        "INTEGER",
        False,
        "cookie id",
    )


@pytest.mark.parametrize("name, data_type", [("", "INTEGER"), ("id", ""), (None, "X")])
def test_column_rejects_blank_name_or_type(name: object, data_type: object) -> None:
    with pytest.raises(ValueError):
        ColumnMetadata(name, data_type)  # type: ignore[arg-type]


def test_index_keeps_columns_and_uniqueness() -> None:
    index = IndexMetadata("orders_customer_idx", ("customer_id",), unique=True)
    assert index.column_names == ("customer_id",) and index.unique


def test_index_rejects_no_columns() -> None:
    with pytest.raises(ValueError):
        IndexMetadata("empty_idx", ())


def test_foreign_key_reports_composite() -> None:
    single = ForeignKeyMetadata(("customer_id",), "shop", "customers", ("id",))
    double = ForeignKeyMetadata(("a", "b"), "shop", "pairs", ("x", "y"))
    assert not single.is_composite
    assert double.is_composite


@pytest.mark.parametrize(
    "columns, referred_table, referred_columns",
    [((), "customers", ()), (("a", "b"), "pairs", ("x",)), (("a",), "", ("x",))],
)
def test_foreign_key_rejects_invalid_columns(
    columns: tuple[str, ...], referred_table: str, referred_columns: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError):
        ForeignKeyMetadata(columns, "shop", referred_table, referred_columns)


def test_table_keeps_columns_and_keys() -> None:
    table = TableMetadata("customers", (ColumnMetadata("id", "INTEGER"),), ("id",))
    assert table.primary_key == ("id",)
    assert table.indexes == () and table.foreign_keys == ()


@pytest.mark.parametrize(
    "name, columns", [("", (ColumnMetadata("id", "INT"),)), ("t", ())]
)
def test_table_rejects_blank_name_or_no_columns(
    name: str, columns: tuple[ColumnMetadata, ...]
) -> None:
    with pytest.raises(ValueError):
        TableMetadata(name, columns)
